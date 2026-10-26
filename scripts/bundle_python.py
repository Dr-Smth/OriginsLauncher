#!/usr/bin/env python3
"""Bundle hash-pinned relocatable Python and its exact upstream licence notices."""
from pathlib import Path, PurePosixPath
import argparse
import json
import os
import shutil
import subprocess
import sys
import tarfile
import tempfile

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / 'source'))
from bootstrap_runtime import archive_in_cache, safe_members


def bundle(destination, cache):
    manifest = json.loads((REPO / 'dependency-manifest.json').read_text())
    asset = manifest['python']
    archive_path = archive_in_cache(cache, asset)
    full = archive_in_cache(cache, manifest['python_licenses'])
    if os.path.lexists(destination):
        raise RuntimeError('Python destination already exists; build into a new app directory.')
    destination.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='python-build-', dir=destination.parent) as temporary:
        stage = Path(temporary)
        with tarfile.open(archive_path, 'r:gz') as archive:
            members = safe_members(archive, 'python')
            for member in members:
                target = stage / member.name
                if member.isdir():
                    target.mkdir(parents=True, exist_ok=True)
                elif member.isfile():
                    target.parent.mkdir(parents=True, exist_ok=True)
                    with archive.extractfile(member) as src, target.open('xb') as out:
                        shutil.copyfileobj(src, out)
                    target.chmod(member.mode & 0o777)
            for member in members:
                if member.issym():
                    target = stage / member.name
                    target.parent.mkdir(parents=True, exist_ok=True)
                    target.symlink_to(member.linkname)
        notices = stage / 'python/THIRD_PARTY_LICENSES'
        notices.mkdir()
        # The newly verified Python 3.14 interpreter has stdlib zstd support;
        # builders need no Homebrew/zstd/pip, and recipients need no Python install.
        unpacked = stage / 'metadata.tar'
        env = os.environ.copy()
        env.pop('PYTHONHOME', None)
        env.pop('PYTHONPATH', None)
        subprocess.run([str(stage / 'python/bin/python3'), '-I', '-B', '-c',
                        'import compression.zstd, shutil, sys; '
                        'src=compression.zstd.open(sys.argv[1], "rb"); '
                        'dst=open(sys.argv[2], "xb"); shutil.copyfileobj(src,dst); dst.close(); src.close()',
                        str(full), str(unpacked)], env=env, check=True)
        with tarfile.open(unpacked, 'r:') as metadata_archive:
            members = safe_members(metadata_archive, 'python')
            selected = [m for m in members if m.isfile() and
                        (m.name == 'python/PYTHON.json' or
                         (PurePosixPath(m.name).parent == PurePosixPath('python/licenses') and
                          PurePosixPath(m.name).name.startswith('LICENSE')))]
            if not any(m.name == 'python/PYTHON.json' for m in selected) or len(selected) < 5:
                raise RuntimeError('Python archive is missing expected dependency licence metadata')
            for member in selected:
                if member.size > 2 * 1024 * 1024:
                    raise RuntimeError('Oversized Python licence metadata')
                with metadata_archive.extractfile(member) as handle:
                    (notices / PurePosixPath(member.name).name).write_bytes(handle.read())
        metadata = json.loads((notices / 'PYTHON.json').read_text())
        required = set()
        def collect(value):
            if isinstance(value, dict):
                for key, child in value.items():
                    if key == 'license_path' and isinstance(child, str):
                        required.add(PurePosixPath(child).name)
                    elif key == 'license_paths' and isinstance(child, list):
                        required.update(PurePosixPath(x).name for x in child)
                    else:
                        collect(child)
            elif isinstance(value, list):
                for child in value:
                    collect(child)
        collect(metadata)
        missing = required - {p.name for p in notices.iterdir()}
        if missing:
            raise RuntimeError('Missing Python licences: ' + ', '.join(sorted(missing)))
        (notices / 'ORIGIN.json').write_text(json.dumps({'python': asset, 'licence_archive': manifest['python_licenses']}, indent=2) + '\n')
        (stage / 'python').rename(destination)
    # No invocation of a system-installed Python is needed by the resulting app.
    env = os.environ.copy()
    env.pop('PYTHONHOME', None)
    env.pop('PYTHONPATH', None)
    env['PYTHONDONTWRITEBYTECODE'] = '1'
    subprocess.run([str(destination / 'bin/python3'), '-I', '-B', '-c',
                    'import ssl, ctypes, lzma, sqlite3, hashlib; print("Bundled Python ready")'], env=env, check=True)
    return {'python': asset['version'], 'notices': len(selected), 'destination': str(destination)}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--destination', type=Path, required=True)
    parser.add_argument('--cache', type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(bundle(args.destination.resolve(), args.cache.resolve())))
