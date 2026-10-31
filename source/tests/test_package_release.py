"""Package-mode checks use temporary fixtures and never create real disk images."""
import contextlib
import hashlib
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
import zipfile
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))
import package_release as packaging


class PackagingTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.base = Path(temp.name).resolve()
        self.root = self.base / "source-tree"
        self.root.mkdir()
        (self.root / "VERSION").write_text("0.2.0-beta.1\n")
        self.app = self.base / "Origins Launcher.app"
        (self.app / "Contents").mkdir(parents=True)
        (self.app / "Contents/Info.plist").write_text("fixture; no executable")
        resources = self.app / "Contents/Resources"
        resources.mkdir()
        (resources / "VERSION").write_bytes((self.root / "VERSION").read_bytes())
        for name in packaging.NOTICE_FILES:
            text = "Fixture notice: " + name + "\n"
            (self.root / name).write_text(text)
            (resources / name).write_text(text)
        self.output = self.base / "release"
        self.commands = []
        self.instructions = None
        self.signature = "Signature=adhoc\n"
        self.fail_tool = None
        entries = [{"path": name, "bytes": (self.root / name).stat().st_size, "sha256": "fixture"}
                   for name in ("VERSION", *packaging.NOTICE_FILES)]
        patch = mock.patch.object(packaging, "audit", return_value=entries)
        self.audit_mock = patch.start()
        self.addCleanup(patch.stop)
        patch = mock.patch.object(packaging.subprocess, "run", side_effect=self.run_fixture_command)
        self.run_mock = patch.start()
        self.addCleanup(patch.stop)

    def run_fixture_command(self, command, **kwargs):
        self.commands.append(command)
        self.assertTrue(kwargs.get("check"))
        if self.fail_tool and self.fail_tool in command:
            raise subprocess.CalledProcessError(1, command)
        if command[0] == "/usr/bin/hdiutil":
            stage = Path(command[command.index("-srcfolder") + 1])
            self.instructions = (stage / "START HERE.txt").read_text()
            self.assertTrue((stage / "Origins Launcher.app/Contents/Info.plist").is_file())
            self.assertEqual((stage / "Applications").readlink(), Path("/Applications"))
            for name in packaging.NOTICE_FILES:
                self.assertEqual((stage / name).read_bytes(), (self.root / name).read_bytes())
                self.assertEqual((stage / "Origins Launcher.app/Contents/Resources" / name).read_bytes(),
                                 (self.root / name).read_bytes())
            Path(command[-1]).write_bytes(b"fixture image placeholder; hdiutil was not run")
        return subprocess.CompletedProcess(command, 0, "", self.signature if "-dv" in command else "")

    def package(self, **kwargs):
        stream = io.StringIO()
        with contextlib.redirect_stdout(stream):
            packaging.package(self.root, self.output, app=self.app, **kwargs)
        return json.loads(stream.getvalue())

    def official_artwork(self):
        resources = self.app / 'Contents/Resources'
        icon = resources / 'DragonAgeOrigins.icns'
        icon.write_bytes(b'fixture icon; no artwork is embedded in this test')
        notice = self.root / packaging.ARTWORK_NOTICE
        notice.parent.mkdir(parents=True, exist_ok=True)
        notice.write_text('Artist permission to use and share unchanged official builds free of charge; sales require separate permission.\n')
        (resources / 'ARTWORK-NOTICE.txt').write_bytes(notice.read_bytes())
        marker = {
            'schema_version': 1,
            'scope': packaging.OFFICIAL_ARTWORK_SCOPE,
            'policy_version': packaging.OFFICIAL_ARTWORK_POLICY_VERSION,
            'credit': packaging.OFFICIAL_ARTWORK_CREDIT,
            'source_sha256': packaging.OFFICIAL_ARTWORK_SOURCE_SHA256,
            'icon_sha256': hashlib.sha256(icon.read_bytes()).hexdigest(),
            'notice_sha256': hashlib.sha256(notice.read_bytes()).hexdigest(),
        }
        path = resources / 'OFFICIAL-ARTWORK.json'
        path.write_text(json.dumps(marker))
        return path, marker

    def test_default_stays_local_preview(self):
        args = packaging.parse_arguments(["--output", str(self.output), "--app", str(self.app)])
        self.assertFalse(args.public)
        self.assertFalse(args.unsigned_beta)
        report = self.package()
        self.assertIn("OriginsLauncher-0.2.0-beta.1-arm64-LOCAL-PREVIEW.dmg", report["files"])
        self.assertEqual(report["distribution_mode"], "local-preview")
        self.assertFalse(report["public_binary"])
        self.assertFalse(report["unsigned_beta"])
        self.assertTrue(self.instructions.startswith("LOCAL PREVIEW"))
        self.assertFalse(any("stapler" in c or "--assess" in c for c in self.commands))

    def test_stale_helper_is_rejected_before_archives(self):
        source = self.root / "source"
        source.mkdir()
        (source / "daoctl.py").write_text("new controller")
        (self.app / "Contents/Resources/daoctl.py").write_text("old controller")
        with self.assertRaisesRegex(ValueError, "App helper differs"):
            self.package(unsigned_beta=True)
        self.assertFalse(self.output.exists())
        self.run_mock.assert_not_called()

    def test_reverb_manager_requires_component_even_if_manifest_missing(self):
        source = self.root / "source"
        source.mkdir()
        (source / "reverb_fix.py").write_text("fixture manager")
        (self.app / "Contents/Resources/reverb_fix.py").write_text("fixture manager")
        with self.assertRaisesRegex(ValueError, "Missing, linked"):
            self.package(unsigned_beta=True)
        self.assertFalse(self.output.exists())
        self.run_mock.assert_not_called()

    def test_local_artwork_cannot_enter_any_distribution_package(self):
        (self.app / "Contents/Resources/LOCAL-ARTWORK.json").write_text('{"scope":"local-only"}')
        for mode in ({}, {"unsigned_beta": True}, {"public": True}):
            with self.subTest(mode=mode), self.assertRaisesRegex(ValueError, "Local artwork"):
                self.package(**mode)
            self.assertFalse(self.output.exists())
        self.run_mock.assert_not_called()

    def test_official_artwork_packages_with_matching_notices_and_icon(self):
        path, marker = self.official_artwork()
        report = self.package(unsigned_beta=True)
        self.assertTrue(report['unsigned_beta'])
        self.assertEqual(json.loads(path.read_text()), marker)
        self.assertTrue(any(c[0] == '/usr/bin/hdiutil' for c in self.commands))
        self.assertFalse((path.parent / 'LOCAL-ARTWORK.json').exists())

    def test_official_artwork_rejects_changed_provenance_before_any_archives(self):
        path, marker = self.official_artwork()
        for key, value in (('source_sha256', '0' * 64), ('credit', 'Someone else'),
                           ('scope', 'unrestricted'), ('schema_version', 2),
                           ('policy_version', '2026-10-26-beta5'), ('notice_sha256', '0' * 64),
                           ('icon_sha256', '0' * 64), ('private_path', 'not permitted')):
            changed = dict(marker)
            changed[key] = value
            path.write_text(json.dumps(changed))
            with self.subTest(key=key), self.assertRaisesRegex(ValueError, 'Official artwork provenance'):
                self.package(unsigned_beta=True)
            self.assertFalse(self.output.exists())
        self.run_mock.assert_not_called()

    def test_beta5_artwork_receipt_is_rejected_even_with_current_notices(self):
        path, marker = self.official_artwork()
        marker['scope'] = 'unchanged-official-builds'
        del marker['policy_version']
        del marker['notice_sha256']
        path.write_text(json.dumps(marker))
        # The app and source already have matching new notices; that alone must
        # never relabel an old beta.5 receipt as a build under the revised policy.
        for mode in ({}, {'unsigned_beta': True}, {'public': True}):
            with self.subTest(mode=mode), self.assertRaisesRegex(ValueError, 'Official artwork provenance'):
                self.package(**mode)
            self.assertFalse(self.output.exists())
        self.run_mock.assert_not_called()

    def test_artwork_receipt_binds_exact_notice_even_when_app_and_source_agree(self):
        path, _ = self.official_artwork()
        altered = b'Changed artist terms after the app was built.\n'
        (self.root / packaging.ARTWORK_NOTICE).write_bytes(altered)
        (path.parent / 'ARTWORK-NOTICE.txt').write_bytes(altered)
        with self.assertRaisesRegex(ValueError, 'Official artwork provenance'):
            self.package(unsigned_beta=True)
        self.assertFalse(self.output.exists())
        self.run_mock.assert_not_called()

    def test_official_artwork_rejects_changed_icon_before_any_archives(self):
        path, _ = self.official_artwork()
        (path.parent / 'DragonAgeOrigins.icns').write_bytes(b'a different icon')
        with self.assertRaisesRegex(ValueError, 'Official artwork provenance'):
            self.package(unsigned_beta=True)
        self.assertFalse(self.output.exists())
        self.run_mock.assert_not_called()

    def test_official_artwork_rejects_malformed_or_linked_marker(self):
        path, _ = self.official_artwork()
        for text in ('{invalid', 'null', '[]'):
            path.write_text(text)
            with self.subTest(text=text), self.assertRaises(ValueError):
                self.package(unsigned_beta=True)
            self.assertFalse(self.output.exists())
        path.unlink()
        path.symlink_to(self.base / 'absent-marker.json')
        with self.assertRaisesRegex(ValueError, 'linked official artwork marker'):
            self.package(unsigned_beta=True)
        self.assertFalse(self.output.exists())
        self.run_mock.assert_not_called()

    def test_official_artwork_rejects_linked_or_missing_icon(self):
        path, _ = self.official_artwork()
        icon = path.parent / 'DragonAgeOrigins.icns'
        icon.unlink()
        for linked in (False, True):
            if linked:
                icon.symlink_to(self.base / 'absent-icon.icns')
            with self.subTest(linked=linked), self.assertRaisesRegex(ValueError, 'linked official artwork icon'):
                self.package(unsigned_beta=True)
            self.assertFalse(self.output.exists())
        self.run_mock.assert_not_called()

    def test_mixed_artwork_markers_and_dangling_local_marker_are_rejected(self):
        path, _ = self.official_artwork()
        local = path.parent / 'LOCAL-ARTWORK.json'
        for linked in (False, True):
            if linked:
                local.unlink()
                local.symlink_to(self.base / 'absent-local-marker.json')
            else:
                local.write_text('{}')
            with self.subTest(linked=linked), self.assertRaisesRegex(ValueError, 'Local artwork'):
                self.package(unsigned_beta=True)
            self.assertFalse(self.output.exists())
        self.run_mock.assert_not_called()

    def test_official_artwork_still_requires_current_notices(self):
        self.official_artwork()
        (self.app / 'Contents/Resources/ARTWORK.md').write_text('old terms')
        with self.assertRaisesRegex(ValueError, 'App notice differs from source: ARTWORK.md'):
            self.package(unsigned_beta=True)
        self.assertFalse(self.output.exists())
        self.run_mock.assert_not_called()

    def test_official_artwork_requires_matching_unlinked_artist_notice(self):
        path, _ = self.official_artwork()
        notice = path.parent / 'ARTWORK-NOTICE.txt'
        notice.write_text('Different artwork terms')
        with self.assertRaisesRegex(ValueError, 'Official artwork notice differs from source'):
            self.package(unsigned_beta=True)
        self.assertFalse(self.output.exists())
        notice.unlink()
        for linked in (False, True):
            if linked:
                notice.symlink_to(self.root / packaging.ARTWORK_NOTICE)
            with self.subTest(linked=linked), self.assertRaisesRegex(ValueError, 'linked official artwork notice'):
                self.package(unsigned_beta=True)
            self.assertFalse(self.output.exists())
        self.run_mock.assert_not_called()

    def test_signed_public_retains_all_three_verification_gates(self):
        self.signature = "Authority=Developer ID Application: Fixture Publisher (TESTTEAM)\n"
        report = self.package(public=True)
        self.assertIn("OriginsLauncher-0.2.0-beta.1-arm64.dmg", report["files"])
        self.assertTrue(report["public_binary"])
        self.assertFalse(report["unsigned_beta"])
        self.assertEqual(report["distribution_mode"], "public")
        self.assertTrue(any(c[:2] == ["/usr/bin/codesign", "--verify"] for c in self.commands))
        self.assertTrue(any(c[:3] == ["/usr/bin/xcrun", "stapler", "validate"] for c in self.commands))
        self.assertTrue(any(c[:2] == ["/usr/sbin/spctl", "--assess"] for c in self.commands))
        self.assertNotIn("Open Anyway", self.instructions)
        self.assertNotIn("UNSIGNED", self.instructions)

    def test_public_refuses_adhoc_signature_before_image_creation(self):
        with contextlib.redirect_stdout(io.StringIO()), self.assertRaisesRegex(ValueError, "Developer ID"):
            self.package(public=True)
        self.assertFalse(any(c[0] == "/usr/bin/hdiutil" for c in self.commands))

    def test_public_refuses_failed_notarization_or_gatekeeper(self):
        self.signature = "Authority=Developer ID Application: Fixture Publisher (TESTTEAM)\n"
        for tool in ("stapler", "/usr/sbin/spctl"):
            with self.subTest(tool=tool):
                self.output = self.base / ("failed-" + Path(tool).name)
                self.commands.clear()
                self.fail_tool = tool
                with self.assertRaises(subprocess.CalledProcessError):
                    self.package(public=True)
                self.assertFalse(any(c[0] == "/usr/bin/hdiutil" for c in self.commands))

    def test_unsigned_beta_is_explicitly_named_and_explained(self):
        args = packaging.parse_arguments(["--output", str(self.output), "--app", str(self.app), "--unsigned-beta"])
        self.assertTrue(args.unsigned_beta)
        self.assertFalse(args.public)
        report = self.package(unsigned_beta=True)
        filename = "OriginsLauncher-0.2.0-beta.1-arm64-UNSIGNED-BETA.dmg"
        self.assertIn(filename, report["files"])
        self.assertTrue(report["unsigned_beta"])
        self.assertFalse(report["public_binary"])
        self.assertEqual(report["distribution_mode"], "unsigned-beta")
        self.assertTrue(self.instructions.startswith("UNSIGNED BETA"))
        for text in ("no Apple Developer ID signature or Apple notarization", "Open Anyway",
                     "https://support.apple.com/en-gb/102445", "Privacy & Security", "Keep Gatekeeper enabled",
                     "Do not disable macOS security checks or remove the app’s quarantine attribute"):
            self.assertIn(text, self.instructions)
        for unsafe in ("xattr -", "--master-disable", "--global-disable", "sudo spctl", "fresh-install test passed"):
            self.assertNotIn(unsafe, self.instructions)
        self.assertFalse(any("stapler" in c or "--assess" in c for c in self.commands))
        self.assertTrue(any(c[:2] == ["/usr/bin/codesign", "--verify"] for c in self.commands))
        expected = hashlib.sha256((self.output / filename).read_bytes()).hexdigest()
        self.assertIn(expected + "  " + filename, (self.output / "SHA256SUMS.txt").read_text())

    def test_unsigned_beta_still_requires_bundle_integrity(self):
        self.fail_tool = "--verify"
        with self.assertRaises(subprocess.CalledProcessError):
            self.package(unsigned_beta=True)
        self.assertFalse(any(c[0] == "/usr/bin/hdiutil" for c in self.commands))

    def test_cli_rejects_conflicting_modes_or_unsigned_without_app(self):
        argument_sets = [
            ["--output", str(self.output), "--app", str(self.app), "--public", "--unsigned-beta"],
            ["--output", str(self.output), "--unsigned-beta"],
        ]
        for arguments in argument_sets:
            with self.subTest(arguments=arguments), contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit) as error:
                packaging.parse_arguments(arguments)
            self.assertEqual(error.exception.code, 2)
        self.assertFalse(self.output.exists())

    def test_api_rejects_conflicting_modes_or_unsigned_without_app_before_writes(self):
        for kwargs in ({"public": True, "unsigned_beta": True, "app": self.app}, {"unsigned_beta": True}):
            with self.subTest(kwargs=kwargs), self.assertRaises(ValueError):
                packaging.package(self.root, self.output, **kwargs)
        self.audit_mock.assert_not_called()
        self.run_mock.assert_not_called()
        self.assertFalse(self.output.exists())

    def test_source_only_packaging_remains_available(self):
        stream = io.StringIO()
        with contextlib.redirect_stdout(stream):
            packaging.package(self.root, self.output)
        report = json.loads(stream.getvalue())
        self.assertEqual(report["distribution_mode"], "source-only")
        self.assertFalse(report["public_binary"])
        self.assertFalse(report["unsigned_beta"])
        self.assertFalse(any(name.endswith(".dmg") for name in report["files"]))
        with zipfile.ZipFile(self.output / "OriginsLauncher-0.2.0-beta.1-source.zip") as archive:
            for name in packaging.NOTICE_FILES:
                self.assertEqual(archive.read("OriginsLauncher/" + name), (self.root / name).read_bytes())
        self.run_mock.assert_not_called()

    def test_missing_app_notices_are_rejected_before_release_files_are_written(self):
        for name in packaging.NOTICE_FILES:
            with self.subTest(name=name):
                notice = self.app / "Contents/Resources" / name
                original = notice.read_bytes()
                notice.unlink()
                with self.assertRaisesRegex(ValueError, "Missing or linked app notice"):
                    self.package(unsigned_beta=True)
                self.assertFalse(self.output.exists())
                self.run_mock.assert_not_called()
                notice.write_bytes(original)

    def test_stale_app_notices_are_rejected_before_release_files_are_written(self):
        for name in packaging.NOTICE_FILES:
            with self.subTest(name=name):
                notice = self.app / "Contents/Resources" / name
                original = notice.read_bytes()
                notice.write_text("Previous release terms\n")
                with self.assertRaisesRegex(ValueError, "App notice differs from source"):
                    self.package(unsigned_beta=True)
                self.assertFalse(self.output.exists())
                self.run_mock.assert_not_called()
                notice.write_bytes(original)

    def test_notice_symlink_cannot_substitute_for_bundled_terms(self):
        notice = self.app / "Contents/Resources/ARTWORK.md"
        notice.unlink()
        notice.symlink_to(self.root / "ARTWORK.md")
        with self.assertRaisesRegex(ValueError, "Missing or linked app notice"):
            self.package(unsigned_beta=True)
        self.assertFalse(self.output.exists())
        self.run_mock.assert_not_called()

    def test_unsigned_mode_retains_private_runtime_exclusion(self):
        resource = self.app / "Contents/Resources"
        resource.mkdir(exist_ok=True)
        (resource / "runtime-location.json").write_text('{"root":"private fixture"}')
        with self.assertRaisesRegex(ValueError, "Private runtime"):
            self.package(unsigned_beta=True)
        self.run_mock.assert_not_called()

    def test_unknown_instruction_mode_is_rejected(self):
        with self.assertRaises(ValueError):
            packaging.start_here("unrecognized")


