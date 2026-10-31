#!/usr/bin/env python3
"""Host regression tests; no proprietary files or Wine/game execution required."""
from pathlib import Path
import argparse,hashlib,json,re,subprocess,tempfile
HERE=Path(__file__).resolve().parent;SOURCE=HERE.parent;IMPL=SOURCE/'overlay/dlls/winmm'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
 p=argparse.ArgumentParser();p.add_argument('--output',type=Path);a=p.parse_args();out=(a.output or Path(tempfile.mkdtemp(prefix='origins-reverb-test-'))).resolve();out.mkdir(parents=True,exist_ok=True)
 # These guard claims are checked in addition to compiling the real wrapper.
 hooks=(IMPL/'origins_reverb_hooks.c').read_text();startup=(IMPL/'origins_reverb_startup.c').read_text();spec=(IMPL/'winmm.spec').read_text()
 for forbidden in ('GetPrivateProfile','setDSPBufferSize','getDSPBufferSize','origins_init','nonce','trial.log','FILE_APPEND_DATA','or_fixture'):
  assert forbidden not in hooks+startup,forbidden
 assert '0x34278u' in hooks and 'caller!=or_bridge_base+0x10dadu' in hooks
 assert 'c->version!=ORIGINS_REVERB_CONFIG_VERSION' in hooks and 'wcsicmp(name,L"DAOrigins.exe")' in hooks
 assert 'MoveFileExW(pending,final,MOVEFILE_REPLACE_EXISTING)' in hooks
 assert 'Sleep(OR_REPORT_INTERVAL_MS)' in hooks and 'OR_REPORT_INTERVAL_MS 5000u' in (IMPL/'reverb_config.h').read_text()
 assert not any(n in spec for n in ('origins_reverb','OriginsFmod','rv_dry'))
 assert sha(IMPL/'reverb_dry.c')=='c1d73b20f3e8c4c3e6e2acbe8839c1f6728bdcc8a2e352bbbc29107de0c7ac4f'
 assert sha(IMPL/'reverb_dry.h')=='cbdb516d1334226a3d644d9f1445f5f3fffae2c12099d790a1233db3226edab6'
 results=[]
 for name in ('test_system_hook','test_startup'):
  source=HERE/(name+'.c');exe=out/name
  cmd=['clang','-std=c11','-O1','-g','-Wall','-Wextra','-Werror','-Wno-unused-function','-Wno-sign-compare','-fsanitize=address,undefined','-I',str(IMPL),str(source),'-o',str(exe)]
  built=subprocess.run(cmd,capture_output=True,text=True);assert built.returncode==0,built.stdout+built.stderr
  ran=subprocess.run([str(exe)],capture_output=True,text=True);assert ran.returncode==0,ran.stdout+ran.stderr
  result={'name':name,'source_sha256':sha(source),'stdout':ran.stdout,'stderr':ran.stderr,'exit_code':ran.returncode};results.append(result)
  if name=='test_system_hook':
   status=json.loads(next(l[len('STATUS '):] for l in ran.stdout.splitlines() if l.startswith('STATUS ')))
   assert status['schema']==1 and status['component_id']=='origins-reverb' and status['component_version']=='1.0.0-beta.1'
   assert status['policy_revision']==1 and status['changes_buffer_size']is False and status['recording']is False and status['profiling']is False
 report={'schema':1,'status':'PASS','sanitizers':['address','undefined'],'results':results,'source_hashes':{str(f.relative_to(SOURCE)):sha(f) for f in sorted(IMPL.glob('*')) if f.is_file()},'limitations':['Windows calls mocked; no native Wine load/game quality claim.','Dry callback is byte-identical to the previously qualified implementation; its prior PE32 ABI and signal checks are not rerun here.'],'live_actions':False}
 (out/'validation.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))
if __name__=='__main__':main()
