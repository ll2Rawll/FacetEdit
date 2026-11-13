"""Textured scene assembly, projection snapshots and model-surface picking."""
from dataclasses import dataclass
import math
from .camera import dot
from .geometry import checkpoint
from .resources import Model,Face,NORMALS


def cross(a,b):return a[1]*b[2]-a[2]*b[1],a[2]*b[0]-a[0]*b[2],a[0]*b[1]-a[1]*b[0]
def subtract(a,b):return tuple(x-y for x,y in zip(a,b))


@dataclass(frozen=True)
class Surface:
    position:tuple
    vertices:tuple
    normal:tuple
    uv:tuple
    texture:object
    color:tuple=(1.,1.,1.,1.)

    @property
    def blended(self):return self.color[3]<1 or self.texture.translucent


class Scene:
    def __init__(self,surfaces,cancel=None):
        self.surfaces=tuple(surfaces);self.cells={};self.animated=any(len(s.texture.frames)>1 for s in self.surfaces)
        if not self.surfaces:self.bounds=((0,0,0),(0,0,0));return
        lo=[float('inf')]*3;hi=[-float('inf')]*3
        references=0;check=checkpoint(cancel)
        for index,surface in enumerate(self.surfaces):
            if index%64==0:check()
            minimum=tuple(min(v[i] for v in surface.vertices) for i in range(3));maximum=tuple(max(v[i] for v in surface.vertices) for i in range(3))
            for i in range(3):lo[i]=min(lo[i],minimum[i]);hi[i]=max(hi[i],maximum[i])
            # Models may extend outside their owning voxel. Index every
            # intersecting cell so picking still reaches overhanging geometry.
            for x in range(math.floor(minimum[0]-1e-7),math.floor(maximum[0]+1e-7)+1):
                for y in range(math.floor(minimum[1]-1e-7),math.floor(maximum[1]+1e-7)+1):
                    for z in range(math.floor(minimum[2]-1e-7),math.floor(maximum[2]+1e-7)+1):
                        references+=1
                        if references>2_000_000:raise ValueError('Model picking budget exceeded; reduce the view radius or simplify the resource pack')
                        self.cells.setdefault((x,y,z),[]).append(index)
        self.bounds=tuple(lo),tuple(hi)

    def pick(self,origin,direction,ticks=0,maximum=10000):
        length=math.sqrt(dot(direction,direction))
        if not length or not self.surfaces:return None
        direction=tuple(v/length for v in direction);enter,leave=0.,float(maximum)
        for i in range(3):
            low,high=self.bounds[0][i],self.bounds[1][i]
            if abs(direction[i])<1e-12:
                if not low<=origin[i]<=high:return None
            else:
                a,b=(low-origin[i])/direction[i],(high-origin[i])/direction[i]
                enter=max(enter,min(a,b));leave=min(leave,max(a,b))
        if leave<enter:return None
        start=tuple(origin[i]+direction[i]*(enter+1e-7) for i in range(3));cell=[math.floor(v) for v in start]
        steps=[1 if v>0 else -1 for v in direction];delta=[abs(1/v) if v else float('inf') for v in direction]
        next_cross=[((cell[i]+1 if steps[i]>0 else cell[i])-origin[i])/direction[i] if direction[i] else float('inf') for i in range(3)]
        checked=set();best=leave+1.;position=None
        for _ in range(30000):
            for index in self.cells.get(tuple(cell),()):
                if index in checked:continue
                checked.add(index);surface=self.surfaces[index]
                if dot(direction,surface.normal)>=-1e-9:continue
                for triangle in ((0,1,2),(0,2,3)):
                    a,b,c=(surface.vertices[i] for i in triangle);edge1,edge2=subtract(b,a),subtract(c,a)
                    p=cross(direction,edge2);det=dot(edge1,p)
                    if abs(det)<1e-10:continue
                    inv=1/det;tvec=subtract(origin,a);u=dot(tvec,p)*inv
                    if u<0 or u>1:continue
                    q=cross(tvec,edge1);v=dot(direction,q)*inv
                    if v<0 or u+v>1:continue
                    distance=dot(edge2,q)*inv
                    if not enter-1e-6<=distance<best or distance>leave+1e-6:continue
                    uv=tuple(surface.uv[triangle[0]][i]*(1-u-v)+surface.uv[triangle[1]][i]*u+surface.uv[triangle[2]][i]*v for i in range(2))
                    image=surface.texture.frame_at(ticks)[1]
                    if image.pixel((uv[0]%1)*image.width,(uv[1]%1)*image.height)[3]/255*surface.color[3]<=.001:continue
                    best,position=distance,surface.position
            axis=min(range(3),key=lambda i:next_cross[i])
            if next_cross[axis]>min(best,leave)+1e-6:return position
            cell[axis]+=steps[axis];next_cross[axis]+=delta[axis]
        return position


