"""Opt-in, per-game address-space support for one hash-pinned Wine runtime.

The caller holds Controller.operation(). This module never launches/stops Wine,
reads game files, or changes game executables. All runtime mutation requires a
successful full process inventory showing that the dedicated Wine session is
stopped. A prepared receipt precedes the atomic runtime rename so interruption
recovery is decided by the actual installed hash, never by a stale phase label.
"""
from __future__ import annotations

import ctypes
import datetime as dt
import hashlib
import json
import os
from pathlib import Path
import shutil
import stat
import struct
import subprocess
import tempfile

from laa_stub import (ORIGINAL_SHA256, ORIGINAL_BYTES, PATCH_OFFSET, PATCH_BYTES,
                      STUB_OFFSET, STUB_CODE, STUB_SHA256, STUB_VERSION)

SCHEMA = 1
MAX_NATIVE_BYTES = 8 * 1024 * 1024


class LargeAddressError(RuntimeError):
    pass


def _sha(raw):
    return hashlib.sha256(raw).hexdigest()


def _now():
    return dt.datetime.now(dt.timezone.utc).isoformat()


def _paths(c):
    directory = c.data / "large-address"
    return dict(target=c.contents / "SharedSupport/wine/lib/wine/x86_64-unix/ntdll.so",
                directory=directory, original=directory / "original-ntdll.so",
                candidate=directory / "patched-ntdll.so", receipt=directory / "receipt.json")


def _contained(c, path):
    """Reject linked manager/runtime paths, including links that stay in root."""
    root = Path(c.root).resolve()
    try:
        relative = path.absolute().relative_to(root)
        path.resolve().relative_to(root)
    except (ValueError, RuntimeError) as exc:
        raise LargeAddressError("The 4 GB support path is outside this launcher's environment.") from exc
    current = root
    for part in relative.parts:
        current /= part
        if current.is_symlink():
            raise LargeAddressError("The 4 GB support path contains a symbolic link; no files were changed.")
    return path


def _read(c, path, limit=MAX_NATIVE_BYTES):
    _contained(c, path)
    flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0)
    with os.fdopen(os.open(path, flags), "rb") as handle:
        info = os.fstat(handle.fileno())
        if not stat.S_ISREG(info.st_mode) or info.st_size > limit:
            raise LargeAddressError("The 4 GB support file has an unexpected type or size.")
        raw = handle.read(limit + 1)
    if len(raw) > limit:
        raise LargeAddressError("The 4 GB support file is too large.")
    return raw


def _macho(raw):
    """Inspect bounds needed for the patch, unused padding and signing changes."""
    if len(raw) < 32 or struct.unpack_from("<II", raw) != (0xfeedfacf, 0x01000007):
        raise LargeAddressError("4 GB support requires the pinned x86_64 Wine module.")
    ncmds, command_size = struct.unpack_from("<II", raw, 16)
    end = 32 + command_size
    if not 0 < ncmds <= 64 or end > len(raw):
        raise LargeAddressError("Invalid Wine Mach-O load commands.")
    at, text, sections, signature, mutable = 32, None, [], None, []
    for _ in range(ncmds):
        if at + 8 > end:
            raise LargeAddressError("Truncated Wine load command.")
        kind, size = struct.unpack_from("<II", raw, at)
        if size < 8 or at + size > end:
            raise LargeAddressError("Invalid Wine load command size.")
        if kind == 0x19:
            if size < 72:
                raise LargeAddressError("Invalid Wine segment.")
            name, vmaddr, vmsize, offset, length = struct.unpack_from("<16sQQQQ", raw, at + 8)
            name = name.rstrip(b"\0")
            count = struct.unpack_from("<I", raw, at + 64)[0]
            if 72 + count * 80 > size:
                raise LargeAddressError("Invalid Wine section list.")
            if name == b"__TEXT":
                if text is not None or vmaddr != 0 or offset != 0 or length > len(raw):
                    raise LargeAddressError("Unexpected Wine text segment mapping.")
                text = (offset, length)
                for index in range(count):
                    section = at + 72 + index * 80
                    sectname, segname, address, sectsize, fileoff = struct.unpack_from("<16s16sQQI", raw, section)
                    if fileoff != address or fileoff + sectsize > length:
                        raise LargeAddressError("Unexpected Wine text section mapping.")
                    sections.append((sectname.rstrip(b"\0"), fileoff, sectsize))
            elif name == b"__LINKEDIT":
                mutable += [(at + 32, 8), (at + 48, 8)]  # vmsize / filesize only
        elif kind == 0x1d:
            if size != 16 or signature is not None:
                raise LargeAddressError("Unexpected Wine signature command.")
            offset, length = struct.unpack_from("<II", raw, at + 8)
            signature = (offset, length)
            mutable.append((at + 12, 4))  # Signature size may shrink on re-signing.
        at += size
    if at != end or text is None or signature is None:
        raise LargeAddressError("Wine module is missing expected text/signature metadata.")
    if signature[0] + signature[1] != len(raw) or signature[0] < text[1]:
        raise LargeAddressError("Unexpected Wine signature bounds.")
    return dict(text=text, sections=sections, signature=signature, mutable=mutable)


