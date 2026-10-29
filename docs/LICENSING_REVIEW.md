# Licensing and distribution review

Reviewed 25 October 2026 against the source, dependency manifest, build scripts
and primary upstream terms; updated 26 October 2026 for the artist-approved
beta.6 artwork terms, while retaining beta.5's original permissions. The project
code uses GNU GPL version 3 only
(`GPL-3.0-only`). This records
a practical release assessment, not blanket legal clearance or advice about
every jurisdiction. Nothing in this review grants rights in another author's
software or artwork.

## Conclusion

The current project-owned work is offered under **GNU GPL version 3 only**
(`GPL-3.0-only`). It is open source: commercial use and selling copies are
permitted without a separate paid licence. Distribution of covered modified or
derivative versions requires preserving GPL freedoms and providing corresponding
source as the licence specifies. Private modifications need not be published,
and there is no requirement to submit changes back to this project. The exact
scope is in [Licensing](../LICENSING.md).

The replacement logo is by **Aberrant Ink** and is excluded from the software
licence. On 26 October 2026, David Richard Smith confirmed the artist's revised
permission for beta.6 and later official builds carrying terms version
`2026-10-26-beta6`: anyone may use the app, including for business use, and share
unchanged official copies free of charge. Selling copies containing the artwork
requires separate permission. Separate logo reuse, artwork modifications and
inclusion in modified or independently built forks also require permission.
This condition is confined to the artwork. GPL-compliant versions using the
default fallback or other authorised art may still be sold.

The original PNG and icon preview are excluded from this public repository and
audited release source ZIPs. GitHub-generated archives of this public repository
also omit those images. Default source builds use the GPL fallback. The asset notice is retained
in both audited source and official artwork packages. See
[Artwork](../ARTWORK.md) for the precise scope.

The frozen **0.2.0-beta.4** packages contain GPL notices and the fallback icon.
**0.2.0-beta.5** introduced the official Aberrant Ink logo under its original
permission to redistribute unchanged official builds including sale. Those
artifacts and embedded terms remain unchanged. The **beta.6** revision does not
revoke prior grants or withdraw separate or earlier permissions. Each exact artifact
must pass its own notice, artwork and corresponding-source checks; results and
hashes belong in the validation record alongside those artifacts, not inferred
from the source-policy or permission change alone.

The exact beta.3 unsigned package passed its artifact and notice checks under
the earlier MIT arrangement. Those historical packages, their supplied terms
and their hashes remain unchanged in the private maintenance repository. The
public repository starts with a clean GPL source snapshot and publishes beta.6
without importing earlier Git history or artwork source files. This assessment neither revokes prior MIT grants
nor relicenses third-party software, and does not establish that every
distribution is permitted.

This conclusion does **not** extend to publishing a prepared game environment or
the complete Sikarugir runtime. Those contain separately licensed and proprietary
components. No game ownership, authentication or DRM bypass was found in the
reviewed launch flow: it asks Steam to install and launch a legitimately acquired
game.

## Component assessment

| Component | Our release boundary | Finding |
| --- | --- | --- |
| Current project-owned launcher, documentation and generated fallback icon | Source and compiled native app | GPL-3.0-only within the scope in `LICENSING.md`; covered binary distributions require corresponding source under the GPL. Prior MIT copies retain their supplied terms. |
| Modified Wine DirectSound audio component (`audio-compat/`) | Game-local DLL plus complete matching source archive in the app and alongside the release | LGPL-2.1-or-later, separately from launcher GPL and artwork terms. Includes pristine pinned Wine 11.0 source, the full overlay, build recipe, notices and tests. No game or FMOD binary is distributed. Exact source/binary hashes and dated modification notices are retained. |
| Aberrant Ink logo | Embedded in official app icons; original PNG and preview omitted from this public repository and audited release source ZIPs | Artist-owned and outside GPL. Beta.6 terms allow app use, including business use, and sharing unchanged official copies free of charge. Selling copies containing the artwork or separate reuse needs permission. Modified/independent builds need permitted replacement artwork or separate permission. Preserve the asset notice. Beta.5 retains its original resale permission. |
| CPython 3.14.9, Astral build 20261021, Apple Silicon | Included in app; downloaded only at build time | Python permits redistribution with its required notices. Dependencies have their own terms. Preserve the exact build's metadata, licence texts and bundled package notices. |
| Sikarugir template 1.0.24 / Wine 11.0_1 | Recipient downloads directly from official upstream on explicit setup | Configure/Wine have FOSS licences; Sikarugir Launcher/Creator are not covered by the stated LGPL licence. Complete-wrapper redistribution is not cleared. |
| D3DMetal contained in upstream template | Downloaded with template, disabled for this DirectX 9 game | Proprietary Apple terms apply. It cannot be described as MIT or LGPL; disabling it would not erase obligations if its bytes were redistributed. |
| Steam and Dragon Age | Recipient obtains through Valve and their own Steam account | No client, game, DLC or account data is included in our app/source release. Their agreements still apply to installation and use. |
| DAFix 0.0.3 / Ultimate ASI Loader | Separate optional download | Both author licences are MIT. Preserve both notices. This is a display extension, not a game licence or a blanket exception to the game's terms. |

