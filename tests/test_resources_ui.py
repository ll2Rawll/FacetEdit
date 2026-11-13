import os,tempfile,time,tkinter as tk,unittest
from pathlib import Path
from unittest import mock
from facetedit.blocks import Block
from facetedit.model import Document,Selection
from facetedit.settings import Settings
from facetedit.world import SampleWorld
from tests.resource_fixture import pack


@unittest.skipUnless(os.environ.get('FACETEDIT_GUI_TESTS')=='1','Desktop test flag required')
class ResourceDesktopTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from facetedit.ui import FacetEditApp
        cls.temp=tempfile.TemporaryDirectory();cls.root=Path(cls.temp.name);cls.pack,_=pack(cls.root/'pack')
        cls.app=FacetEditApp(cls.root/'settings.json');cls.app.update()

    @classmethod
    def tearDownClass(cls):cls.app.destroy();cls.temp.cleanup()

    def setUp(self):
        self.app.viewport.set_resources(None);self.app.viewport.set_mode('orbit');self.app._attach(Document(SampleWorld()))
        self.app.viewport.radius=6;self.app.viewport.reset();self.app.update()

    def tearDown(self):
        for child in self.app.winfo_children():
            if isinstance(child,tk.Toplevel):child.destroy()
        self.app.viewport.set_resources(None);self.app.viewport.stop_flight()

    def until(self,condition,timeout=15):
        deadline=time.monotonic()+timeout
        while time.monotonic()<deadline:
            self.app.update()
            if condition():return
            time.sleep(.004)
        self.fail('Desktop resource action timed out: '+self.app.status_var.get()+' / '+str(self.app.viewport._frame_error))

    def load(self,backend='auto'):
        self.app.load_resources([self.pack],backend=backend)
        self.until(lambda:self.app.viewport._display_frame is not None)
        self.until(lambda:bool(self.app.viewport.find_withtag('textured-terrain')))
        self.app.viewport.draw();self.app.update();return self.app.viewport

    def test_stack_dialog_applies_reorders_and_persists(self):
        self.app.settings.data['resource_packs']=[];self.app.resources_dialog();controls=self.app.resource_controls
        controls['add'](self.pack);other,_=pack(self.root/'other');controls['add'](other);controls['move'](-1)
        self.assertEqual(self.app.resource_paths[0],str(other));controls['remove']();self.assertEqual(self.app.resource_paths,[str(self.pack)])
        controls['backend'].set('auto');controls['enabled'].set(True);controls['apply']()
        self.until(lambda:self.app.viewport._display_frame is not None)
        self.until(lambda:bool(self.app.viewport.find_withtag('textured-terrain')))
        saved=Settings(self.root/'settings.json');self.assertEqual(saved.data['resource_packs'],[str(self.pack)])
        self.assertEqual(self.app.viewport.resources.paths,(str(self.pack),));self.assertTrue(self.app.viewport.find_withtag('textured-terrain'))

    def test_real_pointer_model_pick_fill_and_undo(self):
        view=self.load();frame=view._display_frame;position=None
        for y in range(200,550,15):
            for x in range(330,900,15):
                position=frame.scene.pick(*frame.view.ray(x,y),ticks=frame.ticks)
                if position is not None:break
            if position is not None:break
        self.assertIsNotNone(position);before=self.app.document.get(*position)
        view.event_generate('<ButtonPress-1>',x=x,y=y);view.event_generate('<ButtonRelease-1>',x=x,y=y);self.app.update()
        self.assertEqual(self.app.document.selection.a,position)
        self.app.block_var.set('diamond_block');self.app.fill_button.invoke();self.assertEqual(self.app.document.get(*position),Block('diamond_block'))
        self.until(lambda:view.scene is not frame.scene and view._display_frame.scene is view.scene)
        self.assertTrue(view.find_withtag('model-selection'))
        self.app.undo_button.invoke();self.assertEqual(self.app.document.get(*position),before)

    def test_flight_resize_and_preview_use_displayed_projection(self):
        view=self.load();self.app.toggle_camera();self.until(lambda:view._display_frame is not None and view._display_frame.view.perspective)
        old=view._display_frame;self.app.geometry('1100x730');self.until(lambda:view._display_frame is not old and view._display_frame.view.width==view.winfo_width())
        self.app.document.selection=Selection((0,5,0),(1,6,1));self.app.document.copy();view.preview=(self.app.document.clipboard,(2,8,2));view.draw()
        self.assertTrue(view.find_withtag('paste-preview'));self.app.geometry('1440x900')

    def test_software_backend_and_idle_polling_stops(self):
        view=self.load('software');self.assertIn('software',view.render_status);self.assertGreater(view._display_frame.zoom,1)
        self.until(lambda:view._frame_poll is None and view._geometry_poll is None)
        self.assertIsNone(view._animation_id);self.assertTrue(view.find_withtag('textured-terrain'))

    def test_invalid_pack_keeps_current_resources(self):
        view=self.load();stack=view.resources
        with mock.patch.object(self.app,'show_error') as error:
            self.app.load_resources([self.root/'missing.zip']);self.until(lambda:not self.app.busy)
            error.assert_called_once();self.assertIs(view.resources,stack)

    def test_disable_and_world_switch_discard_old_frames(self):
        view=self.load();old=view._frames;self.app._attach(Document(SampleWorld()));self.assertIsNone(view._display_frame)
        self.until(lambda:view._display_frame is not None);old.join(2);self.assertFalse(old._thread.is_alive())
        self.app.load_resources([self.pack],enabled=False);self.until(lambda:not self.app.busy)
        self.assertIsNone(view.resources);self.assertIsNone(view._frames);view.draw();self.assertGreater(len(view.picks),0)

    def test_diagnostics_panel_and_reload_invalidate_cache(self):
        view=self.load();old=view.scene
        self.app.resources_dialog();self.app.resource_controls['diagnostics']();self.app.update()
        windows=[c for c in self.app.winfo_children() if isinstance(c,tk.Toplevel)]
        self.assertGreaterEqual(len(windows),2)
        self.app.resource_controls['enabled'].set(True);self.app.resource_controls['backend'].set('auto');self.app.resource_controls['apply']()
        self.until(lambda:view.scene is not None and view.scene is not old and view._display_frame is not None)
        self.assertIsNot(view.scene,old)

    def test_animated_texture_advances_and_disabling_stops_idle_frames(self):
        self.app.document.apply('Animated block',[((0,30,0),Block('animated'))])
        self.app.load_resources([self.pack],animate=True);view=self.app.viewport
        self.until(lambda:view._display_frame is not None);old=view._display_frame
        self.until(lambda:view._display_frame is not old and view._display_frame.ticks!=old.ticks)
        self.assertIsNotNone(view._animation_id)
        view.set_resources(view.resources,animate=False)
        self.until(lambda:view._display_frame is not None and view._display_frame.ticks==0 and view._frame_poll is None)
        self.assertIsNone(view._animation_id)

    def test_frame_handoff_keeps_visible_image_and_picking_until_redraw(self):
        view=self.load();old_frame=view._display_frame;old_image=view._terrain_image
        view.angle+=.1;projection=view._view_snapshot(view.winfo_width(),view.winfo_height())
        key=(id(view.scene),projection,0);view._requested_frame=key
        with mock.patch.object(view,'schedule'):
            view._frames.request(key,view.scene,projection);view._poll_frames()
            self.until(lambda:view._ready_frame is not None)
            self.assertIs(view._display_frame,old_frame);self.assertIs(view._terrain_image,old_image)
            self.assertEqual(view.itemcget(view.find_withtag('textured-terrain')[0],'image'),str(old_image))
        view.draw()
        self.assertIsNot(view._display_frame,old_frame);self.assertEqual(view._display_frame.view,projection)
        self.assertEqual(view.itemcget(view.find_withtag('textured-terrain')[0],'image'),str(view._terrain_image))
