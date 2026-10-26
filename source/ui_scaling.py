"""Explicit, pinned DAFix installation into one owned game environment.

Call install_ui_scaling(controller) only inside Controller.operation(). This
module neither launches the game nor changes its display settings. Existing
mods are preserved, including installations this launcher does not manage.
"""
from __future__ import annotations

import hashlib
import io
import json
import os
from pathlib import Path, PurePosixPath
import re
import stat
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
import zipfile

from display_settings import DisplayError, DisplaySettings, _now, _patch_ini

VERSION = "0.0.3"
ARCHIVE_URL = "https://github.com/Lyall/DAFix/releases/download/v0.0.3/DAFix_v0.0.3.zip"
ARCHIVE_SIZE = 1191813
ARCHIVE_SHA256 = "613a3d005da6d95ed773b3281e1d8518c71d91effd1ae32e27d6a5986b64059a"
LICENSE_URL = "https://raw.githubusercontent.com/Lyall/DAFix/v0.0.3/LICENSE.md"
LICENSE_SIZE = 1062
LICENSE_SHA256 = "e6d3e38c2034ff57595323c9a346b9c298ad59074255987fde23993d99cbe88e"
FILES = ("DAFix.asi", "DAFix.ini", "dinput8.dll", "dinput8.ini")
BINARIES = ("DAFix.asi", "dinput8.dll")
LOADER_LICENSE = "UltimateASILoader_LICENSE.md"
DLL_SECTION = r"Software\Wine\AppDefaults\DAOrigins.exe\DllOverrides"
DLL_KEY = "HKCU\\" + DLL_SECTION
OVERRIDE = "native,builtin"
ALLOWED_HOSTS = {"github.com", "raw.githubusercontent.com", "release-assets.githubusercontent.com",
                 "objects.githubusercontent.com", "github-releases.githubusercontent.com"}


def _digest(raw):
    return hashlib.sha256(raw).hexdigest()


def _check_url(url):
    parsed = urllib.parse.urlsplit(url)
    if (parsed.scheme != "https" or parsed.hostname not in ALLOWED_HOSTS or
            parsed.username is not None or parsed.password is not None or parsed.port not in (None, 443)):
        raise DisplayError("The optional UI-scaling download redirected outside its official HTTPS distribution hosts.")


class _PinnedRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        _check_url(newurl)
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def _download(url, expected_size, expected_digest):
    _check_url(url)
    request = urllib.request.Request(url, headers={"User-Agent": "OriginsLauncher/0.2"})
    try:
        opener = urllib.request.build_opener(_PinnedRedirect())
        with opener.open(request, timeout=45) as response:
            _check_url(response.geturl())
            raw = response.read(expected_size + 1)
    except (OSError, urllib.error.URLError) as exc:
        raise DisplayError("The optional UI-scaling download failed. Check your connection and retry; no mod files were installed.") from exc
    if len(raw) != expected_size or _digest(raw) != expected_digest:
        raise DisplayError("The optional UI-scaling download did not match the pinned release. No mod files were installed.")
    return raw


def _archive_files(raw):
    """Read an allowlist in memory; never extract archive paths to the disk."""
    try:
        with zipfile.ZipFile(io.BytesIO(raw)) as archive:
            entries = archive.infolist()
            if len(entries) > 100 or sum(info.file_size for info in entries) > 64 * 1024 * 1024:
                raise DisplayError("The UI-scaling archive is unexpectedly large.")
            seen = set()
            for info in entries:
                name = info.filename
                path = PurePosixPath(name)
                kind = stat.S_IFMT(info.external_attr >> 16)
                if (not name or "\\" in name or "\x00" in name or path.is_absolute() or
                        any(part in ("", ".", "..") for part in name.rstrip("/").split("/")) or
                        ":" in name or name.casefold() in seen or info.flag_bits & 1 or
                        kind not in (0, stat.S_IFREG, stat.S_IFDIR) or
                        info.file_size > 32 * 1024 * 1024):
                    raise DisplayError("The UI-scaling archive contains an unsafe or duplicate path.")
                seen.add(name.casefold())
            wanted = {name: archive.read("bin_ship/" + name) for name in FILES}
            license_raw = archive.read(LOADER_LICENSE)
            if not license_raw or len(license_raw) > 65536:
                raise DisplayError("The loader license is missing or unexpectedly large.")
            if any(not wanted[name].startswith(b"MZ") for name in BINARIES):
                raise DisplayError("The UI-scaling archive does not contain the expected Windows binaries.")
            if any(not wanted[name] for name in FILES):
                raise DisplayError("The UI-scaling archive contains an empty required file.")
            conservative = wanted["DAFix.ini"]
            for section, changes in (
                ("HUD Scale", {"Scale": "1"}),
                ("Borderless Windowed", {"Enabled": "false"}),
                ("Fix Aspect Ratio", {"Enabled": "false"}),
                ("Disable Pillarboxing", {"Enabled": "false"}),
                ("Draw Distances", {"Foliage": "0", "NPC": "0", "Object": "0"}),
                ("Shadow Resolution", {"Resolution": "1024"}),
            ):
                conservative = _patch_ini(conservative, section, changes)
            wanted["DAFix.ini"] = conservative
            return wanted, license_raw
    except (zipfile.BadZipFile, KeyError, RuntimeError, OSError) as exc:
        raise DisplayError("The UI-scaling archive is invalid or missing required files.") from exc


