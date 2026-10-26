"""Bounded first-start updater handoff recovery; never terminates a process.

Only an explicit setup/Open Steam request arms a generation. The CLI caller
serializes arm/maintain/cancel with Controller.operation(); status is read-only.
Only Valve's bounded bootstrap_log tail is read, never account/client logs.
"""
from __future__ import annotations

import hashlib
import math
import os
from pathlib import Path
import time
import uuid

from steam_state import find_steam

KEY = "steam_maintenance"
LIFETIME = 20 * 60
MAX_REOPENS = 3
TAIL_LIMIT = 16 * 1024
QUIET_SECONDS = 10
CORE_IMAGES = {"services.exe", "winedevice.exe", "plugplay.exe", "rpcss.exe", "explorer.exe", "conhost.exe"}


def _read_log(c, steam):
    if not steam:
        return None
    try:
        path = (steam.parent / "logs/bootstrap_log.txt").resolve()
        path.relative_to(c.prefix.resolve())
        with path.open("rb") as handle:
            stat = os.fstat(handle.fileno())
            start = max(0, stat.st_size - TAIL_LIMIT)
            handle.seek(start)
            raw = handle.read(min(TAIL_LIMIT, stat.st_size - start))
        if start:
            first = raw.find(b"\n")
            if first < 0:
                return None
            start += first + 1
            raw = raw[first + 1:]
        return {"identity": [stat.st_dev, stat.st_ino], "size": stat.st_size,
                "start": start, "raw": raw}
    except (OSError, ValueError, RuntimeError):
        return None


def _valid(record, now):
    if not isinstance(record, dict) or record.get("schema_version") != 1 or record.get("armed") is not True:
        return False
    try:
        return (isinstance(record["generation"], str) and len(record["generation"]) == 32
                and type(record["attempts"]) is int and 0 <= record["attempts"] <= MAX_REOPENS
                and type(record["cursor"]) is int and record["cursor"] >= 0
                and isinstance(record["activated_at"], (int, float))
                and isinstance(record["expires_at"], (int, float))
                and record["activated_at"] <= now < record["expires_at"] <= record["activated_at"] + LIFETIME
                and isinstance(record.get("not_before"), (int, float))
                and math.isfinite(record["not_before"])
                and (record.get("identity") is None or (isinstance(record["identity"], list)
                     and len(record["identity"]) == 2 and all(type(n) is int and n >= 0 for n in record["identity"]))))
    except (KeyError, TypeError, ValueError):
        return False


def _handoff(log, record):
    """Require complete+Shutdown after this generation's last consumed byte.

    A later Startup/verification invalidates the old handoff, including when a
    normally started client was deliberately closed before the next UI poll.
    """
    if not log or log["size"] < record["cursor"]:
        return None
    start = max(log["start"], record["cursor"])
    raw = log["raw"][start - log["start"]:]
    complete = None
    shutdown = None
    offset = start
    for line in raw.splitlines(keepends=True):
        offset += len(line)
        if not line.endswith(b"\n"):
            continue
        body = line.decode("utf-8", errors="replace").casefold()
        if "update complete, launching steam" in body:
            complete, shutdown = offset, None
        elif "] shutdown" in body and complete is not None:
            shutdown = offset
        elif any(marker in body for marker in ("startup - updater", "startup - steam client", "verifying installation", "verification complete", "downloading update (", "installing update", "background update loop")):
            complete, shutdown = None, None
    if complete is None or shutdown is None:
        return None
    return hashlib.sha256(repr((log["identity"], complete, shutdown)).encode()).hexdigest()


