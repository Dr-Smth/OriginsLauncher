"""Display fixtures test safety and recovery without running Wine or changing screens."""
import ctypes
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import types
import unittest
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import display_settings as ds


def display(identifier="1", logical=(1496, 967), pixels=(2992, 1934), scale=2, main=True):
    return {"id": identifier, "name": "Fixture display " + identifier, "is_main": main, "builtin": identifier == "1",
            "logical_width": logical[0], "logical_height": logical[1], "pixel_width": pixels[0], "pixel_height": pixels[1],
            "scale": scale, "refresh_rate": 59.94, "available_pixel_width": pixels[0],
            "available_pixel_height": pixels[1] - int(24 * scale)}


class DisplayTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        root = Path(self.temp.name).resolve() / "DAO files"
        runtime = root / "runtime/DAO Runtime.app"
        contents = runtime / "Contents"
        prefix = contents / "SharedSupport/prefix"
        prefix.mkdir(parents=True)
        self.c = types.SimpleNamespace(root=root, runtime=runtime, contents=contents, prefix=prefix, data=root / "data",
                                       wineserver=contents / "wine/wineserver", state=lambda: {"selected_appid": "47810"},
                                       compatibility_verified=mock.Mock(return_value=True), stop=mock.Mock(),
                                       env=lambda: {"WINEPREFIX": str(prefix)}, run_batch=mock.Mock(side_effect=AssertionError("No real Wine operations in tests")))
        self.steam = prefix / "drive_c/Program Files (x86)/Steam"
        self.bin = self.steam / "steamapps/common/Dragon Age Ultimate Edition/bin_ship"
        self.bin.mkdir(parents=True)
        (self.steam / "steam.exe").write_bytes(b"fixture")
        (self.bin / "DAOrigins.exe").write_bytes(b"MZ fixture")
        (self.steam / "steamapps/appmanifest_47810.acf").write_text('"AppState" { "appid" "47810" "installdir" "Dragon Age Ultimate Edition" "StateFlags" "4" }')
        self.m = ds.DisplaySettings(self.c)
        self.m.ini.parent.mkdir(parents=True)
        self.m.ini.write_bytes(b'\xef\xbb\xbf[VideoOptions]\r\nResolutionWidth=2992\r\nResolutionHeight=1934\r\nFullScreen=1\r\nRefreshRate=60\r\nGraphicsDetailLevel=3\r\nTexturePack=2\r\n[AudioOptions]\r\nMasterVolume=90\r\n')
        for name in ("DAFix.asi", "dinput8.dll"):
            (self.bin / name).write_bytes(b"fixture " + name.encode())
        (self.bin / "DAFix.ini").write_text("[HUD Scale]\nScale = 0.5\n[Shadow Resolution]\nResolution = 1024\n[Borderless Windowed]\nEnabled = false\n")
        self.registry({"retina": {"type": "REG_SZ", "value": "Y"}, "dpi": {"type": "REG_DWORD", "value": 96}})
        self.main = display()
        self.probe = mock.patch.object(self.m, "_probe", side_effect=lambda: dict(self.main))
        self.probe_mock = self.probe.start()
        self.addCleanup(self.probe.stop)
        self.processes = mock.patch.object(self.m, "_processes", return_value=[])
        self.processes_mock = self.processes.start()
        self.addCleanup(self.processes.stop)
        self.write_registry = mock.patch.object(self.m, "_write_registry", side_effect=self.registry)
        self.write_registry_mock = self.write_registry.start()
        self.addCleanup(self.write_registry.stop)

    def registry(self, values):
        text = 'WINE REGISTRY Version 2\n\n[Software\\\\Wine\\\\Mac Driver]\n'
        if values["retina"] is not None:
            text += '"RetinaMode"="' + values["retina"]["value"] + '"\n'
        text += '\n[Control Panel\\\\Desktop]\n'
        if values["dpi"] is not None:
            text += '"LogPixels"=dword:' + format(values["dpi"]["value"], '08x') + '\n'
        text += '\n[Unrelated Settings]\n"Keep"="unchanged"\n'
        (self.c.prefix / "user.reg").write_text(text)

    def tree(self):
        return {str(p.relative_to(self.c.root)): p.read_bytes() for p in self.c.root.rglob("*") if p.is_file()}

    def test_options_read_only_catalog_fits_and_keeps_legacy_mode(self):
        before = self.tree()
        options = self.m.options()
        self.assertEqual(before, self.tree())
        self.assertFalse(self.c.data.exists())
        self.c.compatibility_verified.assert_not_called()
        catalog = {p["id"]: p for p in options["presets"]}
        self.assertEqual(catalog["fullscreen-retina"]["hud_scale"], 0.5)
        self.assertTrue(catalog["windowed-1280x800"]["available"])
        self.assertFalse(catalog["windowed-1280x800"]["retina"])
        self.assertEqual(catalog["windowed-1280x800"]["hud_scale"], 1)
        self.assertTrue(catalog["windowed-2560x1600"]["retina"])
        self.assertTrue(catalog["windowed-2560x1600"]["available"])
        self.assertFalse(catalog["windowed-5120x2880"]["available"])
        self.assertTrue(all(p["verification"] == "first_run_check" for p in catalog.values()))

    def test_external_1x_main_has_one_fullscreen_and_no_arbitrary_exclusive_modes(self):
        self.main = display("external", (1920, 1080), (1920, 1080), 1)
        presets = self.m.options()["presets"]
        fullscreen = [p for p in presets if p["fullscreen"]]
        self.assertEqual([(p["width"], p["height"], p["retina"]) for p in fullscreen], [(1920, 1080, False)])
        self.assertFalse(next(p for p in presets if p["id"] == "windowed-1920x1080")["available"])

    def test_probe_uses_explicit_main_id_not_first_display_or_mouse_window(self):
        self.probe.stop()
        helper = self.c.root / "source/display-probe"
        helper.parent.mkdir()
        helper.write_bytes(b"fixture")
        helper.chmod(0o700)
        external = display("external", (1920, 1080), (1920, 1080), 1)
        inventory = {"schema_version": 1, "main_display_id": "external", "displays": [display(main=False), external]}
        with mock.patch.object(ds.subprocess, "run", return_value=subprocess.CompletedProcess([], 0, json.dumps(inventory), "")):
            self.assertEqual(self.m._probe()["id"], "external")
        inventory["main_display_id"] = "missing"
        with mock.patch.object(ds.subprocess, "run", return_value=subprocess.CompletedProcess([], 0, json.dumps(inventory), "")):
            with self.assertRaises(ds.DisplayError):
                self.m._probe()

    def test_non_exact_retina_geometry_never_offers_retina_fullscreen(self):
        self.main = display(logical=(1496, 967), pixels=(3000, 2000), scale=2)
        self.assertNotIn("fullscreen-retina", [p["id"] for p in self.m.options()["presets"]])

    def test_missing_mod_disables_ui_scaled_modes_without_downloading(self):
        (self.bin / "DAFix.asi").unlink()
        catalog = {p["id"]: p for p in self.m.options()["presets"]}
        self.assertFalse(catalog["fullscreen-retina"]["available"])
        self.assertIn("DAFix", catalog["fullscreen-retina"]["reason"])
        self.assertTrue(catalog["windowed-1280x800"]["available"])
        with self.assertRaises(ds.DisplayError):
            self.m.apply("fullscreen-retina")
        with self.assertRaises(ds.DisplayError):
            self.m.apply("windowed-1280x800", "larger")
        self.assertFalse(self.c.data.exists())

    def test_larger_ui_is_clamped_to_usable_1024_by_768_coordinates(self):
        catalog = {p["id"]: p for p in self.m._catalog(self.main, True, "larger")}
        self.assertAlmostEqual(catalog["windowed-1280x800"]["hud_scale"], 0.96)
        self.assertEqual(catalog["windowed-1280x720"]["hud_scale"], 1)
        self.assertAlmostEqual(catalog["fullscreen-retina"]["hud_scale"], 0.4)

    def test_apply_is_guarded_for_game_config_launcher_and_installers(self):
        for name in ("DAOrigins.exe", "DAOriginsConfig.exe", "DAOriginsLauncher.exe", "msiexec.exe", "PhysX_Setup.exe"):
            with self.subTest(name=name):
                self.processes_mock.return_value = [(100, 1, "C:\\Game\\" + name)]
                self.assertFalse(self.m.options()["can_apply"])
                with self.assertRaises(ds.DisplayError):
                    self.m.apply("fullscreen")
        self.assertFalse(self.c.data.exists())
        self.c.stop.assert_not_called()
        self.write_registry_mock.assert_not_called()

    def test_ultimate_addins_update_cannot_be_interrupted_by_display_or_prefix_stop(self):
        before = self.tree()
        # This actual Steam first-run helper does not contain setup/install or
        # vcredist in its name, and its path includes spaces.
        for command in (
                r'C:\Program Files (x86)\Steam\steamapps\common\Dragon Age Ultimate Edition\redist\DAOU_UpdateAddinsXML_Steam.exe',
                r'"C:\Program Files (x86)\Steam\steamapps\common\Dragon Age Ultimate Edition\redist\DAOU_UpdateAddinsXML_Steam.exe" /silent'):
            with self.subTest(command=command):
                self.processes_mock.return_value = [(100, 1, command)]
                self.assertFalse(self.m.options()["can_apply"])
                with self.assertRaises(ds.DisplayError):
                    self.m.apply("fullscreen")
                with self.assertRaises(ds.DisplayError):
                    self.m._stop_prefix()
        self.assertEqual(before, self.tree())
        self.c.stop.assert_not_called()
        self.write_registry_mock.assert_not_called()
        self.c.run_batch.assert_not_called()

    def test_empty_or_unparseable_successful_ps_is_not_an_idle_session(self):
        self.processes.stop()
        for output in ("", "unexpected process output\n"):
            with self.subTest(output=output), \
                    mock.patch.object(ds.subprocess, "run", return_value=subprocess.CompletedProcess([], 0, output, "")), \
                    mock.patch.object(ds.ctypes, "CDLL") as library:
                with self.assertRaisesRegex(ds.DisplayError, "visibility"):
                    self.m._processes()
                library.assert_not_called()

    def test_missing_process_visibility_is_not_treated_as_an_idle_session(self):
        self.processes.stop()
        with mock.patch.object(ds.subprocess, "run", return_value=subprocess.CompletedProcess([], 1, "", "")):
            self.assertFalse(self.m.options()["can_apply"])
            with self.assertRaises(ds.DisplayError):
                self.m.apply("fullscreen")
        self.assertFalse(self.c.data.exists())

    def test_apply_and_restore_preserve_unrelated_graphics_audio_and_mod_settings(self):
        self.m.apply("fullscreen")
        current = self.m.options()["current"]
        self.assertEqual((current["width"], current["height"], current["retina"], current["dpi"], current["hud_scale"]), (1496, 967, False, 96, 1))
        self.assertTrue(self.m.options()["pending_confirmation"])
        self.assertIn(b"GraphicsDetailLevel=3", self.m.ini.read_bytes())
        self.m.ini.write_bytes(self.m.ini.read_bytes().replace(b"GraphicsDetailLevel=3", b"GraphicsDetailLevel=2").replace(b"MasterVolume=90", b"MasterVolume=75"))
        mod = self.bin / "DAFix.ini"
        mod.write_text(mod.read_text().replace("Resolution = 1024", "Resolution = 2048"))
        self.m.restore()
        current = self.m.options()["current"]
        self.assertEqual((current["width"], current["height"], current["retina"], current["hud_scale"]), (2992, 1934, True, 0.5))
        self.assertIn(b"GraphicsDetailLevel=2", self.m.ini.read_bytes())
        self.assertIn(b"MasterVolume=75", self.m.ini.read_bytes())
        self.assertIn("Resolution = 2048", mod.read_text())
        self.assertTrue(self.m.ini.read_bytes().startswith(b"\xef\xbb\xbf"))
        self.assertIn(b"\r\n", self.m.ini.read_bytes())
        self.c.run_batch.assert_not_called()

    def test_unconfirmed_reapply_keeps_original_restore_point_and_keep_replaces_it(self):
        self.m.apply("fullscreen")
        first = self.m._state()["working_snapshot"]
        self.m.apply("windowed-1280x800")
        self.assertEqual(self.m._state()["working_snapshot"], first)
        self.m.confirm()
        self.assertNotEqual(self.m._state()["working_snapshot"], first)
        self.assertFalse(self.m.options()["pending_confirmation"])
        self.m.ini.write_bytes(self.m.ini.read_bytes().replace(b"ResolutionWidth=1280", b"ResolutionWidth=1400"))
        self.m.restore()
        self.assertEqual(self.m.options()["current"]["width"], 1280)

    def test_keep_allows_running_game_but_requires_matching_candidate_and_display(self):
        self.m.apply("fullscreen")
        self.processes_mock.return_value = [(100, 1, "DAOrigins.exe")]
        self.m.confirm()
        self.assertFalse(self.m._state()["pending_confirmation"])
        with self.assertRaises(ds.DisplayError):
            self.m.restore()
        self.processes_mock.return_value = []
        self.m.apply("windowed-1280x800")
        self.main = display("external", (1920, 1080), (1920, 1080), 1)
        with self.assertRaises(ds.DisplayError):
            self.m.confirm()
        self.main = display()
        (self.bin / "DAOrigins.exe").write_bytes(b"updated game")
        with self.assertRaises(ds.DisplayError):
            self.m.confirm()

    def test_seed_requires_existing_human_validation_and_labels_only_same_pipeline_display(self):
        self.c.compatibility_verified.return_value = False
        with self.assertRaises(ds.DisplayError):
            self.m.confirm()
        self.assertFalse(self.c.data.exists())
        self.c.compatibility_verified.return_value = True
        self.m.confirm()
        options = self.m.options()
        sharp = next(p for p in options["presets"] if p["id"] == "fullscreen-retina")
        self.assertEqual(sharp["verification"], "previously_tested_on_this_mac")
        self.main = display("another", (1496, 967), (2992, 1934), 2)
        self.assertTrue(all(p["verification"] == "first_run_check" for p in self.m.options()["presets"]))
        self.main = display()
        (self.bin / "DAFix.asi").write_bytes(b"changed mod")
        self.assertTrue(all(p["verification"] == "first_run_check" for p in self.m.options()["presets"]))

    def test_failure_rolls_back_and_keeps_actionable_journal(self):
        original = self.m._current(self.m._game())
        real_write = self.m._write_settings
        calls = []
        def fail_once(*args, **kwargs):
            calls.append(1)
            if len(calls) == 1:
                raise OSError("simulated disk failure")
            return real_write(*args, **kwargs)
        with mock.patch.object(self.m, "_write_settings", side_effect=fail_once):
            with self.assertRaisesRegex(ds.DisplayError, "Previous settings were restored"):
                self.m.apply("fullscreen")
        self.assertEqual(self.m._current(self.m._game()), original)
        state = self.m._state()
        self.assertFalse(state["recovery_required"])
        self.assertEqual(state["transaction"]["phase"], "failed_rolled_back")
        self.assertTrue((self.m.backups / state["working_snapshot"] / "DragonAge.ini").is_file())

    def test_failed_rollback_and_interrupted_transaction_refuse_further_apply(self):
        self.write_registry_mock.side_effect = OSError("registry unavailable")
        with self.assertRaisesRegex(ds.DisplayError, "recovery is still required"):
            self.m.apply("fullscreen")
        self.assertTrue(self.m._state()["recovery_required"])
        self.assertFalse(self.m.options()["can_apply"])
        self.write_registry_mock.side_effect = self.registry
        self.m.restore()
        state = self.m._state()
        state["transaction"]["phase"] = "changing"
        self.m._json(self.m.state_path, state)
        with self.assertRaises(ds.DisplayError):
            self.m.apply("fullscreen")

    def test_registry_absence_is_restored_individually_without_replacing_user_registry(self):
        self.registry({"retina": None, "dpi": None})
        # An absent Retina registry value uses logical display coordinates.
        raw = self.m.ini.read_bytes().replace(b"2992", b"1496").replace(b"1934", b"967")
        self.m.ini.write_bytes(raw)
        self.m.apply("fullscreen")
        self.m.restore()
        self.assertEqual(self.m._registry(), {"retina": None, "dpi": None})
        self.assertIn('"Keep"="unchanged"', (self.c.prefix / "user.reg").read_text())

    def test_external_symlinks_are_refused_before_settings_or_backups_are_written(self):
        outside = Path(self.temp.name) / "outside.ini"
        raw = self.m.ini.read_bytes()
        outside.write_bytes(raw)
        self.m.ini.unlink()
        self.m.ini.symlink_to(outside)
        with self.assertRaises(ds.DisplayError):
            self.m.apply("fullscreen")
        self.assertEqual(outside.read_bytes(), raw)
        self.write_registry_mock.assert_not_called()

    def test_backup_reference_traversal_is_refused(self):
        self.m._json(self.m.state_path, {"schema_version": 1, "pending_confirmation": True,
                                       "recovery_required": False, "working_snapshot": "../../outside"})
        with self.assertRaises(ds.DisplayError):
            self.m.restore()

    def test_display_change_after_closing_session_refuses_writes(self):
        before = self.m.ini.read_bytes()
        self.probe_mock.side_effect = [display(), display("external", (1920, 1080), (1920, 1080), 1)]
        with self.assertRaisesRegex(ds.DisplayError, "main display changed"):
            self.m.apply("fullscreen")
        self.assertEqual(self.m.ini.read_bytes(), before)
        self.write_registry_mock.assert_not_called()

    def test_display_change_during_registry_operation_rolls_back(self):
        before = self.m._current(self.m._game())
        self.probe_mock.side_effect = [display(), display(), display("external", (1920, 1080), (1920, 1080), 1)]
        with self.assertRaisesRegex(ds.DisplayError, "Previous settings were restored"):
            self.m.apply("fullscreen")
        self.assertEqual(self.m._current(self.m._game()), before)

    def test_recovery_allows_restore_but_not_apply_or_keep_and_bad_candidate_is_safe(self):
        self.m.apply("fullscreen")
        state = self.m._state()
        state["recovery_required"] = True
        self.m._json(self.m.state_path, state)
        options = self.m.options()
        self.assertFalse(options["can_apply"])
        self.assertFalse(options["can_confirm"])
        self.assertTrue(options["can_restore"])
        state.update(recovery_required=False, candidate=["corrupt"])
        self.m._json(self.m.state_path, state)
        self.assertFalse(self.m.options()["can_confirm"])

    def test_normal_modes_disable_borderless_and_restore_preserves_original_flag(self):
        mod = self.bin / "DAFix.ini"
        mod.write_text(mod.read_text().replace("Enabled = false", "Enabled = true"))
        self.assertEqual(self.m._current(self.m._game())["mode"], "borderless")
        self.m.apply("fullscreen")
        self.assertFalse(self.m._current(self.m._game())["borderless"])
        self.assertFalse(any(p["borderless"] for p in self.m.options()["presets"]))
        self.m.restore()
        self.assertTrue(self.m._current(self.m._game())["borderless"])
        self.assertIn("Resolution = 1024", mod.read_text())

    def test_strict_process_inventory_attributes_actual_runtime_not_arguments(self):
        self.processes.stop()
        own = self.c.contents / "SharedSupport/wine/lib/wine/x86_64-unix/wine"
        external = self.c.root.parent / "another-runtime/wine"
        rows = "101 1 C:\\Game\\DAOrigins.exe\n102 1 C:\\Other\\DAOrigins.exe\n103 101 nested-helper\n104 1 python3 inspect.py " + str(self.c.runtime) + "\n"
        paths = {101: own, 102: external, 104: Path("/usr/bin/python3")}
        def pidpath(pid, buffer, size):
            buffer.value = os.fsencode(paths[pid])
            return len(buffer.value)
        library = mock.Mock()
        library.proc_pidpath.side_effect = pidpath
        with mock.patch.object(ds.subprocess, "run", return_value=subprocess.CompletedProcess([], 0, rows, "")), \
                mock.patch.object(ds.ctypes, "CDLL", return_value=library):
            self.assertEqual([row[0] for row in self.m._processes()], [101, 103])

    def test_session_stop_is_prefix_scoped_and_ignores_independent_configure(self):
        configure = str(self.c.contents / "Configure.app/Contents/MacOS/Configure")
        self.processes_mock.side_effect = [[(101, 1, "steam.exe"), (102, 1, configure)], [(102, 1, configure)]]
        with mock.patch.object(ds.subprocess, "run", return_value=subprocess.CompletedProcess([], 0, "", "")) as run:
            self.m._stop_prefix()
        self.c.stop.assert_called_once()
        self.assertEqual(run.call_args.args[0], [str(self.c.wineserver), "-w"])
        self.assertEqual(run.call_args.kwargs["env"]["WINEPREFIX"], str(self.c.prefix))
        self.assertEqual(run.call_args.kwargs["timeout"], 20)

    def test_registry_marker_and_persisted_values_are_both_required(self):
        self.write_registry.stop()
        desired = {"retina": {"type": "REG_SZ", "value": "N"}, "dpi": {"type": "REG_DWORD", "value": 96}}
        def batch(name, body):
            report_name = __import__('re').search(r'display-registry-[a-f0-9]+\.txt', body).group(0)
            path = self.c.prefix / "drive_c/dao-support" / report_name
            path.parent.mkdir(exist_ok=True)
            path.write_text("RetinaMode REG_SZ N\nLogPixels REG_DWORD 0x60\nDAO_DISPLAY_REGISTRY_COMPLETE\n")
            self.registry(desired)
            return mock.Mock(poll=lambda: 0), self.c.root / "fixture.log"
        self.c.run_batch.side_effect = batch
        self.m._write_registry(desired)
        body = self.c.run_batch.call_args[0][1]
        self.assertIn('reg add "HKCU\\Software\\Wine\\Mac Driver" /v RetinaMode /t REG_SZ /d N /f', body)
        self.assertNotIn("reg import", body)
        self.assertNotIn("dinput8", body)
        def mismatch(*args):
            result = batch(*args)
            self.registry({"retina": {"type": "REG_SZ", "value": "Y"}, "dpi": desired["dpi"]})
            return result
        self.c.run_batch.side_effect = mismatch
        with self.assertRaisesRegex(ds.DisplayError, "persist"):
            self.m._write_registry(desired)

    def test_automatic_dafix_scale_zero_is_read_snapshotted_and_restored(self):
        mod = self.bin / "DAFix.ini"
        mod.write_text(mod.read_text().replace("Scale = 0.5", "Scale = 0"))
        self.assertEqual(self.m.options()["current"]["hud_scale"], 0)
        self.m.apply("fullscreen")
        self.assertEqual(self.m.options()["current"]["hud_scale"], 1)
        self.m.restore()
        self.assertEqual(self.m.options()["current"]["hud_scale"], 0)

    def test_fullscreen_restore_refuses_different_display_or_refresh_without_blocking_apply(self):
        self.m.confirm()
        self.main = display("external", (1920, 1080), (1920, 1080), 1)
        options = self.m.options()
        self.assertFalse(options["can_restore"])
        self.assertTrue(options["can_apply"])
        self.assertTrue(options["restore_blocked_reason"])
        before = self.m.state_path.read_bytes()
        with self.assertRaises(ds.DisplayError):
            self.m.restore()
        self.assertEqual(self.m.state_path.read_bytes(), before)
        self.main = display()
        self.main["refresh_rate"] = 120
        self.assertFalse(self.m.options()["can_restore"])
        with self.assertRaises(ds.DisplayError):
            self.m.restore()

    def test_fullscreen_snapshot_with_wrong_dimensions_is_not_restored(self):
        self.m.ini.write_bytes(self.m.ini.read_bytes().replace(b"ResolutionWidth=2992", b"ResolutionWidth=1920"))
        self.m.confirm()
        self.assertFalse(self.m.options()["can_restore"])
        with self.assertRaisesRegex(ds.DisplayError, "dimensions"):
            self.m.restore()

    def test_windowed_restore_requires_fit_but_not_identical_display(self):
        self.m.apply("windowed-1280x800")
        self.m.confirm()
        self.main = display("large external", (1920, 1080), (1920, 1080), 1)
        self.assertTrue(self.m.options()["can_restore"])
        self.m.restore()
        self.main = display("small external", (1024, 768), (1024, 768), 1)
        options = self.m.options()
        self.assertFalse(options["can_restore"])
        self.assertTrue(options["can_apply"])
        with self.assertRaisesRegex(ds.DisplayError, "no longer fits"):
            self.m.restore()

    def test_prepare_unchanged_keeps_live_session_and_ini_refresh_without_writes(self):
        self.main["refresh_rate"] = 120
        before = self.tree()
        result = self.m.prepare_for_play("fullscreen-retina")
        self.assertTrue(result["ok"])
        self.assertFalse(result["changed"])
        self.assertEqual(before, self.tree())
        self.assertEqual(self.m._current(self.m._game())["refresh_rate"], 60)
        self.c.stop.assert_not_called()
        self.write_registry_mock.assert_not_called()
        self.c.compatibility_verified.assert_not_called()

    def test_prepare_reuses_confirmed_settings_without_new_confirmation(self):
        self.main["refresh_rate"] = 120
        self.m.confirm()
        confirmed = self.m._state()
        self.m.prepare_for_play("fullscreen")
        self.assertTrue(self.m._state()["pending_confirmation"])
        self.c.compatibility_verified.reset_mock()
        with mock.patch.object(self.m, "confirm", side_effect=AssertionError("No automatic confirmation")):
            result = self.m.prepare_for_play("fullscreen-retina")
        self.assertTrue(result["changed"])
        state = self.m._state()
        self.assertFalse(state["pending_confirmation"])
        self.assertEqual(state["working_snapshot"], confirmed["working_snapshot"])
        self.assertEqual(state["confirmed_at"], confirmed["confirmed_at"])
        self.assertEqual(self.m._current(self.m._game())["refresh_rate"], 60)
        self.c.compatibility_verified.assert_not_called()

    def test_prepare_new_selection_does_not_claim_validation(self):
        self.main["refresh_rate"] = 120
        result = self.m.prepare_for_play("fullscreen")
        self.assertTrue(result["changed"])
        state = self.m._state()
        self.assertTrue(state["pending_confirmation"])
        self.assertNotIn("confirmation_source", state)
        self.assertEqual(state["candidate"]["preset_id"], "fullscreen")
        self.assertEqual(self.m._current(self.m._game())["refresh_rate"], 120)
        before = self.tree()
        self.assertFalse(self.m.prepare_for_play("fullscreen")["changed"])
        self.assertEqual(before, self.tree())
        self.assertTrue(self.m._state()["pending_confirmation"])
        self.c.compatibility_verified.assert_not_called()

    def test_prepare_validates_fresh_catalog_and_guard_before_any_changes(self):
        before = self.tree()
        for preset, ui_size in (("not-a-preset", "comfortable"), ("windowed-5120x2880", "comfortable"),
                                ("fullscreen", "not-a-size")):
            with self.subTest(preset=preset, ui_size=ui_size), self.assertRaises(ds.DisplayError):
                self.m.prepare_for_play(preset, ui_size)
        self.processes_mock.return_value = [(100, 1, "DAOrigins.exe")]
        with self.assertRaises(ds.DisplayError):
            self.m.prepare_for_play("fullscreen-retina")
        self.assertEqual(before, self.tree())
        self.c.stop.assert_not_called()
        self.write_registry_mock.assert_not_called()

    def test_prepare_unchanged_cannot_bypass_an_unresolved_recovery_record(self):
        self.m.prepare_for_play("fullscreen")
        state = self.m._state()
        state["recovery_required"] = True
        self.m._json(self.m.state_path, state)
        before = self.tree()
        with self.assertRaisesRegex(ds.DisplayError, "recover"):
            self.m.prepare_for_play("fullscreen")
        self.assertEqual(before, self.tree())

    def test_prepare_never_reuses_confirmation_after_pipeline_or_display_change(self):
        for changed in ("display", "exe", "mod", "source"):
            with self.subTest(changed=changed):
                self.m.confirm()
                self.m.prepare_for_play("fullscreen")
                if changed == "display":
                    self.main["refresh_rate"] += 1
                elif changed == "exe":
                    (self.bin / "DAOrigins.exe").write_bytes(b"changed game")
                elif changed == "mod":
                    (self.bin / "DAFix.asi").write_bytes(b"changed mod")
                else:
                    state = self.m._state()
                    state.pop("confirmation_source")
                    self.m._json(self.m.state_path, state)
                self.m.prepare_for_play("fullscreen-retina")
                self.assertTrue(self.m._state()["pending_confirmation"])
                self.assertEqual(self.m._state()["transaction"]["action"], "apply")

    def test_explicit_game_edition_never_falls_back_to_another_installed_edition(self):
        other = dict(self.m._game(), appid="17450")
        with mock.patch.object(ds, "discover_games", return_value=[self.m._game(), other]):
            self.assertEqual(ds.DisplaySettings(self.c, appid="17450")._game()["appid"], "17450")
        with self.assertRaises(ds.DisplayError):
            ds.DisplaySettings(self.c, appid="17450")._game()
        self.assertEqual(ds.DisplaySettings(self.c)._game()["appid"], "47810")


if __name__ == "__main__":
    unittest.main()
