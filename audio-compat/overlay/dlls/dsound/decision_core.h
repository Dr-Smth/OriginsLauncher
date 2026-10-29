/* SPDX-License-Identifier: LGPL-2.1-or-later; Copyright (C) 2026 David Richard Smith. */
/* Same pure state/decision code in host tests and PE32. No pointers to audio
 * objects, allocation, I/O, locks, calls to Sleep or invented PCM. */
#ifndef ORIGINS_DECISION_CORE_H
#define ORIGINS_DECISION_CORE_H
#include "decision_format.h"
#include <string.h>
#include <limits.h>
struct cd_snapshot {
 uint64_t frame_end,qpc;
 uint32_t position,index,count,valid;
};
struct cd_state {
 uint64_t origin_frames,query_qpc;
 int64_t origin_position,next_abs,query_consumer_abs,query_end_abs;
 uint32_t origin,anchored,invalid,writes,last_token,next_offset;
 uint32_t query_valid,query_sequence,query_play,query_write;
 uint32_t calibration,last_calibration_token,last_early_token,early_count;
 uint64_t frequency,recovery_qpc,last_progress_qpc;
 int64_t recovery_consumer,last_progress_consumer;
 uint32_t recovery_active,cutout,anchor_writes;
 int64_t recovery_producer,resume_producer,resume_consumer;
 uint64_t pause_qpc,resume_qpc;
 uint32_t recovery_paused,pause_reason,pause_count,resume_count,resume_streak,resume_token,applied_after_resume;
};
static uint32_t cd_saturating_increment(uint32_t value)
{return value==UINT32_MAX?value:value+1u;}
static int cd_endpoint(int64_t consumer,int64_t*out)
{
 int64_t block;
 if(consumer<0)return 0;block=consumer/CD_BLOCK;
 if(block>INT64_MAX/CD_BLOCK-CD_RESERVE_BLOCKS)return 0;
 *out=(block+CD_RESERVE_BLOCKS)*CD_BLOCK;return 1;
}
static int cd_consumer(struct cd_state*s,const struct cd_snapshot*x,int64_t*out)
{
 uint64_t delta;
 if(!x->valid||x->position>=CD_RING||x->position%4)return 0;
 if(!s->origin){s->origin=1;s->origin_frames=x->frame_end;s->origin_position=CD_RING+x->position;}
 if(x->frame_end<s->origin_frames)return 0;
 delta=x->frame_end-s->origin_frames;
 if(delta>(uint64_t)(INT64_MAX-s->origin_position)/4u)return 0;
 *out=s->origin_position+(int64_t)(delta*4u);
 return (uint32_t)(*out%CD_RING)==x->position;
}
static void cd_write(struct cd_state*s,uint32_t token,uint32_t offset,uint32_t bytes)
{
 if(s->invalid)return;
 if(!token||offset>=CD_RING||offset%CD_BLOCK||bytes!=CD_BLOCK||
    (s->writes&&(token!=s->last_token+1u||offset!=s->next_offset))||
    s->writes==UINT32_MAX||token==UINT32_MAX){s->invalid=1;return;}
 if(s->anchored){if(s->next_abs>INT64_MAX-CD_BLOCK){s->invalid=1;return;}s->next_abs+=CD_BLOCK;}
 s->writes++;s->last_token=token;s->next_offset=(offset+CD_BLOCK)%CD_RING;
}
static void cd_query(struct cd_state*s,uint32_t serial,uint32_t play,uint32_t write,
                     uint64_t qpc,const struct cd_snapshot*x)
{
 int64_t consumer;s->query_valid=0;
 s->query_sequence=serial;s->query_play=play;s->query_write=write;s->query_qpc=qpc;
 if(s->invalid||play>=CD_RING||write>=CD_RING||(write+CD_RING-play)%CD_RING!=CD_LEAD||
    play/CD_BLOCK!=write/CD_BLOCK||!x->valid||x->position!=play||!cd_consumer(s,x,&consumer))return;
 s->query_consumer_abs=consumer;
 if(!cd_endpoint(consumer,&s->query_end_abs))return;
 s->query_valid=1;
}
/* Unknown/unsafe observations cannot carry a partial recovery proof forward. */
static uint32_t cd_reject(struct cd_state*s,uint32_t reason)
{if(s->recovery_paused)s->resume_streak=0;return reason;}
static void cd_pause(struct cd_state*s,uint32_t reason,int64_t consumer,uint64_t qpc)
{
 if(s->recovery_paused)return;
 s->recovery_paused=1;s->pause_reason=reason;s->pause_count=cd_saturating_increment(s->pause_count);s->pause_qpc=qpc;
 s->resume_streak=0;s->resume_token=s->last_token;
 s->resume_consumer=consumer;s->resume_producer=s->next_abs;
}
/* Fixed-origin progress accounting, with one bounded block of phase tolerance.
 * This changes only assistance state: coverage/anchors/budget never reset. */
