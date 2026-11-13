from importlib import resources
import threading,unittest
from unittest import mock
from facetedit.blocks import Block,AIR
from facetedit.model import Document,Selection
from facetedit.operations import OperationSpec,run_operation,Cancelled
from facetedit.world import SampleWorld
from facetedit import nbt


class OperationTests(unittest.TestCase):
    def setUp(self):
        self.doc=Document(SampleWorld());self.doc.selection=Selection((0,40,0),(3,43,3))
    def example(self,name):return OperationSpec.parse(resources.files('facetedit').joinpath('operation_examples',name+'.py').read_text())

    def test_checkerboard_is_one_atomic_undoable_commit(self):
        result=run_operation(self.example('checkerboard'),self.doc,{'cell_size':1})
        self.assertFalse(self.doc.edits);self.assertEqual(result.commit(self.doc),64)
        self.assertEqual(self.doc.get(0,40,0),Block('white_concrete'));self.assertEqual(self.doc.get(1,40,0),Block('stone'))
        self.assertEqual(len(self.doc.undo_stack),1);self.doc.undo();self.assertFalse(self.doc.edits)

    def test_hollow_shell_and_clear_interior(self):
        self.doc.fill(Block('gold_block'))
        run_operation(self.example('shell'),self.doc).commit(self.doc)
        self.assertEqual(self.doc.get(0,40,0),Block('glass'));self.assertEqual(self.doc.get(1,41,1),AIR)
        self.doc.undo();self.assertEqual(self.doc.get(1,41,1),Block('gold_block'))

    def test_script_discovery_does_not_execute_imports_or_top_level_code(self):
        source="raise RuntimeError('must not execute on parse')\nOPERATION={'name':'Example'}\ndef run(context,options): pass\n"
        spec=OperationSpec.parse(source)
        with self.assertRaisesRegex(RuntimeError,'must not execute'):run_operation(spec,self.doc)
        self.assertFalse(self.doc.edits)

    def test_exception_after_proposals_does_not_mutate_document(self):
        source="OPERATION={'name':'Broken'}\ndef run(c,o):\n c.set_block((0,40,0),'glass')\n raise ValueError('broken')\n"
        with self.assertRaisesRegex(ValueError,'broken'):run_operation(OperationSpec.parse(source),self.doc)
        self.assertFalse(self.doc.edits);self.assertFalse(self.doc.undo_stack)

    def test_cancel_before_and_during_execution_discards_proposals(self):
        event=threading.Event();event.set()
        with self.assertRaises(Cancelled):run_operation(self.example('checkerboard'),self.doc,cancel=event)
        event.clear()
        with self.assertRaises(Cancelled):run_operation(self.example('checkerboard'),self.doc,cancel=event,progress=lambda _:event.set())
        self.assertFalse(self.doc.edits)

    def test_stale_revision_and_dimension_results_refused(self):
        result=run_operation(self.example('checkerboard'),self.doc)
        self.doc.apply('other',[((5,40,0),Block('glass'))])
        with self.assertRaisesRegex(ValueError,'changed'):result.commit(self.doc)
        self.assertEqual(len(self.doc.edits),1)

    def test_changed_during_script_keeps_original_revision(self):
        def progress(_):
            if not self.doc.edits:self.doc.apply('concurrent',[((5,40,0),Block('glass'))])
        result=run_operation(self.example('checkerboard'),self.doc,progress=progress)
        with self.assertRaisesRegex(ValueError,'changed'):result.commit(self.doc)

    def test_option_validation_precedes_script_execution(self):
        for value in (0,129,True,'invalid'):
            with self.assertRaises((ValueError,TypeError)):run_operation(self.example('checkerboard'),self.doc,{'cell_size':value})
        with self.assertRaises(ValueError):run_operation(self.example('checkerboard'),self.doc,{'unknown':1})
        self.assertFalse(self.doc.edits)

    def test_bounds_failure_is_atomic_at_commit(self):
        source="OPERATION={'name':'Out of bounds'}\ndef run(c,o):\n c.set_block((0,40,0),'glass')\n c.set_block((0,9999,0),'glass')\n"
        result=run_operation(OperationSpec.parse(source),self.doc)
        with self.assertRaises(ValueError):result.commit(self.doc)
        self.assertFalse(self.doc.edits)

    def test_operation_staging_budget(self):
        with mock.patch('facetedit.operations.MAX_OPERATION',2),self.assertRaises(ValueError):run_operation(self.example('checkerboard'),self.doc)
        self.assertFalse(self.doc.edits)

    def test_script_exit_is_reported_and_proposals_are_discarded(self):
        for exception in ('SystemExit','KeyboardInterrupt'):
            source=f"OPERATION={{'name':'Exit'}}\ndef run(c,o):\n c.set_block((0,40,0),'glass')\n raise {exception}()\n"
            with self.assertRaisesRegex(ValueError,exception):run_operation(OperationSpec.parse(source),self.doc)
        self.assertFalse(self.doc.edits)

    def test_operation_reads_its_own_block_nbt_changes(self):
        position=(0,40,0)
        self.doc.apply('chest',[(position,Block('chest'))])
        self.doc.set_entity(position,nbt.compound(id=nbt.Tag(nbt.STRING,'minecraft:chest'),x=nbt.Tag(nbt.INT,0),y=nbt.Tag(nbt.INT,40),z=nbt.Tag(nbt.INT,0)))
        source="OPERATION={'name':'Replace'}\ndef run(c,o):\n assert c.get_nbt((0,40,0)) is not None\n c.set_block((0,40,0),'glass')\n assert c.get_nbt((0,40,0)) is None\n"
        result=run_operation(OperationSpec.parse(source),self.doc);result.commit(self.doc)
        self.assertIsNone(self.doc.get_entity(*position))
        self.doc.undo();self.assertIsNotNone(self.doc.get_entity(*position))
