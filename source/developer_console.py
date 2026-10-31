"""Per-launch Steam console option and reversible Ultimate launcher XML edits.

The controller holds its operation lock and checks that the game and official
launcher are closed before an explicit change. This module does not launch
processes or touch Steam account settings, game executables, keys or saves.
"""
from __future__ import annotations

import base64
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import tempfile
from xml.parsers import expat

FLAG = "-enabledeveloperconsole"
MAX_XML = 1024 * 1024
MAX_TAG = 16384
MAX_RECEIPT = 65536
SPACE = " \t\r\n"


class DeveloperConsoleError(RuntimeError):
    pass


def _sha(raw):
    return hashlib.sha256(raw).hexdigest()


def _safe(path, root):
    path, root = Path(path), Path(root).resolve()
    if not path.is_absolute() or ".." in path.parts:
        raise DeveloperConsoleError("The developer console path is outside the selected game environment.")
    try:
        relative = path.relative_to(root)
        path.resolve().relative_to(root)
    except (ValueError, RuntimeError) as exc:
        raise DeveloperConsoleError("The developer console path is outside the selected game environment.") from exc
    current = root
    for part in relative.parts:
        current /= part
        if current.is_symlink():
            raise DeveloperConsoleError("A developer console path is a symbolic link; existing files were preserved.")
    return path


def _read(path, root, limit=MAX_XML):
    path = _safe(path, root)
    flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_NONBLOCK", 0)
    with os.fdopen(os.open(path, flags), "rb") as handle:
        info = os.fstat(handle.fileno())
        if not stat.S_ISREG(info.st_mode) or info.st_size > limit or info.st_nlink != 1:
            raise DeveloperConsoleError("The developer console file has an unexpected type, size or shared link.")
        raw = handle.read(limit + 1)
    if len(raw) > limit:
        raise DeveloperConsoleError("The developer console file is too large.")
    return raw


def _paths(c, game):
    if not isinstance(game, dict) or str(game.get("appid")) not in ("17450", "47810") or not game.get("game_dir"):
        raise DeveloperConsoleError("Install a supported Steam edition of Dragon Age: Origins first.")
    prefix = _safe(c.prefix, c.root)
    folder = _safe(Path(game["game_dir"]), prefix)
    if not folder.is_dir():
        raise DeveloperConsoleError("The selected game folder is unavailable.")
    target = _safe(folder / "data/DAOriginsLauncher.xml", prefix)
    relative = target.relative_to(prefix).as_posix()
    store = _safe(c.data / "developer-console" / _sha(relative.encode("utf-8")), c.root)
    return target, store, relative


def _tag_end(raw, start):
    quote = None
    for i in range(start, min(len(raw), start + MAX_TAG + 1)):
        char = raw[i]
        if quote:
            if char == quote:
                quote = None
        elif char in (34, 39):
            quote = char
        elif char == 62:
            return i + 1
    raise DeveloperConsoleError("The game launcher XML has an unsupported launch entry.")


