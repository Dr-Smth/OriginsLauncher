# Compatibility and evidence

The current beta is **0.2.0-beta.6**, which updates the separate Aberrant Ink artwork terms alongside the GPL notice,
Help/About and release-documentation changes. The game/runtime/display behaviour
is unchanged by those changes. Gameplay and downloaded-app approval observations
below are historical beta.3 evidence unless explicitly stated otherwise. Consult
the validation record supplied alongside the beta.6 artifacts for their exact
package, smoke and downloaded-app test results; do not treat beta.3 observations
as a new beta.6 gameplay session.

The target is Apple Silicon with macOS 26 or 27, Rosetta and the pinned Sikarugir
DirectX 9 renderer. The [upstream runtime](https://github.com/Sikarugir-App/Sikarugir)
specifies Apple Silicon/macOS Tahoe for D9VK. The native launcher's ability to
compile on an older system does not establish game compatibility there.

Apple says general Rosetta support is available through macOS 27 and becomes
limited in macOS 28. Future macOS support must be tested rather than inferred
from the app's minimum version. See [Apple's Rosetta guidance](https://support.apple.com/en-us/102527).

## Existing game setup

User-reported testing on an Apple M5 Pro with 24 GB memory and macOS 27.2 found:

- Steam Ultimate Edition installed and launched through the native launcher.
- Normal gameplay, camera input, dialogue/cutscenes and audio.
- Successful saving and loading after quitting and relaunching the game.
- Correct picture and mouse input in a window and in fullscreen when dimensions
  matched the effective desktop.

Those observations establish a working setup on one Mac. They are not a claim
that every Mac, display, DLC campaign or long play session has been tested. They
also do not establish installation on a second machine. The separate fresh
environment test below covers the release setup flow on the same Mac.

## Prerelease preparation checks

Automated test results are recorded in [Release validation](RELEASE_STATUS.md).
The packaged Apple Silicon Python 3.14.9 interpreter passed an isolated empty-environment status
check and a certificate-trust smoke check. Both pinned upstream runtime archives
were freshly assembled without executing Wine or creating a game prefix. These
are setup/component checks, not a fresh game installation.

Beta.3's bounded Steam startup recovery is unit tested; its real multi-update
sequence has not yet been re-exercised.

Inspection of the built app confirmed Python's dependency notices, the project's
notices and absence of a bundled runtime, game or personal environment. Strict
signature verification passed for the exact packaged app. Its signature is
ad-hoc: it has no Developer ID identity or notarization ticket. See the
[licensing review](LICENSING_REVIEW.md) for the artifact evidence.

## Downloaded app and macOS approval

The exact beta.3 disk image passed its artifact audit and was downloaded through
Safari from a temporary loopback-only server. Safari's normal quarantine was
present and the checksum matched. The tester completed macOS **Open Anyway**;
the running AppTranslocation copy matched all 1,739 audited app file/link entries
and displayed the existing environment correctly. All 120 protected files and
the native display preference remained unchanged. Gatekeeper stayed enabled.

This is evidence for direct opening from the downloaded disk image on the test
Mac and account. It does not cover public hosting, drag-install to Applications,
another Mac/account or managed-device restrictions. It is not evidence of
Developer ID signing or notarization. The public beta.6 release uses the same
frozen installer previously validated during private preparation. Its validation
record and any later publication checks identify the exact artifact tested;
this beta.3 observation does not establish beta.6 approval results.

The exact beta.6 approval path was subsequently checked on 26 October 2026.
Its normal browser download retained quarantine and matched the audited SHA-256.
After Finder copied the app to Applications, all 1,743 installed app file/link
entries matched the tested build. The tester observed macOS’s warning, approved
**Open Anyway** in Settings, and confirmed the launcher opened normally.
Gatekeeper stayed enabled. All 33 tracked game/save/settings files were unchanged
after opening compared with the pre-opening baseline.

That beta.6 check stopped at the installed launcher’s main window on the existing
Mac/account; it did not start setup or retest gameplay. It does not establish
anonymous public-host downloading, another Mac/account or managed-device policy
behaviour. See [Release validation](RELEASE_STATUS.md#beta6-downloaded-app-opening-completed).

## Isolated fresh-install test

A separate first-use test repaired an interrupted Windows-profile setup, then
completed the official Steam installer, sign-in and game download. The tester
completed the interactive prerequisites and saved the game configuration;
the setup marker and native DirectX components were verified.

The tester reports that graphics, audio, clicks and cutscenes work, and that
character creation, the first conversation/tutorial controls and saving completed
without incident. The tester then quit, relaunched through the Origins Launcher
test app and successfully loaded the save; controls and audio still worked.
This establishes the core functional path in a fresh environment on the same
Mac, not on a second machine without developer tools.

The tester also enabled UI scaling in the fresh environment; its receipt and
installed files confirm DAFix 0.0.3. After restarting, the tester initially
reported the whole picture, readable text and aligned mouse input at
2992 × 1934 fullscreen Retina, HUD scale 0.5 and DPI 96. The tester then found
that the top HUD is partly obscured by the MacBook's physical camera notch.
Retina graphics, readability and mouse alignment passed with this known
fullscreen HUD limitation; no broader display compatibility is established.

All 19 registered add-ins are enabled and their directories are present. The
tester reports correct installed content, and the Installed Content screenshot
confirms visible DLC entries are Enabled. Full DLC campaigns remain untested.
See [Release validation](RELEASE_STATUS.md).

## Known fullscreen limitation

In fullscreen on a MacBook with a display notch, the game's top menu bar may be
obscured. Menus remain accessible through their keyboard shortcuts; Windowed
mode avoids this. See [Display settings](DISPLAY.md#macbook-camera-notch).
A 2560 × 1600 Retina windowed retest is pending. This is a disclosed beta
limitation, not an absolute release blocker.
Core gameplay and save/reload after relaunch remain verified by the tester.

## Disclosed beta limitations

- A separate Mac with no developer tools, and the missing-Rosetta installation
  prompt, have not been tested.
- Real multi-update Steam startup with the new bounded recovery and cancellation
  has not been re-exercised.
- DLC campaigns remain unverified.
- Other Apple Silicon models, external displays, display-scale changes, all
  presets and long play sessions have not been comprehensively tested.
- Public-host download and normal drag-install on another Mac/account remain
  unverified.

These limitations must accompany the beta; they do not undo the completed core
functional test. Final-package auditing and Apple's per-app approval path passed
for the exact unsigned beta.3 artifacts within the scope above. Repeat those
checks when the package changes; use Developer ID/notarization for the signed
release. See [Releasing](RELEASING.md).

These package observations concern the frozen beta.3 artifacts, which retain
their supplied MIT terms. The beta.6 GPL release is packaged separately and its
artifact checks must be recorded separately. This document does not claim that
the new beta.6 app has repeated all historical gameplay tests. See
[Release validation](RELEASE_STATUS.md).

Automated tests validate controller and filesystem behaviour. Process/log checks
cannot substitute for actual rendered gameplay, working input, audible sound or
successful save/reload. Record these checks independently in a release test
report; never ship a personal `data/validation.json` to pre-verify another Mac.
