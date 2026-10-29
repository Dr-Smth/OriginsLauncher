# Building

Build on Apple Silicon with macOS 26 or later, Xcode command-line tools and
Python 3. The app uses SwiftUI/AppKit and Python's standard library. Homebrew is
not required. End users of a packaged app do not need these development tools.

## Audio component build

Beta.7 includes a modified Wine DirectSound library and its complete matching
LGPL source. Build that component first using the pinned source and instructions
in [audio-compat/README.md](../audio-compat/README.md). That step needs Clang,
LLVM's LLD linker and a compatible Bison; these are developer tools only.
End users still install a single app and need none of them.

Keep the resulting `dsound.dll` and complete `*-source.tar.gz` archive in an output
folder outside this repository. Set `DAO_AUDIO_ARTIFACT_DIR` to that folder when
building the app. The app build verifies the binary, source archive, source
overlay and build recipe against `audio-compat/component.json` before copying
them into the bundle. It refuses missing or mismatched materials. The default
artifact folder is `../origins-audio-build` relative to the repository.

From the repository root, after building the audio component:

```sh
DAO_AUDIO_ARTIFACT_DIR="$PWD/../origins-audio-build" \
  bash source/build.sh "$PWD/../Origins Launcher.app"
python3 -B -m unittest discover -s source/tests -v
```

Choose a new app output path **outside the source tree** for each build. The build
refuses an existing output instead of replacing an installed app or merging stale
resources. The source-release audit deliberately rejects build-directory pollution.

The app build compiles the native launcher and display probe, generates the original
icon, bundles the Python controller and a pinned Apple Silicon Python interpreter,
and signs the app locally. Network access is needed on the first build to obtain
Python 3.14.9 from the official Astral `python-build-standalone` release. Versions,
source URLs and SHA-256 values are recorded in `dependency-manifest.json`.

Python and its dependency notices must remain in the app. The licence of the
Python-build project does not replace the licences of the produced interpreter
and its libraries; see [Third-party components](../THIRD_PARTY.md).

Current-source builds must also retain `LICENSE`, `LICENSING.md` and `ARTWORK.md`
with the project notices. Project-owned source is open source under GNU GPL
version 3 only (`GPL-3.0-only`). Distribution of compiled covered work requires
corresponding source through a GPL-compliant method; private builds need not be
published. The software licence does not grant rights to separately reserved
artwork. See [Licensing](../LICENSING.md).
Default builds use the generated GPL fallback icon. This public repository and
the audited release source ZIPs omit the restricted artwork PNGs, retain their
rights notice, and remain fully buildable without those images. The original
Aberrant Ink assets and earlier history are held in the private maintenance
repository. GitHub-generated archives of this public repository omit them too.

