"""Original resource-pack reader and Java JSON block-model baker.

Resource data is read only. Game assets are supplied by the user; none are
downloaded or distributed by this module. Model and texture caches are bounded.
"""
from collections import OrderedDict
from dataclasses import dataclass
from functools import cached_property
from pathlib import Path,PurePosixPath
import hashlib,json,math,threading,zipfile
from . import png
from .blocks import Block,color
from .geometry import FACE_DEFS

NORMALS={'up':(0,1,0),'down':(0,-1,0),'east':(1,0,0),'west':(-1,0,0),'south':(0,0,1),'north':(0,0,-1)}
FACE_NAMES=('up','east','west','south','north','down')
MAX_FILE=32*1024*1024


def location(value,namespace='minecraft'):
    if not isinstance(value,str):raise ValueError('Resource location must be text')
    return Block(value if ':' in value else namespace+':'+value).name


class Pack:
    def __init__(self,path):
        self.path=Path(path).expanduser().resolve();self._zip=None;self._files={};self._lock=threading.RLock()
        if self.path.is_dir():
            if not (self.path/'assets').is_dir():raise ValueError('Choose a Java resource pack folder containing assets')
        else:
            if not self.path.is_file():raise ValueError('Resource pack was not found')
            self._zip=zipfile.ZipFile(self.path)
            try:
                entries=self._zip.infolist()
                if len(entries)>100_000:raise ValueError('Resource archive has more than 100,000 entries')
                seen=set()
                for entry in entries:
                    if entry.filename in seen:raise ValueError('Resource archive has duplicate filenames')
                    seen.add(entry.filename)
                    if entry.filename.startswith(('assets/','data/')) and not entry.is_dir():self._files[entry.filename]=entry
                if not any(name.startswith('assets/') for name in self._files):raise ValueError('Resource archive contains no Java assets; choose a resource ZIP or Minecraft client JAR')
            except Exception:self.close();raise

    def read(self,name,limit=MAX_FILE):
        path=PurePosixPath(name)
        if path.is_absolute() or '\\' in name or any(part in ('','..','.') for part in name.split('/')):raise ValueError('Unsafe resource path')
        with self._lock:
            if self._zip is not None:
                entry=self._files.get(name)
                if entry is None:return None
                if entry.file_size>limit or entry.external_attr>>16&0o170000==0o120000:raise ValueError('Resource entry is oversized or a symbolic link')
                return self._zip.read(entry)
            file=self.path/path
            if not file.is_file():return None
            if file.resolve().is_relative_to(self.path) is False:raise ValueError('Resource path escapes the selected folder')
            if file.stat().st_size>limit:raise ValueError('Resource file exceeds its size limit')
            return file.read_bytes()

    def block_names(self):
        names=self._files if self._zip is not None else (p.relative_to(self.path).as_posix() for p in (self.path/'assets').glob('*/blockstates/**/*.json'))
        result=[]
        for name in names:
            parts=name.split('/')
            if len(parts)>=4 and parts[0]=='assets' and parts[2]=='blockstates' and name.endswith('.json'):
                try:result.append(location(parts[1]+':'+('/'.join(parts[3:])[:-5])))
                except ValueError:continue
        return tuple(sorted(set(result)))

    def close(self):
        if self._zip is not None:self._zip.close()


