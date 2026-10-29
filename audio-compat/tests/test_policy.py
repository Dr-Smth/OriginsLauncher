"""Pure recovery-policy regression test; never executes Wine."""
# SPDX-License-Identifier: LGPL-2.1-or-later
from pathlib import Path
import hashlib,json,os,subprocess,tempfile
here=Path(__file__).resolve().parent
out=Path(os.environ.get('ORIGINS_AUDIO_TEST_OUTPUT')or tempfile.mkdtemp(prefix='origins-audio-policy-')).resolve();out.mkdir(parents=True,exist_ok=True)
source=here/'policy_recovery_test.c';binary=out/'policy_recovery_test'
r=subprocess.run(['/usr/bin/clang','-std=c11','-O1','-g','-Wall','-Wextra','-Werror','-fsanitize=address,undefined',str(source),'-o',str(binary)],capture_output=True,text=True)
if r.returncode:raise RuntimeError(r.stderr)
r=subprocess.run([str(binary)],capture_output=True,text=True)
result={'status':'PASS_POLICY10_CORE'if not r.returncode else'FAIL_POLICY10_CORE','stdout':r.stdout,'stderr':r.stderr,'exit_code':r.returncode,'source_sha256':hashlib.sha256(source.read_bytes()).hexdigest(),'policy_sha256':hashlib.sha256((here.parent/'overlay/dlls/dsound/decision_core.h').read_bytes()).hexdigest(),'live_actions':False}
(out/'policy-test-result.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2));raise SystemExit(r.returncode)
