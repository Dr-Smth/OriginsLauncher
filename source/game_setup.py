"""First-game setup using only prerequisites supplied with the user's game.

The DirectX subset follows Microsoft's documented small installation package:
https://learn.microsoft.com/windows/win32/dxtecharts/directx-setup-for-game-developers
Original game assets stay unchanged; no Steam account files are read and no
completion registry flags are forged. Private registry backups stay in app data.
Installers remain interactive so their license terms and cancellation are visible.
"""
from __future__ import annotations

import configparser
import hashlib
import json
from pathlib import Path
import re
import shutil
import struct
import uuid

from steam_state import discover_games
from profile_paths import documents_path


class SetupError(ValueError):
    pass


COMPONENTS = ("d3dx9_36.dll", "xactengine2_2.dll", "xactengine2_3.dll", "xactengine2_6.dll")
SETUP_FILES = ("dxsetup.exe", "dsetup.dll", "dsetup32.dll", "dxupdate.cab")
CAB_PATTERN = re.compile(r"[a-z]{3}[0-9]{4}_(?:d3dx9_[0-9]+|xact|xinput|x3daudio)_x86\.cab", re.I)
MAX_PACKAGE_BYTES = 160 * 1024 * 1024


def inside(path, base):
    try:
        result = Path(path).resolve()
        result.relative_to(Path(base).resolve())
        return result
    except (OSError, ValueError, RuntimeError) as exc:
        raise SetupError("A setup path leaves the dedicated game folder. No installer was launched.") from exc


def read(path, base, limit=65536):
    path = inside(path, base)
    with path.open("rb") as handle:
        raw = handle.read(limit + 1)
    if len(raw) > limit:
        raise SetupError("A setup record exceeds its expected size.")
    return raw


def windows(path, controller):
    relative = inside(path, controller.prefix / "drive_c").relative_to((controller.prefix / "drive_c").resolve())
    value = "C:\\" + str(relative).replace("/", "\\")
    if re.search(r'["\r\n&|<>%^!]', value):
        raise SetupError("The game path contains unsupported Windows command characters.")
    return value


def ini_path(c):
    return inside(documents_path(c.prefix) / "BioWare/Dragon Age/Settings/DragonAge.ini", c.prefix)


def fingerprint(c, game):
    exe = inside(game["exe"], c.prefix)
    value = exe.stat()
    return {"appid": game["appid"], "size": value.st_size, "mtime_ns": value.st_mtime_ns}


def components_ready(c):
    """Require the actual 32-bit optional libraries, not a DirectX version flag."""
    for name in COMPONENTS:
        path = inside(c.prefix / "drive_c/windows/syswow64" / name, c.prefix)
        try:
            with path.open("rb") as handle:
                header = handle.read(4096)
            offset = struct.unpack_from("<I", header, 0x3c)[0]
            if (header[:2] != b"MZ" or b"Wine builtin DLL" in header
                    or header[offset:offset + 4] != b"PE\0\0"
                    or struct.unpack_from("<H", header, offset + 4)[0] != 0x14c):
                return False
        except (OSError, struct.error):
            return False
    return True


