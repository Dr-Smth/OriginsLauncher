"""4 GB controller orchestration; no Wine, Steam or native patch is executed."""

import contextlib
import hashlib
import io
import json
from pathlib import Path
import sys
import types
import unittest
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import daoctl
import test_controller as fixtures


class BackendError(RuntimeError):
    pass


class LargeAddressControllerTests(unittest.TestCase):
    # Reuse only the fixture helpers, without inheriting/rerunning its test suite.
    steam = fixtures.ControllerTests.steam
    game = fixtures.ControllerTests.game
    validation = fixtures.ControllerTests.validation

    def setUp(self):
        fixtures.ControllerTests.setUp(self)
        self.backend = types.ModuleType("large_address")
        self.backend.LargeAddressError = BackendError
        self.backend.status = mock.Mock(return_value=self.memory_status())
        self.backend.active_wine_processes = mock.Mock(return_value=[])
        self.backend.set_enabled = mock.Mock()
        self.patch(mock.patch.dict(sys.modules, {"large_address": self.backend}))
        self.processes = self.patch(mock.patch.object(self.c, "processes", return_value=[]))
        self.shutdown = self.patch(mock.patch.object(self.c, "steam_command", return_value={"ok": True}))
        self.stop = self.patch(mock.patch.object(self.c, "stop", return_value={"ok": True}))
        self.startup = self.patch(mock.patch.object(self.c, "steam_startup", return_value="client_running"))
        self.sleep = self.patch(mock.patch.object(daoctl.time, "sleep"))
        self.patch(mock.patch("steam_maintenance.SteamMaintenance.cancel", return_value=None))
        # Test failures must not accidentally spawn a process through another path.
        self.patch(mock.patch.object(daoctl.subprocess, "Popen", side_effect=AssertionError("Unexpected process launch")))
        self.patch(mock.patch.object(daoctl.subprocess, "run", side_effect=AssertionError("Unexpected process execution")))
        self.native = self.c.contents / "SharedSupport/wine/lib/wine/x86_64-unix/ntdll.so"
        self.native.parent.mkdir(parents=True, exist_ok=True)
        self.native.write_bytes(b"fixture original native module; never execute")

    def patch(self, patcher):
        result = patcher.start()
        self.addCleanup(patcher.stop)
        return result

    @staticmethod
    def memory_status(*, supported=True, enabled=False, managed=False):
        return {"laa_supported": supported, "laa_enabled": enabled,
                "laa_managed": managed, "laa_message": "Fixture runtime is unsupported or altered"}

    @staticmethod
    def row(command, pid=101):
        return (pid, 1, command)

    def assert_no_session_change(self):
        self.shutdown.assert_not_called()
        self.stop.assert_not_called()
        self.backend.set_enabled.assert_not_called()

    def test_unchanged_mode_does_not_restart_or_enumerate_a_session(self):
        for enabled in (False, True):
            with self.subTest(enabled=enabled):
                self.backend.status.return_value = self.memory_status(enabled=enabled, managed=enabled)
                self.c.prepare_large_address(enabled)
                self.backend.active_wine_processes.assert_not_called()
                self.assert_no_session_change()

    def test_unknown_unmanaged_runtime_allows_ordinary_off_mode(self):
        self.backend.status.return_value = self.memory_status(supported=False)
        before = self.native.read_bytes()
        self.c.prepare_large_address(False)
        self.backend.active_wine_processes.assert_not_called()
        self.assert_no_session_change()
        self.assertEqual(self.native.read_bytes(), before)

    def test_unsupported_enable_and_managed_tampering_are_blocked(self):
        cases = [(False, True), (True, False), (True, True)]
        for managed, desired in cases:
            with self.subTest(managed=managed, desired=desired):
                self.backend.status.return_value = self.memory_status(supported=False, managed=managed)
                with self.assertRaisesRegex(daoctl.DAOError, "unsupported or altered"):
                    self.c.prepare_large_address(desired)
                self.backend.active_wine_processes.assert_not_called()
                self.assert_no_session_change()

    def test_active_game_launcher_installer_or_unknown_program_never_stops_session(self):
        commands = [r"C:\Game\DAOrigins.exe", r"C:\Game\DAOriginsLauncher.exe",
                    r"C:\Game\DAOriginsConfig.exe", r"C:\Installers\DXSETUP.exe",
                    r"C:\Tools\UnknownProgram.exe", r"C:\Game\DAOrigins.exe.bak"]
        for command in commands:
            with self.subTest(command=command):
                self.backend.active_wine_processes.return_value = [
                    self.row("steam.exe"), self.row(command, 102)]
                with self.assertRaisesRegex(daoctl.DAOError, "Close the game"):
                    self.c.prepare_large_address(True)
                self.assert_no_session_change()
                self.startup.assert_not_called()

    def test_steam_starting_updating_or_handing_off_is_not_interrupted(self):
        self.steam()
        self.backend.active_wine_processes.return_value = [self.row("steam.exe")]
        for startup in ("starting", "downloading", "installing", "handoff", "restart_required"):
            with self.subTest(startup=startup):
                self.startup.return_value = startup
                with self.assertRaisesRegex(daoctl.DAOError, "finish starting or updating"):
                    self.c.prepare_large_address(True)
                self.assert_no_session_change()

    def test_unknown_command_wrappers_and_native_sibling_paths_are_not_stopped(self):
        wine_root = self.c.contents / "SharedSupport/wine"
        support = self.c.prefix / "drive_c/dao-support"
        commands = [
            r"cmd.exe /c C:\Tools\UnknownProgram.exe",
            r"C:\windows\system32\cmd.exe /s/c C:\dao-support\unmanaged-123.bat",
            r"C:\windows\system32\cmd.exe /s/c C:\dao-support\play-123.bat & other.exe",
            str(wine_root) + "-other/bin/wineserver",
            str(wine_root / "bin/wineserver") + " /tmp/unmanaged-program",
            str(wine_root / "lib/wine/x86_64-unix/wine") + " start /unix "
            + str(support / "other-123.bat"),
            str(wine_root / "lib/wine/x86_64-unix/wine") + " start /unix "
            + str(support) + "-other/play-123.bat",
        ]
        for command in commands:
            with self.subTest(command=command):
                self.backend.active_wine_processes.return_value = [self.row(command)]
                with self.assertRaisesRegex(daoctl.DAOError, "Close the game"):
                    self.c.prepare_large_address(True)
                self.assert_no_session_change()

    def test_only_scoped_native_services_and_launcher_batches_can_be_stopped(self):
        wine_root = self.c.contents / "SharedSupport/wine"
        support = self.c.prefix / "drive_c/dao-support"
        commands = [
            str(wine_root / "bin/wineserver") + " -p0",
            str(wine_root / "lib/wine/x86_64-unix/wine") + " start /unix "
            + str(support / "steam-123.bat"),
            r'"C:\windows\system32\cmd.exe" /s/c "C:\dao-support\memory-mode-steam-shutdown-123.bat"',
        ]
        for command in commands:
            with self.subTest(command=command):
                self.stop.reset_mock()
                self.backend.set_enabled.reset_mock()
                self.backend.active_wine_processes.side_effect = [[self.row(command)],
                                                                 [self.row(command)], []]
                self.c.prepare_large_address(True)
                self.stop.assert_called_once_with()
                self.backend.set_enabled.assert_called_once_with(self.c, True)
                self.shutdown.assert_not_called()

    def test_graceful_steam_exit_precedes_wineserver_stop_and_apply(self):
        self.steam()
        steam = self.row(r'"C:\Program Files (x86)\Steam\steam.exe"')
        service = self.row("services.exe", 102)
        self.backend.active_wine_processes.side_effect = [
            [steam, service], [steam, service], [service], [service], []]
        events = []
        self.shutdown.side_effect = lambda *args: events.append("steam-shutdown") or {"ok": True}
        self.stop.side_effect = lambda: events.append("wineserver-stop") or {"ok": True}
        self.backend.set_enabled.side_effect = lambda *args: events.append("apply")
        self.c.prepare_large_address(True)
        self.shutdown.assert_called_once_with(["-shutdown"], "memory-mode-steam-shutdown")
        self.stop.assert_called_once_with()
        self.backend.set_enabled.assert_called_once_with(self.c, True)
        self.assertEqual(events, ["steam-shutdown", "wineserver-stop", "apply"])
        self.assertEqual(self.backend.active_wine_processes.call_count, 5)

    def test_empty_session_applies_without_steam_or_wineserver_shutdown(self):
        self.c.prepare_large_address(True)
        self.shutdown.assert_not_called()
        self.stop.assert_not_called()
        self.backend.set_enabled.assert_called_once_with(self.c, True)

    def test_disabling_also_waits_for_a_clean_session(self):
        self.backend.status.return_value = self.memory_status(enabled=True, managed=True)
        self.backend.active_wine_processes.side_effect = [[self.row("services.exe")],
                                                         [self.row("services.exe")], []]
        events = []
        self.stop.side_effect = lambda: events.append("stop") or {"ok": True}
        self.backend.set_enabled.side_effect = lambda *args: events.append("restore")
        self.c.prepare_large_address(False)
        self.backend.set_enabled.assert_called_once_with(self.c, False)
        self.shutdown.assert_not_called()
        self.assertEqual(events, ["stop", "restore"])

    def test_steam_shutdown_timeout_never_kills_steam_or_changes_module(self):
        self.steam()
        self.backend.active_wine_processes.return_value = [self.row("steam.exe")]
        before = self.native.read_bytes()
        with mock.patch.object(daoctl.time, "monotonic", side_effect=[0, 31]):
            with self.assertRaisesRegex(daoctl.DAOError, "Steam is still open"):
                self.c.prepare_large_address(True)
        self.shutdown.assert_called_once_with(["-shutdown"], "memory-mode-steam-shutdown")
        self.stop.assert_not_called()
        self.backend.set_enabled.assert_not_called()
        self.assertEqual(self.native.read_bytes(), before)

    def test_service_shutdown_timeout_does_not_change_module(self):
        self.backend.active_wine_processes.return_value = [self.row("services.exe")]
        before = self.native.read_bytes()
        with mock.patch.object(daoctl.time, "monotonic", side_effect=[0, 16]):
            with self.assertRaisesRegex(daoctl.DAOError, "still closing"):
                self.c.prepare_large_address(True)
        self.stop.assert_called_once_with()
        self.shutdown.assert_not_called()
        self.backend.set_enabled.assert_not_called()
        self.assertEqual(self.native.read_bytes(), before)

    def test_program_appearing_during_steam_exit_prevents_stop_and_apply(self):
        self.steam()
        self.backend.active_wine_processes.side_effect = [[self.row("steam.exe")],
                                                         [self.row("DAOriginsLauncher.exe")]]
        with self.assertRaisesRegex(daoctl.DAOError, "Close the game"):
            self.c.prepare_large_address(True)
        self.shutdown.assert_called_once_with(["-shutdown"], "memory-mode-steam-shutdown")
        self.stop.assert_not_called()
        self.backend.set_enabled.assert_not_called()

    def test_process_enumeration_error_fails_closed(self):
        self.backend.active_wine_processes.side_effect = BackendError("Process visibility is unavailable")
        with self.assertRaisesRegex(daoctl.DAOError, "Process visibility is unavailable"):
            self.c.prepare_large_address(True)
        self.assert_no_session_change()

    def test_process_enumeration_failure_during_shutdown_is_not_treated_as_exit(self):
        self.steam()
        self.backend.active_wine_processes.side_effect = [
            [self.row("steam.exe")], BackendError("Cannot inspect Steam exit")]
        with self.assertRaisesRegex(daoctl.DAOError, "Cannot inspect Steam exit"):
            self.c.prepare_large_address(True)
        self.stop.assert_not_called()
        self.backend.set_enabled.assert_not_called()

    def test_backend_transaction_error_is_a_controller_error(self):
        self.backend.set_enabled.side_effect = BackendError("Native signature verification failed")
        with self.assertRaisesRegex(daoctl.DAOError, "Native signature verification failed"):
            self.c.prepare_large_address(True)

    def test_play_cli_applies_selected_mode_under_lock_before_game_launch(self):
        self.game()
        for option, desired in (("on", True), ("off", False)):
            with self.subTest(option=option):
                events = []

                @contextlib.contextmanager
                def operation():
                    events.append("lock")
                    try:
                        yield
                    finally:
                        events.append("unlock")

                def prepare(value):
                    self.assertIs(value, desired)
                    self.assertEqual(events, ["lock"])
                    events.append("prepare")

                def launch(arguments, purpose):
                    self.assertEqual(arguments, ["-applaunch", "47810"])
                    self.assertEqual(purpose, "play")
                    self.assertEqual(events, ["lock", "prepare"])
                    events.append("launch")
                    return {"ok": True}

                self.shutdown.side_effect = launch
                with mock.patch.object(daoctl, "project_root", return_value=self.root), \
                        mock.patch.object(daoctl, "Controller", return_value=self.c), \
                        mock.patch.object(self.c, "operation", side_effect=operation), \
                        mock.patch.object(self.c, "prepare_large_address", side_effect=prepare) as memory, \
                        contextlib.redirect_stdout(io.StringIO()) as output:
                    code = daoctl.main(["play", "--appid", "47810", "--large-address-aware", option])
                self.assertEqual(code, 0, output.getvalue())
                self.assertTrue(json.loads(output.getvalue())["ok"])
                memory.assert_called_once_with(desired)
                self.assertEqual(events, ["lock", "prepare", "launch", "unlock"])

    def test_play_without_memory_selection_preserves_existing_mode(self):
        self.game()
        with mock.patch.object(self.c, "prepare_large_address") as prepare:
            self.c.play("47810")
        prepare.assert_not_called()
        self.shutdown.assert_called_once_with(["-applaunch", "47810"], "play")

    def test_busy_operation_lock_prevents_memory_preparation_and_launch(self):
        self.game()
        with mock.patch.object(daoctl, "project_root", return_value=self.root), \
                mock.patch.object(daoctl, "Controller", return_value=self.c), \
                mock.patch.object(self.c, "prepare_large_address") as memory, \
                self.c.operation(), contextlib.redirect_stdout(io.StringIO()) as output:
            code = daoctl.main(["play", "--appid", "47810", "--large-address-aware", "on"])
        self.assertEqual(code, 1)
        self.assertIn("Another launcher operation", json.loads(output.getvalue())["message"])
        memory.assert_not_called()
        self.assert_no_session_change()

    def test_failed_memory_preparation_prevents_display_change_and_game_launch(self):
        self.game()
        display = types.ModuleType("display_settings")
        display.DisplaySettings = mock.Mock()
        with mock.patch.dict(sys.modules, {"display_settings": display}), \
                mock.patch.object(self.c, "prepare_large_address", side_effect=daoctl.DAOError("Unsupported runtime")), \
                mock.patch.object(self.c, "save_state") as save:
            with self.assertRaisesRegex(daoctl.DAOError, "Unsupported runtime"):
                self.c.play("47810", preset="fullscreen-retina", large_address_aware=True)
        display.DisplaySettings.assert_not_called()
        self.shutdown.assert_not_called()
        save.assert_not_called()

    def test_running_game_does_not_apply_a_new_memory_preference(self):
        self.game()
        self.processes.return_value = [self.row("DAOrigins.exe")]
        with mock.patch.object(self.c, "prepare_large_address") as prepare:
            result = self.c.play("47810", large_address_aware=True)
        self.assertIn("already running", result["message"])
        prepare.assert_not_called()
        self.shutdown.assert_not_called()

    def test_old_validation_does_not_verify_enabled_mode(self):
        self.validation()
        game = daoctl.discover_games(self.c.prefix)[0]
        self.assertTrue(self.c.compatibility_verified(game))
        self.backend.status.return_value = self.memory_status(enabled=True, managed=True)
        self.assertFalse(self.c.compatibility_verified(game))

    def test_matching_runtime_identity_verifies_only_exact_mode_and_native_bytes(self):
        report, record, _, _ = self.validation()
        game = daoctl.discover_games(self.c.prefix)[0]
        self.backend.status.return_value = self.memory_status(enabled=True, managed=True)
        identity = {"large_address_aware": True,
                    "ntdll_sha256": hashlib.sha256(self.native.read_bytes()).hexdigest()}
        record["runtime_identity"] = identity
        report.write_text(json.dumps(record))
        self.assertTrue(self.c.compatibility_verified(game))
        for invalid in (None, {}, {**identity, "large_address_aware": False},
                        {**identity, "large_address_aware": 1},
                        {**identity, "ntdll_sha256": "0" * 64}):
            with self.subTest(identity=invalid):
                record["runtime_identity"] = invalid
                report.write_text(json.dumps(record))
                self.assertFalse(self.c.compatibility_verified(game))
        record["runtime_identity"] = identity
        report.write_text(json.dumps(record))
        self.native.write_bytes(b"fixture different native module")
        self.assertFalse(self.c.compatibility_verified(game))

    def test_enabled_mode_validation_is_not_reused_after_disable_or_managed_tamper(self):
        report, record, _, _ = self.validation()
        game = daoctl.discover_games(self.c.prefix)[0]
        record["runtime_identity"] = {
            "large_address_aware": True,
            "ntdll_sha256": hashlib.sha256(self.native.read_bytes()).hexdigest()}
        report.write_text(json.dumps(record))
        for state in (self.memory_status(enabled=False, managed=True),
                      self.memory_status(supported=False, enabled=True, managed=True)):
            with self.subTest(state=state):
                self.backend.status.return_value = state
                self.assertFalse(self.c.compatibility_verified(game))


if __name__ == "__main__":
    unittest.main()
