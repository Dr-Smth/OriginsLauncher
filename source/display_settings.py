"""Display-only presets for an existing, isolated DA:O Wine installation.

No game is launched, no screen mode is changed, and no gameplay validation is
created here. Callers serialize mutations with Controller.operation().
"""
from __future__ import annotations

import configparser
import ctypes
import datetime as dt
import hashlib
import json
import math
import os
from pathlib import Path
import re
import subprocess
import time
import uuid

from steam_state import discover_games
from profile_paths import documents_path


class DisplayError(ValueError):
    pass


STANDARD_SIZES = [(1280, 720), (1280, 800), (1440, 900), (1600, 900),
                  (1680, 1050), (1920, 1080), (1920, 1200), (1920, 1280),
                  (2560, 1080), (2560, 1440), (2560, 1600), (3440, 1440),
                  (3840, 1600), (3840, 2160), (5120, 1440), (5120, 2880)]
VIDEO_KEYS = {"width": "ResolutionWidth", "height": "ResolutionHeight",
              "fullscreen": "FullScreen", "refresh_rate": "RefreshRate"}
REGISTRY_TARGETS = {"retina": (r"Software\Wine\Mac Driver", "RetinaMode"),
                    "dpi": (r"Control Panel\Desktop", "LogPixels")}
BLOCKED_IMAGES = {"daorigins.exe", "daoriginsconfig.exe", "daoriginslauncher.exe",
                  "msiexec.exe", "dxsetup.exe", "vcredist_x86.exe", "vcredist_x64.exe",
                  "physx_9.09.0408_systemsoftware.exe", "dauservicesetup_steam.exe",
                  "daou_updateaddinsxml_steam.exe"}


def _now():
    return dt.datetime.now(dt.timezone.utc).isoformat()


def _image(command):
    command = command.lstrip()
    if command.startswith('"'):
        end = command.find('"', 1)
        if end < 0 or (command[end + 1:] and not command[end + 1].isspace()):
            return ""
        path = command[1:end]
    else:
        match = re.match(r'([^"\r\n]*?\.exe)(?=\s|$)', command, re.I)
        if not match:
            return ""
        path = match.group(1)
        if any(c.isspace() for c in path) and not re.match(r"(?:[a-z]:[\\/]|\\\\)", path, re.I):
            return ""
    return re.split(r"[\\/]", path)[-1].casefold()


def _patch_ini(raw, section, changes):
    """Replace only named keys, preserving unrelated bytes and line endings."""
    try:
        text = raw.decode("utf-8-sig")
        parser = configparser.ConfigParser(interpolation=None)
        parser.read_string(text)
    except (UnicodeError, configparser.Error) as exc:
        raise DisplayError("The settings file is not a supported INI file.") from exc
    if not parser.has_section(section):
        raise DisplayError(f"The settings file has no [{section}] section.")
    lines = text.splitlines(keepends=True)
    current, found, result = None, set(), []
    newline = "\r\n" if "\r\n" in text else "\n"
    pending = {key.casefold(): (key, value) for key, value in changes.items()}

    def insert_missing():
        if result and not result[-1].endswith(("\n", "\r")):
            result[-1] += newline
        for folded, (key, value) in pending.items():
            if folded not in found:
                result.append(f"{key}={value}{newline}")
                found.add(folded)

    for line in lines:
        heading = re.match(r"^\s*\[([^]]+)\]", line)
        if heading:
            if current == section:
                insert_missing()
            current = heading.group(1)
        match = re.match(r"^(\s*)([^=;#\s]+)(\s*=\s*)([^\r\n]*)(\r?\n)?$", line)
        if current == section and match and match.group(2).casefold() in pending:
            folded = match.group(2).casefold()
            if folded in found:
                raise DisplayError("Duplicate display setting; repair the INI before applying a preset.")
            found.add(folded)
            line = match.group(1) + match.group(2) + match.group(3) + str(pending[folded][1]) + (match.group(5) or "")
        result.append(line)
    if current == section:
        insert_missing()
    return (b"\xef\xbb\xbf" if raw.startswith(b"\xef\xbb\xbf") else b"") + "".join(result).encode("utf-8")


