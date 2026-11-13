from pathlib import Path
import tempfile
import unittest

from facetedit import nbt
from facetedit.blocks import AIR,Block
from facetedit.formats import encode_bedrock
from facetedit.model import Document,Selection
from facetedit.structures import save_project,load_project,export_structure,import_mcstructure
from facetedit.world import open_world
from tests.fixtures import bedrock_world
from tests.test_workflows import hashes

WATER=Block('water',(('liquid_depth','0'),),(('liquid_depth',nbt.INT),))


class LayerTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.path=Path(self.temp.name)
        self.doc=Document(open_world(bedrock_world(self.path/'world')))
        self.pos=(1,2,3);self.doc.selection=Selection(self.pos,self.pos)
    def tearDown(self):self.temp.cleanup()

    def wet(self):
        self.doc.waterlog();self.assertEqual(self.doc.get_extra_blocks(*self.pos),(WATER,))

    def test_waterlog_is_layer_only_and_retains_block_nbt(self):
        before=self.doc.get_entity(*self.pos);self.wet()
        self.assertFalse(self.doc.edits);self.assertEqual(self.doc.get_entity(*self.pos),before)
        self.assertEqual(self.doc.waterlog(),0)
        self.doc.undo();self.assertEqual(self.doc.get_extra_blocks(*self.pos),())
        self.doc.redo();self.assertEqual(self.doc.get_extra_blocks(*self.pos),(WATER,))

    def test_normal_replacement_clears_layers_and_undo_restores(self):
        self.wet();self.doc.fill(Block('glass'));self.assertFalse(self.doc.get_extra_blocks(*self.pos))
        self.doc.undo();self.assertEqual(self.doc.get_extra_blocks(*self.pos),(WATER,))

    def test_layer_only_export_reopens_and_source_is_identical(self):
        before=hashes(self.doc.world.path);entity=self.doc.get_entity(*self.pos);self.wet()
        destination=self.path/'out';self.doc.world.export(destination,self.doc.edits,**self.doc.export_metadata())
        out=open_world(destination)
        self.assertEqual(out.get_extra_blocks(*self.pos),(WATER,));self.assertEqual(out.get_block_entity(*self.pos),entity)
        self.assertEqual(hashes(self.doc.world.path),before)

    def test_copy_paste_clone_cut_preserve_layers(self):
        self.wet();self.doc.copy();self.doc.paste((2,2,3))
        self.assertEqual(self.doc.get_extra_blocks(2,2,3),(WATER,))
        self.doc.clone((2,0,0));self.assertEqual(self.doc.get_extra_blocks(3,2,3),(WATER,))
        self.doc.cut();self.assertFalse(self.doc.get_extra_blocks(*self.pos));self.doc.undo()
        self.assertEqual(self.doc.get_extra_blocks(*self.pos),(WATER,))

    def test_project_and_mcstructure_persist_typed_secondary_layer(self):
        self.wet();self.doc.copy();file=self.path/'wet.mcstructure';export_structure(self.doc.clipboard,file)
        loaded=import_mcstructure(file);self.assertEqual(loaded,self.doc.clipboard)
        project=self.path/'wet.facet';save_project(self.doc,project);other=load_project(project)
        self.assertEqual(other.get_extra_blocks(*self.pos),(WATER,))

    def test_pending_block_with_equal_baseline_layer_still_persists(self):
        primary=[Block('stone')]*4096;secondary=[AIR]*4096
        secondary[(1<<8)|(3<<4)|2]=WATER
        self.doc.world.values[b'\0'*8+b'/\0']=encode_bedrock(9,0,[primary,secondary])
        self.doc.apply('glass',[((1,2,3),Block('glass'))],layer_updates=[(self.pos,(WATER,))])
        file=self.path/'equal.facet';save_project(self.doc,file)
        # Use the same in-memory baseline for this deduplication assertion.
        self.assertEqual(self.doc.get_extra_blocks(*self.pos),(WATER,))
        self.assertIn(('overworld',*self.pos),self.doc.layer_edits)
        self.doc.undo();self.assertEqual(self.doc.get_extra_blocks(*self.pos),(WATER,))

    def test_fill_modes(self):
        for mode,base,expected_primary,expected_extra in (
            ('overlay',Block('stone'),Block('stone'),(Block('glass'),)),
            ('overlay',AIR,Block('glass'),()),
            ('underlay',Block('stone'),Block('glass'),(Block('stone'),)),
            ('first',Block('stone'),Block('glass'),()),
            ('second',Block('stone'),Block('stone'),(Block('glass'),)),
            ('game',WATER,Block('glass'),(WATER,))):
            self.doc.apply('setup',[(self.pos,base)])
            self.doc.fill_layers(Block('glass'),mode)
            self.assertEqual(self.doc.get(*self.pos),expected_primary,mode)
            self.assertEqual(self.doc.get_extra_blocks(*self.pos),expected_extra,mode)

    def test_unwaterlog_keeps_other_layers_and_empty_positions(self):
        extras=(WATER,Block('snow_layer'))
        self.doc.apply('layers',[(self.pos,Block('stone'))],layer_updates=[(self.pos,extras)])
        self.doc.waterlog(False);self.assertEqual(self.doc.get_extra_blocks(*self.pos),(AIR,Block('snow_layer')))
        self.doc.undo();self.assertEqual(self.doc.get_extra_blocks(*self.pos),extras)

    def test_waterlog_occupied_secondary_layer_is_atomic(self):
        self.doc.fill_layers(Block('glass'),'second');before=dict(self.doc.layer_edits)
        with self.assertRaisesRegex(ValueError,'occupied'):self.doc.waterlog()
        self.assertEqual(self.doc.layer_edits,before)

    def test_more_than_two_layers_refused_by_mcstructure_without_file(self):
        self.doc.apply('layers',[(self.pos,Block('stone'))],layer_updates=[(self.pos,(WATER,Block('snow_layer')))])
        self.doc.copy();path=self.path/'many.mcstructure'
        with self.assertRaisesRegex(ValueError,'two layers'):export_structure(self.doc.clipboard,path)
        self.assertFalse(path.exists())

    def test_chunk_delete_and_undo_restore_layer_edits(self):
        self.wet();self.doc.delete_chunks();self.assertFalse(self.doc.layer_edits)
        self.doc.undo();self.assertEqual(self.doc.get_extra_blocks(*self.pos),(WATER,))

    def test_bad_layer_transaction_is_atomic(self):
        with self.assertRaises(ValueError):self.doc.apply('invalid',[(self.pos,Block('glass'))],layer_updates=[(self.pos,(WATER,)*8)])
        self.assertFalse(self.doc.edits);self.assertFalse(self.doc.layer_edits)
