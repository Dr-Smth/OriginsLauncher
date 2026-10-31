# Developer console

The development build adds a **Developer console** switch beside **4 GB memory
support**. Quit the game and its official Windows launcher, select the switch,
then press **Play**. Your choice is remembered and applies on the next launch.
Turn it off and launch again to stop enabling the console through this app.

The switch defaults to off for a normal installation. Opening Origins Launcher
does not change game files. If Ultimate Edition's launcher XML already enables
the console and you have not chosen a setting, the switch reflects that existing
setting without changing it.

## Opening the console

The game's usual binding is **grave/backtick** (`Keyboard::Button_Grave`). Its
physical position and the character printed on the key vary with Mac keyboard
layouts. Press the bound key during gameplay; press Return to submit an input.
The standard game may show **no console or typed text**, so an invisible console
does not necessarily mean that it is disabled. This switch does not install a
console-font mod or change your key bindings.

**Files** in the launcher opens the Windows environment. From there, your binding
is in `drive_c/users/<Windows user>/Documents/BioWare/Dragon Age/Settings/KeyBindings.ini`.
Look for `OpenConsole_0` if your console key has been changed. Keep a separate save
before using commands that alter a game.

## How it works

- **Steam standard edition (17450):** passes `-enabledeveloperconsole` to Steam
  for that launch. Turning the switch off omits this flag. An option you added
  separately in Steam's Properties still applies; remove that option there if
  you want it disabled as well. Origins Launcher does not read or rewrite Steam
  account files to control this setting.
- **Steam Ultimate Edition (47810):** adds the flag to the game-launch entry in
  `data/DAOriginsLauncher.xml`, after saving a local backup. Turning the switch
  off removes the flag while preserving unrelated arguments and XML changes.
  The configuration/prerequisite entry is left unchanged. Steam file verification
  or an update can replace the XML; the selected setting is checked again on Play.

Backups and receipts remain inside the launcher's data root under
`data/developer-console`, separately for each installation. They are local
recovery files, not release assets, and remain there when the switch is off.
If a file replacement is interrupted, retrying keeps the original restoration
record and preserves later unrelated XML edits. No game executable, save, key binding, audio
component or shared macOS setting is changed by this feature.

If the XML cannot be safely identified or the game/official launcher is open,
Origins Launcher stops and explains the problem. Close those windows before
retrying. Modified or unsupported XML is preserved rather than replaced with an
old backup.