def _unsigned(original):
    if _sha(original) != ORIGINAL_SHA256 or _sha(STUB_CODE) != STUB_SHA256:
        raise LargeAddressError("The Wine module or 4 GB helper does not match the supported version.")
    meta = _macho(original)
    if len(ORIGINAL_BYTES) != len(PATCH_BYTES) or not ORIGINAL_BYTES:
        raise LargeAddressError("Invalid 4 GB patch definition.")
    if not any(name == b"__text" and start <= PATCH_OFFSET and
               PATCH_OFFSET + len(ORIGINAL_BYTES) <= start + length
               for name, start, length in meta["sections"]):
        raise LargeAddressError("The 4 GB patch is outside the expected Wine code section.")
    last_section = max(start + length for _, start, length in meta["sections"])
    if (STUB_OFFSET < last_section or STUB_OFFSET + len(STUB_CODE) > meta["text"][1]
            or not STUB_CODE or original[STUB_OFFSET:STUB_OFFSET + len(STUB_CODE)] != bytes(len(STUB_CODE))
            or original[PATCH_OFFSET:PATCH_OFFSET + len(ORIGINAL_BYTES)] != ORIGINAL_BYTES):
        raise LargeAddressError("Wine's expected 4 GB patch location or unused padding has changed.")
    patched = bytearray(original)
    patched[PATCH_OFFSET:PATCH_OFFSET + len(PATCH_BYTES)] = PATCH_BYTES
    patched[STUB_OFFSET:STUB_OFFSET + len(STUB_CODE)] = STUB_CODE
    return bytes(patched)


def _validate_candidate(original, candidate):
    expected = bytearray(_unsigned(original))
    actual = bytearray(candidate)
    before, after = _macho(original), _macho(candidate)
    if before["signature"][0] != after["signature"][0] or before["mutable"] != after["mutable"]:
        raise LargeAddressError("The managed 4 GB module's structure has changed.")
    for offset, length in before["mutable"]:
        expected[offset:offset + length] = bytes(length)
        actual[offset:offset + length] = bytes(length)
    signature_at = before["signature"][0]
    if expected[:signature_at] != actual[:signature_at]:
        raise LargeAddressError("The managed 4 GB module contains unexpected changes.")


