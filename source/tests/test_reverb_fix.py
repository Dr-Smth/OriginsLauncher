"""Temporary-file transactions and guards; no real Wine, game, or registry."""
import hashlib
import json
import shutil
from pathlib import Path
import sys
import tempfile
import types
import unittest
from unittest import mock
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import reverb_fix as a


def digest(raw):return hashlib.sha256(raw).hexdigest()


class ReverbFixTests(unittest.TestCase):
    def setUp(self):
        temp=tempfile.TemporaryDirectory();self.addCleanup(temp.cleanup)
        self.home=Path(temp.name).resolve();root=self.home/'environment'
        runtime=root/'runtime/DAO Runtime.app';contents=runtime/'Contents';prefix=contents/'SharedSupport/prefix'
        self.c=types.SimpleNamespace(root=root,runtime=runtime,contents=contents,prefix=prefix,data=root/'data')
        exe=prefix/'drive_c/Program Files (x86)/Steam/steamapps/common/DAO/bin_ship/DAOrigins.exe'
        exe.parent.mkdir(parents=True);exe.write_bytes(b'MZ game original');exe.with_name('fmodex.dll').write_bytes(b'MZ original FMOD');exe.with_name('fmod_event.dll').write_bytes(b'MZ original FMOD event')
        self.game=dict(appid='47810',exe=str(exe));self.paths=a._paths(self.c,self.game)
        self.dsound=exe.with_name('dsound.dll');self.dsound.write_bytes(b'MZ existing timing safeguards')
        self.initial=(b'WINE REGISTRY Version 2\n\n[Software\\\\Wine\\\\AppDefaults\\\\DAOrigins.exe\\\\DllOverrides]\n'
                      b'"dinput8"="native,builtin"\n"dsound"="native"\n\n[Unrelated]\n"value"="keep"\n')
        self.paths['registry'].write_bytes(self.initial)
        self.component=self.home/'reverb-compat';self.component.mkdir();self.payload=b'MZ owned verified audio DLL'
        (self.component/'winmm.dll').write_bytes(self.payload)
        rel='SharedSupport/wine/lib/wine/i386-windows/winmm.dll';original=b'MZ builtin winmm'
        path=contents/rel;path.parent.mkdir(parents=True);path.write_bytes(original)
        self.manifest=dict(schema=1,id='origins-reverb',version='1.0.0-beta.1',policy_revision=1,automatic_game_only=True,changes_buffer_size=False,
            dll=dict(file='winmm.dll',sha256=digest(self.payload),bytes=len(self.payload)),
            game=dict(file='DAOrigins.exe',sha256=digest(exe.read_bytes())),
            fmod=dict(file='fmodex.dll',sha256=digest(exe.with_name('fmodex.dll').read_bytes())),
            fmod_event=dict(file='fmod_event.dll',sha256=digest(exe.with_name('fmod_event.dll').read_bytes())),
            runtime=dict(base='runtime_contents',files=[dict(path=rel,sha256=digest(original))]),
            status_directory='drive_c/dao-support/origins-reverb/status')
        self.save_manifest()
        p=mock.patch.object(a,'_component_dir',return_value=self.component);p.start();self.addCleanup(p.stop)
        p=mock.patch.object(a.large_address,'active_wine_processes',return_value=[]);self.process=p.start();self.addCleanup(p.stop)
    def save_manifest(self):(self.component/'component.json').write_text(json.dumps(self.manifest))
    def enable(self):return a.set_enabled(self.c,self.game,True)
    def disable(self):return a.set_enabled(self.c,self.game,False)
    def test_readonly_default_and_idempotent_disabled(self):
        files=sorted(str(p)for p in self.home.rglob('*'))
        s=a.status(self.c,self.game)
        self.assertTrue(s['reverb_fix_supported']);self.assertFalse(s['reverb_fix_enabled']);self.assertFalse(s['reverb_fix_pending'])
        self.assertFalse(self.disable()['changed']);self.process.assert_not_called()
        self.assertEqual(files,sorted(str(p)for p in self.home.rglob('*')))
    def test_enable_disable_preserves_game_runtime_and_other_registry_settings(self):
        preserved={p:p.read_bytes()for p in (self.paths['exe'],self.paths['fmod'],self.paths['fmod_event'],self.dsound,self.c.contents/self.manifest['runtime']['files'][0]['path'])}
        self.assertTrue(self.enable()['reverb_fix_enabled'])
        self.assertEqual(self.paths['target'].read_bytes(),self.payload)
        self.assertEqual(self.paths['backup'].read_bytes(),self.initial)
        self.paths['registry'].write_bytes(self.paths['registry'].read_bytes()+b'"later"="keep too"\n')
        self.assertFalse(self.disable()['reverb_fix_enabled']);self.assertFalse(self.paths['target'].exists())
        self.assertEqual(self.paths['registry'].read_bytes(),self.initial+b'"later"="keep too"\n')
        for p,raw in preserved.items():self.assertEqual(p.read_bytes(),raw)
        self.assertTrue(self.enable()['reverb_fix_enabled'])
        self.process.reset_mock();self.assertFalse(self.enable()['changed']);self.process.assert_not_called()
    def test_third_party_dll_and_override_are_refused_even_when_identical(self):
        for raw in (b'MZ somebody else',self.payload):
            self.paths['target'].write_bytes(raw)
            with self.assertRaises(a.ReverbFixError):self.enable()
            self.assertEqual(self.paths['target'].read_bytes(),raw);self.paths['target'].unlink()
        self.paths['registry'].write_bytes(a._patch_registry(self.initial,True))
        with self.assertRaises(a.ReverbFixError):self.enable()
        self.assertFalse(self.paths['receipt'].exists())
    def test_global_and_duplicate_override_rejected(self):
        for raw in (self.initial+b'\n[Software\\\\Wine\\\\DllOverrides]\n"winmm"="builtin"\n',
                    a._patch_registry(self.initial,True).replace(b'"winmm"="native,builtin"',b'"winmm"="native,builtin"\n"WINMM"="native,builtin"')):
            self.paths['registry'].write_bytes(raw)
            with self.assertRaises(a.ReverbFixError):self.enable()
            self.assertEqual(self.paths['registry'].read_bytes(),raw)
    def test_manifest_cannot_enable_private_or_block_changing_variant(self):
        for key,bad in (('automatic_game_only',False),('changes_buffer_size',True)):
            original=self.manifest[key];self.manifest[key]=bad;self.save_manifest()
            with self.assertRaisesRegex(a.ReverbFixError,'unsupported'):self.enable()
            self.assertFalse(self.paths['target'].exists());self.manifest[key]=original;self.save_manifest()
    def test_aliased_winmm_overrides_are_preserved(self):
        for section in (a.SECTION,a.GLOBAL_SECTION):
            raw=self.initial+('\n['+section.replace('\\','\\\\')+']\n"winmm.dll"="native,builtin"\n').encode()
            self.paths['registry'].write_bytes(raw)
            with self.assertRaises(a.ReverbFixError):self.enable()
            self.assertEqual(self.paths['registry'].read_bytes(),raw)
            self.assertFalse(self.paths['target'].exists())
    def test_never_writes_private_trial_configuration_or_other_audio_state(self):
        ini=self.paths['exe'].with_name('origins-fmod-blocks-trial.ini');ini.write_bytes(b'preserve unknown configuration')
        receipt=self.c.data/'audio-fix/receipt.json';receipt.parent.mkdir(parents=True);receipt.write_bytes(b'original timing receipt')
        self.enable();self.disable()
        self.assertEqual(ini.read_bytes(),b'preserve unknown configuration')
        self.assertEqual(receipt.read_bytes(),b'original timing receipt')
        self.assertEqual(self.dsound.read_bytes(),b'MZ existing timing safeguards')
        self.assertIn(b'"dsound"="native"',self.paths['registry'].read_bytes())
    def test_game_fmod_runtime_and_payload_hashes_are_required(self):
        for path in (self.paths['exe'],self.paths['fmod'],self.paths['fmod_event'],self.c.contents/self.manifest['runtime']['files'][0]['path'],self.component/'winmm.dll'):
            raw=path.read_bytes();path.write_bytes(b'changed')
            self.assertFalse(a.status(self.c,self.game)['reverb_fix_supported'])
            with self.assertRaises(a.ReverbFixError):self.enable()
            self.assertFalse(self.paths['receipt'].exists());path.write_bytes(raw)
    def test_active_or_uninspectable_session_prevents_preparation(self):
        self.process.return_value=[(1,0,'steam.exe')]
        with self.assertRaisesRegex(a.ReverbFixError,'Close Dragon Age'):self.enable()
        self.assertFalse(self.paths['store'].exists())
        self.process.side_effect=a.large_address.LargeAddressError('uninspectable')
        with self.assertRaisesRegex(a.ReverbFixError,'inspect'):self.enable()
    def test_session_appearing_after_receipt_prevents_game_mutation(self):
        self.process.side_effect=[[],[(1,0,'steam.exe')]]
        with self.assertRaises(a.ReverbFixError):self.enable()
        self.assertTrue(self.paths['receipt'].exists());self.assertFalse(self.paths['target'].exists())
        self.process.side_effect=None;self.process.return_value=[]
        self.assertTrue(a.status(self.c,self.game)['reverb_fix_pending'])
        self.assertTrue(self.enable()['reverb_fix_enabled'])
    def test_interrupted_install_can_finish_or_roll_back(self):
        original=a._write
        def fail_registry(c,path,raw,**kwargs):
            if path==self.paths['registry']:raise OSError('simulated interruption')
            return original(c,path,raw,**kwargs)
        with mock.patch.object(a,'_write',side_effect=fail_registry):
            with self.assertRaises(OSError):self.enable()
        self.assertEqual(self.paths['target'].read_bytes(),self.payload)
        self.assertEqual(self.paths['registry'].read_bytes(),self.initial)
        self.assertTrue(a.status(self.c,self.game)['reverb_fix_pending'])
        self.assertFalse(self.disable()['reverb_fix_pending']);self.assertFalse(self.paths['target'].exists())
        with mock.patch.object(a,'_write',side_effect=fail_registry):
            with self.assertRaises(OSError):self.enable()
        self.assertTrue(self.enable()['reverb_fix_enabled'])
    def test_dll_replacement_before_override_is_not_activated(self):
        calls=0
        def stopped(c):
            nonlocal calls
            calls+=1
            if calls==4:self.paths['target'].write_bytes(b'user replacement')
        with mock.patch.object(a,'_stopped',side_effect=stopped):
            with self.assertRaisesRegex(a.ReverbFixError,'override was not added'):self.enable()
        self.assertEqual(self.paths['registry'].read_bytes(),self.initial)
        self.assertEqual(self.paths['target'].read_bytes(),b'user replacement')
    def test_registry_change_during_install_is_preserved_then_reconciled(self):
        calls=0;changed=self.initial+b'"concurrent"="preserve"\n'
        def stopped(c):
            nonlocal calls
            calls+=1
            if calls==4:self.paths['registry'].write_bytes(changed)
        with mock.patch.object(a,'_stopped',side_effect=stopped):
            with self.assertRaisesRegex(a.ReverbFixError,'changed during'):self.enable()
        self.assertEqual(self.paths['registry'].read_bytes(),changed)
        self.assertTrue(a.status(self.c,self.game)['reverb_fix_pending'])
        self.assertTrue(self.enable()['reverb_fix_enabled'])
        self.disable();self.assertEqual(self.paths['registry'].read_bytes(),changed)
    def test_final_receipt_interruption_reconciles_actual_state(self):
        original=a._save;calls=0
        def fail_final(*args):
            nonlocal calls
            calls+=1
            if calls==2:raise OSError('interrupted before final receipt')
            return original(*args)
        with mock.patch.object(a,'_save',side_effect=fail_final):
            with self.assertRaises(OSError):self.enable()
        s=a.status(self.c,self.game);self.assertTrue(s['reverb_fix_enabled']);self.assertTrue(s['reverb_fix_pending'])
        self.assertFalse(self.enable()['reverb_fix_pending'])
    def test_interrupted_disable_preserves_then_removes_owned_dll(self):
        self.enable();self.process.side_effect=[[],[],[],[(1,0,'steam.exe')]]
        with self.assertRaises(a.ReverbFixError):self.disable()
        self.assertIsNone(a._registry_value(self.paths['registry'].read_bytes()))
        self.assertTrue(self.paths['target'].exists())
        self.process.side_effect=None;self.process.return_value=[]
        self.assertFalse(self.disable()['reverb_fix_pending']);self.assertFalse(self.paths['target'].exists())
    def test_user_changed_owned_dll_or_override_is_not_replaced_or_removed(self):
        self.enable();self.paths['target'].write_bytes(b'user replacement')
        with self.assertRaises(a.ReverbFixError):self.disable()
        self.assertEqual(self.paths['target'].read_bytes(),b'user replacement')
        self.paths['target'].write_bytes(self.payload)
        self.paths['registry'].write_bytes(self.paths['registry'].read_bytes().replace(b'"winmm"="native,builtin"',b'"winmm"="builtin"'))
        with self.assertRaises(a.ReverbFixError):self.disable()
        self.assertTrue(self.paths['target'].exists())
    def test_owned_disable_allowed_after_runtime_game_update(self):
        self.enable();self.paths['exe'].write_bytes(b'updated game')
        s=a.status(self.c,self.game);self.assertFalse(s['reverb_fix_supported']);self.assertTrue(s['reverb_fix_enabled'])
        self.assertFalse(self.disable()['reverb_fix_enabled']);self.assertEqual(self.paths['exe'].read_bytes(),b'updated game')
    def test_symlinks_and_differently_cased_mods_refused(self):
        elsewhere=self.home/'outside';elsewhere.write_bytes(self.payload)
        self.paths['target'].symlink_to(elsewhere)
        with self.assertRaises(a.ReverbFixError):self.enable()
        self.paths['target'].unlink();self.paths['target'].with_name('WINMM.DLL').write_bytes(self.payload)
        with self.assertRaises(a.ReverbFixError):self.enable()
        self.assertEqual(elsewhere.read_bytes(),self.payload)
    def test_recovery_material_tampering_is_refused(self):
        self.enable()
        for path in (self.paths['payload'],self.paths['backup']):
            raw=path.read_bytes();path.write_bytes(b'changed')
            with self.assertRaises(a.ReverbFixError):self.disable()
            self.assertTrue(self.paths['target'].exists());path.write_bytes(raw)
    def other_edition(self, supported=True):
        folder=self.c.prefix/'drive_c/Program Files (x86)/Steam/steamapps/common/DAO Base/bin_ship'
        folder.mkdir(parents=True)
        (folder/'DAOrigins.exe').write_bytes(self.paths['exe'].read_bytes() if supported else b'unsupported base version')
        (folder/'fmodex.dll').write_bytes(self.paths['fmod'].read_bytes())
        (folder/'fmod_event.dll').write_bytes(self.paths['fmod_event'].read_bytes())
        return dict(appid='17450',exe=str(folder/'DAOrigins.exe'))
    def test_alternating_verified_editions_transfers_single_owned_rule(self):
        other=self.other_edition();target=Path(other['exe']).with_name('winmm.dll')
        self.enable()
        status=a.status(self.c,other);self.assertTrue(status['reverb_fix_supported']);self.assertTrue(status['reverb_fix_pending']);self.assertFalse(status['reverb_fix_enabled'])
        self.assertTrue(a.set_enabled(self.c,other,True)['reverb_fix_enabled'])
        self.assertFalse(self.paths['target'].exists());self.assertTrue(target.exists())
        self.assertEqual(a._registry_value(self.paths['registry'].read_bytes()),a.OVERRIDE)
        self.assertTrue(self.enable()['reverb_fix_enabled']);self.assertTrue(self.paths['target'].exists());self.assertFalse(target.exists())
        self.assertTrue(list(self.paths['store'].glob('receipt-*.json')))
    def test_unsupported_alternate_selection_removes_prior_native_only_rule(self):
        other=self.other_edition(False);self.enable()
        state=a.status(self.c,other);self.assertFalse(state['reverb_fix_supported']);self.assertTrue(state['reverb_fix_managed']);self.assertTrue(state['reverb_fix_pending'])
        result=a.set_enabled(self.c,other,False)
        self.assertFalse(result['reverb_fix_managed']);self.assertFalse(result['reverb_fix_enabled'])
        self.assertFalse(self.paths['target'].exists());self.assertIsNone(a._registry_value(self.paths['registry'].read_bytes()))
        self.assertEqual(Path(other['exe']).read_bytes(),b'unsupported base version')
    def test_changed_previous_edition_blocks_transfer_without_mutation(self):
        other=self.other_edition();self.enable();self.paths['target'].write_bytes(b'changed old mod')
        registry=self.paths['registry'].read_bytes();receipt=self.paths['receipt'].read_bytes()
        with self.assertRaises(a.ReverbFixError):a.set_enabled(self.c,other,True)
        self.assertEqual(self.paths['target'].read_bytes(),b'changed old mod');self.assertEqual(self.paths['registry'].read_bytes(),registry);self.assertEqual(self.paths['receipt'].read_bytes(),receipt)
        self.assertFalse(Path(other['exe']).with_name('winmm.dll').exists())
    def test_interrupted_edition_transfer_resumes_without_two_active_dlls(self):
        other=self.other_edition();target=Path(other['exe']).with_name('winmm.dll');self.enable();original=a._write
        def fail_new(c,path,raw,**kwargs):
            if path==target:raise OSError('interrupted selected install')
            return original(c,path,raw,**kwargs)
        with mock.patch.object(a,'_write',side_effect=fail_new):
            with self.assertRaises(OSError):a.set_enabled(self.c,other,True)
        self.assertFalse(self.paths['target'].exists());self.assertFalse(target.exists());self.assertIsNone(a._registry_value(self.paths['registry'].read_bytes()))
        self.assertTrue(a.status(self.c,other)['reverb_fix_pending'])
        self.assertTrue(a.set_enabled(self.c,other,True)['reverb_fix_enabled']);self.assertFalse(self.paths['target'].exists())
    def test_uninstalled_previous_edition_can_transfer_shared_rule(self):
        other=self.other_edition();self.enable();shutil.rmtree(self.paths['exe'].parent)
        self.assertTrue(a.status(self.c,other)['reverb_fix_pending'])
        self.assertTrue(a.set_enabled(self.c,other,True)['reverb_fix_enabled'])
        self.assertFalse(self.paths['exe'].parent.exists());self.assertTrue(Path(other['exe']).with_name('winmm.dll').exists())
    def update_component(self):
        self.manifest['version']='1.0.0-beta.2'
        new=b'MZ newer verified component'
        self.manifest['dll'].update(sha256=digest(new),bytes=len(new))
        (self.component/'winmm.dll').write_bytes(new);self.save_manifest()
        return new
    def test_owned_component_upgrade_preserves_old_evidence(self):
        self.enable();new=self.update_component()
        state=a.status(self.c,self.game)
        self.assertTrue(state['reverb_fix_supported']);self.assertTrue(state['reverb_fix_enabled']);self.assertTrue(state['reverb_fix_pending'])
        self.assertFalse(self.enable()['reverb_fix_pending'])
        self.assertEqual(self.paths['target'].read_bytes(),new)
        self.assertEqual(self.paths['payload'].read_bytes(),self.payload)
        archives=list(self.paths['store'].glob('receipt-*.json'));self.assertEqual(len(archives),1)
        self.assertEqual(json.loads(archives[0].read_text())['dll_sha256'],digest(self.payload))
        self.assertFalse(self.disable()['reverb_fix_enabled']);self.assertEqual(self.paths['registry'].read_bytes(),self.initial)
    def test_old_owned_component_can_be_removed_but_changed_files_are_preserved(self):
        self.enable();self.update_component()
        for path in (self.paths['payload'],self.paths['target']):
            raw=path.read_bytes();path.write_bytes(b'user change')
            with self.assertRaises(a.ReverbFixError):self.enable()
            with self.assertRaises(a.ReverbFixError):self.disable()
            self.assertEqual(path.read_bytes(),b'user change');path.write_bytes(raw)
        self.assertFalse(self.disable()['reverb_fix_enabled'])
    def test_pre_receipt_interruption_allows_unrelated_registry_change(self):
        with mock.patch.object(a,'_save',side_effect=OSError('interrupted before ownership publication')):
            with self.assertRaises(OSError):self.enable()
        self.assertFalse(self.paths['receipt'].exists());self.assertFalse(self.paths['target'].exists())
        changed=self.initial+b'"later"="preserve"\n';self.paths['registry'].write_bytes(changed)
        self.assertTrue(self.enable()['reverb_fix_enabled'])
        self.assertEqual(self.paths['backup'].read_bytes(),self.initial)
        record=json.loads(self.paths['receipt'].read_text())
        self.assertEqual((self.paths['store']/record['registry_backup_file']).read_bytes(),changed)
        self.disable();self.assertEqual(self.paths['registry'].read_bytes(),changed)
    def production_audio_fixture(self):
        import audio_fix
        self.dsound.unlink()
        self.paths['registry'].write_bytes(self.initial.replace(b'"dsound"="native"\n',b''))
        folder=self.home/'audio-compat';folder.mkdir();payload=b'MZ production timing component'
        (folder/'dsound.dll').write_bytes(payload)
        manifest=json.loads(json.dumps(self.manifest))
        manifest.update(id='origins-audio',policy_revision=10,status_directory='drive_c/dao-support/origins-audio/status')
        manifest['dll']=dict(file='dsound.dll',bytes=len(payload),sha256=digest(payload))
        manifest.pop('fmod_event')
        (folder/'component.json').write_text(json.dumps(manifest))
        patch=mock.patch.object(audio_fix,'_component_dir',return_value=folder);patch.start();self.addCleanup(patch.stop)
        audio_fix.set_enabled(self.c,self.game,True)
        return audio_fix,audio_fix._paths(self.c,self.game)
    def test_actual_audio_manager_coexists_through_both_removal_orders(self):
        audio,paths=self.production_audio_fixture()
        timing={key:paths[key].read_bytes() for key in ('receipt','target','payload','backup')}
        self.enable()
        self.assertTrue(audio.status(self.c,self.game)['audio_fix_enabled'])
        for key,raw in timing.items():self.assertEqual(paths[key].read_bytes(),raw)
        self.disable()
        for key,raw in timing.items():self.assertEqual(paths[key].read_bytes(),raw)
        self.assertTrue(audio.status(self.c,self.game)['audio_fix_enabled'])
        self.enable();reverb={key:self.paths[key].read_bytes() for key in ('receipt','target','payload','backup')}
        audio.set_enabled(self.c,self.game,False)
        self.assertTrue(a.status(self.c,self.game)['reverb_fix_enabled'])
        for key,raw in reverb.items():self.assertEqual(self.paths[key].read_bytes(),raw)
        audio.set_enabled(self.c,self.game,True)
        self.assertTrue(a.status(self.c,self.game)['reverb_fix_enabled'])
        for key,raw in reverb.items():self.assertEqual(self.paths[key].read_bytes(),raw)
    def test_actual_audio_manager_survives_reverb_interruption_and_upgrade(self):
        audio,paths=self.production_audio_fixture()
        timing={key:paths[key].read_bytes() for key in ('receipt','target','payload','backup')}
        original=a._write
        def fail_registry(c,path,raw,**kwargs):
            if path==self.paths['registry']:raise OSError('interrupt reverb registry')
            return original(c,path,raw,**kwargs)
        with mock.patch.object(a,'_write',side_effect=fail_registry):
            with self.assertRaisesRegex(OSError,'interrupt'):self.enable()
        self.assertTrue(audio.status(self.c,self.game)['audio_fix_enabled'])
        self.disable();self.enable();self.update_component();self.enable()
        self.assertTrue(audio.status(self.c,self.game)['audio_fix_enabled'])
        for key,raw in timing.items():self.assertEqual(paths[key].read_bytes(),raw)
        self.assertIn(b'"dsound"="native"',self.paths['registry'].read_bytes())
    def test_verified_managed_4gb_exception_only_for_ntdll(self):
        rel='SharedSupport/wine/lib/wine/x86_64-unix/ntdll.so';p=self.c.contents/rel;p.parent.mkdir(parents=True);p.write_bytes(b'managed 4gb')
        self.manifest['runtime']['files'].append(dict(path=rel,sha256=digest(b'original'),managed_laa_override=True));self.save_manifest()
        with mock.patch.object(a.large_address,'_inspection',return_value=({}, {}, True)):
            self.assertTrue(self.enable()['reverb_fix_enabled'])
        with mock.patch.object(a.large_address,'_inspection',return_value=({}, {}, False)):
            self.assertFalse(a.status(self.c,self.game)['reverb_fix_supported'])
        self.assertFalse(self.disable()['reverb_fix_enabled'])

if __name__=='__main__':unittest.main()
