#!/usr/bin/env python3
"""Independent visual reviews. --reviewers codex claude_second selects Claude explicitly.
Default: codex gemini. --resume reuses only fingerprint-matched results;
--repair-missing --resume views missing Codex pins rather than guessing.
No automatic fallback on failures/quota. Files and hashes validated before any call.
"""
import argparse, json, os, subprocess, sys, re, hashlib, tempfile
from pathlib import Path
from common import dump, load, fingerprint, manifest, validate_assets, reviewers, check_pins

HERE = os.path.dirname(os.path.abspath(__file__))
# Model names have no default: pass --codex-model / --gemini-model / --claude-model
# (env VS_CODEX_MODEL / VS_GEMINI_MODEL / VS_CLAUDE_MODEL) for each reviewer you run.
CODEX_MODEL = os.environ.get('VS_CODEX_MODEL')
AGY_MODEL = os.environ.get('VS_GEMINI_MODEL')
CLAUDE_MODEL = os.environ.get('VS_CLAUDE_MODEL')


def read(p):
    return Path(p).read_text(encoding='utf-8')


def tag_prompt(entries, image_dir, respondent, context, attachments):
    files = []
    for k, e in enumerate(entries, 1):
        path = os.path.join(image_dir, f"{e['id']}.jpg")
        files.append(f"Attachment {k} = id {e['id']}, file {path}" if attachments
                     else f"{k}. id {e['id']}: {path}")
    manifest = [{'id': e['id'], 'category': e['category'], 'comment': e['comment']}
                for e in entries]
    return (read(os.path.join(HERE, 'prompt-tag.md'))
            .replace('{{RESPONDENT}}', respondent).replace('{{CONTEXT}}', context.strip())
            .replace('{{COUNT}}', str(len(entries))).replace('{{FILES}}', '\n'.join(files))
            .replace('{{MANIFEST}}', json.dumps(manifest, ensure_ascii=False, indent=1)))


def conclude_text(respondent):
    return read(os.path.join(HERE, 'prompt-conclude.md')).replace('{{RESPONDENT}}', respondent)


def schemas():
    full = load(Path(HERE, 'schema.json'))
    pins = {**full, 'properties': {'pins': full['properties']['pins']}, 'required': ['pins']}
    concl = {**full, 'properties': {'conclusions': full['properties']['conclusions']},
             'required': ['conclusions']}
    return full, pins, concl


def run(cmd, stdin, log, dry):
    if dry:
        print('DRY', ' '.join(c if ' ' not in c else repr(c[:60] + '…') for c in cmd))
        return None
    with open(log, 'a') as lf:
        r = subprocess.run(cmd, input=stdin, text=True, stdout=subprocess.PIPE, stderr=lf)
    if r.returncode:
        sys.exit(f'{cmd[0]} exited {r.returncode}; see {log}')
    return r.stdout


def codex_call(prompt, schema, out, images, raw, dry, resume=False):
    key = fingerprint({"prompt": prompt, "schema": schema, "model": CODEX_MODEL,
                       "images": [hashlib.sha256(Path(p).read_bytes()).hexdigest() for p in images]})
    meta = out + ".meta.json"
    if resume and Path(out).exists() and Path(meta).exists() and load(meta).get("fingerprint") == key:
        return load(out)
    sp = out + '.schema.json'
    dump(sp, schema)
    Path(out + '.prompt.md').write_text(prompt)
    cmd = ['codex', 'exec', '-m', CODEX_MODEL, '--ignore-user-config', '--ephemeral',
           '--skip-git-repo-check', '-s', 'read-only', '-C', raw,
           '--output-schema', sp, '-o', out, '-']
    for img in images:
        cmd += ['-i', img]
    run(cmd, prompt, os.path.join(raw, 'codex.log'), dry)
    if dry:
        return None
    text = read(out).strip() if os.path.exists(out) else ''
    if not text:
        sys.exit(f'codex: empty result in {out}')
    result = json.loads(text)
    dump(meta, {'fingerprint': key, 'model_requested': CODEX_MODEL})
    return result


