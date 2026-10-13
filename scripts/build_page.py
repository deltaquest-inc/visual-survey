#!/usr/bin/env python3
"""Build the respondent's correction page: each pick numbered, with Claude's description.

Usage: build_page.py <run_dir> <image_dir> --title "Pick Check" --intro "Your picks,
       numbered. For each one: is my description right?" [--source-url-template
       "https://example.com/{id}"]

Reads manifest.json and shows.json ({id: {shows, tags[]}}). Thumbnails are made with
`sips -Z 640` and embedded. Sections follow each pin's first category in manifest order.
Writes <run_dir>/page.html. The page expects a host that provides
claude.use with capabilities {db: {}, user: {}}; answers land in the "corrections" collection as
{status: ok|fix|"", note, n, at}, keyed by pin id.
"""
import argparse, base64, html, os, subprocess, sys, tempfile

from common import manifest as read_manifest, validate_assets, dump

HERE = os.path.dirname(os.path.abspath(__file__))
CIRCLED = '①②③④⑤⑥⑦⑧⑨⑩⑪⑫'


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('run_dir'); ap.add_argument('image_dir')
    ap.add_argument('--title', required=True); ap.add_argument('--intro', required=True)
    ap.add_argument('--respondent', help='Names the comment author on teammate pages')
    ap.add_argument('--source-url-template', default=os.environ.get('VS_SOURCE_URL_TEMPLATE'),
                    help='Optional link per image, e.g. https://example.com/{id}; env VS_SOURCE_URL_TEMPLATE')
    a = ap.parse_args()
    import json
    load = lambda f: json.load(open(os.path.join(a.run_dir, f)))
    manifest, shows = read_manifest(os.path.join(a.run_dir, 'manifest.json')), load('shows.json')
    dump(os.path.join(a.run_dir, 'assets.json'), validate_assets(manifest, a.image_dir))
    if a.source_url_template and '{id}' not in a.source_url_template:
        ap.error('--source-url-template must contain {id}')
    missing = [e['id'] for e in manifest if e['id'] not in shows]
    if missing:
        sys.exit(f'shows.json lacks {missing}')
    image_dir = os.path.expanduser(a.image_dir)
    sections = list(dict.fromkeys(e['category'][0] for e in manifest))
    by_shows = {}
    for n, e in enumerate(manifest, 1):
        by_shows.setdefault(shows[e['id']]['shows'], []).append(n)

    cards, last = [], None
    with tempfile.TemporaryDirectory() as tmp:
        for n, e in enumerate(manifest, 1):
            i, s = e['id'], shows[e['id']]
            sec = e['category'][0]
            if sec != last:
                k = sections.index(sec)
                label = f'{CIRCLED[k]} {sec}' if k < len(CIRCLED) else sec
                cards.append(f'<h2 class="sec">{html.escape(label)}</h2>')
                last = sec
            thumb = os.path.join(tmp, f'{i}.jpg')
            subprocess.run(['sips', '-Z', '640', '-s', 'format', 'jpeg',
                            os.path.join(image_dir, f'{i}.jpg'), '--out', thumb],
                           check=True, capture_output=True)
            src = 'data:image/jpeg;base64,' + base64.b64encode(open(thumb, 'rb').read()).decode()
            sib = [m for m in by_shows[s['shows']] if m != n]
            sibnote = (f'<p class="sib">One description covers this pin and #{", #".join(map(str, sib))}.</p>'
                       if sib else '')
            comments = ''.join(f'<li>{html.escape(c)}</li>' for c in e['comment'])
            tags = ''.join(f'<span class="tag">{html.escape(t)}</span>' for t in s.get('tags', []))
            img = f'<img src="{src}" alt="Pin {n}" loading="lazy">'
            if a.source_url_template:
                url = html.escape(a.source_url_template.replace('{id}', i), quote=True)
                img = f'<a href="{url}" target="_blank" rel="noopener">{img}</a>'
            cards.append(f'''<article class="card" id="p{n}" data-id="{i}" data-state="">
 <figure><span class="n">{n}</span>{img}</figure>
 <div class="body">
  <p class="label">What I see</p>
  <p class="shows">{html.escape(s['shows'].rstrip('.'))}.</p>{sibnote}
  <div class="tags">{tags}</div>
  <p class="label">Your comment</p>
  <ul class="yours">{comments}</ul>
  <div class="verdict" role="group" aria-label="Pin {n} verdict">
   <button type="button" class="ok" data-v="ok">Correct</button>
   <button type="button" class="fix" data-v="fix">Needs fixing</button>
  </div>
  <textarea id="note-{i}" rows="2" placeholder="What is wrong, or what it actually shows"></textarea>
  <p class="saved" aria-live="polite"></p>
 </div>
</article>''')
    tpl = open(os.path.join(HERE, 'page.tpl.html')).read()
    out = (tpl.replace('<!--CARDS-->', '\n'.join(cards)).replace('__TITLE__', html.escape(a.title))
           .replace('__INTRO__', html.escape(a.intro)).replace('__TOTAL__', str(len(manifest)))
           .replace('__SOURCE_NOTE__', ' The image opens the source page.' if a.source_url_template else ''))
    if a.respondent:
        out = out.replace('Your comment', html.escape(a.respondent) + '’s comment')
    dest = os.path.join(a.run_dir, 'page.html')
    open(dest, 'w').write(out)
    print(dest, f'{os.path.getsize(dest) / 1e6:.1f} MB')


if __name__ == '__main__':
    main()