def configuration_status(c, game):
    if not game:
        return {"ready": False, "message": "Install Dragon Age in Windows Steam first."}
    try:
        record = inside(c.data / ("game-setup-" + game["appid"] + ".json"), c.root)
        if record.exists():
            receipt = json.loads(read(record, c.root))
            identifier = receipt.get("id") if isinstance(receipt, dict) else None
            if (receipt.get("schema_version") != 1 or not isinstance(identifier, str)
                    or not re.fullmatch(r"[0-9a-f]{32}", identifier)
                    or receipt.get("game") != fingerprint(c, game)):
                raise SetupError("The game changed or its setup record is incomplete. Choose Finish game setup again.")
            result = c.prefix / "drive_c/dao-support" / ("game-setup-" + identifier) / "result.txt"
            if not result.exists():
                return {"ready": False, "message": "Complete the prerequisite installer windows, then the game configuration window. If they were closed or cancelled, choose Finish game setup again."}
            marker = read(result, c.prefix, 256).decode("ascii").strip()
            if marker != "PREREQUISITES_COMPLETE":
                return {"ready": False, "message": "A prerequisite installer did not complete. Close its window, then retry Finish game setup. Logs and the setup backup have been preserved."}
        parser = configparser.ConfigParser(interpolation=None)
        parser.read_string(read(ini_path(c), c.prefix, 1024 * 1024).decode("utf-8-sig"))
        if (not 0 < parser.getint("VideoOptions", "ResolutionWidth") <= 16384
                or not 0 < parser.getint("VideoOptions", "ResolutionHeight") <= 16384
                or parser.get("VideoOptions", "FullScreen").strip() not in ("0", "1")
                or not components_ready(c)):
            raise SetupError("The game needs its supplied native DirectX components and initial display configuration. Choose Finish game setup.")
        return {"ready": True, "message": "Game configuration and native DirectX components are present."}
    except (OSError, ValueError, TypeError, AttributeError, KeyError, struct.error, configparser.Error) as exc:
        return {"ready": False, "message": str(exc) if isinstance(exc, SetupError) else "Choose Finish game setup to install the supplied prerequisites and create the game's initial configuration."}


def select_game(c, appid=None):
    games = [g for g in discover_games(c.prefix) if g["complete"]]
    selected = appid or c.state().get("selected_appid")
    game = next((g for g in games if g["appid"] == selected), None)
    if game is None and appid is None:
        game = next(iter(games), None)
    if game is None:
        raise SetupError("Finish installing the selected Dragon Age edition in Windows Steam first.")
    inside(game["game_dir"], c.prefix)
    return game


def package_files(c, game):
    redist = inside(Path(game["game_dir"]) / "redist", c.prefix)
    directx = inside(redist / "DirectX", redist)
    entries = list(directx.iterdir())
    if len(entries) > 256:
        raise SetupError("The supplied DirectX folder has an unexpected number of files.")
    by_name = {p.name.casefold(): p for p in entries}
    if len(by_name) != len(entries):
        raise SetupError("The supplied DirectX folder contains ambiguous filenames.")
    if any(name not in by_name for name in SETUP_FILES):
        raise SetupError("The game's original DirectX setup files are missing. Verify its files in Steam, then retry.")
    chosen = [by_name[name] for name in SETUP_FILES]
    cabs = [p for p in entries if CAB_PATTERN.fullmatch(p.name)]
    if (not any(re.search(r"_d3dx9_36_x86\.cab$", p.name, re.I) for p in cabs)
            or not any(re.search(r"_xact_x86\.cab$", p.name, re.I) for p in cabs)):
        raise SetupError("The supplied native DirectX package is incomplete. Verify the game files in Steam.")
    chosen.extend(cabs)
    chosen.extend(redist / name for name in ("vcredist_x86.exe", "PhysX_9.09.0408_SystemSoftware.exe"))
    if len(chosen) > 100:
        raise SetupError("The supplied prerequisite package exceeds its expected file count.")
    total = 0
    for path in chosen:
        safe = inside(path, redist)
        if path.is_symlink() or not safe.is_file():
            raise SetupError("A supplied prerequisite is missing or is a symbolic link. Verify the game files in Steam.")
        total += safe.stat().st_size
    if total > MAX_PACKAGE_BYTES:
        raise SetupError("The supplied prerequisite package exceeds its expected size.")
    return sorted(chosen, key=lambda p: p.name.casefold())