def do_codex(entries, ids, image_dir, respondent, context, chunk, run_dir, raw, dry, resume=False, repair_missing=False):
    _, pin_schema, concl_schema = schemas()
    pins = []
    for start in range(0, len(entries), chunk):
        part = entries[start:start + chunk]
        imgs = [os.path.join(image_dir, f"{e['id']}.jpg") for e in part]
        res = codex_call(tag_prompt(part, image_dir, respondent, context, True), pin_schema,
                         os.path.join(raw, f'codex-chunk{start // chunk + 1}.json'), imgs, raw, dry, resume)
        if res and repair_missing:
            expected = [e['id'] for e in part]
            got = [p['id'] for p in res['pins']]
            if set(got) - set(expected) or len(got) != len(set(got)):
                raise ValueError('Cannot repair extra or duplicated Codex ids')
            if not got:
                raise ValueError('Empty Codex chunk; stop and inspect the raw failure')
            check_pins(res['pins'], got, 'Existing partial Codex chunk')
            missing = [e for e in part if e['id'] not in got]
            if missing:
                repair = codex_call(tag_prompt(missing, image_dir, respondent, context, True), pin_schema,
                                    os.path.join(raw, f'codex-chunk{start // chunk + 1}-repair.json'),
                                    [os.path.join(image_dir, e['id']+'.jpg') for e in missing], raw, dry, resume)
                if repair:
                    res['pins'] += check_pins(repair['pins'], [e['id'] for e in missing], 'Codex repair')
                    check_pins(res['pins'], expected, 'Repaired chunk')
                    dump(os.path.join(raw, f'codex-chunk{start // chunk + 1}.json'), res)
        if res:
            pins += check_pins(res['pins'], [e['id'] for e in part], f'codex chunk {start // chunk + 1}')
    manifest = [{'id': e['id'], 'category': e['category'], 'comment': e['comment']} for e in entries]
    prompt = (f'You are an art director. Product context:\n{context.strip()}\n\n'
              f'Below are image tags another pass made for {len(entries)} pins that {respondent} '
              'picked, and the survey manifest with their own comments. You do not see the images.\n\n'
              + conclude_text(respondent) + '\n\nTags:\n' + json.dumps(pins, ensure_ascii=False)
              + '\n\nManifest:\n' + json.dumps(manifest, ensure_ascii=False))
    res = codex_call(prompt, concl_schema, os.path.join(raw, 'codex-conclusions.json'), [], raw, dry, resume)
    if dry:
        return
    pins = check_pins(pins, ids, 'codex')
    reported = re.findall(r'^model:\s*(\S+)', read(os.path.join(raw, 'codex.log')), re.M)
    if not res or not res.get('conclusions'):
        raise ValueError('Codex returned empty conclusions')
    dump(Path(run_dir, 'codex.json'), {'model': reported[-1] if reported else CODEX_MODEL, 'model_requested': CODEX_MODEL,
               'model_source': 'runtime' if reported else 'explicit CLI selection',
               'reviewer': 'codex', 'pins': pins, 'conclusions': res['conclusions']})
    print('codex.json written')


