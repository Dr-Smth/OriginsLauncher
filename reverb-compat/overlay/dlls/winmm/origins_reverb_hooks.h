/* Game-only reverb compatibility. LGPL-2.1-or-later. */
#ifndef ORIGINS_REVERB_HOOKS_H
#define ORIGINS_REVERB_HOOKS_H
#define ORIGINS_REVERB_CONFIG_VERSION 1u
struct origins_reverb_config {
    DWORD bytes, version;
    HMODULE main_module, bridge_module, fmod_module;
};
struct origins_reverb_status {
    DWORD bytes, version, attach_status;
    LONG create_calls, original_failures, other_types, target_successes;
    LONG replaced, validation_failures, compare_failures;
    LONG reporter_started, log_failures;
};
enum {
    OR_REVERB_UNCONFIGURED=0, OR_REVERB_BAD_CONFIG=1, OR_REVERB_BAD_MODULE=2,
    OR_REVERB_BAD_STATIC=3, OR_REVERB_BAD_IMPORT=4, OR_REVERB_PIN_FAILED=5,
    OR_REVERB_IMPORT_PROTECT_FAILED=6, OR_REVERB_IMPORT_CHANGED=7,
    OR_REVERB_IMPORT_RESTORE_FAILED=8, OR_REVERB_ATTACHED=9, OR_REVERB_ACTIVE=10
};
/* Capture-free status. ATTACHED means the System_Create import is staged;
 * ACTIVE means a qualified per-System registry record was replaced. Actual
 * callback execution is reported separately by dry_calls. No FMOD Init or
 * buffer-size API is hooked. The manager creates the fixed status directory. */
BOOL origins_reverb_attach(const struct origins_reverb_config *);
/* Caller owns output; all live counts use atomic reads. No object pointers kept. */
void origins_reverb_get_status(struct origins_reverb_status *);
#endif
