#!/usr/bin/env python3
"""Recreate the pinned DAO runtime without running it or touching an existing one.

Requires macOS and Python 3.9+ (standard library only). Rosetta is required later
to run Wine, not for this bootstrap. HTTPS downloads require network access.

Example, from the source repository:
  python3 -B source/bootstrap_runtime.py \
    --project-root /path/to/isolated-data --cache /path/to/archive-cache

The native app runs this bootstrap after the user chooses setup. The explicit
cache must share a filesystem with the destination for atomic publication.
Existing archives are verified and reused. A bad cached archive causes an error;
it is never silently replaced. --validate-only validates archives without
extracting a runtime. An existing runtime is always preserved, even if incomplete.
The script does not initialize a prefix, install Steam, launch software, modify
Gatekeeper/quarantine, or modify the project's manifest. Source archive hashes
are fixed here rather than trusted from a mutable manifest.
"""
from __future__ import annotations

import argparse
from collections import deque
import ctypes
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import plistlib
import shutil
import sys
import tarfile
import tempfile
import unicodedata
import urllib.parse
import urllib.request


ASSETS = (
    {
        "name": "Template-1.0.24.tar.xz",
        "root": "Template-1.0.24.app",
        "url": "https://github.com/Sikarugir-App/Template/releases/download/v1.0/Template-1.0.24.tar.xz",
        "sha256": "4b5f89eeb9ef139936bdfad33d9b420b05ea4597cb7d63376674f7a8e171321c",
        "bytes": 96198448,
    },
    {
        "name": "WS12WineSikarugir11.0_1.tar.xz",
        "root": "wswine.bundle",
        "url": "https://github.com/Sikarugir-App/Engines/releases/download/v1.0/WS12WineSikarugir11.0_1.tar.xz",
        "sha256": "67e29fb3d74f363af39c69ba11f9b13a79812c5db07cf4748672658e4a200a0e",
        "bytes": 167322744,
    },
)
MAX_MEMBERS = 20000
MAX_EXPANDED_BYTES = 2 * 1024**3


class BootstrapError(RuntimeError):
    pass


def exists(path: Path) -> bool:
    return os.path.lexists(path)


def verify_archive(path: Path, asset: dict) -> None:
    if path.is_symlink() or not path.is_file():
        raise BootstrapError(f"Archive must be a regular, non-symlink file: {path}")
    if path.stat().st_size != asset["bytes"]:
        raise BootstrapError(f"Wrong archive size: {path}")
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    if digest.hexdigest() != asset["sha256"]:
        raise BootstrapError(f"SHA256 mismatch; cached archive preserved: {path}")


class HTTPSOnlyRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        if urllib.parse.urlsplit(newurl).scheme != "https":
            raise BootstrapError("Refusing a non-HTTPS archive redirect.")
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def archive_in_cache(cache: Path, asset: dict) -> Path:
    path = cache / asset["name"]
    if exists(path):
        verify_archive(path, asset)
        return path
    cache.mkdir(parents=True, exist_ok=True)
    # Private staging prevents a partial download from looking like a valid cache.
    with tempfile.TemporaryDirectory(prefix="download-", dir=cache) as temporary:
        pending = Path(temporary) / asset["name"]
        request = urllib.request.Request(asset["url"], headers={"User-Agent": "DAOMac-bootstrap/1.0"})
        opener = urllib.request.build_opener(HTTPSOnlyRedirect())
        with opener.open(request, timeout=60) as response, pending.open("xb") as out:
            received = 0
            while block := response.read(1024 * 1024):
                received += len(block)
                if received > asset["bytes"]:
                    raise BootstrapError("Archive download exceeded its pinned size.")
                out.write(block)
        verify_archive(pending, asset)
        try:
            # Atomic, and fails rather than replacing a concurrently created cache.
            os.link(pending, path)
        except FileExistsError:
            verify_archive(path, asset)
    return path


def path_key(parts) -> str:
    return unicodedata.normalize("NFC", "/".join(parts)).casefold()


