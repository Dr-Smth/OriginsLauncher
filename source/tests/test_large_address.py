"""Native-file safety/recovery fixtures; no real Wine, signing or user files."""
import ctypes
import hashlib
import json
import os
from pathlib import Path
import stat
import struct
import subprocess
import sys
import tempfile
import types
import unittest
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import large_address as laa


def fixture_native():
    raw = bytearray(2368)
    struct.pack_into("<IIIIIIII", raw, 0, 0xfeedfacf, 0x01000007, 3, 6, 3, 240, 0, 0)
    # __TEXT with one __text section; room after the last section for the stub.
    struct.pack_into("<II16sQQQQiiII", raw, 32, 0x19, 152, b"__TEXT", 0, 2048, 0, 2048, 5, 5, 1, 0)
    struct.pack_into("<16s16sQQIIIIIIII", raw, 104, b"__text", b"__TEXT", 512, 128, 512, 4, 0, 0, 0x80000400, 0, 0, 0)
    struct.pack_into("<II16sQQQQiiII", raw, 184, 0x19, 72, b"__LINKEDIT", 2048, 4096, 2048, 320, 1, 1, 0, 0)
    struct.pack_into("<IIII", raw, 256, 0x1d, 16, 2304, 64)
    raw[512:521] = laa.ORIGINAL_BYTES
    raw[2304:] = b"original-signature".ljust(64, b"\0")
    return bytes(raw)


class LargeAddressTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name).resolve() / "Private Game Environment"
        runtime = self.root / "runtime/DAO Runtime.app"
        self.c = types.SimpleNamespace(root=self.root, runtime=runtime,
                                      contents=runtime / "Contents", data=self.root / "data")
        self.paths = laa._paths(self.c)
        self.paths["target"].parent.mkdir(parents=True)
        self.original = fixture_native()
        self.paths["target"].write_bytes(self.original)
        self.paths["target"].chmod(0o755)
        os.utime(self.paths["target"], ns=(1700000000123456789, 1700000000123456789))
        self.original_mtime = self.paths["target"].stat().st_mtime_ns
        for name, value in (("ORIGINAL_SHA256", hashlib.sha256(self.original).hexdigest()),
                            ("PATCH_OFFSET", 512), ("STUB_OFFSET", 1536)):
            patch = mock.patch.object(laa, name, value)
            patch.start()
            self.addCleanup(patch.stop)
        patch = mock.patch.object(laa, "active_wine_processes", return_value=[])
        self.processes = patch.start()
        self.addCleanup(patch.stop)
        patch = mock.patch.object(laa, "_codesign", side_effect=self.fake_codesign)
        self.signer = patch.start()
        self.addCleanup(patch.stop)
        self.game = runtime / "Contents/SharedSupport/prefix/drive_c/Game/DAOrigins.exe"
        self.game.parent.mkdir(parents=True)
        self.game.write_bytes(b"Unmodified Steam game fixture")
        self.game_mtime = self.game.stat().st_mtime_ns

    @staticmethod
    def fake_codesign(path, sign=False):
        if sign:
            raw = bytearray(path.read_bytes()[:2304])
            struct.pack_into("<I", raw, 268, 32)
            struct.pack_into("<Q", raw, 232, 288)
            raw += b"signed-fixture".ljust(32, b"\0")
            path.write_bytes(raw)

    def assert_game_unchanged(self):
        self.assertEqual(self.game.read_bytes(), b"Unmodified Steam game fixture")
        self.assertEqual(self.game.stat().st_mtime_ns, self.game_mtime)

    def enable(self):
        result = laa.set_enabled(self.c, True)
        self.assertTrue(result["laa_enabled"])
        return result

    def test_status_is_read_only_and_defaults_off(self):
        before = sorted(str(x) for x in self.root.rglob("*"))
        result = laa.status(self.c)
        self.assertTrue(result["laa_supported"])
        self.assertFalse(result["laa_enabled"])
        self.assertFalse(result["laa_managed"])
        self.assertEqual(before, sorted(str(x) for x in self.root.rglob("*")))
        self.signer.assert_not_called()
        self.processes.assert_not_called()

    def test_enable_and_restore_preserve_original_game_metadata_and_native(self):
        result = self.enable()
        self.assertTrue(result["changed"])
        installed = self.paths["target"].read_bytes()
        self.assertEqual(installed[512:521], laa.PATCH_BYTES)
        self.assertEqual(installed[1536:1536 + len(laa.STUB_CODE)], laa.STUB_CODE)
        self.assertEqual(self.paths["original"].read_bytes(), self.original)
        self.assertEqual(stat.S_IMODE(self.paths["directory"].stat().st_mode), 0o700)
        self.assertEqual(stat.S_IMODE(self.paths["original"].stat().st_mode), 0o600)
        restored = laa.set_enabled(self.c, False)
        self.assertTrue(restored["changed"])
        self.assertFalse(restored["laa_enabled"])
        self.assertEqual(self.paths["target"].read_bytes(), self.original)
        self.assertEqual(self.paths["target"].stat().st_mtime_ns, self.original_mtime)
        self.assertEqual(stat.S_IMODE(self.paths["target"].stat().st_mode), 0o755)
        self.assert_game_unchanged()

    def test_idempotence_avoids_process_and_signing_mutation(self):
        self.assertFalse(laa.set_enabled(self.c, False)["changed"])
        self.processes.assert_not_called()
        self.enable()
        self.processes.reset_mock()
        self.signer.reset_mock()
        self.assertFalse(laa.set_enabled(self.c, True)["changed"])
        self.processes.assert_not_called()
        self.signer.assert_not_called()

    def test_unknown_runtime_is_unsupported_and_never_overwritten(self):
        self.paths["target"].write_bytes(b"user-supplied different runtime")
        snapshot = laa.status(self.c)
        self.assertFalse(snapshot["laa_supported"])
        self.assertFalse(snapshot["laa_managed"])
        with self.assertRaises(laa.LargeAddressError):
            laa.set_enabled(self.c, True)
        self.assertEqual(self.paths["target"].read_bytes(), b"user-supplied different runtime")
        self.assertFalse(self.paths["directory"].exists())

    def test_active_wine_blocks_preparation(self):
        self.processes.return_value = [(42, 1, r"C:\Steam\steam.exe")]
        with self.assertRaisesRegex(laa.LargeAddressError, "Close Dragon Age"):
            laa.set_enabled(self.c, True)
        self.assertFalse(self.paths["directory"].exists())
        self.assertEqual(self.paths["target"].read_bytes(), self.original)

    def test_process_start_during_preparation_blocks_atomic_swap(self):
        self.processes.side_effect = [[], [(42, 1, "DAOrigins.exe")]]
        with self.assertRaisesRegex(laa.LargeAddressError, "Close Dragon Age"):
            laa.set_enabled(self.c, True)
        self.assertEqual(self.paths["target"].read_bytes(), self.original)
        self.assertEqual(json.loads(self.paths["receipt"].read_text())["phase"], "prepared")
        self.processes.side_effect = None
        self.processes.return_value = []
        self.enable()  # Prepared candidate is reused and its real state reconciled.

    def test_signing_failure_keeps_runtime_and_valid_backup(self):
        self.signer.side_effect = laa.LargeAddressError("fixture signing failure")
        with self.assertRaisesRegex(laa.LargeAddressError, "signing failure"):
            laa.set_enabled(self.c, True)
        self.assertEqual(self.paths["target"].read_bytes(), self.original)
        self.assertEqual(self.paths["original"].read_bytes(), self.original)
        self.assertFalse(self.paths["candidate"].exists())
        self.assertFalse(self.paths["receipt"].exists())
        self.assertTrue(laa.status(self.c)["laa_supported"])

    def test_tampered_candidate_or_backup_refuses_restore(self):
        self.enable()
        installed = self.paths["target"].read_bytes()
        for key in ("candidate", "original"):
            with self.subTest(key=key):
                path = self.paths[key]
                old = path.read_bytes()
                path.write_bytes(b"tampered")
                snapshot = laa.status(self.c)
                self.assertFalse(snapshot["laa_supported"])
                self.assertTrue(snapshot["laa_managed"])
                with self.assertRaises(laa.LargeAddressError):
                    laa.set_enabled(self.c, False)
                self.assertEqual(self.paths["target"].read_bytes(), installed)
                path.write_bytes(old)

    def test_missing_backup_refuses_restore_and_reports_managed_failure(self):
        self.enable()
        self.paths["original"].unlink()
        self.assertFalse(laa.status(self.c)["laa_supported"])
        self.assertTrue(laa.status(self.c)["laa_managed"])
        with self.assertRaises(FileNotFoundError):
            laa.set_enabled(self.c, False)

    def test_matching_receipt_hash_cannot_hide_extra_native_code_change(self):
        self.enable()
        candidate = bytearray(self.paths["candidate"].read_bytes())
        candidate[550] ^= 0x40
        self.paths["candidate"].write_bytes(candidate)
        receipt = json.loads(self.paths["receipt"].read_text())
        receipt["prototype_sha256"] = laa._sha(candidate)
        self.paths["receipt"].write_text(json.dumps(receipt))
        with self.assertRaisesRegex(laa.LargeAddressError, "unexpected changes"):
            laa.set_enabled(self.c, False)

    def test_interruption_after_enable_rename_reconciles_from_hash(self):
        writer = laa._write_record
        def interrupted(c, path, record):
            if record["phase"] == "enabled":
                raise OSError("fixture interrupted after runtime rename")
            return writer(c, path, record)
        with mock.patch.object(laa, "_write_record", side_effect=interrupted):
            with self.assertRaises(OSError):
                laa.set_enabled(self.c, True)
        self.assertEqual(json.loads(self.paths["receipt"].read_text())["phase"], "prepared")
        self.assertTrue(laa.status(self.c)["laa_enabled"])
        self.assertFalse(laa.set_enabled(self.c, True)["changed"])
        self.assertFalse(laa.set_enabled(self.c, False)["laa_enabled"])

    def test_interruption_after_candidate_publication_reconstructs_receipt(self):
        with mock.patch.object(laa, "_write_record", side_effect=OSError("fixture interrupted before receipt")):
            with self.assertRaises(OSError):
                laa.set_enabled(self.c, True)
        self.assertTrue(self.paths["candidate"].is_file())
        self.assertTrue(self.paths["original"].is_file())
        self.assertFalse(self.paths["receipt"].exists())
        self.assertEqual(self.paths["target"].read_bytes(), self.original)
        self.assertTrue(laa.status(self.c)["laa_supported"])
        self.assertTrue(laa.status(self.c)["laa_managed"])
        self.assertFalse(laa.status(self.c)["laa_enabled"])
        self.signer.reset_mock()
        self.enable()
        self.assertTrue(all(call.kwargs.get("sign") is not True for call in self.signer.call_args_list))
        self.assertEqual(json.loads(self.paths["receipt"].read_text())["phase"], "enabled")

    def test_invalid_orphan_candidate_is_never_replaced_or_adopted(self):
        with mock.patch.object(laa, "_write_record", side_effect=OSError("fixture interrupted before receipt")):
            with self.assertRaises(OSError):
                laa.set_enabled(self.c, True)
        broken = bytearray(self.paths["candidate"].read_bytes())
        broken[550] ^= 0x20
        self.paths["candidate"].write_bytes(broken)
        with self.assertRaisesRegex(laa.LargeAddressError, "unexpected changes"):
            laa.set_enabled(self.c, True)
        self.assertEqual(self.paths["candidate"].read_bytes(), broken)
        self.assertEqual(self.paths["target"].read_bytes(), self.original)
        self.assertFalse(self.paths["receipt"].exists())

    def test_interruption_after_restore_rename_reconciles_from_hash(self):
        self.enable()
        writer = laa._write_record
        def interrupted(c, path, record):
            if record["phase"] == "disabled":
                raise OSError("fixture interrupted after restore rename")
            return writer(c, path, record)
        with mock.patch.object(laa, "_write_record", side_effect=interrupted):
            with self.assertRaises(OSError):
                laa.set_enabled(self.c, False)
        self.assertEqual(json.loads(self.paths["receipt"].read_text())["phase"], "prepared")
        self.assertTrue(laa.status(self.c)["laa_supported"])
        self.assertFalse(laa.status(self.c)["laa_enabled"])
        self.assertEqual(self.paths["target"].read_bytes(), self.original)

    def test_invalid_receipt_and_symlink_target_are_refused(self):
        self.enable()
        self.paths["receipt"].write_text("{}");
        with self.assertRaises(laa.LargeAddressError):
            laa.set_enabled(self.c, False)
        other = self.root / "unrelated.so"
        other.write_bytes(self.original)
        self.paths["target"].unlink()
        self.paths["target"].symlink_to(other)
        with self.assertRaisesRegex(laa.LargeAddressError, "symbolic link"):
            laa.set_enabled(self.c, True)
        self.assertEqual(other.read_bytes(), self.original)

    def test_padding_and_context_guards_even_if_hash_definition_is_changed(self):
        for offset in (512, 1536):
            with self.subTest(offset=offset):
                raw = bytearray(self.original)
                raw[offset] ^= 0xFF
                with mock.patch.object(laa, "ORIGINAL_SHA256", laa._sha(raw)):
                    with self.assertRaisesRegex(laa.LargeAddressError, "patch location"):
                        laa._unsigned(bytes(raw))


