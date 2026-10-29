/* SPDX-License-Identifier: LGPL-2.1-or-later; Copyright (C) 2026 David Richard Smith. */
/* Private DA:O-only compatibility adapter. No audio recording or CPU profiling.
 * Original Wine audio bodies are unchanged. LGPL-2.1-or-later. */
#include "clean_config.h"
#include "decision_core.h"
#include "provenance_slots.h"
static DWORD la_load(const volatile LONG*p){return __atomic_load_n(p,__ATOMIC_ACQUIRE);}
static void la_store(volatile LONG*p,DWORD v){__atomic_store_n(p,(LONG)v,__ATOMIC_RELEASE);}
#define LA_LOAD(p) __atomic_load_n((p),__ATOMIC_ACQUIRE)
#define LA_STORE(p,v) __atomic_store_n((p),(v),__ATOMIC_RELEASE)
static int32_t la_snapshot_cas(volatile int32_t*p,int32_t expected,int32_t value)
{__atomic_compare_exchange_n(p,&expected,value,0,__ATOMIC_ACQ_REL,__ATOMIC_ACQUIRE);return expected;}
#define LA_CAS(p,e,v) la_snapshot_cas((p),(e),(v))
#include "latest_snapshot.h"
enum {LA_WAIT=0,LA_ACTIVE=1,LA_FALLBACK=2};
enum {LA_INIT=1,LA_SCOPE,LA_CONTROL,LA_FORMAT,LA_GENERATION,LA_CONCURRENT,LA_THREAD_ENDED,
 LA_PUBLICATION,LA_BUDGET,LA_CUTOUT,LA_API,LA_DESTROY};
enum {ST_APPLIED,ST_REASON,ST_CUTOUT,ST_CUTLO,ST_CUTHI,ST_WRITES,ST_CALIBRATION,ST_EARLY,ST_PAUSED,ST_PAUSE_REASON,ST_PAUSE_COUNT,ST_RESUME_COUNT,ST_AFTER_RESUME,ST_PAUSELO,ST_PAUSEHI,ST_RESUMELO,ST_RESUMEHI,ST_COUNT};
typedef void (WINAPI *la_sleep_fn)(DWORD);
struct rt_context {
 DWORD pid;ULONGLONG frequency,created,activated;HMODULE self,target;
 DWORD module_base,module_size;la_sleep_fn original_sleep;HANDLE producer_handle;
 volatile LONG state,reason,install_status,identity_ready,producer_tid;
 volatile LONG selected,backing,device,epoch,base,invalid;
 volatile LONG active_ops,control_ops,control_serial,looping_seen,observing;
 volatile LONG next_token,write_serial,event_serial,consumer_busy;
 volatile LONG commit_active,commit_sequence,commit_id,last_commit;
 struct pv_slot slots[PV_LOCKS];
 struct la_snapshot latest;struct pv_read staging;DWORD staging_generation;volatile LONG consumer_tid;
 struct cd_state policy;DWORD last_write_serial;
 volatile LONG status[ST_COUNT],qualified_sleep10,forwarded10_after_cutout,applied_after_cutout,paused_sleep10;
};
_Static_assert(sizeof(struct rt_context)<8192,"bounded private compatibility state");
static struct rt_context *context;
static INIT_ONCE once=INIT_ONCE_STATIC_INIT;
static volatile LONG ids;
static void la_fail(struct rt_context*c,DWORD reason)
{if(c){InterlockedCompareExchange(&c->reason,reason,0);InterlockedExchange(&c->state,LA_FALLBACK);}}
static BOOL la_live(struct rt_context*c){return c&&la_load(&c->state)!=LA_FALLBACK;}
static BOOL la_target(struct rt_context*c,IDirectSoundBufferImpl*b)
{return c&&b&&b->rt_id&&la_load(&c->selected)==b->rt_id;}
static DWORD la_next(struct rt_context*c,volatile LONG*p)
{DWORD n=la_load(p),old;for(;;){if(n>=0x7ffffff0u){la_fail(c,LA_GENERATION);return 0;}
 old=InterlockedCompareExchange(p,n+1,n);if(old==n)return n+1;n=old;}}
