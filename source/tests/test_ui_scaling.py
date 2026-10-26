"""Optional-mod safety fixtures: no network, Wine, real game or user files."""
import configparser
import hashlib
import io
import json
from pathlib import Path
import re
import stat
import sys
import tempfile
import types
import unittest
from unittest import mock
import zipfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import display_settings as ds
import ui_scaling as ui


INI = b'''[HUD Scale]\nScale = 0.25\n[Borderless Windowed]\nEnabled = true\n[Fix Aspect Ratio]\nEnabled = true\n[Disable Pillarboxing]\nEnabled = true\n[Draw Distances]\nFoliage = 4\nNPC = 5\nObject = 6\n[Shadow Resolution]\nResolution = 4096\n'''


def archive(extra=None, missing=None):
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as z:
        for name, raw in {"DAFix.asi": b"MZ fixture mod", "DAFix.ini": INI,
                          "dinput8.dll": b"MZ fixture loader", "dinput8.ini": b"[GlobalSets]\nLoadPlugins=1\n"}.items():
            if name != missing:
                z.writestr("bin_ship/" + name, raw)
        z.writestr(ui.LOADER_LICENSE, b"Fixture loader license")
        if extra:
            z.writestr(extra[0], extra[1])
    return buffer.getvalue()


class Response(io.BytesIO):
    def __init__(self, raw, url):
        super().__init__(raw)
        self.url = url

    def geturl(self):
        return self.url


class ScalingTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name).resolve() / "Own Game"
        runtime = self.root / "runtime/DAO Runtime.app"
        contents = runtime / "Contents"
        prefix = contents / "SharedSupport/prefix"
        prefix.mkdir(parents=True)
        self.c = types.SimpleNamespace(root=self.root, runtime=runtime, contents=contents,
            prefix=prefix, data=self.root / "data", state=lambda: {"selected_appid": "47810"},
            run_batch=mock.Mock(side_effect=AssertionError("No real Wine in fixtures")), stop=mock.Mock())
        steam = prefix / "drive_c/Program Files (x86)/Steam"
        self.folder = steam / "steamapps/common/Dragon Age Ultimate Edition/bin_ship"
        self.folder.mkdir(parents=True)
        (steam / "steam.exe").write_bytes(b"MZ fixture Steam")
        self.exe = self.folder / "DAOrigins.exe"
        self.exe.write_bytes(b"MZ fixture game")
        (steam / "steamapps/appmanifest_47810.acf").write_text('"AppState" { "appid" "47810" "installdir" "Dragon Age Ultimate Edition" "StateFlags" "4" }')
        self.ini = prefix / "drive_c/users/Sikarugir/Documents/BioWare/Dragon Age/Settings/DragonAge.ini"
        self.ini.parent.mkdir(parents=True)
        self.ini.write_bytes(b"[VideoOptions]\nResolutionWidth=1280\nFullScreen=0\n")
        self.save = self.ini.parent.parent / "Characters/Fixture/Save1.das"
        self.save.parent.mkdir(parents=True)
        self.save.write_bytes(b"fixture save must remain untouched")
        self.registry(None)
        self.protected = {p: p.read_bytes() for p in (self.exe, self.ini, self.save)}
        self.receipt = self.c.data / "ui-scaling/47810-receipt.json"
        self.archive = archive()
        self.license = b"Fixture DAFix license"
        for name, value in (("ARCHIVE_SIZE", len(self.archive)), ("ARCHIVE_SHA256", ui._digest(self.archive)),
                            ("LICENSE_SIZE", len(self.license)), ("LICENSE_SHA256", ui._digest(self.license))):
            patch = mock.patch.object(ui, name, value)
            patch.start()
            self.addCleanup(patch.stop)
        self.open_mock = mock.Mock(side_effect=lambda request, timeout: Response(
            self.archive if request.full_url == ui.ARCHIVE_URL else self.license, request.full_url))
        patch = mock.patch.object(ui.urllib.request, "build_opener", return_value=types.SimpleNamespace(open=self.open_mock))
        patch.start()
        self.addCleanup(patch.stop)
        patch = mock.patch.object(ds.DisplaySettings, "_processes", return_value=[])
        self.process_mock = patch.start()
        self.addCleanup(patch.stop)
        patch = mock.patch.object(ds.DisplaySettings, "_stop_prefix")
        self.stop_mock = patch.start()
        self.addCleanup(patch.stop)
        patch = mock.patch.object(ui, "_write_override", side_effect=lambda settings, value: self.registry(value))
        self.registry_mock = patch.start()
        self.registry_patch = patch
        self.addCleanup(patch.stop)

    def registry(self, value):
        text = 'WINE REGISTRY Version 2\n\n[Unrelated] 123\n"Keep"="yes"\n\n'
        text += '[' + ui.DLL_SECTION.replace('\\', '\\\\') + '] 123\n'
        if value is not None:
            text += '"dinput8"="' + value + '"\n'
        (self.c.prefix / "user.reg").write_text(text)

    def assert_protected(self):
        self.assertEqual(self.protected, {p: p.read_bytes() for p in self.protected})

    def test_install_pinned_files_conservative_config_and_backup(self):
        original_reg = (self.c.prefix / "user.reg").read_bytes()
        result = ui.install_ui_scaling(self.c)
        self.assertTrue(result["ok"])
        self.assertFalse(result["already_installed"])
        self.assertEqual(self.open_mock.call_count, 2)
        self.assertEqual(set(p.name for p in self.folder.iterdir()), set(ui.FILES) | {"DAOrigins.exe"})
        config = configparser.ConfigParser()
        config.read(self.folder / "DAFix.ini")
        self.assertEqual(config.getfloat("HUD Scale", "Scale"), 1)
        for section in ("Borderless Windowed", "Fix Aspect Ratio", "Disable Pillarboxing"):
            self.assertFalse(config.getboolean(section, "Enabled"))
        for key in ("Foliage", "NPC", "Object"):
            self.assertEqual(config.getint("Draw Distances", key), 0)
        self.assertEqual(config.getint("Shadow Resolution", "Resolution"), 1024)
        record = json.loads(self.receipt.read_text())
        backup = self.root / record["backup"]
        self.assertEqual((backup / "user.reg").read_bytes(), original_reg)
        self.assertEqual((backup / "DAFix-LICENSE.md").read_bytes(), self.license)
        self.assertEqual((backup / ui.LOADER_LICENSE).read_bytes(), b"Fixture loader license")
        self.assertEqual(record["phase"], "installed")
        for name, expected in (("DAFix-LICENSE.md", self.license), (ui.LOADER_LICENSE, b"Fixture loader license")):
            stable = self.root / record["licenses"][name]["path"]
            self.assertEqual(stable.parent, self.c.data / "ui-scaling/licenses" / ui.VERSION)
            self.assertEqual(stable.read_bytes(), expected)
            self.assertEqual(ui._digest(expected), record["licenses"][name]["sha256"])
        self.assertEqual(record["original_files"], dict.fromkeys(ui.FILES))
        self.assertEqual(ui._registry(ds.DisplaySettings(self.c)), ui.OVERRIDE)
        self.assert_protected()

    def test_explicit_edition_overrides_state_selection(self):
        steamapps = self.folder.parents[2]
        base_bin = steamapps / "common/Dragon Age Original Edition/bin_ship"
        base_bin.mkdir(parents=True)
        (base_bin / "DAOrigins.exe").write_bytes(b"MZ original edition fixture")
        (steamapps / "appmanifest_17450.acf").write_text('"AppState" { "appid" "17450" "installdir" "Dragon Age Original Edition" "StateFlags" "4" }')
        ui.install_ui_scaling(self.c, "17450")
        self.assertTrue(all((base_bin / name).is_file() for name in ui.FILES))
        self.assertTrue(all(not (self.folder / name).exists() for name in ui.FILES))
        record = json.loads((self.c.data / "ui-scaling/17450-receipt.json").read_text())
        self.assertEqual(record["appid"], "17450")
        self.assertFalse(self.receipt.exists())

    def test_short_write_failure_removes_its_own_partial_file(self):
        settings = ds.DisplaySettings(self.c)
        target = self.folder / "DAFix.asi"
        with mock.patch.object(ui.os, "fsync", side_effect=OSError("fixture disk full")):
            with self.assertRaises(OSError):
                ui._exclusive_write(settings, target, b"MZ partially written fixture")
        self.assertFalse(target.exists())
        self.assert_protected()

    def test_idempotence_preserves_user_config_and_avoids_network_and_stop(self):
        ui.install_ui_scaling(self.c)
        (self.folder / "DAFix.ini").write_bytes(INI)
        (self.folder / "dinput8.ini").write_bytes(b"custom config")
        self.open_mock.reset_mock()
        self.stop_mock.reset_mock()
        result = ui.install_ui_scaling(self.c)
        self.assertTrue(result["already_installed"])
        self.assertEqual((self.folder / "DAFix.ini").read_bytes(), INI)
        self.assertEqual((self.folder / "dinput8.ini").read_bytes(), b"custom config")
        self.open_mock.assert_not_called()
        self.stop_mock.assert_not_called()

    def test_existing_unmanaged_or_partial_mods_are_never_overwritten(self):
        for name in ui.FILES:
            with self.subTest(name=name):
                target = self.folder / name
                target.write_bytes(b"user mod")
                with self.assertRaisesRegex(ds.DisplayError, "Existing or incomplete"):
                    ui.install_ui_scaling(self.c)
                self.assertEqual(target.read_bytes(), b"user mod")
                target.unlink()
        self.open_mock.assert_not_called()
        self.stop_mock.assert_not_called()
        self.assert_protected()

    def test_existing_binary_modified_after_managed_install_is_refused(self):
        ui.install_ui_scaling(self.c)
        (self.folder / "DAFix.asi").write_bytes(b"MZ different user mod")
        self.open_mock.reset_mock()
        with self.assertRaisesRegex(ds.DisplayError, "Existing or incomplete"):
            ui.install_ui_scaling(self.c)
        self.assertEqual((self.folder / "DAFix.asi").read_bytes(), b"MZ different user mod")
        self.open_mock.assert_not_called()

    def test_active_game_config_launcher_and_installer_refused_before_network(self):
        for image in ("DAOrigins.exe", "DAOriginsConfig.exe", "DAOriginsLauncher.exe", "DXSETUP.exe", "OtherSetup.exe"):
            self.process_mock.return_value = [(123, 1, '"C:\\Game\\' + image + '"')]
            with self.subTest(image=image), self.assertRaises(ds.DisplayError):
                ui.install_ui_scaling(self.c)
        self.open_mock.assert_not_called()
        self.assertFalse(self.receipt.exists())

    def test_process_inventory_failure_is_not_treated_as_idle(self):
        self.process_mock.side_effect = ds.DisplayError("Process visibility unavailable")
        with self.assertRaisesRegex(ds.DisplayError, "visibility"):
            ui.install_ui_scaling(self.c)
        self.open_mock.assert_not_called()

    def test_existing_mod_symlink_is_refused_without_following_it(self):
        elsewhere = self.root / "other-user-file"
        elsewhere.write_bytes(b"preserve")
        (self.folder / "DAFix.ini").symlink_to(elsewhere)
        with self.assertRaisesRegex(ds.DisplayError, "links"):
            ui.install_ui_scaling(self.c)
        self.assertEqual(elsewhere.read_bytes(), b"preserve")
        self.open_mock.assert_not_called()

    def test_game_outside_prefix_is_refused(self):
        outside = self.root / "elsewhere/DAOrigins.exe"
        outside.parent.mkdir()
        outside.write_bytes(b"MZ outside")
        self.exe.unlink()
        self.exe.symlink_to(outside)
        with self.assertRaises(ds.DisplayError):
            ui.install_ui_scaling(self.c)
        self.open_mock.assert_not_called()

    def test_conflicting_override_is_preserved_before_network(self):
        self.registry("builtin")
        original = (self.c.prefix / "user.reg").read_bytes()
        with self.assertRaisesRegex(ds.DisplayError, "different game-specific"):
            ui.install_ui_scaling(self.c)
        self.assertEqual((self.c.prefix / "user.reg").read_bytes(), original)
        self.open_mock.assert_not_called()

    def test_existing_compatible_override_needs_no_registry_write(self):
        self.registry(ui.OVERRIDE)
        ui.install_ui_scaling(self.c)
        self.registry_mock.assert_not_called()
        self.assert_protected()

    def test_wrong_download_digest_or_size_does_not_stop_or_install(self):
        for raw in (self.archive + b"x", self.archive[:-1], b"x" * len(self.archive)):
            self.open_mock.side_effect = lambda request, timeout, raw=raw: Response(raw, request.full_url)
            with self.subTest(length=len(raw)), self.assertRaisesRegex(ds.DisplayError, "pinned release"):
                ui.install_ui_scaling(self.c)
        self.stop_mock.assert_not_called()
        self.assertFalse(self.receipt.exists())
        self.assertEqual(list(self.folder.iterdir()), [self.exe])

    def test_redirects_are_https_and_official_host_only(self):
        for url in ("http://github.com/Lyall/DAFix", "https://example.org/archive", "https://github.com.evil.test/archive", "https://user:password@github.com/archive"):
            with self.subTest(url=url), self.assertRaises(ds.DisplayError):
                ui._check_url(url)
        handler = ui._PinnedRedirect()
        with self.assertRaises(ds.DisplayError):
            handler.redirect_request(None, None, 302, "Moved", {}, "http://example.org/archive")
        self.open_mock.side_effect = lambda request, timeout: Response(self.archive, "https://example.org/archive")
        with self.assertRaises(ds.DisplayError):
            ui.install_ui_scaling(self.c)
        self.stop_mock.assert_not_called()

    def test_archive_rejects_traversal_absolute_backslash_duplicate_and_links(self):
        candidates = [("../escape", b"bad"), ("/absolute", b"bad"), ("bin_ship\\escape", b"bad"), ("BIN_SHIP/DAFIX.ASI", b"bad")]
        link = zipfile.ZipInfo("bin_ship/link")
        link.create_system = 3
        link.external_attr = (stat.S_IFLNK | 0o777) << 16
        candidates.append((link, b"../../outside"))
        for extra in candidates:
            with self.subTest(extra=str(extra[0])), self.assertRaises(ds.DisplayError):
                ui._archive_files(archive(extra=extra))
        with self.assertRaises(ds.DisplayError):
            ui._archive_files(archive(missing="dinput8.ini"))
        self.assert_protected()

    def test_file_appearing_during_download_is_preserved(self):
        original_open = self.open_mock.side_effect
        def fetch(request, timeout):
            if request.full_url == ui.LICENSE_URL:
                (self.folder / "dinput8.dll").write_bytes(b"MZ user installation")
            return original_open(request, timeout)
        self.open_mock.side_effect = fetch
        with self.assertRaisesRegex(ds.DisplayError, "appeared during download"):
            ui.install_ui_scaling(self.c)
        self.assertEqual((self.folder / "dinput8.dll").read_bytes(), b"MZ user installation")
        self.assertFalse(self.receipt.exists())

    def test_registry_failure_rolls_back_only_new_files_and_override(self):
        calls = []
        def fail_after_write(settings, value):
            calls.append(value)
            self.registry(value)
            if value == ui.OVERRIDE:
                raise ds.DisplayError("simulated registry persistence failure")
        self.registry_mock.side_effect = fail_after_write
        with self.assertRaisesRegex(ds.DisplayError, "rolled back"):
            ui.install_ui_scaling(self.c)
        self.assertEqual(calls, [ui.OVERRIDE, None])
        self.assertEqual(list(self.folder.iterdir()), [self.exe])
        self.assertEqual(json.loads(self.receipt.read_text())["phase"], "rolled_back")
        self.assertIsNone(ui._registry(ds.DisplaySettings(self.c)))
        self.assert_protected()

    def test_partial_write_failure_removes_only_completed_new_files(self):
        real = ui._exclusive_write
        def failing(settings, path, raw, base=None):
            if path.name == "dinput8.dll":
                raise OSError("fixture disk error")
            real(settings, path, raw, base)
        with mock.patch.object(ui, "_exclusive_write", side_effect=failing), self.assertRaisesRegex(ds.DisplayError, "rolled back"):
            ui.install_ui_scaling(self.c)
        self.assertEqual(list(self.folder.iterdir()), [self.exe])
        self.assert_protected()

    def test_concurrent_mod_edit_is_preserved_and_marks_recovery_required(self):
        def fail_with_user_edit(settings, value):
            (self.folder / "DAFix.asi").write_bytes(b"MZ user edit during action")
            raise ds.DisplayError("simulated failure")
        self.registry_mock.side_effect = fail_with_user_edit
        with self.assertRaisesRegex(ds.DisplayError, "needs recovery"):
            ui.install_ui_scaling(self.c)
        self.assertEqual((self.folder / "DAFix.asi").read_bytes(), b"MZ user edit during action")
        self.assertEqual(json.loads(self.receipt.read_text())["phase"], "recovery_required")
        with self.assertRaisesRegex(ds.DisplayError, "earlier UI-scaling"):
            ui.install_ui_scaling(self.c)
        self.assert_protected()

    def test_invalid_or_interrupted_receipt_is_not_silently_replaced(self):
        self.receipt.parent.mkdir(parents=True)
        self.receipt.write_text("invalid")
        with self.assertRaisesRegex(ds.DisplayError, "receipt is invalid"):
            ui.install_ui_scaling(self.c)
        self.receipt.write_text(json.dumps({"schema_version": 1, "phase": "installing"}))
        with self.assertRaisesRegex(ds.DisplayError, "earlier UI-scaling"):
            ui.install_ui_scaling(self.c)
        self.open_mock.assert_not_called()

    def test_stable_licenses_survive_transaction_backup_removal(self):
        import shutil
        ui.install_ui_scaling(self.c)
        record = json.loads(self.receipt.read_text())
        shutil.rmtree(self.root / record["backup"])
        for license_record in record["licenses"].values():
            raw = (self.root / license_record["path"]).read_bytes()
            self.assertEqual(ui._digest(raw), license_record["sha256"])

    def test_existing_different_license_is_not_overwritten(self):
        license_path = self.c.data / "ui-scaling/licenses" / ui.VERSION / "DAFix-LICENSE.md"
        license_path.parent.mkdir(parents=True)
        license_path.write_bytes(b"preserve this existing notice")
        with self.assertRaisesRegex(ds.DisplayError, "license differs"):
            ui.install_ui_scaling(self.c)
        self.assertEqual(license_path.read_bytes(), b"preserve this existing notice")
        self.stop_mock.assert_not_called()
        self.assertFalse(self.receipt.exists())

    def test_receipt_symlink_is_refused_without_overwriting_target(self):
        target = self.root / "existing.json"
        target.write_text('{"schema_version": 1, "phase": "rolled_back"}')
        self.receipt.parent.mkdir(parents=True)
        self.receipt.symlink_to(target)
        with self.assertRaisesRegex(ds.DisplayError, "symbolic link"):
            ui.install_ui_scaling(self.c)
        self.assertEqual(target.read_text(), '{"schema_version": 1, "phase": "rolled_back"}')
        self.open_mock.assert_not_called()

    def test_registry_batch_uses_only_game_specific_key_and_checks_persistence(self):
        self.registry_patch.stop()
        settings = ds.DisplaySettings(self.c)
        def batch(name, body):
            self.assertEqual(name, "ui-scaling-registry")
            self.assertIn(ui.DLL_KEY, body)
            self.assertNotIn("RetinaMode", body)
            self.assertNotIn("LogPixels", body)
            self.assertNotIn("DAOrigins.exe\"", body)
            report_name = re.search(r'ui-scaling-registry-[0-9a-f]+\.txt', body).group()
            report = self.c.prefix / "drive_c/dao-support" / report_name
            report.parent.mkdir(parents=True, exist_ok=True)
            value = None if "reg delete" in body else ui.OVERRIDE
            report.write_text(("dinput8 REG_SZ native,builtin\n" if value else "missing\n") + "DAO_UI_SCALING_REGISTRY_COMPLETE\n")
            self.registry(value)
            return types.SimpleNamespace(poll=lambda: 0), self.c.data / "fixture.log"
        self.c.run_batch.side_effect = batch
        ui._write_override(settings, ui.OVERRIDE)
        self.assertEqual(ui._registry(settings), ui.OVERRIDE)
        ui._write_override(settings, None)
        self.assertIsNone(ui._registry(settings))
        self.assertEqual(self.stop_mock.call_count, 2)


if __name__ == "__main__":
    unittest.main()
