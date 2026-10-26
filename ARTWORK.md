# Artwork rights

The code licence does not automatically license every logo or image associated
with this project. The code and documentation are GPL-3.0-only; the logo below has
separate terms.

## Aberrant Ink logo

Copyright 2026 **Aberrant Ink**. All rights reserved except for the permissions
below. The artist retains copyright in the supplied dragon logo and its
renditions in the app icon. The original launcher background and fallback
renderer retain their existing code licence.

These terms apply to **0.2.0-beta.6 and later official builds** that include this
notice (terms version `2026-10-26-beta6`). On 26 October 2026, David Richard Smith
confirmed Aberrant Ink's approval of this revised scope:

- David Richard Smith may include the logo, rendered in the required icon sizes,
  in official Origins Launcher builds.
- Anyone may install, run and display the logo as part of an unchanged official
  build, including for business use, and share that build unchanged **free of
  charge**. Preserve the artwork notice supplied with it.
- Selling copies containing this artwork requires separate permission from
  Aberrant Ink. This is a condition on the artwork, not a ban on commercial use
  of the app or on selling the GPL-covered software without this artwork.
- Separate use of the logo, changes to the artwork, or including it in a modified
  or independently built fork requires separate permission from Aberrant Ink.

These terms cover the artwork embedded in unchanged official builds. They do not
place additional conditions on the GPL-covered code, or limit uses permitted by
applicable law. GPL obligations still apply when distributing the code, including
providing corresponding source through an allowed method. A modified launcher
can use the GPL fallback or other artwork it has permission to use, and may be
sold in compliance with the GPL and any other applicable component licences.

This record does not grant separate promotional, merchandise or trademark rights.
The artist's private contact details and permission correspondence are not part
of the public source package.

## Source assets and fallback

The original artwork is held in the private maintenance repository:

- `branding/aberrant-ink/dragon-logo.png` — the supplied original image.
- `branding/aberrant-ink/app-icon.png` — its preview over the existing background.
- `branding/aberrant-ink/NOTICE.txt` — the asset-specific rights notice.

The two PNGs are **excluded from the GPL grant, this public repository and the
audited release source ZIPs**. GitHub-generated archives of this public repository
therefore do not include them either. The public source retains the notice and
all code needed to build the launcher with its original fallback icon.
`source/Icon.swift` and its original fallback output follow the code licence for
their release; earlier MIT copies retain their existing permissions.

Official artwork builds include an `OFFICIAL-ARTWORK.json` record identifying the
artwork and its terms, plus the artist's notice. See
[Building](docs/BUILDING.md#official-artwork-builds).
The private maintenance repository preserves the earlier history and packages.
Frozen beta.4 packages use the fallback and remain unchanged. Beta.5 introduced
the official Aberrant Ink icon under its original terms, which expressly allowed
redistribution of unchanged official builds **including sale**. Beta.5 artifacts
and their embedded terms remain unchanged; this revision does not withdraw
permissions already granted with those copies. It does not claim that a recipient
with a separate or earlier permission loses it.

Installing the newer app updates its icon and bundled notices; older installed
copies do not update automatically. See [Licensing](LICENSING.md).

## Local custom artwork

`DAO_CUSTOM_LOGO_PATH` and `DAO_CUSTOM_LOGO_CREDIT` also support authorised local
experiments. Without the explicit official-artwork mode, the app receives a
`LOCAL-ARTWORK.json` marker and the release packager refuses it. This prevents an
arbitrary custom image from silently acquiring the official logo's permissions.

The build retains the current icon background and does not copy the original
image or its private filesystem path into the app. See the
[local build instructions](docs/BUILDING.md#local-custom-artwork).
