/* Origins reverb compatibility. LGPL-2.1-or-later.
 * Included after Windows/API declarations (Wine winmm.c or the owned fixture).
 * No proprietary payload; exact-version byte pins are cold compatibility gates. */
#include "origins_reverb_hooks.h"
#include "reverb_config.h"
#include "reverb_dry.h"
#include "reverb_scope.h"
#include "factory_scope.h"

#ifdef __i386__
typedef int (WINAPI *or_create_fn)(void **);
typedef int (WINAPI *or_plugins_fn)(void *,int,int *);
static const char or_create_name[] = "_FMOD_System_Create@4";
static const char or_plugins_name[] = "_FMOD_System_GetNumPlugins@12";
static or_create_fn or_original_create;
static HMODULE or_fmod;
static DWORD or_bridge_base;
static LONG or_cold_state; /* 0 untried, 1 checking, 2 ready, -1 failed; never wait. */
static or_plugins_fn or_plugins;
static DWORD or_fmod_base;
static struct origins_reverb_status or_status = {.bytes=sizeof(or_status),.version=1};
static LONG or_first_system,or_last_creation_reason,or_telemetry_saturated;
static ULONGLONG or_created_tick_ms;

static LONG or_count(LONG *p) { return InterlockedCompareExchange(p,0,0); }
static BOOL or_span(DWORD address,DWORD bytes,BOOL writable)
{
    MEMORY_BASIC_INFORMATION m;
    DWORD offset;
    if(!address || !bytes || address>~(DWORD)0-bytes) return FALSE;
    if(VirtualQuery((void *)(ULONG_PTR)address,&m,sizeof(m))!=sizeof(m) ||
       m.State!=MEM_COMMIT || (m.Protect&(PAGE_GUARD|PAGE_NOACCESS)) ||
       !(m.Protect&(writable ? (PAGE_READWRITE|PAGE_WRITECOPY|PAGE_EXECUTE_READWRITE|PAGE_EXECUTE_WRITECOPY) :
          (PAGE_READONLY|PAGE_READWRITE|PAGE_WRITECOPY|PAGE_EXECUTE_READ|PAGE_EXECUTE_READWRITE|PAGE_EXECUTE_WRITECOPY))) ||
       address<(DWORD)(ULONG_PTR)m.BaseAddress) return FALSE;
    offset=address-(DWORD)(ULONG_PTR)m.BaseAddress;
    return offset<=m.RegionSize && bytes<=m.RegionSize-offset;
}
static BOOL or_read(DWORD address,void *out,SIZE_T bytes)
{
    SIZE_T got=0;
    return bytes<=0xffffffffu && or_span(address,(DWORD)bytes,FALSE) &&
           ReadProcessMemory(GetCurrentProcess(),(const void *)(ULONG_PTR)address,out,bytes,&got) && got==bytes;
}
static BOOL or_word(DWORD address,DWORD *out)
{ return !(address&3u) && or_read(address,out,sizeof(*out)); }
static BOOL or_pe(HMODULE module,DWORD stamp,DWORD size,DWORD entry)
{
    IMAGE_DOS_HEADER dos; IMAGE_NT_HEADERS32 nt; DWORD base=(DWORD)(ULONG_PTR)module;
    if(!or_read(base,&dos,sizeof(dos)) || dos.e_magic!=IMAGE_DOS_SIGNATURE || dos.e_lfanew<64 || dos.e_lfanew>4096 ||
       base>~(DWORD)0-(DWORD)dos.e_lfanew || !or_read(base+dos.e_lfanew,&nt,sizeof(nt)))return FALSE;
    return nt.Signature==IMAGE_NT_SIGNATURE && nt.FileHeader.Machine==IMAGE_FILE_MACHINE_I386 &&
           nt.OptionalHeader.Magic==IMAGE_NT_OPTIONAL_HDR32_MAGIC &&
           nt.FileHeader.TimeDateStamp==stamp && nt.OptionalHeader.SizeOfImage==size &&
           nt.OptionalHeader.AddressOfEntryPoint==entry;
}
static BOOL or_same_directory(HMODULE module,const WCHAR *directory,const WCHAR *name)
{
    WCHAR path[MAX_PATH],expected[MAX_PATH];DWORD n;
    if(wcslen(directory)+wcslen(name)>=MAX_PATH)return FALSE;
    wcscpy(expected,directory);wcscat(expected,name);
    n=GetModuleFileNameW(module,path,ARRAY_SIZE(path));
    return n && n<ARRAY_SIZE(path) && !wcsicmp(path,expected);
}
void origins_reverb_get_status(struct origins_reverb_status *out)
{
    DWORD saved=GetLastError();
    if(out){
        out->bytes=sizeof(*out);out->version=1;out->attach_status=or_status.attach_status;
#define OR_COPY(f) out->f=or_count(&or_status.f)
        OR_COPY(create_calls);OR_COPY(original_failures);OR_COPY(other_types);OR_COPY(target_successes);
        OR_COPY(replaced);OR_COPY(validation_failures);OR_COPY(compare_failures);
        OR_COPY(reporter_started);OR_COPY(log_failures);
#undef OR_COPY
    }
    SetLastError(saved);
}
/* Fixed-size metadata only, on a cold worker. No PCM, paths or user data are
 * recorded. Atomic replacement bounds storage to one JSON file per process. */
