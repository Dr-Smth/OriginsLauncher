/* Host fault-injection tests for the exact creation wrapper; no Wine/game launch.
 * Synthetic addresses are handled by mocked RPM/VirtualQuery/CAS only. */
#include <stdint.h>
#include <stddef.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <wchar.h>
#include <stdarg.h>
typedef uint8_t BYTE;typedef uint16_t WORD;typedef uint32_t DWORD;typedef int32_t LONG;
typedef uint64_t ULONGLONG;typedef int BOOL;typedef uintptr_t ULONG_PTR;typedef size_t SIZE_T;typedef wchar_t WCHAR;
typedef void *HANDLE,*HMODULE;typedef const WCHAR *LPCWSTR;typedef void (*FARPROC)(void);
#define WINAPI
#define TRUE 1
#define FALSE 0
#define MAX_PATH 260
#define ARRAY_SIZE(x) (sizeof(x)/sizeof((x)[0]))
#define MEM_COMMIT 0x1000
#define PAGE_NOACCESS 1
#define PAGE_READONLY 2
#define PAGE_READWRITE 4
#define PAGE_WRITECOPY 8
#define PAGE_EXECUTE_READ 0x20
#define PAGE_EXECUTE_READWRITE 0x40
#define PAGE_EXECUTE_WRITECOPY 0x80
#define PAGE_GUARD 0x100
#define GENERIC_WRITE 1
#define CREATE_ALWAYS 2
#define MOVEFILE_REPLACE_EXISTING 1
#define FILE_SHARE_READ 1
#define FILE_SHARE_WRITE 2
#define OPEN_ALWAYS 4
#define FILE_ATTRIBUTE_NORMAL 0x80
#define INVALID_HANDLE_VALUE ((HANDLE)(ULONG_PTR)-1)
#define GET_MODULE_HANDLE_EX_FLAG_FROM_ADDRESS 4
#define GET_MODULE_HANDLE_EX_FLAG_PIN 1
#define IMAGE_DOS_SIGNATURE 0x5a4d
#define IMAGE_NT_SIGNATURE 0x4550
#define IMAGE_FILE_MACHINE_I386 0x14c
#define IMAGE_NT_OPTIONAL_HDR32_MAGIC 0x10b
#define IMAGE_DIRECTORY_ENTRY_IMPORT 1
#define IMAGE_SNAP_BY_ORDINAL32(x) ((x)&0x80000000u)
typedef struct{void *BaseAddress,*AllocationBase;DWORD AllocationProtect;SIZE_T RegionSize;DWORD State,Protect,Type;}MEMORY_BASIC_INFORMATION;
typedef struct{WORD e_magic;BYTE pad[58];LONG e_lfanew;}IMAGE_DOS_HEADER;
typedef struct{DWORD VirtualAddress,Size;}IMAGE_DATA_DIRECTORY;
typedef struct{WORD Magic;DWORD SizeOfImage,AddressOfEntryPoint;IMAGE_DATA_DIRECTORY DataDirectory[16];}OPTIONAL;
typedef struct{WORD Machine;DWORD TimeDateStamp;}FILEHDR;
typedef struct{DWORD Signature;FILEHDR FileHeader;OPTIONAL OptionalHeader;}IMAGE_NT_HEADERS32;
typedef struct{DWORD OriginalFirstThunk,TimeDateStamp,ForwarderChain,Name,FirstThunk;}IMAGE_IMPORT_DESCRIPTOR;

