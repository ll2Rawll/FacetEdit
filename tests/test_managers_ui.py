import os
from pathlib import Path
import tempfile
import time
import tkinter as tk
import unittest
from unittest import mock

from facetedit.blocks import Block
from facetedit.chrome import Pill
from facetedit.model import Document,Selection
from facetedit.recovery import RecoveryStore
from facetedit.structures import load_project
from facetedit.world import SampleWorld,open_world
from tests.fixtures import java_world
from tests.test_workflows import hashes


@unittest.skipUnless(os.environ.get('FACETEDIT_GUI_TESTS')=='1','Desktop test flag required')
class ManagerDesktopTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from facetedit.ui import FacetEditApp
        cls.temp=tempfile.TemporaryDirectory();cls.path=Path(cls.temp.name)
        cls.app=FacetEditApp(cls.path/'settings.json');cls.app.update()
    @classmethod
    def tearDownClass(cls):cls.app.destroy();cls.temp.cleanup()

    def setUp(self):
        self.app._attach(Document(SampleWorld()));self.app.update()
        self.errors=[]
        self.error_patch=mock.patch('facetedit.ui.messagebox.showerror',side_effect=lambda *a,**k:self.errors.append(a))
        self.error_patch.start()
    def tearDown(self):
        for child in self.app.winfo_children():
            if isinstance(child,tk.Toplevel):child.destroy()
        self.error_patch.stop();self.assertFalse(self.errors)

    def dialog(self):
        self.app.update()
        return next(c for c in self.app.winfo_children() if isinstance(c,tk.Toplevel))

    def widgets(self,parent):
        for child in parent.winfo_children():
            yield child;yield from self.widgets(child)

    def press(self,parent,text):
        next(w for w in self.widgets(parent) if isinstance(w,Pill) and w.text==text).invoke();self.app.update()

    def wait(self,recovery=False):
        end=time.monotonic()+5
        while (self.app._recovery_inflight if recovery else self.app.busy) and time.monotonic()<end:
            self.app.update();time.sleep(.01)
        self.assertFalse(self.app._recovery_inflight if recovery else self.app.busy)
        self.app.update()

    def open_chunks(self,name):
        source=java_world(self.path/name)
        self.app._attach(Document(open_world(source)))
        self.app.chunks_dialog();dialog=self.dialog();self.wait()
        return source,dialog

    def chunk_bounds(self,dialog,values):
        for variable,value in zip(self.app.chunk_vars,values):variable.set(value)
        self.press(dialog,'Select these chunks')

    def test_regions_add_subtract_and_fill_union(self):
        self.app.regions_dialog();dialog=self.dialog()
        for values in ((0,40,0,1,41,1),(1,40,0,2,41,1)):
            for variable,value in zip(self.app.region_vars,values):variable.set(value)
            self.press(dialog,'Add box')
        self.assertEqual(self.app.document.selection.volume,12)
        for variable,value in zip(self.app.region_vars,(1,40,0,1,40,0)):variable.set(value)
        self.press(dialog,'Subtract box');self.assertEqual(self.app.document.selection.volume,11)
        self.app.block_var.set('gold_block');self.app.fill_button.invoke()
        self.assertEqual(len(self.app.document.edits),11)
        self.assertNotEqual(self.app.document.get(1,40,0),Block('gold_block'))

    def test_chunk_map_pointer_add_and_subtract(self):
        _,dialog=self.open_chunks('map')
        canvas=self.app.chunk_map;x,y=canvas.winfo_width()//2,canvas.winfo_height()//2
        canvas.event_generate('<Button-1>',x=x,y=y);self.app.update()
        first=self.app.document.selection.chunks()
        canvas.event_generate('<Button-1>',x=x+27,y=y,state=1);self.app.update()
        self.assertEqual(len(self.app.document.selection.chunks()),2)
        canvas.event_generate('<Button-3>',x=x,y=y);self.app.update()
        self.assertFalse(self.app.document.selection.chunks()&first)

    def test_chunk_create_fill_save_copy_from_ui(self):
        source,dialog=self.open_chunks('new-chunk');before=hashes(source)
        self.chunk_bounds(dialog,(2,0,2,0));self.press(dialog,'Create empty chunks');self.wait()
        self.assertIn((2,0),self.app.document.chunk_positions())
        self.app._pick((33,2,3),False);self.app.block_var.set('glass');self.app.fill()
        output=self.path/'new-chunk-output'
        with mock.patch('facetedit.ui.filedialog.asksaveasfilename',return_value=str(output)):self.app.save_copy()
        self.wait();self.assertEqual(open_world(output).get_block(33,2,3),Block('glass'))
        self.assertEqual(hashes(source),before)

    def test_chunk_delete_undo_redo(self):
        _,dialog=self.open_chunks('delete')
        self.chunk_bounds(dialog,(0,0,0,0));self.press(dialog,'Delete selected chunks');self.wait()
        self.assertNotIn((0,0),self.app.document.chunk_positions())
        self.app.undo_button.invoke();self.app.update();self.assertIn((0,0),self.app.document.chunk_positions())
        self.app.redo_button.invoke();self.app.update();self.assertNotIn((0,0),self.app.document.chunk_positions())

    def test_chunk_prune_confirmation_and_cancel(self):
        _,dialog=self.open_chunks('prune');self.chunk_bounds(dialog,(0,0,0,0))
        with mock.patch('facetedit.managers.messagebox.askyesno',return_value=False):self.press(dialog,'Prune outside selection…')
        self.assertEqual(len(self.app.document.chunk_positions()),5)
        with mock.patch('facetedit.managers.messagebox.askyesno',return_value=True):self.press(dialog,'Prune outside selection…')
        self.wait();self.assertEqual(self.app.document.chunk_positions(),{(0,0)})

    def test_chunk_import_from_native_folder_action(self):
        source=Document(open_world(java_world(self.path/'import-source')))
        source.apply('gold',[((1,2,3),Block('gold_block'))])
        imported=self.path/'import-edited';source.world.export(imported,source.edits,**source.export_metadata())
        _,dialog=self.open_chunks('import-target');self.chunk_bounds(dialog,(0,0,0,0))
        with mock.patch('facetedit.managers.filedialog.askdirectory',return_value=str(imported)):
            self.press(dialog,'Import chunks from world…')
        self.wait();self.assertEqual(self.app.document.get(1,2,3),Block('gold_block'))

    def checkpoint(self):
        self.app._pick((0,40,0),False);self.app.block_var.set('glass');self.app.fill()
        self.app._autosave_tick(reschedule=False);self.wait(recovery=True)

    def test_background_recovery_restores_without_losing_checkpoint(self):
        self.checkpoint();self.assertTrue(self.app.recovery.path.exists())
        self.app.block_var.set('gold_block');self.app.fill()
        self.app.recovery_dialog();dialog=self.dialog();self.app.recovery_list.selection_set(0)
        with mock.patch('facetedit.managers.messagebox.askyesnocancel',return_value=False):
            self.press(dialog,'Restore workspace');self.wait()
        self.assertEqual(self.app.document.get(0,40,0),Block('glass'))
        self.assertTrue(self.app.recovery.path.exists())
        self.assertNotEqual(self.app.document.revision,self.app._saved_revision)

    def test_manual_project_save_clears_recovery(self):
        self.checkpoint();file=self.path/'manual.facet'
        with mock.patch('facetedit.ui.filedialog.asksaveasfilename',return_value=str(file)):
            self.assertTrue(self.app.save_project_dialog())
        self.assertFalse(self.app.recovery.path.exists())
        self.assertEqual(load_project(file).get(0,40,0),Block('glass'))

    def test_recovery_preference_disables_checkpointing(self):
        self.app.settings.data['autosave']=False
        try:
            self.checkpoint();self.assertFalse(self.app.recovery.path.exists())
        finally:self.app.settings.data['autosave']=True

    def test_source_recovery_contains_chunk_transactions(self):
        _,dialog=self.open_chunks('chunk-checkpoint');self.chunk_bounds(dialog,(0,0,0,0))
        self.press(dialog,'Delete selected chunks');self.wait()
        self.app._autosave_tick(reschedule=False);self.wait(recovery=True)
        restored=load_project(self.app.recovery.path)
        self.assertNotIn((0,0),restored.chunk_positions())

    def test_new_manager_controls_fit_screen(self):
        _,dialog=self.open_chunks('fit')
        for title in ('Create empty chunks','Delete selected chunks','Prune outside selection…','Import chunks from world…','Center map on selection'):
            button=next(w for w in self.widgets(dialog) if isinstance(w,Pill) and w.text==title)
            self.assertLessEqual(button.winfo_rooty()+button.winfo_height(),dialog.winfo_rooty()+dialog.winfo_height())
            self.assertTrue(button.winfo_ismapped())
            self.assertGreaterEqual(button.winfo_height(),30)
        self.assertLessEqual(dialog.winfo_rooty()+dialog.winfo_height(),dialog.winfo_screenheight())

    def test_current_recovery_can_restore_after_saving_newer_edits(self):
        self.checkpoint();self.app.block_var.set('gold_block');self.app.fill()
        self.app.recovery_dialog();dialog=self.dialog();self.app.recovery_list.selection_set(0)
        file=self.path/'newer.facet'
        with mock.patch('facetedit.managers.messagebox.askyesnocancel',return_value=True),mock.patch('facetedit.ui.filedialog.asksaveasfilename',return_value=str(file)):
            self.press(dialog,'Restore workspace');self.wait()
        self.assertEqual(load_project(file).get(0,40,0),Block('gold_block'))
        self.assertEqual(self.app.document.get(0,40,0),Block('glass'))
        self.wait(recovery=True)
        self.assertTrue(self.app.recovery.path.exists())
        self.assertEqual(load_project(self.app.recovery.path).get(0,40,0),Block('glass'))

    def test_opening_new_world_closes_stale_managers(self):
        _,dialog=self.open_chunks('stale')
        self.app._attach(Document(SampleWorld()));self.app.update()
        self.assertFalse(dialog.winfo_exists())