@dataclass(frozen=True,eq=False)
class Texture:
    frames:tuple
    durations:tuple=(1,)
    interpolate:bool=False

    def __post_init__(self):
        if not 1<=len(self.frames)<=4096 or len(self.frames)!=len(self.durations) or any(type(v) is not int or not 1<=v<=12000 for v in self.durations):raise ValueError('Invalid texture frames or duration')
        if any((f.width,f.height)!=(self.frames[0].width,self.frames[0].height) for f in self.frames):raise ValueError('Texture frames must have equal dimensions')

    @cached_property
    def images(self):return tuple({id(frame):frame for frame in self.frames}.values())

    @cached_property
    def opaque(self):return all(frame.opaque for frame in self.images)

    @cached_property
    def translucent(self):return (self.interpolate and not self.opaque) or any(any(0<a<255 for a in frame.rgba[3::4]) for frame in self.images)

    @cached_property
    def bytes(self):return sum(len(frame.rgba) for frame in self.images)

    def frame_at(self,ticks=0):
        tick=max(0,float(ticks))%sum(self.durations);index=0
        while tick>=self.durations[index]:tick-=self.durations[index];index+=1
        image=self.frames[index]
        if not self.interpolate or len(self.frames)==1:return index,image
        fraction=int(tick/self.durations[index]*20)/20
        if not fraction:return index,image
        next_frame=self.frames[(index+1)%len(self.frames)]
        return (index,fraction),png.Image(image.width,image.height,bytes(round(a*(1-fraction)+b*fraction) for a,b in zip(image.rgba,next_frame.rgba)))


@dataclass(frozen=True)
class Face:
    vertices:tuple
    normal:tuple
    uv:tuple
    texture:Texture
    cull:tuple|None=None
    shade:bool=True
    tint:int=-1


@dataclass(frozen=True)
class Model:
    faces:tuple
    occludes:frozenset=frozenset()

    @cached_property
    def bytes(self):return len(self.faces)*256+sum(t.bytes for t in {id(f.texture):f.texture for f in self.faces}.values())


def _normal(vertices):
    a,b,c=vertices[:3];u=tuple(b[i]-a[i] for i in range(3));v=tuple(c[i]-a[i] for i in range(3))
    n=(v[1]*u[2]-v[2]*u[1],v[2]*u[0]-v[0]*u[2],v[0]*u[1]-v[1]*u[0]);length=math.sqrt(sum(x*x for x in n))
    return tuple(x/length for x in n) if length else (0,0,0)


def _rotate(point,axis,angle,origin=(.5,.5,.5),rescale=False):
    values=[point[i]-origin[i] for i in range(3)];a,b={'x':(1,2),'y':(2,0),'z':(0,1)}[axis]
    c,s=math.cos(math.radians(angle)),math.sin(math.radians(angle));values[a],values[b]=values[a]*c-values[b]*s,values[a]*s+values[b]*c
    if rescale:
        factor=1/abs(c)
        values[a]*=factor;values[b]*=factor
    return tuple(values[i]+origin[i] for i in range(3))


def _canonical_uv(name,point):
    x,y,z=point
    return {'up':(x,z),'down':(x,1-z),'north':(1-x,1-y),'south':(x,1-y),'west':(z,1-y),'east':(1-z,1-y)}[name]


