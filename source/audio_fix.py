"""Reversible, exact-version DA:O audio compatibility installation.

Caller holds Controller.operation(). This module never starts/stops Wine. All
mutations require the dedicated Wine session stopped. The receipt precedes any
game/registry change; actual hashes reconcile interruptions. Registry backups
are evidence only: removal edits one owned value, never restores an old hive.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import re
import stat
import tempfile

import large_address

ID = "origins-audio"
OVERRIDE = '"native"'
SECTION = r"Software\Wine\AppDefaults\DAOrigins.exe\DllOverrides"
GLOBAL_SECTION = r"Software\Wine\DllOverrides"
MAX_FILE = 64 * 1024 * 1024


class AudioFixError(RuntimeError):
    pass


def _sha(raw):
    return hashlib.sha256(raw).hexdigest()


def _component_dir():
    here = Path(__file__).resolve().parent
    return (here.parent if here.name == "source" else here) / "audio-compat"


def _safe(path, root):
    path, root = Path(path).absolute(), Path(root).resolve()
    try:
        relative = path.relative_to(root)
        path.resolve().relative_to(root)
    except (ValueError, RuntimeError) as exc:
        raise AudioFixError("An audio-fix path is outside the selected game environment.") from exc
    current = root
    for part in relative.parts:
        current /= part
        if current.is_symlink():
            raise AudioFixError("An audio-fix path contains a symbolic link; existing files were preserved.")
    return path


def _read(path, root, limit=MAX_FILE):
    path = _safe(path, root)
    with os.fdopen(os.open(path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0)), "rb") as handle:
        info = os.fstat(handle.fileno())
        if not stat.S_ISREG(info.st_mode) or info.st_size > limit:
            raise AudioFixError("An audio-fix file has an unexpected type or size.")
        raw = handle.read(limit + 1)
    if len(raw) > limit:
        raise AudioFixError("An audio-fix file is too large.")
    return raw


def _json(path, root, limit=65536):
    try:
        value = json.loads(_read(path, root, limit))
    except (ValueError, UnicodeError) as exc:
        raise AudioFixError("Audio-fix metadata is invalid; existing files were preserved.") from exc
    if not isinstance(value, dict):
        raise AudioFixError("Audio-fix metadata is invalid.")
    return value


def _digest(value):
    return isinstance(value, str) and re.fullmatch(r"[0-9a-f]{64}", value) is not None


def _component():
    folder = _component_dir()
    m = _json(folder / "component.json", folder)
    if (m.get("schema") != 1 or m.get("id") != ID or not isinstance(m.get("version"), str)
            or m.get("policy_revision") != 10 or m.get("status_directory") != "drive_c/dao-support/origins-audio/status"):
        raise AudioFixError("The bundled audio compatibility component is unsupported.")
    for key, name in (("dll", "dsound.dll"), ("game", "DAOrigins.exe"), ("fmod", "fmodex.dll")):
        v = m.get(key, {})
        if not isinstance(v, dict) or v.get("file") != name or not _digest(v.get("sha256")):
            raise AudioFixError("The bundled audio compatibility identity is invalid.")
    raw = _read(folder / "dsound.dll", folder)
    if type(m["dll"].get("bytes")) is not int or len(raw) != m["dll"]["bytes"] or _sha(raw) != m["dll"]["sha256"]:
        raise AudioFixError("The bundled audio compatibility file failed verification.")
    runtime = m.get("runtime", {})
    if not isinstance(runtime, dict) or runtime.get("base") != "runtime_contents" or not isinstance(runtime.get("files"), list) or not runtime["files"]:
        raise AudioFixError("The bundled runtime compatibility identity is missing.")
    seen = set()
    for item in runtime["files"]:
        if not isinstance(item, dict):
            raise AudioFixError("The bundled runtime compatibility identity is invalid.")
        rel = item.get("path", "")
        if (not isinstance(rel, str) or not rel.startswith("SharedSupport/wine/")
                or any(p in ("", ".", "..") for p in rel.split("/")) or "\\" in rel
                or rel in seen or not _digest(item.get("sha256"))):
            raise AudioFixError("The bundled runtime compatibility path is invalid.")
        seen.add(rel)
        if item.get("managed_laa_override") and rel != "SharedSupport/wine/lib/wine/x86_64-unix/ntdll.so":
            raise AudioFixError("Unexpected managed runtime exception.")
    return m, raw


def _paths(c, game):
    if not game or str(game.get("appid")) not in ("17450", "47810") or not game.get("exe"):
        raise AudioFixError("Install a supported Steam edition of Dragon Age: Origins to use the audio fix.")
    executable = _safe(Path(game["exe"]), c.prefix)
    if executable.name.casefold() != "daorigins.exe":
        raise AudioFixError("The selected game executable is not Dragon Age: Origins.")
    folder = executable.parent
    if folder.exists() and not folder.is_dir():
        raise AudioFixError("The recorded game folder is not a directory; existing files were preserved.")
    aliases = [f.name for f in folder.iterdir() if f.name.casefold() == "dsound.dll"] if folder.exists() else []
    if aliases not in ([], ["dsound.dll"]):
        raise AudioFixError("An existing differently named dsound.dll was preserved; inspect the game's mods first.")
    store = _safe(c.data / "audio-fix", c.root)
    return dict(exe=executable, fmod=folder / "fmodex.dll", target=folder / "dsound.dll",
                registry=_safe(c.prefix / "user.reg", c.root), store=store,
                receipt=store / "receipt.json", backup=store / "original-user.reg", payload=store / "dsound.dll")


def _supported(c, p, manifest):
    for key in ("game", "fmod"):
        path = p["exe" if key == "game" else key]
        if _sha(_read(path, c.root)) != manifest[key]["sha256"]:
            raise AudioFixError("This game or FMOD version has not been verified for the audio fix.")
    for item in manifest["runtime"]["files"]:
        path = _safe(c.contents / item["path"], c.root)
        if _sha(_read(path, c.root)) == item["sha256"]:
            continue
        if item.get("managed_laa_override"):
            try:
                _, _, enabled = large_address._inspection(c)
            except (OSError, ValueError, large_address.LargeAddressError):
                enabled = False
            if enabled:
                continue
        raise AudioFixError("This compatibility runtime has not been verified for the audio fix.")


def _registry(raw):
    """Return exact byte offsets of only the DAOrigins.exe dsound value."""
    try:
        text = raw.decode("utf-8")
    except UnicodeError as exc:
        raise AudioFixError("The Wine registry cannot be read safely.") from exc
    if not text.startswith("WINE REGISTRY Version 2"):
        raise AudioFixError("The Wine registry has an unsupported format.")
    current, sections, values, global_value = None, [], [], False
    offset = 0
    for line in text.splitlines(keepends=True):
        heading = re.match(r"^\[([^]]+)\][^\r\n]*", line)
        if line.startswith("[") and not heading:
            raise AudioFixError("The Wine registry has an incomplete section.")
        if heading:
            current = heading[1].replace("\\\\", "\\").casefold()
            if current == SECTION.casefold():
                sections.append(offset + len(line.encode("utf-8")))
        if current in (SECTION.casefold(), GLOBAL_SECTION.casefold()):
            value = re.match(r'^"dsound"\s*=(.*?)(?:\r?\n)?$', line, re.I)
            if value:
                if current == GLOBAL_SECTION.casefold():
                    global_value = True
                else:
                    values.append((offset, offset + len(line.encode("utf-8")), value[1].strip()))
        offset += len(line.encode("utf-8"))
    if len(sections) > 1 or len(values) > 1:
        raise AudioFixError("Duplicate Dragon Age audio overrides were found; existing settings were preserved.")
    if global_value:
        raise AudioFixError("An existing shared dsound override was preserved; remove it yourself before using this audio fix.")
    return sections, values


def _registry_value(raw):
    _, values = _registry(raw)
    return values[0][2] if values else None


def _patch_registry(raw, enabled):
    sections, values = _registry(raw)
    if values:
        start, end, current = values[0]
        if current != OVERRIDE:
            raise AudioFixError("The Dragon Age audio override changed; it was preserved.")
        return raw if enabled else raw[:start] + raw[end:]
    if not enabled:
        return raw
    line = b'"dsound"="native"\n'
    if sections:
        at = sections[0]
        return raw[:at] + line + raw[at:]
    heading = SECTION.replace("\\", "\\\\")
    return raw + (b"\n" if not raw.endswith(b"\n") else b"") + ("\n[" + heading + "]\n").encode() + line


def _record(c, p, manifest, game):
    if not p["receipt"].exists() and not p["receipt"].is_symlink():
        return None
    r = _json(p["receipt"], c.root)
    expected = dict(schema=1, id=ID,
                    appid=str(game["appid"]), game_folder=str(p["exe"].parent.relative_to(c.prefix)), original_override=None)
    if any(r.get(k) != v for k, v in expected.items()) or r.get("phase") not in ("prepared", "enabled", "disabled"):
        raise AudioFixError("The audio-fix receipt does not match this game/component; existing files were preserved.")
    if not isinstance(r.get("version"), str) or not r["version"] or not _digest(r.get("dll_sha256")):
        raise AudioFixError("The audio-fix ownership identity is invalid.")
    for key, field, pattern in (("payload", "payload_file", r"dsound(?:-[0-9a-f]{64})?\.dll"),
                                ("backup", "registry_backup_file", r"original-user(?:-[0-9a-f]{64})?\.reg")):
        name = r.get(field, p[key].name)
        if not isinstance(name, str) or not re.fullmatch(pattern, name):
            raise AudioFixError("The audio-fix recovery path is invalid.")
        p[key] = _safe(p["store"] / name, c.root)
    if not _digest(r.get("registry_backup_sha256")) or _sha(_read(p["backup"], c.root, 16*1024*1024)) != r["registry_backup_sha256"]:
        raise AudioFixError("The audio-fix registry backup changed; existing files were preserved.")
    if _sha(_read(p["payload"], c.root)) != r["dll_sha256"]:
        raise AudioFixError("The audio-fix recovery file changed; existing files were preserved.")
    return r


def _current(record, manifest):
    return bool(record and record["version"] == manifest["version"] and record["dll_sha256"] == manifest["dll"]["sha256"])


def _inspect(c, game, manifest):
    p = _paths(c, game)
    for path in p.values():
        _safe(path, c.root)
    r = _record(c, p, manifest, game)
    raw = _read(p["registry"], c.root, 16*1024*1024)
    override = _registry_value(raw)
    present = p["target"].exists() or p["target"].is_symlink()
    if present:
        digest = _sha(_read(p["target"], c.root))
        if r is None or digest != r["dll_sha256"]:
            raise AudioFixError("An existing or changed dsound.dll was preserved; the audio fix will not replace it.")
    if override is not None and (r is None or override != OVERRIDE):
        raise AudioFixError("An existing or changed Dragon Age dsound override was preserved.")
    return p, r, present, override, raw


def _bound_game(c):
    """Read only the bounded prior descriptor; _inspect verifies its ownership."""
    receipt = _safe(c.data / "audio-fix/receipt.json", c.root)
    if not receipt.exists() and not receipt.is_symlink():
        return None
    record = _json(receipt, c.root)
    folder, appid = record.get("game_folder"), record.get("appid")
    if (appid not in ("17450", "47810") or not isinstance(folder, str) or not folder
            or Path(folder).is_absolute() or "\\" in folder
            or any(part in ("", ".", "..") for part in folder.split("/"))):
        raise AudioFixError("The prior audio-fix game location is invalid; existing files were preserved.")
    exe = _safe(c.prefix / folder / "DAOrigins.exe", c.prefix)
    return dict(appid=appid, exe=str(exe))


def _same_game(left, right):
    return bool(left and right and str(left.get("appid")) == str(right.get("appid"))
                and Path(left.get("exe", "")).absolute() == Path(right.get("exe", "")).absolute())


def status(c, game=None):
    """Read-only UI state; does not claim an installed fix is effective in play."""
    receipt = c.data / "audio-fix/receipt.json"
    managed = receipt.exists() or receipt.is_symlink()
    enabled = False
    pending = managed
    try:
        manifest, _ = _component()
        bound = _bound_game(c)
        if bound and not _same_game(bound, game):
            _inspect(c, bound, manifest)  # Never hide changed prior ownership.
            selected = _paths(c, game)
            if selected["target"].exists() or selected["target"].is_symlink():
                raise AudioFixError("An existing audio mod in the selected edition was preserved; the prior managed audio rule will be removed before launch.")
            _supported(c, selected, manifest)
            return dict(audio_fix_supported=True, audio_fix_enabled=False, audio_fix_managed=True,
                        audio_fix_pending=True, audio_fix_message="Audio compatibility will transfer to the selected Dragon Age edition.")
        _, record, present, override, _ = _inspect(c, game, manifest)
        enabled = bool(present and override == OVERRIDE)
        pending = bool(record and (record["phase"] == "prepared" or
            record["phase"] == "enabled" and not enabled or
            record["phase"] == "disabled" and (present or override is not None) or
            enabled and not _current(record, manifest)))
        _supported(c, _paths(c, game), manifest)
        message = ("Audio compatibility is enabled for Dragon Age: Origins only." if enabled else
                   "Audio compatibility is available." if not managed else "Audio compatibility is off or needs to finish an interrupted change.")
        return dict(audio_fix_supported=True, audio_fix_enabled=enabled, audio_fix_managed=managed, audio_fix_pending=pending, audio_fix_message=message)
    except (OSError, ValueError, TypeError, KeyError, AudioFixError) as exc:
        return dict(audio_fix_supported=False, audio_fix_enabled=enabled, audio_fix_managed=managed, audio_fix_pending=pending,
                    audio_fix_message=str(exc) or "The audio-fix state could not be verified.")


def _stopped(c):
    try:
        running = large_address.active_wine_processes(c)
    except large_address.LargeAddressError as exc:
        raise AudioFixError("Could not inspect the dedicated Wine session; audio settings were not changed.") from exc
    if running:
        raise AudioFixError("Close Dragon Age, its official launcher and Windows Steam before changing the audio fix.")


def _sync(folder):
    fd = os.open(folder, os.O_RDONLY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def _write(c, path, raw, expected=None, exclusive=False):
    """Atomic publish, preserving unknown existing contents and mode."""
    _safe(path, c.root)
    mode = stat.S_IMODE(path.stat().st_mode) if path.exists() else 0o600
    with tempfile.NamedTemporaryFile(prefix=".audio-fix-", dir=path.parent, delete=False) as handle:
        temp = Path(handle.name)
        try:
            os.fchmod(handle.fileno(), mode)
            handle.write(raw); handle.flush(); os.fsync(handle.fileno())
            _safe(path, c.root)
            if exclusive:
                os.link(temp, path)  # Never overwrite a file that appeared concurrently.
            else:
                if expected is not None and _sha(_read(path, c.root)) != expected:
                    raise AudioFixError("An audio-fix file changed during the operation; it was preserved.")
                os.replace(temp, path)
            _sync(path.parent)
        finally:
            temp.unlink(missing_ok=True)


def _save(c, p, record, expected):
    raw = (json.dumps(record, indent=2) + "\n").encode()
    _write(c, p["receipt"], raw, expected=expected, exclusive=expected is None)
    return _sha(raw)


def _store_blob(c, store, preferred, raw):
    """Preserve prior/unknown preparation evidence; never overwrite its bytes."""
    path = store / preferred
    if path.exists() or path.is_symlink():
        if _read(path, c.root) == raw:
            return path
        path = store / (Path(preferred).stem + "-" + _sha(raw) + Path(preferred).suffix)
    if path.exists() or path.is_symlink():
        if _read(path, c.root) != raw:
            raise AudioFixError("An audio-fix recovery file changed; it was preserved.")
    else:
        _write(c, path, raw, exclusive=True)
    return path


def _clear_previous_game(c, game, manifest):
    """Keep one managed active edition: the Wine loading rule is shared by name."""
    bound = _bound_game(c)
    if bound is None or _same_game(bound, game):
        return False
    _inspect(c, bound, manifest)
    _stopped(c)
    set_enabled(c, bound, False)
    p, _, present, override, _ = _inspect(c, bound, manifest)
    if present or override is not None:
        raise AudioFixError("The previous edition's audio fix could not be removed safely.")
    raw = _read(p["receipt"], c.root)
    _store_blob(c, p["store"], "receipt-" + _sha(raw) + ".json", raw)
    _stopped(c)
    if _sha(_read(p["receipt"], c.root)) != _sha(raw):
        raise AudioFixError("The previous audio receipt changed; it was preserved.")
    # Its owned game DLL and rule are already gone. A crash after this unlink
    # leaves an ordinary unmodified selected environment ready for fresh setup.
    p["receipt"].unlink()
    _sync(p["store"])
    return True


def set_enabled(c, game, enabled):
    """Caller holds its operation lock; controller handles any session shutdown."""
    if type(enabled) is not bool:
        raise AudioFixError("The audio-fix setting must be explicitly on or off.")
    manifest, payload = _component()
    _paths(c, game)  # Validate the selected descriptor before touching prior ownership.
    transferred = _clear_previous_game(c, game, manifest)
    if transferred and not enabled:
        return dict(ok=True, changed=True, **status(c, game))
    p, record, present, override, registry = _inspect(c, game, manifest)
    receipt_digest = _sha(_read(p["receipt"], c.root)) if record else None
    actual = present and override == OVERRIDE
    complete = actual if enabled else not present and override is None
    if complete and (not enabled or _current(record, manifest)) and (record is None or record["phase"] == ("enabled" if enabled else "disabled")):
        if enabled:
            _supported(c, p, manifest)
        return dict(ok=True, changed=False, **status(c, game))
    if enabled:
        _supported(c, p, manifest)
    _stopped(c)
    if enabled and record is not None and not _current(record, manifest):
        # Remove only verified ownership before upgrading; a crash leaves either
        # an intact old receipt or a prepared new one, never an unowned DLL.
        set_enabled(c, game, False)
        p, record, present, override, registry = _inspect(c, game, manifest)
        old_receipt = _read(p["receipt"], c.root)
        receipt_digest = _sha(old_receipt)
        _store_blob(c, p["store"], "receipt-" + receipt_digest + ".json", old_receipt)
        record = None
    if record is None:
        p["store"].mkdir(parents=True, exist_ok=True, mode=0o700)
        p["backup"] = _store_blob(c, p["store"], "original-user.reg", registry)
        p["payload"] = _store_blob(c, p["store"], "dsound.dll", payload)
        record = dict(schema=1,id=ID,version=manifest["version"],phase="prepared",appid=str(game["appid"]),
                      game_folder=str(p["exe"].parent.relative_to(c.prefix)),dll_sha256=_sha(payload),
                      payload_file=p["payload"].name,registry_backup_file=p["backup"].name,
                      original_override=None,registry_backup_sha256=_sha(registry))
    record.update(phase="prepared", requested_enabled=enabled)
    receipt_digest = _save(c, p, record, receipt_digest)  # Durable ownership before either game/registry mutation.
    _stopped(c)
    _, _, present, override, registry = _inspect(c, game, manifest)
    if enabled:
        _supported(c, p, manifest)
        support = _safe(c.prefix / manifest["status_directory"], c.root)
        support.mkdir(parents=True, exist_ok=True, mode=0o700)
        if not present:
            _stopped(c)
            _write(c, p["target"], payload, exclusive=True)
        if override is None:
            _stopped(c)
            if _sha(_read(p["target"], c.root)) != record["dll_sha256"]:
                raise AudioFixError("The installed audio file changed; its registry override was not added.")
            _write(c, p["registry"], _patch_registry(registry, True), expected=_sha(registry))
    else:
        if override is not None:
            _stopped(c)
            _write(c, p["registry"], _patch_registry(registry, False), expected=_sha(registry))
        if present:
            _stopped(c)
            if _sha(_read(p["target"], c.root)) != record["dll_sha256"]:
                raise AudioFixError("The installed audio file changed; it was preserved.")
            p["target"].unlink(); _sync(p["target"].parent)
    _, _, final_present, final_override, _ = _inspect(c, game, manifest)
    if final_present != enabled or final_override != (OVERRIDE if enabled else None):
        raise AudioFixError("The audio-fix change did not finish; its recovery receipt was preserved.")
    record["phase"] = "enabled" if enabled else "disabled"
    _save(c, p, record, receipt_digest)
    return dict(ok=True,changed=True,**status(c, game))
