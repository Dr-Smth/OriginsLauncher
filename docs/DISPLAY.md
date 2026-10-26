# Display settings

Fullscreen works best when the game's dimensions match the surface exposed by
Wine. macOS can report both a logical desktop size and a larger Retina rendering
size. Selecting an unrelated fullscreen resolution can produce a clear picture
but incorrect mouse coordinates.

Use the launcher's detected presets instead of copying another Mac's dimensions.
Save and quit the game before applying a display change. A mode change may
restart Windows Steam so every Wine process uses the same coordinate system.
The launcher backs up the settings it changes.

## MacBook camera notch

If you use fullscreen on a MacBook with a display notch, the game's top menu bar
may be obscured. You can still access the menus using these default keyboard
shortcuts. You can rebind them in the game's options. The defaults match the
[EA PC manual](https://eaassets-a.akamaihd.net/eahelp/manuals/dragon-age-origins-manuals_PC.pdf)
and the fresh installation's key bindings.

| Menu | Default key |
| --- | --- |
| Character record | **C** |
| Skills | **K** |
| Spells/talents | **P** |
| Inventory | **I** |
| Journal | **J** |
| Area map | **M** |
| World map | **N** |
| Tactics | Backslash (`\`) |
| Main menu/options | **Esc** |

You can also use **Windowed** mode to avoid this. Save and quit first, then choose
a windowed resolution that fits below the notch and relaunch.

## Resolution and UI size

Retina increases rendering resolution and GPU work. Windows DPI settings alone
do not guarantee that the game's HUD becomes larger. Optional **DAFix** supplies
the HUD-scaling support used by the launcher; choose **Enable UI scaling** after
the game is installed if you want those presets.

DAFix is an independent ASI extension by Lyall, loaded through Ultimate ASI
Loader. It is not a replacement game executable. The launcher obtains the pinned
release from its author and keeps both projects' licence notices. Existing mod
files should be preserved rather than silently replaced.

The upstream `[HUD Scale]` value ranges from 0 to 1: lower nonzero values make the
HUD larger, and 0 requests automatic sizing. The launcher presents readable UI
choices instead of requiring you to calculate this value. DAFix is optional;
normal rendering modes remain useful without it.

Source and configuration: [DAFix](https://github.com/Lyall/DAFix) and
[v0.0.3 settings](https://github.com/Lyall/DAFix/blob/v0.0.3/DAFix.ini).

## Check a new setting

At the main menu, check the whole picture, hover highlights and clicks. In a
playable scene, check text, dialogue, inventory and the ability bar. A sharper
image is not a successful setting if the UI becomes uncomfortable or input stops
lining up.

If a preset is unsuitable, quit the game and select a lower-resolution or
windowed preset. Keep the tested setting until a new one has been checked.
Changing Mac display scaling or moving between monitors can require refreshing
the available presets. Multi-monitor behaviour remains an area for further
testing.
