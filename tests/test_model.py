import unittest

from facetedit.blocks import AIR, Block
from facetedit.model import Clipboard, Document, Selection
from facetedit.world import SampleWorld


class ModelTests(unittest.TestCase):
    def setUp(self):
        self.doc = Document(SampleWorld())
        self.doc.selection = Selection((-8, 20, -8), (-6, 21, -6))

    def test_reverse_corners_and_inclusive_volume(self):
        selection = Selection((2, 3, 4), (-1, 2, 0))
        self.assertEqual(selection.size, (4, 2, 5))
        self.assertEqual(len(list(selection.positions())), 40)

    def test_oversized_selection_is_refused(self):
        self.doc.selection = Selection((0, 0, 0), (999, 99, 999))
        with self.assertRaises(ValueError):
            self.doc.fill(Block("stone"))
        self.assertFalse(self.doc.edits)

    def test_fill_undo_redo(self):
        self.assertEqual(self.doc.fill(Block("glass")), 18)
        self.assertEqual(len(self.doc.edits), 18)
        self.doc.undo()
        self.assertFalse(self.doc.edits)
        self.doc.redo()
        self.assertEqual(self.doc.get(-8, 20, -8), Block("glass"))

    def test_replace_and_delete(self):
        self.doc.fill(Block("glass"))
        self.assertEqual(self.doc.fill(Block("gold_block"), replace=Block("stone")), 0)
        self.assertEqual(self.doc.fill(Block("gold_block"), replace=Block("glass")), 18)
        self.assertEqual(self.doc.delete(), 18)
        self.assertEqual(self.doc.get(-8, 20, -8), AIR)
        self.doc.undo()
        self.assertEqual(self.doc.get(-8, 20, -8), Block("gold_block"))

    def test_new_edit_clears_redo(self):
        self.doc.fill(Block("stone"))
        self.doc.undo()
        self.doc.fill(Block("glass"))
        self.assertFalse(self.doc.redo_stack)

    def test_noop_does_not_create_history(self):
        self.doc.fill(Block("stone"))
        self.doc.fill(Block("stone"))
        self.assertEqual(len(self.doc.undo_stack), 1)

    def test_failed_transaction_is_atomic(self):
        with self.assertRaises(ValueError):
            self.doc.apply("bad", [((0, 20, 0), Block("gold_block")), ((0, 999, 0), Block("gold_block"))])
        self.assertFalse(self.doc.edits)

    def test_duplicate_coordinates_refused(self):
        with self.assertRaises(ValueError):
            self.doc.apply("bad", [((0, 20, 0), Block("stone")), ((0, 20, 0), AIR)])
        self.assertFalse(self.doc.edits)

    def test_copy_cut_paste(self):
        self.doc.fill(Block("glass"))
        self.assertEqual(self.doc.copy(), 18)
        self.doc.cut()
        self.assertEqual(self.doc.get(-8, 20, -8), AIR)
        self.assertEqual(self.doc.paste(origin=(2, 30, 3)), 18)
        self.assertEqual(self.doc.get(4, 31, 5), Block("glass"))

    def test_coordinate_and_state_rotation(self):
        block = Block.parse("oak_log[axis=x,facing=north]")
        clip = Clipboard((2, 1, 3), {(0, 0, 0): block})
        rotated = clip.transformed(1)
        self.assertEqual(rotated.size, (3, 1, 2))
        self.assertEqual(rotated.blocks[(2, 0, 0)], Block.parse("oak_log[axis=z,facing=east]"))
        self.assertEqual(clip.transformed(4), clip)

    def test_mirror(self):
        block = Block.parse("oak_stairs[facing=east]")
        clip = Clipboard((4, 1, 1), {(0, 0, 0): block})
        self.assertEqual(clip.transformed(mirror=True).blocks[(3, 0, 0)], Block.parse("oak_stairs[facing=west]"))

    def test_air_paste_opt_in(self):
        self.doc.clipboard = Clipboard((1, 1, 1), {(0, 0, 0): AIR})
        self.assertEqual(self.doc.paste(origin=(-8, 2, -8)), 0)
        self.assertEqual(self.doc.paste(origin=(-8, 2, -8), include_air=True), 1)

    def test_history_keeps_block_states(self):
        block = Block.parse("oak_stairs[facing=north,waterlogged=true]")
        self.doc.fill(block)
        self.doc.delete()
        self.doc.undo()
        self.assertEqual(self.doc.get(-8, 20, -8), block)

    def test_missing_selection(self):
        self.doc.selection = None
        with self.assertRaises(ValueError):
            self.doc.copy()

    def test_invalid_block_names(self):
        for name in ("", "a:b:c", "../bad", "minecraft:Stone", "stone[axis]", "stone[x=1,x=2]"):
            with self.subTest(name=name), self.assertRaises(ValueError):
                Block.parse(name)

    def test_dimension_specific_height_bounds(self):
        world = SampleWorld()
        world.dimensions = ("overworld", "the_nether", "the_end")
        with self.assertRaisesRegex(ValueError, "127"):
            world.validate_edit((0,128,0), "the_nether")
        with self.assertRaisesRegex(ValueError, "255"):
            world.validate_edit((0,256,0), "the_end")
