"""Updater handoff scenarios: fixture files, mocked ownership and no live Steam."""
import contextlib
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import daoctl
import steam_maintenance as sm

COMPLETE = '[2026-10-25 20:57:28] Update complete, launching Steam...\r\n[2026-10-25 20:57:28] Shutdown\r\n'
START = '[2026-10-25 20:57:29] Startup - updater built Oct 21 2026\r\n'
VERIFY = '[2026-10-25 20:57:29] Verification complete\r\n'


class SteamMaintenanceTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        environment = mock.patch.dict(os.environ, {"DAO_LAUNCHER_SESSION": ""})
        environment.start()
        self.addCleanup(environment.stop)
        self.c = daoctl.Controller(Path(tmp.name) / 'Private new install')
        self.steam = self.c.prefix / 'drive_c/Program Files (x86)/Steam/steam.exe'
        self.steam.parent.mkdir(parents=True)
        self.steam.write_bytes(b'MZ fixture - never execute')
        self.log = self.steam.parent / 'logs/bootstrap_log.txt'
        self.log.parent.mkdir()
        self.now = 1000.0
        self.clock = mock.patch.object(sm.time, 'time', side_effect=lambda: self.now)
        self.clock.start()
        self.addCleanup(self.clock.stop)
        for name in ('require_platform', 'require_contained_profile', 'require_runtime'):
            patcher = mock.patch.object(self.c, name)
            patcher.start()
            self.addCleanup(patcher.stop)
        patcher = mock.patch.object(sm.SteamMaintenance, '_inventory', return_value=[])
        self.inventory = patcher.start()
        self.addCleanup(patcher.stop)
        self.launch = mock.patch.object(self.c, 'steam_command', return_value={'ok': True}).start()
        self.addCleanup(mock.patch.stopall)
        self.m = sm.SteamMaintenance(self.c)

    def append(self, text):
        with self.log.open('a') as handle:
            handle.write(text)

    def ready_handoff(self):
        self.append(COMPLETE)
        result = self.m.maintain()
        self.assertEqual(result['action'], 'waiting')
        self.now += 11

    def test_multistage_updates_reopen_once_per_new_completed_handoff(self):
        self.m.arm()
        for index in range(3):
            self.append(START + '[time] Downloading update (239,614 of 239,614 KB)...\n')
            self.ready_handoff()
            self.now += 90  # respect the bounded increasing backoff
            self.assertEqual(self.m.maintain()['action'], 'reopened')
            self.assertEqual(self.launch.call_count, index + 1)
            for _ in range(3):
                self.m.maintain()
            self.assertEqual(self.launch.call_count, index + 1, 'duplicate polls must not reuse a consumed update')
        self.ready_handoff_after_limit()

    def ready_handoff_after_limit(self):
        self.append(START + COMPLETE)
        result = self.m.maintain()
        self.assertEqual(result['action'], 'disarmed')
        self.assertFalse(result['steam_maintenance_active'])
        self.assertEqual(self.launch.call_count, sm.MAX_REOPENS)

    def test_old_completed_log_and_touch_without_new_evidence_never_reopen(self):
        self.append(COMPLETE)
        self.m.arm()
        self.now += 100
        self.log.touch()
        for _ in range(3):
            self.m.maintain()
        self.launch.assert_not_called()

    def test_missing_partial_or_download_only_log_does_not_prove_handoff(self):
        self.m.arm()
        for text in ('', '[time] Download complete.\n', '[time] Update complete, launching Steam...\n', '[time] Shutdown'):
            self.append(text)
            self.now += 20
            self.m.maintain()
        self.launch.assert_not_called()

    def test_unreadable_preexisting_log_cannot_later_become_fresh_evidence(self):
        self.append(COMPLETE)
        with mock.patch.object(sm, '_read_log', return_value=None):
            self.m.arm()
        self.now += 100
        self.assertFalse(self.m.summary()['steam_maintenance_active'])
        self.m.maintain()
        self.launch.assert_not_called()

    def test_live_updater_is_never_stopped_or_reopened_even_after_grace(self):
        self.m.arm()
        self.append(COMPLETE)
        self.inventory.return_value = [(42, 1, r'C:\Program Files (x86)\Steam\steam.exe')]
        self.now += 180
        with mock.patch.object(self.c, 'stop') as stop:
            result = self.m.maintain()
        self.assertIn('still running', result['message'])
        self.launch.assert_not_called()
        stop.assert_not_called()

    def test_ready_ui_disarms_then_intentional_close_cannot_reopen(self):
        self.m.arm()
        self.append(COMPLETE)
        self.inventory.return_value = [(9, 1, r'C:\Program Files (x86)\Steam\bin\cef\steamwebhelper.exe')]
        self.assertTrue(self.m.summary()['steam_maintenance_active'], 'read-only status must permit the cleanup command')
        self.assertEqual(self.m.maintain()['action'], 'disarmed')
        self.inventory.return_value = []
        self.now += 100
        self.append(COMPLETE)
        self.m.maintain()
        self.launch.assert_not_called()

    def test_started_then_closed_between_polls_invalidates_old_handoff(self):
        self.m.arm()
        self.append(COMPLETE + START + VERIFY + '[time] Shutdown\n')
        for _ in range(3):
            self.now += 30
            self.m.maintain()
        self.launch.assert_not_called()

    def test_installers_games_and_unclassified_own_processes_block(self):
        for command in ('SteamSetup.exe', 'DAOrigins.exe', 'DAOriginsConfig.exe',
                        'msiexec.exe /i prerequisite', 'DXSETUP.exe', 'unrecognized.exe',
                        str(self.c.launcher)):
            with self.subTest(command=command):
                self.m.arm()
                self.append(COMPLETE)
                self.inventory.return_value = [(8, 1, command)]
                self.now += 50
                self.m.maintain()
                self.launch.assert_not_called()
        self.inventory.return_value = []

    def test_unavailable_process_visibility_blocks_and_resets_absence_grace(self):
        self.m.arm()
        self.ready_handoff()
        self.inventory.side_effect = ValueError('Cannot attribute processes')
        self.assertFalse(self.m.summary()['steam_maintenance_active'])
        self.assertEqual(self.m.maintain()['action'], 'blocked')
        self.inventory.side_effect = None
        self.inventory.return_value = []
        self.assertEqual(self.m.maintain()['action'], 'waiting')
        self.launch.assert_not_called()
        self.now += 11
        self.assertEqual(self.m.maintain()['action'], 'reopened')

    def test_process_or_log_activity_during_final_recheck_prevents_launch(self):
        for kind in ('process', 'log'):
            with self.subTest(kind=kind):
                self.inventory.side_effect = None
                self.inventory.return_value = []
                self.m.arm()
                self.ready_handoff()
                count = 0
                def inventory():
                    nonlocal count
                    count += 1
                    if count == 2:
                        if kind == 'process':
                            return [(8, 1, 'steam.exe')]
                        self.append(START + VERIFY)
                    return []
                self.inventory.side_effect = inventory
                self.assertEqual(self.m.maintain()['action'], 'waiting')
                self.launch.assert_not_called()

    def test_expired_corrupt_and_unarmed_generations_never_launch(self):
        self.append(COMPLETE)
        for record in (None, [], {'armed': True}, {'schema_version': 1, 'armed': False}):
            self.c.save_state(**{sm.KEY: record})
            self.m.maintain()
        self.m.arm()
        self.append(COMPLETE)
        self.now += sm.LIFETIME + 1
        self.assertEqual(self.m.maintain()['action'], 'disarmed')
        self.launch.assert_not_called()

    def test_rotation_truncation_and_external_log_link_fail_closed(self):
        for kind in ('rotation', 'truncation', 'external'):
            with self.subTest(kind=kind):
                if self.log.exists() or self.log.is_symlink():
                    self.log.unlink()
                self.append('old log\n' * 20)
                self.m.arm()
                if kind == 'rotation':
                    self.log.rename(self.log.with_name('old.log'))
                    self.append(COMPLETE)
                elif kind == 'truncation':
                    self.log.write_text('short\n')
                else:
                    outside = self.c.root / 'outside.log'
                    outside.write_text(COMPLETE)
                    self.log.unlink()
                    self.log.symlink_to(outside)
                self.now += 50
                self.m.maintain()
                self.m.maintain()
                self.launch.assert_not_called()

    def test_bounded_tail_can_follow_large_update_without_reading_accounts(self):
        self.m.arm()
        self.append('progress\n' * 20000 + COMPLETE)
        log = sm._read_log(self.c, self.steam)
        self.assertLessEqual(len(log['raw']), sm.TAIL_LIMIT)
        self.assertGreater(log['start'], 0)
        self.assertEqual(self.m.maintain()['action'], 'waiting')
        self.now += 11
        self.assertEqual(self.m.maintain()['action'], 'reopened')

    def test_attempt_is_recorded_before_launch_and_failure_disarms(self):
        self.m.arm()
        self.ready_handoff()
        def failed(*_):
            state = self.c.state()[sm.KEY]
            self.assertEqual(state['attempts'], 1)
            self.assertEqual(state['cursor'], self.log.stat().st_size)
            raise daoctl.DAOError('fixture launch failed')
        self.launch.side_effect = failed
        self.assertEqual(self.m.maintain()['action'], 'disarmed')
        self.m.maintain()
        self.assertEqual(self.launch.call_count, 1)

    def test_status_is_read_only_and_stop_disarms_before_any_stop_error(self):
        self.m.arm()
        self.append(COMPLETE)
        before = self.c.state_file.read_bytes()
        self.assertTrue(self.m.summary()['steam_maintenance_active'])
        self.assertTrue(self.m.pending_handoff(self.steam))
        self.assertEqual(before, self.c.state_file.read_bytes())
        with mock.patch.object(self.c, 'require_runtime', side_effect=daoctl.DAOError('fixture missing')):
            with self.assertRaises(daoctl.DAOError):
                self.c.stop()
        self.assertFalse(self.m.summary()['steam_maintenance_active'])
        self.m.maintain()
        self.launch.assert_not_called()

    def test_only_explicit_open_arms_and_game_actions_cancel(self):
        self.c.open_steam()
        self.assertTrue(self.m.summary()['steam_maintenance_active'])
        self.c.install_game('47810')
        self.assertFalse(self.m.summary()['steam_maintenance_active'])
        self.c.open_steam()
        with self.assertRaises(daoctl.DAOError):
            self.c.play('47810')
        self.assertFalse(self.m.summary()['steam_maintenance_active'])

    def test_status_visibility_failure_explains_pause_without_handoff_wait_dead_end(self):
        self.m.arm()
        self.append(COMPLETE)
        self.inventory.side_effect = ValueError('process attribution unavailable')
        with mock.patch.object(daoctl, 'platform_status', return_value={'platform_supported': True, 'rosetta_ready': True}), \
                mock.patch.object(self.c, 'runtime_ready', return_value=True), \
                mock.patch.object(self.c, 'prefix_ready', return_value=True), \
                mock.patch.object(self.c, 'processes', return_value=[]):
            before = self.c.state_file.read_bytes()
            result = self.c.status()
        self.assertEqual(result['phase'], 'steam_startup_blocked')
        self.assertFalse(result['steam_maintenance_active'])
        self.assertIn('Refresh', result['message'])
        self.assertIn('Open Steam', result['message'])
        self.assertEqual(before, self.c.state_file.read_bytes())
        self.launch.assert_not_called()

    def test_closed_window_disarms_without_stopping_steam_or_another_owner(self):
        first_id = '11111111-1111-4111-8111-111111111111'
        second_id = '22222222-2222-4222-8222-222222222222'
        with mock.patch.dict(os.environ, {'DAO_LAUNCHER_SESSION': first_id}):
            first = sm.SteamMaintenance(self.c)
            first.arm()
            self.append(COMPLETE)
        before = self.c.state_file.read_bytes()
        with mock.patch.dict(os.environ, {'DAO_LAUNCHER_SESSION': second_id}):
            second = sm.SteamMaintenance(self.c)
            self.assertFalse(second.summary()['steam_maintenance_active'])
            self.assertFalse(second.pending_handoff(self.steam))
            second.maintain()
            second.cancel_request()
        self.assertEqual(before, self.c.state_file.read_bytes(), 'another window cannot resume or cancel the owner generation')
        with mock.patch.object(self.c, 'stop') as stop:
            first.cancel_request()
        stop.assert_not_called()
        self.assertFalse(first.summary()['steam_maintenance_active'])
        first.maintain()
        self.launch.assert_not_called()

    def test_explicit_stop_in_another_window_disarms_prefix_recovery(self):
        self.m.arm()
        with mock.patch.dict(os.environ, {'DAO_LAUNCHER_SESSION': '33333333-3333-4333-8333-333333333333'}), \
                mock.patch.object(self.c, 'require_runtime', side_effect=daoctl.DAOError('fixture missing')):
            with self.assertRaises(daoctl.DAOError):
                self.c.stop()
        self.assertFalse(self.m.summary()['steam_maintenance_active'])

    def test_session_cancel_cli_is_locked_and_never_stops_runtime(self):
        self.m.arm()
        events = []
        @contextlib.contextmanager
        def operation():
            events.append('lock')
            yield
            events.append('unlock')
        with mock.patch.object(daoctl, 'project_root', return_value=self.c.root), \
                mock.patch.object(daoctl, 'Controller', return_value=self.c), \
                mock.patch.object(self.c, 'operation', side_effect=operation), \
                mock.patch.object(self.c, 'stop') as stop, \
                contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(daoctl.main(['steam-maintenance-cancel']), 0)
        self.assertEqual(events, ['lock', 'unlock'])
        stop.assert_not_called()
        self.assertFalse(self.m.summary()['steam_maintenance_active'])
        self.launch.assert_not_called()

    def test_invalid_session_identifier_never_arms(self):
        with mock.patch.dict(os.environ, {'DAO_LAUNCHER_SESSION': 'invalid-session'}):
            with self.assertRaisesRegex(ValueError, 'session identifier'):
                sm.SteamMaintenance(self.c)
        self.assertFalse(self.c.state_file.exists())

    def test_cli_maintain_dispatch_is_locked_and_does_not_arm(self):
        events = []
        @contextlib.contextmanager
        def operation():
            events.append('lock')
            yield
            events.append('unlock')
        with mock.patch.object(daoctl, 'project_root', return_value=self.c.root), \
                mock.patch.object(daoctl, 'Controller', return_value=self.c), \
                mock.patch.object(self.c, 'operation', side_effect=operation), \
                mock.patch.object(sm.SteamMaintenance, 'maintain', side_effect=lambda: events.append('maintain') or {'ok': True}), \
                mock.patch.object(sm.SteamMaintenance, 'arm') as arm, \
                contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(daoctl.main(['steam-maintain']), 0)
        self.assertEqual(events, ['lock', 'maintain', 'unlock'])
        arm.assert_not_called()
