/* SPDX-License-Identifier: LGPL-2.1-or-later; Copyright (C) 2026 David Richard Smith. */
/* Private compatibility adapter: stack-local API data only, no event journal. */
#ifndef ORIGINS_ROUTE_FORMAT_H
#define ORIGINS_ROUTE_FORMAT_H
#include <stdint.h>
enum rt_kind { RT_DEVICE=1,RT_CLIENT,RT_BUFFER,RT_DUPLICATE,RT_DESTROY,RT_CREATE_CALL,
 RT_LOCK,RT_UNLOCK,RT_PLAY,RT_STOP,RT_POSITION,RT_SEEK,RT_FREQUENCY,RT_COOPERATIVE,
 RT_PRIMARY_UNSUPPORTED,RT_DEVICE_CLOSE,RT_REGISTER,RT_DUPLICATE_CALL };
struct rt_event { uint64_t start,end;uint32_t kind,tid,object,backing,device,caller,result,flags,data[20]; };
#endif
