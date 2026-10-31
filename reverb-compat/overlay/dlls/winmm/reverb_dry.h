/* Private exact-version comparison. Include after Windows primitive types.
 * No game code/payload. LGPL-2.1-or-later. */
#ifndef ORIGINS_REVERB_DRY_H
#define ORIGINS_REVERB_DRY_H
#define RV_DRY_MAX_FRAMES 8192u
#define RV_DRY_MAX_CHANNELS 8u
#define RV_DRY_FILTER_VTABLE_RVA 0x683a4u
#define RV_DRY_READ_CALLBACK_RVA 0x51992u
#define RV_DRY_SFX_TYPE 18u
#define RV_DRY_STATE_OFFSET 0x1cu
#define RV_DRY_MASK_OFFSET 0x24u
#define RV_DRY_GAIN_OFFSET 0x764u
#define RV_DRY_OBJECT_REQUIRED_BYTES 0x768u

typedef int (WINAPI *rv_read_fn)(void *state,float *input,float *output,
                               unsigned int frames,int input_channels,int output_channels);
struct rv_dry_counts {
    DWORD dry_calls, original_fallback_calls, invalid_or_unsupported, not_ready_calls;
};
/* Cold, once before publishing the callback. Caller verifies exact module/code,
 * target original callback, new object's class/type/state span and owns its
 * lifetime through FMOD's existing creation/mixer synchronization. */
BOOL rv_dry_initialize(rv_read_fn original,DWORD module_base);
int WINAPI rv_dry_callback(void *state,float *input,float *output,
                          unsigned int frames,int input_channels,int output_channels);
void rv_dry_get_counters(struct rv_dry_counts *out);
#endif
