// SPDX-License-Identifier: LGPL-2.1-or-later
#include <assert.h>
#include <stdint.h>
#include <stdio.h>
#define CD_LOW_LEAD_MAX_BYTES 6144u
#define CD_RECOVERY_LEAD_ABOVE_BYTES 6144u
#include "../overlay/dlls/dsound/decision_core.h"

static struct cd_state base(void)
{
    return (struct cd_state){.frequency=10000000,.origin=1,.origin_position=CD_RING,
        .query_valid=1,.query_consumer_abs=CD_RING+20480,.query_end_abs=CD_RING+36864,
        .query_play=20480,.query_write=22400,.query_sequence=1,.query_qpc=1,
        .writes=24,.last_token=24,.next_offset=36864,.calibration=3,.last_calibration_token=24,
        .anchored=1,.next_abs=CD_RING+36864};
}
static struct cd_snapshot snap(int64_t absolute,uint64_t time)
{
    assert(absolute>=CD_RING && absolute%4==0);
    return (struct cd_snapshot){.frame_end=(absolute-CD_RING)/4,.qpc=time,
        .position=(uint32_t)(absolute%CD_RING),.index=1,.count=2,.valid=1};
}
static uint32_t evaluate(struct cd_state*s,int64_t consumer,uint64_t time,struct cd_record*r)
{
    struct cd_snapshot x=snap(consumer,time);
    memset(r,0,sizeof(*r));r->decision_qpc=time+1;
    return cd_evaluate(s,&x,r);
}
static void finish_query(struct cd_state*s,int64_t consumer,uint64_t time)
{
    struct cd_snapshot x=snap(consumer,time);
    cd_query(s,s->query_sequence+1,x.position,(x.position+CD_LEAD)%CD_RING,time,&x);
    assert(s->query_valid&&!s->invalid);
    while(s->next_abs<s->query_end_abs)cd_write(s,s->last_token+1,s->next_offset,CD_BLOCK);
    assert(s->next_abs==s->query_end_abs&&!s->invalid);
}
static void start_episode(struct cd_state*s,int64_t lead)
{
    s->recovery_active=1;s->recovery_consumer=s->next_abs-lead;
    s->recovery_producer=s->next_abs;s->recovery_qpc=1000;
    s->last_progress_consumer=s->recovery_consumer;s->last_progress_qpc=1000;
}
static void stable_low_reserve(void)
{
    struct cd_state s=base();struct cd_record r;int64_t consumer=s.next_abs-6144;uint64_t time=1000;
    assert(evaluate(&s,consumer,time,&r)==CD_ELIGIBLE);cd_commit_early(&s,&r);
    int64_t episode_consumer=s.recovery_consumer,episode_producer=s.recovery_producer;
    for(unsigned n=1;n<=144;n++){
        finish_query(&s,consumer,time+2);consumer+=8192;time+=426667;
        assert(evaluate(&s,consumer,time,&r)==CD_ELIGIBLE);cd_commit_early(&s,&r);
        assert(!s.recovery_paused&&!s.cutout&&!s.invalid);
        assert(s.recovery_consumer==episode_consumer&&s.recovery_producer==episode_producer);
    }
    assert(s.early_count==145&&consumer-episode_consumer==3*CD_NO_RECOVERY_BYTES);
}
static void cumulative_deficit_boundaries(void)
{
    struct cd_state s=base();start_episode(&s,6144);
    int64_t p=s.recovery_producer,c=s.recovery_consumer;
    s.next_abs=p+CD_NO_RECOVERY_BYTES-CD_RECOVERY_PHASE_TOLERANCE;
    assert(cd_recovery(&s,c+CD_NO_RECOVERY_BYTES,2048,1,2000)==0&&!s.recovery_paused);
    assert(cd_recovery(&s,c+CD_NO_RECOVERY_BYTES+4,2044,1,2001)==CD_RECOVERY_PAUSED);
    assert(s.pause_reason==CD_NO_RECOVERY&&!s.cutout&&s.pause_count==1);
    assert(s.recovery_consumer==c&&s.recovery_producer==p);
    s=base();start_episode(&s,6144);p=s.recovery_producer;c=s.recovery_consumer;
    for(int n=1;n<=4;n++){
        s.next_abs=p+n*(int64_t)CD_NO_RECOVERY_BYTES;
        assert(cd_recovery(&s,c+n*(int64_t)CD_NO_RECOVERY_BYTES+n*1024,6144-n*1024,1,3000+n)==0);
        assert(s.recovery_consumer==c&&s.recovery_producer==p&&!s.recovery_paused);
    }
    assert(cd_recovery(&s,c+4*(int64_t)CD_NO_RECOVERY_BYTES+4100,2044,1,3005)==CD_RECOVERY_PAUSED);
    assert(s.pause_reason==CD_NO_RECOVERY); /* No allowance was replenished at each window. */
}
static void protected_boundary_and_resume(void)
{
    struct cd_state s=base();start_episode(&s,6144);int64_t p=s.next_abs;
    assert(cd_recovery(&s,p-1920,1920,1,2000)==0&&!s.recovery_paused);
    assert(cd_recovery(&s,p-1916,1916,0,2001)==CD_RECOVERY_PAUSED&&s.pause_reason==CD_LOW_PROTECTED);
    uint32_t token=s.last_token,budget=s.early_count;int64_t origin=s.origin_position;
    s.next_abs=p+16384;s.last_token=++token;
    assert(cd_recovery(&s,p+8192,8192,1,2010)==CD_RECOVERY_PAUSED&&s.resume_streak==1);
    assert(cd_recovery(&s,p+8192,8192,1,2011)==CD_RECOVERY_PAUSED&&s.resume_streak==1);
    assert(cd_reject(&s,CD_SNAPSHOT_UNKNOWN)==CD_SNAPSHOT_UNKNOWN&&s.resume_streak==0);
    s.next_abs+=4096;s.last_token=++token;
    assert(cd_recovery(&s,p+12288,8192,1,2020)==CD_RECOVERY_PAUSED&&s.resume_streak==1);
    s.next_abs+=4096;s.last_token=++token;
    assert(cd_recovery(&s,p+18432,6144,1,2021)==CD_RECOVERY_PAUSED&&s.resume_streak==0);
    s.next_abs+=4096;s.last_token=++token;
    assert(cd_recovery(&s,p+20480,8192,0,2022)==CD_RECOVERY_PAUSED&&s.resume_streak==0);
    for(unsigned n=0;n<3;n++){
        s.next_abs+=4096;s.last_token=++token;
        uint32_t reason=cd_recovery(&s,s.next_abs-8192,8192,1,2030+n);
        assert(reason==(n<2?CD_RECOVERY_PAUSED:0));
    }
    assert(!s.recovery_paused&&!s.recovery_active&&s.resume_count==1&&s.pause_count==1);
    assert(s.early_count==budget&&s.origin_position==origin&&s.anchored&&!s.cutout&&!s.invalid);
}
static void known_negative_and_full_recovery(void)
{
    const int64_t deficits[]={-1000,0,4};
    for(unsigned i=0;i<sizeof(deficits)/sizeof(deficits[0]);i++){
        int64_t deficit=deficits[i];
        struct cd_state s=base();struct cd_record r;start_episode(&s,4096);
        uint64_t time=10000;int64_t consumer=s.next_abs+deficit;
        assert(evaluate(&s,consumer,time,&r)==CD_RECOVERY_PAUSED);
        assert(s.recovery_paused&&!s.invalid&&!s.cutout&&s.early_count==0);
        uint32_t anchor=s.anchor_writes;int64_t origin=s.origin_position;
        consumer=(consumer/CD_BLOCK+1)*CD_BLOCK;
        for(unsigned n=0;n<3;n++){
            consumer+=CD_BLOCK;time+=213334;finish_query(&s,consumer,time);
            uint32_t reason=evaluate(&s,consumer,time+1,&r);
            assert(reason==(n<2?CD_RECOVERY_PAUSED:CD_NO_DEMAND));
        }
        assert(s.resume_count==1&&!s.recovery_paused&&s.anchor_writes==anchor&&s.origin_position==origin);
        consumer=s.next_abs-6144;time+=50000;
        assert(evaluate(&s,consumer,time,&r)==CD_ELIGIBLE);cd_commit_early(&s,&r);
        assert(s.applied_after_resume==1&&s.early_count==1);
        s.early_count=4096;s.last_early_token=0;
        assert(evaluate(&s,consumer,time+1,&r)==CD_ELIGIBLE&&s.early_count==4096);
    }
}
static void hard_history_and_stall(void)
{
    struct cd_state s=base();struct cd_record r;start_episode(&s,4096);
    int64_t c=s.next_abs-4096;
    s.invalid=7;s.recovery_paused=1;s.resume_streak=2;
    assert(evaluate(&s,c,1001,&r)==CD_GENERATION&&s.resume_streak==0&&s.invalid==7);
    s=base();start_episode(&s,4096);s.recovery_paused=1;
    assert(evaluate(&s,s.query_consumer_abs+CD_RING,1001,&r)==CD_GENERATION&&s.invalid==7);
    s=base();start_episode(&s,4096);s.recovery_paused=1;
    assert(evaluate(&s,c,1000+5120000,&r)==CD_CONSUMER_STALLED&&s.cutout==CD_CONSUMER_STALLED);
    assert(evaluate(&s,c+4096,1000+6000000,&r)==CD_CONSUMER_STALLED);
}
int main(void)
{
    assert(CD_TELEMETRY_MAX==UINT32_MAX&&CD_NO_RECOVERY_BYTES==393216&&CD_RECOVERY_PHASE_TOLERANCE==4096);
    stable_low_reserve();cumulative_deficit_boundaries();protected_boundary_and_resume();
    known_negative_and_full_recovery();hard_history_and_stall();
    puts("PASS five actual policy10 scenario groups: stable reserve, fixed-origin loss, boundary/hysteresis, known negative recovery, hard history/stall and unlimited telemetry");
    return 0;
}