static void la_count(volatile LONG*p)
{DWORD n=la_load(p);if(n<UINT32_MAX)InterlockedCompareExchange(p,n+1,n);}
DWORD rt_id(void){return la_next(context,&ids);}
ULONGLONG rt_tick(void){LARGE_INTEGER q;DWORD e=GetLastError();BOOL ok=QueryPerformanceCounter(&q);SetLastError(e);return ok?q.QuadPart:0;}
ULONGLONG rt_mixer_tick(void){return 0;}
static BOOL pv_geometry(IDirectSoundBufferImpl*b)
{return b->buffer&&b->pwfx&&b->pwfx->wFormatTag==WAVE_FORMAT_PCM&&b->pwfx->nChannels==2&&
 b->pwfx->nSamplesPerSec==44100&&b->pwfx->wBitsPerSample==16&&b->pwfx->nBlockAlign==4&&b->buflen==CD_RING;}
static BOOL la_secondary(IDirectSoundBufferImpl*b)
{return pv_geometry(b)&&b->freq==48000&&b->freqAdjustNum==48000&&b->freqAdjustDen==48000&&
 b->get==getbpp[1]&&b->put==putieee32&&b->mix_channels==2;}
static BOOL la_primary(const WAVEFORMATEX*w)
{return w&&w->nSamplesPerSec==48000&&w->nChannels==2&&w->nBlockAlign==8&&w->wBitsPerSample==32&&
 (w->wFormatTag==WAVE_FORMAT_IEEE_FLOAT||(w->wFormatTag==WAVE_FORMAT_EXTENSIBLE&&w->cbSize>=22&&
 ((const WAVEFORMATEXTENSIBLE*)w)->Samples.wValidBitsPerSample==32&&IsEqualGUID(&((const WAVEFORMATEXTENSIBLE*)w)->SubFormat,&KSDATAFORMAT_SUBTYPE_IEEE_FLOAT)));}
static BOOL la_scope(struct rt_context*c)
{return la_load(&c->state)==LA_ACTIVE&&la_load(&c->identity_ready)==2&&la_load(&c->looping_seen)&&
 !la_load(&c->invalid)&&!la_load(&c->active_ops)&&!la_load(&c->control_ops);}
struct la_guard {uint32_t generation;DWORD commit_sequence;ULONGLONG end;};
static BOOL la_recheck(struct rt_context*c,const struct la_guard*g)
{ULONGLONG now=rt_tick(),bound=(c->frequency/48000u)*1024u+(c->frequency%48000u)*1024u/48000u;
 return la_scope(c)&&la_snapshot_stable(&c->latest,g->generation)&&g->end&&now>=g->end&&now-g->end<=bound&&
 !la_load(&c->commit_active)&&la_load(&c->commit_sequence)==g->commit_sequence;}