static void or_report(DWORD generation)
{
    struct origins_reverb_status s;struct rv_dry_counts d;char json[2048];int n;
    WCHAR final[MAX_PATH],pending[MAX_PATH];HANDLE file;DWORD done=0;BOOL ok;
    ULONGLONG now=GetTickCount64();const char *state;
    origins_reverb_get_status(&s);rv_dry_get_counters(&d);
    if(d.dry_calls>=0x70000000u||d.original_fallback_calls>=0x70000000u||
       d.invalid_or_unsupported>=0x70000000u||d.not_ready_calls>=0x70000000u||
       (DWORD)s.log_failures>=0x70000000u||generation>=0x70000000u)
        InterlockedExchange(&or_telemetry_saturated,1);
    state=s.attach_status==OR_REVERB_ACTIVE?(d.dry_calls?"active":"waiting_audio"):
          s.attach_status==OR_REVERB_ATTACHED?"waiting_system":"inactive";
    n=snprintf(json,sizeof(json),
        "{\"schema\":1,\"component_id\":\"%s\",\"component_version\":\"%s\","
        "\"policy_revision\":1,\"image\":\"DAOrigins.exe\",\"pid\":%lu,\"generation\":%lu,"
        "\"route\":\"system_registry\",\"state\":\"%s\",\"install_status\":%lu,\"cold_state\":%ld,"
        "\"created_tick_ms\":%llu,\"tick_ms\":%llu,\"uptime_ms\":%llu,\"system\":%lu,"
        "\"create_calls\":%lu,\"original_failures\":%lu,\"scope_skipped\":%lu,"
        "\"target_successes\":%lu,\"replaced\":%lu,\"validation_failures\":%lu,\"compare_failures\":%lu,"
        "\"last_creation_reason\":%lu,\"dry_calls\":%lu,\"original_fallback_calls\":%lu,"
        "\"invalid_or_unsupported\":%lu,\"not_ready_calls\":%lu,\"status_write_failures\":%lu,"
        "\"reporter_started\":%ld,\"telemetry_saturated\":%s,\"callback_policy\":\"process_lifetime\","
        "\"changes_buffer_size\":false,\"recording\":false,\"profiling\":false}\n",
        OR_COMPONENT_ID,OR_COMPONENT_VERSION,GetCurrentProcessId(),generation,state,s.attach_status,or_count(&or_cold_state),
        (unsigned long long)or_created_tick_ms,(unsigned long long)now,(unsigned long long)(now-or_created_tick_ms),
        (DWORD)or_count(&or_first_system),(DWORD)s.create_calls,(DWORD)s.original_failures,(DWORD)s.other_types,
        (DWORD)s.target_successes,(DWORD)s.replaced,(DWORD)s.validation_failures,(DWORD)s.compare_failures,
        (DWORD)or_count(&or_last_creation_reason),d.dry_calls,d.original_fallback_calls,d.invalid_or_unsupported,d.not_ready_calls,
        (DWORD)s.log_failures,s.reporter_started,or_count(&or_telemetry_saturated)?"true":"false");
    if(n<=0||n>=sizeof(json))return;
    if(swprintf(final,ARRAY_SIZE(final),L"%ls\\reverb-%lu.json",OR_STATUS_DIRECTORY,GetCurrentProcessId())<0||
       swprintf(pending,ARRAY_SIZE(pending),L"%ls\\reverb-%lu.pending",OR_STATUS_DIRECTORY,GetCurrentProcessId())<0)return;
    file=CreateFileW(pending,GENERIC_WRITE,0,NULL,CREATE_ALWAYS,FILE_ATTRIBUTE_NORMAL,NULL);
    if(file==INVALID_HANDLE_VALUE){InterlockedIncrement(&or_status.log_failures);return;}
    ok=WriteFile(file,json,n,&done,NULL)&&done==(DWORD)n;CloseHandle(file);
    if(!ok||!MoveFileExW(pending,final,MOVEFILE_REPLACE_EXISTING))InterlockedIncrement(&or_status.log_failures);
}
static DWORD WINAPI or_report_thread(void *unused)
{
    DWORD generation=0;(void)unused;
    for(;;){or_report(generation);if(generation!=0xffffffffu)generation++;Sleep(OR_REPORT_INTERVAL_MS);}
    return 0;
}
static void or_start_reporter(void)
{
    HANDLE h;
    /* Called only from the ordinary original creation caller, never attach. */
    if(InterlockedCompareExchange(&or_status.reporter_started,1,0))return;
    h=CreateThread(NULL,0,or_report_thread,NULL,0,NULL);
    if(h)CloseHandle(h);
    else {InterlockedExchange(&or_status.reporter_started,-1);InterlockedIncrement(&or_status.log_failures);}
}
/* First ordinary Create return is after unpacking. No executable pins or public
 * FMOD calls occur under the dependency's DllMain/loader lock. */