class ArtworkBuildPreflightTests(unittest.TestCase):
    """Invalid official-art builds must stop before compilation or bundle creation."""

    def test_official_mode_requires_reviewed_asset_and_credit(self):
        build = Path(__file__).resolve().parents[1] / 'build.sh'
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            fixture = base / 'unreviewed.png'
            fixture.write_bytes(b'unreviewed image')
            target = base / 'Origins Launcher.app'
            cases = (
                ({'DAO_OFFICIAL_ARTWORK': 'invalid'}, 'must be 0 or 1'),
                ({'DAO_OFFICIAL_ARTWORK': '1', 'DAO_CUSTOM_LOGO_CREDIT': 'Aberrant Ink'},
                 'reviewed, unlinked image'),
                ({'DAO_OFFICIAL_ARTWORK': '1', 'DAO_CUSTOM_LOGO_PATH': str(fixture),
                  'DAO_CUSTOM_LOGO_CREDIT': 'Someone else'}, 'credit Aberrant Ink'),
                ({'DAO_OFFICIAL_ARTWORK': '1', 'DAO_CUSTOM_LOGO_PATH': str(fixture),
                  'DAO_CUSTOM_LOGO_CREDIT': 'Aberrant Ink'}, 'differs from the reviewed'),
            )
            environment = {key: value for key, value in os.environ.items()
                           if not key.startswith('DAO_')}
            environment['DAO_BUILD_PYTHON'] = sys.executable
            for settings, error in cases:
                with self.subTest(settings=settings):
                    result = subprocess.run(['/bin/bash', str(build), str(target)],
                                            env={**environment, **settings},
                                            capture_output=True, text=True)
                    self.assertNotEqual(result.returncode, 0)
                    self.assertIn(error, result.stderr)
                    self.assertFalse(target.exists())

    def test_reviewed_asset_cannot_be_supplied_through_a_symlink(self):
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            original = base / 'image.png'
            original.write_bytes(b'fixture image')
            link = base / 'linked.png'
            link.symlink_to(original)
            with self.assertRaisesRegex(ValueError, 'reviewed, unlinked image'):
                packaging.validate_official_artwork_source(link, packaging.OFFICIAL_ARTWORK_CREDIT)


if __name__ == "__main__":
    unittest.main()