def build_scene(voxels,resources,document=None,cancel=None):
    from .fluids import liquid_info,surfaces as fluid_surfaces
    from .tints import TintSampler
    models={};surfaces=[];check=checkpoint(cancel);fluids={};parts={};textures=set();texture_bytes=0
    def claim(texture):
        nonlocal texture_bytes
        if texture not in textures:
            textures.add(texture);texture_bytes+=texture.bytes
            if texture_bytes>128*1024*1024:raise ValueError('Visible texture budget exceeded; reduce pack resolution or view radius')
    for index,(position,block) in enumerate(voxels.items()):
        if index%32==0:check()
        blocks=[block]
        if document is not None:blocks.extend(document.get_extra_blocks(*position))
        layers=[]
        for value in blocks:
            fluid=liquid_info(value)
            if fluid is not None:fluids[position]=fluid
            if value.air or value.name in ('minecraft:water','minecraft:flowing_water','minecraft:lava','minecraft:flowing_lava'):continue
            model=resources.baked(value,position)
            for face in model.faces:claim(face.texture)
            layers.append((value,model))
        parts[position]=layers
        models[position]=Model((),frozenset(n for _,m in layers for n in m.occludes))
    tint=TintSampler(resources,document)
    for index,(position,layers) in enumerate(parts.items()):
        if index%32==0:check()
        for layer,(block,part) in enumerate(layers):
            for face in part.faces:
                if face.cull:
                    neighbor=models.get(tuple(position[i]+face.cull[i] for i in range(3)))
                    opposite=tuple(-n for n in face.cull)
                    if neighbor is not None and opposite in neighbor.occludes:continue
                light=max(.5,min(1.,.8+.2*face.normal[1]-.12*abs(face.normal[0]))) if face.shade else 1.
                rgb=tint.block(block,position) if face.tint>=0 else (1.,1.,1.)
                vertices=tuple(tuple(position[i]+(v[i]*.999+.0005 if layer else v[i]) for i in range(3)) for v in face.vertices)
                surfaces.append(Surface(position,vertices,face.normal,face.uv,face.texture,(*[c*light for c in rgb],1.)))
                if len(surfaces)>150_000:raise ValueError('Model face budget exceeded; reduce the view radius')
    liquids=fluid_surfaces(fluids,models,resources,cancel,tint,150_000-len(surfaces))
    for face in liquids:claim(face.texture)
    surfaces.extend(liquids)
    if len(surfaces)>150_000:raise ValueError('Model face budget exceeded; reduce the view radius')
    check();return Scene(surfaces,cancel)


@dataclass(frozen=True)
class View:
    width:int
    height:int
    origin:tuple
    right:tuple
    up:tuple
    forward:tuple
    cx:float
    cy:float
    scale:float
    perspective:bool=False
    near:float=.08
    far:float=8192.

    @classmethod
    def flight(cls,camera,width,height,center=None):
        frame=camera.frame(width,height,center)
        return cls(width,height,tuple(camera.position),frame.right,frame.up,frame.forward,frame.cx,frame.cy,frame.focal,True,camera.near)

    @classmethod
    def orbit(cls,width,height,origin,angle,elevation,scale,center):
        c,s,ce,se=math.cos(angle),math.sin(angle),math.cos(elevation),math.sin(elevation)
        return cls(width,height,tuple(origin),(c,0,-s),(-s*se,ce,-c*se),(-s*ce,-se,-c*ce),*center,scale)

    def coordinates(self,point):
        delta=subtract(point,self.origin);return dot(delta,self.right),dot(delta,self.up),dot(delta,self.forward)

    def project(self,point):
        x,y,z=self.coordinates(point)
        if self.perspective:
            if z<=0:return None
            return self.cx+x*self.scale/z,self.cy-y*self.scale/z,z
        return self.cx+x*self.scale,self.cy-y*self.scale,z

    def ray(self,x,y):
        dx,dy=(x-self.cx)/self.scale,(self.cy-y)/self.scale
        if self.perspective:return self.origin,tuple(self.forward[i]+self.right[i]*dx+self.up[i]*dy for i in range(3))
        return tuple(self.origin[i]+self.right[i]*dx+self.up[i]*dy-self.forward[i]*self.far for i in range(3)),self.forward

    def segment(self,a,b):
        va,vb=self.coordinates(a),self.coordinates(b);start,end=0.,1.
        low=self.near if self.perspective else -self.far
        for bound,above in ((low,True),(self.far,False)):
            old=va[2]>=bound if above else va[2]<=bound;new=vb[2]>=bound if above else vb[2]<=bound
            if not old and not new:return None
            if old!=new:
                t=(bound-va[2])/(vb[2]-va[2])
                if old:end=min(end,t)
                else:start=max(start,t)
        if start>end:return None
        p=tuple(a[i]+(b[i]-a[i])*start for i in range(3));q=tuple(a[i]+(b[i]-a[i])*end for i in range(3))
        return (*self.project(p)[:2],*self.project(q)[:2])

    def resized(self,width,height):
        from dataclasses import replace
        sx,sy=width/self.width,height/self.height
        if abs(sx-sy)>.01:raise ValueError('Rendering must preserve viewport aspect ratio')
        return replace(self,width=width,height=height,cx=self.cx*sx,cy=self.cy*sy,scale=self.scale*sy)