def _uv(name,vertices,rectangle=None,rotation=0):
    base=[_canonical_uv(name,v) for v in vertices];lo=tuple(min(v[i] for v in base) for i in range(2));hi=tuple(max(v[i] for v in base) for i in range(2))
    rect=tuple(v/16 for v in rectangle) if rectangle is not None else (*lo,*hi)
    if len(rect)!=4 or any(not math.isfinite(v) or abs(v)>1_000_000 for v in rect):raise ValueError('Invalid face UV coordinates')
    result=[]
    for u,v in base:
        u=(u-lo[0])/(hi[0]-lo[0]) if hi[0]!=lo[0] else 0;v=(v-lo[1])/(hi[1]-lo[1]) if hi[1]!=lo[1] else 0
        for _ in range(rotation//90%4):u,v=v,1-u
        result.append((rect[0]+u*(rect[2]-rect[0]),rect[1]+v*(rect[3]-rect[1])))
    return tuple(result)


def matches(condition,properties,depth=0):
    if depth>16 or not isinstance(condition,dict) or len(condition)>64:raise ValueError('Invalid multipart condition')
    for key,value in condition.items():
        if key in ('OR','AND'):
            if not isinstance(value,list) or not value or len(value)>64:raise ValueError('Invalid multipart logical expression')
            values=[matches(item,properties,depth+1) for item in value]
            if not (any(values) if key=='OR' else all(values)):return False
        else:
            if not isinstance(value,str):raise ValueError('Multipart state value must be text')
            negate=value.startswith('!');choices=(value[1:] if negate else value).split('|')
            found=properties.get(key) in choices
            if found==negate:return False
    return True


class ResourceStack:
    def __init__(self,paths=()):
        paths=tuple(paths)
        if len(paths)>16:raise ValueError('Use at most 16 resource packs')
        self.packs=[];self._lock=threading.RLock();self._json=OrderedDict();self._json_sizes={};self._models=OrderedDict();self._model_sizes={};self._textures=OrderedDict();self._baked=OrderedDict();self._static=OrderedDict();self.warnings=OrderedDict()
        try:
            for path in paths:self.packs.append(Pack(path))
        except Exception:self.close();raise
        self.paths=tuple(str(pack.path) for pack in self.packs)
        self.block_names=tuple(sorted({name for pack in self.packs for name in pack.block_names()}))
        self._fallback={}

    def close(self):
        for pack in self.packs:pack.close()

    def warn(self,key,message):
        self.warnings[key]=str(message)
        while len(self.warnings)>100:self.warnings.popitem(last=False)

    def read(self,name,limit=MAX_FILE):
        for pack in reversed(self.packs):
            raw=pack.read(name,limit)
            if raw is not None:return raw
        return None

    def json(self,category,name,optional=False,root='assets'):
        if root not in ('assets','data'):raise ValueError('Invalid resource root')
        name=location(name);namespace,key=name.split(':',1);path=f'{root}/{namespace}/{category}/{key}.json'
        if path not in self._json:
            raw=self.read(path,1024*1024)
            if raw is None:
                value=None
            else:
                value=json.loads(raw)
                if not isinstance(value,dict):raise ValueError('Resource JSON must be an object')
                def depth(item,level=0):
                    if level>32:raise ValueError('Resource JSON is too deeply nested')
                    if isinstance(item,dict):
                        for child in item.values():depth(child,level+1)
                    elif isinstance(item,list):
                        for child in item:depth(child,level+1)
                depth(value)
            self._json[path]=value;self._json_sizes[path]=len(raw) if raw is not None else 0
            while len(self._json)>512 or sum(self._json_sizes.values())>8*1024*1024:
                removed,_=self._json.popitem(last=False);self._json_sizes.pop(removed)
        self._json.move_to_end(path);value=self._json[path]
        if value is None and not optional:raise ValueError('Missing resource '+path)
        return value

    def texture(self,name):
        name=location(name)
        if name in self._textures:self._textures.move_to_end(name);return self._textures[name]
        namespace,key=name.split(':',1);path=f'assets/{namespace}/textures/{key}.png';raw=self.read(path)
        if raw is None:raise ValueError('Missing texture '+name)
        image=png.decode(raw);meta=self.read(path+'.mcmeta',1024*1024)
        animation=json.loads(meta).get('animation') if meta is not None else None
        if animation is None:texture=Texture((image,))
        else:
            if not isinstance(animation,dict):raise ValueError('Invalid texture animation')
            width=animation.get('width',image.width if 'height' in animation else min(image.width,image.height))
            height=animation.get('height',image.height if 'width' in animation else min(image.width,image.height))
            if type(width) is not int or type(height) is not int or min(width,height)<1 or image.width%width or image.height%height:raise ValueError('Animation frames do not fit the texture')
            count=(image.width//width)*(image.height//height);default=animation.get('frametime',1);entries=animation.get('frames',list(range(count)))
            if not isinstance(entries,list) or not entries or len(entries)>4096 or type(default) is not int or not 1<=default<=12000:raise ValueError('Invalid animation frames or timing')
            frames=[];durations=[];images={}
            for entry in entries:
                index=entry.get('index') if isinstance(entry,dict) else entry;duration=entry.get('time',default) if isinstance(entry,dict) else default
                if type(index) is not int or not 0<=index<count or type(duration) is not int or not 1<=duration<=12000:raise ValueError('Invalid animation frame index/time')
                if index not in images:images[index]=image.crop(index%(image.width//width)*width,index//(image.width//width)*height,width,height)
                frames.append(images[index]);durations.append(duration)
            texture=Texture(tuple(frames),tuple(durations),bool(animation.get('interpolate',False)))
        self._textures[name]=texture
        while len(self._textures)>256 or (len(self._textures)>1 and sum(t.bytes for t in self._textures.values())>32*1024*1024):self._textures.popitem(last=False)
        return texture

    def model(self,name,parents=()):
        name=location(name)
        if name in parents or len(parents)>32:raise ValueError('Cyclic or overly deep model inheritance')
        if name in self._models:self._models.move_to_end(name);return self._models[name]
        own=self.json('models',name,True)
        if own is None:
            if name in ('minecraft:block/block','minecraft:block/thin_block'):own={}
            elif name in ('minecraft:block/cube','minecraft:block/cube_all'):
                own={'textures':{face:'#all' for face in NORMALS} if name.endswith('cube_all') else {},'elements':[{'from':[0,0,0],'to':[16,16,16],'faces':{face:{'texture':'#'+face,'cullface':face} for face in NORMALS}}]}
            else:raise ValueError('Missing model '+name)
        parent=own.get('parent');result={}
        if parent:
            if str(parent).startswith('builtin/'):raise ValueError('Procedural entity model '+str(parent)+' requires a dedicated renderer')
            result=dict(self.model(location(parent),(*parents,name)))
        textures=dict(result.get('textures',{}));textures.update(own.get('textures',{}));result.update(own);result['textures']=textures
        self._models[name]=result
        self._model_sizes[name]=len(json.dumps(result))
        while len(self._models)>256 or sum(self._model_sizes.values())>8*1024*1024:
            removed,_=self._models.popitem(last=False);self._model_sizes.pop(removed)
        return result

    def __del__(self):
        if getattr(self,'_zip',None) is not None:self._zip.close()

    def _texture_ref(self,value,textures):
        # Some shipped Java models use a bare texture-map key on a face.
        if isinstance(value,str) and value in textures:value='#'+value
        visited=set()
        while isinstance(value,str) and value.startswith('#'):
            if value in visited or len(visited)>32:raise ValueError('Cyclic texture reference')
            visited.add(value);key=value[1:]
            if key not in textures:raise ValueError('Missing texture variable '+value)
            value=textures[key]
        return self.texture(location(value))

    @staticmethod
    def _variant(entries,seed):
        if isinstance(entries,dict):return entries
        if not isinstance(entries,list) or not 1<=len(entries)<=256 or any(not isinstance(entry,dict) for entry in entries):raise ValueError('Invalid block model variants')
        weights=[entry.get('weight',1) for entry in entries]
        if any(type(n) is not int or not 1<=n<=65536 for n in weights):raise ValueError('Invalid variant weight')
        choice=seed%sum(weights)
        for entry,weight in zip(entries,weights):
            if choice<weight:return entry
            choice-=weight

    def _bake(self,choice):
        name=location(choice.get('model'));model=self.model(name);elements=model.get('elements',[]);textures=model.get('textures',{})
        if not isinstance(elements,list) or len(elements)>256:raise ValueError('Invalid or oversized element list')
        rx,ry=choice.get('x',0),choice.get('y',0)
        if any(type(v) is not int or v%90 for v in (rx,ry)):raise ValueError('Blockstate rotations must be multiples of 90 degrees')
        rx%=360;ry%=360
        result=[];texture_bytes=0;seen_textures=set()
        for element in elements:
            lo,hi=element.get('from'),element.get('to')
            if not isinstance(lo,list) or not isinstance(hi,list) or len(lo)!=3 or len(hi)!=3 or any(type(v) not in (int,float) or not math.isfinite(v) or abs(v)>128 for v in (*lo,*hi)):raise ValueError('Invalid model element bounds')
            lo=tuple(v/16 for v in lo);hi=tuple(v/16 for v in hi)
            # Inverted elements are valid: Java spawner models use them to
            # render inside faces, so preserve their winding and UV direction.
            rotation=element.get('rotation');surface=element.get('faces',{})
            for face_name,definition in surface.items():
                if face_name not in NORMALS or not isinstance(definition,dict):raise ValueError('Invalid model face')
                offsets=FACE_DEFS[FACE_NAMES.index(face_name)][1]
                vertices=tuple(tuple(hi[i] if v[i] else lo[i] for i in range(3)) for v in offsets)
                uv_rotation=definition.get('rotation',0)
                if type(uv_rotation) is not int or uv_rotation not in (0,90,180,270):raise ValueError('Invalid face UV rotation')
                tint=definition.get('tintindex',-1)
                if type(tint) is not int or not -1<=tint<=255:raise ValueError('Invalid face tint index')
                uv=_uv(face_name,vertices,definition.get('uv'),uv_rotation)
                if rotation:
                    origin=rotation.get('origin',[8,8,8]);axis=rotation.get('axis');angle=rotation.get('angle',0)
                    if axis not in ('x','y','z') or angle not in (-45,-22.5,0,22.5,45) or len(origin)!=3 or any(type(v) not in (int,float) or not math.isfinite(v) or abs(v)>128 for v in origin):raise ValueError('Invalid element rotation')
                    vertices=tuple(_rotate(v,axis,angle,tuple(x/16 for x in origin),rotation.get('rescale',False)) for v in vertices)
                vertices=tuple(_rotate(_rotate(v,'x',-rx),'y',-ry) for v in vertices)
                normal=_normal(vertices)
                if normal==(0,0,0):continue
                if choice.get('uvlock') and not rotation:
                    direction=max(NORMALS,key=lambda key:sum(a*b for a,b in zip(NORMALS[key],normal)))
                    uv=_uv(direction,vertices,definition.get('uv'),uv_rotation)
                cull=definition.get('cullface');cull_normal=None
                if cull:
                    if cull not in NORMALS:raise ValueError('Invalid cullface')
                    cull_normal=tuple(round(v) for v in _rotate(_rotate(NORMALS[cull],'x',-rx,(0,0,0)),'y',-ry,(0,0,0)))
                texture=self._texture_ref(definition.get('texture'),textures)
                if texture not in seen_textures:
                    seen_textures.add(texture);texture_bytes+=texture.bytes
                    if texture_bytes>64*1024*1024:raise ValueError('Model texture budget exceeded')
                result.append(Face(vertices,normal,uv,texture,cull_normal,bool(element.get('shade',True)),tint))
        return tuple(result)

    def fallback(self,block):
        if block in self._fallback:return self._fallback[block]
        tint=color(block);rgba=tuple(int(tint[i:i+2],16) for i in (1,3,5))
        alpha=130 if block.name.endswith((':water',':flowing_water')) else 100 if block.name.endswith(':glass') else 255
        texture=Texture((png.Image(1,1,bytes((*rgba,alpha))),))
        faces=tuple(Face(tuple(tuple(float(n) for n in p) for p in offsets),normal,_uv(name,offsets),texture,normal) for name,(normal,offsets,_) in zip(FACE_NAMES,FACE_DEFS))
        model=Model(faces,frozenset(NORMALS.values()) if alpha==255 else frozenset());self._fallback[block]=model
        if len(self._fallback)>1024:self._fallback.pop(next(iter(self._fallback)))
        return model

    def baked(self,block,position=(0,0,0)):
        with self._lock:
            if block.air:return Model(())
            cached=self._static.get(block)
            if cached in self._baked:
                self._static.move_to_end(block);self._baked.move_to_end(cached);return self._baked[cached]
            try:
                state=self.json('blockstates',block.name,True)
                if state is None:
                    # Texture-only packs can replace a cube without shipping the
                    # vanilla parent graph. Supplied models/variants take priority.
                    namespace,key=block.name.split(':',1)
                    texture=self.texture(namespace+':block/'+key)
                    model=self.fallback(block)
                    return self._remember('texture:'+block.name,Model(tuple(Face(f.vertices,f.normal,f.uv,texture,f.cull,f.shade,f.tint) for f in model.faces),frozenset(NORMALS.values()) if texture.opaque else frozenset()),block)
                props=dict(block.properties);choices=[];static=True
                seed=int.from_bytes(hashlib.blake2s((block.name+str(tuple(position))).encode(),digest_size=8).digest(),'little')
                if 'variants' in state:
                    variants=state['variants']
                    if not isinstance(variants,dict) or len(variants)>4096:raise ValueError('Invalid blockstate variants')
                    for condition,entries in variants.items():
                        pairs=dict(item.split('=',1) for item in condition.split(',')) if condition else {}
                        if all(key not in props or props[key] in value.split('|') for key,value in pairs.items()):
                            static=not isinstance(entries,list) or len(entries)==1
                            choices.append(self._variant(entries,seed));break
                if 'multipart' in state:
                    parts=state['multipart']
                    if not isinstance(parts,list) or len(parts)>256:raise ValueError('Invalid multipart blockstate')
                    for index,part in enumerate(parts):
                        if 'when' not in part or matches(part['when'],props):
                            entries=part.get('apply');static=static and (not isinstance(entries,list) or len(entries)==1)
                            choices.append(self._variant(entries,seed+index))
                if not choices:raise ValueError('No model variant matches '+str(block))
                key=json.dumps(choices,sort_keys=True,separators=(',',':'))
                if key not in self._baked:
                    combined=[];texture_bytes=0;seen_textures=set()
                    for choice in choices:
                        combined.extend(self._bake(choice))
                        if len(combined)>4096:raise ValueError('Multipart model exceeds 4096 faces')
                        for face in combined:
                            if face.texture not in seen_textures:
                                seen_textures.add(face.texture);texture_bytes+=face.texture.bytes
                                if texture_bytes>64*1024*1024:raise ValueError('Multipart model texture budget exceeded')
                    faces=tuple(combined);occludes=set()
                    if not faces:raise ValueError('This block uses procedural game geometry; showing a colored marker')
                    for face in faces:
                        normal=tuple(round(v) for v in face.normal)
                        if face.texture.opaque and face.cull==normal and normal in NORMALS.values():
                            axis=next(i for i,n in enumerate(normal) if n);coordinate=1 if normal[axis]>0 else 0
                            others=[i for i in range(3) if i!=axis]
                            expected={tuple(coordinate if i==axis else corner[others.index(i)] for i in range(3)) for corner in ((0,0),(0,1),(1,0),(1,1))}
                            rounded={tuple(round(v,7) for v in vertex) for vertex in face.vertices}
                            if rounded==expected:occludes.add(normal)
                    return self._remember(key,Model(faces,frozenset(occludes)),block if static else None)
                return self._remember(key,self._baked[key],block if static else None)
            except (ValueError,TypeError,KeyError,IndexError,AttributeError,OverflowError,RecursionError,OSError,zipfile.BadZipFile) as exc:
                self.warn(block.name,exc);return self._remember('fallback:'+str(block),self.fallback(block),block)

    def _remember(self,key,model,block=None):
        self._baked[key]=model;self._baked.move_to_end(key)
        while len(self._baked)>1024 or (len(self._baked)>1 and sum(m.bytes for m in self._baked.values())>64*1024*1024):self._baked.popitem(last=False)
        if block is not None:
            self._static[block]=key;self._static.move_to_end(block)
            while len(self._static)>1024:self._static.popitem(last=False)
        return model