def _load_record(c, paths):
    try:
        record = json.loads(_read(c, paths["receipt"], 16384))
    except (ValueError, TypeError) as exc:
        raise LargeAddressError("The 4 GB support receipt is damaged; existing files were preserved.") from exc
    expected = dict(schema_version=SCHEMA, original_sha256=ORIGINAL_SHA256,
                    stub_version=STUB_VERSION, stub_sha256=STUB_SHA256,
                    patch_offset=PATCH_OFFSET, patch_bytes=PATCH_BYTES.hex(), stub_offset=STUB_OFFSET)
    if not isinstance(record, dict) or any(record.get(k) != v for k, v in expected.items()):
        raise LargeAddressError("The 4 GB support receipt belongs to an unsupported or changed helper.")
    digest = record.get("prototype_sha256")
    if not isinstance(digest, str) or len(digest) != 64 or any(ch not in "0123456789abcdef" for ch in digest):
        raise LargeAddressError("The 4 GB support receipt has an invalid module hash.")
    for key in ("original_mode", "original_mtime_ns", "original_size"):
        if type(record.get(key)) is not int or record[key] < 0:
            raise LargeAddressError("The 4 GB support receipt has invalid original-file metadata.")
    if record["original_mode"] & ~0o777:
        raise LargeAddressError("The 4 GB support receipt has invalid original-file permissions.")
    original = _read(c, paths["original"])
    candidate = _read(c, paths["candidate"])
    if (_sha(original) != ORIGINAL_SHA256 or len(original) != record["original_size"]
            or _sha(candidate) != digest):
        raise LargeAddressError("The 4 GB backup or managed module has changed; no runtime files were replaced.")
    _validate_candidate(original, candidate)
    return record


def _inspection(c):
    paths = _paths(c)
    for path in paths.values():
        _contained(c, path)
    raw = _read(c, paths["target"])
    current = _sha(raw)
    if paths["receipt"].exists():
        record = _load_record(c, paths)
        if current not in (ORIGINAL_SHA256, record["prototype_sha256"]):
            raise LargeAddressError("Wine was changed outside the 4 GB manager; no existing files were replaced.")
        return paths, record, current == record["prototype_sha256"]
    if paths["candidate"].exists():
        # Candidate publication can precede an interrupted first receipt write.
        # Recover only the exact intended code change with the original runtime
        # still installed and its exact backup present. Unknown files stay put.
        if current != ORIGINAL_SHA256:
            raise LargeAddressError("An incomplete 4 GB preparation cannot be verified; existing files were preserved.")
        original = _read(c, paths["original"])
        _validate_candidate(original, _read(c, paths["candidate"]))
        return paths, None, False
    if current != ORIGINAL_SHA256:
        raise LargeAddressError("4 GB support is unavailable for this Wine version.")
    _unsigned(raw)
    if paths["original"].exists() and _sha(_read(c, paths["original"])) != ORIGINAL_SHA256:
        raise LargeAddressError("The saved Wine backup has changed; no existing files were replaced.")
    return paths, None, False


def status(c):
    """Read-only capability/state; an unsupported managed state needs repair."""
    paths = _paths(c)
    managed = any(paths[key].exists() or paths[key].is_symlink() for key in ("receipt", "original", "candidate"))
    try:
        _, _, enabled = _inspection(c)
        return dict(laa_supported=True, laa_enabled=enabled, laa_managed=managed,
                    laa_message="4 GB memory support is enabled for Dragon Age: Origins only." if enabled
                    else "Optional 4 GB memory support is available for Dragon Age: Origins.")
    except (OSError, ValueError, struct.error, LargeAddressError) as exc:
        message = "Set up the compatibility runtime to use optional 4 GB memory support." if isinstance(exc, FileNotFoundError) and not managed else str(exc)
        return dict(laa_supported=False, laa_enabled=False, laa_managed=managed,
                    laa_message=message or "The 4 GB support state could not be verified.")


