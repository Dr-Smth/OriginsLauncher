# SPDX-License-Identifier: LGPL-2.1-or-later
"""Focused host harness compiling actual clean snapshot and Sleep adapter bodies.
Windows identity, clock and original Sleep are deterministic mocks. No Wine/live use.
"""
from pathlib import Path
import hashlib
import json
import subprocess
import re
import os,tempfile

HERE = Path(__file__).resolve().parent
IMPLEMENTATION = HERE.parent / 'overlay/dlls/dsound'
OUTPUT = Path(os.environ.get('ORIGINS_AUDIO_TEST_OUTPUT') or tempfile.mkdtemp(prefix='origins-audio-tests-')).resolve()
OUTPUT.mkdir(parents=True,exist_ok=True)


def function(text, name):
    match = re.search(r'^(?:static )?[^\n]*\b' + re.escape(name) + r'\([^;]*?\)\s*\{', text, re.M)
    if not match:
        raise ValueError('Missing actual function: ' + name)
    pos = match.end()
    depth = 1
    while depth:
        depth += (text[pos] == '{') - (text[pos] == '}')
        pos += 1
    return text[match.start():pos]


def main():
    production = (IMPLEMENTATION / 'clean_audio.c').read_text()
    declarations = production[production.index('enum {LA_WAIT'):production.index('static INIT_ONCE')]
    declarations += re.search(r'struct la_guard \{[^}]+\};', production)[0] + '\n'
    names = ['la_fail', 'la_live', 'la_target', 'la_next', 'la_count', 'la_scope', 'la_recheck', 'la_snapshot', 'la_publish_policy', 'la_sleep', 'cl_expected_module']
    fragments = [function(production, name) for name in names]
    api_source = (IMPLEMENTATION / 'clean_api.c').read_text()
    api_names = ['conditional_api_enter', 'conditional_api_leave', 'la_try_activate', 'rt_end']
    api_fragments = [function(api_source, name) for name in api_names]
    prefix = r'''
#include <stdint.h>
#include <assert.h>
#include <stdio.h>
#include <string.h>
#include <wchar.h>
#include <wctype.h>
typedef wchar_t WCHAR;
#define CL_FIXTURE 0
#define CL_IMAGE L"DAOrigins.exe"
typedef uint32_t DWORD; typedef int32_t LONG; typedef uint64_t ULONGLONG;
typedef uintptr_t ULONG_PTR; typedef int BOOL; typedef int32_t HRESULT;
typedef struct { DWORD rt_id; } IDirectSoundBufferImpl; typedef void *HANDLE; typedef void *HMODULE;
#define WINAPI
#define TRUE 1
#define FALSE 0
#define WAIT_TIMEOUT 258
#define CL_SLEEP_RETURN_RVA 200
#define CL_POSITION_RVA 250
#define CL_LOCK_RVA 300
#define CL_UNLOCK_RVA 400
#define SYNCHRONIZE 0x100000
#define FAILED(x) ((int32_t)(x)<0)
#define CD_LOW_LEAD_MAX_BYTES 6144u
#define CD_RECOVERY_LEAD_ABOVE_BYTES 6144u
#include "decision_core.h"
#include "provenance_format.h"
#include "route_format.h"
struct rt_call { struct rt_event event; LONG slot; BOOL admitted; const struct pv_write *write; };
static DWORD la_load(const volatile LONG*p){return __atomic_load_n(p,__ATOMIC_ACQUIRE);}
static void la_store(volatile LONG*p,DWORD v){__atomic_store_n(p,(LONG)v,__ATOMIC_RELEASE);}
static LONG InterlockedCompareExchange(volatile LONG*p,LONG desired,LONG expected){__atomic_compare_exchange_n(p,&expected,desired,0,__ATOMIC_SEQ_CST,__ATOMIC_SEQ_CST);return expected;}
static LONG InterlockedIncrement(volatile LONG*p){return __atomic_add_fetch(p,1,__ATOMIC_SEQ_CST);}
static LONG InterlockedDecrement(volatile LONG*p){return __atomic_sub_fetch(p,1,__ATOMIC_SEQ_CST);}
static LONG InterlockedExchange(volatile LONG*p,LONG v){return __atomic_exchange_n(p,v,__ATOMIC_SEQ_CST);}
#define LA_LOAD(p) la_load((const volatile LONG*)(p))
#define LA_STORE(p,v) la_store((volatile LONG*)(p),(v))
#define LA_CAS(p,e,v) ((DWORD)InterlockedCompareExchange((volatile LONG*)(p),(v),(e)))
#include "latest_snapshot.h"
#include "provenance_slots.h"
static DWORD mock_error, mock_tid=10, mock_caller=1200, mock_wait=WAIT_TIMEOUT;
static DWORD original_calls, original_argument, original_incoming_error, original_observing;
static DWORD ticks, invalidate_tick, duplicate_calls, duplicate_fail, duplicate_control_race;
static ULONGLONG mock_now=1000000;
static const WCHAR*mock_path=L"C:\\Games\\Origins\\DAOrigins.exe";
static DWORD mock_path_error;
static DWORD GetModuleFileNameW(void*module,WCHAR*out,DWORD capacity){(void)module;if(mock_path_error)return mock_path_error==1?0:capacity;size_t n=wcslen(mock_path);if(n>=capacity)return capacity;wmemcpy(out,mock_path,n+1);return n;}
static int lstrcmpiW(const WCHAR*a,const WCHAR*b){while(*a&&*b&&towlower(*a)==towlower(*b)){a++;b++;}return towlower(*a)!=towlower(*b);}
static DWORD GetLastError(void){return mock_error;}
static void SetLastError(DWORD e){mock_error=e;}
static DWORD GetCurrentThreadId(void){mock_error=0x5555;return mock_tid;}
static DWORD WaitForSingleObject(HANDLE h,DWORD ms){assert(h==(void*)1 && ms==0);mock_error=0x7777;return mock_wait;}
#define __builtin_return_address(n) ((void *)(uintptr_t)mock_caller)
'''
    helpers = r'''
static ULONGLONG rt_tick(void){ticks++;if(ticks==invalidate_tick)context->commit_sequence++;mock_error=0x6666;return mock_now;}
static HANDLE GetCurrentProcess(void){return (void*)2;}
static HANDLE GetCurrentThread(void){return (void*)3;}
static BOOL CloseHandle(HANDLE h){assert(h==(void*)1);return TRUE;}
static BOOL DuplicateHandle(HANDLE a,HANDLE b,HANDLE d,HANDLE*out,DWORD access,BOOL inherit,DWORD options)
{
 assert(a==(void*)2&&b==(void*)3&&d==(void*)2&&access==SYNCHRONIZE&&!inherit&&!options);
 duplicate_calls++;if(duplicate_control_race){context->control_ops++;context->control_serial++;}
 *out=(void*)1;return !duplicate_fail;
}
'''
    tests = r'''
static void original_sleep(DWORD ms)
{
 original_calls++;original_argument=ms;original_incoming_error=mock_error;
 original_observing=context->observing;mock_error=0xabcdef;
}
static void setup(struct rt_context*c)
{
 memset(c,0,sizeof(*c));context=c;c->state=LA_ACTIVE;c->identity_ready=2;c->looping_seen=1;
 c->selected=1;c->backing=2;c->device=3;c->epoch=4;c->producer_tid=10;c->module_base=1000;
 c->producer_handle=(void*)1;c->frequency=10000000;c->original_sleep=original_sleep;c->commit_sequence=2;
 c->policy=(struct cd_state){.frequency=10000000,.origin=1,.origin_position=CD_RING,
 .query_valid=1,.query_consumer_abs=CD_RING+20480,.query_end_abs=CD_RING+36864,
 .query_play=20480,.query_write=22400,.query_sequence=1,.query_qpc=1,
 .writes=24,.last_token=24,.next_offset=36864,.calibration=3,.last_calibration_token=24,
 .anchored=1,.next_abs=CD_RING+36864};
 struct pv_read r={.object=1,.backing=2,.device=3,.epoch=4,.frames=512,.qualified_frames=512,
 .flags=1,.audible=1,.freq_num=48000,.freq_den=48000,.writelead=1920,
 .device_frames=32768/4-512,.sec_after=32768,.end=999900,.sequence_before=2,.sequence_after=2};
 uint32_t words[LA_SNAPSHOT_WORDS];memcpy(words,&r,sizeof(r));
 assert(la_snapshot_publish(&c->latest,la_snapshot_begin(&c->latest),words));
 mock_error=0x123456;mock_tid=10;mock_caller=1200;mock_wait=WAIT_TIMEOUT;
 original_calls=ticks=invalidate_tick=duplicate_calls=duplicate_fail=duplicate_control_race=0;original_argument=999;mock_now=1000000;
}
static struct rt_call activation_setup(struct rt_context*c)
{
 setup(c);c->state=LA_WAIT;c->identity_ready=0;c->producer_tid=0;c->producer_handle=0;
 memset(&c->policy,0,sizeof(c->policy));c->active_ops=1;
 c->slots[0].w[PS_STATE]=PV_OPEN;c->slots[0].w[PS_THREAD]=10;
 struct rt_call t={0};t.admitted=TRUE;t.slot=1;
 t.event=(struct rt_event){.kind=RT_LOCK,.tid=10,.object=1,.backing=2,.device=3,.caller=1300};
 t.event.data[1]=4096;return t;
}
static void invoke(DWORD request,DWORD expected)
{
 DWORD incoming=mock_error;la_sleep(request);
 assert(original_calls==1 && original_argument==expected && original_incoming_error==incoming);
 assert(mock_error==0xabcdef);
}

static void publish_position(struct rt_context*c,DWORD offset)
{
 struct pv_read r={.object=1,.backing=2,.device=3,.epoch=4,.frames=512,.qualified_frames=512,
 .flags=1,.audible=1,.freq_num=48000,.freq_den=48000,.writelead=1920,
 .device_frames=offset/4-512,.sec_after=offset%CD_RING,.end=mock_now-100,.sequence_before=2,.sequence_after=2};
 uint32_t words[LA_SNAPSHOT_WORDS];memcpy(words,&r,sizeof(r));
 assert(la_snapshot_publish(&c->latest,la_snapshot_begin(&c->latest),words));
}
static void paused_setup(struct rt_context*c)
{
 setup(c);c->policy.recovery_active=1;c->policy.recovery_paused=1;c->policy.pause_count=1;
 c->policy.recovery_consumer=c->policy.last_progress_consumer=CD_RING+32768;
 c->policy.recovery_producer=CD_RING+36864;c->policy.last_progress_qpc=mock_now;
 c->policy.resume_consumer=CD_RING+32768;c->policy.resume_producer=c->policy.next_abs;
 c->policy.resume_token=c->policy.last_token;
}
static void advance_burst(struct rt_context*c,DWORD offset)
{
 struct cd_snapshot x;struct la_guard g;int64_t end;
 assert(cd_endpoint(CD_RING+offset,&end));
 while(c->policy.next_abs<end)cd_write(&c->policy,c->policy.last_token+1,c->policy.next_offset,CD_BLOCK);
 assert(c->policy.next_abs==end&&!c->policy.invalid);
 publish_position(c,offset);assert(la_snapshot(c,&x,&g));
 cd_query(&c->policy,c->policy.query_sequence+1,offset%CD_RING,(offset+CD_LEAD)%CD_RING,mock_now,&x);
 assert(c->policy.query_valid);original_calls=0;mock_error=0x123456;
}

int main(void)
{
 struct rt_context c;struct cd_snapshot snapshot;struct la_guard guard;unsigned cases=0;
 setup(&c);assert(la_snapshot(&c,&snapshot,&guard)&&snapshot.valid);cases++;
 setup(&c);invoke(10,0);assert(c.policy.early_count==1 && c.qualified_sleep10==1 && !c.observing);cases++;
 for(unsigned fault=0;fault<12;fault++){
  setup(&c);
  switch(fault){
   case0:c.identity_ready=0;break;case1:mock_tid=11;break;case2:mock_caller=1201;break;
   case3:c.latest.generation=0;break;case4:c.latest.generation|=1;break;
   case5:c.commit_active=1;break;case6:c.active_ops=1;break;case7:c.control_ops=1;break;
   case8:c.slots[0].w[PS_STATE]=PV_OPEN;break;case9:mock_now+=220000;break;
   case10:c.commit_sequence++;break;case11:invalidate_tick=4;break;
  }
  invoke(10,10);assert(c.policy.early_count==0 && !c.observing);cases++;
 }
 setup(&c);invoke(1,1);assert(!c.qualified_sleep10&&!c.policy.early_count);cases++;
 setup(&c);c.observing=1;invoke(10,10);assert(c.observing==1&&!c.policy.early_count);cases++;
 setup(&c);mock_wait=0;invoke(10,10);assert(c.state==LA_FALLBACK&&c.reason==LA_THREAD_ENDED);cases++;
 setup(&c);c.policy.early_count=4096;invoke(10,0);assert(c.state==LA_ACTIVE&&c.status[ST_APPLIED]==4097);cases++;
 setup(&c);c.policy.cutout=CD_CONSUMER_STALLED;invoke(10,10);
 assert(c.state==LA_FALLBACK&&c.reason==LA_CUTOUT&&c.status[ST_CUTOUT]==CD_CONSUMER_STALLED&&!c.forwarded10_after_cutout);
 original_calls=0;mock_error=0x123456;invoke(10,10);
 assert(c.forwarded10_after_cutout==1&&!c.applied_after_cutout&&!c.policy.early_count);cases++;
 setup(&c);assert(la_snapshot(&c,&snapshot,&guard));c.latest.generation+=2;assert(!la_recheck(&c,&guard));cases++;
 setup(&c);la_fail(&c,LA_CONTROL);invoke(10,10);assert(c.reason==LA_CONTROL&&!c.policy.early_count);cases++;
 struct rt_call t=activation_setup(&c);rt_end(&t,0);
 assert(c.state==LA_ACTIVE&&c.identity_ready==2&&duplicate_calls==1&&c.producer_tid==10&&!c.policy.writes);cases++;
 /* The Lock crossing activation is not fabricated into completed coverage. */
 struct pv_write w={.reserved=1,.token=1,.thread=10,.lock_thread=10,.object=1,.backing=2,
 .original_return=999995,.flags=3,.bytes1=4096};
 c.write_serial=1;c.active_ops=0;c.slots[0].w[PS_STATE]=PV_FREE;
 t=(struct rt_call){.admitted=TRUE,.slot=2,.write=&w,.event={.start=999990,.kind=RT_UNLOCK,.tid=10,.object=1,.backing=2,.device=3,.caller=1400}};
 rt_end(&t,0);assert(!c.policy.writes&&c.state==LA_ACTIVE&&c.last_write_serial==1);cases++;
 w.reserved=w.token=2;w.flags=7;w.offset1=4096;c.write_serial=2;t.admitted=TRUE;t.slot=3;
 rt_end(&t,0);assert(c.policy.writes==1&&c.policy.last_token==2&&c.state==LA_ACTIVE);cases++;
 for(unsigned fault=0;fault<6;fault++){
  t=activation_setup(&c);
  switch(fault){case 0:c.control_ops=1;break;case 1:c.latest.generation|=1;break;
   case 2:t.event.caller++;break;case 3:duplicate_fail=1;break;case 4:duplicate_control_race=1;break;
   case 5:c.slots[1].w[PS_STATE]=PV_OPEN;c.slots[1].w[PS_THREAD]=11;break;}
  rt_end(&t,0);assert(c.identity_ready!=2&&c.state!=LA_ACTIVE&&!c.policy.writes);cases++;
 }
 setup(&c);IDirectSoundBufferImpl b={1};BOOL entered=conditional_api_enter(&b,RT_STOP);
 assert(entered==3&&c.state==LA_FALLBACK&&c.reason==LA_CONTROL&&c.active_ops==1&&c.control_ops==1);
 conditional_api_leave(entered);assert(!c.active_ops&&!c.control_ops);cases++;
 setup(&c);c.identity_ready=1;mock_tid=11;
 entered=conditional_api_enter(&b,RT_LOCK);
 assert(entered==1&&c.state==LA_FALLBACK&&c.reason==LA_SCOPE);
 conditional_api_leave(entered);assert(!c.active_ops);cases++;
 setup(&c);c.next_token=0x7ffffff0u;
 assert(!la_next(&c,&c.next_token)&&c.state==LA_FALLBACK&&c.reason==LA_GENERATION&&c.next_token==0x7ffffff0u);cases++;

 /* A qualified known reserve below the protected margin must soft-pause. */
 setup(&c);invoke(10,0);original_calls=0;publish_position(&c,35864);mock_error=0x123456;
 invoke(10,10);assert(c.policy.recovery_paused&&c.policy.pause_count==1&&!c.policy.cutout&&c.state==LA_ACTIVE);cases++;
 setup(&c);invoke(10,0);original_calls=0;publish_position(&c,40960);mock_error=0x123456;
 invoke(10,10);assert(c.policy.recovery_paused&&!c.policy.invalid&&!c.policy.cutout&&c.state==LA_ACTIVE);cases++;
 paused_setup(&c);c.policy.resume_streak=2;c.active_ops=1;invoke(10,10);
 assert(c.policy.resume_streak==0&&c.policy.recovery_paused&&c.paused_sleep10==1&&c.state==LA_ACTIVE);cases++;
 paused_setup(&c);c.policy.resume_streak=2;c.observing=1;
 struct cd_state before=c.policy;invoke(10,10);assert(!memcmp(&before,&c.policy,sizeof(before))&&c.observing==1);cases++;
 paused_setup(&c);c.policy.resume_streak=2;mock_tid=11;before=c.policy;
 invoke(10,10);assert(!memcmp(&before,&c.policy,sizeof(before)));cases++;
 paused_setup(&c);c.policy.resume_streak=2;mock_caller=1201;before=c.policy;
 invoke(10,10);assert(!memcmp(&before,&c.policy,sizeof(before)));cases++;
 paused_setup(&c);c.policy.resume_streak=2;c.latest.generation|=1;
 invoke(10,10);assert(!c.policy.resume_streak&&c.policy.recovery_paused&&!c.policy.early_count);cases++;
 /* Exercise the actual adapter through three healthy advancing bursts. */
 paused_setup(&c);advance_burst(&c,36864);invoke(10,10);
 assert(c.policy.resume_streak==1&&c.policy.recovery_paused&&c.policy.resume_count==0);
 original_calls=0;mock_error=0x123456;invoke(10,10);
 assert(c.policy.resume_streak==1&&c.policy.recovery_paused);
 advance_burst(&c,40960);invoke(10,10);assert(c.policy.resume_streak==2&&c.policy.recovery_paused);
 advance_burst(&c,45056);invoke(10,10);
 assert(!c.policy.recovery_paused&&c.policy.resume_count==1&&!c.policy.early_count&&c.state==LA_ACTIVE);
 publish_position(&c,57344);original_calls=0;mock_error=0x123456;invoke(10,0);
 assert(c.policy.early_count==1&&c.policy.applied_after_resume==1&&!c.applied_after_cutout);cases++;
 paused_setup(&c);la_fail(&c,LA_CONTROL);before=c.policy;
 invoke(10,10);assert(!memcmp(&before,&c.policy,sizeof(before))&&c.state==LA_FALLBACK);cases++;
 setup(&c);c.policy.early_count=4095;invoke(10,0);
 assert(c.state==LA_ACTIVE&&c.policy.early_count==4096);
 original_calls=0;mock_error=0x123456;invoke(10,10);assert(c.policy.early_count==4096);
 advance_burst(&c,40960);publish_position(&c,53248);invoke(10,0);
 assert(c.state==LA_ACTIVE&&c.policy.early_count==4097);cases++;
 setup(&c);c.policy.early_count=UINT32_MAX-1;c.policy.resume_count=UINT32_MAX;c.policy.applied_after_resume=UINT32_MAX;
 invoke(10,0);assert(c.policy.early_count==UINT32_MAX&&c.policy.applied_after_resume==UINT32_MAX&&c.state==LA_ACTIVE);
 advance_burst(&c,40960);publish_position(&c,53248);invoke(10,0);
 assert(c.policy.early_count==UINT32_MAX&&c.state==LA_ACTIVE);
 original_calls=0;mock_error=0x123456;invoke(10,10);assert(c.policy.early_count==UINT32_MAX);cases++;
 paused_setup(&c);c.policy.pause_count=UINT32_MAX;c.policy.resume_count=UINT32_MAX;
 advance_burst(&c,36864);invoke(10,10);advance_burst(&c,40960);invoke(10,10);advance_burst(&c,45056);invoke(10,10);
 assert(c.policy.resume_count==UINT32_MAX&&!c.policy.recovery_paused&&c.state==LA_ACTIVE);
 c.policy.recovery_active=1;cd_pause(&c.policy,CD_NO_RECOVERY,CD_RING+45056,mock_now);
 assert(c.policy.pause_count==UINT32_MAX&&c.policy.recovery_paused);cases++;
 setup(&c);c.qualified_sleep10=(LONG)UINT32_MAX;invoke(10,0);assert(la_load(&c.qualified_sleep10)==UINT32_MAX);cases++;
 WCHAR expected[1024];mock_path=L"D:\\Steam Library\\DAO\\DAOrigins.exe";mock_path_error=0;
 assert(cl_expected_module(expected,1024)&&!wcscmp(expected,L"D:\\Steam Library\\DAO\\fmodex.dll"));cases++;
 mock_path=L"C:/Games/DAO/daorigins.EXE";assert(cl_expected_module(expected,1024)&&!wcscmp(expected,L"C:/Games/DAO/fmodex.dll"));cases++;
 mock_path=L"C:\\Games\\Unrelated.exe";assert(!cl_expected_module(expected,1024));cases++;
 mock_path=L"DAOrigins.exe";assert(!cl_expected_module(expected,1024));cases++;
 mock_path=L"C:\\Games\\DAOrigins.exe";mock_path_error=1;assert(!cl_expected_module(expected,1024));cases++;
 mock_path_error=2;assert(!cl_expected_module(expected,1024));mock_path_error=0;assert(!cl_expected_module(expected,4));cases++;


 printf("PASS %u actual snapshot/Sleep/activation adapter cases; forwarding once, original LastError, scoped changes and sticky fallback\n",cases);
 return 0;
}
'''.replace('case0:', 'case 0:').replace('case1:', 'case 1:').replace('case2:', 'case 2:').replace('case3:', 'case 3:').replace('case4:', 'case 4:').replace('case5:', 'case 5:').replace('case6:', 'case 6:').replace('case7:', 'case 7:').replace('case8:', 'case 8:').replace('case9:', 'case 9:').replace('case10:', 'case 10:').replace('case11:', 'case 11:')
    source = OUTPUT / 'adapter-generated.c'
    source.write_text(prefix + declarations + helpers + '\n'.join(fragments + api_fragments) + tests)
    binary = OUTPUT / 'adapter-test'
    command = ['/usr/bin/clang', '-std=c11', '-O1', '-g', '-Wall', '-Wextra', '-Werror', '-Wno-unused-function', '-fsanitize=address,undefined', '-I', str(IMPLEMENTATION), str(source), '-o', str(binary)]
    built = subprocess.run(command, capture_output=True, text=True)
    if built.returncode:
        raise RuntimeError(built.stdout + built.stderr)
    result = subprocess.run([str(binary)], capture_output=True, text=True)
    output = {'status': 'PASS_EXTRACTED_ADAPTER' if result.returncode == 0 else 'FAIL_EXTRACTED_ADAPTER', 'exit_code': result.returncode, 'stdout': result.stdout, 'stderr': result.stderr, 'production_sha256': hashlib.sha256((IMPLEMENTATION/'clean_audio.c').read_bytes()).hexdigest(), 'policy_source_sha256': hashlib.sha256((IMPLEMENTATION/'decision_core.h').read_bytes()).hexdigest(), 'api_source_sha256': hashlib.sha256((IMPLEMENTATION/'clean_api.c').read_bytes()).hexdigest(), 'fragments': {name: hashlib.sha256(text.encode()).hexdigest() for name,text in zip(names + api_names,fragments + api_fragments)}, 'generated_sha256': hashlib.sha256(source.read_bytes()).hexdigest(), 'limits': ['Host API mocks; no Wine PE ABI, real thread identity, audio device or game execution.', 'Actual snapshot, Sleep, activation and selected control functions are tested; original COM hook placement and real Windows ABI have separate review.']}
    (OUTPUT / 'adapter-test-result.json').write_text(json.dumps(output,indent=2)+'\n')
    print(json.dumps(output,indent=2))
    if result.returncode:
        raise SystemExit(result.returncode)


if __name__ == '__main__':
    main()
