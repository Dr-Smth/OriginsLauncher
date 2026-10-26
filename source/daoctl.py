#!/usr/bin/env python3
"""Local DA:O compatibility controller. No Windows VM or global Wine state.

Every launched Windows process uses the pinned, project-owned Sikarugir wrapper.
Opening the GUI calls status only. No credentials are read or copied.
"""
from __future__ import annotations

import argparse
import configparser
import contextlib
import ctypes
import datetime as dt
import fcntl
import hashlib
import json
import os
from pathlib import Path
import platform
import plistlib
import re
import shutil
import signal
import subprocess
import sys
import time
import urllib.request

from steam_state import GAMES, discover_games, find_steam
from profile_paths import ProfileError, assert_contained, documents_path, localize_user_folders

STEAM_URL = "https://cdn.akamai.steamstatic.com/client/installer/SteamSetup.exe"
BOOTSTRAP_TAIL_BYTES = 16 * 1024
STEAM_HANDOFF_GRACE_SECONDS = 60


def platform_status() -> dict:
    """Read-only requirements for this pinned D9VK runtime, not every Wine build."""
    try:
        major = int(platform.mac_ver()[0].split('.')[0])
    except (ValueError, IndexError):
        major = 0
    apple_silicon = platform.machine().lower() == "arm64"
    if sys.platform == "darwin" and not apple_silicon:
        try:
            result = subprocess.run(["/usr/sbin/sysctl", "-n", "hw.optional.arm64"],
                                    capture_output=True, text=True, timeout=3)
            apple_silicon = result.returncode == 0 and result.stdout.strip() == "1"
        except (OSError, subprocess.TimeoutExpired):
            pass
    supported = sys.platform == "darwin" and major >= 26 and apple_silicon
    rosetta = supported and Path("/Library/Apple/usr/libexec/oah/libRosettaRuntime").is_file()
    if not supported:
        phase, message = "unsupported_platform", "This release requires an Apple silicon Mac running macOS 26 or later for its DirectX 9 renderer. No runtime has been installed."
    elif not rosetta:
        phase, message = "rosetta_required", "Open the Apple Rosetta installer, complete its prompts, then refresh. The launcher never accepts Apple's license for you."
    else:
        phase, message = "supported", "This Mac meets the runtime platform requirements."
    return dict(platform_supported=supported, rosetta_ready=bool(rosetta), phase=phase, message=message)


def windows_process_is(command: str, image_name: str) -> bool:
    """Match the leading Windows image, never an executable named in arguments.

    Wine's ps display may omit quotes around a Windows path containing spaces.
    In that form the first .exe boundary ends the image; do not scan past it.
    Process ownership must still be established separately by processes().
    """
    command = command.lstrip()
    if command.startswith('"'):
        end = command.find('"', 1)
        if end < 0 or (command[end + 1:] and not command[end + 1].isspace()):
            return False
        image = command[1:end]
    else:
        match = re.match(r'([^"\r\n]*?\.exe)(?=\s|$)', command, re.IGNORECASE)
        if not match:
            return False
        image = match.group(1)
        # Spaces are only accepted in an absolute Windows image path. This
        # prevents a native wrapper such as `python script.py ...game.exe`
        # from being classified by its arguments.
        if any(char.isspace() for char in image) and not re.match(r"(?:[a-z]:[\\/]|\\\\)", image, re.IGNORECASE):
            return False
    return re.split(r"[\\/]", image)[-1].casefold() == image_name.casefold()


def project_root() -> Path:
    if os.environ.get("DAO_PROJECT_ROOT"):
        return Path(os.environ["DAO_PROJECT_ROOT"]).expanduser().resolve()
    here = Path(__file__).resolve()
    if (here.parent.name == "Resources" and here.parent.parent.name == "Contents"
            and here.parents[2].suffix.casefold() == ".app"):
        location = here.parent / "runtime-location.json"
        # A copied app can point at the existing runtime without relocating the
        # game. Only a real app bundle may supply this adjacent configuration.
        if location.exists() or location.is_symlink():
            try:
                with location.open("rb") as handle:
                    raw = handle.read(16385)
                if len(raw) > 16384:
                    raise ValueError("the reference is too large")
                record = json.loads(raw)
                root_value = record.get("root") if isinstance(record, dict) else None
                if not isinstance(root_value, str) or not root_value:
                    raise ValueError("root must be an absolute folder path")
                root = Path(root_value)
                if not root.is_absolute():
                    raise ValueError("root must be an absolute folder path")
                root = root.resolve()
                if not root.is_dir():
                    raise ValueError("the referenced runtime folder is missing")
                return root
            except (OSError, ValueError, RuntimeError) as exc:
                raise DAOError(f"The app's runtime-location.json is invalid or unavailable: {exc}. Restore the runtime reference; no files were moved or reset.") from exc
        return Path.home() / "Library/Application Support/OriginsLauncher"
    if here.parent.name == "source":
        return here.parent.parent
    raise RuntimeError("Run the packaged app or source/daoctl.py, or set DAO_PROJECT_ROOT.")