static uint32_t cd_recovery(struct cd_state*s,int64_t consumer,int64_t lead,
                            uint32_t protected_coverage,uint64_t qpc)
{
 int64_t consumed,produced;
 if(!s->recovery_active)return 0;
 if(consumer<s->recovery_consumer||s->next_abs<s->recovery_producer){s->invalid=8;return cd_reject(s,CD_GENERATION);}
 if(!s->recovery_paused){
  consumed=consumer-s->recovery_consumer;produced=s->next_abs-s->recovery_producer;
  if(lead<CD_LEAD)cd_pause(s,CD_LOW_PROTECTED,consumer,qpc);
  else if(consumed>=CD_NO_RECOVERY_BYTES&&consumed>produced&&consumed-produced>CD_RECOVERY_PHASE_TOLERANCE)
   cd_pause(s,CD_NO_RECOVERY,consumer,qpc);
  else if(protected_coverage&&lead>CD_RECOVERY_LEAD_ABOVE_BYTES)s->recovery_active=0;
 }
 if(!s->recovery_paused)return 0;
 if(!protected_coverage||lead<=CD_RECOVERY_LEAD_ABOVE_BYTES){s->resume_streak=0;return CD_RECOVERY_PAUSED;}
 /* A still-valid duplicate is not another proof point. */
 if(s->last_token==s->resume_token||consumer<=s->resume_consumer||s->next_abs<=s->resume_producer)return CD_RECOVERY_PAUSED;
 s->resume_token=s->last_token;s->resume_consumer=consumer;s->resume_producer=s->next_abs;
 if(++s->resume_streak<CD_RECOVERY_RESUME_BURSTS)return CD_RECOVERY_PAUSED;
 s->recovery_paused=0;s->recovery_active=0;s->resume_streak=0;s->resume_count=cd_saturating_increment(s->resume_count);s->resume_qpc=qpc;
 return 0;
}
/* Evaluation records eligibility but never itself changes the requested wait.
 * Caller must recheck publication/control/deadline immediately before commit. */