def safe_members(archive: tarfile.TarFile, top: str) -> list[tarfile.TarInfo]:
    """Validate all writes and links before extraction, including link chains."""
    members = archive.getmembers()
    if len(members) > MAX_MEMBERS or sum(m.size for m in members) > MAX_EXPANDED_BYTES:
        raise BootstrapError("Archive exceeds extraction limits.")
    by_name = {}
    for member in members:
        p = PurePosixPath(member.name)
        if (p.is_absolute() or not p.parts or p.parts[0] != top
                or ".." in p.parts or "\\" in member.name
                or any(ord(c) < 32 for c in member.name)):
            raise BootstrapError(f"Unsafe archive path: {member.name!r}")
        if not (member.isdir() or member.isfile() or member.issym()):
            raise BootstrapError(f"Unsupported archive member type: {member.name!r}")
        key = path_key(p.parts)
        if key in by_name:
            raise BootstrapError(f"Duplicate or case-colliding archive path: {member.name!r}")
        by_name[key] = member
    for member in members:
        parts = PurePosixPath(member.name).parts
        for end in range(1, len(parts)):
            ancestor = by_name.get(path_key(parts[:end]))
            if ancestor and not ancestor.isdir():
                raise BootstrapError(f"Archive member traverses a non-directory: {member.name!r}")
        if not member.issym():
            continue
        link = PurePosixPath(member.linkname)
        if (not member.linkname or link.is_absolute() or "\\" in member.linkname
                or any(ord(c) < 32 for c in member.linkname)):
            raise BootstrapError(f"Unsafe symlink: {member.name!r}")
        pending = deque(parts[:-1] + link.parts)
        resolved = []
        traversed = 0
        while pending:
            part = pending.popleft()
            if part == ".":
                continue
            if part == "..":
                if len(resolved) <= 1:
                    raise BootstrapError(f"Symlink escapes archive root: {member.name!r}")
                resolved.pop()
                continue
            resolved.append(part)
            if resolved[0] != top:
                raise BootstrapError(f"Symlink escapes archive root: {member.name!r}")
            target = by_name.get(path_key(resolved))
            if target and target.issym():
                traversed += 1
                if traversed > 64:
                    raise BootstrapError(f"Cyclic or excessive symlink chain: {member.name!r}")
                resolved.pop()
                pending.extendleft(reversed(PurePosixPath(target.linkname).parts))
    return members


def extract_verified(path: Path, asset: dict, stage: Path | None) -> int:
    # Verify again immediately before reading/extracting; hashes are authoritative.
    verify_archive(path, asset)
    with tarfile.open(path, "r:xz") as archive:
        members = safe_members(archive, asset["root"])
        if stage is None:
            return len(members)
        for member in members:
            target = stage.joinpath(*PurePosixPath(member.name).parts)
            if member.isdir():
                target.mkdir(parents=True, exist_ok=True)
            elif member.isfile():
                target.parent.mkdir(parents=True, exist_ok=True)
                source = archive.extractfile(member)
                if source is None:
                    raise BootstrapError(f"Missing member data: {member.name}")
                with source, target.open("xb") as output:
                    shutil.copyfileobj(source, output)
                target.chmod(member.mode & 0o777)
        # Creating links last means no extracted file is written through a link.
        for member in members:
            if member.issym():
                target = stage.joinpath(*PurePosixPath(member.name).parts)
                target.parent.mkdir(parents=True, exist_ok=True)
                target.symlink_to(member.linkname)
    return len(members)


