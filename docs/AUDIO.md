# Audio compatibility

Origins Launcher includes an automatic audio compatibility fix for the verified
Steam version of Dragon Age: Origins. It is intended to reduce crackling and
repeated or overlapping dialogue reported with Wine. There is no separate audio
setting to enable: press **Play** as usual.

The launcher checks the game, its FMOD audio library and the compatibility
runtime before applying the fix. Unsupported versions and existing third-party
`dsound.dll` mods are preserved. An unsupported installation with no managed
audio fix can still launch normally without it.

## What changes

The fix adds a verified `dsound.dll` beside the game's executable and a Wine
loading rule that applies only to `DAOrigins.exe`. It adjusts when the game's
identified audio-producing thread waits. When the available audio reserve is
unsafe, assistance pauses; it can resume once fresh, complete audio coverage has
recovered. Uncertain identity or broken playback history keeps assistance off.

The game executable, FMOD library, saves and the game’s audio assets are not
replaced. The fix does not change shared macOS audio settings or install a system
audio driver. It can be used independently of the optional **4 GB memory support**
setting.

Installation and removal happen only while this launcher's Wine session is
closed. On the first applicable launch, Origins Launcher may close idle Windows
Steam and its background services before applying the fix. It then launches the
game through Steam normally. Subsequent launches do not restart Steam just to
reinstall an already verified component. An updating Steam client, a game or an
unrecognized Windows program must finish or close first.

If both Steam editions are installed, the launcher transfers its managed audio
component to the edition selected for Play. It removes only its own component
from the previous edition; both game installations and their saves remain in
place. Selecting an unsupported edition clears the previous managed audio rule
before launching with the normal runtime audio handling.

## Current validation and limits

**0.2.0-beta.7 validation:** The production audio
component and **4 GB memory support** have now been tested together on the M5 Pro
MacBook. The user confirmed gameplay, then restarted the game and successfully
reloaded the save with controls and sound working.

A brief audio issue still occurred and cleared itself. The main session's final
local status showed about 11 minutes of process uptime, with assistance still
active, four pauses followed by four resumptions, and no permanent cutoff. This
status describes the component's behavior; it does not measure audible quality
or establish when or why the brief issue happened. No audio was recorded and the
exact symptom timing is unknown.

These are results from one Mac, not a guarantee that every audio problem is
cured. The M1 MacBook Air reports have not yet been retested with this fix.
Automated tests also check policy boundaries, recovery, file ownership and
installation failure handling; they cannot establish audible quality during
gameplay.

## Conflicts and recovery

The launcher keeps a receipt, a verified recovery copy of its component and the
original registry backup under `data/audio-fix` in its local data root. An
interrupted change can be reconciled on the next Play attempt. Registry recovery
edits only the launcher's owned audio rule, preserving unrelated later changes;
it does not replace the whole registry with an old backup.

If a game/runtime update is no longer supported, the launcher removes its own
unchanged component and loading rule before ordinary launch. It refuses to
replace or delete a file or rule that someone else has changed. In that case,
close the game and Windows Steam, keep the files in place and report the exact
message with a reviewed **Diagnostics** summary. Do not remove unrelated mods or
replace game executables to work around the warning.

If audio problems remain, include the Mac model, macOS version, audio output
(built-in speakers, wired headphones or Bluetooth), whether 4 GB support is on,
and whether the problem begins immediately or after playing for a while. Mention
whether it affects music, effects, dialogue or all three. See
[Troubleshooting](TROUBLESHOOTING.md) and [local data/privacy](DATA.md).
