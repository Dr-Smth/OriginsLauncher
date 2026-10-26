#!/usr/bin/env python3
"""Exercise the packaged controller in an empty temporary home for game data."""
from pathlib import Path
import argparse
import json
import os
import subprocess
import tempfile


def smoke(app):
    resources=app.resolve()/'Contents/Resources'
    python=resources/'python/bin/python3'
    assert python.is_file(), 'Private Python is missing'
    assert not (resources/'runtime-location.json').exists(), 'Private runtime pointer must never be shipped'
    for name in ('LICENSE','LICENSING.md','ARTWORK.md','THIRD_PARTY.md','dependency-manifest.json','game_setup.py','ui_scaling.py','profile_paths.py','steam_maintenance.py'):
        assert (resources/name).is_file(), name
    assert len(list((resources/'python/THIRD_PARTY_LICENSES').glob('LICENSE*'))) >= 5
    with tempfile.TemporaryDirectory(prefix='origins-clean-smoke-') as temporary:
        root=Path(temporary)/'Empty install'
        env=os.environ.copy()
        for key in ('PYTHONHOME','PYTHONPATH','PYTHONSTARTUP'):
            env.pop(key,None)
        env.update(DAO_PROJECT_ROOT=str(root), PYTHONDONTWRITEBYTECODE='1', SSL_CERT_FILE='/etc/ssl/cert.pem')
        # No commands that download, start Wine, or inspect account/session files.
        result=subprocess.run([str(python),'-B',str(resources/'daoctl.py'),'status'],env=env,capture_output=True,text=True,timeout=20,check=True)
        status=json.loads(result.stdout)
        assert not status['runtime_ready'] and not status['steam_installed'] and not status['game_installed']
        assert status.get('compatibility_verified') is not True
        assert str(root) in status['data_path']
        assert not root.exists(), 'Status must remain read-only on first launch'
        certs=subprocess.check_output([str(python),'-I','-B','-c','import ssl,json; print(json.dumps(ssl.create_default_context(cafile="/etc/ssl/cert.pem").cert_store_stats()))'],env=env,text=True)
        assert json.loads(certs)['x509_ca']>0
    print(json.dumps({'ok':True,'empty_install_status':'passed','private_python':'passed','ca_store':'passed','wine_started':False,'download_started':False}))

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('app',type=Path)
    smoke(p.parse_args().app)
