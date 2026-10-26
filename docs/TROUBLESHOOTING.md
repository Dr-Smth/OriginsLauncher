# Troubleshooting

## Steam is updating or no sign-in window appears

Give the first update several minutes and keep Origins Launcher open; it can be
minimized. Steam may update more than once. After setup or **Open Steam**, the
launcher watches for a completed updater that has exited and can reopen Steam.
It allows at most three automatic reopen attempts within 20 minutes. It does not
stop a running updater, installer, game or download to do this.

If startup follow-up pauses or expires, read the status message and use **Open
Steam** to retry when appropriate. If an updater is still running, wait for it
to finish. Closing Origins Launcher cancels its follow-up and leaves Steam and
the game running. Do not use **Stop session** during a game download, installer
or unsaved gameplay.

## The game still says downloading

Finish the installation in Windows Steam. The launcher waits for both a complete
Steam manifest and the final installed executable; a partially downloaded file
does not count. Choose the edition actually owned by the signed-in Steam account.

## First-run configuration or a DirectX warning

Let Steam run the shipped prerequisites. If a configuration check is offered,
finish it and close the window before Play. Record the exact error if setup fails
and collect **Diagnostics**. Avoid downloading replacement game executables or
random DLL bundles. Repairs must use the game's own or official dependencies.

## Fullscreen looks cropped or the mouse cannot click

Quit the game, refresh the display choices, then use a preset matching the current
desktop or a smaller window. A visually aligned cursor is not proof that clicks
are mapped correctly. Check hover highlights as well. See [Display](DISPLAY.md).

## The MacBook display notch obscures the game's top menu bar

This may happen in fullscreen. You can still access those menus using the
[default keyboard shortcuts](DISPLAY.md#macbook-camera-notch), or use **Windowed**
mode to avoid it. Save and quit before changing modes.

## The interface is too small

Use a lower rendering resolution or the optional **Enable UI scaling** feature,
then select a comfortable UI size. Save and quit first. Existing UI mods may
conflict; the launcher should report a conflict rather than overwrite them.

## macOS will not open a downloaded app

Check that it came from the intended publisher and that its checksum matches the
release. A download labelled **UNSIGNED-BETA** has no Developer ID identity or
Apple notarization ticket. Its ad-hoc signature checks local integrity; it does
not identify a verified publisher. macOS can block it on first launch rather
than simply show the usual downloaded-app confirmation.

If the warning is about an unidentified developer or Apple being unable to check
the app, and you trust the release:

1. Try opening **Origins Launcher.app** once.
2. Open **System Settings → Privacy & Security**.
3. Find the message about Origins Launcher and choose **Open Anyway**, then
   confirm **Open** in the next prompt.

This approves this app. Follow
[Apple's instructions](https://support.apple.com/en-gb/102445) for your macOS
version. Managed Macs may restrict the option; contact your administrator if it
is unavailable. A signed and notarized release is the recommended installation
path when available.

If macOS reports malware, says the app will damage the computer, or says it is
damaged, do not treat that as the ordinary unsigned-beta warning. Stop and report
the exact message to the maintainer. Do not disable Gatekeeper or remove security
attributes to force a blocked download to run.

## Report a problem

Include launcher/runtime versions, Mac model, macOS version, game edition, display
preset, the exact error and the steps that produced it. Review the local
diagnostic summary before sharing it. Keep account files and raw logs private;
[Data](DATA.md) explains what the environment contains.
