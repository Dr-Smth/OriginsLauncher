# Origins Launcher

An unofficial macOS launcher for **Dragon Age: Origins**.

It runs Steam and the game through Wine, without a Windows install/VM. The native app handles setup, launch and display settings.

**[Download Origins Launcher for Apple Silicon](https://github.com/Dr-Smth/OriginsLauncher/releases/download/v0.2.0-beta.7/OriginsLauncher-0.2.0-beta.7-arm64-UNSIGNED-BETA.dmg)**

This is an unsigned beta. macOS may block the first launch; follow the
[Open Anyway instructions](docs/TROUBLESHOOTING.md#macos-will-not-open-a-downloaded-app)
if you trust the download.

[Release notes and known limitations](https://github.com/Dr-Smth/OriginsLauncher/releases/tag/v0.2.0-beta.7)
· [Launcher source ZIP](https://github.com/Dr-Smth/OriginsLauncher/releases/download/v0.2.0-beta.7/OriginsLauncher-0.2.0-beta.7-source.zip)
· [SHA-256 checksums](https://github.com/Dr-Smth/OriginsLauncher/releases/download/v0.2.0-beta.7/SHA256SUMS.txt)
· [Audio component source](https://github.com/Dr-Smth/OriginsLauncher/releases/download/v0.2.0-beta.7/origins-audio-1.0.0-beta.1-source.tar.gz)

## The App

<img width="800" alt="Origins Launcher showing launch status, display mode, UI size and resolution controls" src="https://github.com/user-attachments/assets/fcab7f38-e4fd-4fab-83de-f93466d44989" />

https://github.com/user-attachments/assets/c6285d07-e5aa-4b58-be90-90414610729a

<details>
<summary>Demo credits</summary>

Music: “Ascending the Vale” by Kevin MacLeod ([incompetech.com](https://www.incompetech.com/music/royalty-free/index.html?isrc=USUAN1600064)), licensed under [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/). Edited for length, volume and fades.

Opening and closing icon artwork by **Aberrant Ink**; see [artwork terms](ARTWORK.md). Artwork, music and game footage retain their respective rights and are not covered by the launcher's GPL licence.

</details>

## What you need

- An Apple Silicon Mac running macOS 26 or 27, with Rosetta available.
- A Steam licence for Dragon Age: Origins or Ultimate Edition. The EA app edition
  is not supported by this launcher (this may change in a future release).
- An internet connection for setup, Steam sign-in and your game download.
- At least 30-35GB of free storage to install the launcher, game, and dependancies.

The built app includes its own Python interpreter. Players do not need Xcode,
Homebrew, a system Python installation or a Windows licence to install the
launcher. Third-party software remains subject to its own terms.

## Start playing

1. Download the installer above, open the disk image, then drag **Origins Launcher.app**
   to Applications and open it.
   For an **UNSIGNED-BETA** download, macOS may initially block opening it. If you
   trust the release, follow the [per-app approval steps](docs/TROUBLESHOOTING.md#macos-will-not-open-a-downloaded-app).
2. Choose **Set up & open Steam**. It downloads the pinned compatibility runtime
   from Sikarugir's official releases and the Steam installer from Valve. Follow
   any macOS Rosetta prompt and review the terms presented by the installers.
3. Sign into the Windows Steam window. Choose the edition you own and download it
   in that window.
4. Let Steam finish the download and prerequisite installers. If **Finish game
   setup** appears, use it, save the settings in the game's configuration window,
   then close that window.
5. Choose **Play Dragon Age: Origins**, the official Dragon Age launcher will open,
   click **Play** and your game will launch. 

**NB** The native macOS Steam client is separate: downloading there does not install
the Windows game into this environment. Steam updates can take several minutes
and may restart the client. Keep Origins Launcher open while setup runs. It can
follow a completed updater's exit and reopen Steam, with a limited number of
attempts; if startup pauses, follow the status message and use **Open Steam**.

## Picture and interface size

Start with a display preset that fits the current screen. The launcher offers
fullscreen (it will only show resolutions that match your detected display) and windowed choices and can keep the HUD readable at higher rendering
resolutions with the optional **DAFix** UI-scaling extension.

Save and quit the game before changing display settings. See
[Display settings](docs/DISPLAY.md) for Retina, UI size and recovery guidance.
**Do not** change resolution in game, as this can break things.

## Audio and memory support

Beta.7 includes automatic DA:O-only audio compatibility for supported game and
runtime versions, aimed at reducing crackling and repeated dialogue.
Optional **4 GB memory support** in the launcher lets DA:O use a larger address space without changing the Steam game executable.

See [Audio compatibility](docs/AUDIO.md) for scope and current limitations.

## Your saves/files

Game data is stored under `~/Library/Application Support/OriginsLauncher`, outside
the app. Updating or removing the app does not by itself delete saves. Install
a newer app build to receive updates, including new icons; installed copies do
not update automatically. Use **Files** to find the environment and
[back up your saves](docs/DATA.md).

**Diagnostics** creates a local summary; the launcher does not upload it.
Sign-in stays in Steam. See [Privacy and data](docs/DATA.md) and
[Troubleshooting](docs/TROUBLESHOOTING.md).

## Why this exists

I’d been feeling pretty nostalgic for Dragon Age and wanted to revisit Origins, it’s one of my all time favourite games, and the RPG that got 16yo me into RPGs.

Only issue is I was away from my home for an extended period and only had my Mac with me. Turns out DA:O doesn’t run natively on Apple Silicon (makes sense it’s 17yo at this point), and I really didn’t want to have to run it via Windows on a VM.

So, I created a native macOS launcher for it (with a lot of help from Codex). Since it’s actually working I thought I’d share it with you all in case it lets anyone else scratch that nostalgia itch.

## Build or contribute

Use the [bug and compatibility report forms](https://github.com/Dr-Smth/OriginsLauncher/issues/new/choose)
for feedback, or follow [Security](SECURITY.md) for confidential vulnerability
reports. The
[installer copy catalogue](docs/INSTALLER-COPY.md) includes the project-owned
setup screens, disclosures, buttons and status/error text for wording reviews.

On an Apple Silicon Mac with Xcode command-line tools and Python 3, first build
the audio component using [Building](docs/BUILDING.md#audio-component-build).
Then run from the repository root:

```sh
bash source/build.sh "$PWD/../Origins Launcher.app"
python3 -B -m unittest discover -s source/tests -v
```

This creates an ad-hoc-signed app for local testing. The build fetches a pinned
Python distribution; setup later fetches the Wine runtime and Steam. See
[Building](docs/BUILDING.md), [Contributing](CONTRIBUTING.md) and the
[release checklist](docs/RELEASING.md).

The current project-owned code and documentation are **open source under
[GNU GPL version 3 only](LICENSE)** (`GPL-3.0-only`). Commercial use and selling
copies are allowed without a separate paid licence. When distributing covered
modified or derivative versions, preserve the GPL freedoms and provide the
corresponding source as the licence requires. Private modifications need not be
published, and contributors are not required to send changes back to this
project. See [Licensing](LICENSING.md).

Logo artwork by **Aberrant Ink** has separate rights and is not part of the GPL
grant. From beta.6, anyone may use official builds, including for business use,
and share them unchanged free of charge while preserving the artist's notice.
Selling copies containing the artwork requires separate permission. Separate
logo reuse and inclusion in modified or independently built forks also need the
artist's permission. This public repository and the audited source ZIP omit the
restricted images and build with the GPL fallback icon. Beta.5 retains its original artwork terms;
these changes do not retrospectively revoke earlier permissions. See
[Artwork](ARTWORK.md) and [Building](docs/BUILDING.md#official-artwork-builds).
[Third-party components](THIRD_PARTY.md) keep their own licences. The repository
does not contain the game, Steam client, a prepared Wine environment or account
data. The [licensing review](docs/LICENSING_REVIEW.md) records these boundaries and
remaining distribution checks.

This repository starts with a clean GPL source snapshot. Earlier private history,
artwork source images and beta.3–beta.5 downloads remain in the private maintenance
repository; earlier permissions are not revoked. The beta.6 installer and its
matching source ZIP are preserved unchanged. The documentation on `main` includes
later publication guidance, so use the release's source ZIP when checking the
exact source shipped with that installer. See the [release record](docs/RELEASE_STATUS.md).

This project is not endorsed by or affiliated with EA or its licensors, BioWare,
Valve, Apple, Sikarugir or the Wine project. Product names identify compatibility
and remain the trademarks of their respective owners.

