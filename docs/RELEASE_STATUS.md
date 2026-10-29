# Release validation

## Beta.7 — 29 October 2026

Beta.7 adds the
built-in audio component, optional DA:O-only 4 GB memory support and launcher UI
cleanup. The public beta.6 installer and its matching source remain unchanged.

Beta.7 adds automatic DA:O-only audio compatibility and optional **4 GB memory
support**. The Steam game executable remains unchanged. The audio component is
installed only for exact supported game, FMOD and runtime versions; unsupported
installations and unrelated audio mods are preserved. See [Audio compatibility](AUDIO.md).

The production audio component and 4 GB mode were tested together on the M5 Pro
MacBook. The user confirmed gameplay, then restarted the game and successfully
reloaded the save with controls and sound working. A brief audio issue occurred
and cleared itself; its precise timing and cause are unknown.

The main session's final component status showed about 11 minutes of process
uptime, four pauses followed by four resumptions, and no permanent cutoff.
Assistance remained active. These counters describe component behavior; they
neither measure audible quality nor establish when or why the brief issue
occurred. No audio was recorded.

The automated launcher suite passed **322 tests**, including **49 audio manager,
controller and packaging tests**. The component's separate sanitizer-backed host
tests passed 52 adapter cases and five policy scenario groups. These checks
cover policy boundaries, recovery, file ownership, interrupted changes and
source/binary pairing; they do not establish audible quality on other hardware.

This evidence is from one Mac. **M1 MacBook Air reports have not yet been
retested with the fix**, and the beta does not claim that every audio problem is
resolved. Exact package checks and artifact hashes are recorded in the
`VALIDATION.json` attached to the beta.7 release. Historical beta.6 opening
checks below do not validate a different installer.

The production audio DLL is `c8a4e9ed9c78c365d0e6d3ca7f5e0d9bb0146257d0d414af8d64d705d5cac136`
(SHA-256). Its complete matching source archive is
`e6a0b76eedd65a8b6f6e3888c98532b95eac6554078bf86ff095efa790853050`.
Three fresh source builds produced the same final DLL with the recorded
toolchain. The app packages the library's LGPL notices and complete source;
see [Building](BUILDING.md) and [third-party notices](../THIRD_PARTY.md).

## Historical beta.6 release

Source preparation date: 26 October 2026. **0.2.0-beta.6** updates the separately
licensed Aberrant Ink artwork terms. The app version is `0.2.0`, build `6`. It
retains the beta.5 logo, background and game behaviour. It remains an explicitly
labelled unsigned beta, with an ad-hoc integrity signature and no Developer ID
or Apple notarization.

