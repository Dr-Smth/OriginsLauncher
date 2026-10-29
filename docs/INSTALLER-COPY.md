# Launcher and installer copy catalogue

Copy snapshot: **0.2.0-beta.6** release-candidate source, 26 October 2026. The About/help and packaging text below includes the GPL notice changes retained from beta.4; they are not present in the frozen MIT beta.3 app or disk image. This is an editable review copy of the project-authored wording; editing this catalogue does not change the application. Send amendments by section and source reference, and update the corresponding source when wording is approved.

## Scope and reading guide

- The main sections follow installation and first use, including the pre-Steam screen, dependency and licence disclosures, optional UI scaling, normal controls, progress text and help. The appendices include authored status messages and failure copy that can be returned by the bundled controller.
- Text is transcribed from the current source. Curly placeholders such as `{log.name}` represent dynamic Python values. Swift placeholders are preserved as `\(expression)`; those expressions are replaced by a value at runtime and are not printed literally. Links are listed with their exact destination.
- Source references are relative to the repository root and describe this snapshot; line numbers may move after edits. Repeated text can appear in several conditions. Some backend entries are diagnostic or command-line-only; they are marked separately from the native screen copy.
- The Apple Gatekeeper/Rosetta dialogs, Windows Steam setup/sign-in/update screens, Steam Guard, game agreements, Microsoft Visual C++/DirectX, NVIDIA PhysX, and the official EA/BioWare game launcher/configuration screens belong to their publishers. Their wording is not controlled by this project and has **not** been invented or extracted here. The same applies to standard macOS menu items and system-generated error descriptions.
- **Project license** opens [`LICENSE`](../LICENSE); **Licensing overview** opens [`LICENSING.md`](../LICENSING.md); **Artwork rights** opens [`ARTWORK.md`](../ARTWORK.md); **Third-party notices** opens [`THIRD_PARTY.md`](../THIRD_PARTY.md). These are maintained separately. This catalogue is not a substitute for their legal text.

## Contents