class DAOError(RuntimeError):
    pass


class Controller:
    def __init__(self, root: Path):
        self.root = root.resolve()
        self.runtime = self.root / "runtime/DAO Runtime.app"
        self.contents = self.runtime / "Contents"
        self.prefix = self.contents / "SharedSupport/prefix"
        self.wine = self.contents / "SharedSupport/wine/bin/wine"
        self.wineserver = self.wine.with_name("wineserver")
        self.launcher = self.contents / "MacOS/wineskinlauncher"
        self.data = self.root / "data"
        self.logs = self.data / "logs"
        self.downloads = self.root / "downloads"
        self.state_file = self.data / "state.json"

    def state(self) -> dict:
        try:
            value = json.loads(self.state_file.read_text())
            return value if isinstance(value, dict) else {}
        except (OSError, ValueError):
            return {}

    def save_state(self, **updates):
        self.data.mkdir(mode=0o700, parents=True, exist_ok=True)
        value = self.state()
        value.update(updates)
        tmp = self.state_file.with_suffix(".tmp")
        tmp.write_text(json.dumps(value, indent=2) + "\n")
        tmp.chmod(0o600)
        tmp.replace(self.state_file)

    def new_log(self, name: str) -> Path:
        self.logs.mkdir(parents=True, exist_ok=True)
        stamp = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%S.%fZ")
        path = self.logs / f"{stamp}-{name}.log"
        path.touch(mode=0o600)
        self.save_state(last_log=str(path))
        return path

    def runtime_ready(self):
        return self.launcher.is_file() and self.wine.is_file() and self.wineserver.is_file()

    def registry_files_ready(self):
        return all((self.prefix / n).is_file() for n in ("system.reg", "user.reg"))

    def prefix_ready(self):
        if not self.registry_files_ready():
            return False
        try:
            self.validate_prefix_scope()
            assert_contained(self.prefix)
            return True
        except (OSError, ValueError, RuntimeError):
            return False

    @property
    def documents(self):
        self.validate_prefix_scope()
        return documents_path(self.prefix)

    def require_contained_profile(self):
        self.require_runtime()
        if not self.registry_files_ready():
            raise DAOError("Finish setting up the Windows environment before opening Steam or the game.")
        try:
            return assert_contained(self.prefix)
        except (OSError, ValueError, RuntimeError) as exc:
            raise DAOError(f"Windows user-folder containment is not ready: {exc} Choose Set up & open Steam to repair local folder links; existing targets are preserved.") from exc

    def validate_prefix_scope(self):
        try:
            self.runtime.resolve().relative_to(self.root)
            self.prefix.resolve().relative_to(self.runtime.resolve())
        except (OSError, ValueError, RuntimeError) as exc:
            raise DAOError("The runtime or prefix points outside this launcher's data folder. No files were changed.") from exc

    def require_runtime(self):
        self.validate_prefix_scope()
        if not self.runtime_ready():
            raise DAOError("The game runtime is not ready. Choose Set up & open Steam first; an incomplete existing runtime is preserved.")

    def require_platform(self):
        observed = platform_status()
        if not observed["platform_supported"] or not observed["rosetta_ready"]:
            raise DAOError(observed["message"])

    def ensure_runtime(self):
        self.require_platform()
        try:
            self.downloads.resolve().relative_to(self.root)
        except ValueError as exc:
            raise DAOError("The download cache points outside this launcher's data folder.") from exc
        if not self.runtime_ready():
            from bootstrap_runtime import BootstrapError, bootstrap
            try:
                bootstrap(self.root, self.downloads / "runtime-cache")
            except BootstrapError as exc:
                raise DAOError(str(exc)) from exc
        self.require_runtime()

    def env(self) -> dict:
        env = os.environ.copy()
        # Do not inherit another Wine session's selection or DLL configuration.
        for key in list(env):
            if key.startswith("WINE") or key in {"DXVK_CONFIG_FILE", "VK_DRIVER_FILES", "VK_ICD_FILENAMES"}:
                env.pop(key, None)
        env.update(WINEPREFIX=str(self.prefix), WINEDEBUG="-all,err+all",
                   DYLD_FALLBACK_LIBRARY_PATH=str(self.contents / "Frameworks"))
        return env

    @contextlib.contextmanager
    def operation(self):
        try:
            self.data.resolve().relative_to(self.root)
        except ValueError as exc:
            raise DAOError("The launcher data directory points outside its dedicated folder.") from exc
        self.data.mkdir(parents=True, exist_ok=True)
        with (self.data / "command.lock").open("a") as lock:
            try:
                fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                raise DAOError("Another launcher operation is in progress. Wait for it to finish.")
            try:
                yield
            finally:
                fcntl.flock(lock, fcntl.LOCK_UN)

    def processes(self) -> list[tuple[int, int, str]]:
        """Read names only; never read command environments/account data."""
        try:
            proc = subprocess.run(["/bin/ps", "-axo", "pid=,ppid=,command="],
                                  capture_output=True, text=True, timeout=4)
            if proc.returncode:
                return []
        except (OSError, subprocess.TimeoutExpired):
            return []
        rows = []
        for line in proc.stdout.splitlines():
            parts = line.strip().split(None, 2)
            if len(parts) == 3 and parts[0].isdigit() and parts[1].isdigit():
                rows.append((int(parts[0]), int(parts[1]), parts[2]))
        # Wine's Windows processes are reparented to PID 1 and display a Windows
        # command line. Bind them to the actual Mach executable, not text matches.
        own = set()
        try:
            lib = ctypes.CDLL("/usr/lib/libproc.dylib")
            lib.proc_pidpath.argtypes = [ctypes.c_int, ctypes.c_void_p, ctypes.c_uint32]
            lib.proc_pidpath.restype = ctypes.c_int
            for pid, _, cmd in rows:
                if ".exe" not in cmd.casefold() and str(self.runtime) not in cmd:
                    continue
                buf = ctypes.create_string_buffer(4096)
                if lib.proc_pidpath(pid, buf, len(buf)) > 0:
                    actual = Path(os.fsdecode(buf.value)).resolve()
                    if self.runtime in actual.parents:
                        own.add(pid)
        except (OSError, AttributeError):
            return []
        while True:
            expanded = own | {pid for pid, parent, _ in rows if parent in own}
            if expanded == own:
                break
            own = expanded
        return [row for row in rows if row[0] in own]

    def steam_bootstrap_tail(self, steam: Path) -> tuple[str, float]:
        """Read only a bounded tail of Steam's updater log, never account logs."""
        try:
            path = (steam.parent / "logs/bootstrap_log.txt").resolve()
            path.relative_to(self.prefix.resolve())
            if not path.is_file():
                return "", 0
            with path.open("rb") as handle:
                handle.seek(0, os.SEEK_END)
                size = handle.tell()
                handle.seek(max(0, size - BOOTSTRAP_TAIL_BYTES))
                raw = handle.read(BOOTSTRAP_TAIL_BYTES)
                modified = os.fstat(handle.fileno()).st_mtime
            if size > BOOTSTRAP_TAIL_BYTES:
                raw = raw.partition(b"\n")[2]  # Ignore a partially read first line.
            return raw.decode("utf-8", errors="replace").casefold(), modified
        except (OSError, ValueError):
            return "", 0

    def steam_startup(self, steam: Path | None, running: list[str]) -> str:
        if not steam:
            return "not_installed"
        # A live UI process takes precedence over old updater history. It does
        # not establish that the user is signed in or that authentication works.
        if any(windows_process_is(cmd, "steamwebhelper.exe") for cmd in running):
            return "client_running"
        if not any(windows_process_is(cmd, "steam.exe") for cmd in running):
            return "stopped"
        text, modified = self.steam_bootstrap_tail(steam)
        start = text.rfind("startup - updater")
        if start >= 0:
            text = text[start:]
        markers = {
            "downloading update (": "updating",
            "download complete.": "updating",
            "extracting package": "updating",
            "installing update": "updating",
            "cleaning up...": "updating",
            "update complete, launching steam": "handoff",
            "verifying installation": "starting",
            "verification complete": "starting",
        }
        _, stage = max(((text.rfind(marker), stage) for marker, stage in markers.items()),
                       default=(-1, "starting"))
        if not any(marker in text for marker in markers):
            return "starting"
        if stage == "handoff":
            age = max(0, time.time() - modified)
            return "restart_required" if age >= STEAM_HANDOFF_GRACE_SECONDS else "starting"
        return stage

    def compatibility_verified(self, game: dict | None) -> bool:
        """Match an explicit human report to this executable and display mode.

        This only reads data/validation.json; running a game never creates or
        upgrades a report. The record is evidence of a user report, not an
        independent automated gameplay test.
        """
        if not game or game.get("complete") is not True:
            return False

        def read_text(path):
            path = path.resolve()
            path.relative_to(self.root)
            if not path.is_file():
                raise ValueError("Missing validation input")
            with path.open("rb") as handle:
                raw = handle.read(65537)
            if len(raw) > 65536:
                raise ValueError("Oversized validation input")
            return raw.decode("utf-8-sig")

        def confirmed_at(value):
            if not isinstance(value, str):
                return False
            timestamp = dt.datetime.fromisoformat(value.replace("Z", "+00:00"))
            return timestamp.utcoffset() is not None

        try:
            report = json.loads(read_text(self.data / "validation.json"))
            if (not isinstance(report, dict) or type(report.get("schema_version")) is not int
                    or report["schema_version"] != 1 or report.get("source") != "user_report"
                    or report.get("appid") != game["appid"] or not confirmed_at(report.get("confirmed_at"))):
                return False
            # A display experiment is not validated merely because its numeric
            # resolution matches an older report. Recovery must finish first.
            display_state = self.data / "display-settings.json"
            if display_state.exists() or display_state.is_symlink():
                display = json.loads(read_text(display_state))
                if (not isinstance(display, dict) or type(display.get("schema_version")) is not int
                        or display["schema_version"] != 1
                        or type(display.get("pending_confirmation")) is not bool
                        or display["pending_confirmation"]
                        or display.get("recovery_required", False) is not False):
                    return False
            checks = report.get("checks")
            if not isinstance(checks, dict) or not all(checks.get(key) is True for key in ("gameplay", "audio", "save_reload")):
                return False
            executable = Path(game["exe"]).resolve()
            executable.relative_to(self.prefix.resolve())
            observed = executable.stat()
            recorded = report.get("game_executable")
            if (not isinstance(recorded, dict)
                    or any(type(recorded.get(key)) is not int for key in ("size", "mtime_ns"))
                    or recorded["size"] != observed.st_size or recorded["mtime_ns"] != observed.st_mtime_ns):
                return False
            ini = configparser.ConfigParser(interpolation=None)
            ini.read_string(read_text(self.documents / "BioWare/Dragon Age/Settings/DragonAge.ini"))
            width = ini.getint("VideoOptions", "ResolutionWidth")
            height = ini.getint("VideoOptions", "ResolutionHeight")
            fullscreen = ini.get("VideoOptions", "FullScreen").strip()
            if width <= 0 or height <= 0 or fullscreen not in ("0", "1"):
                return False
            configurations = report.get("configurations")
            if not isinstance(configurations, list) or not configurations:
                return False
            matched = False
            for config in configurations:
                if (not isinstance(config, dict)
                        or type(config.get("width")) is not int or config["width"] <= 0
                        or type(config.get("height")) is not int or config["height"] <= 0
                        or type(config.get("fullscreen")) is not bool
                        or not confirmed_at(config.get("confirmed_at"))):
                    return False
                matched |= (config["width"], config["height"], config["fullscreen"]) == (width, height, fullscreen == "1")
            return matched
        except (OSError, ValueError, TypeError, KeyError, RuntimeError, configparser.Error):
            return False

    def status(self) -> dict:
        supported = platform_status()
        state = self.state()
        games = discover_games(self.prefix) if self.prefix_ready() else []
        complete = [g for g in games if g["complete"]]
        preferred = state.get("selected_appid")
        game = next((g for g in complete if g["appid"] == preferred), None)
        game = game or next(iter(complete), None)
        steam = find_steam(self.prefix)
        running = [cmd.casefold() for _, _, cmd in self.processes()]
        steam_running = any(windows_process_is(cmd, "steam.exe") for cmd in running)
        game_running = any(windows_process_is(cmd, "DAOrigins.exe") for cmd in running)
        startup = self.steam_startup(steam, running)
        from steam_maintenance import SteamMaintenance
        maintenance = SteamMaintenance(self)
        maintenance_summary = maintenance.summary()
        verified = self.compatibility_verified(game)
        from game_setup import configuration_status
        configuration = configuration_status(self, game)
        config_running = any(windows_process_is(cmd, "DAOriginsConfig.exe") for cmd in running)
        steam_installing = any(windows_process_is(cmd, "SteamSetup.exe") for cmd in running)
        if not supported["platform_supported"] or not supported["rosetta_ready"]:
            phase, message = supported["phase"], supported["message"]
        elif not self.runtime_ready():
            phase, message = "setup", "Set up downloads the pinned compatibility runtime and Windows Steam into this launcher's private data folder."
        elif steam_installing:
            phase, message = "steam_installing", "Complete the Windows Steam installer window and review its terms. Then open Steam and allow its client update to finish."
        elif self.registry_files_ready() and not self.prefix_ready():
            phase = "prefix_containment_required"
            message = "The Windows profile needs local folder setup. Choose Set up & open Steam before continuing."
            try:
                self.require_contained_profile()
            except DAOError as exc:
                message = str(exc)
        elif not self.prefix_ready() or not steam:
            phase, message = "setup", "Prepare Windows Steam in the dedicated game environment."
        elif game_running:
            phase = "playing"
            message = ("The game is running. You confirmed gameplay, audio and save/reload on this Mac." if verified
                       else "The game process is running. Gameplay compatibility is still subject to testing.")
        elif config_running:
            phase, message = "game_configuration_running", "Finish or close Dragon Age's configuration window, then return here to Play."
        elif startup == "updating":
            phase, message = "steam_updating", "Steam is updating its client. Let the update finish before signing in or installing the game."
        elif startup == "starting":
            phase, message = "steam_starting", "Steam is starting. Wait for its window before signing in or installing the game."
        elif startup == "restart_required":
            phase, message = "steam_restart_required", "Steam's update finished, but its main window has not started. If no Steam window is open, use Stop, then Open Steam to finish startup."
        elif startup == "stopped" and maintenance_summary.get("steam_maintenance_blocked_reason"):
            phase, message = "steam_startup_blocked", maintenance_summary["steam_maintenance_blocked_reason"]
        elif startup == "stopped" and maintenance_summary["steam_maintenance_active"] and maintenance.pending_handoff(steam):
            phase, message = "steam_handoff_wait", "Steam completed an update and exited. The launcher is following its startup handoff."
        elif game and not configuration["ready"]:
            phase, message = "game_configuration_required", configuration["message"]
        elif game:
            phase = "ready"
            message = ("Ready to play. You confirmed gameplay, audio and save/reload on this Mac." if verified
                       else "Game files are installed. Launch to test gameplay, sound and save/load.")
        elif games:
            phase, message = "downloading", "Steam has started installing the game. Let its download and first-run setup finish."
        else:
            phase, message = "sign_in", "Open Windows Steam, sign in, then install the edition you own."
        return dict(platform_supported=supported["platform_supported"], rosetta_ready=supported["rosetta_ready"],
                    configuration_ready=configuration["ready"],
                    runtime_ready=self.runtime_ready(), prefix_ready=self.prefix_ready(),
                    steam_installed=steam is not None, steam_running=steam_running,
                    steam_startup_phase=startup,
                    game_installed=game is not None, game_running=game_running,
                    game_title=game["title"] if game else None,
                    game_appid=game["appid"] if game else None,
                    game_dir=game["game_dir"] if game else None,
                    storage_bytes=nonnegative_int(state.get("storage_bytes")),
                    storage_measured_at=state.get("storage_measured_at"),
                    phase=phase, message=message, log_path=str(self.logs),
                    data_path=str(self.prefix if self.prefix_ready() else self.data),
                    installed_editions=games, compatibility_verified=verified, **maintenance_summary)

    def launch_wss(self, args: list[str], name: str) -> tuple[subprocess.Popen, Path]:
        self.require_runtime()
        log = self.new_log(name)
        with log.open("ab", buffering=0) as out:
            p = subprocess.Popen([str(self.launcher), *args], cwd=self.runtime,
                                 env=self.env(), stdin=subprocess.DEVNULL,
                                 stdout=out, stderr=out, start_new_session=True)
        self.save_state(last_launcher_pid=p.pid)
        return p, log

    def wait(self, proc, timeout: float, log: Path):
        try:
            code = proc.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            # Only the controller-created process group, never other Wine apps.
            with contextlib.suppress(ProcessLookupError):
                os.killpg(proc.pid, signal.SIGTERM)
            raise DAOError(f"Runtime operation timed out. See {log.name} in Show logs.")
        if code:
            raise DAOError(f"Runtime exited with code {code}. See {log.name} in Show logs.")

    def contain_user_folders(self):
        """Localize saves/documents without following or deleting home targets."""
        self.require_runtime()
        prefs = self.contents / "Info.plist"
        try:
            prefs.resolve().relative_to(self.runtime.resolve())
        except ValueError as exc:
            raise DAOError("Runtime preferences point outside the dedicated runtime. No user folders were changed.") from exc
        with prefs.open("rb") as f:
            value = plistlib.load(f)
        mapping = localize_user_folders(self.prefix)
        value["Symlinks In User Folder"] = 0
        for label, target in mapping["folders"].items():
            value["Symlink " + label] = str(target)
        with prefs.open("wb") as f:
            plistlib.dump(value, f)

    def initialize(self):
        self.require_runtime()
        if not self.registry_files_ready():
            if any((self.prefix / n).exists() for n in ("user.reg", "system.reg")):
                raise DAOError("Prefix creation left an incomplete registry. The existing environment was preserved; do not reset it over saved data.")
            p, log = self.launch_wss(["WSS-wineprefixcreate"], "initialize")
            self.wait(p, 240, log)
            if not self.registry_files_ready():
                raise DAOError("The runtime did not create a usable environment. Inspect the initialization log.")
        self.contain_user_folders()
        self.require_contained_profile()

    def run_batch(self, name: str, body: str):
        self.require_contained_profile()
        support = self.prefix / "drive_c/dao-support"
        try:
            support.resolve().relative_to(self.prefix.resolve())
        except ValueError as exc:
            raise DAOError("The launcher support directory points outside this game's environment.") from exc
        support.mkdir(parents=True, exist_ok=True)
        # Unique batches allow a previous command to finish without overwritten input.
        path = support / f"{name}-{time.time_ns()}.bat"
        path.write_bytes(("@echo off\r\n" + body.replace("\r\n", "\n").replace("\n", "\r\n") + "\r\n").encode("utf-8"))
        return self.launch_wss(["WSS-installer", str(path)], name)

    def download_steam(self) -> Path:
        self.downloads.mkdir(parents=True, exist_ok=True)
        dest = self.downloads / "SteamSetup.exe"
        receipt = self.downloads / "SteamSetup.receipt.json"
        if dest.is_file() and receipt.is_file():
            try:
                record = json.loads(receipt.read_text())
                digest = hashlib.sha256(dest.read_bytes()).hexdigest()
                if isinstance(record, dict) and record.get("url") == STEAM_URL and record.get("sha256") == digest:
                    return dest
            except (OSError, ValueError):
                pass
        tmp = dest.with_suffix(".download")
        try:
            request = urllib.request.Request(STEAM_URL, headers={"User-Agent": "DAO-local-launcher/0.1"})
            with urllib.request.urlopen(request, timeout=45) as response, tmp.open("wb") as out:
                if not response.url.startswith("https://cdn.akamai.steamstatic.com/"):
                    raise DAOError("Steam download redirected away from Valve's expected distribution host.")
                size = 0
                while True:
                    chunk = response.read(1024 * 1024)
                    if not chunk:
                        break
                    size += len(chunk)
                    if size > 50 * 1024 * 1024:
                        raise DAOError("Unexpectedly large Steam installer. Download stopped for review.")
                    out.write(chunk)
            raw = tmp.read_bytes()
            if len(raw) < 100_000 or not raw.startswith(b"MZ"):
                raise DAOError("Valve's download is not a valid Windows installer.")
            tmp.replace(dest)
            receipt.write_text(json.dumps(dict(url=STEAM_URL, sha256=hashlib.sha256(raw).hexdigest(),
                                               bytes=len(raw), downloaded_at=utc_now()), indent=2) + "\n")
            return dest
        except Exception:
            with contextlib.suppress(OSError):
                tmp.unlink()
            raise

    def measure(self) -> int:
        # du does not follow prefix links into the user's home directory.
        try:
            result = subprocess.run(["/usr/bin/du", "-sk", str(self.root)], capture_output=True,
                                    text=True, timeout=30)
            if result.returncode == 0:
                size = int(result.stdout.split()[0]) * 1024
                self.save_state(storage_bytes=size, storage_measured_at=utc_now())
                return size
        except (OSError, ValueError, subprocess.TimeoutExpired):
            pass
        return nonnegative_int(self.state().get("storage_bytes"))

    def setup(self):
        self.ensure_runtime()
        from display_settings import DisplaySettings
        DisplaySettings(self)._guard()
        self.initialize()
        if find_steam(self.prefix):
            self.measure()
            result = self.open_steam()
            result["message"] = "Windows Steam is installed. Its window or updater is opening; sign in when it is ready."
            return result
        installer = self.download_steam()
        support = self.prefix / "drive_c/dao-support"
        support.mkdir(parents=True, exist_ok=True)
        local_installer = support / "SteamSetup.exe"
        shutil.copy2(installer, local_installer)
        from steam_maintenance import SteamMaintenance
        SteamMaintenance(self).arm()
        p, log = self.run_batch("install-steam", '"C:\\dao-support\\SteamSetup.exe"')
        if p.poll() not in (None, 0):
            SteamMaintenance(self).cancel("Steam installer did not start.")
            raise DAOError(f"Steam's installer could not start. Check {log.name} and retry setup.")
        return dict(ok=True, message="Complete the Windows Steam installer window and review its terms. Then use Open Steam and let its client updates finish before signing in.", log=str(log))

    def open_steam(self):
        self.require_platform()
        self.require_contained_profile()
        if not find_steam(self.prefix):
            raise DAOError("Prepare Steam before opening it.")
        from steam_maintenance import SteamMaintenance
        maintenance = SteamMaintenance(self)
        maintenance.arm()
        try:
            return self.steam_command([], "steam")
        except Exception:
            maintenance.cancel("Steam did not start. Use Open Steam to retry.")
            raise

    def steam_command(self, flags: list[str], name: str):
        self.require_platform()
        self.require_runtime()
        self.require_contained_profile()
        exe = find_steam(self.prefix)
        if not exe:
            raise DAOError("Prepare Steam before opening it.")
        relative = exe.relative_to(self.prefix / "drive_c")
        windows = "C:\\" + str(relative).replace("/", "\\")
        # All flags are internal literals or validated numeric application IDs.
        if any(re.search(r'["\r\n&|<>%]', part) for part in [windows, *flags]):
            raise DAOError("The Steam path contains unsupported Windows command characters.")
        body = f'"{windows}" ' + " ".join(f'"{part}"' for part in flags)
        p, log = self.run_batch(name, body)
        time.sleep(2)
        if p.poll() not in (None, 0):
            raise DAOError(f"The runtime could not start Steam. Check {log.name}.")
        return dict(ok=True, message="Launch request sent to Windows Steam. Allow its window or client update to appear.", log=str(log))

    def install_game(self, appid):
        from steam_maintenance import SteamMaintenance
        SteamMaintenance(self).cancel("Game installation requested; startup follow-up stopped.", force=True)
        if appid not in GAMES:
            raise DAOError("Choose the base game or Ultimate Edition.")
        result = self.steam_command([f"steam://install/{appid}"], "install-game")
        self.save_state(selected_appid=appid)
        result["message"] = f"Asked Windows Steam to install {GAMES[appid]}. Sign in and confirm the download there; this does not purchase the game."
        return result

    def play(self, appid=None, preset=None, ui_size="comfortable"):
        from steam_maintenance import SteamMaintenance
        SteamMaintenance(self).cancel("Game launch requested; startup follow-up stopped.", force=True)
        self.require_platform()
        self.require_contained_profile()
        games = [g for g in discover_games(self.prefix) if g["complete"]]
        chosen = appid or self.state().get("selected_appid")
        game = next((g for g in games if g["appid"] == chosen), None)
        if not appid:
            game = game or next(iter(games), None)
        if not game:
            raise DAOError("No complete DA:O installation was found. Finish the download in Windows Steam first.")
        running = [cmd for _, _, cmd in self.processes()]
        if any(windows_process_is(cmd, "DAOrigins.exe") for cmd in running):
            return dict(ok=True, message="Dragon Age: Origins is already running. No second instance was started.")
        if any(windows_process_is(cmd, "DAOriginsConfig.exe") for cmd in running):
            raise DAOError("Dragon Age's configuration utility is still running. Finish or close it before choosing Play.")
        from game_setup import configuration_status
        if not configuration_status(self, game)["ready"]:
            raise DAOError("Choose Finish game setup before playing. Complete the supplied prerequisite installers and close the game configuration window.")
        if preset:
            from display_settings import DisplaySettings
            DisplaySettings(self, appid=game["appid"]).prepare_for_play(preset, ui_size)
        result = self.steam_command(["-applaunch", game["appid"]], "play")
        self.save_state(selected_appid=game["appid"])
        result["message"] = ("Game launch requested. You confirmed gameplay, audio and save/reload on this Mac." if self.compatibility_verified(game)
                             else "Game launch requested. Steam may run prerequisite installers. Gameplay compatibility has not yet been verified.")
        return result

    def stop(self):
        from steam_maintenance import SteamMaintenance
        SteamMaintenance(self).cancel("Stopped by the user.", force=True)
        self.require_runtime()
        log = self.new_log("stop")
        with log.open("ab") as out:
            result = subprocess.run([str(self.wineserver), "-k"], env=self.env(),
                                    stdout=out, stderr=out, timeout=20)
        if result.returncode not in (0, 1):
            raise DAOError(f"Runtime stop failed. Check {log.name}.")
        return dict(ok=True, message="Requested shutdown of this game's Wine session. Game files and saves are preserved.")

    def diagnostics(self):
        """Summaries only: no Steam account files, environment dumps or raw logs."""
        status = self.status()
        size = self.measure()
        status["storage_bytes"] = size
        status["storage_measured_at"] = self.state().get("storage_measured_at")
        for key in ("game_dir", "data_path", "log_path"):
            if status.get(key):
                status[key] = status[key].replace(str(self.root), "<PROJECT>")
        for game in status.get("installed_editions", []):
            for key in ("game_dir", "exe"):
                if game.get(key):
                    game[key] = game[key].replace(str(self.root), "<PROJECT>")
        report = self.data / "diagnostics.json"
        self.data.mkdir(parents=True, exist_ok=True)
        report.write_text(json.dumps(dict(created_at=utc_now(), status=status,
                                         note="Local summary only. No credentials or Steam account data included."), indent=2) + "\n")
        report.chmod(0o600)
        return dict(ok=True, message="Saved a local diagnostic summary. Nothing was uploaded.", report_path=str(report))


