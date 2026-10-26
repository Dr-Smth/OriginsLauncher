#!/usr/bin/env python3
"""Allowlist the public source tree; reject private state, binaries and secrets."""
from pathlib import Path
import hashlib
import json
import re
import sys

NOTICE_FILES = ('LICENSE', 'LICENSING.md', 'ARTWORK.md', 'THIRD_PARTY.md')
ROOT_FILES = {'LICENSE','LICENSING.md','ARTWORK.md','README.md','THIRD_PARTY.md','CONTRIBUTING.md','SECURITY.md',
              '.gitignore','VERSION','dependency-manifest.json','CHANGELOG.md'}
SOURCE_FILES = {'Launcher.swift','Icon.swift','DisplayProbe.swift','build.sh','daoctl.py',
                'steam_state.py','display_settings.py','bootstrap_runtime.py','game_setup.py','ui_scaling.py','profile_paths.py','steam_maintenance.py'}
SCRIPT_FILES = {'audit_release.py','bundle_python.py','package_release.py','sign_release.py','smoke_app.py'}
ISSUE_FILES = {'bug_report.yml', 'compatibility_report.yml', 'config.yml'}
# Known, separately reserved art in the private maintenance repository. Validate
# identity but omit these images from GPL source exports; retain their notice.
ARTWORK_NOTICE = 'branding/aberrant-ink/NOTICE.txt'
RESERVED_IMAGES = {
    'branding/aberrant-ink/dragon-logo.png': '2bb81041953e5e473937f86fd08e0a1e9e38bff98048021aa6fabbb22c24d34d',
    'branding/aberrant-ink/app-icon.png': 'dbfecaa6c0a7066a486c297e4c7c730d31ae6a0cd7c7c78273cc4c843653feb5',
}
MAGIC = {b'MZ', b'\xcf\xfa\xed\xfe', b'\xfe\xed\xfa\xcf', b'\xca\xfe\xba\xbe'}
PATTERNS = [re.compile(rb'/Users/[A-Za-z0-9_. -]+/'),
            re.compile(rb'gh[pousr]_[A-Za-z0-9]{30,}'),
            re.compile(rb'github_pat_[A-Za-z0-9_]{40,}'),
            re.compile(rb'-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----')]

def allowed(rel):
    parts=rel.parts
    return (rel.as_posix()==ARTWORK_NOTICE or
            len(parts)==1 and rel.name in ROOT_FILES or
            len(parts)==2 and parts[0]=='source' and rel.name in SOURCE_FILES or
            len(parts)==3 and parts[:2]==('source','tests') and rel.name.startswith('test_') and rel.suffix=='.py' or
            len(parts)==2 and parts[0]=='scripts' and rel.name in SCRIPT_FILES or
            len(parts)==2 and parts[0]=='docs' and rel.suffix=='.md' or
            len(parts)==3 and parts[:2]==('.github','workflows') and rel.name=='checks.yml' or
            len(parts)==3 and parts[:2]==('.github','ISSUE_TEMPLATE') and rel.name in ISSUE_FILES)

def audit(root):
    root=Path(root).resolve()
    errors=[]; entries=[]
    for path in sorted(root.rglob('*')):
        rel=path.relative_to(root)
        if '.git' in rel.parts:
            continue
        if path.is_symlink():
            errors.append(f'Symlink is not allowed in source export: {rel}')
            continue
        if path.is_dir():
            continue
        if rel.as_posix() in RESERVED_IMAGES:
            if hashlib.sha256(path.read_bytes()).hexdigest() != RESERVED_IMAGES[rel.as_posix()]:
                errors.append(f'Reserved artwork differs from reviewed asset: {rel}')
            if not (root / ARTWORK_NOTICE).is_file():
                errors.append(f'Missing artwork notice: {ARTWORK_NOTICE}')
            continue
        if not allowed(rel):
            errors.append(f'Not in source allowlist: {rel}')
            continue
        raw=path.read_bytes()
        if len(raw)>2*1024*1024 or any(raw.startswith(magic) for magic in MAGIC) or b'\0' in raw:
            errors.append(f'Binary/oversized file in source: {rel}')
        try:
            raw.decode('utf-8')
        except UnicodeError:
            errors.append(f'Non-text source file: {rel}')
        for pattern in PATTERNS:
            if pattern.search(raw):
                errors.append(f'Possible private data in {rel}; review before export')
        entries.append({'path':rel.as_posix(),'bytes':len(raw),'sha256':hashlib.sha256(raw).hexdigest()})
    for required in (*NOTICE_FILES,'README.md','dependency-manifest.json','source/Launcher.swift'):
        if not (root/required).is_file():errors.append(f'Missing {required}')
    if errors:raise ValueError('\n'.join(errors))
    return entries

if __name__=='__main__':
    try:
        entries=audit(Path(sys.argv[1]) if len(sys.argv)>1 else Path(__file__).resolve().parents[1])
        print(json.dumps({'ok':True,'files':len(entries),'bytes':sum(x['bytes'] for x in entries)}))
    except (ValueError,OSError) as exc:
        print(str(exc),file=sys.stderr);sys.exit(1)