static BOOL la_snapshot(struct rt_context*c,struct cd_snapshot*x,struct la_guard*g)
{
 struct pv_read r;DWORD i;uint32_t words[LA_SNAPSHOT_WORDS];memset(x,0,sizeof(*x));memset(g,0,sizeof(*g));
 if(!la_scope(c)||la_load(&c->commit_active))return FALSE;
 g->commit_sequence=la_load(&c->commit_sequence);
 if(!la_snapshot_copy(&c->latest,words,&g->generation))return FALSE;memcpy(&r,words,sizeof(r));g->end=r.end;
 if(!la_recheck(c,g))return FALSE;
 for(i=0;i<PV_LOCKS;i++)if(la_load(&c->slots[i].w[PS_STATE])!=PV_FREE)return FALSE;
 if(r.object!=la_load(&c->selected)||r.backing!=la_load(&c->backing)||r.device!=la_load(&c->device)||r.epoch!=la_load(&c->epoch)||
 r.flags!=1||r.audible!=1||!r.frames||r.qualified_frames!=r.frames||r.freq_num!=48000||r.freq_den!=48000||
 r.writelead!=CD_LEAD||r.sec_after>=CD_RING||r.active_before||r.active_after||r.sequence_before!=r.sequence_after||
 r.sequence_after!=g->commit_sequence||r.device_frames>UINT64_MAX-r.frames)return FALSE;
 x->position=r.sec_after;x->frame_end=r.device_frames+r.frames;x->qpc=r.end;
 x->index=g->generation/2u-1u;x->count=g->generation/2u;x->valid=1;return la_recheck(c,g);
}
static void la_publish_policy(struct rt_context*c,DWORD reason,ULONGLONG qpc)
{
 la_store(&c->status[ST_APPLIED],c->policy.early_count);la_store(&c->status[ST_EARLY],c->policy.early_count);
 la_store(&c->status[ST_REASON],reason);la_store(&c->status[ST_WRITES],c->policy.writes);la_store(&c->status[ST_CALIBRATION],c->policy.calibration);
 la_store(&c->status[ST_PAUSED],c->policy.recovery_paused);la_store(&c->status[ST_PAUSE_REASON],c->policy.pause_reason);
 la_store(&c->status[ST_PAUSELO],c->policy.pause_qpc);la_store(&c->status[ST_PAUSEHI],c->policy.pause_qpc>>32);
 la_store(&c->status[ST_RESUMELO],c->policy.resume_qpc);la_store(&c->status[ST_RESUMEHI],c->policy.resume_qpc>>32);
 la_store(&c->status[ST_PAUSE_COUNT],c->policy.pause_count);la_store(&c->status[ST_RESUME_COUNT],c->policy.resume_count);
 la_store(&c->status[ST_AFTER_RESUME],c->policy.applied_after_resume);
 if(c->policy.cutout&&!la_load(&c->status[ST_CUTOUT])){
  la_store(&c->status[ST_CUTLO],qpc);la_store(&c->status[ST_CUTHI],qpc>>32);la_store(&c->status[ST_CUTOUT],c->policy.cutout);
 }
}
static void WINAPI la_sleep(DWORD request)
{
 struct rt_context*c=__atomic_load_n(&context,__ATOMIC_ACQUIRE);DWORD incoming=GetLastError(),outgoing,effective=request,reason=CD_NOT_READY;
 DWORD caller=(DWORD)(ULONG_PTR)__builtin_return_address(0),tid=GetCurrentThreadId();BOOL observing=FALSE;
 struct cd_snapshot x={0};struct la_guard g={0};struct cd_record r={0};
 BOOL exact=c&&la_load(&c->identity_ready)==2&&tid==la_load(&c->producer_tid)&&caller==c->module_base+CL_SLEEP_RETURN_RVA;
 if(exact&&request==10){
  la_count(&c->qualified_sleep10);
  if(la_load(&c->status[ST_CUTOUT]))la_count(&c->forwarded10_after_cutout);
  if(la_load(&c->state)==LA_ACTIVE&&InterlockedCompareExchange(&c->observing,1,0)==0){
   observing=TRUE;r.decision_qpc=rt_tick();c->policy.frequency=c->frequency;
   if(!la_scope(c))reason=cd_reject(&c->policy,CD_CONTROL_CHANGED);
   else if(WaitForSingleObject(c->producer_handle,0)!=WAIT_TIMEOUT){la_fail(c,LA_THREAD_ENDED);reason=CD_CONTROL_CHANGED;}
   else{la_snapshot(c,&x,&g);reason=cd_evaluate(&c->policy,&x,&r);
    if(reason==CD_ELIGIBLE){if(la_recheck(c,&g)){effective=0;cd_commit_early(&c->policy,&r);}else reason=CD_CONTROL_CHANGED;}
    if(reason==CD_CONSUMER_STALLED)la_fail(c,LA_CUTOUT);
    else if(c->policy.invalid)la_fail(c,LA_GENERATION);
   }
   if(effective==0&&la_load(&c->status[ST_CUTOUT]))la_count(&c->applied_after_cutout);
   if(effective==10&&c->policy.recovery_paused)la_count(&c->paused_sleep10);
   la_publish_policy(c,reason,r.decision_qpc);
  }
 }
 /* Only a recursion marker spans the original call: no snapshot/admission lock. */
 SetLastError(incoming);c->original_sleep(effective);outgoing=GetLastError();
 if(observing)InterlockedExchange(&c->observing,0);SetLastError(outgoing);
}
/* Cold module validation; no game heap pointers are read from the Sleep path. */
static BOOL cl_region(BYTE*base,DWORD size,DWORD rva,DWORD bytes,BOOL write)
{
 MEMORY_BASIC_INFORMATION m;uintptr_t at,end,next;DWORD p;
 if(!bytes||rva>size||bytes>size-rva)return FALSE;at=(uintptr_t)base+rva;end=at+bytes;if(end<at)return FALSE;
 while(at<end){if(VirtualQuery((void*)at,&m,sizeof(m))!=sizeof(m)||m.AllocationBase!=base||m.State!=MEM_COMMIT||m.Type!=MEM_IMAGE||(m.Protect&(PAGE_GUARD|PAGE_NOACCESS)))return FALSE;
 p=m.Protect&255;if(p!=PAGE_READONLY&&p!=PAGE_READWRITE&&p!=PAGE_WRITECOPY&&p!=PAGE_EXECUTE_READ&&p!=PAGE_EXECUTE_READWRITE&&p!=PAGE_EXECUTE_WRITECOPY)return FALSE;
 if(write&&p!=PAGE_READWRITE&&p!=PAGE_WRITECOPY&&p!=PAGE_EXECUTE_READWRITE&&p!=PAGE_EXECUTE_WRITECOPY)return FALSE;
 next=(uintptr_t)m.BaseAddress+m.RegionSize;if(next<=at)return FALSE;at=next;}return TRUE;
}
static BOOL cl_signature(BYTE*base,DWORD size,DWORD rva,const BYTE*want,DWORD bytes,DWORD fixup)
{BYTE copy[128];DWORD target=(DWORD)(ULONG_PTR)base+CL_SLOT_RVA;
 if(bytes>sizeof(copy)||!cl_region(base,size,rva,bytes,FALSE))return FALSE;memcpy(copy,want,bytes);
 if(fixup!=0xffffffffu){if(fixup>bytes||4>bytes-fixup)return FALSE;memcpy(copy+fixup,&target,4);}return !memcmp(base+rva,copy,bytes);}
