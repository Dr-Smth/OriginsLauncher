#!/usr/bin/env python3
"""Sign every embedded Mach-O from the inside out; no security exceptions."""
from pathlib import Path
import argparse
import os
import subprocess

MAGIC = {bytes.fromhex(x) for x in ('feedface','cefaedfe','feedfacf','cffaedfe','cafebabe','bebafeca','cafebabf','bfbafeca')}

def sign(app, identity):
    app = app.resolve()
    if app.suffix != '.app' or not (app/'Contents/Info.plist').is_file():
        raise ValueError('Expected an existing app bundle')
    paths = []
    for path in app.rglob('*'):
        if path.is_symlink() or not path.is_file():
            continue
        with path.open('rb') as stream:
            if stream.read(4) in MAGIC:
                paths.append(path)
    for path in sorted(paths, key=lambda p: len(p.parts), reverse=True) + [app]:
        args = ['/usr/bin/codesign', '--force', '--sign', identity]
        if identity != '-':
            args += ['--options', 'runtime', '--timestamp']
        subprocess.run(args + [str(path)], check=True)
    subprocess.run(['/usr/bin/codesign', '--verify', '--deep', '--strict', str(app)], check=True)
    print(f'Signed {len(paths)} Mach-O files and app ({"local ad-hoc" if identity == "-" else "Developer ID"}).')

if __name__ == '__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--app', type=Path, required=True)
    parser.add_argument('--identity', required=True, help='Developer ID Application identity, or - for a local ad-hoc build')
    args=parser.parse_args()
    sign(args.app,args.identity)
