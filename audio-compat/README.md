# Origins audio compatibility component

Origins Launcher automatically supplies this game-local DirectSound component for the exact supported Dragon Age: Origins/Wine versions recorded in `component.json`. It does not replace macOS audio drivers or the runtime's shared DirectSound library. No audio is recorded.

The component keeps the game's original audio data and mixing code. For a qualified DA:O producer, it can shorten an otherwise unnecessary wait when fresh, fully protected buffer coverage proves that new audio is needed. If replenishment falls behind, assistance pauses and only resumes after fresh healthy progress. Identity, format, control, coverage and stalled-consumer failures fall back to original behavior. There is no timed trial or lifetime action limit. Diagnostic counters saturate rather than changing playback policy.

This is a beta compatibility component. A successful source build is not proof that every Mac, game revision or audio device has been tested. Exact game, FMOD and runtime checks are deliberate; the launcher preserves unrelated game-local DLLs.

## Source and licensing

The modified library and compatibility additions are licensed under **LGPL-2.1-or-later**, independently of the launcher's GPL licence and artwork terms. See [COPYING.LIB](COPYING.LIB). Wine copyrights and licence notices remain in their original files. Origins Launcher compatibility additions are Copyright (C) 2026 David Richard Smith. Modified upstream files carry dated change notices.

The complete matching source archive named in `component.json` is included beside this file in the built app's `Contents/Resources/audio-compat` directory. It contains:

- The complete unmodified Wine 11.0 source archive, including its dependency sources and notices.
- Every changed upstream file and all added component sources in `overlay/`.
- The build recipe, exact source hashes, toolchain provenance and focused host tests.

No game executable, FMOD binary, Steam client, credentials or save files are included. The DLL is built from the official Wine 11.0 source tag, not from an unreleased Sikarugir source tree. Compatibility with the supported Sikarugir engine is separately checked by the launcher.

The pinned upstream archive is [Wine 11.0](https://codeload.github.com/wine-mirror/wine/tar.gz/refs/tags/wine-11.0), SHA-256 `f09e8153aa46a581d2b56a5b1363b04832070b9409d9244a68cf482b243ff14a`. The source package includes it, so rebuilding does not depend on that download remaining available.

## Rebuilding the library

The tested build host is Apple Silicon macOS with Apple's command-line build tools. Recorded versions are in `build-provenance.json`: Apple Clang 21.0.0, LLD 19.1.7, GNU Bison 3.8.2 and flex 2.6.4. The native build tools target x86_64 and require Rosetta on Apple Silicon. The resulting DLL is PE32 i386 for the specified Wine runtime, not a macOS native audio driver.

The recipe requires Python 3, make, Clang, flex, Bison and a directory exposing both `ld.lld` and `lld-link`. The recorded linker was the unmodified LLD supplied with Rust 1.85.0; the Rust compiler is not a runtime dependency. If using an uninstalled Bison build, supply its source `data` directory as shown. An installed Bison normally finds its own data without that option.

From the extracted corresponding-source directory:

```sh
python3 build.py \
  --wine-archive upstream/wine-11.0.tar.gz \
  --work-dir /tmp/origins-audio-build \
  --output /tmp/origins-audio-output/dsound.dll \
  --bison /path/to/bison \
  --bison-data /path/to/bison/data \
  --lld-dir /path/to/lld/bin
```

Use a new, absent work directory. The recipe verifies the archive and overlay, prepares the full Wine source, configures and builds every required object, and produces the final DLL. It never launches Wine or the game. Generated make rules use Wine's internal import-library generator and a small inherited standard-header correction to retain SafeSEH. The DLL uses native loading rather than Wine's builtin marker.

Debug data and private build paths are excluded. The finalization step validates and removes only Wine's empty CodeView placeholder and unmapped COFF symbols; mapped executable code, imports, exports, resources and relocations are preserved. Link timestamps are fixed. Clean builds in different directories produced identical output with the recorded toolchain; other toolchain versions may produce different hashes.

Run the host tests with:

```sh
python3 tests/test_policy.py
python3 tests/test_adapter.py
```

They compile the actual policy and extracted adapter code with address/undefined-behavior sanitizers. They use deterministic Windows API mocks and do not establish audible quality or execute the game.

## Modifying or replacing the component

You may modify, rebuild and redistribute this library under its LGPL terms. The official manifest's exact hashes are safety checks, not a licence restriction or a requirement to use the official binary.

For a modified launcher build:

1. Edit the overlay sources and update their hashes in `source-manifest.json`.
2. Build your DLL and create its complete matching source archive using `make_source_bundle.py`.
3. Update `component.json` with your DLL/source-archive hashes and sizes, plus the matching source-manifest and build-recipe hashes. Use your own version when distributing a modified component.
4. Put the DLL and source archive together in an artifact directory, and set `DAO_AUDIO_ARTIFACT_DIR` to its absolute path when running the launcher's `source/build.sh`. For modified launcher distributions, use the neutral fallback artwork described in the launcher's build instructions.

The packaged manifest and modified DLL must agree. Rebuilding the launcher from source lets you retain or change these checks; no proprietary signing key is needed to build the component. Existing managed installations are updated through the launcher's ownership checks. Do not overwrite an unrelated game-local `dsound.dll`.

## Optional local status

A small per-process JSON file may be written to `C:\dao-support\origins-audio\status` inside the launcher's Wine prefix. Missing directories or write failures never affect playback. Schema 2 records the component version, active/fallback state and recovery counters; it contains no audio, private host path or trial nonce. `early_action_limit` is null. If `telemetry_saturated` is true, saturated counters are lower bounds. Status fields are approximate concurrent telemetry and must not be used to decide whether a file is safe to install.
