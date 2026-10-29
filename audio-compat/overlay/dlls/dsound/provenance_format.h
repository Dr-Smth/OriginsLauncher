/* SPDX-License-Identifier: LGPL-2.1-or-later; Copyright (C) 2026 David Richard Smith. */
/* Private narrow PCM16 provenance diagnostic. LGPL-2.1-or-later. */
#ifndef ORIGINS_PROVENANCE_FORMAT_H
#define ORIGINS_PROVENANCE_FORMAT_H
#include <stdint.h>
#define PV_RING_BYTES 98304u
#define PV_LOCKS 32u
#define PV_WRITES 16384u
#define PV_COMMITS 4096u
#define PV_READS 32768u
#define PV_META_WRITE_LIMIT PV_WRITES
enum {PV_META_MATCHED=1u,PV_META_SUCCESS=2u,PV_META_ACTIVE_ENTRY=4u};
/* All slot words are atomic; immutable snapshots serialize as 16 uint32. */
enum { PV_FREE=0,PV_RESERVED,PV_OPEN,PV_UNLOCKING };
enum { PS_STATE=0,PS_TOKEN,PS_P1,PS_N1,PS_P2,PS_N2,PS_ENTRY_LO,PS_ENTRY_HI,
 PS_ORIG_RETURN_LO,PS_ORIG_RETURN_HI,PS_RESUME_LO,PS_RESUME_HI,PS_THREAD,PS_WORDS=16 };
struct pv_write {
 uint64_t unlock_entry,original_return,copy_start,copy_end,lock_entry,lock_original_return,lock_resume;
 uint32_t token,object,backing,offset1,bytes1,offset2,bytes2,payload_offset,payload_bytes,flags,thread,lock_thread,result,reserved;
};
struct pv_commit {
 uint64_t start,end,copy_start,copy_end;
 uint32_t id,object,backing,source_offset,source_bytes,bytes,payload_offset,sequence_before,sequence_after,active_before,active_after,flags;
};
struct pv_read {
 uint64_t start,end,device_frames,freq_acc;
 uint32_t object,backing,device,epoch,frames,pcm_frame,sec_before,sec_after,committed_before,committed_after,
 use_before,use_after,writelead,committed_samples,sequence_before,sequence_after,active_before,active_after,
 last_commit_before,last_commit_after,flags,audible,freq_num,freq_den,filters,volume,pan,qualified_frames; /* Actual materialization, NOT PCM recording. */
};
_Static_assert(sizeof(struct pv_write)==112,"write ABI");
_Static_assert(sizeof(struct pv_commit)==80,"commit ABI");
_Static_assert(sizeof(struct pv_read)==144,"read ABI");
#endif
