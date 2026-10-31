"""Console option tests use disposable files; no real Steam, game or saves."""
import json
import os
from pathlib import Path
import stat
import sys
import tempfile
import types
import unittest
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import developer_console as d


TARGET = b'<true action="execute" file="${BINARIES_DIR}\\DAOrigins.exe" path="${BINARIES_DIR}" autoquit="true" />'
CONFIG = b'<false action="execute" file="${BINARIES_DIR}\\DAOriginsConfig.exe" arguments="-p -c &quot;${BINARIES_DIR}\\DAOrigins.exe&quot; -f &quot;${EXE_DIR}\\DAOriginsLauncher.exe&quot;" />'


def document(tag=TARGET):
    return (b'\xef\xbb\xbf<?xml version="1.0" encoding="utf-8" ?>\r\n'
            b'<BioWareApp product="DragonAgeOrigins">\r\n<!-- Caf\xc3\xa9 -->\r\n'
            + tag + b'\r\n' + CONFIG + b'\r\n</BioWareApp>\r\n')


class DeveloperConsoleTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.home = Path(temp.name).resolve()
        root = self.home / 'environment'
        prefix = root / 'runtime/prefix'
        self.c = types.SimpleNamespace(root=root, prefix=prefix, data=root/'data')
        self.folder = prefix / 'drive_c/Steam/steamapps/common/Dragon Age Ultimate Edition'
        self.target = self.folder / 'data/DAOriginsLauncher.xml'
        self.target.parent.mkdir(parents=True)
        self.original = document()
        self.target.write_bytes(self.original)
        self.game = dict(appid='47810', game_dir=str(self.folder))
        self.store = d._paths(self.c, self.game)[1]

    def enable(self):
        return d.prepare(self.c, self.game, True)

    def disable(self):
        return d.prepare(self.c, self.game, False)

    def read(self):
        return self.target.read_bytes()

    def test_default_and_status_are_read_only(self):
        self.assertEqual(d.prepare(self.c, None, None), [])
        s = d.status(self.c, self.game)
        self.assertTrue(s['console_supported'])
        self.assertFalse(s['console_enabled'])
        self.assertFalse(s['console_managed'])
        self.assertEqual(self.disable(), [])
        self.assertFalse(self.c.data.exists())
        self.assertEqual(self.read(), self.original)

    def test_standard_uses_only_per_launch_argument(self):
        self.game['appid'] = '17450'
        self.target.unlink()
        self.assertTrue(d.status(self.c, self.game)['console_supported'])
        self.assertEqual(self.enable(), [d.FLAG])
        self.assertEqual(self.disable(), [])
        self.assertFalse(self.c.data.exists())
        self.assertFalse(self.target.exists())

    def test_exact_round_trip_preserves_bom_newlines_config_and_mode(self):
        self.target.chmod(0o640)
        self.assertEqual(self.enable(), [])
        self.assertTrue(d.status(self.c, self.game)['console_enabled'])
        self.assertEqual(self.read(), self.original.replace(TARGET, TARGET[:-3] + b' arguments="-enabledeveloperconsole" />'))
        self.assertEqual(stat.S_IMODE(self.target.stat().st_mode), 0o640)
        backups = list((self.store/'backups').glob('*.xml'))
        self.assertEqual(len(backups), 1)
        self.assertEqual(backups[0].read_bytes(), self.original)
        self.assertEqual(stat.S_IMODE(backups[0].stat().st_mode), 0o600)
        self.disable()
        self.assertEqual(self.read(), self.original)
        self.assertFalse(d.status(self.c, self.game)['console_enabled'])
        self.assertTrue(d.status(self.c, self.game)['console_managed'])

    def test_existing_arguments_round_trip_exactly(self):
        for value in (b'', b'  ', b'-skip intro', b'-name &quot;Caf\xc3\xa9 &amp; Bob&quot;', b'-option=enabledeveloperconsole'):
            with self.subTest(value=value):
                raw = document(TARGET[:-3] + b" arguments='" + value + b"' />")
                self.target.write_bytes(raw)
                self.enable()
                self.assertIn(value, self.read())
                self.disable()
                self.assertEqual(self.read(), raw)

    def test_existing_manual_flag_is_observed_and_explicit_off_removes_it(self):
        self.target.write_bytes(document(TARGET[:-3] + b' arguments="-other &quot;-ENABLEDEVELOPERCONSOLE&quot; -last" />'))
        self.assertTrue(d.status(self.c, self.game)['console_enabled'])
        self.assertFalse(d.status(self.c, self.game)['console_managed'])
        before = self.read()
        self.enable()
        self.assertEqual(self.read(), before)
        self.assertFalse(self.c.data.exists())
        self.disable()
        self.assertIn(b'arguments="-other -last"', self.read())
        self.assertNotIn(b'ENABLEDEVELOPERCONSOLE', self.read())

    def test_duplicates_entities_and_embedded_quotes_are_removed_as_whole_tokens(self):
        self.target.write_bytes(document(TARGET[:-3] + b' arguments="-keep &#45;enabledeveloperconsole -enable&quot;developer&quot;console -enabledeveloperconsole-extra -tail -enabledeveloperconsole" />'))
        self.disable()
        self.assertIn(b'arguments="-keep -enabledeveloperconsole-extra -tail"', self.read())
        self.assertFalse(d.status(self.c, self.game)['console_enabled'])

    def test_comments_and_configurator_not_selected(self):
        raw = document().replace(b'<!-- Caf\xc3\xa9 -->', b'<!-- ' + TARGET + b' -->')
        self.target.write_bytes(raw)
        self.enable()
        self.assertIn(b'<!-- ' + TARGET + b' -->', self.read())
        self.assertIn(CONFIG, self.read())
        self.disable()
        self.assertEqual(self.read(), raw)

    def test_idempotent_choices_do_not_write(self):
        self.enable()
        with mock.patch.object(d, '_atomic_write') as write:
            self.enable()
            write.assert_not_called()
        self.disable()
        with mock.patch.object(d, '_atomic_write') as write:
            self.disable()
            write.assert_not_called()

    def test_later_unrelated_edits_are_preserved(self):
        self.enable()
        changed = self.read().replace(b'<!-- Caf\xc3\xa9 -->', b'<!-- Later user change -->').replace(b'autoquit="true"', b'custom="preserve" autoquit="true"')
        self.target.write_bytes(changed)
        self.disable()
        self.assertEqual(self.read(), self.original.replace(b'<!-- Caf\xc3\xa9 -->', b'<!-- Later user change -->').replace(b'autoquit="true"', b'custom="preserve" autoquit="true"'))

    def test_later_argument_edits_are_preserved(self):
        self.enable()
        self.target.write_bytes(self.read().replace(b'arguments="-enabledeveloperconsole"', b'arguments="-other &quot;A B&quot; -enabledeveloperconsole -last"'))
        self.disable()
        self.assertIn(b'arguments="-other &quot;A B&quot; -last"', self.read())
        self.assertIn(CONFIG, self.read())

    def test_game_update_can_be_reapplied_without_restoring_old_xml(self):
        self.enable()
        updated = self.original.replace(b'<!-- Caf\xc3\xa9 -->', b'<!-- Steam update -->')
        self.target.write_bytes(updated)
        self.enable()
        self.assertEqual(len(list((self.store/'backups').glob('*.xml'))), 2)
        self.disable()
        self.assertEqual(self.read(), updated)

    def test_malformed_ambiguous_wrong_root_or_declarations_are_unchanged(self):
        cases = [document(TARGET + TARGET), document(b''), document().replace(b'autoquit="true"', b'autoquit="false"'),
                 document().replace(b'product="DragonAgeOrigins"', b'product="Other"'), document()[:-5],
                 b'<!DOCTYPE BioWareApp [<!ENTITY x "value">]>' + document().lstrip(b'\xef\xbb\xbf').split(b'\r\n', 1)[1],
                 document().replace(b'encoding="utf-8"', b'encoding="ISO-8859-1"'),
                 document().decode('utf-8-sig').encode('utf-16'),
                 document(TARGET[:-3] + b' arguments="&quot;unfinished" />')]
        for raw in cases:
            with self.subTest(raw=raw[:50]):
                self.target.write_bytes(raw)
                self.assertFalse(d.status(self.c, self.game)['console_supported'])
                with self.assertRaises(d.DeveloperConsoleError):
                    self.enable()
                self.assertEqual(self.read(), raw)
        self.assertFalse(self.c.data.exists())

    def test_symbolic_link_target_and_store_are_rejected(self):
        original = self.home/'original.xml'
        original.write_bytes(self.original)
        self.target.unlink()
        self.target.symlink_to(original)
        with self.assertRaises(d.DeveloperConsoleError):
            self.enable()
        self.assertEqual(original.read_bytes(), self.original)
        self.target.unlink()
        self.target.write_bytes(self.original)
        outside = self.home/'outside'
        outside.mkdir()
        self.c.data.symlink_to(outside)
        with self.assertRaises(d.DeveloperConsoleError):
            self.enable()
        self.assertEqual(list(outside.iterdir()), [])

    def test_lexical_traversal_and_outside_game_paths_are_rejected(self):
        for path in (str(self.home), str(self.folder/'..'/self.folder.name), 'relative/game'):
            with self.subTest(path=path):
                bad = dict(self.game, game_dir=path)
                with self.assertRaises(d.DeveloperConsoleError):
                    d.prepare(self.c, bad, True)
        self.assertEqual(self.read(), self.original)

    def test_oversized_nonregular_and_shared_link_are_rejected(self):
        self.target.write_bytes(b'x'*(d.MAX_XML + 1))
        with self.assertRaises(d.DeveloperConsoleError):
            self.enable()
        self.target.unlink()
        os.mkfifo(self.target)
        with self.assertRaises(d.DeveloperConsoleError):
            self.enable()
        self.target.unlink()
        original = self.home/'original.xml'
        original.write_bytes(self.original)
        os.link(original, self.target)
        with self.assertRaises(d.DeveloperConsoleError):
            self.enable()
        self.assertEqual(original.read_bytes(), self.original)

    def test_corrupt_backup_or_receipt_prevents_changes(self):
        self.enable()
        active = self.read()
        backup = next((self.store/'backups').glob('*.xml'))
        backup.write_bytes(b'corrupted')
        with self.assertRaises(d.DeveloperConsoleError):
            self.disable()
        self.assertEqual(self.read(), active)
        backup.write_bytes(self.original)
        (self.store/'receipt.json').write_text('{broken')
        with self.assertRaises(d.DeveloperConsoleError):
            self.disable()
        self.assertEqual(self.read(), active)

    def test_failure_before_xml_replacement_keeps_backup_and_can_retry(self):
        writer = d._atomic_write
        def fail(path, *args):
            if path == self.target:
                raise OSError('simulated failed replacement')
            return writer(path, *args)
        with mock.patch.object(d, '_atomic_write', side_effect=fail):
            with self.assertRaises(OSError):
                self.enable()
        self.assertEqual(self.read(), self.original)
        self.assertTrue((self.store/'receipt.json').is_file())
        self.assertEqual(next((self.store/'backups').glob('*.xml')).read_bytes(), self.original)
        self.enable()
        self.disable()
        self.assertEqual(self.read(), self.original)

    def test_interrupted_disable_retains_exact_restore_on_retry(self):
        originals = [self.original, document(TARGET[:-3] + b" arguments='  ' />")]
        for original in originals:
            with self.subTest(original=original):
                self.target.write_bytes(original)
                self.enable()
                enabled = self.read()
                receipt = (self.store/'receipt.json').read_bytes()
                writer = d._atomic_write

                def fail(path, *args):
                    if path == self.target:
                        raise OSError('simulated interrupted disable')
                    return writer(path, *args)

                with mock.patch.object(d, '_atomic_write', side_effect=fail):
                    with self.assertRaises(OSError):
                        self.disable()
                self.assertEqual(self.read(), enabled)
                self.assertEqual((self.store/'receipt.json').read_bytes(), receipt)
                self.assertTrue(d.status(self.c, self.game)['console_enabled'])
                self.disable()
                self.assertEqual(self.read(), original)
                self.assertFalse(d.status(self.c, self.game)['console_enabled'])

    def test_user_edit_after_interrupted_disable_is_preserved(self):
        self.enable()
        writer = d._atomic_write

        def fail(path, *args):
            if path == self.target:
                raise OSError('simulated interrupted disable')
            return writer(path, *args)

        with mock.patch.object(d, '_atomic_write', side_effect=fail):
            with self.assertRaises(OSError):
                self.disable()
        self.target.write_bytes(self.read().replace(b'autoquit="true"', b'custom="keep" autoquit="true"'))
        self.disable()
        self.assertEqual(self.read(), self.original.replace(b'autoquit="true"', b'custom="keep" autoquit="true"'))

    def test_concurrent_game_edit_is_preserved(self):
        writer = d._atomic_write
        changed = self.original.replace(b'<!-- Caf\xc3\xa9 -->', b'<!-- Concurrent user edit -->')
        def concurrent(path, *args):
            if path == self.target:
                self.target.write_bytes(changed)
            return writer(path, *args)
        with mock.patch.object(d, '_atomic_write', side_effect=concurrent):
            with self.assertRaisesRegex(d.DeveloperConsoleError, 'changed during preparation'):
                self.enable()
        self.assertEqual(self.read(), changed)

    def test_boolean_setting_is_required(self):
        for value in ('on', 1, 0, [], {}):
            with self.subTest(value=value), self.assertRaises(d.DeveloperConsoleError):
                d.prepare(self.c, self.game, value)
        self.assertFalse(self.c.data.exists())


if __name__ == '__main__':
    unittest.main()
