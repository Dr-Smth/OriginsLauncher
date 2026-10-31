/* Automatic loader integration: owns only module lookup and calls the guarded
 * attachment entry; original loader LastError must survive either result. */
#include <stdint.h>
#include <stddef.h>
#include <stdio.h>
#include <string.h>
#include <wchar.h>
#include <assert.h>
typedef uint32_t DWORD;typedef int32_t LONG;typedef int BOOL;typedef wchar_t WCHAR;typedef void*HMODULE;
#define TRUE 1
#define FALSE 0
#define __i386__ 1
#include "origins_reverb_hooks.h"
static DWORD error,lookups,attaches;static BOOL result;static HMODULE main_module=(void*)1,bridge_module=(void*)2,fmod_module=(void*)3;
static DWORD GetLastError(void){return error;}static void SetLastError(DWORD v){error=v;}
static HMODULE GetModuleHandleW(const WCHAR*s){lookups++;error++;if(!s)return main_module;if(!wcscmp(s,L"fmod_event.dll"))return bridge_module;assert(!wcscmp(s,L"fmodex.dll"));return fmod_module;}
BOOL origins_reverb_attach(const struct origins_reverb_config*c){attaches++;assert(c->bytes==sizeof(*c)&&c->version==1&&c->main_module==main_module&&c->bridge_module==bridge_module&&c->fmod_module==fmod_module);error=999;return result;}
#include "origins_reverb_startup.c"
int main(void){unsigned cases=0;for(unsigned f=0;f<2;f++)for(unsigned missing=0;missing<4;missing++){
 main_module=missing==1?NULL:(void*)1;bridge_module=missing==2?NULL:(void*)2;fmod_module=missing==3?NULL:(void*)3;
 lookups=attaches=0;error=0xa123;result=f;origins_reverb_attach_game();assert(error==0xa123&&lookups==3&&attaches==1);cases++;}
 printf("startup: %u scope-forwarding/LastError cases passed\n",cases);return 0;}
