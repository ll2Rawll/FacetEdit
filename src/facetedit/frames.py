"""One graphics owner thread, one replaceable pending frame, no Tk worker calls."""
from dataclasses import dataclass,replace
import math,threading,time
from . import png
from .geometry import Superseded
from .graphics import OpenGL,GraphicsUnavailable
from .software import Software


@dataclass(frozen=True)
class Frame:
    scene:object
    view:object
    ticks:float
    data:bytes
    zoom:int
    backend:str
    elapsed_ms:float
    fallback_reason:str=''
    offset:tuple=(0,0)


class FrameStream:
    def __init__(self,backend='auto',factory=None):
        if backend not in ('auto','software'):raise ValueError('Unknown graphics backend')
        self.backend=backend;self.factory=factory
        self._condition=threading.Condition();self._pending=None;self._active=None;self._active_scene=None;self._cancel=None;self._closed=False;self._result=None;self._thread=None
        self.frames=self.cancelled=0

    def request(self,key,scene,view,ticks=0):
        with self._condition:
            if self._closed:return
            if self._pending is not None and self._pending[0]==key:return
            if self._active==key and not self._cancel.is_set():return
            # Keep a completed frame available while a new view is requested.
            # Cancellation is cooperative; graphics calls never run on Tk.
            if self._cancel and scene is not self._active_scene:self._cancel.set()
            self._pending=(key,scene,view,ticks)
            if self._thread is None:
                self._thread=threading.Thread(target=self._run,daemon=True,name='FacetEdit graphics');self._thread.start()
            self._condition.notify()

    @staticmethod
    def _size(renderer,view):
        budget=getattr(renderer,'pixel_budget',2_000_000)
        zoom=max(1,math.ceil(math.sqrt(view.width*view.height/budget)))
        # Tiny rounding differences are below one source pixel. The output is
        # cropped at the canvas boundary after integer nearest-neighbor zoom.
        return zoom,replace(view,width=math.ceil(view.width/zoom),height=math.ceil(view.height/zoom),cx=view.cx/zoom,cy=view.cy/zoom,scale=view.scale/zoom)

    @staticmethod
    def _crop(scene,view):
        if not scene.surfaces:return (0,0),replace(view,width=1,height=1)
        lo,hi=scene.bounds;corners=[(x,y,z) for x in (lo[0],hi[0]) for y in (lo[1],hi[1]) for z in (lo[2],hi[2])]
        # A bounding box crossing the near plane may project unboundedly; the
        # full viewport is the correct conservative target in that case.
        if view.perspective and any(view.coordinates(p)[2]<=view.near for p in corners):return (0,0),view
        points=[view.project(p) for p in corners]
        x=max(0,min(view.width-1,math.floor(min(p[0] for p in points))-2));y=max(0,min(view.height-1,math.floor(min(p[1] for p in points))-2))
        right=max(x+1,min(view.width,math.ceil(max(p[0] for p in points))+2));bottom=max(y+1,min(view.height,math.ceil(max(p[1] for p in points))+2))
        return (x,y),replace(view,width=right-x,height=bottom-y,cx=view.cx-x,cy=view.cy-y)

    def _run(self):
        renderer=None;reason=''
        try:
            while True:
                with self._condition:
                    self._condition.wait_for(lambda:self._closed or self._pending is not None)
                    if self._closed:return
                    key,scene,view,ticks=self._pending;self._pending=None;self._active=key;self._active_scene=scene
                    cancel=self._cancel=threading.Event();cancel.yield_ui=True
                value=error=None
                try:
                    started=time.perf_counter()
                    if renderer is None:
                        if self.factory is not None:renderer=self.factory()
                        elif self.backend=='software':renderer=Software()
                        else:
                            try:renderer=OpenGL()
                            except (GraphicsUnavailable,OSError,AttributeError) as exc:reason=str(exc);renderer=Software()
                    zoom,target=self._size(renderer,view);offset,target=self._crop(scene,target)
                    try:result=renderer.render(scene,target,ticks,cancel)
                    except GraphicsUnavailable as exc:
                        reason=str(exc);renderer.close();renderer=Software();zoom,target=self._size(renderer,view);offset,target=self._crop(scene,target);result=renderer.render(scene,target,ticks,cancel)
                    if cancel.is_set():raise Superseded()
                    data=png.encode(result)
                    value=Frame(scene,view,ticks,data,zoom,renderer.name,(time.perf_counter()-started)*1000,reason,tuple(n*zoom for n in offset))
                except Superseded:pass
                except Exception as exc:error=exc
                with self._condition:
                    if self._closed:return
                    if cancel.is_set():self.cancelled+=1
                    else:self.frames+=1;self._result=(key,value,error)
                    self._active=None;self._active_scene=None;self._cancel=None
        finally:
            if renderer is not None:renderer.close()

    def poll(self):
        with self._condition:result=self._result;self._result=None;return result

    def close(self):
        with self._condition:
            self._closed=True;self._pending=None;self._result=None
            if self._cancel:self._cancel.set()
            self._condition.notify()

    def join(self,timeout=None):
        if self._thread is not None:self._thread.join(timeout)