For the exact code and notices accompanying the beta.6 installer, download its
[matching source ZIP](https://github.com/Dr-Smth/OriginsLauncher/releases/download/v0.2.0-beta.6/OriginsLauncher-0.2.0-beta.6-source.zip).
The installer and source ZIP are frozen; `main` also contains later publication
documentation and is not a byte-for-byte copy of that archive.

## Official artwork builds

The beta.6 official installer uses the logo by **Aberrant Ink** under the separate
[artwork terms](../ARTWORK.md), version `2026-10-26-beta6`. Recipients may use the
app, including for business use, and share unchanged official copies **free of
charge**. Selling copies containing the artwork requires separate permission
from Aberrant Ink. This permission does not authorise a fork or independent
rebuild to reuse the logo.

To distribute or sell a version without this artwork, use the default build
command above, which generates the GPL fallback icon. To distribute a fork with
other artwork you have permission to use, adapt its branding and packaging; the
local custom-artwork option below deliberately blocks release packaging. Follow
the GPL and other applicable component licences. The code's commercial-use and resale rights remain unchanged.

Beta.5's frozen installer carries its original permission to redistribute
unchanged official builds including sale. Its artifacts and embedded terms are
not rewritten or revoked by the beta.6 revision.

For an authorised maintainer's official release build, supply the exact approved
original image separately and choose an output path outside the source tree.
Replace the example image path below with the actual path to that separately
held file; it is not included in the public checkout:

```sh
DAO_OFFICIAL_ARTWORK=1 \
DAO_CUSTOM_LOGO_PATH="/absolute/path/to/approved/dragon-logo.png" \
DAO_CUSTOM_LOGO_CREDIT="Aberrant Ink" \
bash source/build.sh "$PWD/../Origins Launcher - Official.app"
```

The official mode verifies the approved artwork identity and records it, the
terms version and the notice hash in `OFFICIAL-ARTWORK.json`. It keeps the existing
background, renders the required icon sizes and bundles the artwork notice. The
original source PNG is not copied into the app. Audited release source exports
omit the restricted images, so a maintainer building from an export must supply
the separately held approved image by absolute path.
Setting the flag does not itself grant artwork permission.

Default builds need no restricted image and remain the route for GPL source
rebuilds and forks. The release package must provide the matching code source and
notices; see [Releasing](RELEASING.md).

## Local custom artwork

For an authorised local experiment, run from the repository root with an image
you have permission to use. Replace the example path and artist credit:

```sh
DAO_CUSTOM_LOGO_PATH="/absolute/path/to/your-logo.png" \
DAO_CUSTOM_LOGO_CREDIT="Your artist's credit" \
bash source/build.sh "$PWD/../Origins Launcher - Custom Art.app"
```

The build keeps the existing icon background colour, generates the required icon
sizes, and adds the artist credit and a `LOCAL-ARTWORK.json` marker to the app.
The original image is not copied into the app. You may also supply an absolute
path to another image you are authorised to use.

The release packager rejects apps with this marker. This local-build option does
not grant rights to redistribute the logo or derived icon. Use the explicit
official mode only for the approved logo and authorised official builds; see [Artwork](../ARTWORK.md).

## Local testing

Open the built app directly. Its default environment is
`~/Library/Application Support/OriginsLauncher`. Opening the app alone should not
download dependencies or stop running software; setup is a separate user action.

The controller's available commands are listed by
`python3 -B source/daoctl.py --help`. Use `-B` to avoid generating bytecode inside a signed app. For automated
tests, use temporary directories and synthetic manifests rather than a real game
or account. An existing environment must never be replaced to make a test pass.

An ad-hoc signature is useful for local integrity checks. It is not a Developer ID
signature or a notarization ticket. The default package is a `LOCAL-PREVIEW`.
After the core functional and release checks pass, the packaging script's
`--unsigned-beta` option can create an explicitly labelled downloadable beta without a
paid Apple developer account. Recipients may need Apple's per-app **Open Anyway**
approval; managed Macs may prevent it. The `--public` packaging mode remains
reserved for Developer ID-signed and notarized releases. See
[Releasing](RELEASING.md) for both paths.

## GitHub Actions

The manual **Source and audio checks** workflow (`workflow_dispatch`) runs
launcher tests, the clean-source audit, and host audio policy/adapter tests. It
does not build the audio DLL, app or installer, and does not validate packaged-app
launch or gameplay. Those checks remain local until the pinned audio binary and
matching source archive can be reproducibly provisioned in Actions. Runner usage
may consume the account's allowance depending on repository visibility and plan.
Automatic triggers remain disabled; local commands do not use Actions.

## Architecture

The native app invokes its bundled Python controller without a shell. The
controller creates a dedicated Sikarugir/Wine environment, starts Windows Steam,
and asks Steam to install or launch an owned game. The game and runtime remain
outside the app so updating the launcher preserves them.

The downloaded runtime is assembled from pinned upstream archives. Archive path,
link and size validation runs before extraction. An existing runtime is preserved.
The source includes no Windows operating system, game payload or pre-authenticated
Steam session. Optional UI scaling is a separate upstream extension, described in
[Display settings](DISPLAY.md).
