/* SPDX-License-Identifier: LGPL-2.1-or-later; Copyright (C) 2026 David Richard Smith. */
/* Uses Windows Interlocked operations on every mutable slot field.
 * Readers never dereference application pointers. LGPL-2.1-or-later. */
#ifndef ORIGINS_PROVENANCE_SLOTS_H
#define ORIGINS_PROVENANCE_SLOTS_H
struct pv_slot { volatile LONG w[PS_WORDS]; };
struct pv_slot_view { DWORD w[PS_WORDS]; };
static DWORD pv_word(volatile LONG *p){return (DWORD)InterlockedCompareExchange(p,0,0);}
static void pv_put(volatile LONG *p,DWORD n){InterlockedExchange(p,(LONG)n);}
static BOOL pv_snapshot(struct pv_slot *s,struct pv_slot_view *v)
{
 DWORD state=pv_word(&s->w[PS_STATE]),token=pv_word(&s->w[PS_TOKEN]),i;
 if(state!=PV_OPEN&&state!=PV_UNLOCKING)return FALSE;
 for(i=0;i<PS_WORDS;i++)v->w[i]=pv_word(&s->w[i]);
 return state==pv_word(&s->w[PS_STATE])&&token==pv_word(&s->w[PS_TOKEN])&&
  v->w[PS_STATE]==state&&v->w[PS_TOKEN]==token&&token!=0;
}
static BOOL pv_equal_ranges(const struct pv_slot_view *a,DWORD p1,DWORD n1,DWORD p2,DWORD n2)
{return a->w[PS_P1]==p1&&a->w[PS_N1]==n1&&a->w[PS_P2]==p2&&a->w[PS_N2]==n2;}
static BOOL pv_claim(struct pv_slot *s,const struct pv_slot_view *observed)
{
 struct pv_slot_view now;
 if(InterlockedCompareExchange(&s->w[PS_STATE],PV_UNLOCKING,PV_OPEN)!=PV_OPEN)return FALSE;
 /* Revalidate after CAS: a retired slot could have become OPEN with a new token. */
 if(!pv_snapshot(s,&now)||now.w[PS_TOKEN]!=observed->w[PS_TOKEN]||
  !pv_equal_ranges(&now,observed->w[PS_P1],observed->w[PS_N1],observed->w[PS_P2],observed->w[PS_N2])){
  InterlockedCompareExchange(&s->w[PS_STATE],PV_OPEN,PV_UNLOCKING);return FALSE;
 }
 return TRUE;
}
static ULONGLONG pv_time(const struct pv_slot_view *v,DWORD lo)
{return (ULONGLONG)v->w[lo]|((ULONGLONG)v->w[lo+1]<<32);}
static BOOL pv_ranges(DWORD base,DWORD size,DWORD p1,DWORD n1,DWORD p2,DWORD n2,DWORD *o1,DWORD *o2)
{
 if(!n1||!p1||n1>size||n2>size||n1>size-n2)return FALSE;
 if(p1<base)return FALSE;*o1=p1-base;
 if(*o1>=size||n1>size-*o1||(*o1|n1)&3)return FALSE;
 *o2=0;
 if(n2){if(!p2||p2<base)return FALSE;*o2=p2-base;
  if(*o2>=size||n2>size-*o2||(*o2|n2)&3)return FALSE;}
 else if(p2)return FALSE; /* narrow exact split representation */
 return TRUE;
}
#endif
