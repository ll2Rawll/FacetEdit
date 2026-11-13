from pathlib import Path
import tempfile
import unittest
from unittest import mock

from facetedit.blocks import Block
from facetedit.model import Document,Selection
from facetedit.recovery import RecoveryStore
from facetedit.structures import project_data
from facetedit.world import SampleWorld,open_world
from tests.fixtures import java_world


class RecoveryTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.path=Path(self.temp.name)
        self.doc=Document(SampleWorld());self.doc.selection=Selection((0,40,0),(1,40,1));self.doc.fill(Block('glass'))
        self.store=RecoveryStore(self.path/'Recovery',session='a'*32)
    def tearDown(self):self.temp.cleanup()

    def checkpoint(self):
        self.store.write(project_data(self.doc),self.doc.world.name,self.doc.pending_count,self.store.generation)

    def test_restore_block_edits_and_selection(self):
        self.checkpoint();loaded=self.store.restore(self.store.path)
        self.assertEqual(loaded.edits,self.doc.edits);self.assertEqual(loaded.selection,self.doc.selection)
        entry=self.store.entries(include_current=True)[0]
        self.assertEqual(entry.name,'Willow Bay');self.assertEqual(entry.changes,4)

    def test_multiple_sessions_discovery_and_isolated_cleanup(self):
        self.checkpoint();second=RecoveryStore(self.path/'Recovery',session='b'*32)
        self.assertEqual(len(second.entries()),1)
        second.write(project_data(self.doc),'Second',4)
        self.store.clear()
        self.assertTrue(second.path.exists());self.assertFalse(self.store.path.exists())
        self.assertEqual(self.store.entries()[0].name,'Second')

    def test_stale_writer_cannot_resurrect_discarded_session(self):
        generation=self.store.generation;self.checkpoint();self.store.clear()
        self.assertFalse(self.store.write(project_data(self.doc),'Old',4,generation))
        self.assertFalse(self.store.path.exists())

    def test_failed_atomic_write_retains_previous_checkpoint(self):
        self.checkpoint();before=self.store.path.read_bytes()
        self.doc.fill(Block('gold_block'))
        with mock.patch('facetedit.structures.os.replace',side_effect=OSError('disk full')),self.assertRaises(OSError):self.checkpoint()
        self.assertEqual(self.store.path.read_bytes(),before)
        self.assertFalse(list(self.store.directory.glob('.facetedit-*')))

    def test_missing_or_bad_manifest_still_discovers_valid_recovery(self):
        self.checkpoint();metadata=self.store.path.with_suffix('.json')
        metadata.unlink();self.assertEqual(len(self.store.entries(True)),1)
        metadata.write_text('broken');self.assertEqual(len(self.store.entries(True)),1)
        self.assertEqual(self.store.restore(self.store.path).edits,self.doc.edits)

    def test_discard_cannot_remove_unrelated_files(self):
        file=self.path/'outside.facet';file.write_text('keep')
        with self.assertRaises(ValueError):self.store.discard(file)
        self.assertEqual(file.read_text(),'keep')
        self.store.directory.mkdir();link=self.store.directory/'link.facet'
        try:link.symlink_to(file)
        except OSError:self.skipTest('Symlinks unavailable')
        with self.assertRaises(ValueError):self.store.restore(link)

    def test_snapshot_is_detached_from_later_edits(self):
        snapshot=self.doc.snapshot();self.doc.fill(Block('gold_block'))
        self.store.write(project_data(snapshot),'Earlier',4)
        self.assertEqual(self.store.restore(self.store.path).get(0,40,0),Block('glass'))

    def test_changed_source_blocks_recovery_restore(self):
        source=java_world(self.path/'world');doc=Document(open_world(source))
        self.store.write(project_data(doc),'Disk world',0)
        (source/'extra.dat').write_bytes(b'changed')
        with self.assertRaisesRegex(ValueError,'source world has changed'):self.store.restore(self.store.path)