def configure_game(c, appid=None):
    c.require_platform()
    c.require_runtime()
    c.require_contained_profile()
    from display_settings import DisplaySettings
    manager = DisplaySettings(c, appid=appid)
    manager._guard()
    game = select_game(c, appid)
    config = inside(Path(game["exe"]).parent / "DAOriginsConfig.exe", c.prefix)
    if not config.is_file():
        raise SetupError("The game's configuration utility is missing. Verify the game files in Steam.")
    files = package_files(c, game)
    identifier = uuid.uuid4().hex
    stage = inside(c.prefix / "drive_c/dao-support" / ("game-setup-" + identifier), c.prefix)
    backup = inside(c.data / "game-setup-backups" / identifier, c.root)
    # Resolve every execution path before creating files or launching anything.
    config_windows, game_windows = windows(config, c), windows(Path(game["exe"]), c)
    launcher_windows = windows(Path(game["game_dir"]) / "DAOriginsLauncher.exe", c)
    stage_windows = windows(stage, c)
    target_ini = ini_path(c)
    # Flush only this prefix before the backup. A fresh baseline changes Wine's
    # display coordinate mode, which must persist before the next GUI starts.
    manager._stop_prefix()
    stage.mkdir(parents=True, exist_ok=False)
    backup.mkdir(mode=0o700, parents=True, exist_ok=False)
    for name in ("user.reg", "system.reg", "userdef.reg"):
        path = c.prefix / name
        if path.is_file():
            saved = backup / name
            saved.write_bytes(read(path, c.prefix, 32 * 1024 * 1024))
            saved.chmod(0o600)
    if target_ini.exists():
        saved = backup / "DragonAge.ini"
        saved.write_bytes(read(target_ini, c.prefix, 1024 * 1024))
        saved.chmod(0o600)
    receipt = {"schema_version": 1, "id": identifier, "game": fingerprint(c, game),
               "method": "Game-supplied interactive installers; native x86 DirectX subset; original game assets unchanged.",
               "files": []}
    for source in files:
        destination = stage / source.name
        shutil.copyfile(source, destination)
        receipt["files"].append({"name": source.name, "bytes": destination.stat().st_size,
                                 "sha256": hashlib.sha256(destination.read_bytes()).hexdigest()})
    fresh_ini = not target_ini.exists()
    if fresh_ini:
        target_ini.parent.mkdir(parents=True, exist_ok=True)
        with target_ini.open("xb") as handle:
            handle.write(b"[VideoOptions]\r\nResolutionWidth=1280\r\nResolutionHeight=800\r\nFullScreen=0\r\nRefreshRate=60\r\n")
    record = inside(c.data / ("game-setup-" + game["appid"] + ".json"), c.root)
    temporary = record.with_name(record.name + "." + identifier + ".tmp")
    temporary.write_text(json.dumps(receipt, indent=2) + "\n")
    temporary.chmod(0o600)
    temporary.replace(record)
    commands = ["setlocal DisableDelayedExpansion", f'cd /d "{stage_windows}"']
    if fresh_ini:
        manager._write_registry({"retina": {"type": "REG_SZ", "value": "N"},
                                 "dpi": {"type": "REG_DWORD", "value": 96}})
    # No silent/quiet switches: users see and accept each supplied license.
    for name in ("vcredist_x86.exe", "PhysX_9.09.0408_SystemSoftware.exe", "DXSETUP.exe"):
        actual = next(path.name for path in files if path.name.casefold() == name.casefold())
        commands.extend([f'"{stage_windows}\\{actual}"', "if errorlevel 1 goto failed"])
    commands.extend(['echo PREREQUISITES_COMPLETE>result.txt',
                     f'"{config_windows}" -p -c "{game_windows}" -f "{launcher_windows}"',
                     "exit /b 0", ":failed", "echo INSTALLER_FAILED_%errorlevel%>result.txt", "exit /b 1"])
    process, log = c.run_batch("game-setup", "\n".join(commands))
    if process.poll() not in (None, 0):
        raise SetupError("The prerequisite sequence could not start. Its receipt, backup and log are preserved; retry Finish game setup.")
    c.save_state(selected_appid=game["appid"])
    return {"ok": True, "message": "Complete the supplied VC++, PhysX and DirectX installer windows, reviewing their licenses. Then finish and close Dragon Age's configuration window. Steam may run its remaining first-launch setup when you press Play.", "log": str(log)}