Primary terms and provenance:

- [GNU GPL version 3](https://www.gnu.org/licenses/gpl-3.0.html) and
  [GNU's explanation of private modifications and distribution](https://www.gnu.org/licenses/gpl-faq.html#GPLRequireSourcePostedPublic),
  and [its discussion of separately licensed artwork in program output](https://www.gnu.org/licenses/gpl-faq.en.html#WhatCaseIsOutputGPL).
- [Python 3.14 licence](https://docs.python.org/3.14/license.html),
  [Astral distribution licensing](https://gregoryszorc.com/docs/python-build-standalone/main/running.html#licensing),
  [pinned Astral release](https://github.com/astral-sh/python-build-standalone/releases/tag/20261021).
- [Sikarugir component statement](https://github.com/Sikarugir-App/Sikarugir#components-that-fall-under-lgpl-21-license),
  [Configure licence](https://github.com/Sikarugir-App/Sikarugir-foss-sources/blob/main/LICENSE),
  [Wine licence](https://github.com/wine-mirror/wine/blob/master/COPYING.LIB).
- [Apple's separate D3DMetal agreement supplied by upstream](https://github.com/Sikarugir-App/Sikarugir/blob/main/D3DMetal/4.0/License.pdf),
  also inspected in the installed template's `renderer/d3dmetal/License.rtf`.
- [Steam agreement](https://store.steampowered.com/agreement/),
  [game-specific EULA](https://store.steampowered.com/eula/eula_47810),
  [DAFix source licence](https://github.com/Lyall/DAFix/blob/v0.0.3/LICENSE.md).

## Licence transition and contributions

The existing MIT history and frozen beta.3 artifacts are retained privately.
Changing the current licence does not withdraw permissions already granted for
copies under MIT. Before public launch, deliberately choose and review the source
snapshot, reachable history, tags and assets that will be published, and label
their terms accurately. Do not describe old MIT packages as newly restricted or
silently rewrite history to imply that earlier licensing never occurred.

Outside contributions must be available on GPL-compatible terms. Follow
[Contributing](../CONTRIBUTING.md) before accepting them and retain authorship and
required notices. Do not assume that a contributor or the artist has transferred
copyright. Separately reserved artwork needs an explicit asset boundary and
appropriate distribution permission; do not impose its restrictions on the GPL
code. Resolve any uncertainty about combining components or distributing the
artist's work before including them in a release.

For compiled GPL releases, provide corresponding source through a method allowed
by GPLv3 section 6. The intended download workflow is to make the exact matching
source available alongside the app, including required build/installation scripts
and notices. An independent program merely distributed alongside the launcher is
not automatically relicensed under GPL. Combining code into a derivative work
requires separate compatibility analysis; a process boundary alone is not a
blanket legal determination.

## Downloading dependencies is a boundary, not a licence substitute

The setup action identifies upstream sources and provides their terms. Downloads
go from those sources to the recipient's Mac. Our release does not host, mirror
or include the Wine template/engine, Steam installer or game. This keeps those
binaries outside our redistribution package; it does not waive their terms or
guarantee that every possible automated installation/use is permitted.

The Apple agreement inspected limits permitted uses and includes non-commercial
distribution conditions. D3DMetal is not used by this game's renderer, but is
still part of the upstream archive. Do not market the resulting environment as a
fully open-source or commercially cleared port. A future bundled runtime,
commercial port or change of renderer needs renewed review and, where necessary,
rights-holder permission. No such permission has been obtained or implied.

## Concrete checks and remaining gates

The manifest pins Python's install-only archive and matching full archive. The
build script extracts `PYTHON.json` and licence files from the latter, checks that
metadata-referenced licences exist, preserves the install tree and records both
archive identities. This addresses the missing dependency notices in the
install-only archive alone.

The built app and exact beta.3 source ZIP/disk image, carrying the earlier MIT
project notice, were inspected with these results:

- `PYTHON.json` identifies Python 3.14.9, `aarch64-apple-darwin`, `pgo+lto`.
- All 15 licence filenames referenced by that metadata are present. The notice
  directory contains 20 `LICENSE.*` texts, `PYTHON.json` and `ORIGIN.json`.
- Both archive identities in `ORIGIN.json` match the bundled dependency manifest.
- pip's vendor tree retains 20 licence/copying files in their original packages.
- The project `LICENSE` and `THIRD_PARTY.md` are included in app resources.
- No `runtime`, `drive_c`, `steamapps`, Steam client, local `data`/`downloads`
  directory or `runtime-location.json` was found in the app.
- Signature inspection reports `adhoc` and no TeamIdentifier. The disk image is
  explicitly labelled `UNSIGNED-BETA`, not Developer ID signed or notarized.
- The source ZIP's 44 allowlisted files passed manifest and integrity checks.
  The disk image's app matched all 1,739 tested file/link entries and passed
  private-payload, notice and deep strict signature checks. Independent packaged
  licence review found no material findings within this scope.

These findings apply to the inspected build. Repeat the checks on the exact
archive offered for download whenever packaging or dependencies change.
The archives and checksums remain unchanged; current repository documentation
includes later validation results and a changed licence for current project-owned
source. Each new build must include its matching `LICENSE`, `LICENSING.md`
and `ARTWORK.md` alongside `THIRD_PARTY.md` and dependency notices. Official
artwork builds also need the artist notice and `OFFICIAL-ARTWORK.json`. Beta.6's
record identifies the revised terms version and notice hash, so packaging can
reject a build carrying mismatched artwork terms. The earlier package review
does not verify these resources. See
[Release validation](RELEASE_STATUS.md) for exact hashes and the distinction from
the frozen source snapshot.

The DAFix archive was inspected from its author's release. Its SHA-256 is recorded
in [Third-party components](../THIRD_PARTY.md). It contains the loader's MIT notice
but omits DAFix's own notice; setup must retain the separately pinned author
licence as well. No Windows game binaries should be substituted to enable it.
The installer now keeps both texts in a stable versioned licence directory
separate from transaction backups, and records their paths and hashes. Review
of that implementation confirms backup pruning does not define notice retention;
the focused installer test suite also covers this behaviour.

The isolated fresh-install test passed gameplay, audio, controls, cutscenes and
save/reload after relaunch. DLC registration/enabled status passed, while DLC
campaigns remain untested. Safari's normal quarantined download of the exact
disk image also passed the user's Open Anyway flow on the same Mac. This used a
loopback-only download server and direct launch from the disk image; a public
host, drag-install and another Mac/account are not covered. The 120 protected
files and display preference checked during that test were unchanged. These are
functional validation results, not additional rights in third-party components.

Before public binary release, and on each later release:

1. Verify the current licence scope, contribution rights and any included artwork
   permissions. Keep licence notices consistent with the actual source snapshot,
   history and packages offered. Provide the exact corresponding source required
   for a distributed GPL binary. Preserve the checked Python notices and inspect
   the final release archive for
   private paths, accounts, game files, prepared prefixes and signing material.
2. Verify the optional-mod installer preserves both notices and existing mods.
3. Retain the completed fresh-install evidence and publish honest platform
   limitations, including single-Mac coverage and untested Steam multi-update
   recovery, missing Rosetta, other displays and full DLC campaigns.
4. Check the eventual public-host download against the audited checksum and
   repeat normal Gatekeeper tests when the package changes. An explicitly
   labelled unsigned beta may be distributed without a Developer ID certificate;
   explain the missing publisher verification/notarization and link to
   [Apple's per-app approval guidance](https://support.apple.com/en-gb/102445).
   Managed Macs may restrict this path. For the recommended signed-release path,
   Developer ID sign, notarize, staple and verify; see
   [Apple's Developer ID guidance](https://developer.apple.com/developer-id/).
5. Keep distinct branding and an explicit non-affiliation notice. The
   [EA content policy](https://help.ea.com/en/articles/security-and-rules/ea-content-policy/)
   does not grant a general licence to redistribute game content.

The full operational checklist is in [Releasing](RELEASING.md). No public upload,
rights-holder contact, paid membership purchase or legal clearance was performed
as part of this review.

## Beta.7 audio component source boundary

The built-in audio component is a modified Wine library, not a redistribution of
the game's FMOD library or executable. The source and binary correspondence was
checked for the final production component, including the full upstream archive,
all modified sources, the build recipe and LGPL notices. New compatibility code
and build material in `audio-compat/` use LGPL-2.1-or-later. The remaining
project-owned launcher code keeps GPL-3.0-only.

The complete matching source archive is included in each app under
`Contents/Resources/audio-compat/` and is exported beside its installer. The
launcher source ZIP contains the overlay and recipe; it does not replace that
complete library-source archive. Keep both forms of corresponding source and
their notices with distributed artifacts. See [component notices](../audio-compat/README.md)
and [release checks](RELEASING.md#audio-component-checks-for-beta7-and-later).

This records the reviewed source/distribution arrangement, not a blanket legal
clearance or evidence of compatibility on every Mac.