- [Disk-image instructions](#1-disk-image-installation-start-heretxt)
- [Pre-Steam setup screen and terms](#2-first-screen-before-runtime-and-steam-installation)
- [Setup progress and Steam handoff](#3-setup-action-and-steam-handoff)
- [Steam sign-in and edition selection](#4-steam-sign-in-and-game-edition)
- [First-time game setup](#5-first-time-game-prerequisites-and-configuration)
- [Display controls and optional UI scaling](#6-display-settings-and-optional-ui-scaling)
- [Play, status, utilities and About](#7-play-action)
- [Controller messages and diagnostics](#appendix-a-controller-messages-and-diagnostics)

## 1. Disk-image installation: START HERE.txt

The current source generates the following complete text for a new unsigned-beta disk image. The frozen beta.3 disk image predates the added licensing paragraph and has not been repackaged. Source: [`scripts/package_release.py:22`](../scripts/package_release.py#L22).

```text
UNSIGNED BETA — no Apple Developer ID signature or Apple notarization.
This beta may have a local ad-hoc signature for integrity; it does not identify an Apple-verified developer.
Install only if you trust the download and have checked its published checksum.

If macOS blocks this app, follow Apple’s per-app Open Anyway instructions:
https://support.apple.com/en-gb/102445
In System Settings > Privacy & Security, use Open Anyway for Origins Launcher, then review the confirmation.
Keep Gatekeeper enabled. Do not disable macOS security checks or remove the app’s quarantine attribute.
If Open Anyway is unavailable, follow Apple’s guidance or your Mac administrator’s policy.

Drag Origins Launcher to Applications, then open it.
Choose Set up & open Steam. Sign in to your own Steam account and install Dragon Age: Origins.
Return to the app and follow its first-game setup prompts.

Requires Apple Silicon and macOS 26 or 27; Rosetta may prompt for installation.
Unofficial. Not affiliated with EA, BioWare or Valve.

Launcher code is licensed under GNU GPL version 3 only; see LICENSE and LICENSING.md.
Artwork and third-party components have separate terms; see ARTWORK.md and THIRD_PARTY.md.
```

## 2. First screen: before runtime and Steam installation

The setup panel is shown when the compatibility environment, Windows Steam or a platform prerequisite still needs setup. Rosetta-specific controls appear only when Rosetta is missing. The exact text below includes all current disclosure and link labels.

**Heading** — [`source/Launcher.swift:802`](../source/Launcher.swift#L802)

> Play your Steam copy on this Mac

**Body** — [`source/Launcher.swift:803`](../source/Launcher.swift#L803)

> Origins Launcher is an unofficial Dragon Age: Origins launcher. Setup downloads a dedicated compatibility runtime (about 264 MB), then installs and opens Windows Steam. Steam updates and your game download are additional. A Steam copy of the game is required.

**Requirements** — [`source/Launcher.swift:805`](../source/Launcher.swift#L805)

> Requires Apple Silicon, macOS 26 or later, and Rosetta. No Windows installation, Terminal, or separate developer tools are needed.

**Button** — [`source/Launcher.swift:810`](../source/Launcher.swift#L810)

> Open Rosetta installer

**Link label** — [`source/Launcher.swift:813`](../source/Launcher.swift#L813)

> Apple Rosetta help

**Body** — [`source/Launcher.swift:816`](../source/Launcher.swift#L816)

> Complete Apple’s installer prompts, then choose Refresh. Origins Launcher does not accept Apple’s agreement for you.

**Licence disclosure** — [`source/Launcher.swift:820`](../source/Launcher.swift#L820)

> Review the runtime and Steam terms before setup. The Sikarugir download includes Apple’s separately licensed D3DMetal component; this launcher leaves it disabled. Installers may present their own agreements for you to review.

**Link label** — [`source/Launcher.swift:823`](../source/Launcher.swift#L823)

> Sikarugir terms

**Link label** — [`source/Launcher.swift:824`](../source/Launcher.swift#L824)

> Apple D3DMetal terms

**Link label** — [`source/Launcher.swift:825`](../source/Launcher.swift#L825)

> Steam terms

**Body** — [`source/Launcher.swift:827`](../source/Launcher.swift#L827)

> The game and runtime stay in your Application Support folder. Optional DAFix UI scaling can be enabled after installing the game.

**Link destinations**

| Link label | Destination |
|---|---|
| Apple Rosetta help | https://support.apple.com/102527 |
| Sikarugir terms | https://github.com/Sikarugir-App/Sikarugir#components-that-fall-under-lgpl-21-license |
| Apple D3DMetal terms | https://github.com/Sikarugir-App/Sikarugir/blob/main/D3DMetal/4.0/License.pdf |
| Steam terms | https://store.steampowered.com/subscriber_agreement/ |

## 3. Setup action and Steam handoff

The action button and progress label change as setup and Steam updates proceed. The app does not provide a Steam password or Steam Guard form; those belong to the separate Windows Steam window.

| Kind | Exact text | Source |
|---|---|---|
| Progress text | Continuing Steam startup… | [`source/Launcher.swift:373`](../source/Launcher.swift#L373) |
| Conditional text / template | Downloading and preparing the runtime and Steam. This can take several minutes. Keep Origins Launcher open and follow any installer windows that appear. | [`source/Launcher.swift:518`](../source/Launcher.swift#L518) |
| Text | Steam updates can take a few rounds. Startup continues automatically while this app is open, including when minimized. | [`source/Launcher.swift:744`](../source/Launcher.swift#L744) |
| Progress text | Setting up runtime &amp; Steam… | [`source/Launcher.swift:766`](../source/Launcher.swift#L766) |
| Button (conditional) | Steam setup is open | [`source/Launcher.swift:767`](../source/Launcher.swift#L767) |
| Button (conditional) | Set up &amp; open Steam | [`source/Launcher.swift:767`](../source/Launcher.swift#L767) |
| Progress text | Opening Steam download… | [`source/Launcher.swift:788`](../source/Launcher.swift#L788) |
| Button (conditional) | Waiting for Steam… | [`source/Launcher.swift:789`](../source/Launcher.swift#L789) |
| Button (conditional) | Download in Steam | [`source/Launcher.swift:789`](../source/Launcher.swift#L789) |
| Button | Opening Steam… | [`source/Launcher.swift:794`](../source/Launcher.swift#L794) |
| Button | Open Steam | [`source/Launcher.swift:794`](../source/Launcher.swift#L794) |

## 4. Steam sign-in and game edition

| Kind | Exact text | Source |
|---|---|---|
| Label | Your Steam edition | [`source/Launcher.swift:858`](../source/Launcher.swift#L858) |
| Control/accessibility label | Your Steam edition | [`source/Launcher.swift:859`](../source/Launcher.swift#L859) |
| Edition choice | Ultimate Edition | [`source/Launcher.swift:860`](../source/Launcher.swift#L860) |
| Edition choice | Original Edition | [`source/Launcher.swift:861`](../source/Launcher.swift#L861) |
| Body | Sign in to your own account in the Windows Steam window, then download your edition. Complete Steam Guard and any installer agreements there. | [`source/Launcher.swift:871`](../source/Launcher.swift#L871) |

## 5. First-time game prerequisites and configuration

After the game download, the launcher opens the supplied prerequisite installers and the official game configuration tool. Their own dialog copy is external; the project-authored instructions follow.

| Kind | Exact text | Source |
|---|---|---|
| Progress text | Opening first-time game setup… | [`source/Launcher.swift:778`](../source/Launcher.swift#L778) |
| Button (conditional) | Game setup is open | [`source/Launcher.swift:779`](../source/Launcher.swift#L779) |
| Button (conditional) | Finish game setup | [`source/Launcher.swift:779`](../source/Launcher.swift#L779) |
| Body | Choose Finish game setup, complete any supplied installers, then save your settings in the game’s configuration window and close it. Display controls appear once the configuration is ready. | [`source/Launcher.swift:868`](../source/Launcher.swift#L868) |

**Instruction after launching prerequisites** — [`source/game_setup.py:228`](../source/game_setup.py#L228)

> Complete the supplied VC++, PhysX and DirectX installer windows, reviewing their licenses. Then finish and close Dragon Age's configuration window. Steam may run its remaining first-launch setup when you press Play.

## 6. Display settings and optional UI scaling

The display name, dimensions and refresh rate come from the current display. Resolution rows are composed from the templates below. Disabled presets may append an authored reason from the backend appendix. The final UI offers no Apply/Keep/Restore buttons. Any such wording in the backend appendix belongs to support commands.

| Kind | Exact text | Source |
|---|---|---|
| Conditional text / template | &#92;(preset.width) × &#92;(preset.height) | [`source/Launcher.swift:637`](../source/Launcher.swift#L637) |
| Conditional text / template | Native · &#92;(dimensions) | [`source/Launcher.swift:639`](../source/Launcher.swift#L639) |
| Conditional text / template | Performance · &#92;(dimensions) | [`source/Launcher.swift:639`](../source/Launcher.swift#L639) |
| Conditional text / template | Unavailable on this display | [`source/Launcher.swift:640`](../source/Launcher.swift#L640) |
| Section heading | Display &amp; interface | [`source/Launcher.swift:646`](../source/Launcher.swift#L646) |
| Accessibility label | Reading display settings | [`source/Launcher.swift:650`](../source/Launcher.swift#L650) |
| Tooltip | Refresh connected displays | [`source/Launcher.swift:653`](../source/Launcher.swift#L653) |
| Label | Refresh connected displays | [`source/Launcher.swift:653`](../source/Launcher.swift#L653) |
| Text | &#92;(display.name) · &#92;(display.pixel_width) × &#92;(display.pixel_height) pixels | [`source/Launcher.swift:658`](../source/Launcher.swift#L658) |
| Conditional text / template |  · &#92;(Int(display.refresh_rate.rounded())) Hz | [`source/Launcher.swift:658`](../source/Launcher.swift#L658) |
| Label | Mode | [`source/Launcher.swift:665`](../source/Launcher.swift#L665) |
| Control/accessibility label | Display mode | [`source/Launcher.swift:666`](../source/Launcher.swift#L666) |
| Mode choice | Full screen | [`source/Launcher.swift:667`](../source/Launcher.swift#L667) |
| Mode choice | Windowed | [`source/Launcher.swift:668`](../source/Launcher.swift#L668) |
| Label | UI size | [`source/Launcher.swift:672`](../source/Launcher.swift#L672) |
| Control/accessibility label | UI size | [`source/Launcher.swift:673`](../source/Launcher.swift#L673) |
| UI-size choice | Comfortable | [`source/Launcher.swift:674`](../source/Launcher.swift#L674) |
| UI-size choice | Larger | [`source/Launcher.swift:675`](../source/Launcher.swift#L675) |
| Label | Resolution | [`source/Launcher.swift:679`](../source/Launcher.swift#L679) |
| Control/accessibility label | Resolution | [`source/Launcher.swift:680`](../source/Launcher.swift#L680) |
| Resolution choice (disabled) | No available resolution | [`source/Launcher.swift:682`](../source/Launcher.swift#L682) |
| Body | Optional UI scaling adds the DAFix mod for a larger, readable interface and Retina display presets. It is downloaded only when you enable it. | [`source/Launcher.swift:693`](../source/Launcher.swift#L693) |
| Button | Enable UI scaling | [`source/Launcher.swift:696`](../source/Launcher.swift#L696) |
| Progress text | Installing optional UI scaling… | [`source/Launcher.swift:697`](../source/Launcher.swift#L697) |
| Link label | DAFix release &amp; license | [`source/Launcher.swift:699`](../source/Launcher.swift#L699) |
| Progress text | Reading your display and available resolutions… | [`source/Launcher.swift:705`](../source/Launcher.swift#L705) |
| Body | Display settings are not available yet. Refresh to try again. | [`source/Launcher.swift:707`](../source/Launcher.swift#L707) |

The **DAFix release & license** link points to `https://github.com/Lyall/DAFix/releases/tag/v0.0.3`.

Composed display line: `\(display.name) · \(display.pixel_width) × \(display.pixel_height) pixels`, optionally followed by ` · \(Int(display.refresh_rate.rounded())) Hz`. A disabled resolution appends ` — ` and its reason.

## 7. Play action

| Kind | Exact text | Source |
|---|---|---|
| Progress text | Starting game… | [`source/Launcher.swift:782`](../source/Launcher.swift#L782) |
| Button (conditional) | Game running | [`source/Launcher.swift:783`](../source/Launcher.swift#L783) |
| Button (conditional) | Play Dragon Age: Origins | [`source/Launcher.swift:783`](../source/Launcher.swift#L783) |

## 8. Main window branding and status card

Only the heading for the current state is displayed. The game title may be supplied by the installed Steam edition; the possible titles are listed in the backend catalogue.

| Kind | Exact text | Source |
|---|---|---|
| Status heading | Checking your setup | [`source/Launcher.swift:313`](../source/Launcher.swift#L313) |
| Status heading | Finish environment setup | [`source/Launcher.swift:314`](../source/Launcher.swift#L314) |
| Status heading | Your adventure is running | [`source/Launcher.swift:315`](../source/Launcher.swift#L315) |
| Status heading | This Mac is not supported | [`source/Launcher.swift:317`](../source/Launcher.swift#L317) |
| Status heading | Rosetta is required | [`source/Launcher.swift:318`](../source/Launcher.swift#L318) |
| Status heading | Ready to set up | [`source/Launcher.swift:319`](../source/Launcher.swift#L319) |
| Status heading | Finish game setup | [`source/Launcher.swift:320`](../source/Launcher.swift#L320) |
| Status heading | Complete the game setup window | [`source/Launcher.swift:321`](../source/Launcher.swift#L321) |
| Status heading | Complete Steam setup | [`source/Launcher.swift:322`](../source/Launcher.swift#L322) |
| Status heading | Continuing Steam setup | [`source/Launcher.swift:323`](../source/Launcher.swift#L323) |
| Status heading | Steam startup paused | [`source/Launcher.swift:324`](../source/Launcher.swift#L324) |
| Status heading | Steam is updating | [`source/Launcher.swift:325`](../source/Launcher.swift#L325) |
| Status heading | Steam is starting | [`source/Launcher.swift:326`](../source/Launcher.swift#L326) |
| Status heading | Steam needs a restart | [`source/Launcher.swift:327`](../source/Launcher.swift#L327) |
| Status heading | Downloading your game | [`source/Launcher.swift:328`](../source/Launcher.swift#L328) |
| Status heading | Ready to launch | [`source/Launcher.swift:331`](../source/Launcher.swift#L331) |
| Status heading | Sign in and download your game | [`source/Launcher.swift:332`](../source/Launcher.swift#L332) |
| Status heading | Prepare your game environment | [`source/Launcher.swift:333`](../source/Launcher.swift#L333) |
| Accessibility label | Refreshing status | [`source/Launcher.swift:732`](../source/Launcher.swift#L732) |
| Label | Compatibility runtime | [`source/Launcher.swift:736`](../source/Launcher.swift#L736) |
| Conditional text / template | Available | [`source/Launcher.swift:736`](../source/Launcher.swift#L736) |
| Conditional text / template | Not ready | [`source/Launcher.swift:736`](../source/Launcher.swift#L736) |
| Label | Windows Steam | [`source/Launcher.swift:737`](../source/Launcher.swift#L737) |
| Conditional text / template | Dragon Age: Origins | [`source/Launcher.swift:738`](../source/Launcher.swift#L738) |
| Conditional text / template | Running | [`source/Launcher.swift:738`](../source/Launcher.swift#L738) |
| Conditional text / template | Installed | [`source/Launcher.swift:738`](../source/Launcher.swift#L738) |
| Conditional text / template | Download through Steam | [`source/Launcher.swift:738`](../source/Launcher.swift#L738) |
| Brand text | ORIGINS | [`source/Launcher.swift:848`](../source/Launcher.swift#L848) |
| Brand text | Launcher | [`source/Launcher.swift:849`](../source/Launcher.swift#L849) |
| Window/dialog title | Origins Launcher | [`source/Launcher.swift:968`](../source/Launcher.swift#L968) |

## 9. Utilities, storage and stop confirmation

Storage totals and timestamps are dynamic. The full populated storage line is `{formatted storage size} · cached storage measurement`. The help string inserts ` Last measured: {timestamp}.` when available.

| Kind | Exact text | Source |
|---|---|---|
| Conditional text / template | Storage not measured yet | [`source/Launcher.swift:304`](../source/Launcher.swift#L304) |
| Conditional text / template | Storage measurement pending | [`source/Launcher.swift:305`](../source/Launcher.swift#L305) |
| Conditional text / template |  · cached storage measurement | [`source/Launcher.swift:306`](../source/Launcher.swift#L306) |
| Conditional text / template |  Last measured: &#92;($0). | [`source/Launcher.swift:309`](../source/Launcher.swift#L309) |
| Conditional text / template | Storage is measured during setup and when you create a diagnostic report; it is not a live total.&#92;(timestamp) Use Diagnostics to refresh it. | [`source/Launcher.swift:310`](../source/Launcher.swift#L310) |
| Tooltip | Dismiss | [`source/Launcher.swift:883`](../source/Launcher.swift#L883) |
| Button | Files | [`source/Launcher.swift:890`](../source/Launcher.swift#L890) |
| Button | Logs | [`source/Launcher.swift:891`](../source/Launcher.swift#L891) |
| Button | Diagnostics | [`source/Launcher.swift:892`](../source/Launcher.swift#L892) |
| Progress text | Collecting diagnostics… | [`source/Launcher.swift:892`](../source/Launcher.swift#L892) |
| Button | Refresh | [`source/Launcher.swift:893`](../source/Launcher.swift#L893) |
| Button | Stop session | [`source/Launcher.swift:895`](../source/Launcher.swift#L895) |
| Window/dialog title | Stop this game session? | [`source/Launcher.swift:911`](../source/Launcher.swift#L911) |
| Button | Cancel | [`source/Launcher.swift:912`](../source/Launcher.swift#L912) |
| Button | Stop session | [`source/Launcher.swift:913`](../source/Launcher.swift#L913) |
| Progress text | Stopping this session… | [`source/Launcher.swift:913`](../source/Launcher.swift#L913) |
| Confirmation body | This closes the game, Windows Steam, and compatibility processes in this launcher’s game environment. Save your progress first. Other Mac apps and other game environments are not targeted. | [`source/Launcher.swift:915`](../source/Launcher.swift#L915) |

## 10. Help menu and About dialog

**Help menu item** — [`source/Launcher.swift:974`](../source/Launcher.swift#L974)

> About this launcher

**Dialog heading** — [`source/Launcher.swift:976`](../source/Launcher.swift#L976)

> Origins Launcher

**About body** — [`source/Launcher.swift:977`](../source/Launcher.swift#L977)

> An unofficial Mac launcher for a Steam copy of Dragon Age: Origins that you own. BioWare, EA, Valve, Apple, and the compatibility-runtime maintainers are not affiliated with this project.
>
> Launcher code and documentation use GNU GPL version 3 only. See Licensing overview for source-sharing requirements and Artwork rights for separately licensed assets. The game, Steam, downloaded runtime and optional mods have separate licenses.
>
> Closing Origins Launcher cancels its automatic Steam startup follow-up and leaves the game and Steam running. Use Stop session to close this game environment.

**Help menu item** — [`source/Launcher.swift:980`](../source/Launcher.swift#L980)

> Project license

**Help menu item** — [`source/Launcher.swift:983`](../source/Launcher.swift#L983)

> Licensing overview

**Help menu item** — [`source/Launcher.swift:986`](../source/Launcher.swift#L986)

> Artwork rights

**Help menu item** — [`source/Launcher.swift:989`](../source/Launcher.swift#L989)

> Third-party notices

## 11. Native notifications, errors and remaining state labels

These labels and authored messages support the native window. The three `gameplayHint` strings at lines 284–288 are defined in the current source but are not referenced by the current view. The Rosetta-open failure prefix is followed by macOS’s error description.

| Kind | Exact text | Source |
|---|---|---|
| Error | The bundled controller is missing. Rebuild or restore the launcher app. | [`source/Launcher.swift:137`](../source/Launcher.swift#L137) |
| Error | The app’s resources are missing. Download a complete copy of Origins Launcher. | [`source/Launcher.swift:140`](../source/Launcher.swift#L140) |
| Error | The app’s bundled helper is missing or damaged. Download a complete copy of Origins Launcher; no separate Python installation is needed. | [`source/Launcher.swift:144`](../source/Launcher.swift#L144) |
| Error | Your Application Support folder could not be located. | [`source/Launcher.swift:147`](../source/Launcher.swift#L147) |
| Conditional text / template | The launcher is closing. | [`source/Launcher.swift:183`](../source/Launcher.swift#L183) |
| Error | This operation took too long. A Steam or setup window may still be open. Check that window, then refresh or create a diagnostic report before trying again. | [`source/Launcher.swift:222`](../source/Launcher.swift#L222) |
| Error | The controller did not return a valid response. Open the logs for details. | [`source/Launcher.swift:226`](../source/Launcher.swift#L226) |
| Conditional text / template | Sign in and download your owned copy in the Steam window. | [`source/Launcher.swift:284`](../source/Launcher.swift#L284) |
| Conditional text / template | Use Play to launch your installed copy. | [`source/Launcher.swift:287`](../source/Launcher.swift#L287) |
| Conditional text / template | Launch the game to test gameplay, audio, and save/load on this Mac. | [`source/Launcher.swift:288`](../source/Launcher.swift#L288) |
| Steam status detail | Installer open | [`source/Launcher.swift:293`](../source/Launcher.swift#L293) |
| Steam status detail | Continuing startup | [`source/Launcher.swift:294`](../source/Launcher.swift#L294) |
| Steam status detail | Startup paused | [`source/Launcher.swift:295`](../source/Launcher.swift#L295) |
| Steam status detail | Updating client | [`source/Launcher.swift:296`](../source/Launcher.swift#L296) |
| Steam status detail | Starting client | [`source/Launcher.swift:297`](../source/Launcher.swift#L297) |
| Steam status detail | Restart needed | [`source/Launcher.swift:298`](../source/Launcher.swift#L298) |
| Steam status detail | Running | [`source/Launcher.swift:300`](../source/Launcher.swift#L300) |
| Steam status detail | Installed | [`source/Launcher.swift:300`](../source/Launcher.swift#L300) |
| Steam status detail | Preparation needed | [`source/Launcher.swift:300`](../source/Launcher.swift#L300) |
| Error | Choose an available display preset before playing. | [`source/Launcher.swift:497`](../source/Launcher.swift#L497) |
| Conditional text / template | Operation completed. | [`source/Launcher.swift:530`](../source/Launcher.swift#L530) |
| Error | Apple’s Rosetta installer was not found. Use the Apple Rosetta help link, then refresh this launcher. | [`source/Launcher.swift:558`](../source/Launcher.swift#L558) |
| Conditional text / template | Apple’s Rosetta installer could not open:  | [`source/Launcher.swift:566`](../source/Launcher.swift#L566) |
| Conditional text / template | Complete the Apple Rosetta installer’s prompts, then choose Refresh. | [`source/Launcher.swift:567`](../source/Launcher.swift#L567) |
| Conditional text / template | This folder will be created when the game environment is prepared. | [`source/Launcher.swift:579`](../source/Launcher.swift#L579) |

## 12. App identity metadata

| Field | Exact text | Source |
|---|---|---|
| App name / display name | Origins Launcher | [`source/build.sh:44`](../source/build.sh#L44) |
| Copyright metadata | Copyright 2026 David Richard Smith and Origins Launcher contributors. Unofficial; not affiliated with EA, BioWare or Valve. | [`source/build.sh:55`](../source/build.sh#L55) |

## Appendix A. Controller messages and diagnostics

The following tables retain the authored literal wording, including technical errors. Not every line is shown in the native app: some are support-command responses or internal validation diagnostics. When the UI displays a controller error, it prefers the returned `message`; otherwise it may display the last 700 characters of the process error. Operating-system, network, decoding, filesystem and subprocess exceptions can add variable text that is not authored by this project.

`display-apply`, `display-restore` and `display-confirm` remain support commands; their Apply/Keep/Restore wording does not imply those buttons exist in the current app. Runtime-bootstrap validation-only messages and CLI argument help are also support-only.

### Runtime setup, Steam, game launch and diagnostics

| Kind | Exact text | Source |
|---|---|---|
| Status / response | This release requires an Apple silicon Mac running macOS 26 or later for its DirectX 9 renderer. No runtime has been installed. | [`source/daoctl.py:54`](../source/daoctl.py#L54) |
| Status / response | Open the Apple Rosetta installer, complete its prompts, then refresh. The launcher never accepts Apple's license for you. | [`source/daoctl.py:56`](../source/daoctl.py#L56) |
| Status / response | This Mac meets the runtime platform requirements. | [`source/daoctl.py:58`](../source/daoctl.py#L58) |
| Error / diagnostic | the reference is too large | [`source/daoctl.py:102`](../source/daoctl.py#L102) |
| Error / diagnostic | root must be an absolute folder path | [`source/daoctl.py:106`](../source/daoctl.py#L106) |
| Error / diagnostic | root must be an absolute folder path | [`source/daoctl.py:109`](../source/daoctl.py#L109) |
| Error / diagnostic | the referenced runtime folder is missing | [`source/daoctl.py:112`](../source/daoctl.py#L112) |
| Error / diagnostic | The app's runtime-location.json is invalid or unavailable: {exc}. Restore the runtime reference; no files were moved or reset. | [`source/daoctl.py:115`](../source/daoctl.py#L115) |
| Error / diagnostic | Run the packaged app or source/daoctl.py, or set DAO_PROJECT_ROOT. | [`source/daoctl.py:119`](../source/daoctl.py#L119) |
| Error / diagnostic | Finish setting up the Windows environment before opening Steam or the game. | [`source/daoctl.py:188`](../source/daoctl.py#L188) |
| Error / diagnostic | Windows user-folder containment is not ready: {exc} Choose Set up &amp; open Steam to repair local folder links; existing targets are preserved. | [`source/daoctl.py:192`](../source/daoctl.py#L192) |
| Error / diagnostic | The runtime or prefix points outside this launcher's data folder. No files were changed. | [`source/daoctl.py:199`](../source/daoctl.py#L199) |
| Error / diagnostic | The game runtime is not ready. Choose Set up &amp; open Steam first; an incomplete existing runtime is preserved. | [`source/daoctl.py:204`](../source/daoctl.py#L204) |
| Error / diagnostic | The download cache points outside this launcher's data folder. | [`source/daoctl.py:216`](../source/daoctl.py#L216) |
| Error / diagnostic | The launcher data directory points outside its dedicated folder. | [`source/daoctl.py:240`](../source/daoctl.py#L240) |
| Error / diagnostic | Another launcher operation is in progress. Wait for it to finish. | [`source/daoctl.py:246`](../source/daoctl.py#L246) |
| Error / diagnostic | Missing validation input | [`source/daoctl.py:355`](../source/daoctl.py#L355) |
| Error / diagnostic | Oversized validation input | [`source/daoctl.py:359`](../source/daoctl.py#L359) |
| Status / response | Set up downloads the pinned compatibility runtime and Windows Steam into this launcher's private data folder. | [`source/daoctl.py:443`](../source/daoctl.py#L443) |
| Status / response | Complete the Windows Steam installer window and review its terms. Then open Steam and allow its client update to finish. | [`source/daoctl.py:445`](../source/daoctl.py#L445) |
| Status / response | The Windows profile needs local folder setup. Choose Set up &amp; open Steam before continuing. | [`source/daoctl.py:448`](../source/daoctl.py#L448) |
| Status / response | Prepare Windows Steam in the dedicated game environment. | [`source/daoctl.py:454`](../source/daoctl.py#L454) |
| Status / response | The game is running. You confirmed gameplay, audio and save/reload on this Mac. | [`source/daoctl.py:457`](../source/daoctl.py#L457) |
| Status / response | The game process is running. Gameplay compatibility is still subject to testing. | [`source/daoctl.py:458`](../source/daoctl.py#L458) |
| Status / response | Finish or close Dragon Age's configuration window, then return here to Play. | [`source/daoctl.py:460`](../source/daoctl.py#L460) |
| Status / response | Steam is updating its client. Let the update finish before signing in or installing the game. | [`source/daoctl.py:462`](../source/daoctl.py#L462) |
| Status / response | Steam is starting. Wait for its window before signing in or installing the game. | [`source/daoctl.py:464`](../source/daoctl.py#L464) |
| Status / response | Steam's update finished, but its main window has not started. If no Steam window is open, use Stop, then Open Steam to finish startup. | [`source/daoctl.py:466`](../source/daoctl.py#L466) |
| Status / response | Steam completed an update and exited. The launcher is following its startup handoff. | [`source/daoctl.py:470`](../source/daoctl.py#L470) |
| Status / response | Ready to play. You confirmed gameplay, audio and save/reload on this Mac. | [`source/daoctl.py:475`](../source/daoctl.py#L475) |
| Status / response | Game files are installed. Launch to test gameplay, sound and save/load. | [`source/daoctl.py:476`](../source/daoctl.py#L476) |
| Status / response | Steam has started installing the game. Let its download and first-run setup finish. | [`source/daoctl.py:478`](../source/daoctl.py#L478) |
| Status / response | Open Windows Steam, sign in, then install the edition you own. | [`source/daoctl.py:480`](../source/daoctl.py#L480) |
| Error / diagnostic | Runtime operation timed out. See {log.name} in Show logs. | [`source/daoctl.py:513`](../source/daoctl.py#L513) |
| Error / diagnostic | Runtime exited with code {code}. See {log.name} in Show logs. | [`source/daoctl.py:515`](../source/daoctl.py#L515) |
| Error / diagnostic | Runtime preferences point outside the dedicated runtime. No user folders were changed. | [`source/daoctl.py:524`](../source/daoctl.py#L524) |
| Error / diagnostic | Prefix creation left an incomplete registry. The existing environment was preserved; do not reset it over saved data. | [`source/daoctl.py:538`](../source/daoctl.py#L538) |
| Error / diagnostic | The runtime did not create a usable environment. Inspect the initialization log. | [`source/daoctl.py:542`](../source/daoctl.py#L542) |
| Error / diagnostic | The launcher support directory points outside this game's environment. | [`source/daoctl.py:552`](../source/daoctl.py#L552) |
| Error / diagnostic | Steam download redirected away from Valve's expected distribution host. | [`source/daoctl.py:576`](../source/daoctl.py#L576) |
| Error / diagnostic | Unexpectedly large Steam installer. Download stopped for review. | [`source/daoctl.py:584`](../source/daoctl.py#L584) |
| Error / diagnostic | Valve's download is not a valid Windows installer. | [`source/daoctl.py:588`](../source/daoctl.py#L588) |
| Status / response | Windows Steam is installed. Its window or updater is opening; sign in when it is ready. | [`source/daoctl.py:619`](../source/daoctl.py#L619) |
| Status / response | Steam installer did not start. | [`source/daoctl.py:630`](../source/daoctl.py#L630) |
| Error / diagnostic | Steam's installer could not start. Check {log.name} and retry setup. | [`source/daoctl.py:631`](../source/daoctl.py#L631) |
| Status / response | Complete the Windows Steam installer window and review its terms. Then use Open Steam and let its client updates finish before signing in. | [`source/daoctl.py:632`](../source/daoctl.py#L632) |
| Error / diagnostic | Prepare Steam before opening it. | [`source/daoctl.py:638`](../source/daoctl.py#L638) |
| Status / response | Steam did not start. Use Open Steam to retry. | [`source/daoctl.py:645`](../source/daoctl.py#L645) |
| Error / diagnostic | Prepare Steam before opening it. | [`source/daoctl.py:654`](../source/daoctl.py#L654) |
| Error / diagnostic | The Steam path contains unsupported Windows command characters. | [`source/daoctl.py:659`](../source/daoctl.py#L659) |
| Error / diagnostic | The runtime could not start Steam. Check {log.name}. | [`source/daoctl.py:664`](../source/daoctl.py#L664) |
| Status / response | Launch request sent to Windows Steam. Allow its window or client update to appear. | [`source/daoctl.py:665`](../source/daoctl.py#L665) |
| Status / response | Game installation requested; startup follow-up stopped. | [`source/daoctl.py:669`](../source/daoctl.py#L669) |
| Error / diagnostic | Choose the base game or Ultimate Edition. | [`source/daoctl.py:671`](../source/daoctl.py#L671) |
| Status / response | Asked Windows Steam to install {GAMES[appid]}. Sign in and confirm the download there; this does not purchase the game. | [`source/daoctl.py:674`](../source/daoctl.py#L674) |
| Status / response | Game launch requested; startup follow-up stopped. | [`source/daoctl.py:679`](../source/daoctl.py#L679) |
| Error / diagnostic | No complete DA:O installation was found. Finish the download in Windows Steam first. | [`source/daoctl.py:688`](../source/daoctl.py#L688) |
| Status / response | Dragon Age: Origins is already running. No second instance was started. | [`source/daoctl.py:691`](../source/daoctl.py#L691) |
| Error / diagnostic | Dragon Age's configuration utility is still running. Finish or close it before choosing Play. | [`source/daoctl.py:693`](../source/daoctl.py#L693) |
| Error / diagnostic | Choose Finish game setup before playing. Complete the supplied prerequisite installers and close the game configuration window. | [`source/daoctl.py:696`](../source/daoctl.py#L696) |
| Controller response (hidden after successful Play) | Game launch requested. You confirmed gameplay, audio and save/reload on this Mac. | [`source/daoctl.py:702`](../source/daoctl.py#L702) |
| Controller response (hidden after successful Play) | Game launch requested. Steam may run prerequisite installers. Gameplay compatibility has not yet been verified. | [`source/daoctl.py:703`](../source/daoctl.py#L703) |
| Status / response | Stopped by the user. | [`source/daoctl.py:708`](../source/daoctl.py#L708) |
| Error / diagnostic | Runtime stop failed. Check {log.name}. | [`source/daoctl.py:715`](../source/daoctl.py#L715) |
| Status / response | Requested shutdown of this game's Wine session. Game files and saves are preserved. | [`source/daoctl.py:716`](../source/daoctl.py#L716) |
| Status / response | Local summary only. No credentials or Steam account data included. | [`source/daoctl.py:734`](../source/daoctl.py#L734) |
| Status / response | Saved a local diagnostic summary. Nothing was uploaded. | [`source/daoctl.py:736`](../source/daoctl.py#L736) |
| Error / diagnostic | Choose a display preset before applying settings. | [`source/daoctl.py:791`](../source/daoctl.py#L791) |

### Game prerequisites and first configuration

| Kind | Exact text | Source |
|---|---|---|
| Error / diagnostic | A setup path leaves the dedicated game folder. No installer was launched. | [`source/game_setup.py:40`](../source/game_setup.py#L40) |
| Error / diagnostic | A setup record exceeds its expected size. | [`source/game_setup.py:48`](../source/game_setup.py#L48) |
| Error / diagnostic | The game path contains unsupported Windows command characters. | [`source/game_setup.py:56`](../source/game_setup.py#L56) |
| Status / response | Install Dragon Age in Windows Steam first. | [`source/game_setup.py:89`](../source/game_setup.py#L89) |
| Error / diagnostic | The game changed or its setup record is incomplete. Choose Finish game setup again. | [`source/game_setup.py:98`](../source/game_setup.py#L98) |
| Status / response | Complete the prerequisite installer windows, then the game configuration window. If they were closed or cancelled, choose Finish game setup again. | [`source/game_setup.py:101`](../source/game_setup.py#L101) |
| Status / response | A prerequisite installer did not complete. Close its window, then retry Finish game setup. Logs and the setup backup have been preserved. | [`source/game_setup.py:104`](../source/game_setup.py#L104) |
| Error / diagnostic | The game needs its supplied native DirectX components and initial display configuration. Choose Finish game setup. | [`source/game_setup.py:111`](../source/game_setup.py#L111) |
| Status / response | Game configuration and native DirectX components are present. | [`source/game_setup.py:112`](../source/game_setup.py#L112) |
| Status / response | Choose Finish game setup to install the supplied prerequisites and create the game's initial configuration. | [`source/game_setup.py:114`](../source/game_setup.py#L114) |
| Error / diagnostic | Finish installing the selected Dragon Age edition in Windows Steam first. | [`source/game_setup.py:124`](../source/game_setup.py#L124) |
| Error / diagnostic | The supplied DirectX folder has an unexpected number of files. | [`source/game_setup.py:134`](../source/game_setup.py#L134) |
| Error / diagnostic | The supplied DirectX folder contains ambiguous filenames. | [`source/game_setup.py:137`](../source/game_setup.py#L137) |
| Error / diagnostic | The game's original DirectX setup files are missing. Verify its files in Steam, then retry. | [`source/game_setup.py:139`](../source/game_setup.py#L139) |
| Error / diagnostic | The supplied native DirectX package is incomplete. Verify the game files in Steam. | [`source/game_setup.py:144`](../source/game_setup.py#L144) |
| Error / diagnostic | The supplied prerequisite package exceeds its expected file count. | [`source/game_setup.py:148`](../source/game_setup.py#L148) |
| Error / diagnostic | A supplied prerequisite is missing or is a symbolic link. Verify the game files in Steam. | [`source/game_setup.py:153`](../source/game_setup.py#L153) |
| Error / diagnostic | The supplied prerequisite package exceeds its expected size. | [`source/game_setup.py:156`](../source/game_setup.py#L156) |
| Error / diagnostic | The game's configuration utility is missing. Verify the game files in Steam. | [`source/game_setup.py:170`](../source/game_setup.py#L170) |
| Error / diagnostic | The prerequisite sequence could not start. Its receipt, backup and log are preserved; retry Finish game setup. | [`source/game_setup.py:226`](../source/game_setup.py#L226) |
| Status / response | Complete the supplied VC++, PhysX and DirectX installer windows, reviewing their licenses. Then finish and close Dragon Age's configuration window. Steam may run its remaining first-launch setup when you press Play. | [`source/game_setup.py:228`](../source/game_setup.py#L228) |

### Automatic Steam startup follow-up

| Kind | Exact text | Source |
|---|---|---|
| Error / diagnostic | The launcher session identifier is invalid. Reopen the launcher. | [`source/steam_maintenance.py:103`](../source/steam_maintenance.py#L103) |
| Status / response | Following Steam's first-start updates while the launcher is open. | [`source/steam_maintenance.py:130`](../source/steam_maintenance.py#L130) |
| Status / response | Steam's updater log is unavailable. Automatic follow-up is off; use Open Steam as needed. | [`source/steam_maintenance.py:131`](../source/steam_maintenance.py#L131) |
| Status / response | Startup follow-up stopped. | [`source/steam_maintenance.py:133`](../source/steam_maintenance.py#L133) |
| Status / response | Startup follow-up stopped when this launcher window closed. | [`source/steam_maintenance.py:140`](../source/steam_maintenance.py#L140) |
| Status / response | Stopped this launcher window's automatic Steam follow-up. Steam and the game were left running. | [`source/steam_maintenance.py:141`](../source/steam_maintenance.py#L141) |
| Status / response | Steam startup follow-up expired or its state is invalid. Use Open Steam to start again. | [`source/steam_maintenance.py:153`](../source/steam_maintenance.py#L153) |
| Status / response | Process visibility is unavailable, so automatic Steam follow-up is paused. Refresh to retry or use Open Steam. No processes were changed. | [`source/steam_maintenance.py:159`](../source/steam_maintenance.py#L159) |
| Status / response | No startup follow-up is active for this launcher window. | [`source/steam_maintenance.py:208`](../source/steam_maintenance.py#L208) |
| Status / response | Steam startup follow-up has expired or was stopped. Use Open Steam to start again. | [`source/steam_maintenance.py:210`](../source/steam_maintenance.py#L210) |
| Status / response | No active Steam startup follow-up. | [`source/steam_maintenance.py:211`](../source/steam_maintenance.py#L211) |
| Status / response | Process visibility is unavailable. Steam will not be reopened automatically; refresh or use Open Steam. | [`source/steam_maintenance.py:217`](../source/steam_maintenance.py#L217) |
| Status / response | Steam's web interface has started; automatic startup follow-up finished. | [`source/steam_maintenance.py:220`](../source/steam_maintenance.py#L220) |
| Status / response | The game or its configuration is open; startup follow-up stopped. | [`source/steam_maintenance.py:220`](../source/steam_maintenance.py#L220) |
| Status / response | Steam's updater log changed unexpectedly. Use Open Steam if its window has not appeared. | [`source/steam_maintenance.py:224`](../source/steam_maintenance.py#L224) |
| Status / response | Steam's update finished but its updater is still running. Wait for its window; if it remains stuck, close Steam yourself and use Open Steam. Nothing was stopped. | [`source/steam_maintenance.py:230`](../source/steam_maintenance.py#L230) |
| Status / response | Waiting for Steam's updater or installer to finish. No running processes will be restarted. | [`source/steam_maintenance.py:232`](../source/steam_maintenance.py#L232) |
| Status / response | Waiting for a completed Steam update. No restart is attempted without fresh updater evidence. | [`source/steam_maintenance.py:235`](../source/steam_maintenance.py#L235) |
| Status / response | Steam needed several startup attempts. Use Open Steam to continue; automatic follow-up is paused. | [`source/steam_maintenance.py:238`](../source/steam_maintenance.py#L238) |
| Status / response | Steam's update finished. Waiting briefly for its own handoff before reopening it. | [`source/steam_maintenance.py:240`](../source/steam_maintenance.py#L240) |
| Status / response | Waiting briefly for Steam's update handoff. | [`source/steam_maintenance.py:243`](../source/steam_maintenance.py#L243) |
| Status / response | Steam activity resumed; no additional instance was started. | [`source/steam_maintenance.py:248`](../source/steam_maintenance.py#L248) |
| Status / response | Process visibility changed. No Steam instance was started. | [`source/steam_maintenance.py:251`](../source/steam_maintenance.py#L251) |
| Status / response | Steam's updater moved on; no additional instance was started. | [`source/steam_maintenance.py:255`](../source/steam_maintenance.py#L255) |
| Status / response | Continuing Steam's completed update. | [`source/steam_maintenance.py:261`](../source/steam_maintenance.py#L261) |
| Status / response | Steam's update could not be reopened automatically. Use Open Steam. {exc} | [`source/steam_maintenance.py:266`](../source/steam_maintenance.py#L266) |
| Status / response | Steam's completed update exited; reopened this launcher's Steam to continue startup. | [`source/steam_maintenance.py:267`](../source/steam_maintenance.py#L267) |

### Optional UI-scaling installation and recovery

| Kind | Exact text | Source |
|---|---|---|
| Error / diagnostic | The optional UI-scaling download redirected outside its official HTTPS distribution hosts. | [`source/ui_scaling.py:50`](../source/ui_scaling.py#L50) |
| Error / diagnostic | The optional UI-scaling download failed. Check your connection and retry; no mod files were installed. | [`source/ui_scaling.py:68`](../source/ui_scaling.py#L68) |
| Error / diagnostic | The optional UI-scaling download did not match the pinned release. No mod files were installed. | [`source/ui_scaling.py:70`](../source/ui_scaling.py#L70) |
| Error / diagnostic | The UI-scaling archive is unexpectedly large. | [`source/ui_scaling.py:80`](../source/ui_scaling.py#L80) |
| Error / diagnostic | The UI-scaling archive contains an unsafe or duplicate path. | [`source/ui_scaling.py:91`](../source/ui_scaling.py#L91) |
| Error / diagnostic | The loader license is missing or unexpectedly large. | [`source/ui_scaling.py:96`](../source/ui_scaling.py#L96) |
| Error / diagnostic | The UI-scaling archive does not contain the expected Windows binaries. | [`source/ui_scaling.py:98`](../source/ui_scaling.py#L98) |
| Error / diagnostic | The UI-scaling archive contains an empty required file. | [`source/ui_scaling.py:100`](../source/ui_scaling.py#L100) |
| Error / diagnostic | The UI-scaling archive is invalid or missing required files. | [`source/ui_scaling.py:114`](../source/ui_scaling.py#L114) |
| Error / diagnostic | Duplicate game-specific DLL overrides were found. Existing settings were preserved. | [`source/ui_scaling.py:124`](../source/ui_scaling.py#L124) |
| Error / diagnostic | The existing game-specific DLL override has an unsupported type. Existing settings were preserved. | [`source/ui_scaling.py:129`](../source/ui_scaling.py#L129) |
| Error / diagnostic | Unsupported UI-scaling DLL override. | [`source/ui_scaling.py:136`](../source/ui_scaling.py#L136) |
| Error / diagnostic | The game-specific UI-scaling registry command did not verify. | [`source/ui_scaling.py:154`](../source/ui_scaling.py#L154) |
| Error / diagnostic | The UI-scaling registry change did not persist after this runtime closed. | [`source/ui_scaling.py:157`](../source/ui_scaling.py#L157) |
| Error / diagnostic | The game-specific UI-scaling registry command failed. Inspect the launcher logs. | [`source/ui_scaling.py:160`](../source/ui_scaling.py#L160) |
| Error / diagnostic | The UI-scaling registry command did not finish; its backup is retained for recovery. | [`source/ui_scaling.py:162`](../source/ui_scaling.py#L162) |
| Error / diagnostic | The UI-scaling receipt is a symbolic link. It was preserved for inspection. | [`source/ui_scaling.py:167`](../source/ui_scaling.py#L167) |
| Error / diagnostic | The existing UI-scaling receipt is invalid. Preserve it and the current mod files before retrying. | [`source/ui_scaling.py:176`](../source/ui_scaling.py#L176) |
| Error / diagnostic | A UI-scaling destination became a symbolic link. Nothing there was replaced. | [`source/ui_scaling.py:181`](../source/ui_scaling.py#L181) |
| Error / diagnostic | The UI-scaling license folder is a symbolic link. It was preserved for inspection. | [`source/ui_scaling.py:206`](../source/ui_scaling.py#L206) |
| Error / diagnostic | An existing UI-scaling license link was preserved; inspect it before retrying. | [`source/ui_scaling.py:213`](../source/ui_scaling.py#L213) |
| Error / diagnostic | An existing UI-scaling license differs from the pinned release. It was preserved for inspection. | [`source/ui_scaling.py:217`](../source/ui_scaling.py#L217) |
| Error / diagnostic | Existing mod links were preserved. UI scaling will not replace an existing installation. | [`source/ui_scaling.py:233`](../source/ui_scaling.py#L233) |
| Error / diagnostic | The UI-scaling storage folder is a symbolic link. It was preserved for inspection. | [`source/ui_scaling.py:237`](../source/ui_scaling.py#L237) |
| Error / diagnostic | The UI-scaling receipt is a symbolic link. It was preserved for inspection. | [`source/ui_scaling.py:241`](../source/ui_scaling.py#L241) |
| Error / diagnostic | An earlier UI-scaling installation needs recovery. Preserve data/ui-scaling and inspect its receipt before retrying. | [`source/ui_scaling.py:246`](../source/ui_scaling.py#L246) |
| Status / response | Managed UI scaling is already installed. Your mod configuration was preserved. | [`source/ui_scaling.py:258`](../source/ui_scaling.py#L258) |
| Error / diagnostic | Existing or incomplete mod files were found. They were preserved; UI scaling never replaces unmanaged mods. | [`source/ui_scaling.py:260`](../source/ui_scaling.py#L260) |
| Error / diagnostic | The managed UI-scaling files were removed. Preserve the receipt and review the game folder before reinstalling. | [`source/ui_scaling.py:262`](../source/ui_scaling.py#L262) |
| Error / diagnostic | A different game-specific dinput8 override already exists. It was preserved; review it before adding UI scaling. | [`source/ui_scaling.py:265`](../source/ui_scaling.py#L265) |
| Error / diagnostic | Mod files appeared during download. They were preserved; retry after reviewing them. | [`source/ui_scaling.py:277`](../source/ui_scaling.py#L277) |
| Error / diagnostic | The game-specific DLL override changed during download. No mod files were installed. | [`source/ui_scaling.py:279`](../source/ui_scaling.py#L279) |
| Error / diagnostic | The optional UI-scaling loader was not configured successfully. | [`source/ui_scaling.py:312`](../source/ui_scaling.py#L312) |
| Status / response | Optional UI scaling is installed. Choose a display preset, then press Play. Steam can reopen normally. | [`source/ui_scaling.py:315`](../source/ui_scaling.py#L315) |
| Error / diagnostic | The DLL override changed independently; automatic rollback did not replace it. | [`source/ui_scaling.py:324`](../source/ui_scaling.py#L324) |
| Error / diagnostic | A newly installed mod file changed; automatic rollback preserved it for inspection. | [`source/ui_scaling.py:330`](../source/ui_scaling.py#L330) |
| Status / response | The recovery receipt could not be updated. | [`source/ui_scaling.py:339`](../source/ui_scaling.py#L339) |
| Error / diagnostic | UI-scaling installation needs recovery. Existing game data was preserved; inspect data/ui-scaling before retrying. | [`source/ui_scaling.py:341`](../source/ui_scaling.py#L341) |
| Error / diagnostic | UI-scaling installation failed and its changes were rolled back. Your game settings and saves were preserved; inspect the UI-scaling receipt for details. | [`source/ui_scaling.py:342`](../source/ui_scaling.py#L342) |

### Runtime download and archive validation

| Kind | Exact text | Source |
|---|---|---|
| Error / diagnostic | Archive must be a regular, non-symlink file: {path} | [`source/bootstrap_runtime.py:69`](../source/bootstrap_runtime.py#L69) |
| Error / diagnostic | Wrong archive size: {path} | [`source/bootstrap_runtime.py:71`](../source/bootstrap_runtime.py#L71) |
| Error / diagnostic | SHA256 mismatch; cached archive preserved: {path} | [`source/bootstrap_runtime.py:77`](../source/bootstrap_runtime.py#L77) |
| Error / diagnostic | Refusing a non-HTTPS archive redirect. | [`source/bootstrap_runtime.py:83`](../source/bootstrap_runtime.py#L83) |
| Error / diagnostic | Archive download exceeded its pinned size. | [`source/bootstrap_runtime.py:103`](../source/bootstrap_runtime.py#L103) |
| Error / diagnostic | Archive exceeds extraction limits. | [`source/bootstrap_runtime.py:122`](../source/bootstrap_runtime.py#L122) |
| Error / diagnostic | Unsafe archive path: {member.name!r} | [`source/bootstrap_runtime.py:129`](../source/bootstrap_runtime.py#L129) |
| Error / diagnostic | Unsupported archive member type: {member.name!r} | [`source/bootstrap_runtime.py:131`](../source/bootstrap_runtime.py#L131) |
| Error / diagnostic | Duplicate or case-colliding archive path: {member.name!r} | [`source/bootstrap_runtime.py:134`](../source/bootstrap_runtime.py#L134) |
| Error / diagnostic | Archive member traverses a non-directory: {member.name!r} | [`source/bootstrap_runtime.py:141`](../source/bootstrap_runtime.py#L141) |
| Error / diagnostic | Unsafe symlink: {member.name!r} | [`source/bootstrap_runtime.py:147`](../source/bootstrap_runtime.py#L147) |
| Error / diagnostic | Symlink escapes archive root: {member.name!r} | [`source/bootstrap_runtime.py:157`](../source/bootstrap_runtime.py#L157) |
| Error / diagnostic | Symlink escapes archive root: {member.name!r} | [`source/bootstrap_runtime.py:162`](../source/bootstrap_runtime.py#L162) |
| Error / diagnostic | Cyclic or excessive symlink chain: {member.name!r} | [`source/bootstrap_runtime.py:167`](../source/bootstrap_runtime.py#L167) |
| Error / diagnostic | Missing member data: {member.name} | [`source/bootstrap_runtime.py:188`](../source/bootstrap_runtime.py#L188) |
| Error / diagnostic | Runtime installation requires macOS; validation is portable. | [`source/bootstrap_runtime.py:221`](../source/bootstrap_runtime.py#L221) |
| Status / response | Runtime already exists. Nothing was changed or downloaded. | [`source/bootstrap_runtime.py:236`](../source/bootstrap_runtime.py#L236) |
| Error / diagnostic | Use an explicit work/cache directory, not the home or filesystem root. | [`source/bootstrap_runtime.py:239`](../source/bootstrap_runtime.py#L239) |
| Error / diagnostic | The runtime directory must not be a symlink. | [`source/bootstrap_runtime.py:241`](../source/bootstrap_runtime.py#L241) |
| Status / response | Both archive hashes and contained paths/links passed. No runtime extracted or executed. | [`source/bootstrap_runtime.py:246`](../source/bootstrap_runtime.py#L246) |
| Error / diagnostic | Cache and project must use the same filesystem for atomic installation. | [`source/bootstrap_runtime.py:249`](../source/bootstrap_runtime.py#L249) |
| Error / diagnostic | Unexpected existing prefix or engine in template. | [`source/bootstrap_runtime.py:257`](../source/bootstrap_runtime.py#L257) |
| Status / response | Pinned runtime created. No prefix initialized and no software executed. | [`source/bootstrap_runtime.py:262`](../source/bootstrap_runtime.py#L262) |
| CLI help | Dedicated data folder for runtime/ | [`source/bootstrap_runtime.py:267`](../source/bootstrap_runtime.py#L267) |
| CLI help | Explicit project/work cache on the same filesystem; existing pinned archives are reused | [`source/bootstrap_runtime.py:268`](../source/bootstrap_runtime.py#L268) |
| CLI help | Verify both pinned archives and path/link safety without runtime extraction | [`source/bootstrap_runtime.py:269`](../source/bootstrap_runtime.py#L269) |

### Display availability, changes and recovery

| Kind | Exact text | Source |
|---|---|---|
| Error / diagnostic | The settings file is not a supported INI file. | [`source/display_settings.py:71`](../source/display_settings.py#L71) |
| Error / diagnostic | The settings file has no [{section}] section. | [`source/display_settings.py:73`](../source/display_settings.py#L73) |
| Error / diagnostic | Duplicate display setting; repair the INI before applying a preset. | [`source/display_settings.py:97`](../source/display_settings.py#L97) |
| Error / diagnostic | A display settings path escapes its game folder or contains a broken link. | [`source/display_settings.py:127`](../source/display_settings.py#L127) |
| Error / diagnostic | Required settings file is missing: {path.name}. | [`source/display_settings.py:133`](../source/display_settings.py#L133) |
| Error / diagnostic | Settings file could not be read: {path.name}. | [`source/display_settings.py:137`](../source/display_settings.py#L137) |
| Error / diagnostic | Settings file is unexpectedly large: {path.name}. | [`source/display_settings.py:139`](../source/display_settings.py#L139) |
| Error / diagnostic | The display recovery record is invalid. Preserve data/display-backups and repair the record before changing settings. | [`source/display_settings.py:178`](../source/display_settings.py#L178) |
| Error / diagnostic | Finish installing Dragon Age before changing its display settings. | [`source/display_settings.py:187`](../source/display_settings.py#L187) |
| Error / diagnostic | The display probe is missing. Restore the launcher app before choosing a display preset. | [`source/display_settings.py:195`](../source/display_settings.py#L195) |
| Error / diagnostic | The current main display could not be read. Reconnect it and try again; no settings changed. | [`source/display_settings.py:223`](../source/display_settings.py#L223) |
| Error / diagnostic | Duplicate Wine display registry values; inspect the runtime before changing settings. | [`source/display_settings.py:237`](../source/display_settings.py#L237) |
| Error / diagnostic | A Wine display registry value has an unsupported type. No settings changed. | [`source/display_settings.py:245`](../source/display_settings.py#L245) |
| Error / diagnostic | DAFix.ini has an invalid HUD Scale. Repair it before changing display settings. | [`source/display_settings.py:264`](../source/display_settings.py#L264) |
| Error / diagnostic | DAFix.ini has an invalid Borderless Windowed setting. Repair it before changing display settings. | [`source/display_settings.py:275`](../source/display_settings.py#L275) |
| Error / diagnostic | Current game display settings could not be read. Open the game once or restore its INI file. | [`source/display_settings.py:294`](../source/display_settings.py#L294) |
| Error / diagnostic | Choose Comfortable or Larger interface size. | [`source/display_settings.py:303`](../source/display_settings.py#L303) |
| Status / response | This window does not fit the main display's usable area with its title bar. | [`source/display_settings.py:310`](../source/display_settings.py#L310) |
| Status / response | DAFix UI scaling is required for this mode. Install DAFix before selecting it; nothing is downloaded automatically. | [`source/display_settings.py:312`](../source/display_settings.py#L312) |
| Backend preset label/detail | Sharper, with more rendering work; check picture, input and readability. | [`source/display_settings.py:313`](../source/display_settings.py#L313) |
| Backend preset label/detail | Lower rendering load; check picture, input and readability. | [`source/display_settings.py:313`](../source/display_settings.py#L313) |
| Backend preset label/detail | Fullscreen — lighter | [`source/display_settings.py:318`](../source/display_settings.py#L318) |
| Backend preset label/detail | Fullscreen — sharper Retina | [`source/display_settings.py:320`](../source/display_settings.py#L320) |
| Backend preset label/detail | {width} × {height} — windowed | [`source/display_settings.py:326`](../source/display_settings.py#L326) |
| Error / diagnostic | process list unavailable | [`source/display_settings.py:334`](../source/display_settings.py#L334) |
| Error / diagnostic | process list was empty or could not be parsed | [`source/display_settings.py:341`](../source/display_settings.py#L341) |
| Error / diagnostic | process executable unavailable | [`source/display_settings.py:355`](../source/display_settings.py#L355) |
| Error / diagnostic | Process visibility is unavailable. Close the game and retry; settings cannot safely change yet. | [`source/display_settings.py:366`](../source/display_settings.py#L366) |
| Error / diagnostic | Save and close Dragon Age, its Windows launcher/configuration utility, and prerequisite installers before changing display settings. | [`source/display_settings.py:373`](../source/display_settings.py#L373) |
| Error / diagnostic | The game's Wine session has not finished closing. Retry after its windows close. | [`source/display_settings.py:385`](../source/display_settings.py#L385) |
| Error / diagnostic | The game's runtime wrapper is still closing. No new Wine session will be started. | [`source/display_settings.py:391`](../source/display_settings.py#L391) |
| Error / diagnostic | The display backup reference is invalid. | [`source/display_settings.py:420`](../source/display_settings.py#L420) |
| Error / diagnostic | The display backup is incomplete or invalid. Preserve it for recovery; no settings changed. | [`source/display_settings.py:442`](../source/display_settings.py#L442) |
| Error / diagnostic | The Wine display registry deletion did not verify. | [`source/display_settings.py:468`](../source/display_settings.py#L468) |
| Error / diagnostic | The Wine display registry update did not verify. | [`source/display_settings.py:472`](../source/display_settings.py#L472) |
| Error / diagnostic | The Wine display registry update did not persist after the session closed. | [`source/display_settings.py:475`](../source/display_settings.py#L475) |
| Error / diagnostic | The Wine display registry operation failed. Inspect the launcher logs. | [`source/display_settings.py:478`](../source/display_settings.py#L478) |
| Error / diagnostic | The Wine display registry operation did not finish. Its recovery record has been preserved. | [`source/display_settings.py:480`](../source/display_settings.py#L480) |
| Error / diagnostic | DAFix UI scaling is missing; its HUD setting could not be applied. | [`source/display_settings.py:491`](../source/display_settings.py#L491) |
| Error / diagnostic | The main display changed during this operation. Refresh the presets and try again. | [`source/display_settings.py:495`](../source/display_settings.py#L495) |
| Status / response | The saved Retina settings need a display with matching 2× backing dimensions. Reconnect that display or apply a current preset. | [`source/display_settings.py:502`](../source/display_settings.py#L502) |
| Status / response | The saved full-screen settings belong to a different display configuration. Reconnect that display or apply a preset for this display. | [`source/display_settings.py:505`](../source/display_settings.py#L505) |
| Status / response | The saved full-screen dimensions do not match this display. Apply a current preset instead. | [`source/display_settings.py:508`](../source/display_settings.py#L508) |
| Status / response | The saved window no longer fits this display's usable area. Apply a smaller windowed preset instead. | [`source/display_settings.py:514`](../source/display_settings.py#L514) |
| Error / diagnostic | The display backup belongs to another game edition. | [`source/display_settings.py:519`](../source/display_settings.py#L519) |
| Error / diagnostic | Restored display settings did not verify. The recovery snapshot has been preserved. | [`source/display_settings.py:534`](../source/display_settings.py#L534) |
| Error / diagnostic | A previous change needs recovery. Restore working settings before applying another preset. | [`source/display_settings.py:573`](../source/display_settings.py#L573) |
| Error / diagnostic | That preset is not available for the current main display. | [`source/display_settings.py:602`](../source/display_settings.py#L602) |
| Status / response | The selected display settings are already in use. | [`source/display_settings.py:605`](../source/display_settings.py#L605) |
| Status / response | Your confirmed display settings are ready. | [`source/display_settings.py:616`](../source/display_settings.py#L616) |
| Status / response | The selected display settings are ready for this launch. | [`source/display_settings.py:618`](../source/display_settings.py#L618) |
| Error / diagnostic | Restore working settings to recover the previous change before applying another preset. | [`source/display_settings.py:623`](../source/display_settings.py#L623) |
| Error / diagnostic | That preset is not available for the current main display. | [`source/display_settings.py:627`](../source/display_settings.py#L627) |
| Error / diagnostic | The display settings did not match the requested preset after writing. | [`source/display_settings.py:651`](../source/display_settings.py#L651) |
| Status / response | Display settings applied. Use Play, check the picture, mouse and interface, then choose Keep settings. The game was not launched. | [`source/display_settings.py:655`](../source/display_settings.py#L655) |
| Status / response | Previous settings were restored. | [`source/display_settings.py:669`](../source/display_settings.py#L669) |
| Status / response | Preserve data/display-backups and use Restore working settings; recovery is still required. | [`source/display_settings.py:669`](../source/display_settings.py#L669) |
| Status / response | No display settings were changed. | [`source/display_settings.py:669`](../source/display_settings.py#L669) |
| Error / diagnostic | The display change failed: {error} {suffix} | [`source/display_settings.py:670`](../source/display_settings.py#L670) |
| Status / response | Working display settings restored. Other graphics, audio and saves were preserved. Use Play when ready. | [`source/display_settings.py:691`](../source/display_settings.py#L691) |
| Error / diagnostic | Restore working settings before confirming another display mode. | [`source/display_settings.py:698`](../source/display_settings.py#L698) |
| Error / diagnostic | The display or game settings changed since Apply. Apply the intended preset again before keeping it. | [`source/display_settings.py:704`](../source/display_settings.py#L704) |
| Error / diagnostic | Apply a preset and check its picture, input and interface before keeping it. | [`source/display_settings.py:706`](../source/display_settings.py#L706) |
| Error / diagnostic | Settings changed while confirming. No working snapshot was selected; try again after settings settle. | [`source/display_settings.py:709`](../source/display_settings.py#L709) |
| Status / response | These display settings are now your working restore point. This records your display check, not a new gameplay or save/load test. | [`source/display_settings.py:712`](../source/display_settings.py#L712) |

### Dedicated Windows-profile containment

| Kind | Exact text | Source |
|---|---|---|
| Error / diagnostic | A Windows user-folder path escapes the dedicated prefix. Its target was preserved; setup must not continue. | [`source/profile_paths.py:31`](../source/profile_paths.py#L31) |
| Error / diagnostic | The Windows user registry exceeds its expected size. | [`source/profile_paths.py:42`](../source/profile_paths.py#L42) |
| Error / diagnostic | The Windows user registry could not be read safely. | [`source/profile_paths.py:46`](../source/profile_paths.py#L46) |
| Error / diagnostic | The Windows user registry is incomplete or has an unsupported format. | [`source/profile_paths.py:48`](../source/profile_paths.py#L48) |
| Error / diagnostic | The Windows user registry contains an incomplete section. | [`source/profile_paths.py:53`](../source/profile_paths.py#L53) |
| Error / diagnostic | A Windows profile or shell-folder value is malformed. No registry mapping was changed. | [`source/profile_paths.py:76`](../source/profile_paths.py#L76) |
| Error / diagnostic | The Windows user registry has duplicate folder mappings. | [`source/profile_paths.py:78`](../source/profile_paths.py#L78) |
| Error / diagnostic | A Windows user folder maps outside drive C: or uses an unknown variable. No mapping was changed. | [`source/profile_paths.py:86`](../source/profile_paths.py#L86) |
| Error / diagnostic | A Windows user-folder path is invalid. No mapping was changed. | [`source/profile_paths.py:90`](../source/profile_paths.py#L90) |
| Error / diagnostic | A Windows user-folder path is ambiguous. | [`source/profile_paths.py:98`](../source/profile_paths.py#L98) |
| Error / diagnostic | The active Windows profile is not a supported local user directory. | [`source/profile_paths.py:117`](../source/profile_paths.py#L117) |
| Error / diagnostic | The active Windows profile has no Documents mapping. Finish prefix initialization before continuing. | [`source/profile_paths.py:123`](../source/profile_paths.py#L123) |
| Error / diagnostic | Documents refers to another Windows user, but the active user is unknown. Finish prefix initialization before continuing. | [`source/profile_paths.py:126`](../source/profile_paths.py#L126) |
| Error / diagnostic | The Windows Documents or shell-folder mappings disagree. No registry mapping was changed. | [`source/profile_paths.py:128`](../source/profile_paths.py#L128) |
| Error / diagnostic | A Windows user folder is a file. It was preserved; repair the prefix before continuing. | [`source/profile_paths.py:141`](../source/profile_paths.py#L141) |
| Error / diagnostic | The active Windows profile or Documents folder is missing. Finish setup before opening Steam. | [`source/profile_paths.py:143`](../source/profile_paths.py#L143) |
| Error / diagnostic | The active Windows user is unknown. Finish prefix initialization before creating user folders. | [`source/profile_paths.py:159`](../source/profile_paths.py#L159) |

### Steam edition titles and manifest diagnostics

| Kind | Exact text | Source |
|---|---|---|
| Edition title | Dragon Age: Origins | [`source/steam_state.py:20`](../source/steam_state.py#L20) |
| Edition title | Dragon Age: Origins - Ultimate Edition | [`source/steam_state.py:21`](../source/steam_state.py#L21) |
| Error / diagnostic | NUL in KeyValues | [`source/steam_state.py:36`](../source/steam_state.py#L36) |
| Error / diagnostic | Unterminated comment | [`source/steam_state.py:49`](../source/steam_state.py#L49) |
| Error / diagnostic | Too many tokens | [`source/steam_state.py:54`](../source/steam_state.py#L54) |
| Error / diagnostic | Unterminated escape | [`source/steam_state.py:66`](../source/steam_state.py#L66) |
| Error / diagnostic | Unterminated quoted string | [`source/steam_state.py:75`](../source/steam_state.py#L75) |
| Error / diagnostic | Excessive nesting | [`source/steam_state.py:91`](../source/steam_state.py#L91) |
| Error / diagnostic | Unexpected closing brace | [`source/steam_state.py:97`](../source/steam_state.py#L97) |
| Error / diagnostic | Expected key | [`source/steam_state.py:99`](../source/steam_state.py#L99) |
| Error / diagnostic | Duplicate key | [`source/steam_state.py:102`](../source/steam_state.py#L102) |
| Error / diagnostic | Missing value | [`source/steam_state.py:105`](../source/steam_state.py#L105) |
| Error / diagnostic | Expected value | [`source/steam_state.py:111`](../source/steam_state.py#L111) |
| Error / diagnostic | Unclosed object | [`source/steam_state.py:113`](../source/steam_state.py#L113) |

### Display probe diagnostics

These probe messages are technical diagnostics. The controller normally wraps a failed probe in its own display-read error.

| Kind | Exact text | Source |
|---|---|---|
| Diagnostic | No active display is available to the launcher. | [`source/DisplayProbe.swift:36`](../source/DisplayProbe.swift#L36) |
| Diagnostic | An active display did not provide its display identifier. | [`source/DisplayProbe.swift:40`](../source/DisplayProbe.swift#L40) |
| Diagnostic | The active display mode could not be read. Reconnect the display and try again. | [`source/DisplayProbe.swift:44`](../source/DisplayProbe.swift#L44) |
| Diagnostic | The active display returned invalid dimensions. | [`source/DisplayProbe.swift:52`](../source/DisplayProbe.swift#L52) |
| Diagnostic | The main active display could not be identified. | [`source/DisplayProbe.swift:65`](../source/DisplayProbe.swift#L65) |
| Diagnostic | Display information could not be encoded. | [`source/DisplayProbe.swift:76`](../source/DisplayProbe.swift#L76) |

## Appendix B. Other packaging modes

These are complete alternate `START HERE.txt` contents generated by the current packaging function. They include the new licensing paragraph and do not describe the unchanged frozen beta.3 DMG.

### Signed/notarized public mode

```text
Drag Origins Launcher to Applications, then open it.
Choose Set up & open Steam. Sign in to your own Steam account and install Dragon Age: Origins.
Return to the app and follow its first-game setup prompts.

Requires Apple Silicon and macOS 26 or 27; Rosetta may prompt for installation.
Unofficial. Not affiliated with EA, BioWare or Valve.

Launcher code is licensed under GNU GPL version 3 only; see LICENSE and LICENSING.md.
Artwork and third-party components have separate terms; see ARTWORK.md and THIRD_PARTY.md.
```

### Local-preview mode

```text
LOCAL PREVIEW — not signed with Developer ID or notarized.
For public installation, use a separately labeled unsigned beta or a signed/notarized release.
Do not disable macOS security checks.

Drag Origins Launcher to Applications, then open it.
Choose Set up & open Steam. Sign in to your own Steam account and install Dragon Age: Origins.
Return to the app and follow its first-game setup prompts.

Requires Apple Silicon and macOS 26 or 27; Rosetta may prompt for installation.
Unofficial. Not affiliated with EA, BioWare or Valve.

Launcher code is licensed under GNU GPL version 3 only; see LICENSE and LICENSING.md.
Artwork and third-party components have separate terms; see ARTWORK.md and THIRD_PARTY.md.
```

## Coverage and amendment notes

- Reviewed `source/Launcher.swift`, `source/daoctl.py`, `source/bootstrap_runtime.py`, `source/game_setup.py`, `source/ui_scaling.py`, `source/steam_maintenance.py`, `source/display_settings.py`, `source/profile_paths.py`, `source/steam_state.py`, `source/DisplayProbe.swift`, `source/build.sh` and `scripts/package_release.py`.
- Includes native text, headings, button and link labels, picker labels, accessibility text, tooltips, authored success/progress/failure strings, display-row templates, About copy, app identity text, and all three disk-image instruction variants.
- Pure implementation identifiers, registry/configuration keys, shell commands, binary markers, developer build/signing/audit command output, duplicate external licence documents, and third-party installer copy are excluded. Internal diagnostics are included where they may help trace an error, but are not presented as additional installation screens.
- This is a source snapshot. Editing this document alone does not change an app or an existing DMG. Approved wording changes must be made in the referenced source, then rebuilt/repackaged as appropriate.
- The licence-transition update synchronizes the catalogue with changed About/help and packaging source text. It does not replace the installed app, modify runtime/game settings or add a notch warning.
