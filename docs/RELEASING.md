# Releasing

There are three app packaging modes: local preview, an explicitly labelled
unsigned beta, and a Developer ID-signed, notarized release. A source release can
be made separately. Publishing source or building a package does not establish
that the app has passed the fresh-install checks below.

The current beta is **0.2.0-beta.6**, app version `0.2.0`, build `6`.
It updates Aberrant Ink’s separately licensed artwork terms: unchanged official
builds may be shared free of charge; sale of copies containing the artwork needs
separate permission. GPL code may still be sold with the fallback or other
permitted artwork. See [Artwork](../ARTWORK.md). Keep frozen beta.3, beta.4 and
beta.5 packages and their supplied permissions intact.
Use a fresh output directory, freeze the source ZIP, and place final validation
results and checksums beside the artifacts; do not edit an archive to include
its own hash.

## Public source and release boundary

[Dr-Smth/OriginsLauncher](https://github.com/Dr-Smth/OriginsLauncher) starts with a
clean GPL source snapshot. The separate private maintenance repository retains
the earlier Git history, restricted artwork PNGs and beta.3–beta.5 releases.
Do not import that history or copy its raw artwork into the public repository.
The user-facing beta.6 download consists of the already validated, unchanged
installer and its exact matching source ZIP, notices, manifest and checksums.

The frozen `SOURCE-REVISION.txt` identifies the original private build commit;
it is provenance, not a promise that readers can access that private commit.
The attached source ZIP supplies the corresponding code without requiring access
to the maintenance repository. The public `main` documentation is maintained
separately and is not byte-identical to the frozen source ZIP. GitHub-generated
source archives also need not match that audited ZIP. Preserve the original
artifacts and record later publication checks separately on the release page.

Before inviting testers, verify delivery to the contact in [Security](../SECURITY.md),
enable GitHub private vulnerability reporting, and check the bug/compatibility
forms. Verify the reporting feature in GitHub itself rather than treating the
policy file as proof it is enabled. The Actions workflow remains manual; review
runner availability and account settings before starting or changing it.

Historical beta.3 fresh installation, gameplay, save/reload and Retina UI scaling
passed on one Mac. The exact beta.4 app/package checks and the user's downloaded,
copied-to-Applications **Open Anyway** test also passed on that Mac. See
[Release validation](RELEASE_STATUS.md) for the scope and remaining coverage.
A public-host download and another Mac/account are not established by those
tests. Audit beta.6 separately; disclose that its downloaded-app approval flow
has not been repeated unless an exact-artifact test is recorded. Keep prior
gameplay evidence separate from new smoke or gameplay results.

The current repository uses **GNU GPL version 3 only** (`GPL-3.0-only`) for
project-owned work. The code is open source and commercial use is allowed.
Distributed covered derivatives must preserve GPL freedoms and supply
corresponding source as required. See [Licensing](../LICENSING.md) and
[Artwork](../ARTWORK.md) for the separately reserved artwork boundary.

The beta.3 archives predate this change and retain their supplied MIT terms.
Keep those audited archives/checksums intact; do not relabel them as GPL or
claim their tests verified a new build. Existing MIT permissions cannot simply
be withdrawn. Review the source snapshot, Git history, tags and download assets
together for every publication. Earlier MIT-licensed code remains usable under
its earlier terms by those who received it. Its history remains preserved in
the private maintenance repository; the clean public snapshot does not revoke
earlier permissions or require deleting historical evidence.

The current repository docs also include checks completed after the beta.3
archives were frozen. Identify the exact source snapshot and licence associated
with every release; do not imply that a GitHub-generated archive of later source
is byte-identical to the frozen source ZIP. Use a new version and repeat the
package checks when producing a new distributable under the current terms.

## Source release

- Export an explicit allowlist of project source, synthetic tests, scripts,
  documentation, `LICENSE`, `LICENSING.md`, `ARTWORK.md` and the
  dependency manifest.
- Exclude builds, caches, `runtime/`, `data/`, `downloads/`, prepared prefixes,
  account files, registry dumps, saves, logs, screenshots, personal validation
  records, private runtime references and signing material.
- Scan the actual archive and any published Git history for private paths,
  credentials, tokens, account identifiers and proprietary payloads. `.gitignore`
  does not remove files already in history.
- Preserve authorship/licence notices and verify that every contribution can be
  released under its stated licence. Follow [Contributing](../CONTRIBUTING.md)
  before accepting outside code; contributions must be available on terms
  compatible with distribution of the covered work under GPL-3.0-only.
- Preserve the separate Aberrant Ink artwork notice. Its confirmed permission
  covers use and free-of-charge redistribution of unchanged official builds
  from beta.6. Selling copies containing the artwork needs separate permission.
  Reserved images are excluded from the source ZIP; the default GPL fallback
  remains buildable. Confirm appropriate rights before adding different artwork.
- Run the tests and build from this clean export. Document the tested revision,
  platform and limitations without transferring a personal verification record.

## App contents and dependency review

The app should contain only our executables/resources, the pinned Python
distribution and the associated notices. It must not contain the game, Steam,
Sikarugir template/engine, a Wine prefix, repair installers or a signed-in session.
Those are obtained separately on the recipient's Mac.

Check the exact Python archive's licences and retained notices before each
dependency update. Keep source URLs, versions, sizes and SHA-256 values in
`dependency-manifest.json`. Retain upstream licence files when preparing the app.
Hash verification establishes identity/integrity, not that an artifact is safe
or that redistribution is permitted.

The Sikarugir runtime is a mixed-licence upstream dependency. Do not add it to
our download for convenience without a separate redistribution review. In
particular, upstream's non-LGPL launcher components and proprietary D3DMetal are
not relicensed by the project's GPL licence. See
[Third-party components](../THIRD_PARTY.md).

Check that the final app contains the current project licence, its scope and
artwork notices alongside all dependency notices. The
current policy documents do not retrospectively change the frozen MIT beta.3
app. Official beta.6 artwork builds use the explicit build mode documented in
[Building](BUILDING.md); arbitrary local custom-art builds cannot be packaged.
Do not add the separately reserved raw PNGs to a public source download.

For a distributed GPL app, provide the complete corresponding source for the
covered work through an applicable GPLv3 section 6 method. For project downloads,
publish the exact matching source alongside the app with clear download links;
retain required build/installation scripts and notices. A generic link to a
moving default branch is not a substitute for the corresponding source of the
binary being distributed. Independent programs distributed alongside it keep
their own applicable obligations; GPL does not relicense the game or Steam.

## Test the recipient's installation

Verify the core functional path in an isolated fresh environment: setup
disclosures, runtime download, Steam installation/sign-in, game download,
prerequisites, configuration, actual gameplay, audio and save/reload after
relaunching through the app. Keep the original environment and saves separate.
Record which results were observed by a tester and which are automated checks.

Broaden coverage on a separate Mac without developer tools or preinstalled
Python, including a missing-Rosetta path, optional UI scaling and other hardware
and displays. Untested cases can be disclosed beta limitations; do not represent
them as verified or treat every coverage gap as a legal distribution condition.

Re-exercise Steam's real multi-update startup sequence when changing its recovery
logic. Unit tests alone do not establish that updater handoffs work in practice.
Check the retry limit, clear paused/expired messages and cancellation when the
launcher closes, while preserving running installers, downloads and games. If
the real sequence has not been repeated, disclose that limitation alongside the
unit-test results.

Also test ordinary app replacement with existing saves, paths containing spaces,
unavailable network, failed hash validation and an interrupted setup. Preserve
the prior environment when any of these fail. Confirm diagnostics remain local
and do not include account data. Record results in a release-specific report.

## Sign, notarize and verify

Developer ID signing and notarization are recommended for the regular app
release. They are not a prerequisite for distributing a clearly labelled
unsigned beta after the installation and package checks pass. An unsigned beta
has an ad-hoc integrity signature, but no Apple-verified publisher identity or
notarization ticket. Do not describe it as signed by an identified developer or
checked by Apple's notarization service.

For the regular release, use an Apple Developer ID Application certificate
and the hardened runtime, then pass Apple's notarization service. The Python
interpreter, native extensions and other nested executable code need correct
signing before the enclosing app is sealed. Apply only entitlements needed by
the tested build. Keep signing keys and notary credentials outside the repository.

Use Apple's documented Xcode or `notarytool` workflow, staple the resulting ticket
to the distributable as appropriate, and verify the final package on a clean Mac
under normal Gatekeeper settings. A successful local `codesign --verify` is not
evidence of notarization. Do not remove quarantine or disable Gatekeeper as a
release workaround.

References: [Developer ID](https://developer.apple.com/developer-id/),
[notarization](https://developer.apple.com/documentation/security/notarizing-macos-software-before-distribution),
and [macOS code signing](https://support.apple.com/guide/security/sec3ad8e6e53/web).

No paid developer membership, certificate or notarization result is supplied by
this source project. A maintainer supplies their own distribution identity for
the signed release. A paid account is not required for the unsigned-beta path.

## Unsigned-beta installation check

Test the actual downloaded unsigned-beta package under normal Gatekeeper settings.
After the first attempt to open the app, a recipient who trusts the release may
use **System Settings → Privacy & Security → Open Anyway**, then confirm **Open**.
This creates an exception for the app. Follow
[Apple's current guidance](https://support.apple.com/en-gb/102445); managed Macs
may restrict this option. Do not promise that every Mac can open an unsigned app.

The release page and the disk image must identify the build as **UNSIGNED-BETA**,
explain that it lacks Developer ID signing and notarization, and link to the
per-app approval instructions. Publish the checksum alongside the download.
Do not advise disabling Gatekeeper, deleting quarantine attributes or overriding
a malware/damaged-app warning. Investigate those messages instead.

## Package and publish

From the source root, create a source-only ZIP in a new directory outside the
source tree:

```sh
python3 -B scripts/package_release.py --output "$PWD/../release-source"
```

To add a single-app disk image for local preview after building the app:

```sh
python3 -B scripts/package_release.py \
  --app "$PWD/../Origins Launcher.app" \
  --output "$PWD/../release-preview"
```

With neither release flag, the image is explicitly named `LOCAL-PREVIEW` and
contains a local-testing notice. Packaging never uploads files.

After the core functional checks pass, prepare an unsigned-beta package
explicitly, then audit the exact artifacts and test normal Gatekeeper opening
before distributing them. Publish the remaining test limitations with it:

```sh
python3 -B scripts/package_release.py \
  --app "$PWD/../Origins Launcher.app" \
  --output "$PWD/../release-unsigned-beta" --unsigned-beta
```

This mode retains integrity verification, source auditing and dependency notices.
It labels the disk image **UNSIGNED-BETA** and includes the macOS approval
instructions. It does not provide a Developer ID identity or notarization.

For a signed, notarized app, first use `scripts/sign_release.py --app PATH --identity ID`
with your Developer ID Application identity, complete Apple's notarization
workflow and staple the app's ticket. Then package into another new directory:

```sh
python3 -B scripts/package_release.py \
  --app "$PWD/../Origins Launcher.app" \
  --output "$PWD/../release-public" --public
```

The `--public` mode specifically requires a Developer ID Application signature,
successful `stapler validate` and Gatekeeper acceptance. It refuses an ad-hoc app.
It is mutually exclusive with `--unsigned-beta`; neither flag skips the release
checklist. The source audit runs for every mode; outputs inside the source tree
are refused.
Inspect the resulting ZIP or disk image, not only the input directory.
Publish the version, source revision, dependency pins, release notes, limitations,
test report and final archive SHA-256 together.

Use distinct Origins Launcher branding with a descriptive compatibility line.
Do not use official logos or imply that this is an EA-approved Mac port. EA's
[content policy](https://help.ea.com/en/articles/security-and-rules/ea-content-policy/)
does not grant a general licence to redistribute the game or merge its branding
with this project's identity.

Configure and verify the issue tracker and a private security-reporting channel
before inviting testers. Use the repository's [contribution guide](../CONTRIBUTING.md)
and [security policy](../SECURITY.md) for the actual reporting routes; do not
assume a host feature is enabled merely because a policy file exists. Never ask
testers to post credentials, Steam account data, saves or unreviewed full logs.

For a public launch, publish only the authorized clean source and release scope.
Verify the public issue/security routes, publish release notes and checksums
with the exact audited artifacts, then download the public-hosted disk image
without signing in and check its hash. Do not make the private maintenance
repository public as a shortcut. Record host-specific checks separately from
the immutable package-validation record.
