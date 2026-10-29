"""Binary/source pairing checks; all files are synthetic and never executed."""
from pathlib import Path
import hashlib
import json
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'scripts'))
import bundle_audio


class AudioBundleTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.source = self.root / 'source'
        self.artifacts = self.root / 'artifacts'
        self.destination = self.root / 'app-audio'
        self.source.mkdir(); self.artifacts.mkdir()
        for name in ('source-manifest.json', 'build.py', 'COPYING.LIB', 'README.md'):
            (self.source / name).write_text('synthetic ' + name)
        overlay = self.source / 'overlay/dlls/dsound'
        overlay.mkdir(parents=True)
        (overlay / 'audio.c').write_bytes(b'synthetic source')
        (self.source / 'source-manifest.json').write_text(json.dumps({'overlay': {
            'dlls/dsound/audio.c': {'bytes': 16, 'sha256': hashlib.sha256(b'synthetic source').hexdigest()}}}))
        self.manifest = {'schema': 1, 'id': 'origins-audio', 'policy_revision': 10}
        for key, name in (('source_manifest_sha256', 'source-manifest.json'), ('build_recipe_sha256', 'build.py')):
            self.manifest[key] = hashlib.sha256((self.source / name).read_bytes()).hexdigest()
        for key, name in (('dll', 'dsound.dll'), ('corresponding_source', 'audio-source.tar.gz')):
            data = ('synthetic ' + key).encode()
            (self.artifacts / name).write_bytes(data)
            self.manifest[key] = dict(file=name, bytes=len(data), sha256=hashlib.sha256(data).hexdigest())
        self.save_manifest()

    def save_manifest(self):
        (self.source / 'component.json').write_text(json.dumps(self.manifest))

    def test_complete_matching_bundle(self):
        bundle_audio.bundle(self.source, self.artifacts, self.destination)
        bundle_audio.validate(self.source, self.destination, bundled=True)
        self.assertEqual(len(list(self.destination.iterdir())), 6)
        with self.assertRaisesRegex(ValueError, 'already exists'):
            bundle_audio.bundle(self.source, self.artifacts, self.destination)

    def test_altered_binary_or_complete_source_rejected_before_output(self):
        for name in ('dsound.dll', 'audio-source.tar.gz'):
            p = self.artifacts / name; original = p.read_bytes()
            p.write_bytes(b'changed')
            with self.subTest(name=name), self.assertRaisesRegex(ValueError, 'differs'):
                bundle_audio.bundle(self.source, self.artifacts, self.destination)
            self.assertFalse(self.destination.exists())
            p.write_bytes(original)

    def test_stale_build_recipe_and_source_manifest_rejected(self):
        for name in ('build.py', 'source-manifest.json'):
            p = self.source / name; original = p.read_bytes()
            p.write_bytes(b'changed')
            with self.subTest(name=name), self.assertRaisesRegex(ValueError, 'build recipe differs'):
                bundle_audio.validate(self.source, self.artifacts)
            p.write_bytes(original)

    def test_stale_or_extra_overlay_is_rejected_before_output(self):
        p = self.source / 'overlay/dlls/dsound/audio.c'
        original = p.read_bytes(); p.write_bytes(b'edited after binary build')
        with self.assertRaisesRegex(ValueError, 'source overlay differs'):
            bundle_audio.bundle(self.source, self.artifacts, self.destination)
        self.assertFalse(self.destination.exists()); p.write_bytes(original)
        extra = p.with_name('unreviewed.c'); extra.write_bytes(b'extra source')
        with self.assertRaisesRegex(ValueError, 'overlay file list differs'):
            bundle_audio.validate(self.source, self.artifacts)

    def test_source_archive_must_be_present_and_unlinked(self):
        p = self.artifacts / 'audio-source.tar.gz'; p.unlink()
        with self.assertRaisesRegex(ValueError, 'Missing, linked'):
            bundle_audio.validate(self.source, self.artifacts)
        p.symlink_to(self.root / 'missing')
        with self.assertRaisesRegex(ValueError, 'Missing, linked'):
            bundle_audio.validate(self.source, self.artifacts)

    def test_archive_path_cannot_escape_bundle(self):
        for name in ('../outside-source.tar.gz', '/outside-source.tar.gz', '', '.', '..'):
            self.manifest['corresponding_source']['file'] = name
            self.save_manifest()
            with self.subTest(name=name), self.assertRaisesRegex(ValueError, 'filename'):
                bundle_audio.validate(self.source, self.artifacts)

    def test_packaged_notices_and_manifest_must_match_current_source(self):
        bundle_audio.bundle(self.source, self.artifacts, self.destination)
        for name in ('component.json', 'source-manifest.json', 'COPYING.LIB', 'README.md'):
            p = self.destination / name; original = p.read_bytes()
            p.write_bytes(b'old notice or manifest')
            with self.subTest(name=name), self.assertRaisesRegex(ValueError, 'differs from source'):
                bundle_audio.validate(self.source, self.destination, bundled=True)
            p.write_bytes(original)


if __name__ == '__main__':
    unittest.main()
