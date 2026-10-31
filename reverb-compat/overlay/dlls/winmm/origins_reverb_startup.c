/* Automatic DA:O-only startup; no INI, block-size hook or private exports.
 * SPDX-License-Identifier: LGPL-2.1-or-later */
static void origins_reverb_attach_game(void)
{
#ifdef __i386__
    DWORD saved=GetLastError();struct origins_reverb_config c;
    memset(&c,0,sizeof(c));c.bytes=sizeof(c);c.version=ORIGINS_REVERB_CONFIG_VERSION;
    c.main_module=GetModuleHandleW(NULL);c.bridge_module=GetModuleHandleW(L"fmod_event.dll");
    c.fmod_module=GetModuleHandleW(L"fmodex.dll");
    /* Attach itself checks exact executable/PE identity, sibling module paths,
     * and the resolved System_Create import. No FMOD API is invoked here. */
    origins_reverb_attach(&c);SetLastError(saved);
#endif
}
