#!/usr/bin/env python3
"""Outline and saturation counts per sentiment, on final labels.

Usage: counts.py <run_dir>

Final label per pin and field: Claude's value in adjudication.json when present;
otherwise the value both models agree on, ignoring a model adjudication.json marks as
misaligned for that pin. A pin with no final label stops the run. Writes counts.md and
final-labels.json. The counts show a direction, not a rule: the labels are coarse.
"""
import collections, json, os, sys, argparse
from common import manifest as load_manifest, reviewers, read_reviews, adjudication_fingerprint

FIELDS = {'outline': ['bold', 'medium', 'thin', 'none'], 'saturation': ['high', 'medium', 'low']}


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('run_dir'); ap.add_argument('--reviewers', nargs=2, choices=['codex', 'gemini', 'claude_second'])
    a = ap.parse_args(); d = a.run_dir
    models = reviewers(d, a.reviewers)
    load = lambda f: json.load(open(os.path.join(d, f)))
    manifest = load_manifest(os.path.join(d, 'manifest.json'))
    rev = read_reviews(d, manifest, models)
    adj = load('adjudication.json') if os.path.exists(os.path.join(d, 'adjudication.json')) else {}

    meta_path = os.path.join(d, 'adjudication.meta.json')
    if not os.path.exists(meta_path) or load('adjudication.meta.json').get('fingerprint') != adjudication_fingerprint(d, manifest, models):
        sys.exit('Missing/stale adjudication fingerprint: run compare.py and re-view changed inputs first')
    legacy = load('adjudication.meta.json').get('legacy_adopted', False)
    final, open_items = {}, []
    for e in manifest:
        i, a = e['id'], adj.get(e['id'], {})
        if a and not (a.get('resolved') is True or (legacy and 'resolved' not in a)):
            sys.exit(f'{i}: adjudication is unresolved; re-view and set resolved: true')
        if set(a.get('misaligned', [])) - set(models):
            sys.exit(f'{i}: adjudication names an unselected reviewer')
        for field, levels in FIELDS.items():
            if field in a and a[field] is None:
                sys.exit(f'{i}: unresolved null {field}')
            if a.get(field) is not None and a[field] not in levels:
                sys.exit(f'{i}: invalid adjudicated {field}')
        final[i] = {}
        for f in FIELDS:
            if a.get(f):
                final[i][f] = a[f]
                continue
            vals = {rev[m][i][f] for m in models if m not in a.get('misaligned', [])}
            if len(vals) == 1:
                final[i][f] = vals.pop()
            else:
                open_items.append(f'{i} {f}')
    if open_items:
        sys.exit('No final label (fill adjudication.json): ' + ', '.join(open_items))

    groups = sorted({e['sentiment'] for e in manifest}) + ['all']
    out = ['# Outline and saturation counts', '',
           'Final labels: model agreement, or Claude\'s adjudication after viewing the image. '
           'Coarse labels; read as a direction, not a rule.', '']
    for f, levels in FIELDS.items():
        cnt = {g: collections.Counter() for g in groups}
        for e in manifest:
            v = final[e['id']][f]
            cnt[e['sentiment']][v] += 1
            cnt['all'][v] += 1
        out += [f'| {f} | ' + ' | '.join(levels) + ' | n |', '|' + '---|' * (len(levels) + 2)]
        out += [f'| {g} | ' + ' | '.join(str(cnt[g][l]) for l in levels) + f' | {sum(cnt[g].values())} |'
                for g in groups]
        out.append('')
    agree = sum(1 for e in manifest for f in FIELDS
                if len({rev[m][e['id']][f] for m in models}) == 1)
    out.append(f'Raw model agreement: {agree} of {len(manifest) * len(FIELDS)} labels.')
    open(os.path.join(d, 'counts.md'), 'w').write('\n'.join(out) + '\n')
    json.dump(final, open(os.path.join(d, 'final-labels.json'), 'w'), indent=1)
    print('\n'.join(out))


if __name__ == '__main__':
    main()