static BOOL or_cold_qualify(void)
{
    BYTE bytes[64];DWORD i,word;FARPROC fn;
    LONG state=InterlockedCompareExchange(&or_cold_state,1,0);
    if(state) return state==2;
    for(i=0;i<RV_SEMANTIC_PIN_COUNT;i++){
        const struct rv_semantic_pin *p=&rv_semantic_pins[i];
        if(p->bytes>sizeof(bytes)||p->rva>0xbd000u-p->bytes||
           !or_read(or_fmod_base+p->rva,bytes,p->bytes)||memcmp(bytes,p->value,p->bytes))goto bad;
    }
    for(i=0;i<RF_PIN_COUNT;i++){
        const struct rf_pin *p=&rf_pins[i];
        if(p->bytes>sizeof(bytes)||p->rva>0xbd000u-p->bytes||
           !or_read(or_fmod_base+p->rva,bytes,p->bytes)||memcmp(bytes,p->value,p->bytes))goto bad;
    }
    if(!or_word(or_fmod_base+RV_DRY_FILTER_VTABLE_RVA+4,&word)||word!=or_fmod_base+0x4960bu)goto bad;
    fn=GetProcAddress(or_fmod,or_plugins_name);
    if((DWORD)(ULONG_PTR)fn!=or_fmod_base+0x185bu)goto bad;
    or_plugins=(or_plugins_fn)fn;
    if(!rv_dry_initialize((rv_read_fn)(ULONG_PTR)(or_fmod_base+RV_DRY_READ_CALLBACK_RVA),or_fmod_base))goto bad;
    InterlockedExchange(&or_cold_state,2);return TRUE;
bad:
    InterlockedExchange(&or_cold_state,-1);or_status.attach_status=OR_REVERB_BAD_STATIC;return FALSE;
}
static void or_creation_record(LONG ordinal,int result,DWORD system,DWORD registry,
                               DWORD descriptor,int count,DWORD reason,BOOL changed)
{
    (void)ordinal;(void)result;(void)registry;(void)descriptor;(void)count;
    /* Record a scalar identity only. It is never dereferenced after Create. */
    if(changed)InterlockedCompareExchange(&or_first_system,(LONG)system,0);
    InterlockedExchange(&or_last_creation_reason,(LONG)reason);
}
static DWORD or_validate_newborn(void **output,DWORD *system)
{
    BYTE flags[2];DWORD registry,vtable;
    if(!output||!or_word((DWORD)(ULONG_PTR)output,system))return 1;
    if(!*system||(*system&3u)||*system>~(DWORD)0-0xa2f0u)return 2;
    if(!or_word(*system,&vtable)||vtable!=or_fmod_base+0x68904u)return 3;
    if(!or_read(*system+0x15u,flags,2)||flags[0]||flags[1])return 4;
    if(!or_word(*system+0x93dcu,&registry)||registry)return 5;
    return 0;
}
static BOOL or_descriptor_matches(const BYTE *p)
{
    DWORD value;
#define OR_DWORD(off) (memcpy(&value,p+(off),4),value)
    if(memcmp(p,"SFX Reverb\0",11)||OR_DWORD(0x20)!=0x10100u||OR_DWORD(0x24)!=0u||
       OR_DWORD(0x28)!=or_fmod_base+0x52554u||OR_DWORD(0x2c)!=or_fmod_base+0x51968u||
       OR_DWORD(0x30)!=or_fmod_base+0x5197du||OR_DWORD(0x34)!=or_fmod_base+0x51992u||
       OR_DWORD(0x3c)!=15u||OR_DWORD(0x40)!=or_fmod_base+0x854f0u||
       OR_DWORD(0x44)!=or_fmod_base+0x519b9u||OR_DWORD(0x48)!=or_fmod_base+0x519dau||
       OR_DWORD(0x90)!=or_fmod_base+0x51fffu||OR_DWORD(0x94)!=or_fmod_base+0x52569u||
       OR_DWORD(0x6c)!=18u||OR_DWORD(0x70)!=0x770u||OR_DWORD(0x74)!=0u)return FALSE;
#undef OR_DWORD
    return TRUE;
}
/* Only the still-unpublished newborn's list is inspected. Complete bounded
 * circular-list/owner checks precede the single aligned data CAS. No pointer is
 * retained for later access, and no live DSP object/graph is mutated. */