static uint32_t cd_evaluate(struct cd_state*s,const struct cd_snapshot*x,struct cd_record*r)
{
 int64_t consumer,lead,fresh_end,due;
 uint32_t fresh_write,fresh_valid,protected_coverage,recovery_reason;uint64_t stall_ticks;
 r->query_qpc=s->query_qpc;r->query_sequence=s->query_sequence;
 r->query_play=s->query_play;r->query_write=s->query_write;r->query_block=s->query_play/CD_BLOCK;
 r->old_end_block=(r->query_block+CD_RESERVE_BLOCKS)%24u;
 r->query_consumer_abs=s->query_consumer_abs;r->token=s->last_token;r->last_early_token=s->last_early_token;
 r->completed_writes=s->writes;r->early_count=s->early_count;r->next_block=s->next_offset/CD_BLOCK;
 if(s->cutout)return cd_reject(s,s->cutout);
 if(s->invalid)return cd_reject(s,CD_GENERATION);
 if(!s->frequency)return cd_reject(s,CD_NOT_READY);
 stall_ticks=(s->frequency/1000u)*CD_CONSUMER_STALL_MS+(s->frequency%1000u)*CD_CONSUMER_STALL_MS/1000u;
 if(!cd_consumer(s,x,&consumer)){
  if(s->recovery_active&&r->decision_qpc>=s->last_progress_qpc&&r->decision_qpc-s->last_progress_qpc>=stall_ticks){s->cutout=CD_CONSUMER_STALLED;return cd_reject(s,s->cutout);}
  return cd_reject(s,CD_SNAPSHOT_UNKNOWN);
 }
 if(s->recovery_active){
  if(consumer>s->last_progress_consumer){s->last_progress_consumer=consumer;s->last_progress_qpc=r->decision_qpc;}
  else if(r->decision_qpc>=s->last_progress_qpc&&r->decision_qpc-s->last_progress_qpc>=stall_ticks){s->cutout=CD_CONSUMER_STALLED;return cd_reject(s,s->cutout);}
 }
 if(!s->query_valid)return cd_reject(s,CD_QUERY_UNKNOWN);
 r->flags|=CD_FLAG_SNAPSHOT;r->consumer_abs=consumer;r->read_qpc=x->qpc;r->read_index=x->index;r->read_count=x->count;
 if(consumer<s->query_consumer_abs||consumer-s->query_consumer_abs>=CD_RING){s->invalid=7;return cd_reject(s,CD_GENERATION);}
 if(s->next_offset!=(uint32_t)(s->query_end_abs%CD_RING)){
  if(s->anchored)s->invalid=3;
  return cd_reject(s,CD_CALIBRATION);
 }
 if(!s->last_token)return cd_reject(s,CD_INITIAL_COVERAGE);
 /* Anchor once at the FIRST qualified completed burst, then validate every
  * absolute endpoint through warmup. Pre-anchor writes never count as known
  * generation coverage. Never re-anchor after a lost whole traversal. */
 if(!s->anchored){
  s->next_abs=s->query_end_abs;s->anchored=1;s->anchor_writes=s->writes;
  s->calibration=0;s->last_calibration_token=0;
 }
 if(s->next_abs!=s->query_end_abs){s->invalid=2;return cd_reject(s,CD_GENERATION);}
 r->flags|=CD_FLAG_ANCHORED;r->producer_next_abs=s->next_abs;r->anchor_writes=s->anchor_writes;
 if(s->last_calibration_token!=s->last_token){
  s->last_calibration_token=s->last_token;
  if(s->calibration<CD_CALIBRATION_BURSTS)s->calibration++;
 }
 if(s->writes-s->anchor_writes<24u)return cd_reject(s,CD_INITIAL_COVERAGE);
 if(s->calibration<CD_CALIBRATION_BURSTS)return cd_reject(s,CD_CALIBRATION);
 lead=s->next_abs-consumer;
 fresh_write=(x->position+CD_LEAD)%CD_RING;
 fresh_valid=x->position/CD_BLOCK==fresh_write/CD_BLOCK;
 if(!cd_endpoint(consumer,&fresh_end))return cd_reject(s,CD_GENERATION);
 r->fresh_query_block=x->position/CD_BLOCK;r->new_end_block=(r->fresh_query_block+CD_RESERVE_BLOCKS)%24u;
 due=(fresh_end-s->next_abs)/CD_BLOCK;
 if(due>=24)return cd_reject(s,CD_GENERATION);
 protected_coverage=fresh_valid&&s->next_abs-CD_RING+CD_BLOCK<=consumer&&lead>=CD_LEAD&&
    ((s->next_offset+CD_RING-fresh_write)%CD_RING)+CD_BLOCK<=CD_RING-CD_LEAD;
 recovery_reason=cd_recovery(s,consumer,lead,protected_coverage,r->decision_qpc);
 if(recovery_reason)return recovery_reason;
 if(!fresh_valid)return cd_reject(s,CD_QUERY_UNKNOWN);
 if(due<=0)return CD_NO_DEMAND;
 r->due_blocks=(uint32_t)due;
 if(!protected_coverage)return CD_LOW_PROTECTED;
 if(lead>CD_LOW_LEAD_MAX_BYTES)return CD_HEALTHY_LEAD;
 if(!s->last_token||s->last_token==s->last_early_token)return CD_NO_PROGRESS;
 return CD_ELIGIBLE;
}
/* Used only for an actual changed argument after the final adapter checks. */
static void cd_commit_early(struct cd_state*s,const struct cd_record*r)
{
 s->last_early_token=s->last_token;s->early_count=cd_saturating_increment(s->early_count);
 if(s->resume_count)s->applied_after_resume=cd_saturating_increment(s->applied_after_resume);
 if(!s->recovery_active){
  s->recovery_active=1;s->recovery_qpc=s->last_progress_qpc=r->decision_qpc;
  s->recovery_consumer=s->last_progress_consumer=r->consumer_abs;s->recovery_producer=s->next_abs;
 }
}
#endif
