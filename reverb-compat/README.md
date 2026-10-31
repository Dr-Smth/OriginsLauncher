# Origins Launcher reverb compatibility

This Wine-derived `winmm.dll` provides a game-only compatibility adjustment for the exact supported Steam Dragon Age: Origins executable and FMOD libraries. It replaces the expensive SFX Reverb processing callback with the original dry contribution, preserving the dry gain and channel mask. This reduces or removes the corresponding wet environmental reverb; it is an audio trade-off, not a claim of identical sound.

The component activates automatically only for the pinned `DAOrigins.exe`, `fmodex.dll` and `fmod_event.dll`. It stages one resolved `FMOD_System_Create` import, then validates the unpacked FMOD code and a newly created System before replacing its exact type-18 registry callback. It neither redistributes nor edits the proprietary game/FMOD files on disk. Unsupported state uses the original callback. The DLL is retained for the process lifetime.

There is no private INI, FMOD Init hook, buffer-size change, Sleep hook, recording, CPU profiler or append-only trial log. Normal game buffer settings remain intact. Origins Launcher's separate DirectSound compatibility component retains its existing timing safeguards and automatic recovery; this component does not depend on or disable them.

The launcher owns installation, exact file hashes, backup/restore receipts and the DA:O-only DLL override. Do not copy this DLL over a Wine runtime or unrelated game. Per-process, fixed-size metadata is atomically written every five seconds to `C:\dao-support\origins-reverb\status\reverb-{pid}.json`; the launcher creates that directory. Metadata contains counters and status, not audio or user content. `active` requires actual dry callback execution. A status failure does not interrupt sound. The component never dereferences historical object identities from its status output.

The Wine-derived component and these modifications are LGPL-2.1-or-later. `COPYING.LIB` is included. Its complete corresponding-source archive contains the exact pinned Wine 11.0 source archive, all overlays, this build recipe, manifest and host regression tests. Proprietary game binaries and artwork are not included. The public launcher is licensed separately.

## Build

Use an Apple Silicon Mac with Xcode command-line tools, a working x86_64 build toolchain, Bison 3.8.2, Flex 2.6.4 and LLVM LLD (the qualified build used LLD 19.1.7). The supplied archive is verified against `source-manifest.json`. The recipe creates a new build directory and does not launch Wine or change an installed game.

```sh
python3 -B build.py \
  --wine-archive upstream/wine-11.0.tar.gz \
  --work-dir /absolute/path/to/new-build \
  --output /absolute/path/to/winmm.dll \
  --bison /absolute/path/to/bison \
  --bison-data /absolute/path/to/bison/share/bison \
  --lld-dir /absolute/path/to/llvm/bin
```

The build targets 32-bit Windows PE with the existing Wine WoW64 runtime, removes nondeterministic symbol/debug metadata, fixes the PE timestamp to zero and emits build provenance. The checked-in source tree intentionally contains no DLL or bundled Wine archive; release assets supply the matching binary and complete source archive. Rebuild tools/platform differences can affect binary identity; use the recorded toolchain for comparison.

## Tests and limitations

```sh
python3 -B tests/run_tests.py --output /absolute/path/to/test-results
```

The tests compile the actual creation wrapper and automatic startup with deterministic host API mocks under AddressSanitizer and UndefinedBehaviorSanitizer. They cover original-call/LastError preservation, malformed or unsupported Systems/registries, exact callback replacement, bounded atomic status publication, and automatic loader configuration. The dry callback is byte-identical to the prior implementation that passed separate PE32 ABI and controlled-signal comparisons.

Host tests do not establish Wine ABI behavior or audible quality in a new release. A real-game combined check remains necessary. Earlier gameplay testing of the same registry/callback mechanism used the existing timing fix together and showed normal audio in the tested session; that is limited to the tested hardware and areas, not all Macs or scenes.