#include "clean_scope.h"
static BOOL cl_expected_module(WCHAR*path,DWORD capacity)
{
 DWORD n,i,first=0;static const WCHAR leaf[]=L"fmodex.dll";
 n=GetModuleFileNameW(NULL,path,capacity);if(!n||n>=capacity)return FALSE;
 for(i=0;i<n;i++)if(path[i]=='\\'||path[i]=='/')first=i+1;
 if(!first||lstrcmpiW(path+first,CL_IMAGE))return FALSE;
#if CL_FIXTURE
 return TRUE;
#else
 if(first>=capacity||sizeof(leaf)/sizeof(*leaf)>capacity-first)return FALSE;
 memcpy(path+first,leaf,sizeof(leaf));return TRUE;
#endif
}
static void la_install(struct rt_context*c)
{
 HMODULE module=NULL,kernel;WCHAR name[1024],expected[1024];DWORD n;IMAGE_DOS_HEADER dos;IMAGE_NT_HEADERS32 nt;BYTE*base;LONG*slot;void*original;
 la_store(&c->install_status,1);
#if CL_FIXTURE
 module=GetModuleHandleW(NULL);if(!module||!GetModuleHandleExW(GET_MODULE_HANDLE_EX_FLAG_FROM_ADDRESS,(LPCWSTR)module,&module))goto fail;
#else
 if(!GetModuleHandleExW(0,L"fmodex.dll",&module))goto fail;
#endif
 c->target=module;base=(BYTE*)module;n=GetModuleFileNameW(module,name,1024);
 if(!n||n>=1024||!cl_expected_module(expected,1024)||lstrcmpiW(name,expected))goto fail;
 if(!cl_region(base,4096,0,sizeof(dos),FALSE))goto fail;memcpy(&dos,base,sizeof(dos));
 if(dos.e_magic!=IMAGE_DOS_SIGNATURE||dos.e_lfanew>4096-sizeof(nt)||!cl_region(base,4096,dos.e_lfanew,sizeof(nt),FALSE))goto fail;
 memcpy(&nt,base+dos.e_lfanew,sizeof(nt));
 if(nt.Signature!=IMAGE_NT_SIGNATURE||nt.FileHeader.Machine!=IMAGE_FILE_MACHINE_I386||nt.OptionalHeader.Magic!=IMAGE_NT_OPTIONAL_HDR32_MAGIC||nt.OptionalHeader.SizeOfImage!=CL_IMAGE_SIZE||!cl_check_signatures(base,CL_IMAGE_SIZE))goto fail;
 if((CL_SLOT_RVA&3)||!cl_region(base,CL_IMAGE_SIZE,CL_SLOT_RVA,4,TRUE))goto fail;
 kernel=GetModuleHandleW(L"kernel32.dll");original=kernel?(void*)GetProcAddress(kernel,"Sleep"):NULL;slot=(LONG*)(base+CL_SLOT_RVA);
 if(!original||la_load(slot)!=(DWORD)(ULONG_PTR)original)goto fail;
 c->original_sleep=(la_sleep_fn)original;c->module_base=(DWORD)(ULONG_PTR)base;c->module_size=CL_IMAGE_SIZE;
 if(InterlockedCompareExchange(slot,(LONG)(ULONG_PTR)la_sleep,(LONG)(ULONG_PTR)original)!=(LONG)(ULONG_PTR)original)goto fail;
 la_store(&c->install_status,0);return;
 fail:la_fail(c,LA_INIT);
}
static void la_status(struct rt_context*c)
{
 char json[2048];WCHAR final[1024],pending[1024];DWORD wrote,st=la_load(&c->state),cut=la_load(&c->status[ST_CUTOUT]);HANDLE h;BOOL ok;
 ULONGLONG cutq=cut?((ULONGLONG)la_load(&c->status[ST_CUTLO])|((ULONGLONG)la_load(&c->status[ST_CUTHI])<<32)):0,now=rt_tick();
 int n=snprintf(json,sizeof(json),"{\"schema\":2,\"component_id\":\"%s\",\"component_version\":\"%s\",\"pid\":%lu,\"image\":\"%s\",\"install_status\":%lu,\"state\":\"%s\",\"fallback_reason\":%lu,\"uptime_ms\":%llu,\"qpc_frequency\":%llu,\"created_qpc\":%llu,\"activated_qpc\":%llu,\"cutout_uptime_ms\":%llu,\"object\":%lu,\"backing\":%lu,\"device\":%lu,\"epoch\":%lu,\"producer_tid\":%lu,\"applied\":%lu,\"last_reason\":%lu,\"cutout\":%lu,\"cutout_qpc\":%llu,\"early_action_limit\":null,\"qualified_sleep10\":%lu,\"forwarded10_after_cutout\":%lu,\"applied_after_cutout\":%lu,\"recovery_paused\":%s,\"pause_reason\":%lu,\"pause_count\":%lu,\"resume_count\":%lu,\"applied_after_resume\":%lu,\"paused_sleep10\":%lu,\"last_pause_qpc\":%llu,\"last_resume_qpc\":%llu,\"policy_revision\":10,\"telemetry_saturated\":%s,\"recording\":false,\"profiling\":false}\n",CL_COMPONENT_ID,CL_COMPONENT_VERSION,c->pid,CL_IMAGE_ASCII,la_load(&c->install_status),st==LA_ACTIVE?"active":st==LA_WAIT?"waiting":"fallback",la_load(&c->reason),(unsigned long long)((now-c->created)/(c->frequency/1000u)),(unsigned long long)c->frequency,(unsigned long long)c->created,(unsigned long long)(la_load(&c->identity_ready)==2?c->activated:0),(unsigned long long)(cutq>=c->created?(cutq-c->created)/(c->frequency/1000u):0),la_load(&c->selected),la_load(&c->backing),la_load(&c->device),la_load(&c->epoch),la_load(&c->producer_tid),la_load(&c->status[ST_APPLIED]),la_load(&c->status[ST_REASON]),cut,(unsigned long long)cutq,la_load(&c->qualified_sleep10),la_load(&c->forwarded10_after_cutout),la_load(&c->applied_after_cutout),la_load(&c->status[ST_PAUSED])?"true":"false",la_load(&c->status[ST_PAUSE_REASON]),la_load(&c->status[ST_PAUSE_COUNT]),la_load(&c->status[ST_RESUME_COUNT]),la_load(&c->status[ST_AFTER_RESUME]),la_load(&c->paused_sleep10),(unsigned long long)((ULONGLONG)la_load(&c->status[ST_PAUSELO])|((ULONGLONG)la_load(&c->status[ST_PAUSEHI])<<32)),(unsigned long long)((ULONGLONG)la_load(&c->status[ST_RESUMELO])|((ULONGLONG)la_load(&c->status[ST_RESUMEHI])<<32)),(la_load(&c->status[ST_APPLIED])==UINT32_MAX||la_load(&c->status[ST_PAUSE_COUNT])==UINT32_MAX||la_load(&c->status[ST_RESUME_COUNT])==UINT32_MAX||la_load(&c->status[ST_AFTER_RESUME])==UINT32_MAX||la_load(&c->qualified_sleep10)==UINT32_MAX||la_load(&c->forwarded10_after_cutout)==UINT32_MAX||la_load(&c->applied_after_cutout)==UINT32_MAX||la_load(&c->paused_sleep10)==UINT32_MAX)?"true":"false");
 if(n<=0||n>=sizeof(json))return;
 if(swprintf(final,1024,L"%ls\\clean-audio-%lu.json",CL_STATUS_DIRECTORY,c->pid)<0||swprintf(pending,1024,L"%ls\\clean-audio-%lu.pending",CL_STATUS_DIRECTORY,c->pid)<0)return;
 h=CreateFileW(pending,GENERIC_WRITE,0,NULL,CREATE_ALWAYS,FILE_ATTRIBUTE_NORMAL,NULL);if(h==INVALID_HANDLE_VALUE)return;
 ok=WriteFile(h,json,n,&wrote,NULL)&&wrote==(DWORD)n;CloseHandle(h);if(ok)MoveFileExW(pending,final,MOVEFILE_REPLACE_EXISTING);
}
static DWORD WINAPI la_worker(void*arg)
{struct rt_context*c=arg;la_install(c);for(;;){la_status(c);Sleep(1000);}return 0;}
static BOOL CALLBACK la_initialize(INIT_ONCE*unused,void*parameter,void**result)
{
 WCHAR name[1024];DWORD n,i,first=0;LARGE_INTEGER f;struct rt_context*c;HMODULE self;HANDLE worker;
 n=GetModuleFileNameW(NULL,name,1024);if(!n||n>=1024)return TRUE;for(i=0;i<n;i++)if(name[i]=='\\'||name[i]=='/')first=i+1;
 if(lstrcmpiW(name+first,CL_IMAGE)||!QueryPerformanceFrequency(&f)||f.QuadPart<1000)return TRUE;
 if(!GetModuleHandleExW(GET_MODULE_HANDLE_EX_FLAG_FROM_ADDRESS,(LPCWSTR)la_initialize,&self))return TRUE;
 c=HeapAlloc(GetProcessHeap(),HEAP_ZERO_MEMORY,sizeof(*c));if(!c){FreeLibrary(self);return TRUE;}
 c->self=self;c->pid=GetCurrentProcessId();c->frequency=f.QuadPart;c->created=rt_tick();c->install_status=1;
 InterlockedExchangePointer((void**)&context,c);worker=CreateThread(NULL,128*1024,la_worker,c,0,NULL);
 if(worker)CloseHandle(worker);else la_fail(c,LA_INIT);return TRUE;
}
void rt_init(void){InitOnceExecuteOnce(&once,la_initialize,NULL,NULL);}
#include "clean_provenance.c"
#include "clean_api.c"
