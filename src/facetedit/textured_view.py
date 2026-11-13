"""Tk-facing model viewport; geometry and graphics remain on worker threads."""
import time
import tkinter as tk
from .chrome import rounded
from .frames import FrameStream
from .scene import View


class TexturedView:
    def set_resources(self,resources,backend='auto',animate=False):
        if backend not in ('auto','software'):raise ValueError('Unknown graphics backend')
        self._stop_geometry();self._stop_frames()
        self.resources=resources;self.renderer_backend=backend;self.animate_textures=bool(animate)
        self.scene=None;self.faces=[];self.picks.clear();self._geometry_key=None
        self.render_status='Preparing models' if resources is not None else 'Solid colors'
        self.schedule()

    def _view_snapshot(self,width,height):
        center=((width-self.stage_right)/2+35+self.pan_x,height*.52+self.pan_y)
        if self.mode=='fly':return View.flight(self.camera,width,height,((width-self.stage_right)/2+35,height*.5))
        return View.orbit(width,height,(self.center_x,self.height_origin,self.center_z),self.angle,self.elevation,self.scale,center)

    def _stop_frames(self):
        if self._frames is not None:self._frames.close()
        self._frames=None
        for timer in (self._frame_poll,self._animation_id):
            if timer is not None:self.after_cancel(timer)
        self._frame_poll=self._animation_id=None;self._requested_frame=self._frame_key=None
        self._display_frame=self._terrain_image=self._ready_frame=None;self._frame_error=None

    def _poll_frames(self):
        self._frame_poll=None
        if self._frames is None:return
        result=self._frames.poll()
        if result is not None:
            key,frame,error=result
            if error is not None:
                if key==self._requested_frame:
                    self._frame_key=key;self._frame_error=str(error);self.on_error(str(error));self.schedule()
            elif frame.scene is self.scene:
                try:
                    image=tk.PhotoImage(master=self,data=frame.data,format='png')
                    self._ready_frame=(frame,image.zoom(frame.zoom,frame.zoom) if frame.zoom>1 else image)
                    self._frame_key=key;self._frame_error=None
                    self.schedule()
                except tk.TclError as exc:
                    self._frame_key=key;self._frame_error=str(exc);self.on_error(str(exc));self.schedule()
        if self._requested_frame!=self._frame_key:self._frame_poll=self.after(20,self._poll_frames)

    def _draw_resources(self,width,height):
        if min(width,height)<2:return
        if self._ready_frame is not None:
            frame,image=self._ready_frame;self._ready_frame=None
            if frame.scene is self.scene:
                # Keep the old PhotoImage and picking snapshot alive until the
                # canvas redraw commits their replacements together.
                self._display_frame,self._terrain_image=frame,image
                self.render_status=f'{frame.backend} · {frame.elapsed_ms:.0f} ms'
        if self.scene is not None:
            view=self._view_snapshot(width,height)
            ticks=int(time.monotonic()*20) if self.animate_textures and self.scene.animated else 0
            key=(id(self.scene),view,ticks)
            if key!=self._requested_frame:
                if self._frames is None:self._frames=FrameStream(self.renderer_backend)
                self._requested_frame=key;self._frames.request(key,self.scene,view,ticks)
            if self._frame_poll is None and self._frame_key!=self._requested_frame:self._frame_poll=self.after(20,self._poll_frames)
            if self.animate_textures and self.scene.animated and self._animation_id is None:
                def advance():self._animation_id=None;self.schedule()
                self._animation_id=self.after(100,advance)
        frame=self._display_frame
        if frame is not None:
            view=frame.view
            if not view.perspective and self.grid:
                floor=self.height_origin-9;r=self.radius+8
                for offset in range(-r,r+1,4):
                    for a,b in (((self.center_x+offset,floor,self.center_z-r),(self.center_x+offset,floor,self.center_z+r)),((self.center_x-r,floor,self.center_z+offset),(self.center_x+r,floor,self.center_z+offset))):
                        segment=view.segment(a,b)
                        if segment:self.create_line(*segment,fill='#172b3c',width=1)
            self.create_image(*frame.offset,image=self._terrain_image,anchor='nw',tags=('textured-terrain',))
            self.face_count=len(frame.scene.surfaces)
            selection=self.document.selection
            for box in selection.boxes if selection else ():
                a,b=box.minimum,tuple(v+1 for v in box.maximum)
                corners=[(x,y,z) for x in (a[0],b[0]) for y in (a[1],b[1]) for z in (a[2],b[2])]
                for i,point in enumerate(corners):
                    for bit in (1,2,4):
                        j=i^bit
                        if j>i:
                            segment=view.segment(point,corners[j])
                            if segment:
                                self.create_line(*segment,fill='#325e79',width=4,tags=('model-selection',))
                                self.create_line(*segment,fill='#9af5f2',width=1.5,tags=('model-selection',))
            self._draw_preview(frame=view)
            if not frame.scene.surfaces:self.create_text(view.cx,height*.5,text='No blocks within the display radius',fill='#9cafcb')
        elif self.scene is not None:
            self.create_text((width-self.stage_right)/2+35,height*.5,text='Rendering models…',fill='#9cafcb')
        x,y=(width-self.stage_right)/2+35,height-112
        rounded(self,x-240,y-15,x+240,y+15,12,fill='#0c1728',outline='#1e3046')
        hint='W A S D  MOVE · Q / E  VERTICAL · DRAG TO LOOK' if self.mode=='fly' else 'DRAG TO ORBIT · SCROLL TO ZOOM · SHIFT-CLICK TO SELECT'
        self.create_text(x,y,text=hint,font=('Helvetica',8),fill='#9cafcb')
        self.create_text(110,116,anchor='w',text=self.render_status,font=('Helvetica',8),fill='#7d94ae')
        if self._frame_error:self.create_text(28,120,anchor='nw',text=self._frame_error,width=500,fill='#f0bf96')
