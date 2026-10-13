#!/usr/bin/env python3
"""Cross-check the two model reviews against Claude's own first read.

Usage: compare.py <run_dir>

Reads manifest.json, claude.json ({id: one-line subject}, written by Claude from the
images before any model ran), codex.json and gemini.json. Writes:
- disagreements.md: pins where a model's subject shares too few words with the other two
  (possibly describing a different image; expect false flags, Claude views each one), and
  every outline/saturation disagreement;
- adjudication.json: one entry per flagged pin for Claude to fill after viewing the image
  ({misaligned: [models], outline, saturation, note}); null values still need a verdict.
An existing adjudication.json is never overwritten.
"""
import json, os, re, sys, argparse
from common import manifest, reviewers, read_reviews, adjudication_fingerprint, dump, load as read_json

FIELDS = ('outline', 'saturation')
STOP = set('''a an the and or of in on at to with without from by for over under into its his
her their this that these those is are was were be been very some one two three small large
big tiny huge background foreground image picture shows showing view scene style art digital
illustration painting render rendering concept against while which who where near behind front
left right top bottom side single several other'''.split())
# Recall screen, not a verdict: a low threshold keeps recall high at the cost of false flags.
THRESHOLD = 0.20


def words(s):
    return {w for w in re.findall(r'[a-z]{3,}', s.lower()) if w not in STOP}


def overlap(a, b):
    a, b = words(a), words(b)
    return len(a & b) / min(len(a), len(b)) if a and b else 0.0


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('run_dir'); ap.add_argument('--reviewers', nargs=2, choices=['codex', 'gemini', 'claude_second'])
    ap.add_argument('--adopt-legacy-adjudication', action='store_true', help='Only after checking legacy adjudication belongs to these unchanged inputs')
    a = ap.parse_args(); d = a.run_dir
    models = reviewers(d, a.reviewers)
    load = lambda f: json.load(open(os.path.join(d, f)))
    entries = manifest(os.path.join(d, 'manifest.json'))
    ids = [e['id'] for e in entries]
    claude = load('claude.json')
    rev = read_reviews(d, entries, models)
    missing = [i for i in ids if i not in claude]
    if missing:
        sys.exit(f'claude.json lacks subjects for {missing}')

    signature = adjudication_fingerprint(d, entries, models)
    meta = os.path.join(d, 'adjudication.meta.json')
    adj = os.path.join(d, 'adjudication.json')
    if os.path.exists(meta) and read_json(meta).get('fingerprint') != signature:
        sys.exit('Stale adjudication: inputs changed. Preserve old evidence and use a new run directory; re-view flags.')
    if os.path.exists(adj) and not os.path.exists(meta) and not a.adopt_legacy_adjudication:
        sys.exit('Legacy adjudication has no input fingerprint. Verify provenance, then explicitly --adopt-legacy-adjudication.')

    flags = {}
    lines = ['# Review disagreements', '',
             f'Subject check: a model is flagged when its subject shares under {THRESHOLD:.0%} of '
             'content words with both the other model and Claude. View the image before deciding.', '',
             '## Possible misalignment', '']
    for n, i in enumerate(ids, 1):
        s = {'claude': claude[i], **{m: rev[m][i]['subject'] for m in models}}
        bad = [m for m in models
               if overlap(s[m], s['claude']) < THRESHOLD and
               overlap(s[m], s[[x for x in models if x != m][0]]) < THRESHOLD]
        if bad:
            flags.setdefault(i, {})['misaligned'] = bad
            lines += [f'- #{n} `{i}` flagged: {", ".join(bad)}',
                      *[f'  - {k}: {v}' for k, v in s.items()]]
    if not any('misaligned' in f for f in flags.values()):
        lines.append('None.')

    for field in FIELDS:
        lines += ['', f'## {field.capitalize()} disagreements', '']
        rows = 0
        for n, i in enumerate(ids, 1):
            v = {m: rev[m][i][field] for m in models}
            if len(set(v.values())) > 1:
                flags.setdefault(i, {})[field] = None
                lines.append(f'- #{n} `{i}`: ' + ', '.join(f'{m} {x}' for m, x in v.items()))
                rows += 1
        if not rows:
            lines.append('None.')

    lines += ['', '## Marks named by only one model', '']
    for n, i in enumerate(ids, 1):
        mk = {m: set(rev[m][i]['marks']) for m in models}
        if bool(mk[models[0]]) != bool(mk[models[1]]):
            lines.append(f'- #{n} `{i}`: ' + '; '.join(f'{m}: {", ".join(sorted(x)) or "none"}'
                                                       for m, x in mk.items()))

    open(os.path.join(d, 'disagreements.md'), 'w').write('\n'.join(lines) + '\n')
    adj = os.path.join(d, 'adjudication.json')
    if os.path.exists(adj):
        print('adjudication.json exists; left untouched')
    else:
        tpl = {i: {'resolved': False, 'misaligned': f.get('misaligned', []),
                   **{k: None for k in FIELDS if k in f or f.get('misaligned')},
                   'note': ''} for i, f in flags.items()}
        json.dump(tpl, open(adj, 'w'), ensure_ascii=False, indent=1)
    prior_legacy = read_json(meta).get('legacy_adopted', False) if os.path.exists(meta) else False
    dump(meta, {'fingerprint': signature, 'legacy_adopted': prior_legacy or bool(a.adopt_legacy_adjudication)})
    mis = sum(1 for f in flags.values() if f.get('misaligned'))
    print(f'{mis} pins flagged for misalignment, {len(flags)} pins to adjudicate')


if __name__ == '__main__':
    main()
