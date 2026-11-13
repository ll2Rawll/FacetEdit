"""Run with DISPLAY set and FACETEDIT_GUI_TESTS=1 to exercise real Tk widgets."""
import os
from pathlib import Path
import tempfile
import time
import tkinter as tk
import unittest
from unittest import mock

from facetedit.blocks import AIR, Block
from facetedit.model import Document, Selection
from facetedit.world import SampleWorld
from tests.fixtures import java_world,bedrock_world


@unittest.skipUnless(os.environ.get("FACETEDIT_GUI_TESTS") == "1", "Set FACETEDIT_GUI_TESTS=1 on a desktop/X display")
class DesktopTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from facetedit.ui import FacetEditApp
        cls.temp = tempfile.TemporaryDirectory()
        cls.app = FacetEditApp(Path(cls.temp.name) / "settings.json")
        cls.app.update()

    @classmethod
    def tearDownClass(cls):
        cls.app.destroy()
        cls.temp.cleanup()

    def setUp(self):
        self.app._attach(Document(SampleWorld()))
        self.app.update()

    def test_render_has_real_pickable_geometry(self):
        self.app.viewport.draw()
        self.assertGreater(self.app.viewport.face_count, 500)
        self.assertGreater(len(self.app.viewport.picks), 500)

    def test_real_pointer_event_selects_rendered_block(self):
        canvas = self.app.viewport
        canvas.draw()
        for item in reversed(canvas.picks):
            points = canvas.coords(item)
            x = sum(points[0::2]) / 4
            y = sum(points[1::2]) / 4
            if 100 < x < canvas.winfo_width()-100 and 80 < y < canvas.winfo_height()-80:
                canvas.event_generate("<ButtonPress-1>", x=int(x), y=int(y))
                canvas.event_generate("<ButtonRelease-1>", x=int(x), y=int(y))
                break
        self.assertIsNotNone(self.app.document.selection)

    def test_keyboard_shortcut_undo(self):
        self.app._pick((2,30,2),False)
        self.app.block_var.set("minecraft:glass")
        self.app.fill()
        self.app.viewport.focus_force()
        self.app.update()
        import sys
        modifier = "Command" if sys.platform == "darwin" else "Control"
        self.app.viewport.event_generate(f"<{modifier}-z>")
        self.app.update()
        self.assertEqual(self.app.document.get(2,30,2), AIR)

    def test_selection_fill_undo_redo_buttons(self):
        self.app._pick((-8, 30, -8), False)
        self.app._pick((-7, 31, -7), True)
        self.assertEqual(self.app.document.selection.volume, 8)
        self.app.block_var.set("minecraft:gold_block")
        self.app.fill_button.invoke()
        self.assertEqual(self.app.document.get(-8, 30, -8), Block("gold_block"))
        self.app.undo_button.invoke()
        self.assertEqual(self.app.document.get(-8, 30, -8), AIR)
        self.app.redo_button.invoke()
        self.assertEqual(self.app.document.get(-8, 30, -8), Block("gold_block"))

    def test_numeric_selection(self):
        for var, value in zip(self.app.selection_vars, (1,30,1,2,31,2)):
            var.set(value)
        self.app.set_selection()
        self.assertEqual(self.app.document.selection.volume, 8)

    def test_invalid_numeric_selection_shows_error(self):
        self.app.selection_vars[0].set("no")
        with mock.patch("facetedit.ui.messagebox.showerror") as error:
            self.app.set_selection()
            error.assert_called_once()

    def test_material_search_and_pick(self):
        self.app.search_var.set("diamond")
        self.assertEqual(len(self.app.filtered_blocks), 1)
        self.app.block_list.selection_set(0)
        self.app._choose_block(None)
        self.assertEqual(self.app.block_var.get(), "minecraft:diamond_block")
        self.app.search_var.set("")

    def test_copy_paste_ui(self):
        self.app._pick((-8, 30, -8), False)
        self.app.block_var.set("minecraft:glass")
        self.app.fill()
        self.app.copy()
        self.app._pick((3, 30, 3), False)
        self.app.paste()
        self.assertEqual(self.app.document.get(3,30,3), Block("glass"))

    def test_camera_zoom_and_reset(self):
        self.app.viewport.zoom(1.4)
        self.assertAlmostEqual(self.app.viewport.scale, 26.6)
        self.app.viewport.reset()
        self.assertEqual(self.app.viewport.scale, 19)

    def test_resize_minimum_and_large(self):
        for size in ("1040x700", "1440x900"):
            self.app.geometry(size)
            self.app.update()
            self.assertGreater(self.app.viewport.winfo_width(), 500)
            self.assertGreater(self.app.viewport.winfo_height(), 450)
        self.app.geometry("1040x700")
        self.app.update()
        self.assertTrue(self.app.preferences_button.winfo_ismapped())
        self.assertLess(self.app.preferences_button.winfo_rooty() + self.app.preferences_button.winfo_height(), self.app.winfo_rooty() + self.app.winfo_height())
        self.app.inspector_scroll.yview_moveto(1)
        self.app.update()
        self.assertGreater(self.app.inspector_scroll.yview()[0], 0)
        self.app.geometry("1440x900")
        self.app.inspector_scroll.yview_moveto(0)

    def test_save_project_from_native_action(self):
        path = str(Path(self.temp.name) / "ui.facetedit")
        with mock.patch("facetedit.ui.filedialog.asksaveasfilename", return_value=path):
            self.assertTrue(self.app.save_project_dialog())
        self.assertTrue(Path(path).exists())

    def test_async_world_open_completes_on_ui_thread(self):
        path = java_world(Path(self.temp.name) / "ui-java")
        self.app.open_path(path)
        end = time.monotonic()+5
        while self.app.busy and time.monotonic() < end:
            self.app.update()
            time.sleep(.01)
        self.assertFalse(self.app.busy)
        self.assertEqual(self.app.document.world.name, "Test meadow")

    def test_native_save_copy_action_exports_edits(self):
        from facetedit.world import open_world
        path = java_world(Path(self.temp.name) / "save-java")
        destination = Path(self.temp.name) / "saved-java"
        self.app._attach(Document(open_world(path)))
        self.app._pick((1,2,3),False)
        self.app.block_var.set("minecraft:gold_block")
        self.app.fill()
        with mock.patch("facetedit.ui.filedialog.asksaveasfilename", return_value=str(destination)):
            self.app.save_copy()
        end = time.monotonic()+5
        while self.app.busy and time.monotonic() < end:
            self.app.update()
            time.sleep(.01)
        self.assertFalse(self.app.busy)
        self.assertEqual(open_world(destination).get_block(1,2,3),Block("gold_block"))
        self.assertEqual(open_world(path).get_block(1,2,3),Block("stone"))

    def test_command_palette_and_preferences_open(self):
        for function in (self.app.command_palette, self.app.preferences, self.app.help_dialog):
            function()
            self.app.update()
            dialogs = [c for c in self.app.winfo_children() if isinstance(c, tk.Toplevel)]
            self.assertEqual(len(dialogs), 1)
            dialogs[0].destroy()

    def test_close_cancel_preserves_document(self):
        self.app._pick((1,30,1), False)
        self.app.block_var.set("minecraft:stone")
        self.app.fill()
        with mock.patch("facetedit.ui.messagebox.askyesnocancel", return_value=None):
            self.assertFalse(self.app._confirm_discard())
        self.assertTrue(self.app.document.edits)

    def widgets(self,parent):
        for child in parent.winfo_children():
            yield child
            yield from self.widgets(child)

    def dialog(self):
        self.app.update()
        return next(c for c in self.app.winfo_children() if isinstance(c,tk.Toplevel))

    def press(self,parent,text):
        from facetedit.chrome import Pill
        button = next(c for c in self.widgets(parent) if isinstance(c,Pill) and c.text==text)
        button.invoke()
        self.app.update()

    def wait_for_job(self):
        end = time.monotonic()+5
        while self.app.busy and time.monotonic()<end:
            self.app.update()
            time.sleep(.01)
        self.assertFalse(self.app.busy)

    def test_segmented_inspector_tabs_all_accessible(self):
        for i,button in enumerate(self.app.inspector_tabs.buttons):
            button.invoke();self.app.update()
            self.assertEqual(self.app.inspector_tabs.current,i)
            self.assertTrue(self.app.inspector_tabs.pages[i].winfo_ismapped())
            self.assertEqual(sum(page.winfo_ismapped() for page in self.app.inspector_tabs.pages),1)
        self.app.inspector_tabs.select(0)

    def test_dark_defaults_and_compact_controls_do_not_overlap(self):
        self.assertEqual(self.app.cget('bg'),'#080f1d')
        self.assertEqual(self.app.settings.data['theme'],'midnight')
        for size in ('1040x700','1440x900','1920x1080'):
            self.app.geometry(size);self.app.update()
            dock = self.app.action_dock;inspector = self.app.inspector_panel
            self.assertLess(inspector.winfo_y()+inspector.winfo_height(),dock.winfo_y())
            self.assertLess(dock.winfo_x()+dock.winfo_width(),self.app.view_controls.winfo_x())
            rail = self.app.tool_rail
            children = rail.body.winfo_children()
            self.assertLessEqual(max(w.winfo_y()+w.winfo_height() for w in children),rail.body.winfo_height())
            self.assertEqual(bool(self.app.material_tray.winfo_ismapped()),size!='1040x700')
        self.app.geometry('1440x900');self.app.update()

    def test_compact_inspector_wheel_reaches_material_controls(self):
        self.app.geometry('1040x700');self.app.inspector_tabs.select(0);self.app.update()
        self.app.inspector_scroll.yview_moveto(0)
        for _ in range(20):
            self.app.selection_label.event_generate('<MouseWheel>',delta=-120)
        self.app.update()
        self.assertGreater(self.app.inspector_scroll.yview()[0],0)
        self.app.inspector_scroll.yview_moveto(0)
        self.app.geometry('1440x900');self.app.update()

    def test_clone_dialog_creates_real_blocks(self):
        self.app._pick((0,40,0),False)
        self.app.block_var.set('minecraft:glass');self.app.fill()
        self.app.clone_dialog();dialog = self.dialog()
        self.press(dialog,'Create copies')
        self.assertEqual(self.app.document.get(8,40,0),Block('glass'))
        self.app.undo();self.assertEqual(self.app.document.get(8,40,0),AIR)

    def test_biome_dialog_changes_cells_and_undo_restores(self):
        from tkinter import ttk
        self.app._pick((0,30,0),False)
        self.app.biome_dialog();dialog = self.dialog()
        combo = next(c for c in self.widgets(dialog) if isinstance(c,ttk.Combobox))
        combo.set('minecraft:desert');self.press(dialog,'Apply biome')
        self.assertEqual(self.app.document.get_biome(0,30,0),'minecraft:desert')
        self.app.undo();self.assertEqual(self.app.document.get_biome(0,30,0),'minecraft:plains')

    def test_nbt_dialog_updates_typed_payload_and_undo_restores(self):
        from facetedit import nbt
        from facetedit.nbt_edit import from_json,to_json
        from facetedit.world import open_world
        self.app._attach(Document(open_world(java_world(Path(self.temp.name)/'nbt-ui'))))
        self.app._pick((1,2,3),False)
        original = self.app.document.get_entity(1,2,3)
        self.app.nbt_dialog();dialog = self.dialog()
        editor = self.app.nbt_editor
        tag = from_json(editor.get('1.0','end-1c'))
        tag.value['CustomName'] = nbt.Tag(nbt.STRING,'UI treasure')
        editor.delete('1.0','end');editor.insert('1.0',to_json(tag))
        self.press(dialog,'Apply NBT')
        self.assertEqual(nbt.get(nbt.loads(self.app.document.get_entity(1,2,3))[1],'CustomName'),'UI treasure')
        self.app.undo();self.assertEqual(self.app.document.get_entity(1,2,3),original)

    def test_history_rewind_keeps_redo(self):
        self.app._pick((0,40,0),False)
        for name in ('stone','glass','gold_block'):
            self.app.block_var.set(name);self.app.fill()
        self.app.history_list.selection_set(1);self.app.history_restore()
        self.assertEqual(self.app.document.get(0,40,0),Block('stone'))
        self.assertEqual(len(self.app.document.redo_stack),2)
        self.app.redo();self.assertEqual(self.app.document.get(0,40,0),Block('glass'))

    def test_mcworld_native_export_and_import_actions(self):
        from facetedit.world import open_world
        root = Path(self.temp.name)
        source = bedrock_world(root/'archive-ui')
        self.app._attach(Document(open_world(source)))
        self.app._pick((1,2,3),False)
        self.app.block_var.set('gold_block');self.app.fill()
        archive = root/'ui.mcworld'
        with mock.patch('facetedit.ui.filedialog.asksaveasfilename',return_value=str(archive)):
            self.app.export_world_archive()
        self.wait_for_job();self.assertTrue(archive.exists())
        output = root/'archive-ui-imported'
        with mock.patch('facetedit.ui.filedialog.askopenfilename',return_value=str(archive)),mock.patch('facetedit.ui.filedialog.asksaveasfilename',return_value=str(output)):
            self.app.import_world_archive()
        self.wait_for_job()
        self.assertEqual(self.app.document.get(1,2,3),Block('gold_block'))
        self.assertEqual(self.app.document.world.path,output)
        self.assertEqual(open_world(source).get_block(1,2,3),Block('stone'))

    def test_glass_button_keyboard_activation(self):
        self.app._pick((0,40,0),False)
        self.app.block_var.set('diamond_block')
        self.app.fill_button.focus_force();self.app.update()
        self.app.fill_button.event_generate('<Return>');self.app.update()
        self.assertEqual(self.app.document.get(0,40,0),Block('diamond_block'))

    def test_new_dialogs_fit_on_screen(self):
        for function in (self.app.clone_dialog,self.app.nudge_dialog,self.app.material_dialog):
            function();dialog = self.dialog()
            self.assertGreaterEqual(dialog.winfo_rootx(),0)
            self.assertGreaterEqual(dialog.winfo_rooty(),0)
            self.assertLessEqual(dialog.winfo_rootx()+dialog.winfo_width(),dialog.winfo_screenwidth())
            self.assertLessEqual(dialog.winfo_rooty()+dialog.winfo_height(),dialog.winfo_screenheight())
            dialog.destroy()
