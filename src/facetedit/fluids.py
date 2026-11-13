"""Independent fluid surfaces derived from stored levels and adjacent blocks."""
import math
from .resources import _normal
from .scene import Surface
from .geometry import checkpoint
from .blocks import Block


def liquid_info(block):
    props=dict(block.properties)
    kind=block.name.removeprefix('minecraft:').removeprefix('flowing_')
    if block.name.startswith('minecraft:') and kind in ('water','lava'):
        try:level=int(props.get('level',props.get('liquid_depth','0')))
        except ValueError:level=0
        return kind,max(0,min(15,level))
    if props.get('waterlogged')=='true':return 'water',0
    return None


def surfaces(fluids,models,resources,cancel=None,tints=None,max_surfaces=150_000):
    textures={};check=checkpoint(cancel);result=[];height_cache={}
    def texture(kind,flow=False):
        key=kind,flow
        if key not in textures:
            try:textures[key]=(resources.texture('minecraft:block/'+kind+('_flow' if flow else '_still')),True)
            except (OSError,ValueError):textures[key]=(resources.fallback(Block(kind)).faces[0].texture,False)
        return textures[key]
    def solid(p,normal=None):
        model=models.get(p)
        return model is not None and (normal in model.occludes if normal is not None else len(model.occludes)==6)
    def own(kind,x,y,z):
        value=fluids.get((x,y,z))
        if value is not None and value[0]==kind:
            above=fluids.get((x,y+1,z))
            if above is not None and above[0]==kind:return 1.
            return (8-(value[1] if value[1]<8 else 0))/9
        return -1. if solid((x,y,z)) else 0.
    def corner(kind,x,y,z):
        key=kind,x,y,z
        if key not in height_cache:
            values=[own(kind,bx,y,bz) for bx,bz in ((x-1,z-1),(x,z-1),(x-1,z),(x,z))]
            if max(values)>=1:height_cache[key]=1.
            else:
                total=weight=0.
                for value in values:
                    if value>=0:
                        w=10 if value>=.8 else 1;total+=value*w;weight+=w
                height_cache[key]=total/weight if weight else 0.
        return height_cache[key]
    for index,(position,(kind,level)) in enumerate(fluids.items()):
        if index%16==0:check()
        x,y,z=position
        heights=(corner(kind,x,y,z),corner(kind,x+1,y,z),corner(kind,x+1,y,z+1),corner(kind,x,y,z+1))
        top=((0,heights[0],0),(1,heights[1],0),(1,heights[2],1),(0,heights[3],1))
        flowing=max(heights)-min(heights)>1e-6
        gx=(heights[0]+heights[3]-heights[1]-heights[2])/2;gz=(heights[0]+heights[1]-heights[2]-heights[3])/2
        angle=math.atan2(gz,gx)-math.pi/2;c,s=math.cos(angle),math.sin(angle)
        top_uv=tuple((.5+(u-.5)*c*.5-(v-.5)*s*.5,.5+(u-.5)*s*.5+(v-.5)*c*.5) for u,v in ((0,0),(1,0),(1,1),(0,1))) if flowing else ((0,0),(1,0),(1,1),(0,1))
        candidates=[((0,1,0),top,top_uv,flowing),((0,-1,0),((0,0,1),(1,0,1),(1,0,0),(0,0,0)),((0,0),(1,0),(1,1),(0,1)),False)]
        for normal,indices in (((1,0,0),(1,2)),((-1,0,0),(3,0)),((0,0,1),(2,3)),((0,0,-1),(0,1))):
            a,b=top[indices[0]],top[indices[1]]
            vertices=((a[0],0,a[2]),(b[0],0,b[2]),b,a)
            uv=((0,.5),(.5,.5),(.5,(1-b[1])*.5),(0,(1-a[1])*.5))
            candidates.append((normal,vertices,uv,True))
        for normal,vertices,uv,flow in candidates:
            adjacent=tuple(position[i]+normal[i] for i in range(3));other=fluids.get(adjacent)
            if (other is not None and other[0]==kind) or solid(adjacent,tuple(-v for v in normal)) or solid(position,normal):continue
            tex,supplied=texture(kind,flow)
            rgb=(tints.color('water',position) if tints is not None else (.247,.463,.894)) if kind=='water' and supplied else (1.,1.,1.)
            alpha=.65 if kind=='water' and supplied else 1.
            light=1. if kind=='lava' else max(.5,.8+.2*normal[1]-.12*abs(normal[0]))
            result.append(Surface(position,tuple(tuple(position[i]+v[i] for i in range(3)) for v in vertices),_normal(vertices),uv,tex,(*(v*light for v in rgb),alpha)))
            if len(result)>max_surfaces:raise ValueError('Fluid face budget exceeded; reduce the view radius')
    check();return result
