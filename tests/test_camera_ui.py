import math
import os
from pathlib import Path
import tempfile
import time
import tkinter as tk
from tkinter import ttk
import unittest

from facetedit.blocks import Block
from facetedit.chrome import Pill
from facetedit.model import Document,Selection
from facetedit.world import SampleWorld


@unittest.skipUnless(os.environ.get('FACETEDIT_GUI_TESTS')=='1','Desktop test flag required')
class CameraDesktopTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from facetedit.ui import FacetEditApp
        cls.temp=tempfile.TemporaryDirectory();cls.app=FacetEditApp(Path(cls.temp.name)/'settings.json');cls.app.update()
    @classmethod
    def tearDownClass(cls):cls.app.destroy();cls.temp.cleanup()
    def setUp(self):
        self.app.viewport.set_mode('orbit');self.app._attach(Document(SampleWorld()))
        self.app.viewport.radius=8;self.app.viewport.reset();self.app.update()
    def tearDown(self):
        self.app.viewport.stop_flight()
        for child in self.app.winfo_children():
            if isinstance(child,tk.Toplevel):child.destroy()

    def fly(self):
        self.app.camera_button.invoke();self.app.update();self.app.viewport.draw()
        return self.app.viewport

    def pump(self,duration=.08):
        end=time.monotonic()+duration
        while time.monotonic()<end:self.app.update();time.sleep(.003)

    def test_mode_button_draws_perspective_and_returns_to_orbit(self):
        view=self.fly()
        self.assertEqual(view.mode,'fly');self.assertGreater(view.face_count,100)
        self.assertIn('PERSPECTIVE',self.app.view_label.cget('text'))
        self.app.camera_button.invoke();self.app.update();self.assertEqual(view.mode,'orbit')

    def test_flight_real_pointer_picks_and_fill_undo(self):
        view=self.fly()
        for item in reversed(view.picks):
            points=view.coords(item);x=sum(points[::2])/(len(points)/2);y=sum(points[1::2])/(len(points)/2)
            if 270<x<view.winfo_width()-340 and 150<y<view.winfo_height()-170:
                view.event_generate('<ButtonPress-1>',x=int(x),y=int(y));view.event_generate('<ButtonRelease-1>',x=int(x),y=int(y));break
        self.assertIsNotNone(self.app.document.selection)
        position=self.app.document.selection.a;before=self.app.document.get(*position)
        self.app.block_var.set('gold_block');self.app.fill_button.invoke()
        self.assertEqual(self.app.document.get(*position),Block('gold_block'))
        self.app.undo_button.invoke();self.assertEqual(self.app.document.get(*position),before)

    def test_wasd_moves_and_release_stops_idle_loop(self):
        view=self.fly();view.focus_force();self.app.update();before=tuple(view.camera.position)
        view.event_generate('<KeyPress-w>');self.pump()
        view.event_generate('<KeyRelease-w>');self.pump(.03)
        self.assertNotEqual(tuple(view.camera.position),before)
        self.assertFalse(view._keys);self.assertIsNone(view._flight_id)

    def test_typing_in_entry_does_not_move_camera(self):
        view=self.fly();entry=ttk.Entry(self.app);entry.pack();entry.focus_force();self.app.update()
        before=tuple(view.camera.position)
        entry.event_generate('<KeyPress-w>');entry.event_generate('<KeyRelease-w>');self.pump()
        self.assertEqual(tuple(view.camera.position),before);self.assertEqual(entry.get(),'w');entry.destroy()

    def test_focus_loss_stops_held_key(self):
        view=self.fly();view.focus_force();self.app.update();view.event_generate('<KeyPress-w>');self.pump()
        self.app.camera_button.focus_force();self.app.update()
        before=tuple(view.camera.position);self.pump()
        self.assertEqual(tuple(view.camera.position),before);self.assertIsNone(view._flight_id)

    def test_drag_looks_without_selecting_and_scroll_changes_speed(self):
        view=self.fly();yaw=view.camera.yaw
        view.event_generate('<ButtonPress-3>',x=500,y=300)
        view.event_generate('<B3-Motion>',x=550,y=310)
        view.event_generate('<ButtonRelease-3>',x=550,y=310)
        self.assertNotEqual(yaw,view.camera.yaw);self.assertIsNone(self.app.document.selection)
        speed=view.camera.speed;view.event_generate('<Button-4>');self.assertGreater(view.camera.speed,speed)

    def test_near_plane_selection_and_underground_faces_render(self):
        doc=self.app.document;doc.selection=Selection((0,0,0),(1,5,1));doc.delete()
        view=self.fly();view.go_to(.5,3,.5);view.camera.yaw=math.pi;view.camera.pitch=0
        view.draw()
        self.assertGreater(view.face_count,0)
        for item in view.picks:
            self.assertTrue(all(math.isfinite(c) and abs(c)<5000 for c in view.coords(item)))

    def test_movement_changes_geometry_tiles_but_look_reuses_mesh(self):
        view=self.fly();faces=view.faces;view.camera.look(10,10);view.draw();self.assertIs(view.faces,faces)
        view.camera.position[0]+=8;view.draw();self.assertIsNot(view.faces,faces)

    def test_f5_and_new_world_stop_flight(self):
        view=self.app.viewport;view.focus_force();self.app.update();view.event_generate('<F5>');self.app.update()
        self.assertEqual(view.mode,'fly')
        view.event_generate('<KeyPress-e>');self.pump()
        self.app._attach(Document(SampleWorld()));self.assertFalse(view._keys);self.assertIsNone(view._flight_id)

    def test_goto_moves_perspective_camera(self):
        view=self.fly();self.app.goto_dialog();self.app.update()
        dialog=next(c for c in self.app.winfo_children() if isinstance(c,tk.Toplevel))
        def all_widgets(parent):
            for child in parent.winfo_children():yield child;yield from all_widgets(child)
        widgets=list(all_widgets(dialog));entries=[w for w in widgets if isinstance(w,ttk.Entry)]
        for entry,value in zip(entries,(5,22,-8)):entry.delete(0,'end');entry.insert(0,str(value))
        next(w for w in widgets if isinstance(w,Pill) and w.text=='Go to location').invoke()
        self.assertEqual(view.camera.position,[5.,22.,-8.])
