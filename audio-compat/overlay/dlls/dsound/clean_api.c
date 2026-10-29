/* SPDX-License-Identifier: LGPL-2.1-or-later; Copyright (C) 2026 David Richard Smith. */
/* Original control calls execute once; this adapter only consumes their results. */
BOOL conditional_api_enter(IDirectSoundBufferImpl*b,DWORD kind)
{
 struct rt_context*c=context;BOOL control=kind!=RT_LOCK&&kind!=RT_UNLOCK;
 if(!la_live(c)||!la_target(c,b))return FALSE;
 InterlockedIncrement(&c->active_ops);if(control){InterlockedIncrement(&c->control_ops);la_next(c,&c->control_serial);}
 if(la_load(&c->state)==LA_ACTIVE){
  if(control)la_fail(c,LA_CONTROL);
  else if(!la_load(&c->producer_tid)||GetCurrentThreadId()!=la_load(&c->producer_tid))la_fail(c,LA_SCOPE);
 }
 return 1|(control?2:0);
}
void conditional_api_leave(BOOL guard)
{if(guard){if(guard&2)InterlockedDecrement(&context->control_ops);InterlockedDecrement(&context->active_ops);}}
void conditional_invalidate(IDirectSoundBufferImpl*b)
{if(la_target(context,b))la_fail(context,LA_DESTROY);}
static void la_try_activate(struct rt_context*c,const struct rt_event*e)
{
 uint32_t words[LA_SNAPSHOT_WORDS],generation;DWORD serial;struct pv_read r;HANDLE thread=NULL;
 ULONGLONG now,bound;DWORD i,opens=0;
 if(la_load(&c->state)!=LA_WAIT||la_load(&c->install_status)||e->kind!=RT_LOCK||e->result||
 e->caller!=c->module_base+CL_LOCK_RVA||e->data[1]!=CD_BLOCK||e->data[2]||e->data[0]%CD_BLOCK||
 e->object!=la_load(&c->selected)||e->backing!=la_load(&c->backing)||e->device!=la_load(&c->device)||
 !la_load(&c->looping_seen)||la_load(&c->active_ops)!=1||la_load(&c->control_ops)||la_load(&c->invalid)||la_load(&c->commit_active))return;
 serial=la_load(&c->control_serial);if(!la_snapshot_copy(&c->latest,words,&generation))return;memcpy(&r,words,sizeof(r));
 now=rt_tick();bound=(c->frequency/48000u)*1024u+(c->frequency%48000u)*1024u/48000u;
 if(r.flags!=1||!r.qualified_frames||r.qualified_frames!=r.frames||r.audible!=1||!r.epoch||r.epoch!=la_load(&c->epoch)||
 r.object!=e->object||r.backing!=e->backing||r.device!=e->device||r.freq_num!=48000||r.freq_den!=48000||r.writelead!=CD_LEAD||
 r.active_before||r.active_after||r.sequence_before!=r.sequence_after||r.sequence_after!=la_load(&c->commit_sequence)||
 !r.end||now<r.end||now-r.end>bound||!la_snapshot_stable(&c->latest,generation))return;
 for(i=0;i<PV_LOCKS;i++){DWORD state=la_load(&c->slots[i].w[PS_STATE]);if(state!=PV_FREE){
  if(state!=PV_OPEN||la_load(&c->slots[i].w[PS_THREAD])!=e->tid)return;opens++;}}
 if(opens!=1)return;
 if(!DuplicateHandle(GetCurrentProcess(),GetCurrentThread(),GetCurrentProcess(),&thread,SYNCHRONIZE,FALSE,0)){la_fail(c,LA_SCOPE);return;}
 if(InterlockedCompareExchange(&c->identity_ready,1,0)){CloseHandle(thread);return;}
 c->producer_handle=thread;la_store(&c->producer_tid,e->tid);c->activated=rt_tick();
 if(InterlockedCompareExchange(&c->state,LA_ACTIVE,LA_WAIT)!=LA_WAIT)return;
 /* A control that started in WAITING is still counted until its return. If it
  * crossed our checks, never expose a usable identity for an early decision. */
 if(serial!=la_load(&c->control_serial)||la_load(&c->active_ops)!=1||la_load(&c->control_ops)||la_load(&c->invalid)||
 !la_load(&c->looping_seen)||r.epoch!=la_load(&c->epoch)||!la_snapshot_stable(&c->latest,generation)){
  la_fail(c,LA_CONTROL);return;
 }
 la_store(&c->identity_ready,2);
}
struct rt_call rt_begin(IDirectSoundBufferImpl*b,DirectSoundDevice*d,DWORD kind,void*caller,BOOL always)
{
 struct rt_call t={0};struct rt_context*c=context;(void)always;
 if(!la_live(c)||!b||!la_target(c,b)||(kind!=RT_POSITION&&kind!=RT_LOCK&&kind!=RT_UNLOCK))return t;
 t.slot=la_next(c,&c->event_serial);if(!t.slot)return t;t.admitted=TRUE;
 t.event.start=rt_tick();t.event.kind=kind;t.event.tid=GetCurrentThreadId();t.event.caller=(DWORD)(ULONG_PTR)caller;
 t.event.object=b->rt_id;t.event.backing=b->buffer?b->buffer->rt_id:0;t.event.device=d?d->rt_id:0;t.event.flags=la_load(&c->state)==LA_ACTIVE;return t;
}
void rt_end(struct rt_call*t,HRESULT result)
{
 struct rt_context*c=context;struct rt_event*e=&t->event;struct cd_snapshot x;struct la_guard g;const struct pv_write*w;DWORD saved=GetLastError(),rva;
 if(!t->admitted)return;e->end=rt_tick();e->result=result;la_try_activate(c,e);
 if(la_load(&c->state)!=LA_ACTIVE||la_load(&c->identity_ready)!=2||e->tid!=la_load(&c->producer_tid)||
 e->object!=la_load(&c->selected)||e->backing!=la_load(&c->backing)||e->device!=la_load(&c->device))goto done;
 if(e->caller<c->module_base){la_fail(c,LA_SCOPE);goto done;}rva=e->caller-c->module_base;
 if((e->kind==RT_POSITION&&rva!=CL_POSITION_RVA)||(e->kind==RT_LOCK&&rva!=CL_LOCK_RVA)||(e->kind==RT_UNLOCK&&rva!=CL_UNLOCK_RVA)||FAILED(result)){la_fail(c,FAILED(result)?LA_API:LA_SCOPE);goto done;}
 c->policy.frequency=c->frequency;
 if(e->kind==RT_LOCK){if(e->data[1]!=CD_BLOCK||e->data[2]||e->data[0]%CD_BLOCK)la_fail(c,LA_SCOPE);goto done;}
 if(e->kind==RT_POSITION){memset(&x,0,sizeof(x));la_snapshot(c,&x,&g);if(!e->data[2]||!e->data[3])x.valid=0;
  cd_query(&c->policy,t->slot,e->data[0],e->data[1],e->end,&x);goto done;}
 w=t->write;if(!w||!w->reserved||la_load(&c->write_serial)!=w->reserved||
 w->thread!=e->tid||w->lock_thread!=e->tid||w->object!=e->object||w->backing!=e->backing||w->result||w->original_return<e->start||w->original_return>e->end||
 (c->last_write_serial&&w->reserved!=c->last_write_serial+1u)){la_fail(c,LA_SCOPE);goto done;}
 c->last_write_serial=w->reserved;
 if(w->flags!=(PV_META_MATCHED|PV_META_SUCCESS|PV_META_ACTIVE_ENTRY)){if(c->policy.writes)la_fail(c,LA_GENERATION);goto done;}
 if(w->bytes2||w->bytes1!=CD_BLOCK){la_fail(c,LA_SCOPE);goto done;}
 cd_write(&c->policy,w->token,w->offset1,w->bytes1);if(c->policy.invalid)la_fail(c,LA_GENERATION);
 done:t->admitted=FALSE;SetLastError(saved);
}
void rt_device_created(DirectSoundDevice*d){d->rt_id=rt_id();}
void rt_client_open(DirectSoundDevice*d)
{DWORD epoch=la_next(context,(volatile LONG*)&d->rt_epoch);d->rt_frames=0;
 la_store(&d->rt_primary_format_epoch,epoch&&la_primary(d->pwfx)?epoch:0);}
