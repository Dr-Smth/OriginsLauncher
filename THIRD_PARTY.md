# Third-party components

The project's [GNU GPL version 3 only licence](LICENSE) covers the current
project-owned work identified in [Licensing](LICENSING.md). It does not replace
another author's licence or grant rights to the game, reserved artwork or a
prepared game environment. The launcher code is open source; independently
licensed components keep their own terms. Earlier MIT-licensed copies keep
their supplied terms.

## Included in a built launcher

| Component | Source and terms | Distribution handling |
| --- | --- | --- |
| CPython 3.14.9 from Astral's `python-build-standalone`, build 20261021 | [Official release](https://github.com/astral-sh/python-build-standalone/releases/tag/20261021), [Python licence](https://docs.python.org/3.14/license.html) | A pinned Apple Silicon interpreter is bundled so players need no system Python. Preserve the interpreter and dependency licences from the exact archive. |
| Python's included libraries | [Upstream licensing guidance](https://gregoryszorc.com/docs/python-build-standalone/main/running.html#licensing) | Components have individual licences; use the shipped notices and distribution metadata. Do not label the entire interpreter as GPL, MIT or MPL. |

The `python-build-standalone` build system itself is
[MPL-2.0](https://github.com/astral-sh/python-build-standalone/blob/main/LICENSE).
That is distinct from the licences of its generated Python distribution.
The application invokes Python as a separate executable. Build-time version, URL
and hash pins are recorded in `dependency-manifest.json`.

The build retains the install-only distribution and adds `PYTHON.json` and its
top-level licence files from the matching full archive under
`Contents/Resources/python/THIRD_PARTY_LICENSES`. `ORIGIN.json` identifies both
inputs. Bundled package notices, including pip's vendor licences, remain with
their packages. No changes are made to Python source; local signing changes
signature metadata for the packaged executables.

## Built-in DA:O audio compatibility

Beta.7 bundles a modified Wine 11.0 DirectSound library (`dsound.dll`),
licensed under **LGPL-2.1-or-later**, separately from the GPL launcher. It is
installed beside a verified DA:O executable and selected only for `DAOrigins.exe`.
It does not replace the game executable, FMOD, shared Wine audio driver or macOS
audio settings. No game or FMOD binary is redistributed.

The app retains the LGPL text, upstream notices, modification details and the
complete matching source archive under `Contents/Resources/audio-compat/`.
The archive contains the pinned pristine Wine source, the complete changed-file
overlay, build recipe and tests. The same archive accompanies a packaged release.
See [component source and build instructions](audio-compat/README.md) and its
[source manifest](audio-compat/source-manifest.json). Keep those materials with
redistributed binaries. A reference to upstream source alone is not the source
package for this modified build.

## Built-in DA:O reverb compatibility

Beta.8 adds a modified Wine 11.0 `winmm.dll`, separately licensed under
**LGPL-2.1-or-later**. It supplies a DA:O-specific replacement for the identified
FMOD SFX reverb callback, preserving dry audio and omitting the wet reverb effect.
It uses independently written compatibility code; no game or FMOD binary is
redistributed or replaced on disk.

The component is confined to the verified game process. It does not change
other games, macOS audio settings or the existing timing safeguard. Its complete
matching source, licence, manifests and notices are included under
`Contents/Resources/reverb-compat/`. The same complete source archive accompanies
the installer. See [reverb source and build instructions](reverb-compat/README.md).

## Downloaded during setup, not shipped in our app or source archive

| Component | Official source | Licence/provenance note |
| --- | --- | --- |
| Sikarugir template 1.0.24 | [Template releases](https://github.com/Sikarugir-App/Template/releases/tag/v1.0) | A mixed-licence upstream wrapper. Its terms are not replaced by ours. |
| WS12WineSikarugir11.0_1 | [Engine releases](https://github.com/Sikarugir-App/Engines/releases/tag/v1.0) | Wine is LGPL; the engine contains downstream changes and supporting components. |
| Windows Steam | [Valve installer](https://cdn.akamai.steamstatic.com/client/installer/SteamSetup.exe), [Steam agreement](https://store.steampowered.com/agreement/) | Proprietary client, obtained from Valve. The user signs in and acquires game content through Steam. |
| Dragon Age: Origins and prerequisites | User's Steam library; [game EULA](https://store.steampowered.com/eula/eula_47810) | Game, DLC, assets and shipped Microsoft/NVIDIA installers are not included in this repository or launcher distribution. |

The runtime bootstrap verifies pinned archive hashes and preserves upstream
notices. Sikarugir explicitly identifies Configure.app as LGPL-2.1 and says its
Launcher/Creator are outside that licence. Do not assume the whole template is
LGPL or mirror it under this project's licence. See the
[upstream component statement](https://github.com/Sikarugir-App/Sikarugir#components-that-fall-under-lgpl-21-license)
and [Configure sources/licence](https://github.com/Sikarugir-App/Sikarugir-foss-sources).

The template supplies DXVK/D9VK, Mesa KosmicKrisp and other supporting libraries.
[DXVK](https://github.com/doitsujin/dxvk/blob/master/LICENSE) uses the zlib/libpng
licence. [Mesa](https://docs.mesa3d.org/license.html) is mostly MIT, with
component-specific terms. Any future binary redistribution needs an audit of the
exact build and its dependencies, not just the headline project licences.
Redistributing LGPL binaries also requires compliance with applicable
corresponding-source obligations for that build.

The upstream template also contains Apple's proprietary D3DMetal. This launcher
selects D9VK and leaves D3DMetal disabled. Its presence in the downloaded template
still matters to anyone contemplating redistribution: Apple's
[separate agreement](https://github.com/Sikarugir-App/Sikarugir/blob/main/D3DMetal/4.0/License.pdf)
has non-commercial distribution and other restrictions. The project does not
bundle or mirror the template in its own release.

## Optional UI scaling

[DAFix v0.0.3](https://github.com/Lyall/DAFix/releases/tag/v0.0.3), by Lyall, is an
optional download after game installation. Its source is
[MIT licensed](https://github.com/Lyall/DAFix/blob/v0.0.3/LICENSE.md), copyright 2024
Lyall. The archive includes Ultimate ASI Loader, copyright 2023 ThirteenAG, also
under MIT; its licence is supplied in `UltimateASILoader_LICENSE.md`.

The installer must preserve both notices: the release ZIP includes the loader's
licence but not DAFix's own licence, so the latter is obtained separately from the
pinned upstream tag. This extension modifies display behaviour while the game
runs. It does not supply the game or unlock ownership. Users remain responsible
for the terms applying to their game and other installed mods.

Installed notices are retained under
`data/ui-scaling/licenses/0.0.3/` within the local data root, separately from
transaction backups. The installation receipt records their paths and hashes.

Verified DAFix artifact on 25 October 2026:

```text
URL: https://github.com/Lyall/DAFix/releases/download/v0.0.3/DAFix_v0.0.3.zip
Size: 1191813 bytes
SHA-256: 613a3d005da6d95ed773b3281e1d8518c71d91effd1ae32e27d6a5986b64059a
Licence URL: https://raw.githubusercontent.com/Lyall/DAFix/v0.0.3/LICENSE.md
Licence SHA-256: e6d3e38c2034ff57595323c9a346b9c298ad59074255987fde23993d99cbe88e
```

## Names and artwork

Official builds use separately licensed artwork by Aberrant Ink; source builds
default to the original icon generated by `source/Icon.swift`. The artist-owned
logo has separate reserved rights, rather than inheriting the software licence;
see [Artwork](ARTWORK.md) for the scope and permission requirements. The GPL
software licence does not include rights to that separately identified artwork.

No EA game logo, art, music or other game asset is included. Product names identify
supported software and remain their respective owners' trademarks. This project
is not endorsed by or affiliated with EA or its licensors, BioWare, Valve, Apple,
Sikarugir, Astral, Lyall or the Wine project.
