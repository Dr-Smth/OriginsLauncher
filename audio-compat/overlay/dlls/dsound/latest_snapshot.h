/* SPDX-License-Identifier: LGPL-2.1-or-later; Copyright (C) 2026 David Richard Smith. */
/* Bounded latest-value publication. Every concurrently accessed word is atomic.
 * LA_LOAD/STORE/CAS supply acquire/release or stronger operations in PE/tests. */
#ifndef ORIGINS_LATEST_SNAPSHOT_H
#define ORIGINS_LATEST_SNAPSHOT_H
#include <stdint.h>
#define LA_SNAPSHOT_WORDS 36u
struct la_snapshot { volatile int32_t generation; volatile int32_t word[LA_SNAPSHOT_WORDS]; };
/* Caller already owns the single consumer writer claim. No generation reuse. */
static uint32_t la_snapshot_begin(struct la_snapshot *s)
{
 uint32_t n=LA_LOAD(&s->generation);
 if((n&1)||n>=0x7ffffffcu)return 0;
 return LA_CAS(&s->generation,n,n+1u)==n?n+1u:0;
}
static int la_snapshot_publish(struct la_snapshot*s,uint32_t writing,const uint32_t *words)
{
 uint32_t i;if(!writing||!(writing&1)||LA_LOAD(&s->generation)!=writing)return 0;
 for(i=0;i<LA_SNAPSHOT_WORDS;i++)LA_STORE(&s->word[i],words[i]);
 LA_STORE(&s->generation,writing+1u);return 1;
}
/* One bounded attempt; a concurrent change is UNKNOWN, never a blocking retry. */
static int la_snapshot_copy(const struct la_snapshot*s,uint32_t *words,uint32_t *generation)
{
 uint32_t i,n=LA_LOAD(&s->generation);if(!n||(n&1))return 0;
 for(i=0;i<LA_SNAPSHOT_WORDS;i++)words[i]=LA_LOAD(&s->word[i]);
 if(LA_LOAD(&s->generation)!=n)return 0;*generation=n;return 1;
}
static int la_snapshot_stable(const struct la_snapshot*s,uint32_t generation)
{return generation&&!(generation&1)&&LA_LOAD(&s->generation)==generation;}
#endif
