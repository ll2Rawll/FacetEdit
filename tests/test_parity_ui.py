import os,time,tkinter as tk,tempfile
from pathlib import Path
from tkinter import ttk
import unittest
from unittest import mock
from facetedit.blocks import Block
from facetedit.chrome import Pill
from facetedit.model import Document,Selection
from facetedit.world import open_world,SampleWorld
from tests.fixtures import java_world,bedrock_world
from facetedit.worldsave import list_saves
from tests.test_workflows import hashes


@unittest.skipUnless(os.environ.get('FACETEDIT_GUI_TESTS')=='1','Desktop test flag required')
class ParityDesktopTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from facetedit.ui import FacetEditApp
        cls.temp=tempfile.TemporaryDirectory();cls.path=Path(cls.temp.name);cls.app=FacetEditApp(cls.path/'settings.json');cls.app.update()
    @classmethod
    def tearDownClass(cls):cls.app.destroy();cls.temp.cleanup()
    def setUp(self):
        self.app._attach(Document(SampleWorld()));self.app.update()
        self.errors=[];self.patcher=mock.patch('facetedit.ui.messagebox.showerror',side_effect=lambda *a,**k:self.errors.append(a));self.patcher.start()
    def tearDown(self):
        for child in self.app.winfo_children():
            if isinstance(child,tk.Toplevel):child.destroy()
        self.patcher.stop();self.assertFalse(self.errors)
    def widgets(self,parent):
        for child in parent.winfo_children():yield child;yield from self.widgets(child)
    def dialog(self):
        self.app.update();return next(c for c in self.app.winfo_children() if isinstance(c,tk.Toplevel))
    def press(self,parent,text):
        next(w for w in self.widgets(parent) if isinstance(w,Pill) and w.text==text).invoke();self.app.update()
    def wait(self):
        end=time.monotonic()+8
        while self.app.busy and time.monotonic()<end:self.app.update();time.sleep(.005)
        self.assertFalse(self.app.busy);self.app.update()

    def test_bundled_operation_ui_and_one_undo(self):
        self.app.document.selection=Selection((0,40,0),(3,43,3));self.app.operations_dialog();dialog=self.dialog()
        self.app.operation_vars['cell_size'].set('1');self.press(dialog,'Run operation');self.wait()
        self.assertEqual(self.app.document.get(0,40,0),Block('white_concrete'));self.assertEqual(len(self.app.document.undo_stack),1)
        self.app.undo();self.assertFalse(self.app.document.edits)

    def test_custom_script_load_and_run(self):
        file=self.path/'own.py';file.write_text("OPERATION={'name':'Original custom operation'}\ndef run(c,o):\n for p in c.positions():c.set_block(p,'gold_block')\n")
        self.app.document.selection=Selection((0,40,0),(1,40,0));self.app.operations_dialog();dialog=self.dialog()
        with mock.patch('facetedit.operation_ui.filedialog.askopenfilename',return_value=str(file)):self.press(dialog,'Load script…')
        self.press(dialog,'Run operation');self.wait();self.assertEqual(self.app.document.get(1,40,0),Block('gold_block'))

    def test_cancel_custom_operation_keeps_document_unchanged(self):
        file=self.path/'slow.py';file.write_text("import time\nOPERATION={'name':'Cooperative work'}\ndef run(c,o):\n for i in range(100):\n  c.check_cancelled()\n  c.set_block((0,40,0),'gold_block')\n  time.sleep(.01)\n")
        self.app.document.selection=Selection((0,40,0),(0,40,0));self.app.operations_dialog();dialog=self.dialog()
        with mock.patch('facetedit.operation_ui.filedialog.askopenfilename',return_value=str(file)):self.press(dialog,'Load script…')
        self.press(dialog,'Run operation');self.press(dialog,'Cancel run');self.wait();self.assertFalse(self.app.document.edits)

    def test_layered_fill_ui_and_waterlog_undo(self):
        self.app._attach(Document(open_world(bedrock_world(self.path/'layers'))));self.app._pick((1,2,3),False)
        self.app.block_var.set('water');self.app.layer_dialog();dialog=self.dialog();self.press(dialog,'Apply layered fill')
        self.assertEqual(self.app.document.get_extra_blocks(1,2,3),(Block('water'),));self.app.undo()
        self.assertFalse(self.app.document.get_extra_blocks(1,2,3))

    def test_biome_column_mode_ui(self):
        self.app._pick((0,40,0),False);self.app.biome_dialog();dialog=self.dialog()
        boxes=[w for w in self.widgets(dialog) if isinstance(w,ttk.Combobox)];boxes[0].set('minecraft:desert');boxes[1].set('column')
        self.press(dialog,'Apply biome');self.assertEqual(self.app.document.get_biome(0,92,0),'minecraft:desert')

    def test_original_save_ui_retains_undo_and_backup(self):
        source=java_world(self.path/'original');before=hashes(source);self.app._attach(Document(open_world(source)))
        self.app._pick((1,4,3),False);self.app.block_var.set('glass');self.app.fill()
        with mock.patch('facetedit.save_ui.messagebox.askyesno',return_value=True):self.app.save_original();self.wait()
        self.assertEqual(open_world(source).get_block(1,4,3),Block('glass'))
        entry=list_saves(source.parent,source.name,include_finished=True)[0];self.assertEqual(hashes(entry[0]/'original'),before)
        self.app.undo();self.assertEqual(self.app.document.get(1,4,3),Block('stone'))

    def test_original_save_cancel_preserves_world(self):
        source=java_world(self.path/'cancel-original');before=hashes(source);self.app._attach(Document(open_world(source)))
        self.app._pick((1,4,3),False);self.app.fill()
        with mock.patch('facetedit.save_ui.messagebox.askyesno',return_value=False):self.app.save_original()
        self.assertFalse(self.app.busy);self.assertEqual(hashes(source),before)

    def test_world_backup_recovery_ui(self):
        source=java_world(self.path/'restore-original');self.app._attach(Document(open_world(source)));self.app._pick((1,4,3),False)
        self.app.block_var.set('gold_block');self.app.fill()
        with mock.patch('facetedit.save_ui.messagebox.askyesno',return_value=True):self.app.save_original();self.wait()
        self.app.world_recovery_dialog();dialog=self.dialog()
        listing=self.app.world_save_list
        for i in range(listing.size()):
            if listing.get(i).startswith('restore-original '):listing.selection_set(i);break
        with mock.patch('facetedit.save_ui.messagebox.askyesno',return_value=True):self.press(dialog,'Restore original backup');self.wait()
        self.assertEqual(open_world(source).get_block(1,4,3),Block('stone'))

    def test_transform_preview_nudge_paste_and_undo(self):
        self.app.document.selection=Selection((0,40,0),(1,40,0));self.app.block_var.set('gold_block');self.app.fill();self.app.copy()
        self.app.document.selection=Selection((4,40,0),(4,40,0));self.app.transform_dialog();dialog=self.dialog()
        self.app.transform_vars['scale'][0].set('2');self.app.transform_vars['rotation'][1].set('90')
        self.press(dialog,'Preview');self.press(dialog,'X +');self.app.viewport.draw()
        for text in ('Preview','Cancel','Paste transform'):
            button=next(w for w in self.widgets(dialog) if isinstance(w,Pill) and w.text==text)
            self.assertGreaterEqual(button.winfo_height(),30)
            self.assertLessEqual(button.winfo_rooty()+button.winfo_height(),dialog.winfo_rooty()+dialog.winfo_height())
        self.assertTrue(self.app.viewport.find_withtag('paste-preview'));self.assertEqual(self.app.document.get(5,40,0),Block('air'))
        self.press(dialog,'Paste transform');self.assertIsNone(self.app.viewport.preview)
        for z in range(4):self.assertEqual(self.app.document.get(5,40,z),Block('gold_block'))
        self.app.undo();self.assertEqual(self.app.document.get(5,40,0),Block('air'))

    def test_transform_cancel_and_document_change_clear_preview(self):
        self.app.document.selection=Selection((0,40,0),(0,40,0));self.app.copy();self.app.transform_dialog();dialog=self.dialog()
        self.assertIsNotNone(self.app.viewport.preview);self.press(dialog,'Cancel');self.assertIsNone(self.app.viewport.preview)
        self.app.transform_dialog();self.dialog();self.app._attach(Document(SampleWorld()));self.app.update();self.assertIsNone(self.app.viewport.preview)
