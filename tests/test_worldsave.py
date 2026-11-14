from pathlib import Path
import json,tempfile,unittest,subprocess,sys
from unittest import mock
from facetedit.blocks import Block
from facetedit.model import Document,Selection
from facetedit.world import open_world
from facetedit.worldsave import save_original,recover,list_saves,load_journal
from facetedit.filelock import file_lock
from tests.fixtures import java_world,bedrock_world
from tests.test_workflows import hashes


class WorldSaveTests(unittest.TestCase):
    def setUp(self):self.temp=tempfile.TemporaryDirectory();self.path=Path(self.temp.name)
    def tearDown(self):self.temp.cleanup()
    def document(self,bedrock=False):
        world=(bedrock_world if bedrock else java_world)(self.path/('bedrock' if bedrock else 'java'))
        doc=Document(open_world(world));doc.apply('glass',[((1,4,3),Block('glass'))]);return doc

    def test_save_original_both_editions_retains_exact_backup(self):
        for bedrock in (False,True):
            doc=self.document(bedrock);before=hashes(doc.world.path)
            result=save_original(doc.world,doc.edits,**doc.export_metadata())
            self.assertEqual(result.world.get_block(1,4,3),Block('glass'));self.assertEqual(hashes(result.backup),before)
            self.assertEqual(load_journal(result.transaction)[1]['state'],'committed')

    def test_block_undo_after_original_save_and_save_again(self):
        doc=self.document();history=doc.history_for_saved_world()
        result=save_original(doc.world,doc.edits,**doc.export_metadata());doc.rebase_saved_world(result.world,history)
        self.assertFalse(doc.edits);doc.undo();self.assertEqual(doc.get(1,4,3),Block('stone'))
        second=save_original(doc.world,doc.edits,**doc.export_metadata());self.assertEqual(second.world.get_block(1,4,3),Block('stone'))
        self.assertTrue(result.backup.exists())

    def test_chunk_undo_after_original_save_resolves_old_source(self):
        doc=self.document();doc.selection=Selection((0,0,0),(15,0,15));doc.delete_chunks()
        history=doc.history_for_saved_world();result=save_original(doc.world,doc.edits,**doc.export_metadata());doc.rebase_saved_world(result.world,history)
        self.assertNotIn((0,0),doc.chunk_positions());doc.undo();self.assertEqual(doc.get(1,4,3),Block('glass'))
        doc.undo();self.assertEqual(doc.get(1,4,3),Block('stone'))
        doc.redo();doc.redo();self.assertNotIn((0,0),doc.chunk_positions())

    def test_io_failures_roll_back_every_publication_boundary(self):
        for phase in ('preparing','prepared','backed_up','installed'):
            root=self.path/phase;doc=Document(open_world(java_world(root)));doc.apply('glass',[((1,4,3),Block('glass'))]);before=hashes(root)
            def fault(value):
                if value==phase:raise OSError('injected disk failure')
            with self.assertRaises(OSError):save_original(doc.world,doc.edits,fault=fault,**doc.export_metadata())
            self.assertEqual(hashes(root),before,phase)

    def test_crash_after_backup_is_discoverable_and_can_restore(self):
        doc=self.document();target=doc.world.path;before=hashes(target)
        def crash(phase):
            if phase=='backed_up':raise SystemExit('simulated process death')
        with self.assertRaises(SystemExit):save_original(doc.world,doc.edits,fault=crash,**doc.export_metadata())
        self.assertFalse(target.exists());entries=list_saves(self.path,target.name);self.assertEqual(len(entries),1)
        recover(entries[0][0]);self.assertEqual(hashes(target),before)

    def test_crash_after_backup_can_finish_prepared_save(self):
        doc=self.document()
        def crash(phase):
            if phase=='backed_up':raise SystemExit()
        with self.assertRaises(SystemExit):save_original(doc.world,doc.edits,fault=crash,**doc.export_metadata())
        entry=list_saves(self.path)[0];result=recover(entry[0],'finish')
        self.assertEqual(result.get_block(1,4,3),Block('glass'));self.assertTrue((entry[0]/'original').exists())

    def test_crash_after_install_can_complete_or_restore(self):
        for action in ('finish','rollback'):
            target=java_world(self.path/action);doc=Document(open_world(target));doc.apply('glass',[((1,4,3),Block('glass'))])
            def crash(phase):
                if phase=='installed':raise SystemExit()
            with self.assertRaises(SystemExit):save_original(doc.world,doc.edits,fault=crash,**doc.export_metadata())
            entry=list_saves(self.path,action)[0];out=recover(entry[0],action)
            self.assertEqual(out.get_block(1,4,3),Block('glass' if action=='finish' else 'stone'))

    def test_changed_world_and_changed_backups_are_preserved(self):
        doc=self.document();result=save_original(doc.world,doc.edits,**doc.export_metadata())
        (result.world.path/'extra.dat').write_bytes(b'new external modification')
        with self.assertRaisesRegex(ValueError,'changed'):recover(result.transaction)
        self.assertEqual((result.world.path/'extra.dat').read_bytes(),b'new external modification')
        (result.backup/'extra.dat').write_bytes(b'changed backup')
        with self.assertRaisesRegex(ValueError,'backup changed'):recover(result.transaction)

    def test_source_change_blocks_original_save_before_any_rename(self):
        doc=self.document();(doc.world.path/'extra.dat').write_bytes(b'changed')
        with self.assertRaisesRegex(ValueError,'changed'):save_original(doc.world,doc.edits)
        self.assertTrue(doc.world.path.exists());self.assertFalse(list(self.path.glob('.facetedit-save-*')))

    def test_process_lock_prevents_concurrent_save(self):
        from facetedit.worldsave import lock_path
        doc=self.document()
        with file_lock(lock_path(doc.world.path),True):
            with self.assertRaises(OSError):save_original(doc.world,doc.edits)
        self.assertEqual(open_world(doc.world.path).get_block(1,4,3),Block('stone'))

    def test_native_record_lock_layouts_match_linux_and_darwin_abis(self):
        import struct
        from facetedit.filelock import record_lock_data
        # XNU declares off_t start/length, pid_t pid, short type/whence.
        # Linux's 64-bit ABI puts the shorts first, with aligned off_t fields.
        darwin=record_lock_data(3,'darwin');linux=record_lock_data(1,'linux')
        self.assertEqual(darwin,struct.pack('=qqihh',0,0,0,3,0))
        self.assertEqual(len(linux),32);self.assertEqual(struct.unpack_from('=hh',linux),(1,0))
        self.assertEqual(struct.unpack_from('=qqi',linux,8),(0,0,0))

    def test_game_lock_held_by_another_process_refuses_save(self):
        doc=self.document();lock=doc.world.path/'session.lock';lock.write_bytes(b'\0'*8)
        doc=Document(open_world(doc.world.path));doc.apply('glass',[((1,4,3),Block('glass'))])
        source="from facetedit.filelock import file_lock\nimport sys\nwith file_lock(sys.argv[1]):\n print('locked',flush=True)\n sys.stdin.readline()\n"
        child=subprocess.Popen([sys.executable,'-u','-c',source,str(lock)],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
        try:
            self.assertEqual(child.stdout.readline().strip(),'locked')
            with self.assertRaises(OSError):save_original(doc.world,doc.edits)
            self.assertEqual(open_world(doc.world.path).get_block(1,4,3),Block('stone'))
        finally:
            child.communicate('\n',timeout=10)
        self.assertEqual(child.returncode,0)
        result=save_original(doc.world,doc.edits);self.assertEqual(result.world.get_block(1,4,3),Block('glass'))

    def test_save_faults_and_recovery_keep_real_game_lock_files(self):
        for phase in ('prepared','backed_up','installed'):
            target=java_world(self.path/phase);(target/'session.lock').write_bytes(b'game-lock-bytes')
            doc=Document(open_world(target));doc.apply('glass',[((1,4,3),Block('glass'))]);before=hashes(target)
            def crash(value):
                if value==phase:raise SystemExit('interrupted with a game lock')
            with self.assertRaises(SystemExit):save_original(doc.world,doc.edits,fault=crash)
            entry=list_saves(self.path,phase)[0];restored=recover(entry[0])
            self.assertEqual(hashes(restored.path),before);self.assertEqual((restored.path/'session.lock').read_bytes(),b'game-lock-bytes')
        target=java_world(self.path/'io-failure');(target/'session.lock').write_bytes(b'game-lock-bytes')
        doc=Document(open_world(target));doc.apply('glass',[((1,4,3),Block('glass'))]);before=hashes(target)
        def failed(value):
            if value=='installed':raise OSError('interrupted install')
        with self.assertRaises(OSError):save_original(doc.world,doc.edits,fault=failed)
        self.assertEqual(hashes(target),before)

    def test_journal_rejects_traversal_and_symlinks(self):
        doc=self.document();result=save_original(doc.world,doc.edits)
        file=result.transaction/'transaction.json';data=json.loads(file.read_text());data['world']='../outside';file.write_text(json.dumps(data))
        with self.assertRaises(ValueError):load_journal(result.transaction)

    def test_completed_backup_is_restorable_without_deleting_edited_world(self):
        doc=self.document();result=save_original(doc.world,doc.edits,**doc.export_metadata());recover(result.transaction)
        self.assertEqual(open_world(doc.world.path).get_block(1,4,3),Block('stone'))
        self.assertEqual(open_world(result.transaction/'displaced').get_block(1,4,3),Block('glass'))

    def test_abrupt_process_exit_at_each_swap_boundary_recovers_original(self):
        source="from facetedit.world import open_world\nfrom facetedit.worldsave import save_original\nfrom facetedit.blocks import Block\nimport sys,os\nworld=open_world(sys.argv[1])\ndef crash(phase):\n if phase==sys.argv[2]:os._exit(71)\nsave_original(world,{('overworld',1,4,3):Block('glass')},fault=crash)\n"
        for phase in ('prepared','backed_up','installed'):
            target=java_world(self.path/('process-'+phase));before=hashes(target)
            result=subprocess.run([sys.executable,'-c',source,str(target),phase],capture_output=True,text=True,timeout=15)
            self.assertEqual(result.returncode,71,result.stderr)
            entry=list_saves(self.path,target.name)[0];recover(entry[0]);self.assertEqual(hashes(target),before)

    def test_game_lock_is_still_held_after_copy_and_hash_before_publication(self):
        doc=self.document();lock=doc.world.path/'session.lock';lock.write_bytes(b'\0'*8)
        doc=Document(open_world(doc.world.path));doc.apply('glass',[((1,4,3),Block('glass'))])
        # Probe with a distinct process and a classic POSIX record lock, as
        # used by the Java FileChannel API (native Windows uses our adapter).
        source="import sys,os\nif os.name=='nt':\n from facetedit.filelock import file_lock\n try:\n  with file_lock(sys.argv[1]):pass\n except OSError:sys.exit(19)\nelse:\n import fcntl\n with open(sys.argv[1],'r+b') as f:\n  try:fcntl.lockf(f,fcntl.LOCK_EX|fcntl.LOCK_NB)\n  except OSError:sys.exit(19)\n"
        probes=[]
        def probe(phase):
            if phase=='prepared':
                result=subprocess.run([sys.executable,'-c',source,str(lock)],capture_output=True,text=True,timeout=10)
                self.assertEqual(result.returncode,19,result.stderr);probes.append(phase)
        save_original(doc.world,doc.edits,fault=probe);self.assertEqual(probes,['prepared'])