The public repository at
[Dr-Smth/OriginsLauncher](https://github.com/Dr-Smth/OriginsLauncher) starts with a
clean GPL snapshot. The earlier Git history, original artwork PNGs and
beta.3–beta.5 releases remain in the private maintenance repository. Their
artifacts and permissions are preserved, not rewritten.

Beta.6's installer and matching audited source ZIP are published unchanged from
private validation. The public `main` branch includes later documentation edits;
the release's attached source ZIP is the exact source supplied with the app.
Its `SOURCE-REVISION.txt` records the original private build commit. The frozen
`VALIDATION.json` describes validation before public launch; later publication
and download checks belong in the release record rather than being written back
into those historical files.

## Beta.6 changes and validation boundary

The maintainer confirmed Aberrant Ink's revised permission on 26 October 2026:
anyone may use official builds, including for business use, and share unchanged
copies free of charge. Selling copies containing the artwork requires separate
permission. Separate logo reuse and inclusion in modified or independently built
forks still require permission. See [Artwork](../ARTWORK.md). The restriction is
on the separately licensed artwork. The GPL-covered code may still be used,
modified, distributed and sold in accordance with GPL-3.0-only. Source builds can
use the original GPL fallback icon or other permitted artwork.

The official artwork receipt identifies this policy and the hash of its notice.
Packaging rejects earlier policy receipts, changed artwork or stale notices.
The audited source ZIP contains the project code, build scripts and notices,
excludes the reserved PNGs, and builds with the original fallback icon. The
maintainer's simplified README is retained with the release and artwork sections
updated. There are no game-launch, runtime, display or save changes.

The report beside the frozen beta.6 artifacts records 226 automated tests passing
under system Python and bundled Python 3.14.9. Source ZIP integrity and all 51
exported files were verified. Disk-image integrity, deep strict ad-hoc signature,
project/artwork notices and empty-install smoke checks passed; all 1,743 mounted
app file/link entries matched the built app. The 33 checked existing game, save
and configuration files were unchanged, and packaging did not replace the
installed app.

Those frozen package checks did not include a new gameplay session or
downloaded-app Open Anyway test for beta.6. The later opening check is recorded
below; historical observations apply only to the versions and environment
identified. There is no automatic app updater.

| Frozen beta.6 artifact | SHA-256 |
| --- | --- |
| `OriginsLauncher-0.2.0-beta.6-arm64-UNSIGNED-BETA.dmg` | `55bc81020a6f17095d5061cd1bee95243887778960763de211dd522371cab170` |
| `OriginsLauncher-0.2.0-beta.6-source.zip` | `f2d8cbe6579ebb2417ee06c1934e7e97c239d17e05be596ef0d84a5bab7a320d` |

## Beta.6 downloaded-app opening: completed

On 26 October 2026, the exact beta.6 disk image was downloaded through the browser
with normal quarantine and its SHA-256 matched the value above. Finder copied
the app into Applications; all 1,743 installed app file/link entries matched the
validated build (`0.2.0`, build `6`).

The tester observed the macOS warning, personally approved **Open Anyway** in
Settings, and confirmed that the launcher opened normally. Gatekeeper remained
enabled. The check stopped at the installed main window without starting setup
or the game. All 33 tracked game, settings and save files matched the pre-opening
baseline when compared after successful opening.

This establishes the exact beta.6 approval path on the existing test Mac/account.
It is separate from the earlier beta.4 result and from a gameplay test. Another
Mac/account and managed-device policies are not established by this observation.
Anonymous public downloads were verified separately below. The original frozen `VALIDATION.json` remains
unchanged; this is later supplemental evidence.

## Historical beta.5 validation and artwork terms

The frozen beta.5 app uses build `5` and the same Aberrant Ink icon. Its original
artwork notice expressly permits resale of unchanged official builds. Beta.6's
new terms do not rewrite that notice or purport to revoke prior grants. The
beta.5 tag, source ZIP, installer and release record are preserved unchanged.

All 224 tests passed with system Python and bundled Python 3.14.9. Its 51-file
source export, source/archive equality, app and artwork notices, disk-image
integrity, deep strict ad-hoc signature and empty-install controller smoke
checks passed. All 1,743 app file/link entries matched between built and mounted
copies, and the icon matched the previously inspected local artwork build.
All 33 checked game/save/configuration files were unchanged; the installed app
was not replaced. There was no new beta.5 gameplay or Open Anyway session.

The private GitHub prerelease's six reported asset checksums matched the locally
verified files; its downloaded source ZIP also matched. An in-app-browser
re-download of the DMG timed out and was not verified. This is a download-test
limitation, not a checksum mismatch. The complete 53-file repository snapshot
matched the local source at commit `26ce0627cf4bb098ef25385ad7b83352534ab3f0`.

| Frozen beta.5 artifact | SHA-256 |
| --- | --- |
| `OriginsLauncher-0.2.0-beta.5-arm64-UNSIGNED-BETA.dmg` | `18bd33e5364caabc457aa0e7ba3d1756c58136559d2547c4993406be2017ebe9` |
| `OriginsLauncher-0.2.0-beta.5-source.zip` | `b06f2ac375938e9b5239835b9579ac9dedc7dcf995bf3684897ff6084be798fc` |

## Historical beta.4 validation: completed

The frozen GPL beta.4 app used the original generated icon, app build `4`.
All 210 tests passed with system Python and the bundled Python 3.14.9. Its
50-file source export, source/archive equality, app notices, disk-image integrity,
deep strict ad-hoc signature and empty-install smoke checks passed. All 1,741
app file/link entries matched between built, mounted and installed copies.

Safari applied normal quarantine to the exact beta.4 disk image. After copying
the app to the user's Applications folder, the user completed **Open Anyway**
and confirmed it opened normally. The installed and running copy matched the
audited app. Gatekeeper remained enabled. All 33 checked current game, save and
configuration files were unchanged. This checked one Mac and existing account,
using a loopback download; public hosting and another Mac/account remain untested.
There was no new beta.4 gameplay session.

| Frozen beta.4 artifact | SHA-256 |
| --- | --- |
| `OriginsLauncher-0.2.0-beta.4-arm64-UNSIGNED-BETA.dmg` | `5dc2dbe3bdaea12273a246a47cf169fe4e4169244639fda650f5f673899f2c6f` |
| `OriginsLauncher-0.2.0-beta.4-source.zip` | `537b6bfa16a26eca2d15fe35f9bc4888e83d00ac0df3b490642cb89b8ea55e18` |

Frozen beta.3 and beta.4 archives are preserved unchanged. Beta.3 retains its
supplied MIT terms; beta.4 uses GPL-3.0-only for the covered project work.
Their tests are historical evidence, not beta.6 artifact verification.

## Historical beta.3 validation: completed

The following checks apply to the frozen MIT beta.3 build and its preparation,
unless a later source-only check is explicitly identified.

- All 205 automated tests passed for the frozen beta.3 source snapshot. The later
  private-repository source passed 206 tests, including the added issue-template
  export-audit regression, on 25 October 2026. Its 48-file source audit also passed.
  Tests cover install detection, download/extraction integrity, runtime
  preservation, active Windows-profile containment and interrupted setup, display
  settings, optional UI scaling, bounded Steam startup recovery, unsigned-beta
  packaging and source export checks.
- The Apple Silicon app builds with its own Python interpreter. Its nested code
  and enclosing bundle pass local ad-hoc signature verification.
- The packaged controller reports an empty installation correctly without
  creating game data, starting Wine or downloading anything. The bundled Python
  can load the system CA trust store.
- The final first-use window was inspected visually. Setup information, licence
  links and the fixed bottom setup action are visible.
- A separate empty fixture successfully downloaded and verified both pinned
  Sikarugir archives, validated their extraction and assembled the runtime.
  A second bootstrap preserved the existing result. This check did not run Wine,
  install Steam or create a signed-in environment.
- Python component notices and pip vendor notices are retained in the app.
  The source export and app were inspected for personal paths, account data,
  game files, prepared prefixes and legacy runtime-location pointers.
- Existing gameplay evidence includes rendering, input, audio, Retina/UI scaling
  and save/reload on one Mac. See [Compatibility](COMPATIBILITY.md) for its scope.
- The exact source ZIP passed integrity, allowlist, manifest and independent
  review checks. Its 44 exported files contain no prepared environment or private
  validation record. The disk image passed checksum, private-payload, dependency
  notice, deep strict ad-hoc signature and empty-install smoke checks. All 1,739
  app file/link entries matched the tested build.

## Exact beta.3 artifacts

| Artifact | SHA-256 |
| --- | --- |
| `OriginsLauncher-0.2.0-beta.3-arm64-UNSIGNED-BETA.dmg` | `0263f55e45b2ecd2653ac513a114d818c6367cccfa159cf60171a8f73bddd073` |
| `OriginsLauncher-0.2.0-beta.3-source.zip` | `fa41701239ba18e3c80c20da41e42c2acc2f579f1448f65f1019f9fe1b04678b` |

These archives are frozen and have not been repackaged. Repository documentation
was refreshed after their creation, so archived statements that the final
artifact audit or Open Anyway check are pending are superseded by this record.
The source ZIP is the packaging-time snapshot, not an export of the current
repository documentation.

## Historical beta.3 downloaded-app approval test: passed

Safari downloaded the exact disk image from a temporary loopback-only server and
applied normal quarantine. Its checksum matched the audited release. Gatekeeper
displayed the expected unsigned-app block; the tester used **Privacy & Security →
Open Anyway**, authenticated and confirmed the launch. The running executable
was verified in macOS AppTranslocation, and all 1,739 file/link entries matched
the audited app. It displayed the installed game and existing display choices.

All 120 checked game, save, configuration, mod and launcher-data files across the
two existing environments remained unchanged, as did the native display
preference. No setup, Steam launch, game launch or display change was invoked.
The test app was closed, its image ejected, the temporary server stopped and the
usual launcher reopened. No additional app was installed. Gatekeeper remained
enabled; quarantine was not removed and no global security policy was changed.

This verifies this Mac and user account, opening directly from a browser-downloaded
disk image. It does not verify a public download host, a drag-install destination,
another Mac/account or managed-device policies. Automatic signature assessment
still rejects the unsigned app; the successful path was the user's per-app
approval, not Developer ID signing or notarization.

## Historical changes in beta.3

- Added bounded Steam startup recovery. An explicit setup or **Open Steam** action
  enables follow-up while Origins Launcher remains open, including when minimized.
  Fresh updater-completion evidence and confirmed process absence are required
  before Steam is reopened. Follow-up is limited to three reopen attempts within
  20 minutes, stops when Steam's interface or the game starts, and is cancelled
  when Origins Launcher closes. It does not terminate running processes.
- The recovery logic is implemented and unit tested. The real multi-update
  startup sequence has **not** been re-exercised with this implementation yet.
- Restored the original gold app logo. The separately previewed palette change
  has not been applied to the launcher.

## Historical beta.3 isolated fresh-install functional test: passed

The real first-use flow downloaded and verified the runtime into an empty data
folder. An interrupted prefix creation exposed a profile-containment issue: a
noncanonical Windows user could still have Documents linked to the host Mac.
The controller now resolves the actual profile, repairs only local leaf
links, rejects escaping parent paths and blocks Steam/game launch until the
profile is contained. Automated regressions and the real profile repair pass.
The GUI retry started the official Steam installer with all user-folder links
contained. Hash checks confirmed the existing game’s protected
configuration/save files were unchanged.

The tester completed the fresh Steam installer and sign-in, and confirmed that
the game download had begun in the isolated environment. The complete Steam
manifest and final executable subsequently confirmed installation completion.
The prerequisite sequence was started once through the packaged launcher.
The tester completed its interactive installers and saved/closed configuration.
The success marker, native DirectX components and valid configuration were then
verified.
The tester subsequently confirmed normal graphics, audio, clicks and cutscenes,
created a character, completed the first conversation/tutorial controls, and
saved without incident. These are user-observed gameplay results, not conclusions
drawn from process or log checks. The tester then quit, relaunched through the
Origins Launcher test app and successfully reloaded the save, with controls and
audio still working. All 46 protected original-environment files remained
unchanged at the checkpoint after the first session. The original working
game environment remained separate from this test.

The tester enabled optional UI scaling in the fresh environment. The installation
receipt and installed files confirm DAFix 0.0.3. After restarting, the tester
initially reported a complete picture, readable text and correctly aligned mouse
input at 2992 × 1934 fullscreen Retina, with HUD scale 0.5 and DPI 96. The tester
then noticed that the top HUD was partly hidden behind the MacBook's physical
camera notch. Retina graphics, text readability and mouse alignment passed with
this known fullscreen HUD limitation.

All 19 registered add-ins are enabled and their directories are present. The
tester reports the installed content is correct; the Installed Content screen
shows Enabled for visible entries including Warden's Keep, Blood Dragon Armor,
The Stone Prisoner, Golem's Might, Witch Hunt, Awakening and Return to Ostagar.
Registration and visible enabled status pass; full DLC campaign play is untested.

## Known fullscreen limitation

In fullscreen on a MacBook with a display notch, the game's top menu bar may be
obscured. Its menus remain accessible through their keyboard shortcuts; Windowed
mode avoids the notch. See [Display settings](DISPLAY.md#macbook-camera-notch).
A specific 2560 × 1600 Retina windowed retest is pending; it is not yet a verified
preset.
This disclosed limitation is accepted for the beta and is not an absolute
release blocker. Core gameplay and save/reload checks still stand.

## Public publication checks

Published and checked on 26 October 2026. The public tag `v0.2.0-beta.6` points to
clean snapshot `d3725b65e7c9f31d57a2eee27daea90bad31841a`. Its 51 text files
were checked against the staging snapshot; source and scripts match the frozen
beta.6 code, with public documentation refreshed separately. Later documentation
commits record these publication results without changing the tag or artifacts.

All five anonymous HTTPS verification checks passed, without browser cookies or
GitHub credentials:

- The public main-branch ZIP returned HTTP 200 and contained exactly the 51
  staged files, byte for byte, with no restricted artwork PNGs.
- The public installer and exact-source ZIP each returned HTTP 200. Both complete
  downloads matched the immutable beta.6 SHA-256 values above.
- Requests for the old private build commit and `OriginsLauncher-maintenance`
  returned HTTP 404. They were not accessible to those anonymous requests;
  this does not claim deletion or revoke earlier permissions.

GitHub's displayed SHA-256 values for all six published release assets matched
the immutable local files. The issue chooser and both report forms rendered
correctly during staging; no test issue was submitted. GitHub private
vulnerability reporting is enabled, as confirmed in the public repository's
Security overview. The maintainer confirms that `security@xr0.io` receives mail
reliably; no independent delivery test was sent for this publication.

A normal drag-install test on another Mac/account remains recommended. Managed
Macs may restrict Open Anyway even though the exact beta.6 check passed on the
test Mac. These publication checks did not start a new gameplay session.

The historical beta.3 clean-app review found no known redistribution blocker
within its reviewed scope. Beta.6 has separate final notice/artifact checks, recorded beside its packages.
This is not blanket legal clearance. The runtime, Steam, game and optional mods
are obtained separately and remain subject to their own terms.

## Disclosed beta limitations

- Fullscreen can obscure the game's top menu bar behind a MacBook display notch;
  use its keyboard shortcuts or Windowed mode as described above.
- The functional test used a fresh environment on the existing test Mac. A second
  Mac without developer tools and the missing-Rosetta path are unverified.
- The real Steam multi-update sequence has not been re-exercised with beta.3's
  new recovery logic; that logic is unit tested.
- DLC campaigns, other Apple Silicon models, external displays, all display
  presets and long play sessions have not been comprehensively tested.
- Normal drag-install and opening on another Mac/account remain unverified.

These are test-coverage limitations to disclose for the beta, not claims that
each is a legal prerequisite to distributing the clean launcher.

## Recommended follow-up for the regular release

Obtain a Developer ID Application identity, sign with hardened runtime, notarize,
staple and verify the final downloaded package. No Apple distribution identity or
notarization result is included. This is the smoother installation route, but it
is not a prerequisite for an explicitly labelled and tested unsigned beta.

Earlier local-preview packages remain labelled `LOCAL-PREVIEW`; the audited
beta.3 disk image is explicitly named `UNSIGNED-BETA`. A build, local signature
or mocked test alone does not establish interactive compatibility. The evidence
above records the checks actually completed. [Releasing](RELEASING.md) describes
the repeatable release process.
