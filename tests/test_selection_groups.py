import random
import unittest
import tempfile
from pathlib import Path

from facetedit.blocks import AIR,Block
from facetedit.model import Document,Selection,SelectionGroup
from facetedit.world import SampleWorld
from facetedit.structures import export_structure,import_structure,import_mcstructure
from facetedit.schematic import save_schematic


class SelectionGroupTests(unittest.TestCase):
    def test_union_overlap_edits_each_block_once(self):
        a,b = Selection((0,30,0),(2,32,2)),Selection((1,31,1),(3,33,3))
        group = SelectionGroup((a,b))
        expected = set(a.positions())|set(b.positions())
        self.assertEqual(group.volume,len(expected))
        self.assertEqual(len(list(group.positions())),len(expected))
        doc = Document(SampleWorld());doc.selection = group
        self.assertEqual(doc.fill(Block('glass')),len(expected))
        self.assertEqual(len(doc.undo_stack),1)
        doc.undo();self.assertFalse(doc.edits)

    def test_subtraction_preserves_nonoverlapping_slabs(self):
        outer = Selection((0,0,0),(4,4,4));inner = Selection((1,1,1),(3,3,3))
        result = SelectionGroup((outer,)).subtract(inner)
        self.assertEqual(len(result.boxes),6)
        self.assertEqual(set(result.positions()),set(outer.positions())-set(inner.positions()))
        self.assertFalse(result.contains((2,2,2)))
        self.assertTrue(result.contains((4,4,4)))

    def test_random_box_algebra_against_sets(self):
        rng = random.Random(809)
        for _ in range(70):
            boxes = [Selection(tuple(rng.randrange(-4,5) for _ in range(3)),tuple(rng.randrange(-4,5) for _ in range(3))) for _ in range(4)]
            group = SelectionGroup(boxes[:3])
            expected = set().union(*(set(box.positions()) for box in boxes[:3]))
            self.assertEqual(set(group.positions()),expected)
            self.assertEqual(group.volume,len(expected))
            sub = group.subtract(boxes[3]);expected -= set(boxes[3].positions())
            self.assertEqual(set(sub.positions()),expected)
            self.assertEqual(sub.volume,len(expected))

    def test_chunk_floor_and_multibox_deduplication(self):
        group = SelectionGroup((Selection((-1,0,-1),(0,0,0)),Selection((0,10,0),(15,20,15))))
        self.assertEqual(group.chunks(),{(-1,-1),(-1,0),(0,-1),(0,0)})

    def test_limits_before_enumeration(self):
        with self.assertRaises(ValueError):list(Selection((0,0,0),(100,100,100)).positions())
        with self.assertRaises(ValueError):Selection((0,0,0),(16*65536,0,0)).chunks()
        with self.assertRaises(ValueError):SelectionGroup(Selection((x*2,0,0),(x*2,0,0)) for x in range(257))
        for values in ((1.2,0,0),(True,0,0),(30_000_001,0,0)):
            with self.assertRaises(ValueError):Selection(values,(0,0,0))

    def test_empty_subtraction_and_atomic_shrink(self):
        doc = Document(SampleWorld());box = Selection((0,30,0),(0,30,0));doc.selection=box
        with self.assertRaises(ValueError):doc.expand_selection(-1)
        self.assertEqual(doc.selection,box)
        doc.combine_selection(box,'subtract');self.assertIsNone(doc.selection)

    def test_multibox_nudge_and_expand(self):
        doc=Document(SampleWorld())
        doc.selection=SelectionGroup((Selection((0,30,0),(0,30,0)),Selection((10,30,0),(10,30,0))))
        doc.nudge_selection((-2,1,3))
        self.assertEqual(doc.selection.minimum,(-2,31,3));self.assertEqual(doc.selection.volume,2)
        doc.expand_selection(1);self.assertEqual(doc.selection.volume,54)

    def test_sparse_clipboard_never_fills_gap_even_with_air(self):
        doc=Document(SampleWorld())
        doc.selection=SelectionGroup((Selection((0,40,0),(0,40,0)),Selection((20,40,0),(20,40,0))))
        doc.fill(Block('gold_block'));doc.copy()
        doc.apply('gap',[((10,60,0),Block('glass'))])
        doc.paste((0,60,0),include_air=True)
        self.assertEqual(doc.get(10,60,0),Block('glass'))
        self.assertEqual(doc.get(20,60,0),Block('gold_block'))
        self.assertEqual(doc.get(5,60,0),AIR)

    def test_biomes_respect_gaps_and_shared_cells(self):
        doc=Document(SampleWorld())
        doc.selection=SelectionGroup((Selection((0,40,0),(0,40,0)),Selection((3,40,0),(3,40,0)),Selection((20,40,0),(20,40,0))))
        self.assertEqual(doc.set_biome('desert'),2)
        self.assertEqual(doc.get_biome(8,40,0),'minecraft:plains')
        doc.undo();self.assertFalse(doc.biome_edits)

    def test_sparse_structure_roundtrips_both_editions(self):
        doc=Document(SampleWorld())
        doc.selection=SelectionGroup((Selection((0,40,0),(0,40,0)),Selection((10,40,0),(10,40,0))))
        doc.fill(Block('stone'));doc.copy();clipboard=doc.clipboard
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'sparse.nbt';export_structure(clipboard,path)
            self.assertEqual(import_structure(path).blocks,clipboard.blocks)
            with self.assertRaisesRegex(ValueError,'selection gaps'):save_schematic(clipboard,Path(directory)/'gaps.schem')
            clipboard.edition='Bedrock';path=Path(directory)/'sparse.mcstructure';export_structure(clipboard,path)
            self.assertEqual(set(import_mcstructure(path).blocks),set(clipboard.blocks))

    def test_widely_spaced_boxes_cannot_export_unreadable_bounding_volume(self):
        doc=Document(SampleWorld())
        doc.selection=SelectionGroup((Selection((0,40,0),(0,40,0)),Selection((100000,40,0),(100000,40,0))))
        doc.copy();clipboard=doc.clipboard
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'too-wide.nbt'
            with self.assertRaisesRegex(ValueError,'bounding volume'):export_structure(clipboard,path)
            self.assertFalse(path.exists())
