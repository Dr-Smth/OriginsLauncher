"""Resolve Wine's actual user profile without assuming the wrapper renamed it.

Only relevant profile/shell-folder values are inspected. No registry values are
rewritten. Containment replaces links inside the prefix, never their targets.
"""
from __future__ import annotations

import json
from pathlib import Path
import re


class ProfileError(ValueError):
    pass


SHELL = r"software\microsoft\windows\currentversion\explorer\shell folders"
USER_SHELL = r"software\microsoft\windows\currentversion\explorer\user shell folders"
VOLATILE = "volatile environment"
FOLDERS = {"Desktop": ("Desktop", "desktop"), "Downloads": ("Downloads", "{374de290-123f-4565-9164-39c4925e467b}"),
           "My Documents": ("Documents", "personal"), "My Music": ("Music", "my music"),
           "My Pictures": ("Pictures", "my pictures"), "My Videos": ("Videos", "my video"),
           "Templates": ("Templates", "templates")}
RELEVANT = {"userprofile", "username", "appdata", "local appdata", *(value[1] for value in FOLDERS.values())}


def _within(path, prefix):
    try:
        path.resolve().relative_to(prefix.resolve())
    except (ValueError, OSError, RuntimeError) as exc:
        raise ProfileError("A Windows user-folder path escapes the dedicated prefix. Its target was preserved; setup must not continue.") from exc


def _registry(prefix):
    path = prefix / "user.reg"
    _within(path, prefix)
    if not path.exists():
        return {}
    with path.open("rb") as handle:
        raw = handle.read(16 * 1024 * 1024 + 1)
    if len(raw) > 16 * 1024 * 1024:
        raise ProfileError("The Windows user registry exceeds its expected size.")
    try:
        text = raw.decode("utf-8")
    except UnicodeError as exc:
        raise ProfileError("The Windows user registry could not be read safely.") from exc
    if not text.startswith("WINE REGISTRY Version 2"):
        raise ProfileError("The Windows user registry is incomplete or has an unsupported format.")
    result, section = {}, None
    for line in text.splitlines():
        heading = re.match(r"^\[([^]]+)\]", line)
        if line.startswith("[") and not heading:
            raise ProfileError("The Windows user registry contains an incomplete section.")
        if heading:
            section = heading[1].replace("\\\\", "\\").casefold()
            continue
        if section not in (SHELL, USER_SHELL, VOLATILE):
            continue
        field = re.match(r'^("(?:\\.|[^"\\])*")=(.*)$', line)
        if not field:
            continue
        try:
            key = json.loads(field[1]).casefold()
        except (ValueError, AttributeError):
            continue
        if key not in RELEVANT:
            continue
        value = field[2].strip()
        if value.startswith("str(2):"):
            value = value[7:]
        try:
            value = json.loads(value)
            if not isinstance(value, str) or "\0" in value:
                raise ValueError()
        except ValueError as exc:
            raise ProfileError("A Windows profile or shell-folder value is malformed. No registry mapping was changed.") from exc
        if (section, key) in result:
            raise ProfileError("The Windows user registry has duplicate folder mappings.")
        result[section, key] = value
    return result


def _windows_path(value, prefix, userprofile):
    value = re.sub(r"%USERPROFILE%", lambda _: userprofile, value, flags=re.I)
    if not re.match(r"^c:[\\/]", value, re.I) or "%" in value:
        raise ProfileError("A Windows user folder maps outside drive C: or uses an unknown variable. No mapping was changed.")
    parts = re.split(r"[\\/]", value[3:])
    if (not parts or any(not part or part in (".", "..") or part != part.rstrip(" .")
                         or re.search(r'[<>:"|?*\x00-\x1f]', part) for part in parts)):
        raise ProfileError("A Windows user-folder path is invalid. No mapping was changed.")
    path = prefix / "drive_c"
    for part in parts:
        _within(path, prefix)
        # Wine registry spelling can differ on a case-sensitive filesystem.
        if path.is_dir():
            matches = [p for p in path.iterdir() if p.name.casefold() == part.casefold()]
            if len(matches) > 1:
                raise ProfileError("A Windows user-folder path is ambiguous.")
            path = matches[0] if matches else path / part
        else:
            path /= part
    return path


def profile_paths(prefix, *, allow_leaf_links=False, require_existing=False):
    prefix = Path(prefix)
    values = _registry(prefix)
    userprofile = values.get((VOLATILE, "userprofile"))
    active = userprofile is not None
    if not active:
        # Older completed wrappers and synthetic fixtures use this canonical
        # profile. Never use it to override an explicitly different active user.
        userprofile = r"C:\users\Sikarugir"
    profile = _windows_path(userprofile, prefix, userprofile)
    relative = profile.relative_to(prefix / "drive_c")
    if len(relative.parts) != 2 or relative.parts[0].casefold() != "users":
        raise ProfileError("The active Windows profile is not a supported local user directory.")
    _within(profile, prefix)
    targets = {}
    for label, (default, key) in FOLDERS.items():
        mapped = [values[section, key] for section in (SHELL, USER_SHELL) if (section, key) in values]
        if active and key == "personal" and not mapped:
            raise ProfileError("The active Windows profile has no Documents mapping. Finish prefix initialization before continuing.")
        paths = [_windows_path(value, prefix, userprofile) for value in mapped] or [profile / default]
        if not active and key == "personal" and any(str(path).casefold() != str(profile / "Documents").casefold() for path in paths):
            raise ProfileError("Documents refers to another Windows user, but the active user is unknown. Finish prefix initialization before continuing.")
        if any(str(path).casefold() != str(paths[0]).casefold() for path in paths[1:]):
            raise ProfileError("The Windows Documents or shell-folder mappings disagree. No registry mapping was changed.")
        targets[label] = paths[0]
    # AppData is not redirected or repaired, but it must not hide an escape via
    # a parent symlink. Steam stores private state here as well as in its folder.
    for key in ("appdata", "local appdata"):
        for section in (SHELL, USER_SHELL):
            if (section, key) in values:
                _within(_windows_path(values[section, key], prefix, userprofile), prefix)
    for path in targets.values():
        _within(path.parent, prefix)
        if not allow_leaf_links or not path.is_symlink():
            _within(path, prefix)
        if path.exists() and not path.is_dir():
            raise ProfileError("A Windows user folder is a file. It was preserved; repair the prefix before continuing.")
    if require_existing and (not profile.is_dir() or not targets["My Documents"].is_dir()):
        raise ProfileError("The active Windows profile or Documents folder is missing. Finish setup before opening Steam.")
    return {"profile": profile, "documents": targets["My Documents"], "folders": targets, "active_mapping": active}


def documents_path(prefix):
    return profile_paths(prefix)["documents"]


def assert_contained(prefix):
    return profile_paths(prefix, require_existing=True)


def localize_user_folders(prefix):
    """Preflight all paths, then replace only leaf links inside the prefix."""
    mapping = profile_paths(prefix, allow_leaf_links=True)
    if not mapping["active_mapping"] and not mapping["profile"].is_dir():
        raise ProfileError("The active Windows user is unknown. Finish prefix initialization before creating user folders.")
    for path in mapping["folders"].values():
        _within(path.parent, Path(prefix))
        if path.is_symlink():
            path.unlink()  # The host target is neither traversed nor removed.
        path.mkdir(parents=True, exist_ok=True)
    return assert_contained(prefix)
