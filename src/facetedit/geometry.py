"""Cancellable bounded voxel geometry, with a latest-request background stream."""
from collections import OrderedDict
from dataclasses import dataclass
import threading,time
from .blocks import color,shade

FACE_DEFS=(
    ((0,1,0),((0,1,0),(1,1,0),(1,1,1),(0,1,1)),1.08),
    ((1,0,0),((1,0,0),(1,0,1),(1,1,1),(1,1,0)),.86),
    ((-1,0,0),((0,0,1),(0,0,0),(0,1,0),(0,1,1)),.82),
    ((0,0,1),((1,0,1),(0,0,1),(0,1,1),(1,1,1)),.94),
    ((0,0,-1),((0,0,0),(1,0,0),(1,1,0),(0,1,0)),.90),
    ((0,-1,0),((0,0,1),(1,0,1),(1,0,0),(0,0,0)),.65))


class Superseded(Exception):pass


def checkpoint(cancel):
    deadline=time.monotonic()+.002
    def check():
        nonlocal deadline
        if cancel is not None and cancel.is_set():raise Superseded()
        if getattr(cancel,'yield_ui',False) and time.monotonic()>=deadline:
            # Tk releases the GIL for Canvas calls. Briefly yield CPU-bound
            # Python meshing so those calls can regain it without repeated
            # interpreter time-slice stalls during a frame.
            time.sleep(.001);deadline=time.monotonic()+.002
    return check


def mesh(voxels,cancel=None):
    result=[];colors={};check=checkpoint(cancel)
    for index,(position,block) in enumerate(voxels.items()):
        if index%64==0:check()
        x,y,z=position
        for normal,offsets,light in FACE_DEFS:
            if (x+normal[0],y+normal[1],z+normal[2]) in voxels:continue
            key=(block,light)
            if key not in colors:colors[key]=shade(color(block),light)
            result.append((position,normal,tuple((x+ox,y+oy,z+oz) for ox,oy,oz in offsets),colors[key]))
    return result


@dataclass
class Geometry:
    faces:list
    height_origin:int


def build(document,mode,center,radius,ceiling,cancel):
    minimum,maximum=document.world.bounds(document.dimension);voxels={};height=0
    check=checkpoint(cancel)
    if mode=='fly':
        x,y,z=center;r=radius+3
        for bx in range(x-r,x+r+1):
            check()
            for bz in range(z-r,z+r+1):
                check()
                for by in range(max(minimum,y-r),min(maximum,y+r)+1):
                    block=document.get(bx,by,bz)
                    if not block.air:voxels[bx,by,bz]=block
    else:
        cx,cz=center;heights={};world=document.view_world
        edited={}
        for dim,x,y,z in document.edits:
            if dim==document.dimension:edited.setdefault((x//16,z//16),set()).add(y//16)
        for x in range(cx-radius,cx+radius):
            check()
            for z in range(cz-radius,cz+radius):
                check()
                sections=world.stored_sections(x//16,z//16,document.dimension)
                if sections is None:ranges=((min(maximum,ceiling),minimum),)
                else:ranges=((min(maximum,ceiling,sy*16+15),max(minimum,sy*16)) for sy in sorted(set(sections)|edited.get((x//16,z//16),set()),reverse=True))
                found=False
                for high,low in ranges:
                    for y in range(high,low-1,-1):
                        if not document.get(x,y,z).air:heights[x,z]=y;found=True;break
                    if found:break
        if heights:
            floor=max(minimum,min(heights.values())-3)
            for index,((x,z),top) in enumerate(heights.items()):
                if index%32==0:check()
                for y in range(max(floor,top-24),top+1):
                    block=document.get(x,y,z)
                    if not block.air:voxels[x,y,z]=block
            height=sorted(heights.values())[len(heights)//2]-2
    check();return Geometry(mesh(voxels,cancel),height)


class GeometryStream:
    """At most one running build and one replaceable pending request."""
    def __init__(self):
        self._condition=threading.Condition();self._pending=None;self._active=None;self._cancel=None;self._closed=False
        self._result=None;self._cache=OrderedDict();self._thread=None
        self.builds=self.cache_hits=self.cancelled=0

    def request(self,key,work):
        with self._condition:
            if self._closed:return
            if key in self._cache:
                self.cache_hits+=1;self._cache.move_to_end(key);self._result=(key,self._cache[key],None)
                self._pending=None
                if self._cancel:self._cancel.set()
                return
            if (self._pending and self._pending[0]==key) or (self._active==key and not self._cancel.is_set()):return
            if self._cancel:self._cancel.set()
            self._pending=(key,work)
            if self._thread is None:
                self._thread=threading.Thread(target=self._run,daemon=True,name='FacetEdit terrain');self._thread.start()
            self._condition.notify()

    def _run(self):
        while True:
            with self._condition:
                self._condition.wait_for(lambda:self._pending is not None or self._closed)
                if self._closed:return
                key,work=self._pending;self._pending=None;cancel=self._cancel=threading.Event();self._active=key
                cancel.yield_ui=True
            value,error=None,None
            try:value=work(cancel)
            except Superseded:pass
            except Exception as exc:error=exc
            with self._condition:
                if self._closed:return
                if cancel.is_set():self.cancelled+=1
                else:
                    self.builds+=1;self._result=(key,value,error)
                    if error is None:
                        self._cache[key]=value
                        while len(self._cache)>2:self._cache.popitem(last=False)
                self._active=None;self._cancel=None

    def poll(self):
        with self._condition:
            result=self._result;self._result=None
            return result

    def close(self):
        with self._condition:
            self._closed=True;self._pending=None;self._cache.clear();self._result=None
            if self._cancel:self._cancel.set()
            self._condition.notify()