def _registry(settings):
    raw = settings._read(settings.prefix / "user.reg", settings.prefix, limit=16 * 1024 * 1024)
    text = raw.decode("utf-8", errors="replace")
    escaped = DLL_SECTION.replace("\\", "\\\\")
    sections = re.findall(r"^\[" + re.escape(escaped) + r"\][^\n]*\n((?:(?!\[).*(?:\n|$))*)", text, re.M | re.I)
    values = re.findall(r'^"dinput8"=(.*)$', sections[0], re.M | re.I) if len(sections) == 1 else []
    if len(sections) > 1 or len(values) > 1:
        raise DisplayError("Duplicate game-specific DLL overrides were found. Existing settings were preserved.")
    if not values:
        return None
    match = re.fullmatch(r'"([^"\\]*)"', values[0].strip())
    if not match:
        raise DisplayError("The existing game-specific DLL override has an unsupported type. Existing settings were preserved.")
    return match.group(1)


def _write_override(settings, value):
    """Use Wine's registry command and verify persistence after scoped shutdown."""
    if value not in (None, OVERRIDE):
        raise DisplayError("Unsupported UI-scaling DLL override.")
    support = settings._safe(settings.prefix / "drive_c/dao-support", settings.prefix)
    report = support / ("ui-scaling-registry-" + uuid.uuid4().hex + ".txt")
    winreport = "C:\\dao-support\\" + report.name
    command = (f'reg delete "{DLL_KEY}" /v dinput8 /f' if value is None else
               f'reg add "{DLL_KEY}" /v dinput8 /t REG_SZ /d {value} /f')
    body = "\n".join([command, "if errorlevel 1 exit /b 1",
                      f'reg query "{DLL_KEY}" /v dinput8 > "{winreport}" 2>&1',
                      f'echo DAO_UI_SCALING_REGISTRY_COMPLETE >> "{winreport}"'])
    process, _ = settings.c.run_batch("ui-scaling-registry", body)
    deadline = time.monotonic() + 45
    while time.monotonic() < deadline:
        if report.is_file():
            output = settings._read(report, settings.prefix, limit=65536).decode("utf-8", errors="replace")
            if "DAO_UI_SCALING_REGISTRY_COMPLETE" in output:
                match = re.search(r"\bdinput8\s+REG_SZ\s+([^\r\n]+)", output, re.I)
                actual = match.group(1).strip() if match else None
                if actual != value:
                    raise DisplayError("The game-specific UI-scaling registry command did not verify.")
                settings._stop_prefix()
                if _registry(settings) != value:
                    raise DisplayError("The UI-scaling registry change did not persist after this runtime closed.")
                return
        if process.poll() not in (None, 0):
            raise DisplayError("The game-specific UI-scaling registry command failed. Inspect the launcher logs.")
        time.sleep(0.25)
    raise DisplayError("The UI-scaling registry command did not finish; its backup is retained for recovery.")


def _existing_receipt(settings, path):
    if path.is_symlink():
        raise DisplayError("The UI-scaling receipt is a symbolic link. It was preserved for inspection.")
    if not path.exists():
        return None
    try:
        value = json.loads(settings._read(path, settings.data, limit=65536))
        if not isinstance(value, dict) or value.get("schema_version") != 1:
            raise ValueError()
        return value
    except (ValueError, OSError) as exc:
        raise DisplayError("The existing UI-scaling receipt is invalid. Preserve it and the current mod files before retrying.") from exc