def configure_runtime(staged_app: Path, final_app: Path) -> None:
    info = staged_app / "Contents/Info.plist"
    value = plistlib.loads(info.read_bytes())
    suffix = hashlib.sha256(os.fsencode(final_app)).hexdigest()[:12]
    value.update({"CFBundleName": "DAO Runtime", "CFBundleIdentifier": f"local.dao.runtime.{suffix}",
                  "Debug Mode": True, "Skip Gecko": True, "Skip Mono": True,
                  "Symlinks In User Folder": 0, "WINEDEBUG": "-all,err+all",
                  "D9VK": 1, "DXVK": 0, "D3DMETAL": 0})
    user = final_app / "Contents/SharedSupport/prefix/drive_c/users/Sikarugir"
    for key, folder in [("Desktop", "Desktop"), ("Downloads", "Downloads"),
                        ("My Documents", "Documents"), ("My Music", "Music"),
                        ("My Pictures", "Pictures"), ("My Videos", "Videos"),
                        ("Templates", "Templates")]:
        value[f"Symlink {key}"] = str(user / folder)
    info.write_bytes(plistlib.dumps(value))


def publish_exclusively(source: Path, destination: Path) -> None:
    """macOS atomic rename with RENAME_EXCL: even an empty target is preserved."""
    if sys.platform != "darwin":
        raise BootstrapError("Runtime installation requires macOS; validation is portable.")
    libc = ctypes.CDLL(None, use_errno=True)
    rename = libc.renamex_np
    rename.argtypes = (ctypes.c_char_p, ctypes.c_char_p, ctypes.c_uint)
    rename.restype = ctypes.c_int
    if rename(os.fsencode(source), os.fsencode(destination), 0x00000004):
        error = ctypes.get_errno()
        raise OSError(error, os.strerror(error), str(destination))


def bootstrap(project: Path, cache: Path, validate_only: bool = False) -> dict:
    project = project.expanduser().resolve()
    destination = project / "runtime/DAO Runtime.app"
    if exists(destination) and not validate_only:
        return {"ok": True, "status": "preserved", "runtime": str(destination),
                "message": "Runtime already exists. Nothing was changed or downloaded."}
    cache = cache.expanduser().resolve()
    if cache == Path.home().resolve() or cache == Path("/"):
        raise BootstrapError("Use an explicit work/cache directory, not the home or filesystem root.")
    if not validate_only and destination.parent.is_symlink():
        raise BootstrapError("The runtime directory must not be a symlink.")
    paths = [archive_in_cache(cache, asset) for asset in ASSETS]
    if validate_only:
        counts = [extract_verified(path, asset, None) for path, asset in zip(paths, ASSETS)]
        return {"ok": True, "status": "validated", "members": counts,
                "message": "Both archive hashes and contained paths/links passed. No runtime extracted or executed."}
    destination.parent.mkdir(parents=True, exist_ok=True)
    if cache.stat().st_dev != destination.parent.stat().st_dev:
        raise BootstrapError("Cache and project must use the same filesystem for atomic installation.")
    with tempfile.TemporaryDirectory(prefix="dao-runtime-stage-", dir=cache) as temporary:
        stage = Path(temporary)
        for path, asset in zip(paths, ASSETS):
            extract_verified(path, asset, stage)
        app = stage / ASSETS[0]["root"]
        support = app / "Contents/SharedSupport"
        if exists(support / "prefix") or exists(support / "wine"):
            raise BootstrapError("Unexpected existing prefix or engine in template.")
        (stage / ASSETS[1]["root"]).rename(support / "wine")
        configure_runtime(app, destination)
        publish_exclusively(app, destination)
    return {"ok": True, "status": "created", "runtime": str(destination),
            "message": "Pinned runtime created. No prefix initialized and no software executed."}


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--project-root", type=Path, required=True, help="Dedicated data folder for runtime/")
    parser.add_argument("--cache", type=Path, required=True, help="Explicit project/work cache on the same filesystem; existing pinned archives are reused")
    parser.add_argument("--validate-only", action="store_true", help="Verify both pinned archives and path/link safety without runtime extraction")
    args = parser.parse_args(argv)
    try:
        print(json.dumps(bootstrap(args.project_root, args.cache, args.validate_only), indent=2))
        return 0
    except (BootstrapError, OSError, ValueError, tarfile.TarError) as exc:
        print(json.dumps({"ok": False, "message": str(exc)}))
        return 1


if __name__ == "__main__":
    sys.exit(main())
