/* SPDX-License-Identifier: LGPL-2.1-or-later; Copyright (C) 2026 David Richard Smith. */
/* Small live coverage/snapshot state; no payload copies or growing journals. */
void pv_register(IDirectSoundBufferImpl*b,HRESULT result)
{
 struct rt_context*c=context;DWORD selected;
 if(!la_live(c)||FAILED(result)||!b->buffer)return;selected=la_load(&c->selected);
 if(selected==0xffffffffu||(selected&&selected!=b->rt_id&&la_load(&c->backing)==b->buffer->rt_id)){la_fail(c,LA_SCOPE);return;}
 if(!pv_geometry(b))return;selected=InterlockedCompareExchange(&c->selected,-1,0);
 if(!selected){la_store(&c->backing,b->buffer->rt_id);la_store(&c->device,b->device->rt_id);la_store(&c->base,(DWORD)(ULONG_PTR)b->buffer->memory);la_store(&c->selected,b->rt_id);}
 else if(selected!=b->rt_id)la_fail(c,LA_SCOPE);
}
ULONGLONG pv_timestamp(IDirectSoundBufferImpl*b){return la_live(context)&&la_target(context,b)?rt_tick():0;}
ULONGLONG pv_lock_enter(IDirectSoundBufferImpl*b){return pv_timestamp(b);}
static void la_slot_time(struct pv_slot*s,DWORD lo,ULONGLONG time){pv_put(&s->w[lo],time);pv_put(&s->w[lo+1],time>>32);}
DWORD pv_lock_return(IDirectSoundBufferImpl*b,HRESULT result,void*p1,DWORD n1,void*p2,DWORD n2,ULONGLONG entry,ULONGLONG original_return)
{
 struct rt_context*c=context;struct pv_slot*s=NULL;DWORD o1,o2,i,token;
 if(!entry||!la_live(c))return 0;if(FAILED(result)){if(la_load(&c->state)==LA_ACTIVE)la_fail(c,LA_API);return 0;}
 if(!pv_ranges((DWORD)(ULONG_PTR)b->buffer->memory,b->buflen,(DWORD)(ULONG_PTR)p1,n1,(DWORD)(ULONG_PTR)p2,n2,&o1,&o2)){la_fail(c,LA_SCOPE);return 0;}
 token=la_next(c,&c->next_token);if(!token)return 0;
 for(i=0;i<PV_LOCKS;i++)if(InterlockedCompareExchange(&c->slots[i].w[PS_STATE],PV_RESERVED,PV_FREE)==PV_FREE){s=&c->slots[i];break;}
 if(!s){la_fail(c,LA_GENERATION);return 0;}
 pv_put(&s->w[PS_TOKEN],token);pv_put(&s->w[PS_P1],(DWORD)(ULONG_PTR)p1);pv_put(&s->w[PS_N1],n1);
 pv_put(&s->w[PS_P2],(DWORD)(ULONG_PTR)p2);pv_put(&s->w[PS_N2],n2);pv_put(&s->w[PS_THREAD],GetCurrentThreadId());
 la_slot_time(s,PS_ENTRY_LO,entry);la_slot_time(s,PS_ORIG_RETURN_LO,original_return);la_slot_time(s,PS_RESUME_LO,rt_tick());
 pv_put(&s->w[13],la_load(&c->state)==LA_ACTIVE);pv_put(&s->w[PS_STATE],PV_OPEN);return token;
}
struct pv_unlock_call pv_unlock_begin(IDirectSoundBufferImpl*b,void*p1,DWORD n1,void*p2,DWORD n2)
{
 struct pv_unlock_call t={0};struct rt_context*c=context;struct pv_slot_view v,match;DWORD i,count=0,o1,o2;
 t.slot=t.record=-1;if(!la_live(c)||!la_target(c,b))return t;
 if(!pv_ranges((DWORD)(ULONG_PTR)b->buffer->memory,b->buflen,(DWORD)(ULONG_PTR)p1,n1,(DWORD)(ULONG_PTR)p2,n2,&o1,&o2)){la_fail(c,LA_SCOPE);return t;}
 for(i=0;i<PV_LOCKS;i++)if(pv_snapshot(&c->slots[i],&v)&&v.w[PS_STATE]==PV_OPEN&&pv_equal_ranges(&v,(DWORD)(ULONG_PTR)p1,n1,(DWORD)(ULONG_PTR)p2,n2)){t.slot=i;match=v;count++;}
 if(count!=1||!pv_claim(&c->slots[t.slot],&match)){la_fail(c,LA_SCOPE);return t;}
 t.admitted=TRUE;t.token=match.w[PS_TOKEN];t.pending.token=t.token;t.pending.unlock_entry=rt_tick();
 t.pending.lock_entry=pv_time(&match,PS_ENTRY_LO);t.pending.lock_original_return=pv_time(&match,PS_ORIG_RETURN_LO);t.pending.lock_resume=pv_time(&match,PS_RESUME_LO);
 t.pending.object=b->rt_id;t.pending.backing=b->buffer->rt_id;t.pending.offset1=o1;t.pending.bytes1=n1;t.pending.offset2=o2;t.pending.bytes2=n2;
 t.pending.thread=GetCurrentThreadId();t.pending.lock_thread=match.w[PS_THREAD];t.pending.flags=PV_META_MATCHED;
 if(la_load(&c->state)==LA_ACTIVE){t.pending.reserved=la_next(c,&c->write_serial);if(match.w[13])t.pending.flags|=PV_META_ACTIVE_ENTRY;}
 return t;
}
void pv_unlock_end(IDirectSoundBufferImpl*b,struct pv_unlock_call*t,HRESULT result,ULONGLONG original_return)
{
 struct rt_context*c=context;(void)b;if(!c||!t->admitted)return;
 if(pv_word(&c->slots[t->slot].w[PS_TOKEN])!=t->token||pv_word(&c->slots[t->slot].w[PS_STATE])!=PV_UNLOCKING)la_fail(c,LA_SCOPE);
 else pv_put(&c->slots[t->slot].w[PS_STATE],SUCCEEDED(result)?PV_FREE:PV_OPEN);
 t->pending.original_return=original_return;t->pending.result=result;if(SUCCEEDED(result))t->pending.flags|=PV_META_SUCCESS;else la_fail(c,LA_API);
}
void pv_transition(IDirectSoundBufferImpl*b,DWORD kind,HRESULT result)
{(void)b;(void)kind;(void)result;/* Controls are guarded before the original call. */}
struct pv_commit_call pv_commit_begin(IDirectSoundBufferImpl*b,DWORD offset,DWORD size,DWORD bytes)
{
 struct pv_commit_call t={-1,0,0,FALSE,FALSE};struct rt_context*c=context;
 if(!la_live(c)||!la_target(c,b))return t;
 t.tracked=TRUE;InterlockedIncrement(&c->commit_active);t.sequence=la_next(c,&c->commit_sequence);t.id=la_next(c,&c->commit_id);
 if(la_load(&c->state)==LA_ACTIVE&&(!la_secondary(b)||!la_load(&b->device->rt_primary_format_epoch)||la_load(&b->device->rt_primary_format_epoch)!=b->device->rt_epoch||size!=CD_RING||offset>=size||bytes!=1920||bytes>b->maxwritelead||bytes>size))la_fail(c,LA_FORMAT);
 return t;
}
void pv_commit_end(IDirectSoundBufferImpl*b,struct pv_commit_call*t)
{
 struct rt_context*c=context;DWORD active,sequence;(void)b;if(!c||!t->tracked)return;
 active=la_load(&c->commit_active);sequence=la_next(c,&c->commit_sequence);
 la_store(&c->last_commit,active==1&&sequence==t->sequence+1u?t->id:0);InterlockedDecrement(&c->commit_active);
}
LONG pv_read_begin(IDirectSoundBufferImpl*b,DWORD frames)
{
 struct rt_context*c=context;struct pv_read*r;DWORD epoch,generation;
 if(!la_live(c)||!la_target(c,b))return -1;
 if(!la_secondary(b)||!la_primary(b->device->pwfx)||!b->device->rt_epoch||la_load(&b->device->rt_primary_format_epoch)!=b->device->rt_epoch||b->buffer->rt_id!=la_load(&c->backing)||b->state!=STATE_PLAYING||!(b->playflags&DSBPLAY_LOOPING)){
  if(la_load(&c->state)==LA_ACTIVE)la_fail(c,LA_FORMAT);return -1;
 }
 if(InterlockedCompareExchange(&c->consumer_busy,1,0)){la_fail(c,LA_CONCURRENT);return -1;}
 if(la_load(&c->consumer_tid)&&la_load(&c->consumer_tid)!=GetCurrentThreadId()){la_fail(c,LA_CONCURRENT);InterlockedExchange(&c->consumer_busy,0);return -1;}
 la_store(&c->consumer_tid,GetCurrentThreadId());epoch=la_load(&c->epoch);
 if(epoch&&epoch!=b->device->rt_epoch){la_fail(c,LA_FORMAT);InterlockedExchange(&c->consumer_busy,0);return -1;}
 if(!epoch){epoch=b->device->rt_epoch;la_store(&c->epoch,epoch);}
 generation=la_snapshot_begin(&c->latest);if(!generation){la_fail(c,LA_PUBLICATION);InterlockedExchange(&c->consumer_busy,0);return -1;}
 c->staging_generation=generation;r=&c->staging;memset(r,0,sizeof(*r));r->start=rt_tick();
 r->sequence_before=la_load(&c->commit_sequence);r->active_before=la_load(&c->commit_active);r->last_commit_before=la_load(&c->last_commit);
 r->object=b->rt_id;r->backing=b->buffer->rt_id;r->device=b->device->rt_id;r->epoch=epoch;r->frames=frames;r->device_frames=b->device->rt_frames;r->freq_acc=b->freqAccNum;
 r->sec_before=b->sec_mixpos;r->committed_before=b->committed_mixpos;r->use_before=b->use_committed;r->writelead=b->writelead;
 r->freq_num=b->freqAdjustNum;r->freq_den=b->freqAdjustDen;r->filters=b->num_filters;r->volume=b->volpan.lVolume;r->pan=b->volpan.lPan;r->audible=0xffffffffu;return generation;
}
void pv_read_local(IDirectSoundBufferImpl*b,DWORD frames,DWORD committed_samples,BOOL audible)
{
 struct rt_context*c=context;if(!c||!la_target(c,b)||!la_load(&c->consumer_busy)||la_load(&c->consumer_tid)!=GetCurrentThreadId())return;
 c->staging.committed_samples=committed_samples;c->staging.audible=audible?1:0;if(c->staging.frames!=frames)la_fail(c,LA_PUBLICATION);
}
void pv_read_end(IDirectSoundBufferImpl*b,LONG slot)
{
 struct rt_context*c=context;struct pv_read*r;uint32_t words[LA_SNAPSHOT_WORDS];
 if(!c||slot<0)return;r=&c->staging;
 if((DWORD)slot!=c->staging_generation||la_load(&c->consumer_tid)!=GetCurrentThreadId()){la_fail(c,LA_PUBLICATION);return;}
 if(r->audible==1){r->qualified_frames=r->frames;r->flags|=1;}else if(!r->audible)r->flags|=4;else{r->flags|=8;la_fail(c,LA_PUBLICATION);}
 r->sec_after=b->sec_mixpos;r->committed_after=b->committed_mixpos;r->use_after=b->use_committed;r->active_after=la_load(&c->commit_active);
 r->sequence_after=la_load(&c->commit_sequence);r->last_commit_after=la_load(&c->last_commit);r->end=rt_tick();
 if(r->active_before||r->active_after||r->sequence_before!=r->sequence_after)r->flags|=2;
 memcpy(words,r,sizeof(*r));if(!la_snapshot_publish(&c->latest,slot,words))la_fail(c,LA_PUBLICATION);
 if(r->flags==1)la_store(&c->looping_seen,1);InterlockedExchange(&c->consumer_busy,0);
}