def strict_processes(c):
    """Full inventory; every possible owned Wine process must be inspectable."""
    try:
        result = subprocess.run(["/bin/ps", "-axo", "pid=,ppid=,uid=,stat=,command="],
                                capture_output=True, text=True, timeout=5, check=True)
        rows = []
        for line in result.stdout.splitlines():
            fields = line.strip().split(None, 4)
            if len(fields) != 5 or not all(x.isdigit() for x in fields[:3]):
                raise LargeAddressError("Could not read a complete process inventory; 4 GB support was not changed.")
            rows.append((int(fields[0]), int(fields[1]), int(fields[2]), fields[3], fields[4]))
        if not any(row[0] == 1 for row in rows):
            raise LargeAddressError("Could not verify process visibility; 4 GB support was not changed.")
        lib = ctypes.CDLL("/usr/lib/libproc.dylib")
        lib.proc_pidpath.argtypes = [ctypes.c_int, ctypes.c_void_p, ctypes.c_uint32]
        lib.proc_pidpath.restype = ctypes.c_int
        own = set()
        runtime = Path(c.runtime).resolve()
        for pid, _, uid, state, command in rows:
            if uid != os.getuid() or state.startswith("Z"):
                continue
            # Windows images expose .exe names; native Wine processes expose
            # the dedicated runtime path. Unrelated native apps need not grant
            # proc_pidpath access. Keep all rows for descendant propagation.
            if ".exe" not in command.casefold() and str(runtime) not in command:
                continue
            buffer = ctypes.create_string_buffer(4096)
            if lib.proc_pidpath(pid, buffer, len(buffer)) <= 0:
                try:
                    os.kill(pid, 0)
                except ProcessLookupError:
                    continue
                raise LargeAddressError(f"Could not inspect process {pid}; 4 GB support was not changed.")
            executable = Path(os.fsdecode(buffer.value)).resolve()
            if runtime in executable.parents:
                own.add(pid)
        while True:
            expanded = own | {pid for pid, parent, _, state, _ in rows if parent in own and not state.startswith("Z")}
            if expanded == own:
                break
            own = expanded
        return [(pid, parent, command) for pid, parent, _, _, command in rows if pid in own]
    except (OSError, subprocess.SubprocessError) as exc:
        raise LargeAddressError("Could not inspect the dedicated Wine session; 4 GB support was not changed.") from exc


def active_wine_processes(c):
    configure = str(c.contents / "Configure.app/Contents/MacOS/Configure")
    return [row for row in strict_processes(c) if row[2] != configure]


def _ensure_stopped(c):
    if active_wine_processes(c):
        raise LargeAddressError("Close Dragon Age and Windows Steam before changing 4 GB memory support.")


def _sync_directory(path):
    fd = os.open(path, os.O_RDONLY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def _write_record(c, path, record):
    _contained(c, path)
    with tempfile.NamedTemporaryFile(prefix="receipt-", suffix=".tmp", dir=path.parent, delete=False) as handle:
        temporary = Path(handle.name)
        try:
            os.chmod(temporary, 0o600)
            handle.write((json.dumps(record, indent=2) + "\n").encode())
            handle.flush()
            os.fsync(handle.fileno())
            _contained(c, path)
            os.replace(temporary, path)
            _sync_directory(path.parent)
        finally:
            if temporary.exists():
                temporary.unlink()


def _codesign(path, sign=False):
    arguments = ["/usr/bin/codesign", "--force", "--sign", "-", str(path)] if sign else ["/usr/bin/codesign", "--verify", "--strict", str(path)]
    try:
        subprocess.run(arguments, capture_output=True, text=True, timeout=30, check=True)
    except (OSError, subprocess.SubprocessError) as exc:
        raise LargeAddressError("The local 4 GB Wine module could not be signed or verified; the runtime was preserved.") from exc


def _new_record(info, original, candidate):
    return dict(schema_version=SCHEMA, phase="prepared", created_at=_now(),
        original_sha256=ORIGINAL_SHA256, prototype_sha256=_sha(candidate),
        original_size=len(original), original_mode=info.st_mode & 0o777,
        original_mtime_ns=info.st_mtime_ns, stub_version=STUB_VERSION,
        stub_sha256=STUB_SHA256, patch_offset=PATCH_OFFSET,
        patch_bytes=PATCH_BYTES.hex(), stub_offset=STUB_OFFSET)


def _prepare(c, paths):
    original = _read(c, paths["target"])
    patched = _unsigned(original)
    info = paths["target"].stat()
    _contained(c, paths["directory"])
    paths["directory"].mkdir(mode=0o700, parents=True, exist_ok=True)
    paths["directory"].chmod(0o700)
    if not paths["original"].exists():
        fd = os.open(paths["original"], os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0), 0o600)
        try:
            with os.fdopen(fd, "wb") as handle:
                handle.write(original)
                handle.flush()
                os.fsync(handle.fileno())
            os.utime(paths["original"], ns=(info.st_atime_ns, info.st_mtime_ns))
            _sync_directory(paths["directory"])
        except BaseException:
            # Only this call's exclusive incomplete backup may be removed.
            paths["original"].unlink(missing_ok=True)
            raise
    if _sha(_read(c, paths["original"])) != ORIGINAL_SHA256:
        raise LargeAddressError("The original Wine backup could not be verified.")
    if paths["receipt"].exists():
        raise LargeAddressError("A 4 GB preparation already exists; it was preserved.")
    if paths["candidate"].exists():
        candidate = _read(c, paths["candidate"])
        _validate_candidate(original, candidate)
        _codesign(paths["candidate"])
        record = _new_record(info, original, candidate)
        _write_record(c, paths["receipt"], record)
        return record
    with tempfile.NamedTemporaryFile(prefix="candidate-", suffix=".so", dir=paths["directory"], delete=False) as handle:
        temporary = Path(handle.name)
        try:
            handle.write(patched)
            handle.flush()
            os.fsync(handle.fileno())
            os.chmod(temporary, info.st_mode & 0o777)
            _codesign(temporary, sign=True)
            _codesign(temporary)
            candidate = _read(c, temporary)
            _validate_candidate(original, candidate)
            record = _new_record(info, original, candidate)
            os.replace(temporary, paths["candidate"])
            _sync_directory(paths["directory"])
            _write_record(c, paths["receipt"], record)
            return record
        finally:
            if temporary.exists():
                temporary.unlink()


