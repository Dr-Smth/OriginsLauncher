/* SPDX-License-Identifier: LGPL-2.1-or-later; Copyright (C) 2026 David Richard Smith. */
#ifndef ORIGINS_ROUTE_TRACE_H
#define ORIGINS_ROUTE_TRACE_H
#include "route_format.h"
#include "provenance_api.h"
struct rt_call {struct rt_event event;LONG slot;BOOL admitted;const struct pv_write *write;};
void rt_init(void);DWORD rt_id(void);ULONGLONG rt_tick(void);ULONGLONG rt_mixer_tick(void);
void rt_device_created(DirectSoundDevice*);void rt_client_open(DirectSoundDevice*);
void rt_buffer_created(IDirectSoundBufferImpl*,DWORD);void rt_buffer_registered(IDirectSoundBufferImpl*,HRESULT);
void rt_close(IDirectSoundBufferImpl*);void rt_device_close(DirectSoundDevice*);
struct rt_call rt_begin(IDirectSoundBufferImpl*,DirectSoundDevice*,DWORD,void*,BOOL);
void rt_end(struct rt_call*,HRESULT);
LONG rt_mix_begin(DirectSoundDevice*,const void*,DWORD,ULONGLONG,ULONGLONG);
void rt_mix_end(DirectSoundDevice*,LONG,DWORD,HRESULT);void rt_primary_unsupported(DirectSoundDevice*);
void cursor_device_changing(DirectSoundDevice*);void cursor_advertise(IDirectSoundBufferImpl*,DWORD*,DWORD*);
BOOL conditional_api_enter(IDirectSoundBufferImpl*,DWORD);void conditional_api_leave(BOOL);
void conditional_invalidate(IDirectSoundBufferImpl*);
#endif
