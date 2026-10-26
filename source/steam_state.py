"""Read Dragon Age installations from a dedicated Windows Steam Wine prefix.

Supported layout: Steam in C:\\Program Files (x86)\\Steam or
C:\\Program Files\\Steam. Additional libraries may use C: or a dosdevices
drive mapping, but every resolved target must remain inside ``prefix``.
External libraries, UNC paths and traversals are deliberately unsupported.

This module never changes files, runs Steam, or establishes game ownership.
``complete`` describes observable installation state, not playability.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Dict, Iterator, List, Optional, Tuple, Union


GAMES = {
    "17450": "Dragon Age: Origins",
    "47810": "Dragon Age: Origins - Ultimate Edition",
}
MAX_VDF_BYTES = 1024 * 1024
MAX_TOKENS = 100000
MAX_DEPTH = 64
KVValue = Union[str, Dict[str, "KVValue"]]


class _InvalidVDF(ValueError):
    pass


def _tokens(text: str) -> Iterator[Tuple[str, str]]:
    """Tokenize quoted/bare KeyValues tokens, braces and comments."""
    if "\x00" in text:
        raise _InvalidVDF("NUL in KeyValues")
    i, count = 0, 0
    while i < len(text):
        if text[i].isspace() or (i == 0 and text[i] == "\ufeff"):
            i += 1
            continue
        if text.startswith("//", i):
            newline = text.find("\n", i + 2)
            i = len(text) if newline < 0 else newline + 1
            continue
        if text.startswith("/*", i):
            end = text.find("*/", i + 2)
            if end < 0:
                raise _InvalidVDF("Unterminated comment")
            i = end + 2
            continue
        count += 1
        if count > MAX_TOKENS:
            raise _InvalidVDF("Too many tokens")
        char = text[i]
        if char in "{}":
            yield char, char
            i += 1
        elif char == '"':
            i += 1
            value = []
            while i < len(text) and text[i] != '"':
                if text[i] == "\\":
                    i += 1
                    if i == len(text):
                        raise _InvalidVDF("Unterminated escape")
                    escaped = text[i]
                    escapes = {'"': '"', "\\": "\\", "n": "\n", "r": "\r", "t": "\t"}
                    # Preserve unknown escapes, e.g. an unescaped Windows \\P.
                    value.append(escapes.get(escaped, "\\" + escaped))
                else:
                    value.append(text[i])
                i += 1
            if i == len(text):
                raise _InvalidVDF("Unterminated quoted string")
            i += 1
            yield "value", "".join(value)
        else:
            start = i
            while i < len(text) and not text[i].isspace() and text[i] not in '{}"':
                i += 1
            yield "value", text[start:i]


def _parse_keyvalues(text: str) -> Dict[str, KVValue]:
    """Parse a complete document; reject ambiguity and malformed nesting."""
    tokens = iter(_tokens(text))

    def block(nested: bool, depth: int) -> Dict[str, KVValue]:
        if depth > MAX_DEPTH:
            raise _InvalidVDF("Excessive nesting")
        result: Dict[str, KVValue] = {}
        for kind, key in tokens:
            if kind == "}":
                if nested:
                    return result
                raise _InvalidVDF("Unexpected closing brace")
            if kind != "value":
                raise _InvalidVDF("Expected key")
            key = key.casefold()
            if key in result:
                raise _InvalidVDF("Duplicate key")
            value = next(tokens, None)
            if value is None:
                raise _InvalidVDF("Missing value")
            if value[0] == "{":
                result[key] = block(True, depth + 1)
            elif value[0] == "value":
                result[key] = value[1]
            else:
                raise _InvalidVDF("Expected value")
        if nested:
            raise _InvalidVDF("Unclosed object")
        return result

    return block(False, 0)


def _within(path: Path, boundary: Path) -> bool:
    try:
        path.relative_to(boundary)
        return True
    except ValueError:
        return False


def _boundary(prefix: Path) -> Optional[Path]:
    try:
        resolved = prefix.resolve(strict=True)
        return resolved if resolved.is_dir() else None
    except (OSError, RuntimeError, ValueError):
        return None


def _child(parent: Path, name: str, boundary: Path) -> Optional[Path]:
    """Resolve one component case-insensitively without following escapes."""
    try:
        candidate = parent / name
        if not candidate.exists() and not candidate.is_symlink() and parent.is_dir():
            matches = [p for p in parent.iterdir() if p.name.casefold() == name.casefold()]
            if len(matches) > 1:
                return None  # Ambiguous on a case-sensitive filesystem.
            if matches:
                candidate = matches[0]
        candidate = candidate.resolve(strict=False)
        return candidate if _within(candidate, boundary) else None
    except (OSError, RuntimeError, ValueError):
        return None


def _path(parent: Path, parts: List[str], boundary: Path) -> Optional[Path]:
    for part in parts:
        parent = _child(parent, part, boundary)
        if parent is None:
            return None
    return parent


def _read_vdf(path: Optional[Path], boundary: Path) -> Optional[Dict[str, KVValue]]:
    if path is None:
        return None
    try:
        path = path.resolve(strict=True)
        if not _within(path, boundary) or not path.is_file():
            return None
        with path.open("rb") as handle:
            raw = handle.read(MAX_VDF_BYTES + 1)
        if len(raw) > MAX_VDF_BYTES:
            return None
        return _parse_keyvalues(raw.decode("utf-8-sig"))
    except (OSError, RuntimeError, ValueError, UnicodeError):
        return None


def find_steam(prefix: Path) -> Optional[Path]:
    """Return the Windows Steam executable inside prefix, if present."""
    boundary = _boundary(prefix)
    if boundary is None:
        return None
    for program_files in ("Program Files (x86)", "Program Files"):
        executable = _path(boundary, ["drive_c", program_files, "Steam", "steam.exe"], boundary)
        if executable is not None and executable.is_file():
            return executable
    return None


def _parts(value: str) -> Optional[List[str]]:
    if not value or any(ord(c) < 32 for c in value) or ":" in value:
        return None
    pieces = re.split(r"[\\/]", value)
    if any(piece in ("", ".", "..") or piece.rstrip(" .") != piece for piece in pieces):
        return None
    return pieces


def _library_path(value: str, boundary: Path) -> Optional[Path]:
    match = re.fullmatch(r"([A-Za-z]):[\\/](.*)", value)
    if match is None:
        return None
    drive, suffix = match.groups()
    suffix = suffix.rstrip("\\/")
    parts = _parts(suffix) if suffix else []
    if parts is None:
        return None
    if drive.casefold() == "c":
        root = _child(boundary, "drive_c", boundary)
    else:
        root = _path(boundary, ["dosdevices", drive.casefold() + ":"], boundary)
    if root is None or not root.is_dir():
        return None
    return _path(root, parts, boundary)


def _libraries(steam_dir: Path, boundary: Path) -> List[Path]:
    libraries = [steam_dir]
    # Current Steam uses steamapps; also accept its older config location.
    for location in ("steamapps", "config"):
        document = _read_vdf(_path(steam_dir, [location, "libraryfolders.vdf"], boundary), boundary)
        folders = document.get("libraryfolders") if document else None
        if not isinstance(folders, dict):
            continue
        for key, entry in folders.items():
            if not key.isdecimal():
                continue
            value = entry.get("path") if isinstance(entry, dict) else entry
            if not isinstance(value, str):
                continue
            library = _library_path(value, boundary)
            if library is not None and library.is_dir() and library not in libraries:
                libraries.append(library)
    return libraries


def _number(state: Dict[str, KVValue], key: str) -> Optional[int]:
    value = state.get(key, "0")
    if not isinstance(value, str) or not re.fullmatch(r"[0-9]{1,20}", value):
        return None
    return int(value)


def discover_games(prefix: Path) -> List[dict]:
    """Return existing/download-in-progress DAO records; never infer ownership.

    Only FullyInstalled (4), optionally combined with AppRunning (64), is
    accepted as complete. All update/download/validation/corruption states,
    and unknown flags, remain incomplete. Missing executables also prevent
    completeness even if a manifest claims that installation finished.
    """
    boundary = _boundary(prefix)
    steam = find_steam(prefix)
    if boundary is None or steam is None:
        return []
    found: List[dict] = []
    seen = set()
    for library in _libraries(steam.parent, boundary):
        steamapps = _child(library, "steamapps", boundary)
        if steamapps is None:
            continue
        for appid, title in GAMES.items():
            document = _read_vdf(_child(steamapps, "appmanifest_" + appid + ".acf", boundary), boundary)
            state = document.get("appstate") if document else None
            if not isinstance(state, dict) or state.get("appid") != appid:
                continue
            installdir = state.get("installdir")
            parts = _parts(installdir) if isinstance(installdir, str) else None
            if parts is None:
                continue
            game_dir = _path(steamapps, ["common"] + parts, boundary)
            if game_dir is None or (appid, game_dir) in seen:
                continue
            numbers = [_number(state, key) for key in
                       ("stateflags", "bytestodownload", "bytesdownloaded", "bytestostage", "bytesstaged")]
            if any(number is None for number in numbers):
                continue
            flags, to_download, downloaded, to_stage, staged = numbers
            executable = _path(game_dir, ["bin_ship", "DAOrigins.exe"], boundary)
            has_exe = executable is not None and executable.is_file()
            complete = bool(has_exe and flags in (4, 4 | 64)
                            and downloaded >= to_download and staged >= to_stage)
            found.append({
                "appid": appid,
                "title": title,
                "game_dir": str(game_dir),
                "exe": str(executable) if has_exe else "",
                "complete": complete,
                "bytes_to_download": to_download,
                "bytes_downloaded": downloaded,
            })
            seen.add((appid, game_dir))
    return found