def _inspect(raw):
    """Use XML parsing to select a real element, then retain its original bytes."""
    if len(raw) > MAX_XML:
        raise DeveloperConsoleError("The game launcher XML is too large.")
    try:
        raw.decode("utf-8-sig")
    except UnicodeError as exc:
        raise DeveloperConsoleError("The game launcher XML must use UTF-8; existing files were preserved.") from exc
    parser = expat.ParserCreate()
    candidates = []
    root_seen = False

    def forbidden(*args):
        raise DeveloperConsoleError("The game launcher XML contains unsupported declarations.")

    def declaration(version, encoding, standalone):
        if encoding and encoding.casefold() not in ("utf-8", "utf8"):
            forbidden()

    def element(name, attrs):
        nonlocal root_seen
        if not root_seen:
            root_seen = True
            if name != "BioWareApp" or attrs.get("product") != "DragonAgeOrigins":
                raise DeveloperConsoleError("This is not the expected Dragon Age launcher XML.")
        file = attrs.get("file", "").replace("/", "\\").casefold()
        if attrs.get("action") == "execute" and file == "${binaries_dir}\\daorigins.exe":
            if name != "true" or attrs.get("path") != "${BINARIES_DIR}" or attrs.get("autoquit") != "true":
                raise DeveloperConsoleError("The Dragon Age launch entry differs from the supported format.")
            start = parser.CurrentByteIndex
            candidates.append((start, _tag_end(raw, start), attrs))

    parser.StartElementHandler = element
    parser.XmlDeclHandler = declaration
    parser.StartDoctypeDeclHandler = forbidden
    parser.EntityDeclHandler = forbidden
    parser.ExternalEntityRefHandler = forbidden
    try:
        parser.Parse(raw, True)
    except (expat.ExpatError, ValueError) as exc:
        raise DeveloperConsoleError("The game launcher XML is malformed; existing files were preserved.") from exc
    if len(candidates) != 1:
        raise DeveloperConsoleError("The game launcher XML must contain one unambiguous Dragon Age launch entry.")
    start, end, attrs = candidates[0]
    tag = raw[start:end]
    matches = list(re.finditer(rb'''\s+([A-Za-z_:][A-Za-z0-9_:.-]*)\s*=\s*(["'])(.*?)\2''', tag, re.S))
    spans = {m[1].decode("ascii"): m for m in matches}
    if set(spans) != set(attrs):
        raise DeveloperConsoleError("The game launcher XML has unsupported attributes.")
    argument = spans.get("arguments")
    enabled = bool(argument and _flag_ranges(argument[3]))
    return dict(start=start, end=end, tag=tag, argument=argument, enabled=enabled)


def _decoded(raw):
    """Map XML-decoded characters back to their untouched UTF-8 byte spans."""
    chars, spans, i = [], [], 0
    entities = {b"amp": "&", b"lt": "<", b"gt": ">", b"quot": '"', b"apos": "'"}
    while i < len(raw):
        start = i
        if raw[i] == 38:
            end = raw.find(b";", i) + 1
            value = raw[i + 1:end - 1]
            if not end:
                raise DeveloperConsoleError("The game launch arguments contain an invalid entity.")
            try:
                char = (chr(int(value[2:], 16)) if value.startswith(b"#x") else
                        chr(int(value[1:], 10)) if value.startswith(b"#") else entities[value])
            except (KeyError, ValueError, OverflowError) as exc:
                raise DeveloperConsoleError("The game launch arguments contain an invalid entity.") from exc
            i = end
        else:
            first = raw[i]
            size = 1 if first < 128 else 2 if first < 224 else 3 if first < 240 else 4
            i += size
            char = raw[start:i].decode("utf-8")
        chars.append(char)
        spans.append((start, i))
    return "".join(chars), spans


