"""Fresh-release safety checks; fixtures never run an installer or use a network."""
import contextlib
import io
import json
from pathlib import Path
import plistlib
import struct
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import bootstrap_runtime
import daoctl
import display_settings
import game_setup


def pe32():
    data = bytearray(512)
    data[:2] = b"MZ"
    struct.pack_into("<I", data, 0x3c, 0x80)
    data[0x80:0x84] = b"PE\0\0"
    struct.pack_into("<H", data, 0x84, 0x14c)
    return bytes(data)


class PlatformTests(unittest.TestCase):
    def observe(self, version="26.0", machine="arm64", rosetta=True, system="darwin"):
        with mock.patch.object(daoctl.sys, "platform", system), \
                mock.patch.object(daoctl.platform, "mac_ver", return_value=(version, (), "")), \
                mock.patch.object(daoctl.platform, "machine", return_value=machine), \
                mock.patch.object(daoctl.Path, "is_file", return_value=rosetta), \
                mock.patch.object(daoctl.subprocess, "run", return_value=subprocess.CompletedProcess([], 0, "0\n", "")):
            return daoctl.platform_status()

    def test_d9vk_release_requires_apple_silicon_and_macos_26(self):
        self.assertTrue(self.observe()["platform_supported"])
        for inputs in ({"version": "15.7"}, {"machine": "x86_64"}, {"system": "linux"}, {"version": ""}):
            with self.subTest(inputs=inputs):
                self.assertEqual(self.observe(**inputs)["phase"], "unsupported_platform")

    def test_missing_rosetta_explains_license_prompt_without_running_installation(self):
        status = self.observe(rosetta=False)
        self.assertTrue(status["platform_supported"])
        self.assertFalse(status["rosetta_ready"])
        self.assertEqual(status["phase"], "rosetta_required")
        self.assertIn("Open the Apple Rosetta installer", status["message"])
        self.assertNotIn("--agree-to-license", status["message"])


class FreshSetupTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve() / "Origins data"
        self.c = daoctl.Controller(self.root)
        platform = mock.patch.object(daoctl, "platform_status", return_value={"platform_supported": True, "rosetta_ready": True, "phase": "supported", "message": "fixture"})
        platform.start()
        self.addCleanup(platform.stop)

    def runtime(self):
        for path in (self.c.launcher, self.c.wine, self.c.wineserver):
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(b"fixture, never execute")
        (self.c.contents / "Info.plist").write_bytes(plistlib.dumps({}))
        self.c.prefix.mkdir(parents=True, exist_ok=True)
        for name in ("system.reg", "user.reg"):
            (self.c.prefix / name).write_text("WINE REGISTRY Version 2\n")
        (self.c.prefix / "drive_c/users/Sikarugir/Documents").mkdir(parents=True, exist_ok=True)

    def game(self):
        self.runtime()
        steam = self.c.prefix / "drive_c/Program Files (x86)/Steam"
        game = steam / "steamapps/common/Dragon Age Ultimate Edition"
        (game / "bin_ship").mkdir(parents=True)
        (steam / "steam.exe").write_bytes(pe32())
        (steam / "steamapps/appmanifest_47810.acf").write_text('"AppState" { "appid" "47810" "installdir" "Dragon Age Ultimate Edition" "StateFlags" "4" }')
        for file in ("bin_ship/DAOrigins.exe", "bin_ship/DAOriginsConfig.exe", "DAOriginsLauncher.exe"):
            (game / file).write_bytes(pe32())
        directx = game / "redist/DirectX"
        directx.mkdir(parents=True)
        for name in (*game_setup.SETUP_FILES, "NOV2007_d3dx9_36_x86.cab", "AUG2006_XACT_x86.cab",
                     "Apr2006_MDX1_x86_Archive.cab", "NOV2007_d3dx9_36_x64.cab"):
            (directx / name).write_bytes(b"fixture " + name.encode())
        for name in ("vcredist_x86.exe", "PhysX_9.09.0408_SystemSoftware.exe"):
            (game / "redist" / name).write_bytes(pe32())
        return game_setup.select_game(self.c)

    def launch_setup(self):
        process = mock.Mock()
        process.poll.return_value = None
        with mock.patch.object(display_settings.DisplaySettings, "_guard"), \
                mock.patch.object(display_settings.DisplaySettings, "_stop_prefix"), \
                mock.patch.object(display_settings.DisplaySettings, "_write_registry") as registry, \
                mock.patch.object(self.c, "run_batch", return_value=(process, self.c.root / "fixture.log")) as batch:
            result = game_setup.configure_game(self.c, "47810")
        self.registry_call = registry
        return result, batch.call_args.args[1]

    def components(self):
        folder = self.c.prefix / "drive_c/windows/syswow64"
        folder.mkdir(parents=True, exist_ok=True)
        for name in game_setup.COMPONENTS:
            (folder / name).write_bytes(pe32())

    def marker(self, value="PREREQUISITES_COMPLETE"):
        record = json.loads((self.c.data / "game-setup-47810.json").read_text())
        path = self.c.prefix / "drive_c/dao-support" / ("game-setup-" + record["id"]) / "result.txt"
        path.write_text(value)

    def test_first_status_is_read_only_and_explains_setup(self):
        with mock.patch.object(self.c, "processes", return_value=[]):
            status = self.c.status()
        self.assertEqual(status["phase"], "setup")
        self.assertFalse(self.root.exists())

    def test_unsupported_platform_cannot_download_or_initialize(self):
        with mock.patch.object(daoctl, "platform_status", return_value={"platform_supported": False, "rosetta_ready": False, "message": "Unsupported fixture"}), \
                mock.patch.object(bootstrap_runtime, "bootstrap") as download, \
                mock.patch.object(self.c, "initialize") as initialize:
            with self.assertRaisesRegex(daoctl.DAOError, "Unsupported"):
                self.c.setup()
        download.assert_not_called()
        initialize.assert_not_called()
        self.assertFalse(self.root.exists())

    def test_missing_runtime_bootstraps_once_and_preserves_existing_runtime(self):
        with mock.patch.object(bootstrap_runtime, "bootstrap", side_effect=lambda *_: self.runtime()) as download:
            self.c.ensure_runtime()
            self.c.ensure_runtime()
        download.assert_called_once_with(self.root, self.c.downloads / "runtime-cache")
        self.assertEqual((self.c.prefix / "user.reg").read_text(), "WINE REGISTRY Version 2\n")

    def test_partial_runtime_is_preserved_and_not_initialized(self):
        self.c.runtime.mkdir(parents=True)
        marker = self.c.runtime / "save-data"
        marker.write_text("preserve me")
        with mock.patch.object(self.c, "initialize") as initialize:
            with self.assertRaisesRegex(daoctl.DAOError, "incomplete"):
                self.c.setup()
        initialize.assert_not_called()
        self.assertEqual(marker.read_text(), "preserve me")
        self.assertFalse(self.c.downloads.exists())

    def test_download_and_lock_symlinks_cannot_write_outside_data_root(self):
        outside = Path(self.temp.name) / "outside"
        outside.mkdir()
        self.root.mkdir()
        self.c.downloads.symlink_to(outside)
        with mock.patch.object(bootstrap_runtime, "bootstrap") as download:
            with self.assertRaises(daoctl.DAOError):
                self.c.ensure_runtime()
        download.assert_not_called()
        self.c.data.symlink_to(outside)
        with self.assertRaises(daoctl.DAOError), self.c.operation():
            pass
        self.assertEqual(list(outside.iterdir()), [])

    def test_complete_download_is_not_mistaken_for_configured_game(self):
        self.game()
        with mock.patch.object(self.c, "processes", return_value=[]):
            status = self.c.status()
        self.assertTrue(status["game_installed"])
        self.assertFalse(status["configuration_ready"])
        self.assertEqual(status["phase"], "game_configuration_required")
        with mock.patch.object(self.c, "processes", return_value=[]), mock.patch.object(self.c, "steam_command") as launch:
            with self.assertRaisesRegex(daoctl.DAOError, "Finish game setup"):
                self.c.play("47810")
        launch.assert_not_called()

    def test_supplied_native_subset_excludes_managed_and_64bit_cabs(self):
        game = self.game()
        files = game_setup.package_files(self.c, game)
        names = {p.name.casefold() for p in files}
        self.assertIn("nov2007_d3dx9_36_x86.cab", names)
        self.assertIn("aug2006_xact_x86.cab", names)
        self.assertFalse(any("mdx" in name or "x64" in name for name in names))

    def test_interactive_preparation_preserves_game_files_and_existing_ini(self):
        game = self.game()
        ini = game_setup.ini_path(self.c)
        ini.parent.mkdir(parents=True)
        original = b"[VideoOptions]\nResolutionWidth=1280\nResolutionHeight=800\nFullScreen=0\n[AudioOptions]\nMasterVolume=71\n"
        ini.write_bytes(original)
        source = Path(game["game_dir"])
        before = {str(p.relative_to(source)): p.read_bytes() for p in source.rglob("*") if p.is_file()}
        result, batch = self.launch_setup()
        self.assertTrue(result["ok"])
        self.assertNotIn("/silent", batch.lower())
        self.assertNotIn("/quiet", batch.lower())
        self.assertNotIn(" /q", batch.lower())
        self.assertNotIn("reg add", batch)
        self.assertIn("if errorlevel 1 goto failed", batch)
        self.assertIn("PREREQUISITES_COMPLETE", batch)
        self.assertEqual(ini.read_bytes(), original)
        self.assertEqual(before, {str(p.relative_to(source)): p.read_bytes() for p in source.rglob("*") if p.is_file()})

    def test_marker_and_actual_components_are_required_before_ready(self):
        game = self.game()
        _, batch = self.launch_setup()
        self.registry_call.assert_called_once_with({"retina": {"type": "REG_SZ", "value": "N"},
                                                   "dpi": {"type": "REG_DWORD", "value": 96}})
        self.assertFalse(game_setup.configuration_status(self.c, game)["ready"])
        self.marker()
        self.assertFalse(game_setup.configuration_status(self.c, game)["ready"])
        self.components()
        self.assertTrue(game_setup.configuration_status(self.c, game)["ready"])
        (Path(game["exe"])).write_bytes(pe32() + b"updated")
        self.assertFalse(game_setup.configuration_status(self.c, game)["ready"])

    def test_cancelled_installer_never_reports_configuration_ready(self):
        game = self.game()
        self.launch_setup()
        self.components()
        self.marker("INSTALLER_FAILED_1602")
        status = game_setup.configuration_status(self.c, game)
        self.assertFalse(status["ready"])
        self.assertIn("did not complete", status["message"])

    def test_existing_native_libraries_and_valid_configuration_are_recognized_read_only(self):
        game = self.game()
        self.components()
        ini = game_setup.ini_path(self.c)
        ini.parent.mkdir(parents=True)
        ini.write_text("[VideoOptions]\nResolutionWidth=1280\nResolutionHeight=800\nFullScreen=0\n")
        self.assertTrue(game_setup.configuration_status(self.c, game)["ready"])
        self.assertFalse(self.c.data.exists())

    def test_missing_or_escaped_source_is_rejected_before_any_installer(self):
        game = self.game()
        path = Path(game["game_dir"]) / "redist/DirectX/dxsetup.exe"
        outside = Path(self.temp.name) / "foreign.exe"
        outside.write_bytes(pe32())
        path.unlink()
        path.symlink_to(outside)
        with mock.patch.object(display_settings.DisplaySettings, "_guard"), \
                mock.patch.object(self.c, "run_batch") as batch:
            with self.assertRaises(game_setup.SetupError):
                game_setup.configure_game(self.c, "47810")
        batch.assert_not_called()
        self.assertFalse(self.c.data.exists())

    def test_installer_parent_guard_blocks_a_second_configuration_sequence(self):
        self.game()
        for name in ("PhysX_9.09.0408_SystemSoftware.exe", "DAUServiceSetup_Steam.exe"):
            with self.subTest(name=name), \
                    mock.patch.object(display_settings.DisplaySettings, "_processes", return_value=[(111, 1, "C:\\Game\\" + name)]), \
                    mock.patch.object(self.c, "run_batch") as batch:
                with self.assertRaises(ValueError):
                    game_setup.configure_game(self.c, "47810")
                batch.assert_not_called()

    def test_interactive_steam_installer_blocks_duplicate_setup(self):
        self.runtime()
        with mock.patch.object(display_settings.DisplaySettings, "_processes", return_value=[(111, 1, r"C:\dao-support\SteamSetup.exe")]), \
                mock.patch.object(self.c, "initialize") as initialize, \
                mock.patch.object(self.c, "download_steam") as download:
            with self.assertRaises(ValueError):
                self.c.setup()
        initialize.assert_not_called()
        download.assert_not_called()


if __name__ == "__main__":
    unittest.main()