class ProcessGuardTests(unittest.TestCase):
    def setUp(self):
        self.c = types.SimpleNamespace(runtime=Path("/fixture/DAO Runtime.app"),
            contents=Path("/fixture/DAO Runtime.app/Contents"))

    def test_ps_failure_and_incomplete_snapshot_fail_closed(self):
        for outcome in (subprocess.CalledProcessError(1, "ps"), types.SimpleNamespace(stdout=""),
                        types.SimpleNamespace(stdout="not a process row")):
            with self.subTest(outcome=str(outcome)):
                patch = mock.patch.object(laa.subprocess, "run", side_effect=outcome) if isinstance(outcome, Exception) else mock.patch.object(laa.subprocess, "run", return_value=outcome)
                with patch, self.assertRaises(laa.LargeAddressError):
                    laa.strict_processes(self.c)

    def test_libproc_failure_is_not_an_empty_process_list(self):
        result = types.SimpleNamespace(stdout="1 0 0 S /sbin/launchd\n")
        with mock.patch.object(laa.subprocess, "run", return_value=result), \
                mock.patch.object(laa.ctypes, "CDLL", side_effect=OSError("no process access")), \
                self.assertRaises(laa.LargeAddressError):
            laa.strict_processes(self.c)

    def test_configure_only_is_excluded_without_hiding_wine_children(self):
        configure = str(self.c.contents / "Configure.app/Contents/MacOS/Configure")
        rows = [(1, 0, configure), (2, 1, "DAOrigins.exe"), (3, 0, "steam.exe")]
        with mock.patch.object(laa, "strict_processes", return_value=rows):
            self.assertEqual(laa.active_wine_processes(self.c), rows[1:])

    def test_live_uninspectable_wine_candidate_is_refused(self):
        uid = os.getuid()
        result = types.SimpleNamespace(stdout=f"1 0 0 S /sbin/launchd\n42 1 {uid} S C:\\Steam\\STEAM.EXE\n")
        fn = mock.Mock(return_value=0)
        with mock.patch.object(laa.subprocess, "run", return_value=result), \
                mock.patch.object(laa.ctypes, "CDLL", return_value=types.SimpleNamespace(proc_pidpath=fn)), \
                mock.patch.object(laa.os, "kill", return_value=None), \
                self.assertRaisesRegex(laa.LargeAddressError, "Could not inspect process"):
            laa.strict_processes(self.c)

    def test_unrelated_uninspectable_native_process_is_ignored(self):
        uid = os.getuid()
        result = types.SimpleNamespace(stdout=f"1 0 0 S /sbin/launchd\n42 1 {uid} S /unrelated/blender-mcp/venv/bin/python server.py\n")
        fn = mock.Mock(return_value=0)
        with mock.patch.object(laa.subprocess, "run", return_value=result), \
                mock.patch.object(laa.ctypes, "CDLL", return_value=types.SimpleNamespace(proc_pidpath=fn)), \
                mock.patch.object(laa.os, "kill") as kill:
            self.assertEqual(laa.strict_processes(self.c), [])
        fn.assert_not_called()
        kill.assert_not_called()

    def test_uninspectable_native_process_in_dedicated_runtime_is_refused(self):
        uid = os.getuid()
        result = types.SimpleNamespace(stdout=f"1 0 0 S /sbin/launchd\n42 1 {uid} S {self.c.runtime}/Contents/SharedSupport/wine/bin/wineserver\n")
        fn = mock.Mock(return_value=0)
        with mock.patch.object(laa.subprocess, "run", return_value=result), \
                mock.patch.object(laa.ctypes, "CDLL", return_value=types.SimpleNamespace(proc_pidpath=fn)), \
                mock.patch.object(laa.os, "kill", return_value=None), \
                self.assertRaisesRegex(laa.LargeAddressError, "Could not inspect process"):
            laa.strict_processes(self.c)


if __name__ == "__main__":
    unittest.main()
