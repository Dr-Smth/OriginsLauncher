"""Automatic DA:O audio orchestration; all processes and managers are mocked."""
import contextlib
import hashlib
import io
import json
from pathlib import Path
import sys
import types
import unittest
from unittest import mock
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import daoctl
import test_controller as fixtures

class BackendError(RuntimeError):pass

class AudioControllerTests(unittest.TestCase):
    steam=fixtures.ControllerTests.steam
    game=fixtures.ControllerTests.game
    validation=fixtures.ControllerTests.validation
    def patch(self,p):
        value=p.start();self.addCleanup(p.stop);return value
    def setUp(self):
        fixtures.ControllerTests.setUp(self)
        self.game();self.selected=daoctl.discover_games(self.c.prefix)[0]
        self.backend=types.ModuleType('audio_fix');self.backend.AudioFixError=BackendError
        self.backend.status=mock.Mock(return_value=self.state())
        self.backend.set_enabled=mock.Mock(return_value={'ok':True})
        self.patch(mock.patch.dict(sys.modules,{'audio_fix':self.backend}))
        self.memory=types.ModuleType('large_address');self.memory.LargeAddressError=BackendError
        self.memory.active_wine_processes=mock.Mock(return_value=[])
        self.memory.status=mock.Mock(return_value={'laa_supported':False,'laa_enabled':False,'laa_managed':False})
        self.patch(mock.patch.dict(sys.modules,{'large_address':self.memory}))
        self.processes=self.patch(mock.patch.object(self.c,'processes',return_value=[]))
        self.steam_command=self.patch(mock.patch.object(self.c,'steam_command',return_value={'ok':True}))
        self.stop=self.patch(mock.patch.object(self.c,'stop',return_value={'ok':True}))
        self.patch(mock.patch.object(self.c,'steam_startup',return_value='client_running'))
        self.patch(mock.patch.object(daoctl.time,'sleep'))
        self.patch(mock.patch('steam_maintenance.SteamMaintenance.cancel',return_value=None))
        self.patch(mock.patch.object(daoctl.subprocess,'Popen',side_effect=AssertionError('Unexpected process launch')))
        self.patch(mock.patch.object(daoctl.subprocess,'run',side_effect=AssertionError('Unexpected process execution')))
    @staticmethod
    def state(supported=True,enabled=False,managed=False,pending=False):
        return dict(audio_fix_supported=supported,audio_fix_enabled=enabled,audio_fix_managed=managed,
            audio_fix_pending=pending,audio_fix_message='Audio component could not be verified')
    def test_recognized_fresh_game_enables_automatically(self):
        self.c.prepare_audio_fix(self.selected)
        self.backend.set_enabled.assert_called_once_with(self.c,self.selected,True)
        self.stop.assert_not_called();self.steam_command.assert_not_called()
    def test_enabled_committed_state_does_not_inspect_or_restart_session(self):
        self.backend.status.return_value=self.state(enabled=True,managed=True)
        self.c.prepare_audio_fix(self.selected)
        self.memory.active_wine_processes.assert_not_called();self.backend.set_enabled.assert_not_called()
    def test_unknown_or_modded_unmanaged_game_skips_automatically(self):
        self.backend.status.return_value=self.state(supported=False)
        self.c.prepare_audio_fix(self.selected)
        self.memory.active_wine_processes.assert_not_called();self.backend.set_enabled.assert_not_called()
    def test_pending_supported_state_is_reconciled_even_if_dll_looks_enabled(self):
        self.backend.status.return_value=self.state(enabled=True,managed=True,pending=True)
        self.c.prepare_audio_fix(self.selected)
        self.backend.set_enabled.assert_called_once_with(self.c,self.selected,True)
    def test_owned_unsupported_state_is_removed_or_reconciled(self):
        for enabled,pending in ((True,False),(False,True)):
            self.backend.set_enabled.reset_mock()
            self.backend.status.return_value=self.state(supported=False,enabled=enabled,managed=True,pending=pending)
            self.c.prepare_audio_fix(self.selected)
            self.backend.set_enabled.assert_called_once_with(self.c,self.selected,False)
    def test_unsupported_owned_already_disabled_needs_no_shutdown(self):
        self.backend.status.return_value=self.state(supported=False,managed=True)
        self.c.prepare_audio_fix(self.selected)
        self.memory.active_wine_processes.assert_not_called();self.backend.set_enabled.assert_not_called()
    def test_active_game_or_unknown_program_prevents_any_shutdown_or_apply(self):
        for image in ('DAOrigins.exe','DAOriginsLauncher.exe','DXSETUP.exe','OtherProgram.exe'):
            self.memory.active_wine_processes.return_value=[(100,1,image)]
            with self.assertRaisesRegex(daoctl.DAOError,'Close the game'):self.c.prepare_audio_fix(self.selected)
            self.stop.assert_not_called();self.steam_command.assert_not_called();self.backend.set_enabled.assert_not_called()
    def test_scoped_steam_exit_precedes_audio_install(self):
        self.steam()
        self.memory.active_wine_processes.side_effect=[[(100,1,'steam.exe'),(101,1,'services.exe')],
            [(101,1,'services.exe')],[(101,1,'services.exe')],[]]
        events=[]
        self.steam_command.side_effect=lambda *args:events.append('steam shutdown') or {'ok':True}
        self.stop.side_effect=lambda:events.append('session stop') or {'ok':True}
        self.backend.set_enabled.side_effect=lambda *args:events.append('install') or {'ok':True}
        self.c.prepare_audio_fix(self.selected)
        self.steam_command.assert_called_once_with(['-shutdown'],'audio-mode-steam-shutdown')
        self.assertEqual(events,['steam shutdown','session stop','install'])
    def test_process_visibility_failure_never_means_stopped(self):
        self.memory.active_wine_processes.side_effect=BackendError('Cannot inspect owned session')
        with self.assertRaisesRegex(daoctl.DAOError,'Cannot inspect'):self.c.prepare_audio_fix(self.selected)
        self.backend.set_enabled.assert_not_called();self.stop.assert_not_called()
    def test_backend_transaction_failure_is_controller_error(self):
        for error in (BackendError('Changed owned DLL'),OSError('Write failed')):
            self.backend.set_enabled.side_effect=error
            with self.assertRaises(daoctl.DAOError):self.c.prepare_audio_fix(self.selected)
    def test_automatic_prepare_runs_under_lock_before_display_and_launch(self):
        events=[]
        @contextlib.contextmanager
        def operation():
            events.append('lock')
            try:yield
            finally:events.append('unlock')
        def prepare(game):
            self.assertEqual(game['appid'],'47810');self.assertEqual(events,['lock']);events.append('audio')
        display=types.ModuleType('display_settings');display.DisplaySettings=mock.Mock()
        display.DisplaySettings.return_value.prepare_for_play.side_effect=lambda *args:events.append('display')
        self.steam_command.side_effect=lambda *args:events.append('launch') or {'ok':True}
        with mock.patch.dict(sys.modules,{'display_settings':display}), \
             mock.patch.object(daoctl,'project_root',return_value=self.root), \
             mock.patch.object(daoctl,'Controller',return_value=self.c), \
             mock.patch.object(self.c,'operation',side_effect=operation), \
             mock.patch.object(self.c,'prepare_audio_fix',side_effect=prepare), \
             contextlib.redirect_stdout(io.StringIO()) as out:
            code=daoctl.main(['play','--appid','47810','--preset','fullscreen-retina'])
        self.assertEqual(code,0,out.getvalue());self.assertEqual(events,['lock','audio','display','launch','unlock'])
    def test_audio_failure_prevents_display_change_and_launch(self):
        display=types.ModuleType('display_settings');display.DisplaySettings=mock.Mock()
        with mock.patch.dict(sys.modules,{'display_settings':display}), \
             mock.patch.object(self.c,'prepare_audio_fix',side_effect=daoctl.DAOError('Changed owned DLL')), \
             mock.patch.object(self.c,'save_state') as save:
            with self.assertRaisesRegex(daoctl.DAOError,'Changed owned DLL'):self.c.play('47810',preset='fullscreen-retina')
        display.DisplaySettings.assert_not_called();self.steam_command.assert_not_called();save.assert_not_called()
    def test_baseline_validation_does_not_validate_new_audio(self):
        self.validation()
        self.backend.status.return_value=self.state(supported=False)
        self.assertTrue(self.c.compatibility_verified(self.selected))
        self.backend.status.return_value=self.state(enabled=True,managed=True)
        self.assertFalse(self.c.compatibility_verified(self.selected))
    def test_exact_audio_identity_validates_only_matching_file_and_mode(self):
        report,record,_,exe=self.validation()
        audio=exe.with_name('dsound.dll');audio.write_bytes(b'verified fixture audio')
        self.backend.status.return_value=self.state(enabled=True,managed=True)
        identity=dict(enabled=True,component_sha256=hashlib.sha256(audio.read_bytes()).hexdigest())
        record['audio_identity']=identity;report.write_text(json.dumps(record))
        self.assertTrue(self.c.compatibility_verified(self.selected))
        for invalid in ({},dict(identity,enabled=1),dict(identity,enabled=False),dict(identity,component_sha256='0'*64)):
            record['audio_identity']=invalid;report.write_text(json.dumps(record))
            self.assertFalse(self.c.compatibility_verified(self.selected))
        record['audio_identity']=identity;report.write_text(json.dumps(record))
        audio.write_bytes(b'changed component')
        self.assertFalse(self.c.compatibility_verified(self.selected))
    def test_audio_identity_cannot_survive_off_pending_or_unsupported_owned_state(self):
        report,record,_,exe=self.validation();audio=exe.with_name('dsound.dll');audio.write_bytes(b'audio')
        record['audio_identity']=dict(enabled=True,component_sha256=hashlib.sha256(audio.read_bytes()).hexdigest())
        report.write_text(json.dumps(record))
        for status in (self.state(enabled=False,managed=True),self.state(enabled=True,managed=True,pending=True),
                       self.state(supported=False,enabled=True,managed=True)):
            self.backend.status.return_value=status
            self.assertFalse(self.c.compatibility_verified(self.selected))
    def test_memory_and_audio_share_one_clean_session_before_launch(self):
        self.memory.status.return_value={'laa_supported':True,'laa_enabled':False,'laa_managed':False}
        self.memory.set_enabled=mock.Mock()
        running=[(100,1,'steam.exe'),(101,1,'services.exe')];events=[]
        self.memory.active_wine_processes.side_effect=lambda c:list(running)
        def steam(arguments,purpose):
            if arguments==['-shutdown']:
                events.append('shutdown');running[:]=[(101,1,'services.exe')]
            else:events.append('launch')
            return {'ok':True}
        def stop():events.append('stop');running.clear();return {'ok':True}
        self.steam_command.side_effect=steam;self.stop.side_effect=stop
        self.memory.set_enabled.side_effect=lambda *args:events.append('memory')
        self.backend.set_enabled.side_effect=lambda *args:events.append('audio')
        self.c.play('47810',large_address_aware=True)
        self.assertEqual(events,['shutdown','stop','memory','audio','launch'])
        self.stop.assert_called_once_with()
        self.memory.set_enabled.assert_called_once_with(self.c,True)
        self.backend.set_enabled.assert_called_once_with(self.c,self.selected,True)
    def test_running_game_does_not_reconfigure_or_launch_duplicate(self):
        self.processes.return_value=[(100,1,'DAOrigins.exe')]
        with mock.patch.object(self.c,'prepare_audio_fix') as prepare:
            result=self.c.play('47810')
        self.assertIn('already running',result['message']);prepare.assert_not_called();self.steam_command.assert_not_called()

if __name__=='__main__':unittest.main()