def _replace_runtime(c, paths, record, enabled, expected_current):
    source = paths["candidate"] if enabled else paths["original"]
    expected_source = record["prototype_sha256"] if enabled else ORIGINAL_SHA256
    if _sha(_read(c, source)) != expected_source:
        raise LargeAddressError("The saved Wine module changed before installation.")
    target = paths["target"]
    with tempfile.NamedTemporaryFile(prefix=".ntdll-laa-", suffix=".tmp", dir=target.parent, delete=False) as handle:
        temporary = Path(handle.name)
    try:
        shutil.copyfile(source, temporary)
        temporary.chmod(record["original_mode"])
        if not enabled:
            os.utime(temporary, ns=(record["original_mtime_ns"], record["original_mtime_ns"]))
        with temporary.open("rb") as handle:
            os.fsync(handle.fileno())
        if _sha(_read(c, temporary)) != expected_source:
            raise LargeAddressError("The staged Wine module did not verify.")
        _codesign(temporary)
        _ensure_stopped(c)
        if _sha(_read(c, target)) != expected_current:
            raise LargeAddressError("Wine changed during preparation; no existing runtime was overwritten.")
        os.replace(temporary, target)
        _sync_directory(target.parent)
    finally:
        if temporary.exists():
            temporary.unlink()


def set_enabled(c, enabled):
    """Enable/restore only verified native files while the caller holds its lock."""
    if type(enabled) is not bool:
        raise LargeAddressError("The 4 GB setting must be explicitly on or off.")
    paths, record, current_enabled = _inspection(c)
    if current_enabled == enabled:
        return dict(ok=True, changed=False, **status(c))
    _ensure_stopped(c)
    if record is None:
        record = _prepare(c, paths)
    # Persist prepared state before the only externally observable mutation.
    # An interrupted final receipt write is recoverable from the installed hash.
    record = dict(record, phase="prepared", requested_enabled=enabled, updated_at=_now())
    _write_record(c, paths["receipt"], record)
    expected_current = record["prototype_sha256"] if current_enabled else ORIGINAL_SHA256
    _replace_runtime(c, paths, record, enabled, expected_current)
    record.update(phase="enabled" if enabled else "disabled", updated_at=_now())
    _write_record(c, paths["receipt"], record)
    return dict(ok=True, changed=True,
                message="4 GB memory support enabled for Dragon Age: Origins only." if enabled else "Normal Dragon Age memory limits restored.",
                **status(c))
