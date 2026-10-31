"""Console launch orchestration without running Wine or changing real games."""
import contextlib
import io
from pathlib import Path
import sys
import unittest
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import daoctl
import developer_console
import large_address
import test_controller as fixtures


class ConsoleControllerTests(unittest.TestCase):
    steam = fixtures.ControllerTests.steam
    game = fixtures.ControllerTests.game

    def setUp(self):
        fixtures.ControllerTests.setUp(self)
        self.patch(mock.patch.object(self.c, "processes", return_value=[]))
        self.strict = self.patch(mock.patch("large_address.active_wine_processes", return_value=[]))
        self.prepare = self.patch(mock.patch("developer_console.prepare", return_value=[]))
        self.audio = self.patch(mock.patch.object(self.c, "prepare_audio_fix"))
        self.memory = self.patch(mock.patch.object(self.c, "prepare_large_address"))
        self.launch = self.patch(mock.patch.object(self.c, "steam_command", return_value={"ok": True}))
        self.patch(mock.patch("steam_maintenance.SteamMaintenance.cancel"))
        self.patch(mock.patch.object(self.c, "compatibility_verified", return_value=False))

    def patch(self, patcher):
        result = patcher.start()
        self.addCleanup(patcher.stop)
        return result

    def test_standard_flag_reaches_steam_after_appid(self):
        self.game(appid="17450")
        self.prepare.return_value = ["-enabledeveloperconsole"]
        self.c.play("17450", developer_console=True)
        self.launch.assert_called_once_with(["-applaunch", "17450", "-enabledeveloperconsole"], "play")
        self.assertEqual(self.prepare.call_args.args[1]["appid"], "17450")
        self.assertIs(self.prepare.call_args.args[2], True)

    def test_ultimate_prepares_xml_then_uses_ordinary_steam_launch(self):
        self.game()
        events = []
        self.prepare.side_effect = lambda *args: events.append("console") or []
        self.audio.side_effect = lambda *args: events.append("audio")
        self.memory.side_effect = lambda *args: events.append("memory")
        self.launch.side_effect = lambda *args: events.append("launch") or {"ok": True}
        self.c.play("47810", developer_console=True, large_address_aware=True)
        self.assertEqual(events, ["console", "memory", "audio", "launch"])
        self.launch.assert_called_once_with(["-applaunch", "47810"], "play")

    def test_unspecified_console_preserves_backwards_compatible_launch(self):
        self.game()
        self.c.play("47810")
        self.assertIsNone(self.prepare.call_args.args[2])
        self.strict.assert_not_called()
        self.launch.assert_called_once_with(["-applaunch", "47810"], "play")

    def test_open_game_launcher_or_config_blocks_before_any_preparation(self):
        self.game()
        for name in ["DAOrigins.exe", "DAOriginsLauncher.exe", "DAOriginsConfig.exe"]:
            with self.subTest(name=name):
                self.strict.return_value = [(123, 1, '"C:\\Game\\' + name + '"')]
                with self.assertRaisesRegex(daoctl.DAOError, "Close Dragon Age"):
                    self.c.play("47810", developer_console=False, large_address_aware=True)
        self.prepare.assert_not_called()
        self.memory.assert_not_called()
        self.audio.assert_not_called()
        self.launch.assert_not_called()

    def test_incomplete_process_inventory_blocks_console_edits(self):
        self.game()
        self.strict.side_effect = large_address.LargeAddressError("visibility unavailable")
        with self.assertRaisesRegex(daoctl.DAOError, "Could not confirm"):
            self.c.play("47810", developer_console=True)
        self.prepare.assert_not_called()
        self.launch.assert_not_called()

    def test_malformed_xml_error_prevents_game_launch_and_other_changes(self):
        self.game()
        self.prepare.side_effect = developer_console.DeveloperConsoleError("Malformed launcher XML")
        with self.assertRaisesRegex(daoctl.DAOError, "Malformed launcher XML"):
            self.c.play("47810", developer_console=True, large_address_aware=True)
        self.memory.assert_not_called()
        self.audio.assert_not_called()
        self.launch.assert_not_called()

    def test_console_cli_forwards_both_choices_under_operation_lock(self):
        for choice in ["on", "off"]:
            events = []
            @contextlib.contextmanager
            def operation():
                events.append("lock")
                yield
                events.append("unlock")
            with mock.patch.object(daoctl, "Controller", return_value=self.c), \
                    mock.patch.object(self.c, "operation", side_effect=operation), \
                    mock.patch.object(self.c, "play", side_effect=lambda *a, **k: events.append("play") or {"ok": True}) as play, \
                    contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(daoctl.main(["play", "--appid", "47810", "--developer-console", choice]), 0)
            play.assert_called_once_with("47810", preset=None, ui_size="comfortable",
                                         large_address_aware=None, developer_console=choice == "on")
            self.assertEqual(events, ["lock", "play", "unlock"])


if __name__ == "__main__":
    unittest.main()