class SteamMaintenance:
    def __init__(self, controller):
        self.c = controller
        session = os.environ.get("DAO_LAUNCHER_SESSION")
        try:
            self.owner = uuid.UUID(session).hex if session else "cli"
        except (ValueError, AttributeError) as exc:
            raise ValueError("The launcher session identifier is invalid. Reopen the launcher.") from exc

    def _owned(self, record):
        return isinstance(record, dict) and record.get("owner") == self.owner

    def _save(self, record):
        self.c.save_state(**{KEY: record})

    def arm(self):
        now = time.time()
        steam = find_steam(self.c.prefix)
        log = _read_log(self.c, steam)
        usable = True
        if steam and log is None:
            # A genuinely absent log may be created by the upcoming first
            # start. An unreadable/escaping existing log cannot establish a
            # generation boundary and must not authorize later old evidence.
            try:
                path = steam.parent / "logs/bootstrap_log.txt"
                path.resolve().relative_to(self.c.prefix.resolve())
                usable = not path.exists() and not path.is_symlink()
            except (OSError, ValueError, RuntimeError):
                usable = False
        self._save({"schema_version": 1, "armed": usable, "owner": self.owner, "generation": uuid.uuid4().hex,
                    "activated_at": now, "expires_at": now + LIFETIME, "attempts": 0,
                    "identity": log["identity"] if log else None,
                    "cursor": log["size"] if log else 0, "not_before": now + QUIET_SECONDS,
                    "message": ("Following Steam's first-start updates while the launcher is open." if usable else
                                "Steam's updater log is unavailable. Automatic follow-up is off; use Open Steam as needed.")})

    def cancel(self, reason="Startup follow-up stopped.", force=False):
        record = self.c.state().get(KEY)
        if isinstance(record, dict) and record.get("armed") is True and (force or self._owned(record)):
            record = dict(record, armed=False, message=reason)
            self._save(record)

    def cancel_request(self):
        self.cancel("Startup follow-up stopped when this launcher window closed.")
        return self._result("disarmed", "Stopped this launcher window's automatic Steam follow-up. Steam and the game were left running.")

    def summary(self):
        """No writes or process actions; the GUI invokes maintain separately."""
        record = self.c.state().get(KEY)
        if not self._owned(record):
            return {"steam_maintenance_active": False, "steam_maintenance_message": None,
                    "steam_maintenance_blocked_reason": None}
        active = _valid(record, time.time())
        message = record.get("message") if isinstance(record, dict) else None
        blocked = None
        if isinstance(record, dict) and record.get("armed") is True and not active:
            message = "Steam startup follow-up expired or its state is invalid. Use Open Steam to start again."
        if active:
            try:
                self._inventory()
            except (OSError, ValueError, RuntimeError):
                active = False
                blocked = "Process visibility is unavailable, so automatic Steam follow-up is paused. Refresh to retry or use Open Steam. No processes were changed."
                message = blocked
        return {"steam_maintenance_active": active,
                "steam_maintenance_message": message if isinstance(message, str) else None,
                "steam_maintenance_blocked_reason": blocked}

    def pending_handoff(self, steam):
        record = self.c.state().get(KEY)
        if not self._owned(record) or not _valid(record, time.time()):
            return False
        log = _read_log(self.c, steam)
        return bool(log and (record["identity"] is None or log["identity"] == record["identity"])
                    and _handoff(log, record))

    def _result(self, action, message, record=None, **updates):
        if record is not None:
            changed = dict(record, message=message, **updates)
            if changed != record:
                self._save(changed)
        return dict(ok=True, action=action, message=message, **self.summary())

    def _inventory(self):
        # Reuse strict Mach-executable attribution. Unlike status.processes(),
        # this fails closed when ps/proc_pidpath visibility is uncertain.
        from display_settings import DisplaySettings
        return DisplaySettings(self.c)._processes()

    @staticmethod
    def _classify(rows):
        from display_settings import _image
        names = {_image(command) for _, _, command in rows}
        if "steamwebhelper.exe" in names:
            return "ready"
        if any(name.startswith("daorigins") for name in names):
            return "game"
        if "steam.exe" in names:
            return "steam"
        if "steamsetup.exe" in names:
            return "installer"
        # Core Wine services can outlive the exited updater. Every other own
        # Windows image, native wrapper or installer blocks an automatic open.
        if any(not name or name not in CORE_IMAGES for name in names):
            return "busy"
        return "idle"

    def maintain(self):
        record = self.c.state().get(KEY)
        now = time.time()
        if not self._owned(record):
            return self._result("disarmed", "No startup follow-up is active for this launcher window.")
        if not _valid(record, now):
            self.cancel("Steam startup follow-up has expired or was stopped. Use Open Steam to start again.")
            return self._result("disarmed", "No active Steam startup follow-up.")
        self.c.require_platform()
        self.c.require_contained_profile()
        try:
            phase = self._classify(self._inventory())
        except (OSError, ValueError, RuntimeError):
            return self._result("blocked", "Process visibility is unavailable. Steam will not be reopened automatically; refresh or use Open Steam.", record,
                                observed_handoff=None, absent_since=None)
        if phase in ("ready", "game"):
            return self._result("disarmed", "Steam's web interface has started; automatic startup follow-up finished." if phase == "ready" else "The game or its configuration is open; startup follow-up stopped.", record, armed=False)
        steam = find_steam(self.c.prefix)
        log = _read_log(self.c, steam)
        if log and record["identity"] is not None and (log["identity"] != record["identity"] or log["size"] < record["cursor"]):
            return self._result("disarmed", "Steam's updater log changed unexpectedly. Use Open Steam if its window has not appeared.", record, armed=False)
        if log and record["identity"] is None:
            record = dict(record, identity=log["identity"])
            self._save(record)
        evidence = _handoff(log, record)
        if phase != "idle":
            message = ("Steam's update finished but its updater is still running. Wait for its window; if it remains stuck, close Steam yourself and use Open Steam. Nothing was stopped."
                       if phase == "steam" and evidence else
                       "Waiting for Steam's updater or installer to finish. No running processes will be restarted.")
            return self._result("waiting", message, record, observed_handoff=None, absent_since=None)
        if not evidence:
            return self._result("waiting", "Waiting for a completed Steam update. No restart is attempted without fresh updater evidence.", record,
                                observed_handoff=None, absent_since=None)
        if record["attempts"] >= MAX_REOPENS:
            return self._result("disarmed", "Steam needed several startup attempts. Use Open Steam to continue; automatic follow-up is paused.", record, armed=False)
        if record.get("observed_handoff") != evidence or not isinstance(record.get("absent_since"), (int, float)):
            return self._result("waiting", "Steam's update finished. Waiting briefly for its own handoff before reopening it.", record,
                                observed_handoff=evidence, absent_since=now)
        if now < max(record["not_before"], record["absent_since"] + QUIET_SECONDS):
            return self._result("waiting", "Waiting briefly for Steam's update handoff.", record)
        # Recheck both process absence and the exact update event immediately
        # before launching. The operation lock also prevents overlapping polls.
        try:
            if self._classify(self._inventory()) != "idle":
                return self._result("waiting", "Steam activity resumed; no additional instance was started.", record,
                                    observed_handoff=None, absent_since=None)
        except (OSError, ValueError, RuntimeError):
            return self._result("blocked", "Process visibility changed. No Steam instance was started.", record,
                                observed_handoff=None, absent_since=None)
        latest = _read_log(self.c, steam)
        if not latest or latest["identity"] != log["identity"] or _handoff(latest, record) != evidence:
            return self._result("waiting", "Steam's updater moved on; no additional instance was started.", record,
                                observed_handoff=None, absent_since=None)
        attempts = record["attempts"] + 1
        # Consume evidence before launching: even a controller crash cannot
        # cause the next poll to reuse this same handoff and duplicate Steam.
        record = dict(record, attempts=attempts, cursor=latest["size"], not_before=now + 20 * 2 ** (attempts - 1),
                      observed_handoff=None, absent_since=None, message="Continuing Steam's completed update.")
        self._save(record)
        try:
            self.c.steam_command([], "steam-handoff")
        except (OSError, ValueError, RuntimeError) as exc:
            return self._result("disarmed", f"Steam's update could not be reopened automatically. Use Open Steam. {exc}", record, armed=False)
        return self._result("reopened", "Steam's completed update exited; reopened this launcher's Steam to continue startup.", record)
