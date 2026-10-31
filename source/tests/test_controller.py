"""Controller regression tests: all processes and network requests are mocked."""

import contextlib
import io
import json
import os
from pathlib import Path
import plistlib
import signal
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import daoctl
import game_setup


class Download(io.BytesIO):
    url = daoctl.STEAM_URL


class ProjectRootTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        self.original = self.root / "Original DAOMac"
        self.original.mkdir()
        self.script = self.root / "Applications/Dragon Age Origins.app/Contents/Resources/daoctl.py"
        self.script.parent.mkdir(parents=True)
        self.script.write_text("# fixture\n")
        self.location = self.script.parent / "runtime-location.json"
        self.environment = mock.patch.dict(os.environ, {"DAO_PROJECT_ROOT": ""})
        self.environment.start()
        self.addCleanup(self.environment.stop)

    def test_copied_app_resolves_original_runtime_without_creating_files(self):
        self.location.write_text(json.dumps({"root": str(self.original)}))
        before = sorted(str(path.relative_to(self.root)) for path in self.root.rglob("*"))
        with mock.patch.object(daoctl, "__file__", str(self.script)):
            self.assertEqual(daoctl.project_root(), self.original)
        self.assertEqual(before, sorted(str(path.relative_to(self.root)) for path in self.root.rglob("*")))

    def test_explicit_environment_takes_priority_over_invalid_bundle_reference(self):
        self.location.write_text("not JSON")
        with mock.patch.object(daoctl, "__file__", str(self.script)), \
                mock.patch.dict(os.environ, {"DAO_PROJECT_ROOT": str(self.original)}):
            self.assertEqual(daoctl.project_root(), self.original)

    def test_source_ignores_adjacent_reference_and_keeps_original_derivation(self):
        source = self.original / "source/daoctl.py"
        source.parent.mkdir()
        source.write_text("# fixture\n")
        (source.parent / "runtime-location.json").write_text(json.dumps({"root": str(self.root / "Applications")}))
        with mock.patch.object(daoctl, "__file__", str(source)):
            self.assertEqual(daoctl.project_root(), self.original)

    def test_bundle_without_reference_defaults_to_private_application_support(self):
        script = self.original / "Dragon Age Origins.app/Contents/Resources/daoctl.py"
        script.parent.mkdir(parents=True)
        script.write_text("# fixture\n")
        with mock.patch.object(daoctl, "__file__", str(script)):
            self.assertEqual(daoctl.project_root(), Path.home() / "Library/Application Support/OriginsLauncher")

    def test_non_app_resources_directory_cannot_supply_runtime_reference(self):
        script = self.root / "Ordinary Folder/Contents/Resources/daoctl.py"
        script.parent.mkdir(parents=True)
        script.write_text("# fixture\n")
        (script.parent / "runtime-location.json").write_text(json.dumps({"root": str(self.original)}))
        with mock.patch.object(daoctl, "__file__", str(script)):
            with self.assertRaises(RuntimeError):
                daoctl.project_root()

    def test_malformed_relative_missing_and_oversized_references_are_refused(self):
        records = [None, [], {}, {"root": None}, {"root": "../Original DAOMac"},
                   {"root": "~/Original DAOMac"}, {"root": str(self.root / "gone")},
                   {"root": str(self.script)}]
        raw_records = [json.dumps(value) for value in records] + ["{bad JSON", " " * 16385]
        with mock.patch.object(daoctl, "__file__", str(self.script)):
            for raw in raw_records:
                with self.subTest(raw=raw[:100]):
                    self.location.write_text(raw)
                    with self.assertRaisesRegex(daoctl.DAOError, "runtime-location.json"):
                        daoctl.project_root()

    def test_dangling_reference_does_not_fall_back_to_applications(self):
        self.location.symlink_to(self.root / "missing-reference.json")
        with mock.patch.object(daoctl, "__file__", str(self.script)):
            with self.assertRaises(daoctl.DAOError):
                daoctl.project_root()

    def test_invalid_reference_returns_clear_cli_error_before_controller_creation(self):
        self.location.write_text("{}")
        with mock.patch.object(daoctl, "__file__", str(self.script)), \
                mock.patch.object(daoctl, "Controller") as controller, \
                contextlib.redirect_stdout(io.StringIO()) as output:
            code = daoctl.main(["status"])
        self.assertEqual(code, 1)
        self.assertFalse(json.loads(output.getvalue())["ok"])
        self.assertIn("runtime-location.json", json.loads(output.getvalue())["message"])
        controller.assert_not_called()