class DisplaySettings:
    def __init__(self, controller, appid=None):
        self.c = controller
        self.appid = appid
        self.root = self.c.root.resolve()
        self.prefix = self._safe(self.c.prefix, self.root)
        self.data = self._safe(self.c.data, self.root)
        self.state_path = self.data / "display-settings.json"
        self.backups = self.data / "display-backups"

    @property
    def ini(self):
        return documents_path(self.prefix) / "BioWare/Dragon Age/Settings/DragonAge.ini"

    @staticmethod
    def _safe(path, base):
        try:
            resolved = Path(path).resolve()
            resolved.relative_to(Path(base).resolve())
            return resolved
        except (OSError, ValueError, RuntimeError) as exc:
            raise DisplayError("A display settings path escapes its game folder or contains a broken link.") from exc

    def _read(self, path, base=None, limit=1024 * 1024):
        path = self._safe(path, base or self.root)
        try:
            if not path.is_file():
                raise DisplayError(f"Required settings file is missing: {path.name}.")
            with path.open("rb") as handle:
                value = handle.read(limit + 1)
        except OSError as exc:
            raise DisplayError(f"Settings file could not be read: {path.name}.") from exc
        if len(value) > limit:
            raise DisplayError(f"Settings file is unexpectedly large: {path.name}.")
        return value

    def _atomic(self, path, raw):
        path = self._safe(path, self.root)
        self._safe(path.parent, self.root).mkdir(parents=True, exist_ok=True)
        temporary = path.with_name("." + path.name + "." + uuid.uuid4().hex + ".tmp")
        mode = path.stat().st_mode & 0o777 if path.exists() else 0o600
        try:
            with temporary.open("xb") as handle:
                handle.write(raw)
                handle.flush()
                os.fsync(handle.fileno())
            temporary.chmod(mode)
            temporary.replace(path)
        finally:
            if temporary.exists():
                temporary.unlink()

    def _json(self, path, value):
        self._atomic(path, (json.dumps(value, indent=2, sort_keys=True) + "\n").encode())

    def _state(self):
        if not self.state_path.exists() and not self.state_path.is_symlink():
            return {"schema_version": 1, "pending_confirmation": False, "recovery_required": False}
        try:
            state = json.loads(self._read(self.state_path, limit=65536))
            if (not isinstance(state, dict) or state.get("schema_version") != 1
                    or type(state.get("pending_confirmation")) is not bool
                    or type(state.get("recovery_required")) is not bool):
                raise ValueError()
            for key in ("working_snapshot", "previous_snapshot"):
                if state.get(key) is not None and not re.fullmatch(r"[0-9a-f]{32}", str(state[key])):
                    raise ValueError()
            transaction = state.get("transaction")
            if isinstance(transaction, dict) and transaction.get("phase") in ("preparing", "changing"):
                state["recovery_required"] = True  # An interrupted transaction is never a clean state.
            return state
        except (ValueError, RuntimeError, OSError) as exc:
            raise DisplayError("The display recovery record is invalid. Preserve data/display-backups and repair the record before changing settings.") from exc

    def _game(self):
        games = [g for g in discover_games(self.prefix) if g["complete"]]
        selected = self.appid if self.appid is not None else self.c.state().get("selected_appid")
        game = next((g for g in games if g["appid"] == selected), None)
        if game is None and self.appid is None:
            game = next(iter(games), None)
        if not game:
            raise DisplayError("Finish installing Dragon Age before changing its display settings.")
        self._safe(game["exe"], self.prefix)
        return game

    def _probe(self):
        candidates = [Path(__file__).resolve().parent / "display-probe", self.root / "source/display-probe"]
        probe = next((p for p in candidates if p.is_file() and os.access(p, os.X_OK)), None)
        if probe is None:
            raise DisplayError("The display probe is missing. Restore the launcher app before choosing a display preset.")
        try:
            result = subprocess.run([str(probe)], capture_output=True, text=True, timeout=8)
            if result.returncode or len(result.stdout) > 65536:
                raise ValueError()
            inventory = json.loads(result.stdout)
            if not isinstance(inventory, dict) or inventory.get("schema_version") != 1:
                raise ValueError()
            main_id = inventory.get("main_display_id")
            displays = inventory.get("displays")
            if not isinstance(main_id, str) or not isinstance(displays, list):
                raise ValueError()
            matches = [d for d in displays if isinstance(d, dict) and d.get("id") == main_id]
            if len(matches) != 1 or matches[0].get("is_main") is not True:
                raise ValueError()
            display = dict(matches[0])
            for key in ("logical_width", "logical_height", "pixel_width", "pixel_height", "available_pixel_width", "available_pixel_height"):
                if type(display.get(key)) is not int or not 0 < display[key] <= 16384:
                    raise ValueError()
            for key in ("scale", "refresh_rate"):
                if type(display.get(key)) not in (int, float) or not math.isfinite(display[key]):
                    raise ValueError()
            if display["scale"] <= 0 or display["refresh_rate"] < 0:
                raise ValueError()
            if not isinstance(display.get("name"), str) or not isinstance(display.get("builtin"), bool):
                raise ValueError()
            return display
        except (OSError, ValueError, RuntimeError, subprocess.TimeoutExpired) as exc:
            raise DisplayError("The current main display could not be read. Reconnect it and try again; no settings changed.") from exc

    @staticmethod
    def _display_signature(display):
        return {key: display[key] for key in ("id", "name", "builtin", "logical_width", "logical_height", "pixel_width", "pixel_height", "scale", "refresh_rate")}

    def _registry(self):
        text = self._read(self.prefix / "user.reg", self.prefix, limit=16 * 1024 * 1024).decode("utf-8", errors="replace")
        values = {}
        for label, (section, key) in REGISTRY_TARGETS.items():
            escaped = section.replace("\\", "\\\\")
            found = re.findall(r"^\[" + re.escape(escaped) + r"\][^\n]*\n((?:(?!\[).*(?:\n|$))*)", text, re.M | re.I)
            entries = re.findall(r'^"' + re.escape(key) + r'"=(.*)$', found[0], re.M | re.I) if len(found) == 1 else []
            if len(found) > 1 or len(entries) > 1:
                raise DisplayError("Duplicate Wine display registry values; inspect the runtime before changing settings.")
            if not entries:
                values[label] = None
            elif label == "retina" and re.fullmatch(r'"[YNyn]"', entries[0].strip()):
                values[label] = {"type": "REG_SZ", "value": entries[0].strip()[1:-1]}
            elif label == "dpi" and re.fullmatch(r"dword:[0-9a-fA-F]{1,8}", entries[0].strip()):
                values[label] = {"type": "REG_DWORD", "value": int(entries[0].strip()[6:], 16)}
            else:
                raise DisplayError("A Wine display registry value has an unsupported type. No settings changed.")
        return values

    def _mod(self, game):
        folder = self._safe(Path(game["exe"]).parent, self.prefix)
        paths = [folder / n for n in ("DAFix.ini", "DAFix.asi", "dinput8.dll")]
        for path in paths:
            self._safe(path, self.prefix)
        available = all(path.is_file() for path in paths)
        if not available:
            return None, 1.0
        try:
            config = configparser.ConfigParser(interpolation=None)
            config.read_string(self._read(paths[0], self.prefix).decode("utf-8-sig"))
            scale = config.getfloat("HUD Scale", "Scale")
            if not math.isfinite(scale) or not 0 <= scale <= 1:
                raise ValueError()
            return paths[0], scale
        except (ValueError, configparser.Error) as exc:
            raise DisplayError("DAFix.ini has an invalid HUD Scale. Repair it before changing display settings.") from exc

    def _borderless(self, game):
        mod, _ = self._mod(game)
        if mod is None:
            return False
        try:
            config = configparser.ConfigParser(interpolation=None)
            config.read_string(self._read(mod, self.prefix).decode("utf-8-sig"))
            return config.getboolean("Borderless Windowed", "Enabled")
        except (ValueError, configparser.Error) as exc:
            raise DisplayError("DAFix.ini has an invalid Borderless Windowed setting. Repair it before changing display settings.") from exc

    def _current(self, game):
        try:
            ini = configparser.ConfigParser(interpolation=None)
            ini.read_string(self._read(self.ini, self.prefix).decode("utf-8-sig"))
            width, height = ini.getint("VideoOptions", "ResolutionWidth"), ini.getint("VideoOptions", "ResolutionHeight")
            fullscreen = ini.get("VideoOptions", "FullScreen").strip()
            refresh = ini.getint("VideoOptions", "RefreshRate", fallback=60)
            if width <= 0 or height <= 0 or fullscreen not in ("0", "1") or refresh < 0:
                raise ValueError()
            registry = self._registry()
            _, scale = self._mod(game)
            borderless = self._borderless(game)
            return {"width": width, "height": height, "fullscreen": fullscreen == "1", "refresh_rate": refresh,
                    "retina": bool(registry["retina"] and registry["retina"]["value"].upper() == "Y"),
                    "dpi": registry["dpi"]["value"] if registry["dpi"] else 96, "hud_scale": scale,
                    "borderless": borderless, "mode": "borderless" if borderless else "fullscreen" if fullscreen == "1" else "windowed"}
        except (ValueError, configparser.Error) as exc:
            raise DisplayError("Current game display settings could not be read. Open the game once or restore its INI file.") from exc

    @staticmethod
    def _hud_scale(width, height, retina, ui_size):
        desired = (0.5 if retina else 1.0) / (1.25 if ui_size == "larger" else 1.0)
        return min(1.0, max(desired, 768.0 / height, 1024.0 / width))

    def _catalog(self, display, mod_available, ui_size="comfortable"):
        if ui_size not in ("comfortable", "larger"):
            raise DisplayError("Choose Comfortable or Larger interface size.")
        twox = (display["pixel_width"] == 2 * display["logical_width"] and
                display["pixel_height"] == 2 * display["logical_height"] and display["scale"] == 2)
        presets = []

        def add(identifier, width, height, fullscreen, retina, title, fit=True):
            hud = self._hud_scale(width, height, retina, ui_size)
            reason = None if fit else "This window does not fit the main display's usable area with its title bar."
            if fit and hud < 1 and not mod_available:
                reason = "DAFix UI scaling is required for this mode. Install DAFix before selecting it; nothing is downloaded automatically."
            presets.append({"id": identifier, "title": title, "detail": ("Sharper, with more rendering work; check picture, input and readability." if retina else "Lower rendering load; check picture, input and readability."),
                            "width": width, "height": height, "fullscreen": fullscreen, "retina": retina,
                            "available": reason is None, "reason": reason, "verification": "first_run_check", "hud_scale": hud,
                            "borderless": False, "mode": "fullscreen" if fullscreen else "windowed"})

        add("fullscreen", display["logical_width"], display["logical_height"], True, False, "Fullscreen — lighter")
        if twox:
            add("fullscreen-retina", display["pixel_width"], display["pixel_height"], True, True, "Fullscreen — sharper Retina")
        for width, height in STANDARD_SIZES:
            normal = (width + 16 <= display["available_pixel_width"] / display["scale"] and
                      height + 40 <= display["available_pixel_height"] / display["scale"])
            retina_fit = twox and width + 32 <= display["available_pixel_width"] and height + 80 <= display["available_pixel_height"]
            add(f"windowed-{width}x{height}", width, height, False, not normal and bool(retina_fit),
                f"{width} × {height} — windowed", normal or retina_fit)
        return presets

    def _processes(self):
        """Strict owned-process inventory: inspection failure is not an idle session."""
        try:
            result = subprocess.run(["/bin/ps", "-axo", "pid=,ppid=,command="], capture_output=True, text=True, timeout=5)
            if result.returncode:
                raise OSError("process list unavailable")
            rows = []
            for line in result.stdout.splitlines():
                parts = line.strip().split(None, 2)
                if len(parts) == 3 and parts[0].isdigit() and parts[1].isdigit():
                    rows.append((int(parts[0]), int(parts[1]), parts[2]))
            if not rows:
                raise OSError("process list was empty or could not be parsed")
            library = ctypes.CDLL("/usr/lib/libproc.dylib")
            library.proc_pidpath.argtypes = [ctypes.c_int, ctypes.c_void_p, ctypes.c_uint32]
            library.proc_pidpath.restype = ctypes.c_int
            own = set()
            for pid, _, command in rows:
                if ".exe" not in command.casefold() and str(self.c.runtime) not in command:
                    continue
                buffer = ctypes.create_string_buffer(4096)
                if library.proc_pidpath(pid, buffer, len(buffer)) <= 0:
                    try:
                        os.kill(pid, 0)
                    except ProcessLookupError:
                        continue
                    raise OSError("process executable unavailable")
                actual = Path(os.fsdecode(buffer.value)).resolve()
                if self.c.runtime.resolve() in actual.parents:
                    own.add(pid)
            while True:
                expanded = own | {pid for pid, parent, _ in rows if parent in own}
                if expanded == own:
                    break
                own = expanded
            return [row for row in rows if row[0] in own]
        except (OSError, RuntimeError, AttributeError, subprocess.TimeoutExpired) as exc:
            raise DisplayError("Process visibility is unavailable. Close the game and retry; settings cannot safely change yet.") from exc

    def _guard(self):
        rows = self._processes()
        for _, _, command in rows:
            name = _image(command)
            if name in BLOCKED_IMAGES or (name and any(word in name for word in ("setup", "install", "vcredist"))):
                raise DisplayError("Save and close Dragon Age, its Windows launcher/configuration utility, and prerequisite installers before changing display settings.")
        return rows

    def _stop_prefix(self):
        configure = str(self.c.contents / "Configure.app/Contents/MacOS/Configure")
        rows = [r for r in self._guard() if r[2].strip('"') != configure]
        if not rows:
            return
        self.c.stop()
        try:
            subprocess.run([str(self.c.wineserver), "-w"], env=self.c.env(), capture_output=True, timeout=20, check=True)
        except (OSError, subprocess.SubprocessError) as exc:
            raise DisplayError("The game's Wine session has not finished closing. Retry after its windows close.") from exc
        deadline = time.monotonic() + 20
        while time.monotonic() < deadline:
            if not [r for r in self._processes() if r[2].strip('"') != configure]:
                return
            time.sleep(0.25)
        raise DisplayError("The game's runtime wrapper is still closing. No new Wine session will be started.")

    def _signature(self, game):
        executable = self._safe(game["exe"], self.prefix)
        stat = executable.stat()
        mod, _ = self._mod(game)
        signatures = {}
        if mod:
            for name in ("DAFix.asi", "dinput8.dll"):
                signatures[name] = hashlib.sha256(self._read(mod.parent / name, self.prefix, limit=32 * 1024 * 1024)).hexdigest()
        return {"appid": game["appid"], "exe_size": stat.st_size, "exe_mtime_ns": stat.st_mtime_ns,
                "settings": self._current(game), "mod_files": signatures}

    def _snapshot(self, game, display):
        identifier = uuid.uuid4().hex
        folder = self._safe(self._safe(self.backups / identifier, self.data), self.root)
        folder.mkdir(parents=True, exist_ok=False)
        self._atomic(folder / "DragonAge.ini", self._read(self.ini, self.prefix))
        mod, _ = self._mod(game)
        if mod:
            self._atomic(folder / "DAFix.ini", self._read(mod, self.prefix))
        snapshot = {"schema_version": 1, "id": identifier, "created_at": _now(), "appid": game["appid"],
                    "registry": self._registry(), "settings": self._current(game),
                    "signature": self._signature(game), "display": self._display_signature(display), "mod_present": mod is not None}
        self._json(folder / "snapshot.json", snapshot)
        return identifier

    def _load_snapshot(self, identifier):
        if not isinstance(identifier, str) or not re.fullmatch(r"[0-9a-f]{32}", identifier):
            raise DisplayError("The display backup reference is invalid.")
        try:
            value = json.loads(self._read(self.backups / identifier / "snapshot.json", self.data, limit=65536))
            if not isinstance(value, dict) or value.get("schema_version") != 1 or value.get("id") != identifier:
                raise ValueError()
            settings = value["settings"]
            if any(type(settings.get(k)) is not int or not 0 < settings[k] <= 16384 for k in ("width", "height")) or type(settings.get("fullscreen")) is not bool:
                raise ValueError()
            if type(settings.get("refresh_rate")) is not int or not 0 <= settings["refresh_rate"] <= 1000:
                raise ValueError()
            if type(settings.get("borderless")) is not bool or settings.get("mode") != ("borderless" if settings["borderless"] else "fullscreen" if settings["fullscreen"] else "windowed"):
                raise ValueError()
            for label in REGISTRY_TARGETS:
                entry = value["registry"][label]
                if entry is not None and (not isinstance(entry, dict) or
                        (label == "retina" and (entry.get("type") != "REG_SZ" or entry.get("value") not in ("Y", "N", "y", "n"))) or
                        (label == "dpi" and (entry.get("type") != "REG_DWORD" or type(entry.get("value")) is not int or not 0 <= entry["value"] <= 0xffffffff))):
                    raise ValueError()
            if type(value.get("mod_present")) is not bool or type(settings.get("hud_scale")) not in (int, float) or not 0 <= settings["hud_scale"] <= 1:
                raise ValueError()
            return value
        except (OSError, ValueError, TypeError, KeyError, RuntimeError) as exc:
            raise DisplayError("The display backup is incomplete or invalid. Preserve it for recovery; no settings changed.") from exc

    def _write_registry(self, values):
        support = self._safe(self.prefix / "drive_c/dao-support", self.prefix)
        report = support / ("display-registry-" + uuid.uuid4().hex + ".txt")
        winreport = "C:\\dao-support\\" + report.name
        commands = []
        for label, (section, key) in REGISTRY_TARGETS.items():
            entry = values[label]
            if entry is None:
                commands.append(f'reg delete "HKCU\\{section}" /v {key} /f >nul 2>&1')
            else:
                commands.extend([f'reg add "HKCU\\{section}" /v {key} /t {entry["type"]} /d {entry["value"]} /f', 'if errorlevel 1 exit /b 1'])
        for index, (section, key) in enumerate(REGISTRY_TARGETS.values()):
            commands.append(f'reg query "HKCU\\{section}" /v {key} {">" if index == 0 else ">>"} "{winreport}" 2>&1')
        commands.append(f'echo DAO_DISPLAY_REGISTRY_COMPLETE >> "{winreport}"')
        process, _ = self.c.run_batch("display-registry", "\n".join(commands))
        deadline = time.monotonic() + 45
        while time.monotonic() < deadline:
            if report.is_file():
                output = self._read(report, self.prefix, limit=65536).decode("utf-8", errors="replace")
                if "DAO_DISPLAY_REGISTRY_COMPLETE" in output:
                    for label, (_, key) in REGISTRY_TARGETS.items():
                        expected = values[label]
                        match = re.search(re.escape(key) + r"\s+(REG_SZ|REG_DWORD)\s+([^\r\n]+)", output, re.I)
                        if expected is None and match:
                            raise DisplayError("The Wine display registry deletion did not verify.")
                        if expected is not None:
                            actual = int(match.group(2).strip(), 0) if match and expected["type"] == "REG_DWORD" else match.group(2).strip() if match else None
                            if not match or match.group(1).upper() != expected["type"] or actual != expected["value"]:
                                raise DisplayError("The Wine display registry update did not verify.")
                    self._stop_prefix()
                    if self._registry() != values:
                        raise DisplayError("The Wine display registry update did not persist after the session closed.")
                    return
            if process.poll() not in (None, 0):
                raise DisplayError("The Wine display registry operation failed. Inspect the launcher logs.")
            time.sleep(0.25)
        raise DisplayError("The Wine display registry operation did not finish. Its recovery record has been preserved.")

    def _write_settings(self, game, settings, mod_required=False):
        changes = {name: str(int(settings[key])) for key, name in VIDEO_KEYS.items()}
        self._atomic(self.ini, _patch_ini(self._read(self.ini, self.prefix), "VideoOptions", changes))
        mod, _ = self._mod(game)
        if mod:
            raw = _patch_ini(self._read(mod, self.prefix), "HUD Scale", {"Scale": format(settings["hud_scale"], ".10g")})
            raw = _patch_ini(raw, "Borderless Windowed", {"Enabled": "true" if settings["borderless"] else "false"})
            self._atomic(mod, raw)
        elif mod_required or settings["hud_scale"] < 1 or settings["borderless"]:
            raise DisplayError("DAFix UI scaling is missing; its HUD setting could not be applied.")

    def _assert_display(self, expected):
        if self._display_signature(self._probe()) != self._display_signature(expected):
            raise DisplayError("The main display changed during this operation. Refresh the presets and try again.")

    def _restore_blocked_reason(self, snapshot, display):
        settings = snapshot["settings"]
        twox = (display["pixel_width"] == 2 * display["logical_width"] and
                display["pixel_height"] == 2 * display["logical_height"] and display["scale"] == 2)
        if settings["retina"] and not twox:
            return "The saved Retina settings need a display with matching 2× backing dimensions. Reconnect that display or apply a current preset."
        if settings["fullscreen"] or settings["borderless"]:
            if snapshot.get("display") != self._display_signature(display):
                return "The saved full-screen settings belong to a different display configuration. Reconnect that display or apply a preset for this display."
            expected = (display["pixel_width"], display["pixel_height"]) if settings["retina"] else (display["logical_width"], display["logical_height"])
            if (settings["width"], settings["height"]) != expected:
                return "The saved full-screen dimensions do not match this display. Apply a current preset instead."
        else:
            coordinate_scale = 2 if settings["retina"] else 1
            width = display["available_pixel_width"] / display["scale"] * coordinate_scale
            height = display["available_pixel_height"] / display["scale"] * coordinate_scale
            if settings["width"] + 16 * coordinate_scale > width or settings["height"] + 40 * coordinate_scale > height:
                return "The saved window no longer fits this display's usable area. Apply a smaller windowed preset instead."
        return None

    def _restore_snapshot(self, snapshot, game, expected_display=None):
        if snapshot["appid"] != game["appid"]:
            raise DisplayError("The display backup belongs to another game edition.")
        self._guard()
        self._stop_prefix()
        if expected_display:
            self._assert_display(expected_display)
            reason = self._restore_blocked_reason(snapshot, expected_display)
            if reason:
                raise DisplayError(reason)
        self._write_registry(snapshot["registry"])
        if expected_display:
            self._assert_display(expected_display)
        self._write_settings(game, snapshot["settings"], snapshot["mod_present"])
        actual = self._current(game)
        if any(actual[key] != value if key != "hud_scale" else not math.isclose(actual[key], value, abs_tol=1e-9)
               for key, value in snapshot["settings"].items()):
            raise DisplayError("Restored display settings did not verify. The recovery snapshot has been preserved.")

    def options(self):
        display, game, state = self._probe(), self._game(), self._state()
        mod, _ = self._mod(game)
        current = self._current(game)
        presets = self._catalog(display, mod is not None)
        candidate = state.get("candidate")
        signature = self._signature(game)
        if isinstance(candidate, dict) and candidate.get("signature") == signature:
            current.update(preset_id=candidate.get("preset_id"), ui_size=candidate.get("ui_size"))
        if not current.get("preset_id"):
            for ui_size in ("comfortable", "larger"):
                for preset in self._catalog(display, mod is not None, ui_size):
                    if (current["dpi"] == 96 and all(current[key] == preset[key] for key in ("width", "height", "fullscreen", "retina", "borderless", "mode"))
                            and math.isclose(current["hud_scale"], preset["hud_scale"], abs_tol=1e-9)):
                        current.update(preset_id=preset["id"], ui_size=ui_size)
                        break
                if current.get("preset_id"):
                    break
        if state.get("working_snapshot") and state.get("confirmation_source") == "user_display_check":
            working = self._load_snapshot(state["working_snapshot"])
            old_signature = working.get("signature", {})
            if (working.get("display") == self._display_signature(display)
                    and all(old_signature.get(key) == signature.get(key) for key in ("appid", "exe_size", "exe_mtime_ns", "mod_files"))):
                for preset in presets:
                    expected = {key: preset[key] for key in ("width", "height", "fullscreen", "retina", "hud_scale", "borderless", "mode")}
                    expected["dpi"] = 96
                    if all(working["settings"].get(key) == value for key, value in expected.items()):
                        preset["verification"] = "previously_tested_on_this_mac"
        reason = None
        can_restore = False
        restore_reason = None
        try:
            self._guard()
            if state.get("working_snapshot"):
                restore_reason = self._restore_blocked_reason(self._load_snapshot(state["working_snapshot"]), display)
                can_restore = restore_reason is None
            if state.get("recovery_required"):
                raise DisplayError("A previous change needs recovery. Restore working settings before applying another preset.")
        except DisplayError as exc:
            reason = str(exc)
            if not can_restore and not restore_reason:
                restore_reason = reason
        return {"ok": True, "display": display, "presets": presets, "current": current,
                "can_apply": reason is None, "blocked_reason": reason,
                "restore_available": bool(state.get("working_snapshot")),
                "can_restore": can_restore,
                "restore_blocked_reason": restore_reason,
                "pending_confirmation": state["pending_confirmation"], "ui_scaling_available": mod is not None,
                "can_confirm": bool(not state.get("recovery_required") and state["pending_confirmation"] and isinstance(candidate, dict) and candidate.get("signature") == signature
                                    and candidate.get("display") == self._display_signature(display))}

    @staticmethod
    def _matches_preset(settings, preset):
        # RefreshRate in the game's INI need not equal the actual display rate.
        return (settings.get("dpi") == 96
                and all(settings.get(key) == preset[key] for key in
                        ("width", "height", "fullscreen", "retina", "borderless", "mode"))
                and type(settings.get("hud_scale")) in (int, float)
                and math.isclose(settings["hud_scale"], preset["hud_scale"], abs_tol=1e-9))

    def prepare_for_play(self, preset_id, ui_size="comfortable"):
        """Prepare one launch without treating selection as human validation."""
        display, game, state = self._probe(), self._game(), self._state()
        mod, _ = self._mod(game)
        preset = next((p for p in self._catalog(display, mod is not None, ui_size) if p["id"] == preset_id), None)
        if not preset or not preset["available"]:
            raise DisplayError(preset["reason"] if preset else "That preset is not available for the current main display.")
        self._guard()
        if not state.get("recovery_required") and self._matches_preset(self._current(game), preset):
            return {"ok": True, "changed": False, "message": "The selected display settings are already in use."}
        if state.get("working_snapshot") and state.get("confirmation_source") == "user_display_check":
            working = self._load_snapshot(state["working_snapshot"])
            old_signature = working.get("signature")
            signature = self._signature(game)
            if (isinstance(old_signature, dict)
                    and working.get("display") == self._display_signature(display)
                    and all(old_signature.get(key) == signature[key] for key in
                            ("appid", "exe_size", "exe_mtime_ns", "mod_files"))
                    and self._matches_preset(working["settings"], preset)):
                self.restore()
                return {"ok": True, "changed": True, "message": "Your confirmed display settings are ready."}
        self.apply(preset_id, ui_size)
        return {"ok": True, "changed": True, "message": "The selected display settings are ready for this launch."}

    def apply(self, preset_id, ui_size="comfortable"):
        display, game, state = self._probe(), self._game(), self._state()
        if state.get("recovery_required"):
            raise DisplayError("Restore working settings to recover the previous change before applying another preset.")
        mod, _ = self._mod(game)
        preset = next((p for p in self._catalog(display, mod is not None, ui_size) if p["id"] == preset_id), None)
        if not preset or not preset["available"]:
            raise DisplayError(preset["reason"] if preset else "That preset is not available for the current main display.")
        self._guard()
        self._current(game)  # Refuse missing/invalid settings before creating a journal.
        state.update(pending_confirmation=True, recovery_required=False, candidate=None,
                     transaction={"id": uuid.uuid4().hex, "action": "apply", "phase": "preparing", "started_at": _now()})
        self._json(self.state_path, state)
        previous = None
        try:
            self._stop_prefix()
            self._assert_display(display)
            previous = self._snapshot(game, display)
            state["previous_snapshot"] = previous
            if not state.get("working_snapshot"):
                state["working_snapshot"] = previous
            state["transaction"]["phase"] = "changing"
            self._json(self.state_path, state)
            settings = {key: preset[key] for key in ("width", "height", "fullscreen", "retina", "hud_scale", "borderless", "mode")}
            settings.update(dpi=96, refresh_rate=max(1, int(math.floor(display["refresh_rate"] + 0.5))) if display["refresh_rate"] else 60)
            registry = {"retina": {"type": "REG_SZ", "value": "Y" if settings["retina"] else "N"}, "dpi": {"type": "REG_DWORD", "value": 96}}
            self._write_registry(registry)
            self._assert_display(display)
            self._write_settings(game, settings, settings["hud_scale"] < 1)
            actual = self._current(game)
            if any(actual[key] != value if key != "hud_scale" else not math.isclose(actual[key], value, abs_tol=1e-9) for key, value in settings.items()):
                raise DisplayError("The display settings did not match the requested preset after writing.")
            state.update(candidate={"preset_id": preset_id, "ui_size": ui_size, "signature": self._signature(game), "display": self._display_signature(display)}, pending_confirmation=True)
            state["transaction"].update(phase="awaiting_confirmation", finished_at=_now())
            self._json(self.state_path, state)
            return {"ok": True, "message": "Display settings applied. Use Play, check the picture, mouse and interface, then choose Keep settings. The game was not launched."}
        except Exception as exc:
            self._failed(state, previous, game, exc)

    def _failed(self, state, previous, game, error):
        rollback_error = None
        if previous:
            try:
                self._restore_snapshot(self._load_snapshot(previous), game)
            except Exception as exc:
                rollback_error = str(exc)
        state.update(recovery_required=rollback_error is not None, pending_confirmation=True)
        state["transaction"].update(phase="recovery_required" if rollback_error else "failed_rolled_back" if previous else "failed_before_change", error=str(error), rollback_error=rollback_error, finished_at=_now())
        self._json(self.state_path, state)
        suffix = "Previous settings were restored." if previous and not rollback_error else "Preserve data/display-backups and use Restore working settings; recovery is still required." if rollback_error else "No display settings were changed."
        raise DisplayError(f"The display change failed: {error} {suffix}") from error

    def restore(self):
        display, game, state = self._probe(), self._game(), self._state()
        snapshot = self._load_snapshot(state.get("working_snapshot"))
        reason = self._restore_blocked_reason(snapshot, display)
        if reason:
            raise DisplayError(reason)
        self._guard()
        state.update(pending_confirmation=True, transaction={"id": uuid.uuid4().hex, "action": "restore", "phase": "preparing", "started_at": _now()})
        self._json(self.state_path, state)
        previous = None
        try:
            self._stop_prefix()
            previous = self._snapshot(game, display)
            state["previous_snapshot"] = previous
            self._json(self.state_path, state)
            self._restore_snapshot(snapshot, game, display)
            state.update(pending_confirmation=False, recovery_required=False, candidate=None)
            state["transaction"].update(phase="restored", finished_at=_now())
            self._json(self.state_path, state)
            return {"ok": True, "message": "Working display settings restored. Other graphics, audio and saves were preserved. Use Play when ready."}
        except Exception as exc:
            self._failed(state, previous, game, exc)

    def confirm(self):
        display, game, state = self._probe(), self._game(), self._state()
        if state.get("recovery_required"):
            raise DisplayError("Restore working settings before confirming another display mode.")
        signature = self._signature(game)
        if state["pending_confirmation"]:
            candidate = state.get("candidate")
            if (not isinstance(candidate, dict) or candidate.get("signature") != signature
                    or candidate.get("display") != self._display_signature(display)):
                raise DisplayError("The display or game settings changed since Apply. Apply the intended preset again before keeping it.")
        elif not self.c.compatibility_verified(game):
            raise DisplayError("Apply a preset and check its picture, input and interface before keeping it.")
        working = self._snapshot(game, display)
        if signature != self._signature(game):
            raise DisplayError("Settings changed while confirming. No working snapshot was selected; try again after settings settle.")
        state.update(working_snapshot=working, pending_confirmation=False, recovery_required=False, confirmed_at=_now(), confirmation_source="user_display_check")
        self._json(self.state_path, state)
        return {"ok": True, "message": "These display settings are now your working restore point. This records your display check, not a new gameplay or save/load test."}