static DWORD or_registry(DWORD system,int count,DWORD *registry,DWORD *descriptor)
{
    DWORD owner,sentinel,next,previous,tail,links[2],seen[64],i,j,type;
    BYTE flags[2],record[0x98];
    if(count<1||count>64)return 10;
    if(!or_read(system+0x15u,flags,2)||flags[0]||flags[1]!=1)return 11;
    if(!or_word(system+0x93dcu,registry)||!*registry||(*registry&3u)||*registry>~(DWORD)0-0x2b8u)return 12;
    if(!or_word(*registry+0x2b0u,&owner)||owner!=system)return 13;
    sentinel=*registry+0x160u;
    if(!or_read(sentinel,links,8))return 14;
    next=links[0];tail=links[1];previous=sentinel;
    for(i=0;i<(DWORD)count;i++){
        DWORD candidate;
        if(!next||(next&3u)||next==sentinel||next<0x5cu)return 15;
        for(j=0;j<i;j++)if(seen[j]==next)return 16;
        seen[i]=next;candidate=next-0x5cu;
        if(candidate>~(DWORD)0-0x98u||!or_read(candidate,record,sizeof(record)))return 17;
        memcpy(links,record+0x5c,8);
        if(links[1]!=previous)return 18;
        memcpy(&type,record+0x6c,4);
        if(type==18u){
            if(*descriptor||!or_descriptor_matches(record))return 19;
            *descriptor=candidate;
        }
        previous=next;next=links[0];
    }
    if(next!=sentinel||previous!=tail||!*descriptor)return 20;
    /* Sentinel/owner/flags must remain coherent before writing the owned record. */
    if(!or_read(sentinel,links,8)||links[0]!=seen[0]||links[1]!=tail||
       !or_word(*registry+0x2b0u,&owner)||owner!=system||
       !or_read(system+0x15u,flags,2)||flags[0]||flags[1]!=1)return 21;
    if(!or_span(*descriptor+0x34u,4,TRUE))return 22;
    return 0;
}
static int WINAPI or_create(void **output)
{
    DWORD incoming=GetLastError(),outgoing,system=0,registry=0,descriptor=0,reason=0;
    DWORD caller=(DWORD)(ULONG_PTR)__builtin_return_address(0);
    BOOL changed=FALSE;int count=0,result;LONG old;
    LONG ordinal=InterlockedIncrement(&or_status.create_calls);
    SetLastError(incoming);result=or_original_create(output);outgoing=GetLastError();
    if(result){InterlockedIncrement(&or_status.original_failures);reason=30;}
    else if(ordinal>16||caller!=or_bridge_base+0x10dadu){
        InterlockedIncrement(&or_status.other_types);reason=31;
    }else if(!or_cold_qualify())reason=32;
    else {
        reason=or_validate_newborn(output,&system);
        if(!reason){
            InterlockedIncrement(&or_status.target_successes);
            if(or_plugins((void *)(ULONG_PTR)system,2,&count))reason=33;
            else reason=or_registry(system,count,&registry,&descriptor);
        }
        if(!reason){
            old=InterlockedCompareExchange((LONG *)(ULONG_PTR)(descriptor+0x34u),
                (LONG)(ULONG_PTR)rv_dry_callback,(LONG)(or_fmod_base+RV_DRY_READ_CALLBACK_RVA));
            if((DWORD)old==or_fmod_base+RV_DRY_READ_CALLBACK_RVA){
                changed=TRUE;InterlockedIncrement(&or_status.replaced);or_status.attach_status=OR_REVERB_ACTIVE;
            }else{reason=34;InterlockedIncrement(&or_status.compare_failures);}
        }
    }
    if(reason&&reason!=30&&reason!=31&&reason!=34)InterlockedIncrement(&or_status.validation_failures);
    or_creation_record(ordinal,result,system,registry,descriptor,count,reason,changed);
    /* Immediate failure evidence also exists; activation still requires dry_calls. */
    or_start_reporter();
    SetLastError(outgoing);return result;
}
static BOOL or_string(BYTE *base,DWORD size,DWORD rva,const char *value)
{
    SIZE_T n=strlen(value);
    return rva<size && n<size-rva && !memcmp(base+rva,value,n+1);
}
static DWORD *or_import_slot(HMODULE bridge)
{
    BYTE *base=(BYTE *)bridge;IMAGE_DOS_HEADER *dos=(IMAGE_DOS_HEADER *)bridge;
    IMAGE_NT_HEADERS32 *nt=(IMAGE_NT_HEADERS32 *)(base+dos->e_lfanew);
    DWORD size=nt->OptionalHeader.SizeOfImage,rva=nt->OptionalHeader.DataDirectory[IMAGE_DIRECTORY_ENTRY_IMPORT].VirtualAddress;
    DWORD length=nt->OptionalHeader.DataDirectory[IMAGE_DIRECTORY_ENTRY_IMPORT].Size,end,i;
    if(!rva||rva>=size||length<sizeof(IMAGE_IMPORT_DESCRIPTOR)||length>size-rva)return NULL;
    end=rva+length;
    for(;rva<=end-sizeof(IMAGE_IMPORT_DESCRIPTOR);rva+=sizeof(IMAGE_IMPORT_DESCRIPTOR)){
        IMAGE_IMPORT_DESCRIPTOR *d=(IMAGE_IMPORT_DESCRIPTOR *)(base+rva);
        if(!d->Name)break;
        if(!or_string(base,size,d->Name,"fmodex.dll"))continue;
        if(!d->OriginalFirstThunk||d->OriginalFirstThunk>=size||d->FirstThunk>=size)return NULL;
        for(i=0;i<2048;i++){
            DWORD lookup,target,name;
            if(i>(size-d->OriginalFirstThunk)/4 || i>(size-d->FirstThunk)/4)return NULL;
            lookup=d->OriginalFirstThunk+i*4;target=d->FirstThunk+i*4;
            if(lookup>size-4||target>size-4)return NULL;
            name=*(DWORD *)(base+lookup);if(!name)break;
            if(IMAGE_SNAP_BY_ORDINAL32(name)||name>size-2||!or_string(base,size,name+2,or_create_name))continue;
            if(target!=0x34278u)return NULL;
            return (DWORD *)(base+target);
        }
    }
    return NULL;
}
BOOL origins_reverb_attach(const struct origins_reverb_config *c)
{
    DWORD saved=GetLastError(),*slot=NULL,oldprotect,restoreprotect;BOOL ok=FALSE;
    HMODULE pinned=NULL;FARPROC original;WCHAR directory[MAX_PATH],*name;DWORD length;
    if(or_status.attach_status){SetLastError(saved);return FALSE;}
    or_status.attach_status=OR_REVERB_BAD_CONFIG;
    if(!c||c->bytes!=sizeof(*c)||c->version!=ORIGINS_REVERB_CONFIG_VERSION)goto done;
    or_status.attach_status=OR_REVERB_BAD_MODULE;
    length=GetModuleFileNameW(c->main_module,directory,ARRAY_SIZE(directory));
    if(!length||length>=ARRAY_SIZE(directory)||(name=wcsrchr(directory,'\\'))==NULL)goto done;
    name++;
    if(wcsicmp(name,L"DAOrigins.exe")||!or_pe(c->main_module,0x4eb19d53,0xa49000,0x9ed2ee))goto done;
    *name=0;
    if(!or_pe(c->fmod_module,0x4b01a22c,0xbd000,0xb2770)||
       !or_same_directory(c->fmod_module,directory,L"fmodex.dll"))goto done;
    if(!or_pe(c->bridge_module,0x4b01a23d,0x47000,0x32dec)||
       !or_same_directory(c->bridge_module,directory,L"fmod_event.dll"))goto done;
    /* Packed FMOD code is not ready during this dependency's DllMain. Only
     * resolve its public export address and stage the import; defer code reads. */
    or_fmod=c->fmod_module;or_fmod_base=(DWORD)(ULONG_PTR)or_fmod;
    original=GetProcAddress(or_fmod,or_create_name);
    if((DWORD)(ULONG_PTR)original!=or_fmod_base+0x11bfu)goto done;
    or_status.attach_status=OR_REVERB_BAD_IMPORT;
    slot=or_import_slot(c->bridge_module);
    if(!slot||*slot!=(DWORD)(ULONG_PTR)original)goto done;
    or_status.attach_status=OR_REVERB_PIN_FAILED;
    if(!GetModuleHandleExW(GET_MODULE_HANDLE_EX_FLAG_FROM_ADDRESS|GET_MODULE_HANDLE_EX_FLAG_PIN,
         (LPCWSTR)(ULONG_PTR)origins_reverb_attach,&pinned))goto done;
    or_created_tick_ms=GetTickCount64();
    or_original_create=(or_create_fn)original;
    or_bridge_base=(DWORD)(ULONG_PTR)c->bridge_module;
    or_status.attach_status=OR_REVERB_IMPORT_PROTECT_FAILED;
    if(!VirtualProtect(slot,sizeof(*slot),PAGE_READWRITE,&oldprotect))goto done;
    or_status.attach_status=OR_REVERB_IMPORT_CHANGED;
    if((DWORD)InterlockedCompareExchange((LONG *)slot,(LONG)(ULONG_PTR)or_create,(LONG)(ULONG_PTR)original)!=(DWORD)(ULONG_PTR)original){
        VirtualProtect(slot,sizeof(*slot),oldprotect,&restoreprotect);goto done;
    }
    if(!VirtualProtect(slot,sizeof(*slot),oldprotect,&restoreprotect)){
        or_status.attach_status=OR_REVERB_IMPORT_RESTORE_FAILED;
        InterlockedCompareExchange((LONG *)slot,(LONG)(ULONG_PTR)original,(LONG)(ULONG_PTR)or_create);
        VirtualProtect(slot,sizeof(*slot),oldprotect,&restoreprotect);goto done;
    }
    or_status.attach_status=OR_REVERB_ATTACHED;ok=TRUE;
done:SetLastError(saved);return ok;
}
#else
BOOL origins_reverb_attach(const struct origins_reverb_config *c){(void)c;return FALSE;}
void origins_reverb_get_status(struct origins_reverb_status *out){if(out)*out=(struct origins_reverb_status){.bytes=sizeof(*out),.version=1};}
#endif
