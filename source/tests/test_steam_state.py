import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from steam_state import _InvalidVDF, _parse_keyvalues, discover_games, find_steam


def quote(value):
    return '"' + str(value).replace('\\', '\\\\').replace('"', '\\"') + '"'


class SteamStateTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.prefix = self.root / "A prefix with spaces"
        self.steam = self.prefix / "drive_c" / "Program Files (x86)" / "Steam"
        self.steam.mkdir(parents=True)
        (self.steam / "steam.exe").write_bytes(b"fixture")

    def manifest(self, appid="47810", library=None, folder="Dragon Age Ultimate Edition",
                 flags=4, to_download=0, downloaded=0, exe=True, extra=None):
        library = library or self.steam
        steamapps = library / "steamapps"
        steamapps.mkdir(parents=True, exist_ok=True)
        data = {"appid": appid, "installdir": folder, "StateFlags": str(flags),
                "BytesToDownload": str(to_download), "BytesDownloaded": str(downloaded)}
        data.update(extra or {})
        manifest = steamapps / ("appmanifest_" + appid + ".acf")
        manifest.write_text('"AppState" {\n' + "\n".join(quote(k) + " " + quote(v)
                            for k, v in data.items()) + "\n}", encoding="utf-8")
        game_dir = steamapps / "common" / folder
        if exe:
            (game_dir / "bin_ship").mkdir(parents=True, exist_ok=True)
            (game_dir / "bin_ship" / "DAOrigins.exe").write_bytes(b"MZ fixture")
        return manifest, game_dir

    def libraryfolders(self, text):
        path = self.steam / "steamapps" / "libraryfolders.vdf"
        path.parent.mkdir(exist_ok=True)
        path.write_text(text, encoding="utf-8")

    def test_both_editions_and_running_install(self):
        self.manifest("17450", folder="Dragon Age Origins", flags=68)
        self.manifest("47810")
        games = discover_games(self.prefix)
        self.assertEqual([g["appid"] for g in games], ["17450", "47810"])
        self.assertTrue(all(g["complete"] for g in games))
        self.assertTrue(find_steam(self.prefix).samefile(self.steam / "steam.exe"))
        self.assertEqual(games[1]["title"], "Dragon Age: Origins - Ultimate Edition")

    def test_download_without_executable_is_reported_incomplete(self):
        self.manifest(flags=1048576 | 1024, to_download=1000, downloaded=300, exe=False)
        game = discover_games(self.prefix)[0]
        self.assertFalse(game["complete"])
        self.assertEqual(game["exe"], "")
        self.assertEqual((game["bytes_to_download"], game["bytes_downloaded"]), (1000, 300))

    def test_manifest_alone_is_not_complete(self):
        self.manifest(exe=False)
        self.assertFalse(discover_games(self.prefix)[0]["complete"])

    def test_all_update_states_and_unknown_flags_block_completeness(self):
        for flag in (1, 2, 8, 16, 32, 128, 256, 512, 1024, 2048, 4096,
                     65536, 131072, 262144, 524288, 1048576, 2097152, 4194304, 8388608,
                     1 << 30):
            with self.subTest(flag=flag):
                self.manifest(flags=4 | flag)
                self.assertFalse(discover_games(self.prefix)[0]["complete"])

    def test_pending_bytes_and_staging_block_completeness(self):
        self.manifest(to_download=10, downloaded=9)
        self.assertFalse(discover_games(self.prefix)[0]["complete"])
        self.manifest(to_download=10, downloaded=10, extra={"BytesToStage": "8", "BytesStaged": "7"})
        self.assertFalse(discover_games(self.prefix)[0]["complete"])
        self.manifest(to_download=10, downloaded=10, extra={"BytesToStage": "8", "BytesStaged": "8"})
        self.assertTrue(discover_games(self.prefix)[0]["complete"])

    def test_case_insensitive_paths_and_program_files_fallback(self):
        self.steam.rename(self.steam.with_name("sTeAm"))
        self.steam = self.steam.with_name("sTeAm")
        (self.steam / "steam.exe").rename(self.steam / "STEAM.EXE")
        _, game_dir = self.manifest()
        (game_dir / "bin_ship" / "DAOrigins.exe").rename(game_dir / "bin_ship" / "daorigins.EXE")
        (game_dir / "bin_ship").rename(game_dir / "BIN_SHIP")
        self.assertTrue(discover_games(self.prefix)[0]["complete"])
        fallback = self.prefix / "drive_c" / "Program Files" / "Steam"
        fallback.parent.mkdir()
        self.steam.rename(fallback)
        self.assertTrue(find_steam(self.prefix).samefile(fallback / "STEAM.EXE"))
        self.assertTrue(discover_games(self.prefix)[0]["complete"])

    def test_modern_libraryfolders_c_path_with_spaces_and_duplicates(self):
        library = self.prefix / "drive_c" / "Games With Spaces" / "Steam Library"
        self.manifest(library=library)
        value = quote(r"c:\Games With Spaces\Steam Library")
        self.libraryfolders('"libraryfolders" { "0" { "path" ' + value +
                            ' "apps" { "47810" "10" } } "1" { "path" ' + value + ' } }')
        games = discover_games(self.prefix)
        self.assertEqual(len(games), 1)
        self.assertTrue(games[0]["complete"])
        self.assertIn("Games With Spaces", games[0]["game_dir"])

    def test_legacy_libraryfolders_and_internal_drive_mapping(self):
        mapped = self.prefix / "game_disk"
        library = mapped / "Steam Library"
        self.manifest(library=library)
        (self.prefix / "dosdevices").mkdir()
        (self.prefix / "dosdevices" / "d:").symlink_to(mapped, target_is_directory=True)
        self.libraryfolders('"libraryfolders" { "1" ' + quote(r"D:\Steam Library") + ' }')
        self.assertTrue(discover_games(self.prefix)[0]["complete"])

    def test_invalid_manifest_syntax_is_ignored_without_losing_other_game(self):
        self.manifest("17450", folder="Dragon Age Origins")
        manifest, _ = self.manifest()
        for bad in ('"AppState" { "appid" "47810"', '"AppState" { "appid" }',
                    '"AppState" { "appid" "47810" "APPID" "17450" }',
                    '"AppState" { "appid" "47810\\', '/* never closed'):
            with self.subTest(bad=bad):
                manifest.write_text(bad, encoding="utf-8")
                self.assertEqual([g["appid"] for g in discover_games(self.prefix)], ["17450"])

    def test_invalid_manifest_numbers_and_mismatched_appid_are_ignored(self):
        for field, value in (("StateFlags", "invalid"), ("BytesDownloaded", "-1"),
                             ("BytesToDownload", "9" * 21), ("appid", "17450")):
            with self.subTest(field=field):
                self.manifest(extra={field: value})
                self.assertEqual(discover_games(self.prefix), [])

    def test_install_directory_traversal_absolute_and_windows_aliases_refused(self):
        for folder in ("../outside", r"..\outside", "/absolute", r"C:\outside",
                       "safe/../../outside", "safe/../outside", "safe/.. /outside", "safe."):
            with self.subTest(folder=folder):
                self.manifest(folder=folder, exe=False)
                self.assertEqual(discover_games(self.prefix), [])

    def test_external_and_traversing_library_paths_refused(self):
        external = self.root / "external"
        self.manifest(library=external)
        (self.prefix / "dosdevices").mkdir()
        (self.prefix / "dosdevices" / "d:").symlink_to(external, target_is_directory=True)
        (self.prefix / "dosdevices" / "z:").symlink_to("/", target_is_directory=True)
        for value in ("D:\\", r"C:\..\..\external", str(external),
                      r"\\server\share", "Z:" + str(external)):
            with self.subTest(value=value):
                self.libraryfolders('"libraryfolders" { "1" ' + quote(value) + ' }')
                self.assertEqual(discover_games(self.prefix), [])

    def test_symlink_escape_from_game_or_executable_refused(self):
        manifest, game_dir = self.manifest(exe=False)
        external = self.root / "external_game"
        (external / "bin_ship").mkdir(parents=True)
        (external / "bin_ship" / "DAOrigins.exe").write_bytes(b"fixture")
        game_dir.parent.mkdir(parents=True)
        game_dir.symlink_to(external, target_is_directory=True)
        self.assertEqual(discover_games(self.prefix), [])
        game_dir.unlink()
        (game_dir / "bin_ship").mkdir(parents=True)
        (game_dir / "bin_ship" / "DAOrigins.exe").symlink_to(external / "bin_ship" / "DAOrigins.exe")
        self.assertFalse(discover_games(self.prefix)[0]["complete"])

    def test_manifest_symlink_outside_prefix_refused(self):
        manifest, _ = self.manifest()
        outside = self.root / "external_manifest.acf"
        manifest.rename(outside)
        manifest.symlink_to(outside)
        self.assertEqual(discover_games(self.prefix), [])

    def test_missing_prefix_and_steam_are_safe(self):
        self.assertIsNone(find_steam(self.root / "missing"))
        self.assertEqual(discover_games(self.root / "missing"), [])
        (self.steam / "steam.exe").unlink()
        self.assertEqual(discover_games(self.prefix), [])


class KeyValuesTests(unittest.TestCase):
    def test_comments_quotes_braces_and_escapes(self):
        document = _parse_keyvalues('\ufeff// header\nroot {\n'
                                    'path "C:\\\\Games With Spaces\\\\Steam" /* note */\n'
                                    'description "quoted \\\"text\\\" { // literal }"\n'
                                    'unknown "\\Q"\n}\n// tail')
        self.assertEqual(document["root"]["path"], r"C:\Games With Spaces\Steam")
        self.assertEqual(document["root"]["description"], 'quoted "text" { // literal }')
        self.assertEqual(document["root"]["unknown"], r"\Q")

    def test_malformed_and_excessive_nesting_rejected(self):
        for text in ('}', '{ "a" "b" }', 'key', '"key" "unterminated',
                     '"a" "b" "A" "c"', '"a" "b\x00c"',
                     'a { ' * 70 + 'v "x" ' + '} ' * 70):
            with self.subTest(text=text[:40]):
                with self.assertRaises(_InvalidVDF):
                    _parse_keyvalues(text)


if __name__ == "__main__":
    unittest.main()
