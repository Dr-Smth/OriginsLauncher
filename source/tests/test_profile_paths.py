"""Actual-profile containment regressions; all host directories are temp fixtures."""
import json
from pathlib import Path
import plistlib
import shutil
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import daoctl
import display_settings
import game_setup
import profile_paths as profiles


class ProfileTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name).resolve()
        self.c = daoctl.Controller(self.base / "new app data")
        for file in (self.c.wine, self.c.wineserver, self.c.launcher):
            file.parent.mkdir(parents=True, exist_ok=True)
            file.write_bytes(b"fixture, never execute")
        (self.c.contents / "Info.plist").write_bytes(plistlib.dumps({"Symlinks In User Folder": 0}))
        self.c.prefix.mkdir(parents=True)
        (self.c.prefix / "system.reg").write_text("WINE REGISTRY Version 2\n")
        self.profile = self.c.prefix / "drive_c/users/testuser"
        self.profile.mkdir(parents=True)
        self.registry()
        self.host = self.base / "host Documents"
        self.host.mkdir()
        (self.host / "precious-save").write_bytes(b"preserve exactly")

    def registry(self, username="testuser", personal=None, expanded=None):
        profile = "C:\\users\\" + username
        personal = personal or profile + "\\Documents"
        expanded = expanded or "%USERPROFILE%\\Documents"
        text = "WINE REGISTRY Version 2\n\n[Volatile Environment]\n"
        text += '"USERPROFILE"=' + json.dumps(profile) + '\n"USERNAME"=' + json.dumps(username) + "\n"
        text += "\n[Software\\\\Microsoft\\\\Windows\\\\CurrentVersion\\\\Explorer\\\\Shell Folders]\n"
        text += '"Personal"=' + json.dumps(personal) + "\n"
        text += "\n[Software\\\\Microsoft\\\\Windows\\\\CurrentVersion\\\\Explorer\\\\User Shell Folders]\n"
        text += '"Personal"=str(2):' + json.dumps(expanded) + "\n"
        (self.c.prefix / "user.reg").write_text(text)

    def test_observed_testuser_profile_is_localized_without_touching_host_targets(self):
        for name in ("Documents", "Desktop", "Downloads", "Music", "Pictures", "Videos"):
            (self.profile / name).symlink_to(self.host)
        raw = (self.c.prefix / "user.reg").read_bytes()
        self.assertFalse(self.c.prefix_ready())
        with mock.patch.object(self.c, "launch_wss") as launch:
            self.c.initialize()
        launch.assert_not_called()  # Retry repairs an interrupted prefix; no reset.
        self.assertTrue(self.c.prefix_ready())
        self.assertEqual(self.c.documents, self.profile / "Documents")
        self.assertEqual((self.host / "precious-save").read_bytes(), b"preserve exactly")
        self.assertEqual(list(self.host.iterdir()), [self.host / "precious-save"])
        self.assertFalse((self.profile / "Documents").is_symlink())
        self.assertFalse((self.c.prefix / "drive_c/users/Sikarugir").exists())
        self.assertEqual((self.c.prefix / "user.reg").read_bytes(), raw)
        prefs = plistlib.loads((self.c.contents / "Info.plist").read_bytes())
        self.assertEqual(prefs["Symlink My Documents"], str(self.profile / "Documents"))

    def test_steam_and_batch_launch_refuse_external_documents_before_any_process(self):
        (self.profile / "Documents").symlink_to(self.host)
        with mock.patch.object(self.c, "require_platform"), mock.patch.object(self.c, "launch_wss") as launch:
            with self.assertRaisesRegex(daoctl.DAOError, "containment"):
                self.c.steam_command([], "steam")
            with self.assertRaisesRegex(daoctl.DAOError, "containment"):
                self.c.run_batch("anything", "echo must not execute")
        launch.assert_not_called()
        self.assertFalse(self.c.data.exists())

    def test_status_reports_repair_read_only_for_existing_registry_with_unsafe_profile(self):
        (self.profile / "Documents").symlink_to(self.host)
        with mock.patch.object(self.c, "processes", return_value=[]), \
                mock.patch.object(daoctl, "platform_status", return_value={"platform_supported": True, "rosetta_ready": True, "phase": "supported", "message": "fixture"}):
            status = self.c.status()
        self.assertEqual(status["phase"], "prefix_containment_required")
        self.assertFalse(status["prefix_ready"])
        self.assertTrue((self.profile / "Documents").is_symlink())
        self.assertFalse(self.c.data.exists())

    def test_disagreeing_registry_mappings_refuse_all_repairs(self):
        (self.profile / "Documents").symlink_to(self.host)
        self.registry(expanded=r"C:\users\testuser\Other")
        with self.assertRaisesRegex(profiles.ProfileError, "disagree"):
            self.c.contain_user_folders()
        self.assertTrue((self.profile / "Documents").is_symlink())
        self.assertEqual(list(self.host.iterdir()), [self.host / "precious-save"])

    def test_external_windows_drive_or_unknown_variable_never_falls_back_to_canonical(self):
        for path in (r"Z:\Users\testuser\Documents", r"%HOSTHOME%\Documents", r"C:\users\testuser\..\..\outside"):
            with self.subTest(path=path):
                self.registry(personal=path, expanded=path)
                with self.assertRaises(profiles.ProfileError):
                    self.c.contain_user_folders()
        self.assertFalse((self.c.prefix / "drive_c/users/Sikarugir").exists())

    def test_profile_and_drive_ancestor_escapes_preserve_external_tree(self):
        for parent in (self.profile, self.c.prefix / "drive_c"):
            with self.subTest(parent=parent):
                parked = parent.with_name(parent.name + "-parked")
                parent.rename(parked)
                parent.symlink_to(self.host)
                try:
                    with self.assertRaises(profiles.ProfileError):
                        self.c.contain_user_folders()
                    self.assertEqual(list(self.host.iterdir()), [self.host / "precious-save"])
                finally:
                    parent.unlink()
                    parked.rename(parent)

    def test_prefix_symlink_into_another_install_is_rejected_before_repair(self):
        parked = self.c.prefix.with_name("original-prefix")
        self.c.prefix.rename(parked)
        self.c.prefix.symlink_to(self.host)
        with self.assertRaisesRegex(daoctl.DAOError, "outside"):
            self.c.contain_user_folders()
        self.assertEqual(list(self.host.iterdir()), [self.host / "precious-save"])

    def test_preferences_symlink_is_rejected_before_replacing_documents_link(self):
        (self.profile / "Documents").symlink_to(self.host)
        prefs = self.c.contents / "Info.plist"
        prefs.unlink()
        foreign = self.host / "foreign.plist"
        original = plistlib.dumps({"Keep": "original"})
        foreign.write_bytes(original)
        prefs.symlink_to(foreign)
        with self.assertRaises(daoctl.DAOError):
            self.c.contain_user_folders()
        self.assertTrue((self.profile / "Documents").is_symlink())
        self.assertEqual(foreign.read_bytes(), original)

    def test_internal_profile_alias_is_supported_and_existing_save_is_preserved(self):
        real = self.profile.with_name("Sikarugir")
        self.profile.rename(real)
        self.profile.symlink_to(real.name)
        (real / "Documents").mkdir()
        save = real / "Documents/save.das"
        save.write_bytes(b"existing character")
        self.c.contain_user_folders()
        self.assertTrue(self.c.prefix_ready())
        self.assertEqual(save.read_bytes(), b"existing character")

    def test_canonical_legacy_fallback_requires_existing_user_not_a_new_guess(self):
        (self.c.prefix / "user.reg").write_text("WINE REGISTRY Version 2\n")
        with self.assertRaisesRegex(profiles.ProfileError, "unknown"):
            self.c.contain_user_folders()
        canonical = self.profile.with_name("Sikarugir")
        (canonical / "Documents").mkdir(parents=True)
        self.c.contain_user_folders()
        self.assertEqual(self.c.documents, canonical / "Documents")

    def test_incomplete_registry_is_not_ready_just_because_files_exist(self):
        (self.profile / "Documents").mkdir()
        for raw in ('partial registry', 'WINE REGISTRY Version 2\n[Volatile Environment\n',
                    'WINE REGISTRY Version 2\n[Volatile Environment]\n"USERPROFILE"=invalid\n'):
            with self.subTest(raw=raw):
                (self.c.prefix / "user.reg").write_text(raw)
                self.assertFalse(self.c.prefix_ready())
                with self.assertRaises(profiles.ProfileError):
                    self.c.contain_user_folders()

    def test_game_and_display_use_actual_documents_and_follow_later_profile_change(self):
        (self.profile / "Documents").mkdir()
        manager = display_settings.DisplaySettings(self.c)
        expected = self.profile / "Documents/BioWare/Dragon Age/Settings/DragonAge.ini"
        self.assertEqual(manager.ini, expected)
        self.assertEqual(game_setup.ini_path(self.c), expected)
        canonical = self.profile.with_name("Sikarugir")
        (canonical / "Documents").mkdir(parents=True)
        self.registry(username="Sikarugir")
        self.assertEqual(manager.ini, canonical / "Documents/BioWare/Dragon Age/Settings/DragonAge.ini")


if __name__ == "__main__":
    unittest.main()
