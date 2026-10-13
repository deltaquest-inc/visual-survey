import importlib.util
import json
import os
import pathlib
import struct
import subprocess
import sys
import tempfile
import unittest
import zlib
from unittest.mock import patch

S = pathlib.Path(__file__).resolve().parents[1] / 'scripts'
sys.path.insert(0, str(S))
import common
import review


def png(rgb=b'\x00\x80\xff'):
    def chunk(kind, data):
        return struct.pack('>I', len(data)) + kind + data + struct.pack('>I', zlib.crc32(kind+data))
    return b'\x89PNG\r\n\x1a\n' + chunk(b'IHDR', struct.pack('>IIBBBBB', 1, 1, 8, 2, 0, 0, 0)) + chunk(b'IDAT', zlib.compress(b'\x00'+rgb)) + chunk(b'IEND', b'')


def pin(i):
    return {'id': i, 'subject': 'Armoured white vehicle in rocky canyon', 'palette': ['white'],
            'light': 'sun', 'rendering': 'flat', 'outline': 'none', 'saturation': 'medium',
            'composition': 'wide', 'mood': 'calm', 'marks': [], 'tags': [], 'reading_vs_comment': 'matches'}


class Workflow(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = pathlib.Path(self.tmp.name)
        self.run = self.root / 'run'; self.run.mkdir()
        self.images = self.root / 'images'; self.images.mkdir()
        self.raw = self.run / 'raw'; self.raw.mkdir()
        self.entries = [{'id': i, 'category': ['Art style', 'Painterly'], 'comment': ['warm'], 'sentiment': 'like'} for i in ['1', '2']]
        common.dump(self.run/'manifest.json', self.entries)
        common.dump(self.run/'claude.json', {e['id']: pin(e['id'])['subject'] for e in self.entries})
        (self.run/'context.md').write_text('Candidate only. Final style blank.')
        (self.raw/'codex.log').write_text('model: fixture-codex\n')
        review.CODEX_MODEL, review.AGY_MODEL, review.CLAUDE_MODEL = 'fixture-codex', 'fixture-gemini', 'fixture-claude'
        for e in self.entries:
            (self.images/(e['id']+'.jpg')).write_bytes(png())

    def tearDown(self):
        self.tmp.cleanup()

    def test_assets_duplicates_corruption_and_manifest(self):
        assets = common.validate_assets(self.entries, self.images)
        self.assertEqual(assets['duplicate_images'], [['1','2']])
        self.assertEqual(assets['assets']['1']['width'], 1)
        (self.images/'2.jpg').write_bytes(b'not an image')
        with self.assertRaises(ValueError): common.validate_assets(self.entries, self.images)
        common.dump(self.run/'manifest.json', [self.entries[0]]*2)
        with self.assertRaises(ValueError): common.manifest(self.run/'manifest.json')

    def test_cache_reuses_only_matching_images(self):
        out = str(self.raw/'chunk.json')
        def fake_run(cmd, stdin, log, dry): common.dump(out, {'pins': [pin('1')]})
        with patch.object(review, 'run', side_effect=fake_run) as call:
            review.codex_call('prompt', {}, out, [str(self.images/'1.jpg')], str(self.raw), False, True)
            review.codex_call('prompt', {}, out, [str(self.images/'1.jpg')], str(self.raw), False, True)
            self.assertEqual(call.call_count, 1)
            (self.images/'1.jpg').write_bytes(png(b'\xff\x00\x00'))
            review.codex_call('prompt', {}, out, [str(self.images/'1.jpg')], str(self.raw), False, True)
            self.assertEqual(call.call_count, 2)

    def test_targeted_missing_read_and_extra_stop(self):
        calls = []
        def fake(prompt, schema, out, images, raw, dry, resume):
            calls.append([pathlib.Path(i).stem for i in images])
            if 'repair' in out: return {'pins': [pin('2')]}
            if 'conclusions' in out: return {'conclusions': {'direction_summary': 'proposal'}}
            return {'pins': [pin('1')]}
        with patch.object(review, 'codex_call', side_effect=fake):
            review.do_codex(self.entries, ['1','2'], str(self.images), 'Name', 'context', 15, str(self.run), str(self.raw), False, True, True)
        self.assertEqual(calls, [['1','2'], ['2'], []])
        self.assertEqual(len(common.load(self.run/'codex.json')['pins']), 2)
        with patch.object(review, 'codex_call', return_value={'pins': [pin('3')]}):
            with self.assertRaises(ValueError):
                review.do_codex(self.entries, ['1','2'], str(self.images), 'Name', '', 15, str(self.run), str(self.raw), False, True, True)

    def test_claude_denial_stops(self):
        raw = {'is_error': False, 'permission_denials': ['Read'], 'structured_output': {'pins': [pin('1'),pin('2')], 'conclusions': {'x':'y'}}, 'modelUsage': {'fixture-claude': {}}}
        result = subprocess.CompletedProcess([], 0, json.dumps(raw))
        with patch.object(review.subprocess, 'run', return_value=result):
            with self.assertRaises(ValueError):
                review.do_claude(self.entries, ['1','2'], str(self.images), 'Name', '', str(self.run), str(self.raw), False)

    def test_selected_reviewers_compare_and_counts(self):
        common.dump(self.run/'reviewers.json', {'reviewers': ['codex','claude_second']})
        for role in ['codex','claude_second']:
            common.dump(self.run/(role+'.json'), {'pins':[pin('1'),pin('2')]})
        for name in ['compare.py', 'counts.py']:
            subprocess.run([sys.executable, str(S/name), str(self.run)], check=True, capture_output=True)
        self.assertEqual(len(common.load(self.run/'final-labels.json')), 2)
        common.dump(self.run/'adjudication.json', {'1': {'misaligned':['gemini']}})
        result = subprocess.run([sys.executable, str(S/'counts.py'), str(self.run)], capture_output=True)
        self.assertNotEqual(result.returncode, 0)

    def test_failed_verdict_survives_snapshot(self):
        template = (S/'page.tpl.html').read_text()
        js = template.split('<script>', 1)[1].split('</script>', 1)[0]
        script = """import assert from 'node:assert/strict'; import vm from 'node:vm';
const elements=new Map();const el=id=>{if(!elements.has(id))elements.set(id,{style:{},addEventListener(){}});return elements.get(id);};
const buttons=['ok','fix'].map(v=>({dataset:{v},handlers:{},setAttribute(){},addEventListener(k,f){this.handlers[k]=f;}}));
const ta={value:'',handlers:{},addEventListener(k,f){this.handlers[k]=f;},focus(){}};const saved={textContent:''};
const card={id:'p1',dataset:{id:'1',state:''},querySelector(q){return q==='.ok'?buttons[0]:q==='.fix'?buttons[1]:q==='textarea'?ta:saved;},querySelectorAll(){return buttons;}};
let snapshot;const col={doc(){return {async set(){throw Error('offline');}};},onSnapshot(fn){snapshot=fn;}};
const context={document:{activeElement:null,querySelectorAll(q){return q==='.card'?[card]:[];},getElementById:el},window:{claude:true},claude:{async use(){return {collection(){return col;}};}},setTimeout(){return 1;},clearTimeout(){}};
await vm.runInNewContext(SCRIPT,context);buttons[1].handlers.click();await new Promise(resolve=>setImmediate(resolve));
assert.match(saved.textContent,/Not saved/);snapshot({docs:[{id:'1',data:()=>({status:'ok',note:''})}]});assert.equal(card.dataset.state,'fix');
""".replace('SCRIPT', json.dumps(js))
        p = self.root/'draft.mjs'; p.write_text(script)
        subprocess.run(['node', str(p)], check=True, capture_output=True)

    def test_inflight_old_save_cannot_erase_new_note(self):
        js = (S/'page.tpl.html').read_text().split('<script>',1)[1].split('</script>',1)[0]
        script = """import assert from 'node:assert/strict'; import vm from 'node:vm';
const elements=new Map();const el=id=>{if(!elements.has(id))elements.set(id,{style:{},addEventListener(){}});return elements.get(id);};
const buttons=['ok','fix'].map(v=>({dataset:{v},handlers:{},setAttribute(){},addEventListener(k,f){this.handlers[k]=f;}}));
const ta={value:'',handlers:{},addEventListener(k,f){this.handlers[k]=f;},focus(){}};const saved={textContent:''};
const card={id:'p1',dataset:{id:'1',state:''},querySelector(q){return q==='.ok'?buttons[0]:q==='.fix'?buttons[1]:q==='textarea'?ta:saved;},querySelectorAll(){return buttons;}};
let snapshot,resolveWrite;const col={doc(){return {set(){return new Promise(resolve=>{resolveWrite=resolve;});}};},onSnapshot(fn){snapshot=fn;}};
const context={document:{activeElement:null,querySelectorAll(q){return q==='.card'?[card]:[];},getElementById:el},window:{claude:true},claude:{async use(){return {collection(){return col;}};}},setTimeout(){return 1;},clearTimeout(){}};
await vm.runInNewContext(SCRIPT,context);buttons[1].handlers.click();ta.value='newer correction';ta.handlers.input();resolveWrite();await new Promise(resolve=>setImmediate(resolve));
assert.equal(saved.textContent,'Unsaved changes');snapshot({docs:[{id:'1',data:()=>({status:'fix',note:''})}]});assert.equal(ta.value,'newer correction');
""".replace('SCRIPT',json.dumps(js))
        p=self.root/'inflight.mjs';p.write_text(script)
        subprocess.run(['node',str(p)],check=True,capture_output=True)

    def test_unresolved_null_and_stale_adjudication_stop(self):
        common.dump(self.run/'reviewers.json', {'reviewers':['codex','claude_second']})
        for role in ['codex','claude_second']:
            common.dump(self.run/(role+'.json'), {'model':'fixture','pins':[pin('1'),pin('2')]})
        subprocess.run([sys.executable,str(S/'compare.py'),str(self.run)],check=True,capture_output=True)
        for adjudication, message in [({'1':{'resolved':False,'misaligned':['codex']}},'unresolved'), ({'1':{'resolved':True,'misaligned':[],'outline':None}},'null')]:
            common.dump(self.run/'adjudication.json',adjudication)
            result=subprocess.run([sys.executable,str(S/'counts.py'),str(self.run)],capture_output=True,text=True)
            self.assertNotEqual(result.returncode,0);self.assertIn(message,result.stderr)
        common.dump(self.run/'adjudication.json',{})
        data=common.load(self.run/'codex.json');data['model']='changed';common.dump(self.run/'codex.json',data)
        for command in ['compare.py','counts.py']:
            result=subprocess.run([sys.executable,str(S/command),str(self.run)],capture_output=True,text=True)
            self.assertNotEqual(result.returncode,0);self.assertIn('adjudication',result.stderr)

    def test_legacy_adoption_survives_unchanged_compare(self):
        common.dump(self.run/'reviewers.json', {'reviewers':['codex','claude_second']})
        for role in ['codex','claude_second']:
            common.dump(self.run/(role+'.json'), {'pins':[pin('1'),pin('2')]})
        common.dump(self.run/'adjudication.json', {'1':{'misaligned':[],'outline':'thin'}})
        subprocess.run([sys.executable,str(S/'compare.py'),str(self.run),'--adopt-legacy-adjudication'],check=True,capture_output=True)
        subprocess.run([sys.executable,str(S/'compare.py'),str(self.run)],check=True,capture_output=True)
        subprocess.run([sys.executable,str(S/'counts.py'),str(self.run)],check=True,capture_output=True)
        self.assertTrue(common.load(self.run/'adjudication.meta.json')['legacy_adopted'])

    def test_source_link_is_optional(self):
        common.dump(self.run/'shows.json', {i:{'shows':pin(i)['subject'],'tags':[]} for i in ['1','2']})
        cmd = [sys.executable, str(S/'build_page.py'), str(self.run), str(self.images), '--title','Test Check','--intro','Two picks','--respondent','Alex']
        env = {k: v for k, v in os.environ.items() if k != 'VS_SOURCE_URL_TEMPLATE'}
        subprocess.run(cmd, check=True, capture_output=True, env=env)
        page = (self.run/'page.html').read_text()
        self.assertIn('Alex’s comment', page); self.assertIn('claude.use', page)
        self.assertNotIn('https://example.com/', page); self.assertNotIn('opens the source page', page)
        subprocess.run(cmd+['--source-url-template','https://example.com/{id}'], check=True, capture_output=True, env=env)
        page = (self.run/'page.html').read_text()
        self.assertIn('href="https://example.com/1"', page); self.assertIn('opens the source page', page)


if __name__ == '__main__': unittest.main()