def _exclusive_write(settings, path, raw, base=None):
    if path.is_symlink():
        raise DisplayError("A UI-scaling destination became a symbolic link. Nothing there was replaced.")
    settings._safe(path, base or settings.prefix)
    created_stat = None
    try:
        with path.open("xb") as handle:
            created_stat = os.fstat(handle.fileno())
            os.fchmod(handle.fileno(), 0o600)
            handle.write(raw)
            handle.flush()
            os.fsync(handle.fileno())
    except Exception:
        # A short/disk-full write belongs to this transaction, but a replacement
        # by another actor does not. Never delete a different inode or a link.
        if created_stat is not None:
            current = path.lstat()
            if (stat.S_ISREG(current.st_mode) and current.st_ino == created_stat.st_ino
                    and current.st_dev == created_stat.st_dev):
                path.unlink()
        raise


def _preserve_licenses(settings, storage, license_raw, loader_license):
    folder = storage / "licenses" / VERSION
    for path in (storage / "licenses", folder):
        if path.is_symlink():
            raise DisplayError("The UI-scaling license folder is a symbolic link. It was preserved for inspection.")
        settings._safe(path, settings.data)
    folder.mkdir(parents=True, exist_ok=True)
    records = {}
    for name, raw in (("DAFix-LICENSE.md", license_raw), (LOADER_LICENSE, loader_license)):
        path = folder / name
        if path.is_symlink():
            raise DisplayError("An existing UI-scaling license link was preserved; inspect it before retrying.")
        settings._safe(path, settings.data)
        if path.exists():
            if settings._read(path, settings.data, limit=65536) != raw:
                raise DisplayError("An existing UI-scaling license differs from the pinned release. It was preserved for inspection.")
        else:
            _exclusive_write(settings, path, raw, settings.data)
        records[name] = {"path": str(path.relative_to(settings.root)), "sha256": _digest(raw)}
    return records


