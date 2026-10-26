# Privacy, saves and local data

The app's default data root is:

```text
~/Library/Application Support/OriginsLauncher
```

It contains the downloaded runtime, Windows Steam, game installation, settings,
saves, setup receipts and local logs. Keep this folder in place: Wine may store
absolute paths inside its configuration.

The game normally stores saves under this relative path inside the data root:

```text
runtime/DAO Runtime.app/Contents/SharedSupport/prefix/drive_c/users/<WindowsUser>/Documents/BioWare/Dragon Age/Characters
```

`<WindowsUser>` is the Windows profile created in this environment, often
`Sikarugir`. The launcher reads the active profile rather than assuming its name,
and checks that its Documents folder remains inside this environment before
opening Steam or the game. Use **Files** to locate that profile's Documents folder.

Save and quit the game before backing up the entire `BioWare/Dragon Age` folder.
Preserve it before removing or changing the runtime. Steam Cloud is not a
substitute for checking that a usable local backup exists.

Closing Origins Launcher does not stop the game or Steam. **Stop session** ends
this environment's Wine processes after confirmation, so save your progress
first. Removing the app bundle leaves the data root and saves in place.

## Network and diagnostics

Setup contacts official upstream download services; Steam then handles sign-in,
updates and game downloads. Enter credentials and Steam Guard codes only in
Steam. The game, Steam and runtime dependencies have their own network behaviour
and privacy terms.

Origins Launcher does not send telemetry or automatically upload diagnostics.
**Diagnostics** writes a local summary with project paths redacted. Review it
before sharing: hardware, versions and configuration can still identify a setup.
Raw Steam, Wine and installer logs may contain personal details; do not post them
without inspection and redaction.

Do not share the whole data root, prepared prefix, registry, Steam `config` or
`userdata` folders. Those are not release artifacts and may contain account data.
