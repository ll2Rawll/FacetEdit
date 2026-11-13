"""Original orthographic and perspective voxel renderer using only Tk Canvas."""

import math
import time
import tkinter as tk

from .blocks import color, shade
from .chrome import rounded
from .camera import Camera
from .textured_view import TexturedView

SKY = "#080f1d"


class VoxelView(TexturedView,tk.Canvas):
    def __init__(self, parent, document, on_pick, on_error, **kwargs):
        super().__init__(parent, background=SKY, highlightthickness=0, **kwargs)
        self.document = document
        self.on_pick, self.on_error = on_pick, on_error
        self.radius = 12
        self.mode = 'orbit'
        self.camera = Camera()
        self._keys = set()
        self._key_releases = {}
        self._flight_id = None
        self._last_move = 0
        self.grid = True
        self.glass = True
        self.stage_right = 330
        self._background_source = None
        self._background_image = None
        self._background_zoom = None
        self.center_x = self.center_z = 0
        self.angle = math.pi / 4
        self.elevation = .65
        self.scale = 19.0
        self.auto_fit = True
        self.pan_x = self.pan_y = 0
        self.ceiling = document.world.bounds(document.dimension)[1]
        self.faces = []
        self.preview = None
        self.picks = {}
        self._geometry_key = None
        self._geometry_error = None
        self._requested_geometry = None
        self._geometry_stream = None
        self._geometry_poll = None
        self._display_scope = None
        self._pending = None
        self._drag = None
        self.last_ms = 0
        self.face_count = 0
        self.height_origin = 0
        self.resources=None
        self.scene=None
        self.renderer_backend='auto'
        self.animate_textures=False
        self._frames=None
        self._frame_poll=None
        self._animation_id=None
        self._requested_frame=None
        self._frame_key=None
        self._display_frame=None
        self._ready_frame=None
        self._terrain_image=None
        self.render_status='Solid colors'
        self._frame_error=None
        self.bind("<Configure>", lambda _: self.schedule())
        self.bind("<ButtonPress-1>", self._press)
        self.bind("<B1-Motion>", self._motion)
        self.bind("<ButtonRelease-1>", self._release)
        self.bind("<ButtonPress-3>", self._press)
        self.bind("<B3-Motion>", self._pan)
        self.bind("<ButtonRelease-3>", self._end_pan)
        self.bind("<MouseWheel>", lambda e: self.zoom(1.1 if e.delta > 0 else 1 / 1.1))
        self.bind("<Button-4>", lambda _: self.zoom(1.1))
        self.bind("<Button-5>", lambda _: self.zoom(1 / 1.1))
        self.bind('<KeyPress>',self._key_press)
        self.bind('<KeyRelease>',self._key_release)
        self.bind('<FocusOut>',lambda _:self.stop_flight())
        self.bind('<Escape>',lambda _:self.stop_flight())

    def attach(self, document):
        self.stop_flight()
        self._stop_geometry()
        self._stop_frames()
        self.scene=None
        self.faces=[];self.picks.clear()
        self.preview=None
        self.document = document
        self.center_x, _, self.center_z = document.world.spawn
        self.height_origin=document.world.spawn[1]-2
        self.ceiling = document.world.bounds(document.dimension)[1]
        self.pan_x = self.pan_y = 0
        self._geometry_key = None
        if self.mode=='fly':
            x,y,z=document.world.spawn
            self.camera.position=[float(x),float(y)+8,float(z)+8]
        self.schedule()

    def schedule(self):
        if self._pending is None and self.winfo_exists():
            self._pending = self.after(20, self.draw)

    def zoom(self, factor):
        if self.mode=='fly':
            self.camera.speed=min(64,max(1,self.camera.speed*factor))
            self.schedule()
            return
        self.auto_fit = False
        self.scale = min(52, max(6, self.scale * factor))
        self.schedule()

    def reset(self):
        self.stop_flight()
        if self.mode=='fly':
            self.camera.yaw,self.camera.pitch,self.camera.speed=0.,-.3,8.
            self.schedule()
            return
        self.auto_fit = True
        self.angle, self.elevation, self.scale = math.pi / 4, .65, 19
        self.pan_x = self.pan_y = 0
        self.schedule()

    def set_mode(self,mode):
        if mode not in ('orbit','fly'):raise ValueError('Unknown camera mode')
        if mode==self.mode:return
        self.stop_flight()
        if mode=='fly':
            self._geometry()
            distance=self.radius*.65
            self.camera.position=[self.center_x+math.sin(self.angle)*distance,
                                  self.height_origin+distance+6,self.center_z+math.cos(self.angle)*distance]
            self.camera.yaw=-self.angle
            self.camera.pitch=-.6
        else:
            self.center_x,self.center_z=math.floor(self.camera.position[0]),math.floor(self.camera.position[2])
            self.pan_x=self.pan_y=0
        self.mode=mode
        self._geometry_key=None
        self.schedule()

    def go_to(self,x,y,z):
        self.stop_flight()
        self.center_x,self.center_z=x,z
        if self.mode=='fly':self.camera.position=[float(x),float(y),float(z)]
        else:self.ceiling=y
        self.pan_x=self.pan_y=0
        self.schedule()

    def _key_press(self,event):
        key=event.keysym.lower()
        if self.mode!='fly' or key not in ('w','a','s','d','q','e','space','shift_l','shift_r') or event.state&12:return
        if key in self._key_releases:self.after_cancel(self._key_releases.pop(key))
        self._keys.add(key)
        if self._flight_id is None:
            self._last_move=time.monotonic()
            self._flight_id=self.after(16,self._flight_tick)
        return 'break'

    def _key_release(self,event):
        key=event.keysym.lower()
        if key in self._keys:
            if key in self._key_releases:self.after_cancel(self._key_releases.pop(key))
            def release():
                self._keys.discard(key);self._key_releases.pop(key,None)
                if not self._keys:self.stop_flight()
            # X11 autorepeat emits release/press pairs. Wait for the paired press.
            self._key_releases[key]=self.after_idle(release)
            return 'break'

    def stop_flight(self):
        self._keys.clear()
        if self._flight_id is not None:self.after_cancel(self._flight_id)
        self._flight_id=None
        for pending in self._key_releases.values():self.after_cancel(pending)
        self._key_releases.clear()

    def _flight_tick(self):
        self._flight_id=None
        if self.mode!='fly' or self.focus_get() is not self or not self._keys:
            self.stop_flight();return
        now=time.monotonic();elapsed=now-self._last_move;self._last_move=now
        keys=self._keys
        changed=self.camera.move(int('w' in keys)-int('s' in keys),int('d' in keys)-int('a' in keys),
                                 int(bool(keys&{'e','space'}))-int('q' in keys),elapsed,
                                 bool(keys&{'shift_l','shift_r'}),self.document.world.bounds(self.document.dimension))
        if changed:
            self.center_x,self.center_z=math.floor(self.camera.position[0]),math.floor(self.camera.position[2])
            self.schedule()
        self._flight_id=self.after(16,self._flight_tick)

    def _press(self, event):
        self.focus_set()
        self._drag = (event.x, event.y, self.camera.yaw if self.mode=='fly' else self.angle,
                      self.camera.pitch if self.mode=='fly' else self.elevation,self.pan_x,self.pan_y)
        self._moved = False

    def _motion(self, event):
        if self._drag:
            x, y, angle, elevation, _, _ = self._drag
            if abs(event.x - x) + abs(event.y - y) > 5:
                self._moved = True
                if self.mode=='fly':
                    self.camera.yaw,self.camera.pitch=angle,elevation
                    self.camera.look(event.x-x,event.y-y)
                else:
                    self.angle = angle + (event.x - x) * .008
                    self.elevation = min(1.2, max(.25, elevation + (event.y - y) * .004))
                self.schedule()

    def _pan(self, event):
        if self.mode=='fly':
            self._motion(event)
            return
        if self._drag:
            x, y, _, _, px, py = self._drag
            self.pan_x, self.pan_y = px + event.x - x, py + event.y - y
            self._moved = True
            self.schedule()

    def _end_pan(self, event):
        self._drag = None

    def _release(self, event):
        if self._drag and not self._moved:
            if self.resources is not None and self._display_frame is not None:
                frame=self._display_frame
                position=frame.scene.pick(*frame.view.ray(event.x,event.y),ticks=frame.ticks)
                if position is not None:self.on_pick(position,bool(event.state&1))
                self._drag=None
                return
            items = self.find_overlapping(event.x - 1, event.y - 1, event.x + 1, event.y + 1)
            for item in reversed(items):
                if item in self.picks:
                    self.on_pick(self.picks[item], bool(event.state & 1))
                    break
        self._drag = None

    def project(self, x, y, z):
        return self._projector()(x,y,z)

    def _projector(self):
        # Snapshot Tk geometry and trigonometry once per frame, not per vertex.
        cx,cz = self.center_x,self.center_z
        px = (self.winfo_width()-self.stage_right)/2+35+self.pan_x
        py = self.winfo_height()*.52+self.pan_y
        origin,scale = self.height_origin,self.scale
        c,s = math.cos(self.angle),math.sin(self.angle)
        se,ce = math.sin(self.elevation),math.cos(self.elevation)
        def project(x,y,z):
            dx,dz = x-cx,z-cz
            return px+(dx*c-dz*s)*scale,py+((dx*s+dz*c)*se-(y-origin)*ce)*scale
        return project

    def _geometry(self):
        from .geometry import build,GeometryStream
        import threading
        doc=self.document
        center=tuple(math.floor(v/4)*4 for v in self.camera.position) if self.mode=='fly' else (self.center_x,self.center_z)
        key=(self.mode,id(doc),doc.revision,doc.dimension,center,self.radius,self.ceiling,id(self.resources))
        if key==self._geometry_key:
            if self._geometry_error:raise ValueError(self._geometry_error)
            return
        if doc.world.path is None and self.resources is None:
            value=build(doc,self.mode,center,self.radius,self.ceiling,threading.Event())
            self.faces,self.height_origin=value.faces,value.height_origin
            self._geometry_key=key;self._geometry_error=None
            return
        if key!=self._requested_geometry:
            if self._display_scope!=(id(doc),doc.dimension):
                self.faces=[];self.picks.clear();self.scene=None;self._stop_frames()
            self._display_scope=(id(doc),doc.dimension)
            if self._geometry_stream is None:self._geometry_stream=GeometryStream()
            snapshot=doc.snapshot();mode,radius,ceiling,resources=self.mode,self.radius,self.ceiling,self.resources
            self._requested_geometry=key;self._geometry_error=None
            self._geometry_stream.request(key,lambda cancel:build(snapshot,mode,center,radius,ceiling,cancel,resources))
        if self._geometry_poll is None:self._geometry_poll=self.after(25,self._poll_geometry)

    def _poll_geometry(self):
        self._geometry_poll=None
        if self._geometry_stream is None:return
        result=self._geometry_stream.poll()
        if result is not None:
            key,value,error=result
            if key==self._requested_geometry:
                self._geometry_key=key
                if error is None:self.faces,self.height_origin,self.scene=value.faces,value.height_origin,value.scene
                else:self.faces=[];self.scene=None;self._stop_frames();self._geometry_error=str(error)
                self.schedule()
        if self._geometry_key!=self._requested_geometry:self._geometry_poll=self.after(25,self._poll_geometry)

    def _mesh(self,voxels):
        from .geometry import mesh
        self.faces=mesh(voxels)

    def _stop_geometry(self):
        if self._geometry_stream is not None:self._geometry_stream.close()
        self._geometry_stream=None
        if self._geometry_poll is not None:self.after_cancel(self._geometry_poll)
        self._geometry_poll=None;self._requested_geometry=None;self._geometry_error=None

    def draw(self):
        if self._pending is not None:
            self.after_cancel(self._pending)
        self._pending = None
        start = time.perf_counter()
        if self.auto_fit and self.winfo_width() > 1:
            self.scale = max(6, min(19, (self.winfo_width() - self.stage_right - 130) / (self.radius * 2 * 1.42), (self.winfo_height() - 210) / (self.radius * 1.2 + 10)))
        try:
            self._geometry()
        except Exception as exc:
            self.delete("all")
            self.create_text(self.winfo_width() / 2, self.winfo_height() / 2, text="This area could not be displayed.\n" + str(exc), width=450, fill="#5f6b80", justify="center")
            self.on_error(str(exc))
            return
        self.delete("all")
        self.picks.clear()
        width, height = self.winfo_width(), self.winfo_height()
        project = self._projector()
        self._draw_background(width,height)
        if self._requested_geometry is not None and self._requested_geometry!=self._geometry_key:
            self.create_text(28,100,text='Loading terrain…',anchor='nw',fill='#9cafcb',font=('Helvetica',10))
        if self.resources is not None:
            self._draw_resources(width,height)
            self.last_ms=(time.perf_counter()-start)*1000
            return
        if self.mode=='fly':
            self._draw_flight(width,height)
            self.last_ms=(time.perf_counter()-start)*1000
            return
        # Fine construction grid on the plane below the bounded terrain.
        floor = self.height_origin-9
        radius = self.radius+8
        for offset in range(-radius,radius+1,4):
            self.create_line(*project(self.center_x+offset,floor,self.center_z-radius),*project(self.center_x+offset,floor,self.center_z+radius),fill="#172b3c",width=1)
            self.create_line(*project(self.center_x-radius,floor,self.center_z+offset),*project(self.center_x+radius,floor,self.center_z+offset),fill="#172b3c",width=1)
        c, s = math.cos(self.angle), math.sin(self.angle)
        se, ce = math.sin(self.elevation), math.cos(self.elevation)
        camera = (s * ce, se, c * ce)
        visible = [face for face in self.faces if sum(a * b for a, b in zip(face[1], camera)) > 0]
        visible.sort(key=lambda f: sum((f[0][i] + .5 + f[1][i] * .5) * camera[i] for i in range(3)))
        selection = self.document.selection
        lo, hi = (selection.minimum, selection.maximum) if selection else (None, None)
        projected,outlines = {},{}
        for pos, normal, vertices, tint in visible:
            points = []
            for vertex in vertices:
                if vertex not in projected:
                    projected[vertex] = project(*vertex)
                points.extend(projected[vertex])
            if max(points[0::2]) < -40 or min(points[0::2]) > width + 40 or max(points[1::2]) < -40 or min(points[1::2]) > height + 40:
                continue
            selected = lo is not None and all(lo[i] <= pos[i] <= hi[i] for i in range(3)) and selection.contains(pos)
            if tint not in outlines:
                outlines[tint] = shade(tint,.95) if self.grid else tint
            outline = "#86eff2" if selected else outlines[tint]
            item = self.create_polygon(points, fill=tint, outline=outline, width=1.5 if selected else .5)
            self.picks[item] = pos
        self.face_count = len(self.picks)
        for box in selection.boxes if selection else ():
            a, b = box.minimum, tuple(v + 1 for v in box.maximum)
            corners = [(x, y, z) for x in (a[0], b[0]) for y in (a[1], b[1]) for z in (a[2], b[2])]
            for i, point in enumerate(corners):
                for bit in (1, 2, 4):
                    j = i ^ bit
                    if j > i:
                        self.create_line(*project(*point), *project(*corners[j]), fill="#325e79", width=4)
                        self.create_line(*project(*point), *project(*corners[j]), fill="#9af5f2", width=1.5)
        if not visible:
            self.create_text(width / 2, height / 2, text="No blocks in this view\nUse Go to coordinates to find generated terrain.", font=("Helvetica", 12), fill="#68768d", justify="center")
        self._draw_preview(project)
        hint_x,hint_y = (width-self.stage_right)/2+35,height-112
        rounded(self,hint_x-220,hint_y-12,hint_x+220,hint_y+12,12,fill="#0c1728",outline="#1e3046")
        self.create_text(hint_x,hint_y,anchor="center",text="DRAG TO ORBIT   ·   SCROLL TO ZOOM   ·   SHIFT-CLICK TO SELECT",font=("Helvetica",8),fill="#9cafcb")
        self.last_ms = (time.perf_counter() - start) * 1000

    def _draw_flight(self,width,height):
        frame=self.camera.frame(width,height,((width-self.stage_right)/2+35,height*.5))
        selection=self.document.selection
        visible=[face for face in self.faces if frame.visible(face[0],face[1])]
        visible.sort(key=lambda face:frame.depth(face[0],face[1]),reverse=True)
        outlines={}
        for position,normal,vertices,tint in visible:
            points=frame.polygon(vertices)
            if len(points)<6:continue
            selected=selection and selection.contains(position)
            if tint not in outlines:outlines[tint]=shade(tint,.95) if self.grid else tint
            item=self.create_polygon(points,fill=tint,outline='#86eff2' if selected else outlines[tint],width=1.5 if selected else .5)
            self.picks[item]=position
        self.face_count=len(self.picks)
        for box in selection.boxes if selection else ():
            a,b=box.minimum,tuple(v+1 for v in box.maximum)
            corners=[(x,y,z) for x in (a[0],b[0]) for y in (a[1],b[1]) for z in (a[2],b[2])]
            for i,point in enumerate(corners):
                for bit in (1,2,4):
                    j=i^bit
                    if j>i:
                        segment=frame.segment(point,corners[j])
                        if segment:
                            self.create_line(*segment,fill='#325e79',width=4)
                            self.create_line(*segment,fill='#9af5f2',width=1.5)
        x,y=frame.cx,height-128
        rounded(self,x-250,y-21,x+250,y+22,12,fill='#0c1728',outline='#284259')
        self.create_text(x,y-8,text='W A S D  MOVE   ·   Q / E  DOWN / UP   ·   SHIFT  FASTER',font=('Helvetica',8),fill='#b9cede')
        self.create_text(x,y+9,text=f'DRAG TO LOOK  ·  SCROLL SPEED  {self.camera.speed:.0f}  ·  '+', '.join(f'{v:.1f}' for v in self.camera.position),font=('Helvetica',8),fill='#83e1e8')
        if not self.picks:
            self.create_text(frame.cx,height*.5,text='No blocks within the display radius\nFly toward terrain or use Go to coordinates.',font=('Helvetica',11),fill='#8296b0',justify='center')
        self._draw_preview(frame=frame)

    def _draw_preview(self,project=None,frame=None):
        if self.preview is None:return
        clip,origin=self.preview
        def box(a,b,color,width):
            corners=[(x,y,z) for x in (a[0],b[0]) for y in (a[1],b[1]) for z in (a[2],b[2])]
            for i,point in enumerate(corners):
                for bit in (1,2,4):
                    j=i^bit
                    if j<=i:continue
                    segment=frame.segment(point,corners[j]) if frame else (*project(*point),*project(*corners[j]))
                    if segment:self.create_line(*segment,fill=color,width=width,tags=('paste-preview',))
        box(origin,tuple(origin[i]+clip.size[i] for i in range(3)),'#d0b1ff',2)
        stride=max(1,math.ceil(len(clip.blocks)/256))
        for index,(pos,block) in enumerate(clip.blocks.items()):
            if index%stride or block.air:continue
            target=tuple(pos[i]+origin[i] for i in range(3))
            box(target,tuple(v+1 for v in target),'#8f83b7',.5)

    def _draw_background(self,width,height):
        if not self.glass:
            self.create_rectangle(0,0,width,height,fill=SKY,outline="")
            return
        if self._background_source is None:
            w,h = 320,180
            data = bytearray()
            for y in range(h):
                for x in range(w):
                    u,v = x/w,y/h
                    cyan = math.exp(-(((u-.28)/.34)**2+((v-.47)/.5)**2)*2)
                    violet = math.exp(-(((u-.77)/.36)**2+((v-.35)/.6)**2)*2)
                    data.extend((round(8+4*cyan+12*violet),round(15+15*cyan+4*violet),round(29+17*cyan+18*violet)))
            self._background_source = tk.PhotoImage(master=self,data=f"P6\n{w} {h}\n255\n".encode()+bytes(data),format="PPM")
        zoom = (max(1,math.ceil(width/320)),max(1,math.ceil(height/180)))
        if self._background_zoom != zoom:
            self._background_image = self._background_source.zoom(*zoom)
            self._background_zoom = zoom
        self.create_image(0,0,image=self._background_image,anchor="nw")

    def destroy(self):
        self.stop_flight()
        self._stop_geometry()
        self._stop_frames()
        if self._pending is not None:
            self.after_cancel(self._pending)
        super().destroy()