def _tokens(text):
    """Windows-style argument boundaries; retain each token's source span."""
    i = 0
    while i < len(text):
        while i < len(text) and text[i] in SPACE:
            i += 1
        start, quoted, value = i, False, []
        while i < len(text) and (quoted or text[i] not in SPACE):
            if text[i] == "\\":
                slash = i
                while i < len(text) and text[i] == "\\":
                    i += 1
                count = i - slash
                if i < len(text) and text[i] == '"':
                    value.extend("\\" * (count // 2))
                    if count % 2:
                        value.append('"')
                        i += 1
                    else:
                        quoted = not quoted
                        i += 1
                else:
                    value.extend("\\" * count)
            elif text[i] == '"':
                if quoted and i + 1 < len(text) and text[i + 1] == '"':
                    value.append('"')
                    i += 2
                else:
                    quoted = not quoted
                    i += 1
            else:
                value.append(text[i])
                i += 1
        if quoted:
            raise DeveloperConsoleError("The game launch arguments contain an unfinished quote.")
        if i > start:
            yield "".join(value), start, i


def _flag_ranges(raw):
    text, positions = _decoded(raw)
    ranges = []
    for value, start, end in _tokens(text):
        if value.casefold() != FLAG:
            continue
        # Remove the separator following this option, or its preceding separator
        # at the end. Other tokens and their XML escaping remain byte-for-byte.
        if end < len(text) and text[end] in SPACE:
            while end < len(text) and text[end] in SPACE:
                end += 1
        else:
            while start > 0 and text[start - 1] in SPACE:
                start -= 1
        ranges.append((positions[start][0], positions[end - 1][1]))
    return ranges


def _without_flags(raw):
    ranges = _flag_ranges(raw)
    merged = []
    for start, end in sorted(ranges):
        if merged and start <= merged[-1][1]:
            merged[-1] = (merged[-1][0], max(end, merged[-1][1]))
        else:
            merged.append((start, end))
    for start, end in reversed(merged):
        raw = raw[:start] + raw[end:]
    return raw


def _receipt(c, store, relative):
    path = _safe(store / "receipt.json", c.root)
    if not path.exists():
        return None
    try:
        value = json.loads(_read(path, c.root, MAX_RECEIPT))
        if (not isinstance(value, dict) or value.get("schema") != 1 or value.get("target") != relative
                or type(value.get("enabled")) is not bool or type(value.get("created_arguments")) is not bool
                or not re.fullmatch(r"[0-9a-f]{64}", value.get("before_sha256", ""))):
            raise ValueError()
        before = base64.b64decode(value["before_tag"], validate=True)
        after = base64.b64decode(value["after_tag"], validate=True)
        if not before or not after or max(len(before), len(after)) > MAX_TAG:
            raise ValueError()
        backup = _read(store / "backups" / (value["before_sha256"] + ".xml"), c.root)
        if _sha(backup) != value["before_sha256"] or _inspect(backup)["tag"] != before:
            raise ValueError()
        value.update(before_tag_bytes=before, after_tag_bytes=after)
        return value
    except (KeyError, TypeError, ValueError, UnicodeError, FileNotFoundError) as exc:
        raise DeveloperConsoleError("The developer console backup record is damaged; existing files were preserved.") from exc


def _rewrite(raw, info, enabled, receipt):
    tag, argument = info["tag"], info["argument"]
    if info["enabled"] == enabled:
        return raw
    if enabled:
        if argument:
            value = argument[3]
            decoded, _ = _decoded(value)
            separator = b" " if decoded and decoded[-1] not in SPACE else b""
            value += separator + FLAG.encode("ascii")
            replacement = tag[:argument.start(3)] + value + tag[argument.end(3):]
        else:
            close = re.search(rb"\s*/?>$", tag)
            if close is None:
                raise DeveloperConsoleError("The game launcher XML has an unsupported launch entry.")
            replacement = tag[:close.start()] + b' arguments="' + FLAG.encode("ascii") + b'"' + tag[close.start():]
    elif receipt and receipt["enabled"] and tag == receipt["after_tag_bytes"]:
        replacement = receipt["before_tag_bytes"]
    else:
        value = _without_flags(argument[3])
        if receipt and receipt["enabled"] and receipt["created_arguments"] and not _decoded(value)[0].strip(SPACE):
            replacement = tag[:argument.start()] + tag[argument.end():]
        else:
            replacement = tag[:argument.start(3)] + value + tag[argument.end(3):]
    changed = raw[:info["start"]] + replacement + raw[info["end"]:]
    if _inspect(changed)["enabled"] != enabled:
        raise DeveloperConsoleError("The console change could not be verified; existing files were preserved.")
    return changed


def _atomic_write(path, root, raw, mode, expected):
    path = _safe(path, root)
    if expected is None:
        if path.exists():
            raise DeveloperConsoleError("A developer console file appeared during preparation; please retry.")
    elif _read(path, root) != expected:
        raise DeveloperConsoleError("The game launcher file changed during preparation; please retry.")
    descriptor, temporary = tempfile.mkstemp(prefix=".console-", dir=path.parent)
    temporary = Path(temporary)
    try:
        with os.fdopen(descriptor, "wb") as handle:
            os.fchmod(handle.fileno(), mode)
            handle.write(raw)
            handle.flush()
            os.fsync(handle.fileno())
        _safe(path, root)
        if expected is None:
            if path.exists():
                raise DeveloperConsoleError("A developer console file appeared during preparation; please retry.")
        elif _read(path, root) != expected:
            raise DeveloperConsoleError("The game launcher file changed during preparation; please retry.")
        os.replace(temporary, path)
    finally:
        if temporary.exists():
            temporary.unlink()


def status(c, game):
    """Read-only observation; never adopt or modify the user's preference."""
    try:
        target, store, relative = _paths(c, game)
        if str(game["appid"]) == "17450":
            return dict(console_supported=True, console_enabled=False, console_managed=False,
                        console_message="Available as a per-launch option. Any options set separately in Steam still apply.")
        info = _inspect(_read(target, c.root))
        receipt = _receipt(c, store, relative)
        return dict(console_supported=True, console_enabled=info["enabled"], console_managed=receipt is not None,
                    console_message="The developer console is enabled in the game's launcher." if info["enabled"]
                    else "The developer console can be enabled for the next launch.")
    except (DeveloperConsoleError, OSError, ValueError, RuntimeError) as exc:
        return dict(console_supported=False, console_enabled=False, console_managed=False,
                    console_message=str(exc) if isinstance(exc, DeveloperConsoleError)
                    else "The game's console settings are unavailable. Existing files were preserved.")


def prepare(c, game, enabled=None):
    """Apply an explicit next-launch choice and return extra Steam arguments.

    None preserves existing settings. Backups are content-addressed evidence;
    disabling never replaces a whole XML file with an older backup.
    """
    if enabled is None:
        return []
    if type(enabled) is not bool:
        raise DeveloperConsoleError("The developer console setting must be explicitly on or off.")
    target, store, relative = _paths(c, game)
    if str(game["appid"]) == "17450":
        return [FLAG] if enabled else []
    raw = _read(target, c.root)
    info = _inspect(raw)
    receipt = _receipt(c, store, relative)
    changed = _rewrite(raw, info, enabled, receipt)
    if changed == raw:
        return []
    backup = _safe(store / "backups" / (_sha(raw) + ".xml"), c.root)
    backup.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    _safe(backup.parent, c.root)
    if backup.exists():
        if _read(backup, c.root) != raw:
            raise DeveloperConsoleError("The developer console backup changed; existing files were preserved.")
    else:
        _atomic_write(backup, c.root, raw, 0o600, None)
    record = dict(schema=1, target=relative, before_sha256=_sha(raw), enabled=enabled,
                  created_arguments=info["argument"] is None,
                  before_tag=base64.b64encode(info["tag"]).decode("ascii"),
                  after_tag=base64.b64encode(_inspect(changed)["tag"]).decode("ascii"))
    path = _safe(store / "receipt.json", c.root)
    old_record = _read(path, c.root, MAX_RECEIPT) if path.exists() else None
    # Keep the enabling receipt until another enable replaces it. It contains
    # the original tag, including whether we introduced the arguments attribute.
    # Replacing it before a disable reaches the XML would lose that provenance
    # on an interrupted write; retries could then leave an empty attribute or
    # discard the original whitespace. Observed XML, not this receipt's last
    # requested state, determines whether the console is currently enabled.
    if enabled or receipt is None or not receipt["enabled"]:
        _atomic_write(path, c.root, (json.dumps(record, indent=2) + "\n").encode("utf-8"), 0o600, old_record)
    mode = stat.S_IMODE(target.lstat().st_mode)
    _atomic_write(target, c.root, changed, mode, raw)
    if _read(target, c.root) != changed:
        raise DeveloperConsoleError("The console change could not be verified. Its original XML backup was retained.")
    return []