class WindowsImageTests(unittest.TestCase):
    def test_leading_image_handles_windows_paths_and_arguments(self):
        for command in (
                "DAOrigins.exe", "  DAOrigins.exe -windowed",
                r"C:\Program Files (x86)\Steam\steamapps\common\Dragon Age Ultimate Edition\bin_ship\DAOrigins.exe -windowed",
                r'"C:\Program Files (x86)\Steam\steamapps\common\Dragon Age Ultimate Edition\bin_ship\DAOrigins.exe" -windowed',
                r"c:/Program Files/Dragon Age/bin_ship/daorigins.EXE",
                r"\\server\game files\bin_ship\DAOrigins.exe -windowed"):
            with self.subTest(command=command):
                self.assertTrue(daoctl.windows_process_is(command, "DAOrigins.exe"))

    def test_other_image_arguments_and_filename_lookalikes_are_not_game(self):
        for command in (
                r"C:\Program Files (x86)\Steam\steamapps\common\Dragon Age Ultimate Edition\bin_ship\DAOriginsConfig.exe -p -c C:\Program Files (x86)\Steam\steamapps\common\Dragon Age Ultimate Edition\bin_ship\DAOrigins.exe -f DAOriginsLauncher.exe",
                r'"C:\Game\DAOriginsConfig.exe" -c "C:\Game\DAOrigins.exe"',
                r"cmd.exe /c C:\Game\DAOrigins.exe",
                r"python inspect.py C:\Game\DAOrigins.exe",
                r"/usr/bin/python3 inspect.py C:\Game\DAOrigins.exe",
                "OtherDAOrigins.exe", "DAOrigins.exe.backup", '"DAOrigins.exe"suffix',
                '"C:\\Game\\DAOrigins.exe', ""):
            with self.subTest(command=command):
                self.assertFalse(daoctl.windows_process_is(command, "DAOrigins.exe"))