void rt_buffer_created(IDirectSoundBufferImpl*b,DWORD duplicate){(void)duplicate;b->rt_id=rt_id();b->rt_seen=0;}
void rt_buffer_registered(IDirectSoundBufferImpl*b,HRESULT result){pv_register(b,result);}
void rt_close(IDirectSoundBufferImpl*b){conditional_invalidate(b);}
void rt_device_close(DirectSoundDevice*d){if(context&&la_load(&context->device)==d->rt_id)la_fail(context,LA_DESTROY);}
void cursor_device_changing(DirectSoundDevice*d)
{
 struct rt_context*c=context;la_store(&d->rt_primary_format_epoch,0);
 if(c&&la_load(&c->device)==d->rt_id){
  if(la_load(&c->state)==LA_ACTIVE)la_fail(c,LA_FORMAT);
  else if(la_load(&c->state)==LA_WAIT){la_store(&c->epoch,0);la_store(&c->looping_seen,0);}
 }
}
void cursor_advertise(IDirectSoundBufferImpl*b,DWORD*play,DWORD*write){(void)b;(void)play;(void)write;}
void rt_primary_unsupported(DirectSoundDevice*d){if(context&&la_load(&context->device)==d->rt_id)la_fail(context,LA_FORMAT);}
LONG rt_mix_begin(DirectSoundDevice*d,const void*pcm,DWORD frames,ULONGLONG entry,ULONGLONG acquired)
{(void)d;(void)pcm;(void)frames;(void)entry;(void)acquired;return -1;}
void rt_mix_end(DirectSoundDevice*d,LONG slot,DWORD frames,HRESULT result)
{(void)slot;if(SUCCEEDED(result)){if(d->rt_frames>UINT64_MAX-frames){la_fail(context,LA_GENERATION);return;}d->rt_frames+=frames;}
 else if(context&&la_load(&context->device)==d->rt_id)la_fail(context,LA_API);}