def utc_now():
    return dt.datetime.now(dt.timezone.utc).isoformat()


def nonnegative_int(value):
    try:
        return max(0, int(value))
    except (TypeError, ValueError, OverflowError):
        return 0


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["status", "setup", "steam", "steam-maintain", "steam-maintenance-cancel", "install-game", "play", "stop", "diagnostics", "configure-game", "install-ui-scaling",
                                          "display-options", "display-apply", "display-restore", "display-confirm"])
    parser.add_argument("--appid", choices=sorted(GAMES))
    parser.add_argument("--preset")
    parser.add_argument("--ui-size", choices=["comfortable", "larger"], default="comfortable")
    args = parser.parse_args(argv)
    try:
        c = Controller(project_root())
        if args.command == "status":
            result = c.status()
        elif args.command == "display-options":
            from display_settings import DisplaySettings
            result = DisplaySettings(c).options()
        else:
            with c.operation():
                if args.command == "setup": result = c.setup()
                elif args.command == "steam": result = c.open_steam()
                elif args.command in ("steam-maintain", "steam-maintenance-cancel"):
                    from steam_maintenance import SteamMaintenance
                    maintenance = SteamMaintenance(c)
                    result = maintenance.maintain() if args.command == "steam-maintain" else maintenance.cancel_request()
                elif args.command == "install-game": result = c.install_game(args.appid or "47810")
                elif args.command == "play": result = c.play(args.appid, preset=args.preset, ui_size=args.ui_size)
                elif args.command == "stop": result = c.stop()
                elif args.command in ("configure-game", "install-ui-scaling"):
                    c.require_platform()
                    from display_settings import DisplaySettings
                    DisplaySettings(c, appid=args.appid)._guard()
                    if args.command == "configure-game":
                        from game_setup import configure_game
                        result = configure_game(c, args.appid)
                    else:
                        from ui_scaling import install_ui_scaling
                        result = install_ui_scaling(c, appid=args.appid)
                elif args.command.startswith("display-"):
                    from display_settings import DisplaySettings
                    displays = DisplaySettings(c)
                    if args.command == "display-apply":
                        if not args.preset:
                            raise DAOError("Choose a display preset before applying settings.")
                        result = displays.apply(args.preset, args.ui_size)
                    elif args.command == "display-restore": result = displays.restore()
                    else: result = displays.confirm()
                else: result = c.diagnostics()
        print(json.dumps(result))
        return 0
    except (DAOError, OSError, ValueError, subprocess.TimeoutExpired) as exc:
        print(json.dumps(dict(ok=False, message=str(exc))))
        return 1


if __name__ == "__main__":
    sys.exit(main())
