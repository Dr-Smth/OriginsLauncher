/* SPDX-License-Identifier: LGPL-2.1-or-later; Copyright (C) 2026 David Richard Smith. */
/* Private conditional-wait experiment, LGPL-2.1-or-later. */
#ifndef ORIGINS_DECISION_FORMAT_H
#define ORIGINS_DECISION_FORMAT_H
#include <stdint.h>
#define CD_RING 98304u
#define CD_BLOCK 4096u
#define CD_LEAD 1920u
/* Private Stage7 profiles: admission and recovery remain explicitly paired. */
#ifndef CD_LOW_LEAD_MAX_BYTES
#define CD_LOW_LEAD_MAX_BYTES 4096u
#endif
#ifndef CD_RECOVERY_LEAD_ABOVE_BYTES
#define CD_RECOVERY_LEAD_ABOVE_BYTES CD_LOW_LEAD_MAX_BYTES
#endif
_Static_assert(CD_LOW_LEAD_MAX_BYTES==4096u || CD_LOW_LEAD_MAX_BYTES==6144u,"reviewed guard profiles only");
_Static_assert(CD_RECOVERY_LEAD_ABOVE_BYTES==CD_LOW_LEAD_MAX_BYTES,"matching admission and recovery bounds");
#define CD_RESERVE_BLOCKS 4u
#define CD_MAX_RECORDS 32768u
#define CD_TELEMETRY_MAX UINT32_MAX
#define CD_CALIBRATION_BURSTS 3u
#define CD_NO_RECOVERY_BYTES (4u*CD_RING)
#define CD_CONSUMER_STALL_MS 512u
#define CD_RECOVERY_PHASE_TOLERANCE CD_BLOCK
#define CD_RECOVERY_RESUME_BURSTS 3u
enum cd_reason { CD_ELIGIBLE=0, CD_NOT_READY, CD_QUERY_UNKNOWN, CD_SNAPSHOT_UNKNOWN,
 CD_INITIAL_COVERAGE, CD_CALIBRATION, CD_GENERATION, CD_NO_DEMAND,
 CD_LOW_PROTECTED, CD_HEALTHY_LEAD, CD_NO_PROGRESS, CD_BUDGET,
 CD_CONTROL_CHANGED, CD_HELPER_FAILURE, CD_WRONG_REQUEST, CD_EXHAUSTED,
 CD_NO_RECOVERY, CD_CONSUMER_STALLED, CD_RECOVERY_PAUSED,
 CD_REASON_COUNT };
enum { CD_FLAG_SCOPE=1u, CD_FLAG_SNAPSHOT=2u, CD_FLAG_ANCHORED=4u,
 CD_FLAG_ENABLED=8u, CD_FLAG_APPLIED=16u };
struct cd_record {
 uint64_t decision_qpc, query_qpc, read_qpc;
 int64_t producer_next_abs, consumer_abs, query_consumer_abs;
 uint32_t sequence,call_id,request_ms,effective_ms,reason,flags,read_index,read_count;
 uint32_t query_sequence,query_play,query_write,query_block,fresh_query_block;
 uint32_t old_end_block,new_end_block,next_block,due_blocks,token,last_early_token;
 uint32_t object,backing,device,epoch,windows_tid,completed_writes,early_count;
 uint32_t scope_error,anchor_writes;
};
_Static_assert(sizeof(struct cd_record)==160,"conditional decision ABI");
#endif
