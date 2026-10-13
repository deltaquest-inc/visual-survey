"""Shared validation for visual-survey runs. No network access."""
import hashlib
import json
import os
import struct
from pathlib import Path

REVIEWERS = ('codex', 'gemini', 'claude_second')


def dump(path, value):
    path = Path(path)
    tmp = path.with_name(path.name + f'.{os.getpid()}.tmp')
    tmp.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')
    tmp.replace(path)


def load(path):
    return json.loads(Path(path).read_text())


def fingerprint(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def manifest(path):
    entries = load(path)
    if not isinstance(entries, list) or not entries:
        raise ValueError('Manifest must be a nonempty list')
    seen = set()
    for e in entries:
        i = e.get('id')
        if not isinstance(i, str) or not i.isdigit() or i in seen:
            raise ValueError(f'Invalid or duplicate pin id: {i}')
        seen.add(i)
        if e.get('sentiment') not in ('like', 'mixed', 'dislike'):
            raise ValueError(f'Invalid sentiment: {i}')
        for key in ('category', 'comment'):
            if not isinstance(e.get(key), list) or not e[key] or not all(isinstance(x, str) and x.strip() for x in e[key]):
                raise ValueError(f'{i}: {key} must contain nonempty strings')
    return entries


def dimensions(data):
    if data.startswith(b'\x89PNG\r\n\x1a\n') and len(data) >= 24:
        return struct.unpack('>II', data[16:24])
    if not data.startswith(b'\xff\xd8'):
        raise ValueError('Expected JPEG or PNG image')
    pos = 2
    while pos < len(data):
        if data[pos] != 255:
            raise ValueError('Invalid JPEG marker')
        while pos < len(data) and data[pos] == 255:
            pos += 1
        marker = data[pos]; pos += 1
        if marker in (0xD8, 0xD9) or 0xD0 <= marker <= 0xD7:
            continue
        length = int.from_bytes(data[pos:pos+2], 'big')
        if length < 2 or pos + length > len(data):
            raise ValueError('Truncated JPEG')
        if marker in (0xC0, 0xC1, 0xC2, 0xC3, 0xC5, 0xC6, 0xC7, 0xC9, 0xCA, 0xCB, 0xCD, 0xCE, 0xCF):
            height, width = struct.unpack('>HH', data[pos+3:pos+7])
            return width, height
        if marker == 0xDA:
            break
        pos += length
    raise ValueError('No JPEG dimensions found')


def validate_assets(entries, image_dir):
    assets = {}
    groups = {}
    for e in entries:
        p = (Path(image_dir).expanduser().resolve() / (e['id'] + '.jpg'))
        data = p.read_bytes()
        width, height = dimensions(data)
        if not width or not height:
            raise ValueError(f'Empty image: {p}')
        digest = hashlib.sha256(data).hexdigest()
        assets[e['id']] = {'path': str(p), 'width': width, 'height': height, 'sha256': digest}
        groups.setdefault(digest, []).append(e['id'])
    return {'assets': assets, 'duplicate_images': [ids for ids in groups.values() if len(ids) > 1]}


def reviewers(run_dir, requested=None):
    path = Path(run_dir) / 'reviewers.json'
    selected = requested or (load(path)['reviewers'] if path.exists() else ['codex', 'gemini'])
    if len(selected) != 2 or len(set(selected)) != 2 or any(x not in REVIEWERS for x in selected):
        raise ValueError('Choose exactly two distinct reviewer roles: codex, gemini, claude_second')
    return selected


def check_pins(pins, ids, who):
    if not isinstance(pins, list):
        raise ValueError(f'{who}: pins is not a list')
    got = [p['id'] for p in pins]
    missing, extra = set(ids) - set(got), set(got) - set(ids)
    if missing or extra or len(got) != len(set(got)):
        raise ValueError(f'{who}: ids do not match (missing {sorted(missing)}, extra {sorted(extra)}, duplicates {len(got) != len(set(got))})')
    for p in pins:
        if p.get('outline') not in ('none', 'thin', 'medium', 'bold') or p.get('saturation') not in ('low', 'medium', 'high'):
            raise ValueError(f'{who}: invalid labels for {p["id"]}')
        if not isinstance(p.get('subject'), str) or not p['subject'].strip() or not isinstance(p.get('marks'), list):
            raise ValueError(f'{who}: invalid subject/marks for {p["id"]}')
    return sorted(pins, key=lambda p: ids.index(p['id']))


def read_reviews(run_dir, entries, selected):
    ids = [e['id'] for e in entries]
    return {m: {p['id']: p for p in check_pins(load(Path(run_dir) / f'{m}.json')['pins'], ids, m)} for m in selected}


def adjudication_fingerprint(run_dir, entries, selected):
    run = Path(run_dir)
    return fingerprint({'manifest': entries, 'reviewers': selected,
                        'first_read': load(run/'claude.json'),
                        'reviews': {role: load(run/(role+'.json')) for role in selected},
                        'assets': load(run/'assets.json') if (run/'assets.json').exists() else None})