def do_gemini(entries, ids, image_dir, respondent, context, run_dir, raw, dry, resume=False):
    full, _, _ = schemas()
    # The closing rules block matters: without it the CLI can end on a denied shell call.
    # Keep its wording and the paths last.
    paths = [os.path.join(image_dir, f"{e['id']}.jpg") for e in entries]
    prompt = (tag_prompt(entries, image_dir, respondent, context, False) + '\n'
              + conclude_text(respondent) + '\n\nRules for this run: do NOT run any terminal '
              'command and do NOT write any file (both are blocked and will abort the run). '
              f'Use only your file-viewing tool on these {len(paths)} absolute paths, then give '
              'the JSON as your final answer:\n' + '\n'.join(paths) + '\n')
    Path(raw, 'gemini.prompt.md').write_text(prompt)
    sp = os.path.join(raw, 'gemini.schema.json')
    dump(sp, full)
    cmd = ['agy', '-p', prompt, '--model', AGY_MODEL, '--add-dir', image_dir, '--mode', 'plan',
           '--json-schema', sp, '--output-format', 'json', '--print-timeout', '1800s']
    output = Path(raw, 'gemini-out.json'); meta = Path(raw, 'gemini-out.meta.json')
    key = fingerprint({'prompt': prompt, 'schema': full, 'model': AGY_MODEL, 'assets': validate_assets(entries, image_dir)})
    if resume and output.exists() and meta.exists() and load(meta).get('fingerprint') == key:
        d = load(output)
    else:
        out = run(cmd, None, os.path.join(raw, 'gemini.log'), dry)
        if dry:
            return
        output.write_text(out)
        d = json.loads(out)
    if d.get('denied_actions'):
        sys.exit(f"agy: tools denied {d['denied_actions']}; the prompt must keep it to viewing files")
    if d.get('status') != 'SUCCESS':
        sys.exit(f"agy: status {d.get('status')}; see raw/gemini-out.json")
    res = d.get('structured_output') or d.get('response') or ''
    if isinstance(res, str):
        if not res.strip():
            sys.exit('agy: empty response (often a denied tool or quota); see raw/gemini-out.json')
        res = json.loads(res)
    pins = check_pins(res['pins'], ids, 'gemini')
    if not res.get('conclusions'):
        raise ValueError('Gemini returned empty conclusions')
    dump(meta, {'fingerprint': key})
    dump(Path(run_dir, 'gemini.json'), {'model': d.get('model') or AGY_MODEL, 'model_requested': AGY_MODEL,
               'model_source': 'runtime' if d.get('model') else 'explicit CLI selection',
               'reviewer': 'gemini', 'pins': pins, 'conclusions': res['conclusions'],
               'usage': d.get('usage'), 'duration_seconds': d.get('duration_seconds')})
    print('gemini.json written')


def do_claude(entries, ids, image_dir, respondent, context, run_dir, raw, dry, resume=False):
    full, _, _ = schemas()
    prompt = (tag_prompt(entries, image_dir, respondent, context, False) + '\n' + conclude_text(respondent)
              + '\nUse only Read to view these images. Do not read any other reviews. Return the complete schema JSON.')
    output = Path(raw) / 'claude_second-out.json'
    meta = output.with_suffix('.meta.json')
    key = fingerprint({'prompt': prompt, 'schema': full, 'model': CLAUDE_MODEL,
                       'assets': validate_assets(entries, image_dir)})
    Path(raw, 'claude_second.prompt.md').write_text(prompt)
    cmd = ['claude', '-p', prompt, '--model', CLAUDE_MODEL, '--output-format', 'json',
           '--json-schema', json.dumps(full), '--tools', 'Read', '--allowedTools', 'Read',
           '--add-dir', image_dir, '--no-session-persistence', '--setting-sources', '']
    if resume and output.exists() and meta.exists() and load(meta).get('fingerprint') == key:
        d = load(output)
    else:
        # Fresh session outside any repo. No inherited previous-review context.
        if dry:
            run(cmd, None, str(Path(raw, 'claude_second.log')), True)
            return
        with open(Path(raw, 'claude_second.log'), 'a') as log:
            r = subprocess.run(cmd, cwd=tempfile.gettempdir(), text=True, stdout=subprocess.PIPE, stderr=log)
        if r.returncode:
            raise ValueError(f'Claude exited {r.returncode}; see claude_second.log')
        d = json.loads(r.stdout)
        dump(output, d)
    if d.get('is_error') or d.get('permission_denials') or d.get('denied_actions'):
        raise ValueError('Claude failed or tools denied; see raw result')
    res = d.get('structured_output')
    if not isinstance(res, dict) or not res.get('conclusions'):
        raise ValueError('Claude returned empty structured result')
    actual = list(d.get('modelUsage', {}))
    if not actual:
        raise ValueError('Claude returned no actual model metadata')
    pins = check_pins(res['pins'], ids, 'claude_second')
    dump(meta, {'fingerprint': key})
    dump(Path(run_dir, 'claude_second.json'), {'reviewer': 'claude_second', 'model': actual,
         'model_requested': CLAUDE_MODEL, 'model_source': 'runtime', 'pins': pins,
         'conclusions': res['conclusions'], 'usage': d.get('usage')})
    print('claude_second.json written')


