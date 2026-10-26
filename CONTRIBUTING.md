# Contributing

Origins Launcher is a small native interface and controller for an independently
installed game. Changes should preserve that boundary and existing user data.

## Bug reports and security

Use the [bug report form](https://github.com/Dr-Smth/OriginsLauncher/issues/new?template=bug_report.yml)
for setup or runtime problems, and the
[compatibility report form](https://github.com/Dr-Smth/OriginsLauncher/issues/new?template=compatibility_report.yml)
to share tests on another Mac or display. While this repository is private, these
forms are available only to people with repository access.

Check [Troubleshooting](docs/TROUBLESHOOTING.md) first. Include the launcher version,
Mac and macOS version, Steam game edition, steps to reproduce and observed result.
For display problems, include the display, resolution, mode and UI size. The
launcher's Diagnostics button creates a local summary: review and redact it before
sharing. Do not attach a complete environment, raw account files or saves.

For vulnerabilities, follow [Security](SECURITY.md) instead of opening a bug report.
The editable [installer copy catalogue](docs/INSTALLER-COPY.md) contains the
project-owned setup wording and source references for proposed text changes.

## Development

Follow [Building](docs/BUILDING.md). Run the focused tests for the code you change,
then the full source test suite. Describe the concrete problem, resulting
behaviour and validation in your contribution. Include your Mac model, macOS
version, runtime version and game edition when they affect a compatibility fix.

Keep download URLs, versions and checksums explicit. Dependency updates need
licence/provenance review and actual runtime testing; passing parser tests is not
proof that the game renders correctly. Scope process shutdown to this launcher's
own environment. Back up display settings before editing them and refuse changes
while the game or an installer is active.

## What belongs in a contribution

Contribute code and documentation you have the right to share under the project's
**GNU GPL version 3 only** (`GPL-3.0-only`) licence. Intentionally submitted code
and documentation contributions for inclusion in this project are offered under
that licence unless explicitly agreed otherwise before acceptance. Contributors
retain their copyright; no copyright assignment or separate commercial-relicensing
permission is assumed. Identify adapted third-party code, preserve its notices
and explain the applicable licence. AI-assisted contributions need the same human
review, provenance checks and testing as other changes.

Artwork is handled separately under [Artwork rights](ARTWORK.md). Do not submit
another person's logo or images under the code licence without their permission.
The planned artist-supplied logo is excluded from the code grant and is not yet
included. A fork must use its own authorised assets or the licensed fallback when
the artist's terms do not permit reuse.

Commercial use and sale of GPL-compliant code are permitted without paying the
maintainer. Distributed covered derivatives must meet GPL v3's obligations,
including corresponding source; private work need not be published and there is
no obligation to contribute it upstream. See [Licensing](LICENSING.md).

Do not submit game files, Steam files, account data, saves, prepared Wine prefixes,
proprietary installers, DLLs, registry dumps or raw logs. Use synthetic fixtures
for tests. Review diagnostic summaries before attaching them, and redact account
names and local paths.

No bypasses for game ownership, authentication or DRM, and no instructions to
disable macOS security protections. Use the official download and launch paths.

## Compatibility reports

Report picture, mouse alignment, hover/click behaviour, UI readability, audio and
save/reload separately. Clearly distinguish direct observation from another
person's report. Use a new test character and save when appropriate; do not
overwrite a player's existing progress. See [Compatibility](docs/COMPATIBILITY.md)
for the current evidence and outstanding checks.