class ControllerTests(unittest.TestCase):
    def setUp(self):
        platform = mock.patch.object(daoctl, "platform_status", return_value={"platform_supported": True, "rosetta_ready": True, "phase": "supported", "message": "Fixture platform"})
        platform.start()
        self.addCleanup(platform.stop)
        configuration = mock.patch.object(game_setup, "configuration_status", return_value={"ready": True, "message": "Fixture configured game"})
        configuration.start()
        self.addCleanup(configuration.stop)
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = (Path(self.temp.name) / "DAO project with spaces").resolve()
        self.c = daoctl.Controller(self.root)
        for executable in (self.c.launcher, self.c.wine, self.c.wineserver):
            executable.parent.mkdir(parents=True, exist_ok=True)
            executable.write_bytes(b"fixture - never execute")
        self.c.prefix.mkdir(parents=True, exist_ok=True)
        for name in ("system.reg", "user.reg"):
            (self.c.prefix / name).write_text("WINE REGISTRY Version 2\n")
        (self.c.prefix / "drive_c/users/Sikarugir/Documents").mkdir(parents=True)
        with (self.c.contents / "Info.plist").open("wb") as handle:
            plistlib.dump({}, handle)
        self.steam_dir = self.c.prefix / "drive_c/Program Files (x86)/Steam"

    def steam(self):
        self.steam_dir.mkdir(parents=True, exist_ok=True)
        exe = self.steam_dir / "steam.exe"
        exe.write_bytes(b"fixture - never execute")
        return exe

    def game(self, flags=4, appid="47810", manifest=True):
        self.steam()
        steamapps = self.steam_dir / "steamapps"
        folder = "Dragon Age Ultimate Edition" if appid == "47810" else "Dragon Age Origins"
        game_dir = steamapps / "common" / folder
        (game_dir / "bin_ship").mkdir(parents=True, exist_ok=True)
        (game_dir / "bin_ship/DAOrigins.exe").write_bytes(b"MZ fixture")
        if manifest:
            (steamapps / ("appmanifest_" + appid + ".acf")).write_text(
                '"AppState" { "appid" "' + appid + '" "installdir" "' + folder +
                '" "StateFlags" "' + str(flags) + '" }')
        return game_dir

    def validation(self):
        game_dir = self.game()
        stat = (game_dir / "bin_ship/DAOrigins.exe").stat()
        confirmed = "2026-10-25T18:00:00+00:00"
        record = {"schema_version": 1, "source": "user_report", "appid": "47810",
                  "game_executable": {"size": stat.st_size, "mtime_ns": stat.st_mtime_ns},
                  "checks": {"gameplay": True, "audio": True, "save_reload": True},
                  "configurations": [{"width": 1280, "height": 800, "fullscreen": False,
                                      "confirmed_at": confirmed}], "confirmed_at": confirmed}
        self.c.data.mkdir(exist_ok=True)
        report = self.c.data / "validation.json"
        report.write_text(json.dumps(record))
        ini = self.c.prefix / "drive_c/users/Sikarugir/Documents/BioWare/Dragon Age/Settings/DragonAge.ini"
        ini.parent.mkdir(parents=True, exist_ok=True)
        ini.write_text("[VideoOptions]\nResolutionWidth=1280\nResolutionHeight=800\nFullScreen=0\n")
        return report, record, ini, game_dir / "bin_ship/DAOrigins.exe"

    def tree(self):
        return {str(path.relative_to(self.root)): (path.stat().st_mtime_ns,
                path.read_bytes() if path.is_file() else None)
                for path in self.root.rglob("*")}

    def test_status_is_read_only_and_does_not_initialize_or_measure(self):
        self.steam()
        before = self.tree()
        with mock.patch.object(self.c, "processes", return_value=[]), \
                mock.patch.object(self.c, "initialize") as initialize, \
                mock.patch.object(self.c, "measure") as measure, \
                mock.patch.object(daoctl.subprocess, "Popen") as popen, \
                mock.patch.object(daoctl.urllib.request, "urlopen") as urlopen:
            status = self.c.status()
        self.assertEqual(status["phase"], "sign_in")
        self.assertFalse(status["compatibility_verified"])
        self.assertEqual(before, self.tree())
        self.assertFalse(self.c.data.exists())
        for forbidden in (initialize, measure, popen, urlopen):
            forbidden.assert_not_called()

    def test_status_missing_manifest_does_not_claim_game_installed(self):
        self.game(manifest=False)
        with mock.patch.object(self.c, "processes", return_value=[]):
            status = self.c.status()
        self.assertFalse(status["game_installed"])
        self.assertEqual(status["installed_editions"], [])

    def test_explicit_matching_validation_is_read_only_and_reaches_status_and_play(self):
        self.validation()
        before = self.tree()
        with mock.patch.object(self.c, "processes", return_value=[]), \
                mock.patch.object(self.c, "steam_command", return_value={"ok": True}) as command:
            status = self.c.status()
            self.assertEqual(before, self.tree())
            self.assertTrue(status["compatibility_verified"])
            self.assertEqual(status["phase"], "ready")
            self.assertIn("You confirmed", status["message"])
            result = self.c.play("47810")
        command.assert_called_once_with(["-applaunch", "47810"], "play")
        self.assertIn("You confirmed", result["message"])
        with mock.patch.object(self.c, "processes", return_value=[(104, 1, "DAOrigins.exe")]):
            status = self.c.status()
        self.assertTrue(status["compatibility_verified"])
        self.assertEqual(status["phase"], "playing")
        self.assertIn("You confirmed", status["message"])

    def test_invalid_or_nonhuman_validation_never_verifies(self):
        report, valid, _, _ = self.validation()
        invalid = [None, [], {**valid, "source": "automatic"}, {**valid, "schema_version": True},
                   {**valid, "confirmed_at": "not-a-date"},
                   {**valid, "checks": {"gameplay": True, "audio": True, "save_reload": False}},
                   {**valid, "checks": {"gameplay": "true", "audio": True, "save_reload": True}},
                   {**valid, "configurations": []},
                   {**valid, "configurations": [{"width": 1280, "height": 800, "fullscreen": 0,
                                                 "confirmed_at": valid["confirmed_at"]}]}]
        with mock.patch.object(self.c, "processes", return_value=[]):
            for record in invalid:
                with self.subTest(record=record):
                    report.write_text(json.dumps(record))
                    self.assertFalse(self.c.status()["compatibility_verified"])
            for raw in ("{malformed", "[" * 2000 + "]" * 2000, " " * 65537 + json.dumps(valid)):
                report.write_text(raw)
                self.assertFalse(self.c.status()["compatibility_verified"])
            report.unlink()
            self.assertFalse(self.c.status()["compatibility_verified"])

    def test_pending_or_failed_display_change_cannot_reuse_old_validation(self):
        self.validation()
        ledger = self.c.data / "display-settings.json"
        records = [
            {"schema_version": 1, "pending_confirmation": True},
            {"schema_version": 1, "pending_confirmation": False, "recovery_required": True},
            {"schema_version": True, "pending_confirmation": False},
            {"schema_version": 1}, None, [],
        ]
        with mock.patch.object(self.c, "processes", return_value=[]):
            for record in records:
                ledger.write_text(json.dumps(record))
                self.assertFalse(self.c.status()["compatibility_verified"])
            ledger.write_text("{broken")
            self.assertFalse(self.c.status()["compatibility_verified"])
            ledger.write_text(json.dumps({"schema_version": 1, "pending_confirmation": False,
                                          "recovery_required": False}))
            before = self.tree()
            self.assertTrue(self.c.status()["compatibility_verified"])
            self.assertEqual(before, self.tree())

    def test_changed_executable_invalidates_validation_even_when_size_or_time_matches(self):
        _, _, _, exe = self.validation()
        original = exe.stat()
        with mock.patch.object(self.c, "processes", return_value=[]):
            os.utime(exe, ns=(original.st_atime_ns, original.st_mtime_ns + 1_000_000))
            self.assertFalse(self.c.status()["compatibility_verified"])
            exe.write_bytes(exe.read_bytes() + b"new version")
            os.utime(exe, ns=(original.st_atime_ns, original.st_mtime_ns))
            self.assertFalse(self.c.status()["compatibility_verified"])

    def test_unconfirmed_display_mode_requires_its_own_human_confirmation(self):
        report, record, ini, _ = self.validation()
        ini.write_text("[VideoOptions]\nResolutionWidth=1920\nResolutionHeight=1200\nFullScreen=1\n")
        with mock.patch.object(self.c, "processes", return_value=[]):
            self.assertFalse(self.c.status()["compatibility_verified"])
            record["configurations"].append({"width": 1920, "height": 1200, "fullscreen": True,
                                             "confirmed_at": "2026-10-25T18:10:00Z"})
            report.write_text(json.dumps(record))
            self.assertTrue(self.c.status()["compatibility_verified"])
            ini.write_text("[VideoOptions]\nResolutionWidth=1280\nResolutionHeight=800\nFullScreen=1\n")
            self.assertFalse(self.c.status()["compatibility_verified"])

    def test_validation_does_not_transfer_to_another_selected_or_incomplete_edition(self):
        self.validation()
        self.game(appid="17450")
        self.c.save_state(selected_appid="17450")
        with mock.patch.object(self.c, "processes", return_value=[]):
            status = self.c.status()
        self.assertEqual(status["game_appid"], "17450")
        self.assertFalse(status["compatibility_verified"])
        self.c.save_state(selected_appid="47810")
        manifest = self.steam_dir / "steamapps/appmanifest_47810.acf"
        manifest.write_text(manifest.read_text().replace('"StateFlags" "4"', '"StateFlags" "1048580"'))
        with mock.patch.object(self.c, "processes", return_value=[]):
            self.assertFalse(self.c.status()["compatibility_verified"])

    def test_missing_invalid_or_external_display_settings_fail_closed(self):
        _, _, ini, _ = self.validation()
        with mock.patch.object(self.c, "processes", return_value=[]):
            for content in ("[VideoOptions]\nFullScreen=0\n", "malformed INI", 
                            "[VideoOptions]\nResolutionWidth=1280\nResolutionHeight=800\nFullScreen=2\n"):
                ini.write_text(content)
                self.assertFalse(self.c.status()["compatibility_verified"])
            ini.unlink()
            self.assertFalse(self.c.status()["compatibility_verified"])
            external = self.root.parent / "external.ini"
            external.write_text("[VideoOptions]\nResolutionWidth=1280\nResolutionHeight=800\nFullScreen=0\n")
            ini.symlink_to(external)
            self.assertFalse(self.c.status()["compatibility_verified"])
            ini.unlink()
            ini.symlink_to(ini.name)
            self.assertFalse(self.c.status()["compatibility_verified"])

    def test_status_distinguishes_configuration_from_running_game(self):
        self.game()
        steam = (101, 1, r"C:\Program Files (x86)\Steam\steam.exe")
        webhelper = (102, 1, r'"C:\Program Files (x86)\Steam\bin\cef\cef.win7x64\steamwebhelper.exe" --type=renderer')
        config = (103, 1, r"C:\Program Files (x86)\Steam\steamapps\common\Dragon Age Ultimate Edition\bin_ship\DAOriginsConfig.exe -p -c C:\Program Files (x86)\Steam\steamapps\common\Dragon Age Ultimate Edition\bin_ship\DAOrigins.exe -f DAOriginsLauncher.exe")
        with mock.patch.object(self.c, "processes", return_value=[steam, webhelper, config]):
            status = self.c.status()
        self.assertFalse(status["game_running"])
        self.assertTrue(status["steam_running"])
        self.assertEqual(status["steam_startup_phase"], "client_running")
        self.assertEqual(status["phase"], "game_configuration_running")
        game_path = r"C:\Program Files (x86)\Steam\steamapps\common\Dragon Age Ultimate Edition\bin_ship\DAOrigins.exe"
        for command in (game_path, '"' + game_path + '" -windowed'):
            with self.subTest(command=command), mock.patch.object(self.c, "processes", return_value=[
                    steam, webhelper, (104, 1, command)]):
                status = self.c.status()
            self.assertTrue(status["game_running"])
            self.assertEqual(status["phase"], "playing")

    def test_steam_detection_uses_images_not_process_arguments(self):
        self.steam()
        config = (101, 1, r"C:\Windows\system32\cmd.exe /c C:\Program Files (x86)\Steam\steam.exe steamwebhelper.exe")
        with mock.patch.object(self.c, "processes", return_value=[config]):
            status = self.c.status()
        self.assertFalse(status["steam_running"])
        self.assertEqual(status["steam_startup_phase"], "stopped")
        for command in (r"C:\Program Files (x86)\Steam\steam.exe --arg=steamwebhelper.exe",
                        r'"C:\Program Files (x86)\Steam\steam.exe" --arg=steamwebhelper.exe'):
            with self.subTest(command=command), mock.patch.object(self.c, "processes", return_value=[(101, 1, command)]):
                status = self.c.status()
            self.assertTrue(status["steam_running"])
            self.assertEqual(status["steam_startup_phase"], "starting")

    def test_steam_update_status_is_read_only_and_does_not_offer_sign_in(self):
        self.steam()
        log = self.steam_dir / "logs/bootstrap_log.txt"
        log.parent.mkdir()
        log.write_text("[2026-10-25 16:13:46] Downloading update (194,299 of 239,614 KB)...\n")
        before = self.tree()
        with mock.patch.object(self.c, "processes", return_value=[(101, 1, "steam.exe")]):
            status = self.c.status()
        self.assertEqual(status["phase"], "steam_updating")
        self.assertEqual(status["steam_startup_phase"], "updating")
        self.assertEqual(before, self.tree())

    def test_live_webhelper_ignores_stale_updater_history_without_reading_it(self):
        self.steam()
        with mock.patch.object(self.c, "processes", return_value=[
                (101, 1, "steam.exe"), (102, 1, "steamwebhelper.exe")]), \
                mock.patch.object(self.c, "steam_bootstrap_tail") as read_tail:
            status = self.c.status()
        self.assertEqual(status["phase"], "sign_in")
        self.assertEqual(status["steam_startup_phase"], "client_running")
        read_tail.assert_not_called()

    def test_completed_updater_without_ui_gets_grace_then_restart_advice(self):
        self.steam()
        text = "update complete, launching steam...\nshutdown\n"
        with mock.patch.object(self.c, "processes", return_value=[(101, 1, "steam.exe")]), \
                mock.patch.object(self.c, "steam_bootstrap_tail", return_value=(text, 100)), \
                mock.patch.object(daoctl.time, "time", return_value=120):
            self.assertEqual(self.c.status()["phase"], "steam_starting")
        with mock.patch.object(self.c, "processes", return_value=[(101, 1, "steam.exe")]), \
                mock.patch.object(self.c, "steam_bootstrap_tail", return_value=(text, 100)), \
                mock.patch.object(daoctl.time, "time", return_value=200):
            status = self.c.status()
        self.assertEqual(status["phase"], "steam_restart_required")
        self.assertIn("use Stop, then Open Steam", status["message"])
        # With no client process, opening Steam is sufficient; do not request a stop.
        with mock.patch.object(self.c, "processes", return_value=[]), \
                mock.patch.object(self.c, "steam_bootstrap_tail") as read_tail:
            self.assertEqual(self.c.status()["steam_startup_phase"], "stopped")
        read_tail.assert_not_called()

    def test_new_bootstrap_session_does_not_inherit_old_completed_update(self):
        exe = self.steam()
        text = ("update complete, launching steam...\nshutdown\n"
                "startup - updater built oct 21 2026\nverification complete\n")
        with mock.patch.object(self.c, "steam_bootstrap_tail", return_value=(text, 100)):
            self.assertEqual(self.c.steam_startup(exe, ["steam.exe"]), "starting")

    def test_bootstrap_log_read_is_bounded_and_refuses_external_symlink(self):
        exe = self.steam()
        path = self.steam_dir / "logs/bootstrap_log.txt"
        path.parent.mkdir()
        payload = b"old history\n" * daoctl.BOOTSTRAP_TAIL_BYTES + b"Downloading update (1 of 2 KB)...\n"
        path.write_bytes(payload)
        reader = io.BytesIO(payload)
        real_read = reader.read
        with mock.patch.object(reader, "read", wraps=real_read) as read, \
                mock.patch.object(reader, "fileno", return_value=123), \
                mock.patch.object(Path, "open", return_value=reader), \
                mock.patch.object(daoctl.os, "fstat", return_value=mock.Mock(st_mtime=100)):
            text, modified = self.c.steam_bootstrap_tail(exe)
        read.assert_called_once_with(daoctl.BOOTSTRAP_TAIL_BYTES)
        self.assertLessEqual(len(text), daoctl.BOOTSTRAP_TAIL_BYTES)
        self.assertIn("downloading update", text)
        self.assertEqual(modified, 100)
        outside = self.root / "private-account-data.txt"
        outside.write_text("SYNTHETIC_SECRET_DO_NOT_READ")
        path.unlink()
        path.symlink_to(outside)
        with mock.patch.object(Path, "open") as forbidden:
            self.assertEqual(self.c.steam_bootstrap_tail(exe), ("", 0))
        forbidden.assert_not_called()

    def test_status_and_failed_measure_tolerate_malformed_cached_storage(self):
        self.steam()
        for value in (None, [], {}, "not-a-number"):
            with self.subTest(value=value):
                self.c.save_state(storage_bytes=value)
                with mock.patch.object(self.c, "processes", return_value=[]), \
                        mock.patch.object(daoctl.subprocess, "run", return_value=
                                          subprocess.CompletedProcess([], 1, "", "")):
                    self.assertEqual(self.c.status()["storage_bytes"], 0)
                    self.assertEqual(self.c.measure(), 0)

    def test_setup_is_idempotent_for_existing_steam(self):
        self.steam()
        with mock.patch.object(self.c, "download_steam") as download, \
                mock.patch("display_settings.DisplaySettings._guard"), \
                mock.patch.object(self.c, "launch_wss") as launch, \
                mock.patch.object(self.c, "run_batch") as batch, \
                mock.patch.object(self.c, "steam_command", return_value={"ok": True}) as steam, \
                mock.patch.object(self.c, "measure", return_value=0):
            first = self.c.setup()
            first_plist = (self.c.contents / "Info.plist").read_bytes()
            second = self.c.setup()
        self.assertTrue(first["ok"] and second["ok"])
        self.assertEqual(first_plist, (self.c.contents / "Info.plist").read_bytes())
        for forbidden in (download, launch, batch):
            forbidden.assert_not_called()
        self.assertEqual(steam.call_count, 2)

    def test_setup_opens_interactive_installer_without_claiming_it_finished(self):
        installer = self.root / "test-installer.exe"
        installer.write_bytes(b"MZ fake installer")
        process = mock.Mock()
        process.poll.return_value = 0
        log = self.root / "installer.log"
        with mock.patch.object(self.c, "initialize"), \
                mock.patch("display_settings.DisplaySettings._guard"), \
                mock.patch.object(self.c, "download_steam", return_value=installer), \
                mock.patch.object(self.c, "run_batch", return_value=(process, log)) as batch, \
                mock.patch.object(self.c, "steam_command", return_value={"ok": True}), \
                mock.patch.object(self.c, "measure", return_value=0), \
                mock.patch.object(daoctl, "find_steam", return_value=None), \
                mock.patch.object(daoctl.time, "sleep"), \
                mock.patch.object(daoctl.time, "monotonic", side_effect=range(10)):
            result = self.c.setup()
        self.assertTrue(result["ok"])
        self.assertIn("Complete the Windows Steam installer", result["message"])
        self.assertEqual(batch.call_args.args[1], '"C:\\dao-support\\SteamSetup.exe"')

    def test_malformed_receipt_is_not_trusted_or_an_unhandled_error(self):
        self.c.downloads.mkdir()
        dest = self.c.downloads / "SteamSetup.exe"
        receipt = self.c.downloads / "SteamSetup.receipt.json"
        payload = b"MZ" + b"0" * 100001
        for record in ([], None, "not-an-object"):
            with self.subTest(record=record):
                dest.write_bytes(b"untrusted old content")
                receipt.write_text(json.dumps(record))
                with mock.patch.object(daoctl.urllib.request, "urlopen",
                                       return_value=Download(payload)) as fetch:
                    self.assertEqual(self.c.download_steam(), dest)
                fetch.assert_called_once()
                self.assertEqual(dest.read_bytes(), payload)
                self.assertEqual(json.loads(receipt.read_text())["url"], daoctl.STEAM_URL)

    def test_stop_uses_only_this_prefix_and_cleans_inherited_wine_configuration(self):
        foreign = self.root.parent / "other-wine-prefix"
        foreign.mkdir()
        marker = foreign / "keep.txt"
        marker.write_text("unchanged")
        inherited = {"WINEPREFIX": str(foreign), "WINEDLLOVERRIDES": "hostile",
                     "WINELOADER": "/another/wine", "DXVK_CONFIG_FILE": "/another/config",
                     "VK_DRIVER_FILES": "/another/icd", "VK_ICD_FILENAMES": "/another/icd2"}
        with mock.patch.dict(os.environ, inherited), \
                mock.patch.object(daoctl.subprocess, "run", return_value=
                                  subprocess.CompletedProcess([], 0)) as run, \
                mock.patch.object(daoctl.os, "killpg") as killpg:
            result = self.c.stop()
        self.assertTrue(result["ok"])
        run.assert_called_once()
        args, kwargs = run.call_args
        self.assertEqual(args[0], [str(self.c.wineserver), "-k"])
        self.assertEqual(kwargs["env"]["WINEPREFIX"], str(self.c.prefix))
        for name in inherited:
            if name != "WINEPREFIX":
                self.assertNotIn(name, kwargs["env"])
        killpg.assert_not_called()
        self.assertEqual(marker.read_text(), "unchanged")

    def test_process_attribution_handles_orphans_and_rejects_command_text_spoofing(self):
        own_engine = self.c.contents / "SharedSupport/wine/lib/wine/x86_64-unix/wine"
        other_engine = self.root.parent / "Unrelated Runtime.app/Contents/wine"
        sibling_engine = Path(str(self.c.runtime) + ".other") / "Contents/wine"
        commands = [
            (101, 1, r"C:\Program Files (x86)\Steam\steam.exe"),
            (102, 1, r"C:\Other Game\DAOrigins.exe"),
            (103, 1, "/usr/bin/python3 inspect.py " + str(self.c.launcher)),
            (104, 101, "child-helper-without-exe-name"),
            (105, 104, "nested-helper"),
            (106, 1, str(self.c.runtime) + ".other/Contents/MacOS/game.exe"),
            (107, 1, "unknown.exe"),
        ]
        actual = {101: own_engine, 102: other_engine, 103: Path("/usr/bin/python3"),
                  106: sibling_engine}

        def pidpath(pid, buffer, length):
            path = actual.get(pid)
            if path is None:
                return 0
            buffer.value = os.fsencode(path)
            return len(buffer.value)

        library = mock.Mock()
        library.proc_pidpath.side_effect = pidpath
        output = "\n".join(f"{pid} {ppid} {cmd}" for pid, ppid, cmd in commands)
        with mock.patch.object(daoctl.subprocess, "run", return_value=
                               subprocess.CompletedProcess([], 0, output, "")), \
                mock.patch.object(daoctl.ctypes, "CDLL", return_value=library):
            rows = self.c.processes()
        self.assertEqual([row[0] for row in rows], [101, 104, 105])

    def test_unavailable_process_inspection_fails_closed(self):
        with mock.patch.object(daoctl.subprocess, "run", return_value=
                               subprocess.CompletedProcess([], 0, "101 1 steam.exe", "")), \
                mock.patch.object(daoctl.ctypes, "CDLL", side_effect=OSError("unavailable")):
            self.assertEqual(self.c.processes(), [])

    def test_timeout_targets_only_controller_created_process_group(self):
        process = mock.Mock(pid=12345)
        process.wait.side_effect = subprocess.TimeoutExpired("fixture", 1)
        with mock.patch.object(daoctl.os, "killpg") as killpg:
            with self.assertRaises(daoctl.DAOError):
                self.c.wait(process, 1, self.root / "fixture.log")
        killpg.assert_called_once_with(12345, signal.SIGTERM)

    def test_lock_excludes_second_controller_then_releases(self):
        second = daoctl.Controller(self.root)
        with self.c.operation():
            with self.assertRaises(daoctl.DAOError):
                with second.operation():
                    self.fail("Second operation must not enter")
        with second.operation():
            pass

    def test_cli_mutation_honors_lock_and_returns_structured_error(self):
        with self.c.operation(), mock.patch.dict(os.environ, {"DAO_PROJECT_ROOT": str(self.root)}), \
                mock.patch.object(daoctl.Controller, "play") as play, \
                contextlib.redirect_stdout(io.StringIO()) as output:
            code = daoctl.main(["play"])
        self.assertEqual(code, 1)
        self.assertFalse(json.loads(output.getvalue())["ok"])
        play.assert_not_called()

    def test_display_cli_reads_without_lock_but_mutations_obey_shared_lock(self):
        module = mock.Mock()
        manager = module.DisplaySettings.return_value
        manager.options.return_value = {"ok": True, "presets": []}
        with self.c.operation(), mock.patch.dict(os.environ, {"DAO_PROJECT_ROOT": str(self.root)}), \
                mock.patch.dict(sys.modules, {"display_settings": module}):
            with contextlib.redirect_stdout(io.StringIO()) as output:
                self.assertEqual(daoctl.main(["display-options"]), 0)
            self.assertEqual(json.loads(output.getvalue()), {"ok": True, "presets": []})
            for command in ["display-apply", "display-restore", "display-confirm"]:
                with contextlib.redirect_stdout(io.StringIO()) as output:
                    self.assertEqual(daoctl.main([command]), 1)
                self.assertIn("Another launcher operation", json.loads(output.getvalue())["message"])
        manager.apply.assert_not_called()
        manager.restore.assert_not_called()
        manager.confirm.assert_not_called()

    def test_display_cli_requires_selection_and_surfaces_backend_errors(self):
        module = mock.Mock()
        manager = module.DisplaySettings.return_value
        manager.apply.side_effect = ValueError("The display changed. Choose a preset again.")
        with mock.patch.dict(os.environ, {"DAO_PROJECT_ROOT": str(self.root)}), \
                mock.patch.dict(sys.modules, {"display_settings": module}):
            with contextlib.redirect_stdout(io.StringIO()) as output:
                self.assertEqual(daoctl.main(["display-apply"]), 1)
            self.assertIn("Choose a display preset", json.loads(output.getvalue())["message"])
            manager.apply.assert_not_called()
            with contextlib.redirect_stdout(io.StringIO()) as output:
                code = daoctl.main(["display-apply", "--preset", "window-1280x800", "--ui-size", "larger"])
            self.assertEqual(code, 1)
            self.assertEqual(json.loads(output.getvalue())["message"], "The display changed. Choose a preset again.")
        manager.apply.assert_called_once_with("window-1280x800", "larger")

    def test_windows_shell_metacharacters_are_rejected_before_batch_creation(self):
        self.steam()
        for flag in ('steam://install/47810&calc', '" & calc', "%COMSPEC%", "a\nb",
                     "a\rb", "a|b", "a>b", "a<b"):
            with self.subTest(flag=flag), mock.patch.object(self.c, "run_batch") as batch:
                with self.assertRaises(daoctl.DAOError):
                    self.c.steam_command([flag], "fixture")
                batch.assert_not_called()

    def test_play_rejects_incomplete_and_missing_manifest(self):
        self.game(flags=4 | 1048576)
        with mock.patch.object(self.c, "steam_command") as command:
            with self.assertRaises(daoctl.DAOError):
                self.c.play("47810")
            (self.steam_dir / "steamapps/appmanifest_47810.acf").unlink()
            with self.assertRaises(daoctl.DAOError):
                self.c.play()
            command.assert_not_called()

    def test_play_uses_selected_complete_edition_and_never_claims_verification(self):
        self.game(appid="17450")
        self.game(appid="47810")
        self.c.save_state(selected_appid="47810")
        with mock.patch.object(self.c, "steam_command", return_value={"ok": True}) as command, \
                mock.patch.object(self.c, "processes", return_value=[]):
            result = self.c.play()
        command.assert_called_once_with(["-applaunch", "47810"], "play")
        self.assertIn("not yet been verified", result["message"])

    def test_play_requires_configuration_to_finish_without_launching_again(self):
        self.game()
        process = (103, 1, r'"C:\Program Files (x86)\Steam\steamapps\common\Dragon Age Ultimate Edition\bin_ship\DAOriginsConfig.exe" -p -c "C:\Game\DAOrigins.exe"')
        with mock.patch.object(self.c, "processes", return_value=[process]), \
                mock.patch.object(self.c, "steam_command") as command:
            with self.assertRaisesRegex(daoctl.DAOError, "Finish or close it"):
                self.c.play("47810")
        command.assert_not_called()

    def test_play_is_successful_noop_when_main_game_is_running(self):
        self.game()
        process = (104, 1, r"C:\Program Files (x86)\Steam\steamapps\common\Dragon Age Ultimate Edition\bin_ship\DAOrigins.exe")
        with mock.patch.object(self.c, "processes", return_value=[process]), \
                mock.patch.object(self.c, "steam_command") as command, \
                mock.patch.object(self.c, "save_state") as save:
            result = self.c.play("47810")
        self.assertTrue(result["ok"])
        self.assertIn("already running", result["message"])
        command.assert_not_called()
        save.assert_not_called()

    def test_play_prepares_selected_display_for_explicit_edition_before_launch(self):
        self.game(appid="17450")
        self.game(appid="47810")
        self.c.save_state(selected_appid="17450")
        manager = mock.Mock()
        module = mock.Mock(DisplaySettings=mock.Mock(return_value=manager))
        events = []
        manager.prepare_for_play.side_effect = lambda *args: events.append("prepare")
        def launch(*args):
            events.append("launch")
            return {"ok": True}
        with mock.patch.dict(sys.modules, {"display_settings": module}), \
                mock.patch.object(self.c, "processes", return_value=[]), \
                mock.patch.object(self.c, "steam_command", side_effect=launch):
            self.c.play("47810", preset="fullscreen-retina", ui_size="comfortable")
        module.DisplaySettings.assert_called_once_with(self.c, appid="47810")
        manager.prepare_for_play.assert_called_once_with("fullscreen-retina", "comfortable")
        self.assertEqual(events, ["prepare", "launch"])

    def test_failed_display_preparation_prevents_game_launch(self):
        self.game()
        manager = mock.Mock()
        manager.prepare_for_play.side_effect = ValueError("Display changed")
        module = mock.Mock(DisplaySettings=mock.Mock(return_value=manager))
        with mock.patch.dict(sys.modules, {"display_settings": module}), \
                mock.patch.object(self.c, "processes", return_value=[]), \
                mock.patch.object(self.c, "steam_command") as launch:
            with self.assertRaisesRegex(ValueError, "Display changed"):
                self.c.play("47810", preset="fullscreen")
        launch.assert_not_called()

    def test_active_game_does_not_apply_new_display_selection(self):
        self.game()
        module = mock.Mock()
        process = (104, 1, r"C:\Game\DAOrigins.exe")
        with mock.patch.dict(sys.modules, {"display_settings": module}), \
                mock.patch.object(self.c, "processes", return_value=[process]), \
                mock.patch.object(self.c, "steam_command") as launch:
            result = self.c.play("47810", preset="fullscreen", ui_size="larger")
        self.assertIn("already running", result["message"])
        module.DisplaySettings.assert_not_called()
        launch.assert_not_called()

    def test_play_cli_forwards_selected_preferences_under_operation_lock(self):
        events = []
        @contextlib.contextmanager
        def operation():
            events.append("lock")
            yield
            events.append("unlock")
        with mock.patch.object(daoctl, "project_root", return_value=self.root), \
                mock.patch.object(daoctl, "Controller", return_value=self.c), \
                mock.patch.object(self.c, "operation", side_effect=operation), \
                mock.patch.object(self.c, "play", side_effect=lambda *args, **kwargs: events.append("play") or {"ok": True}) as play, \
                contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(daoctl.main(["play", "--appid", "47810", "--preset", "fullscreen-retina", "--ui-size", "larger"]), 0)
        play.assert_called_once_with("47810", preset="fullscreen-retina", ui_size="larger", large_address_aware=None, developer_console=None)
        self.assertEqual(events, ["lock", "play", "unlock"])

    def test_ui_scaling_cli_honors_explicit_edition_after_scoped_guard_under_lock(self):
        self.game(appid="17450")
        self.game(appid="47810")
        self.c.save_state(selected_appid="47810")
        events = []
        @contextlib.contextmanager
        def operation():
            events.append("lock")
            yield
            events.append("unlock")
        with mock.patch.object(daoctl, "project_root", return_value=self.root), \
                mock.patch.object(daoctl, "Controller", return_value=self.c), \
                mock.patch.object(self.c, "operation", side_effect=operation), \
                mock.patch("display_settings.DisplaySettings._guard", side_effect=lambda: events.append("guard")), \
                mock.patch("ui_scaling.install_ui_scaling", side_effect=lambda *args, **kwargs: events.append("install") or {"ok": True}) as install, \
                contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(daoctl.main(["install-ui-scaling", "--appid", "17450"]), 0)
        install.assert_called_once_with(self.c, appid="17450")
        self.assertEqual(events, ["lock", "guard", "install", "unlock"])

    def test_diagnostics_redacts_paths_and_excludes_accounts_environment_and_raw_logs(self):
        self.game()
        sentinel = "SYNTHETIC_SECRET_DO_NOT_EXPORT"
        account = self.steam_dir / "config/loginusers.vdf"
        account.parent.mkdir()
        account.write_text(sentinel)
        self.c.logs.mkdir(parents=True)
        (self.c.logs / "raw.log").write_text(sentinel)
        self.c.save_state(storage_bytes=0, password=sentinel, last_log=str(self.c.logs / "raw.log"))
        process = (123, 1, str(self.c.wine) + " steam.exe --password=" + sentinel)

        def measure():
            self.c.save_state(storage_bytes=1234, storage_measured_at="2026-10-25T16:17:00+00:00")
            return 1234

        with mock.patch.object(self.c, "processes", return_value=[process]), \
                mock.patch.object(self.c, "measure", side_effect=measure), \
                mock.patch.dict(os.environ, {"SYNTHETIC_ACCOUNT_SECRET": sentinel}):
            result = self.c.diagnostics()
        report = Path(result["report_path"])
        text = report.read_text()
        self.assertNotIn(sentinel, text)
        self.assertNotIn(str(self.root), text)
        self.assertNotIn("loginusers.vdf", text)
        self.assertIn("<PROJECT>", text)
        self.assertEqual(report.stat().st_mode & 0o777, 0o600)
        data = json.loads(text)
        self.assertFalse(data["status"]["compatibility_verified"])
        self.assertEqual(data["status"]["storage_bytes"], 1234)
        self.assertEqual(data["status"]["storage_measured_at"], "2026-10-25T16:17:00+00:00")


if __name__ == "__main__":
    unittest.main()
