#!/usr/bin/env python3
"""Verify and bundle the DA:O-only reverb library and its complete source."""
from pathlib import Path
import argparse
import hashlib
import json
import shutil


def read_regular(path, limit=256 * 1024 * 1024):
    if path.is_symlink() or not path.is_file() or path.stat().st_size > limit:
        raise ValueError(f'Missing, linked or oversized reverb material: {path.name}')
    return path.read_bytes()


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def validate(source, artifacts, bundled=False):
    """Bind binary, complete source and notices to the selected source revision."""
    source, artifacts = Path(source), Path(artifacts)
    raw = read_regular(source / 'component.json', 65536)
    manifest = json.loads(raw)
    if (manifest.get('schema') != 1 or manifest.get('id') != 'origins-reverb'
            or manifest.get('policy_revision') != 1):
        raise ValueError('Unsupported reverb component manifest')
    expected = {
        'source_manifest_sha256': sha(read_regular(source / 'source-manifest.json', 65536)),
        'build_recipe_sha256': sha(read_regular(source / 'build.py', 1024 * 1024)),
    }
    for key, digest in expected.items():
        if manifest.get(key) != digest:
            raise ValueError('Reverb source or build recipe differs from the component manifest')
    source_manifest = json.loads(read_regular(source / 'source-manifest.json', 65536))
    overlay = source_manifest.get('overlay')
    if not isinstance(overlay, dict) or not overlay:
        raise ValueError('Reverb source overlay manifest is missing')
    overlay_root = source / 'overlay'
    actual = set()
    for path in overlay_root.rglob('*'):
        if path.is_symlink():
            raise ValueError('Linked reverb overlay source is not allowed')
        if path.is_file():
            actual.add(path.relative_to(overlay_root).as_posix())
    if actual != set(overlay):
        raise ValueError('Reverb source overlay file list differs from its manifest')
    for name, entry in overlay.items():
        if (not isinstance(name, str) or name.startswith('/') or '\\' in name
                or any(part in ('', '.', '..') for part in name.split('/'))
                or not isinstance(entry, dict)):
            raise ValueError('Invalid reverb source overlay path')
        data = read_regular(overlay_root / name, 2 * 1024 * 1024)
        if (type(entry.get('bytes')) is not int or len(data) != entry['bytes']
                or sha(data) != entry.get('sha256')):
            raise ValueError('Reverb source overlay differs from its verified build')
    files = []
    for key in ('dll', 'corresponding_source'):
        entry = manifest.get(key, {})
        name = entry.get('file', '')
        if (not isinstance(name, str) or Path(name).name != name or name in ('', '.', '..')
                or (key == 'dll' and name != 'winmm.dll')
                or (key == 'corresponding_source' and not name.endswith('-source.tar.gz'))):
            raise ValueError('Invalid reverb component filename')
        data = read_regular(artifacts / name)
        if (type(entry.get('bytes')) is not int or len(data) != entry['bytes']
                or sha(data) != entry.get('sha256')):
            raise ValueError(f'Reverb {key} differs from its verified build')
        files.append(name)
    if bundled:
        for name in ('component.json', 'source-manifest.json', 'COPYING.LIB', 'README.md'):
            if read_regular(artifacts / name) != read_regular(source / name):
                raise ValueError(f'Bundled reverb {name} differs from source')
    return manifest, files


def bundle(source, artifacts, destination):
    source, artifacts, destination = map(Path, (source, artifacts, destination))
    manifest, files = validate(source, artifacts)
    if destination.exists() or destination.is_symlink():
        raise ValueError('Reverb bundle output already exists; use a new app build')
    destination.mkdir(parents=True)
    for name in files:
        shutil.copyfile(artifacts / name, destination / name)
    for name in ('component.json', 'source-manifest.json', 'COPYING.LIB', 'README.md'):
        shutil.copyfile(source / name, destination / name)
    validate(source, destination, bundled=True)
    return manifest


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--artifacts', type=Path, required=True)
    parser.add_argument('--destination', type=Path)
    args = parser.parse_args()
    if args.destination:
        bundle(args.source, args.artifacts, args.destination)
    else:
        validate(args.source, args.artifacts)
    print('Verified reverb binary and complete matching source.')