static DWORD mock_caller=0x60010dad;
#define __builtin_return_address(n) ((void*)(uintptr_t)mock_caller)
static DWORD last_error,failed_read,short_read,guard_address,readonly_address;
static DWORD sysaddr=0x30000000,outaddr=0x20000000,regaddr=0x40000000,descaddr=0x50001000,otheraddr=0x50002000;
static BYTE sysmem[0xa2f0],outmem[4],regmem[0x2b8],descmem[0x98],othermem[0x98];
static DWORD cas_conflict,cas_count,read_count,thread_count,plugin_count,plugin_calls;
static int original_result,original_count,plugin_result;static DWORD original_seen_error;
static void *expected_output;
#define CHECK(x) do{if(!(x)){fprintf(stderr,"line%d %s\n",__LINE__,#x);exit(1);}}while(0)
static BYTE *mapped(DWORD a,SIZE_T n){
 struct{DWORD base;BYTE*p;SIZE_T n;}r[]={{sysaddr,sysmem,sizeof(sysmem)},{outaddr,outmem,sizeof(outmem)},
 {regaddr,regmem,sizeof(regmem)},{descaddr,descmem,sizeof(descmem)},{otheraddr,othermem,sizeof(othermem)}};
 unsigned i;for(i=0;i<ARRAY_SIZE(r);i++)if(a>=r[i].base&&a-r[i].base<=r[i].n&&n<=r[i].n-(a-r[i].base))return r[i].p+a-r[i].base;
 return NULL;
}
static void put(BYTE*p,unsigned o,DWORD v){memcpy(p+o,&v,4);}
static DWORD get(BYTE*p,unsigned o){DWORD v;memcpy(&v,p+o,4);return v;}
static DWORD GetLastError(void){return last_error;}
static void SetLastError(DWORD x){last_error=x;}
static LONG InterlockedCompareExchange(LONG*p,LONG x,LONG compare){
 if((ULONG_PTR)p==descaddr+0x34){DWORD old=cas_conflict?cas_conflict:get(descmem,0x34);cas_count++;if(old==(DWORD)compare)put(descmem,0x34,x);last_error=0xabc1;return (LONG)old;}
 LONG old=*p;if(old==compare)*p=x;return old;
}
static LONG InterlockedIncrement(LONG*p){return ++*p;}
static LONG InterlockedExchange(LONG*p,LONG x){LONG old=*p;*p=x;return old;}
static HANDLE GetCurrentProcess(void){return (HANDLE)(ULONG_PTR)-1;}
static DWORD GetCurrentProcessId(void){return 77;}
static DWORD GetCurrentThreadId(void){return 88;}
static unsigned long long GetTickCount64(void){return 99;}
static SIZE_T VirtualQuery(const void*a,MEMORY_BASIC_INFORMATION*m,SIZE_T bytes){
 DWORD address=(DWORD)(ULONG_PTR)a;last_error=0xabc2;memset(m,0,sizeof(*m));
 m->BaseAddress=(void*)(ULONG_PTR)(address&~0xfffffu);m->RegionSize=0x100000;m->State=MEM_COMMIT;
 m->Protect=address==guard_address?PAGE_READWRITE|PAGE_GUARD:address==readonly_address?PAGE_READONLY:PAGE_READWRITE;
 return bytes;
}
static BOOL ReadProcessMemory(HANDLE p,const void*a,void*out,SIZE_T bytes,SIZE_T*got){
 DWORD address=(DWORD)(ULONG_PTR)a;BYTE*source;(void)p;read_count++;last_error=0xabc3;*got=0;
 if(address==failed_read)return FALSE;
 if(address==short_read){*got=1;return TRUE;}
 source=mapped(address,bytes);if(!source)return FALSE;memcpy(out,source,bytes);*got=bytes;return TRUE;
}
static HANDLE CreateThread(void*a,SIZE_T s,DWORD(WINAPI*f)(void*),void*b,DWORD flags,DWORD*tid){
 (void)a;(void)s;(void)f;(void)b;(void)flags;(void)tid;thread_count++;last_error=0xabc4;return (HANDLE)1;
}
static BOOL CloseHandle(HANDLE h){(void)h;last_error=0xabc5;return TRUE;}
static void Sleep(DWORD n){(void)n;abort();}
static char status_json[4096];static DWORD status_bytes,status_writes,fail_write,fail_move;
static HANDLE CreateFileW(const WCHAR*a,DWORD b,DWORD c,void*d,DWORD e,DWORD f,HANDLE g){(void)c;(void)d;(void)f;(void)g;CHECK(b==GENERIC_WRITE&&e==CREATE_ALWAYS);CHECK(wcsstr(a,L"reverb-77.pending")!=NULL);return (HANDLE)1;}
static BOOL WriteFile(HANDLE a,const void*b,DWORD c,DWORD*d,void*e){(void)a;(void)e;CHECK(c<sizeof(status_json));memcpy(status_json,b,c);status_json[c]=0;status_bytes=c;*d=c;status_writes++;return !fail_write;}
static BOOL MoveFileExW(const WCHAR*a,const WCHAR*b,DWORD f){CHECK(wcsstr(a,L"reverb-77.pending")&&wcsstr(b,L"reverb-77.json")&&f==MOVEFILE_REPLACE_EXISTING);return !fail_move;}
static DWORD GetModuleFileNameW(HMODULE h,WCHAR*out,DWORD n){(void)h;(void)out;(void)n;return 0;}
static FARPROC GetProcAddress(HMODULE h,const char*s){(void)h;(void)s;return NULL;}
static BOOL GetModuleHandleExW(DWORD f,LPCWSTR p,HMODULE*out){(void)f;(void)p;(void)out;return FALSE;}
static BOOL VirtualProtect(void*a,SIZE_T n,DWORD p,DWORD*out){(void)a;(void)n;(void)p;(void)out;return FALSE;}
static int test_snprintf(char*a,SIZE_T n,const char*f,...){char fmt[4096];size_t i=0,j=0;for(;f[i];i++){if(f[i]=='%'&&f[i+1]=='l'&&(f[i+2]=='u'||f[i+2]=='d')){fmt[j++]='%';fmt[j++]=f[i+2];i+=2;}else fmt[j++]=f[i];}fmt[j]=0;va_list v;va_start(v,f);int out=vsnprintf(a,n,fmt,v);va_end(v);return out;}
static int test_swprintf(WCHAR*a,SIZE_T n,const WCHAR*f,...){WCHAR fmt[1024];size_t i=0,j=0;for(;f[i];i++){if(f[i]=='%'&&f[i+1]=='l'&&(f[i+2]=='u'||f[i+2]=='d')){fmt[j++]='%';fmt[j++]=f[i+2];i+=2;}else fmt[j++]=f[i];}fmt[j]=0;va_list v;va_start(v,f);int out=vswprintf(a,n,fmt,v);va_end(v);return out;}
#define swprintf test_swprintf
#define snprintf test_snprintf
#define wcsicmp wcscasecmp
#ifndef __i386__
#define __i386__ 1
#endif
#include "origins_reverb_hooks.c"
BOOL rv_dry_initialize(rv_read_fn f,DWORD base){(void)f;(void)base;return TRUE;}
int WINAPI rv_dry_callback(void*s,float*i,float*o,unsigned f,int a,int b){(void)s;(void)i;(void)o;(void)f;(void)a;(void)b;return 0;}
static struct rv_dry_counts fake_counts;
void rv_dry_get_counters(struct rv_dry_counts*c){*c=fake_counts;}
static int WINAPI original(void**o){
 original_count++;original_seen_error=GetLastError();CHECK(o==expected_output);
 SetLastError(0xf00d1234);return original_result;
}
static int WINAPI plugins(void*s,int type,int*n){
 CHECK((ULONG_PTR)s==sysaddr&&type==2);plugin_calls++;*n=plugin_count;
 sysmem[0x16]=1;put(sysmem,0x93dc,regaddr);SetLastError(0xbad123);return plugin_result;
}
static void reset(void){
 failed_read=short_read=guard_address=readonly_address=cas_conflict=cas_count=read_count=thread_count=plugin_calls=0;
 original_count=0;original_result=plugin_result=0;plugin_count=2;last_error=0x12345678;
 or_fmod_base=0x10000000;or_original_create=original;or_cold_state=2;or_plugins=plugins;or_bridge_base=0x60000000;mock_caller=0x60010dad;
 memset(&or_status,0,sizeof(or_status));or_status.bytes=sizeof(or_status);or_status.version=1;or_status.attach_status=OR_REVERB_ATTACHED;or_first_system=or_last_creation_reason=or_telemetry_saturated=0;or_created_tick_ms=0;
 memset(&fake_counts,0,sizeof(fake_counts));status_bytes=status_writes=fail_write=fail_move=0;
 memset(sysmem,0,sizeof(sysmem));memset(outmem,0,sizeof(outmem));memset(regmem,0,sizeof(regmem));memset(descmem,0,sizeof(descmem));memset(othermem,0,sizeof(othermem));
 put(sysmem,0,or_fmod_base+0x68904);put(outmem,0,sysaddr);put(regmem,0x2b0,sysaddr);
 put(regmem,0x160,otheraddr+0x5c);put(regmem,0x164,descaddr+0x5c);
 put(othermem,0x5c,descaddr+0x5c);put(othermem,0x60,regaddr+0x160);put(othermem,0x6c,2);
 put(descmem,0x5c,regaddr+0x160);put(descmem,0x60,otheraddr+0x5c);
 memcpy(descmem,"SFX Reverb",11);put(descmem,0x20,0x10100);
 put(descmem,0x28,or_fmod_base+0x52554);put(descmem,0x2c,or_fmod_base+0x51968);put(descmem,0x30,or_fmod_base+0x5197d);
 put(descmem,0x34,or_fmod_base+0x51992);put(descmem,0x3c,15);put(descmem,0x40,or_fmod_base+0x854f0);put(descmem,0x44,or_fmod_base+0x519b9);put(descmem,0x48,or_fmod_base+0x519da);
 put(descmem,0x6c,18);put(descmem,0x70,0x770);put(descmem,0x90,or_fmod_base+0x51fff);put(descmem,0x94,or_fmod_base+0x52569);
 expected_output=(void*)(ULONG_PTR)outaddr;
}
static unsigned tests;
static void invoke(BOOL changed){
 int result=or_create(expected_output);
 CHECK(result==original_result);CHECK(original_count==1);CHECK(original_seen_error==0x12345678);CHECK(GetLastError()==0xf00d1234);
 CHECK(or_status.replaced==(changed?1:0));CHECK(thread_count==1);
 CHECK(get(descmem,0x34)==(changed?(DWORD)(ULONG_PTR)rv_dry_callback:or_fmod_base+RV_DRY_READ_CALLBACK_RVA));tests++;
}
int main(void){
 reset();invoke(TRUE);CHECK(cas_count==1&&plugin_calls==1&&or_status.target_successes==1&&or_status.attach_status==10);
 reset();original_result=-7;invoke(FALSE);CHECK(!read_count&&!cas_count&&!plugin_calls&&or_status.original_failures==1);
 reset();original_result=2;invoke(FALSE);CHECK(!read_count&&!cas_count&&!plugin_calls);
 reset();expected_output=NULL;invoke(FALSE);CHECK(or_status.validation_failures==1&&!cas_count&&!plugin_calls);
 reset();put(outmem,0,0);invoke(FALSE);CHECK(!plugin_calls);
 reset();put(outmem,0,sysaddr+1);invoke(FALSE);CHECK(!plugin_calls);
 reset();put(outmem,0,0xfffffffc);invoke(FALSE);CHECK(!plugin_calls);
 reset();put(sysmem,0,or_fmod_base+0x68905);invoke(FALSE);CHECK(!plugin_calls);
 reset();sysmem[0x15]=1;invoke(FALSE);CHECK(!plugin_calls);
 reset();sysmem[0x16]=1;invoke(FALSE);CHECK(!plugin_calls);
 reset();put(sysmem,0x93dc,regaddr);invoke(FALSE);CHECK(!plugin_calls);
 reset();failed_read=outaddr;invoke(FALSE);CHECK(!plugin_calls);
 reset();short_read=outaddr;invoke(FALSE);CHECK(!plugin_calls);
 reset();guard_address=outaddr;invoke(FALSE);CHECK(!plugin_calls);
 reset();mock_caller++;invoke(FALSE);CHECK(!plugin_calls&&or_status.other_types==1);
 reset();or_status.create_calls=16;invoke(FALSE);CHECK(!plugin_calls&&or_status.other_types==1);
 reset();or_cold_state=-1;invoke(FALSE);CHECK(!plugin_calls&&or_status.validation_failures==1);
 reset();or_cold_state=1;invoke(FALSE);CHECK(!plugin_calls);
 reset();plugin_result=-2;invoke(FALSE);CHECK(plugin_calls==1&&!cas_count);
 reset();plugin_count=0;invoke(FALSE);CHECK(!cas_count);
 reset();plugin_count=65;invoke(FALSE);CHECK(!cas_count);
 reset();plugin_count=1;invoke(FALSE);CHECK(!cas_count);
 reset();plugin_count=3;invoke(FALSE);CHECK(!cas_count);
 reset();put(regmem,0x2b0,sysaddr+4);invoke(FALSE);CHECK(!cas_count);
 reset();put(regmem,0x160,regaddr+0x160);invoke(FALSE);CHECK(!cas_count);
 reset();put(regmem,0x160,0);invoke(FALSE);CHECK(!cas_count);
 reset();put(regmem,0x160,otheraddr+0x5d);invoke(FALSE);CHECK(!cas_count);
 reset();put(othermem,0x5c,otheraddr+0x5c);invoke(FALSE);CHECK(!cas_count);
 reset();put(descmem,0x5c,otheraddr+0x5c);invoke(FALSE);CHECK(!cas_count);
 reset();put(descmem,0x60,regaddr+0x160);invoke(FALSE);CHECK(!cas_count);
 reset();put(othermem,0x6c,18);invoke(FALSE);CHECK(!cas_count);
 reset();put(descmem,0x6c,2);invoke(FALSE);CHECK(!cas_count);
 reset();put(descmem,0x34,or_fmod_base+0x51993);/* intentionally wrong remains */
 CHECK(or_create(expected_output)==0);CHECK(!cas_count&&or_status.validation_failures==1);tests++;
 reset();put(descmem,0x70,0x771);invoke(FALSE);CHECK(!cas_count);
 reset();descmem[0]=0;invoke(FALSE);CHECK(!cas_count);
 reset();failed_read=descaddr;invoke(FALSE);CHECK(!cas_count);
 reset();readonly_address=descaddr+0x34;invoke(FALSE);CHECK(!cas_count);
 reset();cas_conflict=0xdeadbeef;invoke(FALSE);CHECK(cas_count==1&&or_status.compare_failures==1);
 reset();invoke(TRUE);CHECK((DWORD)or_first_system==sysaddr&&!or_last_creation_reason);
 or_report(0);CHECK(status_writes==1&&strstr(status_json,"\"state\":\"waiting_audio\"")&&strstr(status_json,"\"changes_buffer_size\":false"));tests++;
 fake_counts.dry_calls=7;or_report(1);CHECK(status_writes==2&&strstr(status_json,"\"state\":\"active\"")&&strstr(status_json,"\"dry_calls\":7"));tests++;
 fail_write=1;or_report(2);CHECK(or_status.log_failures==1);tests++;
 fail_write=0;fail_move=1;or_report(3);CHECK(or_status.log_failures==2);tests++;
 fake_counts.dry_calls=0x70000000u;or_report(4);CHECK(or_telemetry_saturated==1&&strstr(status_json,"\"telemetry_saturated\":true"));tests++;
 fake_counts.dry_calls=1;or_report(5);CHECK(or_telemetry_saturated==1);tests++;
 or_status.attach_status=OR_REVERB_BAD_STATIC;or_report(6);CHECK(strstr(status_json,"\"state\":\"inactive\""));tests++;
 printf("STATUS %s",status_json);
 printf("system registry hook: %u exact-source fault/forwarding cases passed\n",tests);return 0;
}
