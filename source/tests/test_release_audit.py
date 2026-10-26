"""The source export must fail closed on unexpected files or private material."""
from pathlib import Path
import hashlib
import sys
import tempfile
import unittest
from unittest import mock
sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'scripts'))
from audit_release import NOTICE_FILES, audit
import audit_release

class ReleaseAuditTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name)
        for name in (*NOTICE_FILES,'README.md','dependency-manifest.json','source/Launcher.swift'):
            p=self.root/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_text('fixture\n')
    def test_clean_allowlisted_source_passes(self):
        self.assertEqual(len(audit(self.root)),7)
    def test_licensing_scope_notices_cannot_be_omitted_from_source_export(self):
        for name in NOTICE_FILES:
            with self.subTest(name=name):
                path=self.root/name
                original=path.read_bytes()
                path.unlink()
                with self.assertRaisesRegex(ValueError,'Missing '+name):audit(self.root)
                path.write_bytes(original)
    def test_known_issue_forms_pass_but_unexpected_github_files_fail(self):
        directory=self.root/'.github'/'ISSUE_TEMPLATE'
        directory.mkdir(parents=True)
        for name in ('bug_report.yml','compatibility_report.yml','config.yml'):
            (directory/name).write_text('fixture\n')
        self.assertEqual(len(audit(self.root)),10)
        (directory/'private-notes.yml').write_text('fixture\n')
        with self.assertRaisesRegex(ValueError,'allowlist'):audit(self.root)
    def test_unexpected_game_payload_fails(self):
        (self.root/'game.exe').write_bytes(b'MZ fixture')
        with self.assertRaisesRegex(ValueError,'allowlist'):audit(self.root)
    def test_reviewed_artwork_is_excluded_but_its_notice_is_exported(self):
        relative='branding/aberrant-ink/app-icon.png'
        image=self.root/relative
        image.parent.mkdir(parents=True)
        image.write_bytes(b'\x89PNG\0synthetic artwork fixture')
        (self.root/audit_release.ARTWORK_NOTICE).write_text('Reserved artwork fixture notice\n')
        with mock.patch.dict(audit_release.RESERVED_IMAGES,{relative:hashlib.sha256(image.read_bytes()).hexdigest()}):
            entries=audit(self.root)
        paths={entry['path'] for entry in entries}
        self.assertNotIn(relative,paths)
        self.assertIn(audit_release.ARTWORK_NOTICE,paths)
    def test_changed_artwork_and_unreviewed_siblings_are_rejected(self):
        image=self.root/'branding/aberrant-ink/app-icon.png'
        image.parent.mkdir(parents=True)
        image.write_bytes(b'changed image fixture')
        (self.root/audit_release.ARTWORK_NOTICE).write_text('Fixture notice\n')
        with self.assertRaisesRegex(ValueError,'differs from reviewed'):audit(self.root)
        image.unlink()
        (image.parent/'other-image.png').write_bytes(b'fixture')
        with self.assertRaisesRegex(ValueError,'allowlist'):audit(self.root)
    def test_reserved_artwork_requires_its_notice(self):
        relative='branding/aberrant-ink/app-icon.png'
        image=self.root/relative
        image.parent.mkdir(parents=True)
        image.write_bytes(b'artwork fixture')
        with mock.patch.dict(audit_release.RESERVED_IMAGES,{relative:hashlib.sha256(image.read_bytes()).hexdigest()}):
            with self.assertRaisesRegex(ValueError,'Missing artwork notice'):audit(self.root)
    def test_private_user_path_fails(self):
        # Construct a synthetic path without placing a private path in source.
        (self.root/'README.md').write_text('/'+'Users'+'/'+'Example User'+'/Steam')
        with self.assertRaisesRegex(ValueError,'private data'):audit(self.root)
    def test_external_link_fails(self):
        (self.root/'docs').mkdir();(self.root/'docs/link.md').symlink_to('/tmp/example')
        with self.assertRaisesRegex(ValueError,'Symlink'):audit(self.root)
    def test_disguised_binary_fails(self):
        (self.root/'README.md').write_bytes(b'MZ\0fixture')
        with self.assertRaisesRegex(ValueError,'Binary'):audit(self.root)
    def test_key_material_fails(self):
        (self.root/'README.md').write_text('-----BEGIN '+'OPENSSH PRIVATE KEY-----')
        with self.assertRaisesRegex(ValueError,'private data'):audit(self.root)
