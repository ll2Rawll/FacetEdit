"""Original, event-driven orthographic voxel renderer using only Tk Canvas."""

import math
import time
import tkinter as tk

from .blocks import color, shade
from .chrome import rounded

SKY = "#080f1d"


class VoxelView(tk.Canvas):
    def __init__(self, parent, document, on_pick, on_error, **kwargs):
        super().__init__(parent, background=SKY, highlightthickness=0, **kwargs)
        self.document = document
        self.on_pick, self.on_error = on_pick, on_error
        self.radius = 12
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
        self.ceiling = document.world.maximum_y
        self.faces = []
        self.picks = {}
        self._geometry_key = None
        self._pending = None
        self._drag = None
        self.last_ms = 0
        self.face_count = 0
        self.height_origin = 0
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

    def attach(self, document):
        self.document = document
        self.center_x, _, self.center_z = document.world.spawn
        self.ceiling = document.world.maximum_y
        self.pan_x = self.pan_y = 0
        self._geometry_key = None
        self.schedule()

    def schedule(self):
        if self._pending is None and self.winfo_exists():
            self._pending = self.after(20, self.draw)

    def zoom(self, factor):
        self.auto_fit = False
        self.scale = min(52, max(6, self.scale * factor))
        self.schedule()

    def reset(self):
        self.auto_fit = True
        self.angle, self.elevation, self.scale = math.pi / 4, .65, 19
        self.pan_x = self.pan_y = 0
        self.schedule()

    def _press(self, event):
        self.focus_set()
        self._drag = (event.x, event.y, self.angle, self.elevation, self.pan_x, self.pan_y)
        self._moved = False

    def _motion(self, event):
        if self._drag:
            x, y, angle, elevation, _, _ = self._drag
            if abs(event.x - x) + abs(event.y - y) > 5:
                self._moved = True
                self.angle = angle + (event.x - x) * .008
                self.elevation = min(1.2, max(.25, elevation + (event.y - y) * .004))
                self.schedule()

    def _pan(self, event):
        if self._drag:
            x, y, _, _, px, py = self._drag
            self.pan_x, self.pan_y = px + event.x - x, py + event.y - y
            self._moved = True
            self.schedule()

    def _end_pan(self, event):
        self._drag = None

    def _release(self, event):
        if self._drag and not self._moved:
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
        doc = self.document
        key = (id(doc), doc.revision, doc.dimension, self.center_x, self.center_z, self.radius, self.ceiling)
        if key == self._geometry_key:
            return
        voxels = {}
        heights = {}
        world = doc.world
        cx, cz, radius = self.center_x, self.center_z, self.radius
        for x in range(cx - radius, cx + radius):
            for z in range(cz - radius, cz + radius):
                for y in range(min(world.maximum_y, self.ceiling), world.minimum_y - 1, -1):
                    if not doc.get(x, y, z).air:
                        heights[(x, z)] = y
                        break
        if not heights:
            self.faces = []
            self.height_origin = 0
            self._geometry_key = key
            return
        floor = max(world.minimum_y, min(heights.values()) - 3)
        # A bounded cutaway keeps Canvas work predictable even on tall terrain.
        for (x, z), top in heights.items():
            for y in range(max(floor, top - 24), top + 1):
                block = doc.get(x, y, z)
                if not block.air:
                    voxels[(x, y, z)] = block
        self.height_origin = sorted(heights.values())[len(heights) // 2] - 2
        face_defs = (
            ((0, 1, 0), ((0, 1, 0), (1, 1, 0), (1, 1, 1), (0, 1, 1)), 1.08),
            ((1, 0, 0), ((1, 0, 0), (1, 0, 1), (1, 1, 1), (1, 1, 0)), .86),
            ((-1, 0, 0), ((0, 0, 1), (0, 0, 0), (0, 1, 0), (0, 1, 1)), .82),
            ((0, 0, 1), ((1, 0, 1), (0, 0, 1), (0, 1, 1), (1, 1, 1)), .94),
            ((0, 0, -1), ((0, 0, 0), (1, 0, 0), (1, 1, 0), (0, 1, 0)), .90),
        )
        faces = []
        colors = {}
        for position, block in voxels.items():
            x, y, z = position
            for normal, offsets, light in face_defs:
                neighbor = (x + normal[0], y + normal[1], z + normal[2])
                if neighbor in voxels:
                    continue
                if (block,light) not in colors:
                    colors[(block,light)] = shade(color(block),light)
                tint = colors[(block,light)]
                faces.append((position, normal, tuple((x + ox, y + oy, z + oz) for ox, oy, oz in offsets), tint))
        self.faces, self._geometry_key = faces, key

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
            selected = lo is not None and all(lo[i] <= pos[i] <= hi[i] for i in range(3))
            if tint not in outlines:
                outlines[tint] = shade(tint,.95) if self.grid else tint
            outline = "#86eff2" if selected else outlines[tint]
            item = self.create_polygon(points, fill=tint, outline=outline, width=1.5 if selected else .5)
            self.picks[item] = pos
        self.face_count = len(self.picks)
        if selection:
            a, b = selection.minimum, tuple(v + 1 for v in selection.maximum)
            corners = [(x, y, z) for x in (a[0], b[0]) for y in (a[1], b[1]) for z in (a[2], b[2])]
            for i, point in enumerate(corners):
                for bit in (1, 2, 4):
                    j = i ^ bit
                    if j > i:
                        self.create_line(*project(*point), *project(*corners[j]), fill="#325e79", width=4)
                        self.create_line(*project(*point), *project(*corners[j]), fill="#9af5f2", width=1.5)
        if not visible:
            self.create_text(width / 2, height / 2, text="No blocks in this view\nUse Go to coordinates to find generated terrain.", font=("Helvetica", 12), fill="#68768d", justify="center")
        hint_x,hint_y = (width-self.stage_right)/2+35,height-112
        rounded(self,hint_x-220,hint_y-12,hint_x+220,hint_y+12,12,fill="#0c1728",outline="#1e3046")
        self.create_text(hint_x,hint_y,anchor="center",text="DRAG TO ORBIT   ·   SCROLL TO ZOOM   ·   SHIFT-CLICK TO SELECT",font=("Helvetica",8),fill="#9cafcb")
        self.last_ms = (time.perf_counter() - start) * 1000

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
        if self._pending is not None:
            self.after_cancel(self._pending)
        super().destroy()
