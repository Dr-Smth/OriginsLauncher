#!/usr/bin/env python3
"""Package complete matching library source; no game or FMOD files are accepted."""
# SPDX-License-Identifier: LGPL-2.1-or-later
from pathlib import Path
import argparse,gzip,hashlib,json,tarfile
HERE=Path(__file__).resolve().parent
p=argparse.ArgumentParser(description=__doc__);p.add_argument('--wine-archive',type=Path,required=True);p.add_argument('--output',type=Path,required=True);args=p.parse_args()
m=json.loads((HERE/'source-manifest.json').read_text());digest=lambda f:hashlib.sha256(f.read_bytes()).hexdigest()
assert digest(args.wine_archive)==m['upstream']['sha256']
files={n:HERE/n for n in ['README.md','COPYING.LIB','source-manifest.json','build-provenance.json','build.py','make_source_bundle.py']}
files.update({'overlay/'+n:HERE/'overlay'/n for n in m['overlay']})
for n,v in m['overlay'].items():assert digest(HERE/'overlay'/n)==v['sha256'],n
files.update({'tests/'+n:HERE/'tests'/n for n in ['run_tests.py','test_system_hook.c','test_startup.c']})
files['upstream/wine-11.0.tar.gz']=args.wine_archive
args.output.parent.mkdir(parents=True,exist_ok=True)
with args.output.open('wb')as raw,gzip.GzipFile(filename='',mode='wb',fileobj=raw,mtime=0,compresslevel=1)as compressed,tarfile.open(mode='w',fileobj=compressed,format=tarfile.USTAR_FORMAT)as archive:
 for name,path in sorted(files.items()):
  info=tarfile.TarInfo('origins-reverb-source/'+name);info.size=path.stat().st_size;info.mode=0o755 if name.endswith('.py')else 0o644;info.mtime=0;info.uid=info.gid=0
  with path.open('rb')as content:archive.addfile(info,content)
print(json.dumps({'file':args.output.name,'bytes':args.output.stat().st_size,'sha256':digest(args.output)},indent=2))
