/* SPDX-License-Identifier: LGPL-2.1-or-later; Copyright (C) 2026 David Richard Smith. */
#ifndef ORIGINS_PROVENANCE_API_H
#define ORIGINS_PROVENANCE_API_H
#include "provenance_format.h"
struct pv_unlock_call { LONG slot,record; DWORD token; BOOL admitted; struct pv_write pending; /* Stack-local matched completion; payload fields always zero. */ };
struct pv_commit_call { LONG record; DWORD id,sequence; BOOL tracked,admitted; };
void pv_register(IDirectSoundBufferImpl *b,HRESULT result);
ULONGLONG pv_lock_enter(IDirectSoundBufferImpl *b);
ULONGLONG pv_timestamp(IDirectSoundBufferImpl *b);
DWORD pv_lock_return(IDirectSoundBufferImpl *b,HRESULT result,void *p1,DWORD n1,void *p2,DWORD n2,ULONGLONG entry,ULONGLONG original_return);
struct pv_unlock_call pv_unlock_begin(IDirectSoundBufferImpl *b,void *p1,DWORD n1,void *p2,DWORD n2);
void pv_unlock_end(IDirectSoundBufferImpl *b,struct pv_unlock_call *call,HRESULT result,ULONGLONG original_return);
void pv_transition(IDirectSoundBufferImpl *b,DWORD kind,HRESULT result);
struct pv_commit_call pv_commit_begin(IDirectSoundBufferImpl *b,DWORD offset,DWORD size,DWORD bytes);
void pv_commit_end(IDirectSoundBufferImpl *b,struct pv_commit_call *call);
LONG pv_read_begin(IDirectSoundBufferImpl *b,DWORD frames);
void pv_read_local(IDirectSoundBufferImpl *b,DWORD frames,DWORD committed_samples,BOOL audible);
void pv_read_end(IDirectSoundBufferImpl *b,LONG slot);
#endif