def install_ui_scaling(controller, appid=None):
    """Install only after a user opt-in; caller holds Controller.operation()."""
    settings = DisplaySettings(controller, appid=appid)
    settings._guard()
    game = settings._game()
    folder = settings._safe(Path(game["exe"]).parent, settings.prefix)
    targets = {name: folder / name for name in FILES}
    for target in targets.values():
        if target.is_symlink():
            raise DisplayError("Existing mod links were preserved. UI scaling will not replace an existing installation.")
        settings._safe(target, settings.prefix)
    storage = settings.data / "ui-scaling"
    if storage.is_symlink():
        raise DisplayError("The UI-scaling storage folder is a symbolic link. It was preserved for inspection.")
    settings._safe(storage, settings.data)
    receipt_path = storage / (game["appid"] + "-receipt.json")
    if receipt_path.is_symlink():
        raise DisplayError("The UI-scaling receipt is a symbolic link. It was preserved for inspection.")
    settings._safe(receipt_path, settings.data)
    receipt = _existing_receipt(settings, receipt_path)
    relative_game = str(folder.relative_to(settings.prefix))
    if receipt and receipt.get("phase") not in ("installed", "rolled_back"):
        raise DisplayError("An earlier UI-scaling installation needs recovery. Preserve data/ui-scaling and inspect its receipt before retrying.")
    present = [name for name, target in targets.items() if target.exists()]
    if present:
        managed = (len(present) == len(FILES) and receipt and receipt.get("phase") == "installed" and
                   receipt.get("version") == VERSION and receipt.get("archive_sha256") == ARCHIVE_SHA256 and
                   receipt.get("appid") == game["appid"] and receipt.get("game_folder") == relative_game)
        if managed:
            hashes = receipt.get("installed_sha256", {})
            managed = (isinstance(hashes, dict) and all(target.is_file() for target in targets.values()) and
                       all(_digest(settings._read(targets[name], settings.prefix, 32 * 1024 * 1024)) == hashes.get(name)
                           for name in BINARIES) and _registry(settings) == OVERRIDE)
        if managed:
            return {"ok": True, "message": "Managed UI scaling is already installed. Your mod configuration was preserved.",
                    "already_installed": True, "receipt_path": str(receipt_path)}
        raise DisplayError("Existing or incomplete mod files were found. They were preserved; UI scaling never replaces unmanaged mods.")
    if receipt and receipt.get("phase") == "installed":
        raise DisplayError("The managed UI-scaling files were removed. Preserve the receipt and review the game folder before reinstalling.")
    existing_override = _registry(settings)
    if existing_override not in (None, OVERRIDE):
        raise DisplayError("A different game-specific dinput8 override already exists. It was preserved; review it before adding UI scaling.")

    # Fetch and validate everything before stopping Steam or changing the game.
    raw = _download(ARCHIVE_URL, ARCHIVE_SIZE, ARCHIVE_SHA256)
    license_raw = _download(LICENSE_URL, LICENSE_SIZE, LICENSE_SHA256)
    payload, loader_license = _archive_files(raw)
    licenses = _preserve_licenses(settings, storage, license_raw, loader_license)
    settings._guard()
    settings._stop_prefix()
    settings._guard()
    for target in targets.values():
        if target.exists() or target.is_symlink():
            raise DisplayError("Mod files appeared during download. They were preserved; retry after reviewing them.")
    if _registry(settings) != existing_override:
        raise DisplayError("The game-specific DLL override changed during download. No mod files were installed.")

    transaction = uuid.uuid4().hex
    backup = settings._safe(storage / "backups" / transaction, settings.data)
    backup.mkdir(parents=True, exist_ok=False)
    settings._atomic(backup / "user.reg", settings._read(settings.prefix / "user.reg", settings.prefix, 16 * 1024 * 1024))
    settings._atomic(backup / "DAFix-LICENSE.md", license_raw)
    settings._atomic(backup / LOADER_LICENSE, loader_license)
    record = {"schema_version": 1, "version": VERSION, "phase": "preparing", "appid": game["appid"],
              "game_folder": relative_game, "created_at": _now(), "backup": str(backup.relative_to(settings.root)),
              "archive_url": ARCHIVE_URL, "archive_sha256": ARCHIVE_SHA256, "archive_bytes": len(raw),
              "license_url": LICENSE_URL, "license_sha256": LICENSE_SHA256, "licenses": licenses,
              "original_files": {name: None for name in FILES}, "original_override": existing_override,
              "installed_sha256": {name: _digest(data) for name, data in payload.items()}, "created_files": []}

    def save_record():
        settings._json(backup / "receipt.json", record)
        settings._json(receipt_path, record)

    save_record()
    created = []
    try:
        record["phase"] = "installing"
        save_record()
        for name in FILES:
            _exclusive_write(settings, targets[name], payload[name])
            created.append(name)
            record["created_files"] = list(created)
            save_record()
        settings._guard()
        if existing_override is None:
            _write_override(settings, OVERRIDE)
        if _registry(settings) != OVERRIDE:
            raise DisplayError("The optional UI-scaling loader was not configured successfully.")
        record.update(phase="installed", completed_at=_now())
        save_record()
        return {"ok": True, "message": "Optional UI scaling is installed. Choose a display preset, then press Play. Steam can reopen normally.",
                "already_installed": False, "receipt_path": str(receipt_path)}
    except Exception as original:
        rollback_error = None
        try:
            settings._guard()
            settings._stop_prefix()
            current_override = _registry(settings)
            if current_override not in (existing_override, OVERRIDE):
                raise DisplayError("The DLL override changed independently; automatic rollback did not replace it.")
            if current_override != existing_override:
                _write_override(settings, existing_override)
            for name in reversed(created):
                target = targets[name]
                if target.is_symlink() or not target.is_file() or _digest(settings._read(target, settings.prefix, 32 * 1024 * 1024)) != record["installed_sha256"][name]:
                    raise DisplayError("A newly installed mod file changed; automatic rollback preserved it for inspection.")
                target.unlink()
            record.update(phase="rolled_back", rolled_back_at=_now(), failure=str(original))
        except Exception as exc:
            rollback_error = exc
            record.update(phase="recovery_required", failure=str(original), rollback_error=str(exc))
        try:
            save_record()
        except Exception:
            rollback_error = rollback_error or DisplayError("The recovery receipt could not be updated.")
        if rollback_error:
            raise DisplayError("UI-scaling installation needs recovery. Existing game data was preserved; inspect data/ui-scaling before retrying.") from original
        raise DisplayError("UI-scaling installation failed and its changes were rolled back. Your game settings and saves were preserved; inspect the UI-scaling receipt for details.") from original