def main():
    global CODEX_MODEL, AGY_MODEL, CLAUDE_MODEL
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('run_dir'); ap.add_argument('image_dir')
    ap.add_argument('--respondent', default='the respondent')
    ap.add_argument('--reviewers', nargs=2, choices=['codex', 'gemini', 'claude_second'])
    ap.add_argument('--only', choices=['codex', 'gemini', 'claude_second'])
    ap.add_argument('--chunk', type=int, default=15)
    ap.add_argument('--codex-model', default=CODEX_MODEL, help='env VS_CODEX_MODEL')
    ap.add_argument('--gemini-model', default=AGY_MODEL, help='env VS_GEMINI_MODEL')
    ap.add_argument('--claude-model', default=CLAUDE_MODEL, help='env VS_CLAUDE_MODEL')
    ap.add_argument('--dry-run', action='store_true')
    ap.add_argument('--resume', action='store_true')
    ap.add_argument('--repair-missing', action='store_true')
    a = ap.parse_args()
    if a.chunk < 1 or (a.repair_missing and not a.resume):
        ap.error('chunk must be positive; --repair-missing requires --resume')
    CODEX_MODEL, AGY_MODEL, CLAUDE_MODEL = a.codex_model, a.gemini_model, a.claude_model
    run_dir, image_dir = os.path.abspath(a.run_dir), os.path.abspath(os.path.expanduser(a.image_dir))
    entries = manifest(Path(run_dir, 'manifest.json'))
    anchor = load(Path(run_dir, 'claude.json'))
    if set(anchor) != {e['id'] for e in entries} or not all(isinstance(v, str) and v.strip() for v in anchor.values()):
        raise ValueError('Complete first-read claude.json required before model review')
    assets = validate_assets(entries, image_dir)
    dump(Path(run_dir, 'assets.json'), assets)
    print(f"Validated {len(entries)} pins; duplicate image groups: {assets['duplicate_images']}")
    selected = reviewers(run_dir, a.reviewers)
    if a.only and a.only not in selected:
        ap.error('--only must be one of --reviewers (or the saved reviewers.json)')
    cfg = Path(run_dir, 'reviewers.json')
    if cfg.exists() and load(cfg)['reviewers'] != selected:
        ap.error('Reviewer selection changed: use a new run directory to avoid stale adjudication')
    dump(cfg, {'reviewers': selected})
    for role, model, flag in (('codex', CODEX_MODEL, '--codex-model'), ('gemini', AGY_MODEL, '--gemini-model'),
                              ('claude_second', CLAUDE_MODEL, '--claude-model')):
        if role in ([a.only] if a.only else selected) and not model:
            ap.error(f'{flag} (or its VS_*_MODEL env var) is required for reviewer {role}')
    ids = [e['id'] for e in entries]
    context = read(os.path.join(run_dir, 'context.md'))
    raw = os.path.join(run_dir, 'raw'); os.makedirs(raw, exist_ok=True)
    for role in ([a.only] if a.only else selected):
        if role == 'codex':
            do_codex(entries, ids, image_dir, a.respondent, context, a.chunk, run_dir, raw, a.dry_run, a.resume, a.repair_missing)
        elif role == 'gemini':
            do_gemini(entries, ids, image_dir, a.respondent, context, run_dir, raw, a.dry_run, a.resume)
        else:
            do_claude(entries, ids, image_dir, a.respondent, context, run_dir, raw, a.dry_run, a.resume)


if __name__ == '__main__':
    try:
        main()
    except (ValueError, KeyError, OSError, IndexError) as e:
        sys.exit(str(e))
