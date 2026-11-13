import os
from pathlib import Path
import tempfile
import time
import tkinter as tk
import unittest
from unittest import mock

from facetedit.blocks import Block
from facetedit.model import Clipboard,Document,Selection
from facetedit.world import SampleWorld,open_world
from tests.test_conversion import plain_java,modern_bedrock
from facetedit.construction import save_construction,load_construction


@unittest.skipUnless(os.environ.get('FACETEDIT_GUI_TESTS')=='1','Desktop test flag required')
class ConversionDesktopTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from facetedit.ui import FacetEditApp
        cls.temp=tempfile.TemporaryDirectory();cls.path=Path(cls.temp.name)
        cls.app=FacetEditApp(cls.path/'settings.json');cls.app.update()

    @classmethod
    def tearDownClass(cls):cls.app.destroy();cls.temp.cleanup()

    def setUp(self):
        self.app._attach(Document(SampleWorld()));self.app.update()
        self.errors=[];self.patcher=mock.patch('facetedit.ui.messagebox.showerror',side_effect=lambda *a,**k:self.errors.append(a));self.patcher.start()

    def tearDown(self):
        for child in self.app.winfo_children():
            if isinstance(child,tk.Toplevel):child.destroy()
        self.patcher.stop();self.assertFalse(self.errors)

    def dialog(self):
        self.app.update()
        return next(w for w in self.app.winfo_children() if isinstance(w,tk.Toplevel))

    def assert_actions_visible(self,window):
        from facetedit.chrome import Pill
        def walk(parent):
            for child in parent.winfo_children():
                yield child;yield from walk(child)
        self.app.update()
        for widget in walk(window):
            if isinstance(widget,Pill):
                self.assertTrue(widget.winfo_ismapped(),widget.text)
                self.assertLessEqual(widget.winfo_rooty()+widget.winfo_height(),window.winfo_rooty()+window.winfo_height(),widget.text)

    def wait(self):
        deadline=time.monotonic()+15
        while self.app.busy and time.monotonic()<deadline:
            self.app.update();time.sleep(.01)
        self.assertFalse(self.app.busy)
        self.app.update()

    def test_material_search_states_and_actual_fill(self):
        self.app.material_dialog();dialog=self.dialog();c=dialog.material_controls
        c['search'].set('oak stairs');self.app.update()
        self.assertIn('half',c['states'])
        c['states']['facing'].set('east');c['states']['half'].set('top')
        self.assertIn('facing=east',c['preview'].get())
        c['choose']();self.app.document.selection=Selection((1,30,1),(1,30,1));self.app.fill()
        self.assertEqual(dict(self.app.document.get(1,30,1).properties)['half'],'top')
        self.app.undo();self.assertTrue(self.app.document.get(1,30,1).air)

    def test_bedrock_material_state_types_survive_text_field(self):
        target=open_world(modern_bedrock(self.path/'bedrock-material'))
        self.app._attach(Document(target));self.app.material_dialog();dialog=self.dialog();c=dialog.material_controls
        c['search'].set('acacia stairs');self.app.update()
        c['states']['weirdo_direction'].set('2');c['states']['upside_down_bit'].set('true');c['choose']()
        self.app.document.selection=Selection((1,1,1),(1,1,1));self.app.fill()
        self.assertEqual(dict(self.app.document.get(1,1,1).state_types),{'upside_down_bit':1,'weirdo_direction':3})

    def test_clipboard_preflight_use_and_paste(self):
        target=open_world(modern_bedrock(self.path/'bedrock-clipboard'))
        self.app._attach(Document(target));self.app.document.clipboard=Clipboard((1,1,1),{(0,0,0):Block.parse('oak_log[axis=x]')})
        self.app.translate_clipboard_dialog();dialog=self.dialog();c=dialog.conversion_controls
        self.assert_actions_visible(dialog)
        c['preview']();self.wait();self.assertIsNotNone(c['prepared'][0])
        self.assertIn('1 / 1',c['report'].get('1.0','end'))
        c['use']();self.app.document.paste((1,5,1))
        self.assertEqual(dict(self.app.document.get(1,5,1).properties),{'pillar_axis':'x'})

    def test_unknown_clipboard_does_not_enable_application(self):
        original=Clipboard((1,1,1),{(0,0,0):Block('custom:machine')});self.app.document.clipboard=original
        self.app.translate_clipboard_dialog();c=self.dialog().conversion_controls
        c['target'].set('Bedrock 1.21.50');c['preview']();self.wait();c['use']()
        self.assertIs(self.app.document.clipboard,original)
        self.assertIn('BLOCKED',c['report'].get('1.0','end'))

    def test_material_variables_and_traces_are_released_when_rebuilt_and_closed(self):
        self.app.material_dialog();dialog=self.dialog();c=dialog.material_controls
        c['search'].set('oak_stairs');self.app.update()
        previous=list(c['states'].values())
        commands=[name for var in previous for _,name in var.trace_info()]
        c['search'].set('gold_block');self.app.update()
        for variable in previous:
            self.assertFalse(self.app.tk.getboolean(self.app.tk.call('info','exists',str(variable))))
        for name in commands:
            self.assertFalse(self.app.tk.call('info','commands',name))
        retained=[c['search'],c['profile'],c['preview'],*c['states'].values()]
        dialog.destroy()
        for variable in retained:
            self.assertFalse(self.app.tk.getboolean(self.app.tk.call('info','exists',str(variable))))
            self.assertIsNone(variable._tk)

    def test_material_properties_scroll_and_keyboard_focus_reveals_last_control(self):
        from tkinter import ttk
        self.app.material_dialog();dialog=self.dialog();c=dialog.material_controls
        dialog.geometry('680x520');c['search'].set('cobblestone_wall');self.app.update()
        canvas=c['state_canvas'];self.assertLess(canvas.yview()[1],1)
        combos=[child for row in c['state_panel'].winfo_children() for child in row.winfo_children() if isinstance(child,ttk.Combobox)]
        last=combos[-1];last.focus_force();self.app.update()
        self.assertGreater(canvas.yview()[0],0)
        self.assertGreaterEqual(last.winfo_rooty(),canvas.winfo_rooty())
        self.assertLessEqual(last.winfo_rooty()+last.winfo_height(),canvas.winfo_rooty()+canvas.winfo_height()+1)
        c['states']['waterlogged'].set('true');self.assertIn('waterlogged=true',c['preview'].get())
        self.assert_actions_visible(dialog)

    def test_closed_preflight_dialog_releases_prepared_files_without_publication(self):
        doc=plain_java(self.path/'java-closed');target=modern_bedrock(self.path/'bedrock-closed')
        self.app._attach(doc);self.app.convert_world_dialog();dialog=self.dialog();c=dialog.conversion_controls
        c['template'].set(str(target));c['preview']();self.wait()
        temporary=Path(c['plan'][0].temporary.name);self.assertTrue(temporary.exists())
        dialog.destroy()
        self.assertTrue(c['cancel'].is_set());self.assertIsNone(c['plan'][0]);self.assertFalse(temporary.exists())

    def test_changed_translation_options_discard_background_result(self):
        import threading
        from facetedit.translation import translate_clipboard
        gate=threading.Event()
        self.app.document.clipboard=Clipboard((1,1,1),{(0,0,0):Block('stone')})
        self.app.translate_clipboard_dialog();c=self.dialog().conversion_controls
        c['target'].set('Bedrock 1.21.50')
        def slow(*args,**kwargs):
            if not gate.wait(5):raise RuntimeError('Test gate timed out')
            return translate_clipboard(*args,**kwargs)
        with mock.patch('facetedit.conversion_ui.translate_clipboard',side_effect=slow):
            try:
                c['preview']();c['target'].set('Java 1.21.4')
            finally:gate.set()
            self.wait()
        self.assertIsNone(c['prepared'][0]);self.assertIn('Options changed',c['report'].get('1.0','end'))

    def test_construction_import_and_export_menu_paths(self):
        incoming=self.path/'incoming.construction';save_construction(Clipboard((1,1,1),{(0,0,0):Block('gold_block')}),incoming)
        with mock.patch('facetedit.ui.filedialog.askopenfilename',return_value=str(incoming)):
            self.app.import_dialog()
        self.assertEqual(self.app.document.clipboard.blocks[(0,0,0)],Block('gold_block'))
        self.app.document.selection=Selection((1,30,1),(1,30,1));self.app.document.paste()
        outgoing=self.path/'outgoing.construction'
        with mock.patch('facetedit.ui.filedialog.asksaveasfilename',return_value=str(outgoing)):
            self.app.export_dialog()
        self.assertEqual(load_construction(outgoing).blocks[(0,0,0)],Block('gold_block'))

    def test_world_preflight_and_save_through_desktop_callbacks(self):
        doc=plain_java(self.path/'java-convert');target=modern_bedrock(self.path/'bedrock-convert')
        self.app._attach(doc);self.app.convert_world_dialog();c=self.dialog().conversion_controls
        self.assert_actions_visible(self.dialog())
        c['template'].set(str(target));c['preview']();self.wait()
        self.assertTrue(c['plan'][0].report.ok,c['report'].get('1.0','end'))
        output=self.path/'desktop-converted'
        with mock.patch('facetedit.conversion_ui.filedialog.asksaveasfilename',return_value=str(output)):
            c['publish']()
        self.wait();self.assertEqual(open_world(output).get_block(512,1,0),Block('stone'))
        self.assertIn('saved',self.app.status_var.get())

    def test_world_library_search_and_open_without_loading_database_during_scan(self):
        root=self.path/'library';doc=plain_java(root/'java');modern_bedrock(root/'bedrock')
        self.app.settings.data['world_roots']=[str(root)]
        with mock.patch('facetedit.library_ui.standard_paths',return_value=()):
            self.app.open_dialog();dialog=self.dialog();self.wait()
        self.assert_actions_visible(dialog)
        c=dialog.library_controls;self.assertEqual(len(c['worlds']),2)
        c['search'].set('Test meadow');self.app.update();items=c['listing'].get_children();self.assertEqual(len(items),1)
        c['listing'].selection_set(items[0]);c['open']();self.wait()
        self.assertEqual(self.app.document.world.path,doc.world.path)

    def test_navigation_controls_change_actual_key_movement_and_persist(self):
        self.app.navigation_dialog();dialog=self.dialog();c=dialog.navigation_controls
        self.assert_actions_visible(dialog)
        c['values']['speed'].set('16');c['values']['fov'].set('90');c['bindings']['forward'].set('i');c['save']()
        view=self.app.viewport;view.set_mode('fly');view.focus_force();self.app.update()
        before=tuple(view.camera.position);view.event_generate('<KeyPress-i>')
        deadline=time.monotonic()+.06
        while time.monotonic()<deadline:self.app.update();time.sleep(.004)
        view.event_generate('<KeyRelease-i>');self.app.update();view.stop_flight()
        self.assertNotEqual(tuple(view.camera.position),before)
        self.assertEqual(view.camera.fov,90);self.assertEqual(view.camera.speed,16)
        from facetedit.settings import Settings
        self.assertEqual(Settings(self.path/'settings.json').data['navigation']['bindings']['forward'],'i')
        from facetedit.navigation import apply_navigation,validate_navigation
        defaults=validate_navigation({});self.app.settings.data['navigation']=defaults;apply_navigation(view,defaults);view.set_mode('orbit')
