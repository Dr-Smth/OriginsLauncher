/* Private SFX Reverb dry-only comparison. LGPL-2.1-or-later.
 * Include after reverb_dry.h and Windows API declarations.
 * The installer only publishes this callback on a newly created, exact-version
 * DSPFilter/SFX Reverb object. FMOD supplies the same valid, live state and
 * audio buffers that its original callback would use. Cold qualification must
 * verify object readability through +0x767 and retain the module lifetime.
 * This code does not make arbitrary pointers safe: integer/identity guards are
 * logical checks under that callback contract, not page-access probes.
 * No hot heap allocation, locks, waits, file I/O, RPM or metadata API queries.
 */
static volatile LONG rv_dry_ready;
static rv_read_fn rv_dry_original;
static DWORD rv_dry_module_base;
static volatile LONG rv_dry_calls,rv_dry_fallback_calls,rv_dry_invalid,rv_dry_not_ready;

BOOL rv_dry_initialize(rv_read_fn original,DWORD module_base)
{
    DWORD saved=GetLastError();LONG state;BOOL ok=FALSE;
    if(!original||!module_base||module_base>0xffffffffu-0xbd000u)goto done;
    state=InterlockedCompareExchange(&rv_dry_ready,1,0);
    if(!state){
        rv_dry_original=original;rv_dry_module_base=module_base;
        InterlockedExchange(&rv_dry_ready,2);ok=TRUE;
    }else if(state==2){ok=rv_dry_original==original&&rv_dry_module_base==module_base;}
done:SetLastError(saved);return ok;
}

static int rv_dry_forward(void *state,float *input,float *output,unsigned int frames,
                          int input_channels,int output_channels,DWORD incoming_error)
{
    InterlockedIncrement(&rv_dry_fallback_calls);
    InterlockedIncrement(&rv_dry_invalid);
    SetLastError(incoming_error);
    /* Exactly one original call, same arguments and incoming LastError. Its
     * result and outgoing LastError are returned untouched. */
    return rv_dry_original(state,input,output,frames,input_channels,output_channels);
}

int WINAPI rv_dry_callback(void *state,float *input,float *output,unsigned int frames,
                          int input_channels,int output_channels)
{
    DWORD saved=GetLastError(),state_address=(DWORD)(ULONG_PTR)state;
    DWORD object,input_address=(DWORD)(ULONG_PTR)input,output_address=(DWORD)(ULONG_PTR)output;
    DWORD samples,bytes,i,channel,mask;union{float f;DWORD bits;}gain;
    if(InterlockedCompareExchange(&rv_dry_ready,2,2)!=2){
        InterlockedIncrement(&rv_dry_not_ready);SetLastError(saved);
        return 0x25; /* Exact legacy FMOD invalid-parameter result. Never published before init. */
    }
    if(state_address<RV_DRY_STATE_OFFSET||(state_address&3u)||!frames||frames>RV_DRY_MAX_FRAMES||
       input_channels<1||input_channels>(int)RV_DRY_MAX_CHANNELS||input_channels!=output_channels||
       !input_address||!output_address||(input_address&3u)||(output_address&3u))goto fallback;
    object=state_address-RV_DRY_STATE_OFFSET;
    if(object>0xffffffffu-(RV_DRY_OBJECT_REQUIRED_BYTES-1u))goto fallback;
    samples=frames*(DWORD)input_channels;bytes=samples*4u; /* bounded above by 8192*8*4 */
    if(input_address>0xffffffffu-(bytes-1u)||output_address>0xffffffffu-(bytes-1u))goto fallback;
    if(input_address!=output_address &&
       ((input_address<output_address&&output_address-input_address<bytes)||
        (output_address<input_address&&input_address-output_address<bytes)))goto fallback;
    /* These are original callback-owned fields, read only while FMOD owns this
     * invocation. Do not use this API as a general object/pointer validator. */
    if(*(const DWORD *)(ULONG_PTR)object!=rv_dry_module_base+RV_DRY_FILTER_VTABLE_RVA||
       *(const DWORD *)(ULONG_PTR)(object+0xc8u)!=RV_DRY_SFX_TYPE||
       *(const DWORD *)(ULONG_PTR)state_address!=object)goto fallback;
    mask=*(const WORD *)(ULONG_PTR)(object+RV_DRY_MASK_OFFSET);
    gain.f=*(const float *)(ULONG_PTR)(object+RV_DRY_GAIN_OFFSET);
    if((gain.bits&0x7f800000u)==0x7f800000u||gain.f<0.0f||gain.f>1.0f)goto fallback;
    /* Exact dry term of the original engine: enabled channel = input*gain;
     * other channels = input. Keep upstream graph mixing/connection gains.
     * A float store rounds once, as the original x87 dry-product output does
     * when its wet contribution is zero. Compile without unsafe fast-math. */
    for(i=0,channel=0;i<samples;i++){
        if(mask&(1u<<channel))output[i]=input[i]*gain.f;
        else output[i]=input[i];
        if(++channel==(DWORD)input_channels)channel=0;
    }
    InterlockedIncrement(&rv_dry_calls);
    SetLastError(saved);return 0;
fallback:return rv_dry_forward(state,input,output,frames,input_channels,output_channels,saved);
}

void rv_dry_get_counters(struct rv_dry_counts *out)
{
    DWORD saved=GetLastError();
    if(out){
        out->dry_calls=(DWORD)InterlockedCompareExchange(&rv_dry_calls,0,0);
        out->original_fallback_calls=(DWORD)InterlockedCompareExchange(&rv_dry_fallback_calls,0,0);
        out->invalid_or_unsupported=(DWORD)InterlockedCompareExchange(&rv_dry_invalid,0,0);
        out->not_ready_calls=(DWORD)InterlockedCompareExchange(&rv_dry_not_ready,0,0);
    }
    SetLastError(saved);
}
