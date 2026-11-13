"""Bounded affine voxel resampling with explicit block-state rotation policy.

Scale, then rotate X, Y, Z about the clipboard's local origin. Translate the
resulting bounding box to local zero. Destination cell centers sample source
cells through the inverse matrix; holes in a sparse clipboard remain holes.
"""
import itertools,math
from .blocks import Block
from . import nbt

VECTORS={'east':(1,0,0),'west':(-1,0,0),'up':(0,1,0),'down':(0,-1,0),'south':(0,0,1),'north':(0,0,-1)}


def multiply(a,b):return tuple(tuple(sum(a[i][k]*b[k][j] for k in range(3)) for j in range(3)) for i in range(3))
def vector(matrix,value):return tuple(sum(matrix[i][j]*value[j] for j in range(3)) for i in range(3))
def integer(value):return round(value) if abs(value-round(value))<1e-8 else value


class Transform:
    def __init__(self,size,rotation=(0,0,0),scale=(1,1,1),limit=65536):
        if len(size)!=3 or any(type(n) is not int or n<=0 for n in size):raise ValueError('Transform requires positive integer dimensions')
        if len(rotation)!=3 or len(scale)!=3:raise ValueError('Transform needs three angles and three scales')
        rotation=tuple(float(v) for v in rotation);scale=tuple(float(v) for v in scale)
        if any(not math.isfinite(v) for v in (*rotation,*scale)) or any(not .01<=abs(v)<=100 for v in scale):raise ValueError('Scales must be finite and between ±0.01 and ±100')
        x,y,z=(math.radians(v%360) for v in rotation)
        cx,sx,cy,sy,cz,sz=math.cos(x),math.sin(x),math.cos(y),math.sin(y),math.cos(z),math.sin(z)
        # Positive Y matches the editor's clockwise quarter-turn convention.
        rotation_matrix=multiply(((cz,-sz,0),(sz,cz,0),(0,0,1)),multiply(((cy,0,-sy),(0,1,0),(sy,0,cy)),((1,0,0),(0,cx,-sx),(0,sx,cx))))
        self.matrix=tuple(tuple(rotation_matrix[i][j]*scale[j] for j in range(3)) for i in range(3))
        self.inverse=tuple(tuple(rotation_matrix[j][i]/scale[i] for j in range(3)) for i in range(3))
        corners=[vector(self.matrix,p) for p in itertools.product(*((0,n) for n in size))]
        self.minimum=tuple(math.floor(integer(min(p[i] for p in corners))) for i in range(3))
        self.size=tuple(math.ceil(integer(max(p[i] for p in corners)))-self.minimum[i] for i in range(3))
        if math.prod(self.size)>limit:raise ValueError('Transformed bounding volume exceeds 65,536 blocks; use a smaller selection or scale')
        self.source_size=size

    def source(self,position):
        value=tuple(integer(v) for v in vector(self.inverse,tuple(position[i]+.5+self.minimum[i] for i in range(3))))
        if any(v<0 or v>=self.source_size[i] for i,v in enumerate(value)):return None
        return tuple(math.floor(integer(v)) for v in value)

    def target(self,position):
        value=vector(self.matrix,tuple(v+.5 for v in position))
        return tuple(math.floor(integer(value[i]-self.minimum[i])) for i in range(3))

    def offset(self,offset):return tuple(math.floor(integer(v)) for v in vector(self.matrix,offset))

    def direction(self,direction):
        if direction not in VECTORS:return direction
        value=vector(self.matrix,VECTORS[direction]);axis=max(range(3),key=lambda i:abs(value[i]))
        return (('west','east'),('down','up'),('north','south'))[axis][int(value[axis]>=0)]

    def rotation16(self,number):
        angle=number*math.pi/8
        x,_,z=vector(self.matrix,(-math.sin(angle),0,math.cos(angle)))
        if abs(x)+abs(z)<1e-9:raise ValueError('A standing sign cannot face vertically; disable block-state rotation for this transform')
        return round(math.atan2(-x,z)*8/math.pi)%16

    def block(self,block,edition,legacy=False):
        if all(self.direction(key)==key for key in VECTORS):return block
        if legacy:
            from .legacy import identifier
            number,data=identifier(block)
            if data or number in (23,26,27,28,29,33,34,50,53,54,61,62,63,64,65,66,67,68,69,71,75,76,77,96,106,107,108,109,114,128,130,134,135,136,143,146,154,156,158,163,164,167,180,193,194,195,196,197,198,203,218):
                raise ValueError('Legacy metadata rotation needs a versioned state translator; disable block-state rotation to transform geometry')
            return block
        props=dict(block.properties);original_properties=dict(props)
        up=self.direction('up')
        horizontal=all(self.direction(key) not in ('up','down') for key in ('north','east','south','west'))
        if horizontal:
            order=('north','east','south','west');turns=order.index(self.direction('north'))
            mirror=self.direction('east')!=order[(turns+1)%4]
            block=block.transform(turns,mirror,edition);props=dict(block.properties)
        else:
            complex_keys={'shape','hinge','half','type','face','rotation','ground_sign_direction','rail_direction','vine_direction_bits','direction','weirdo_direction','door_hinge_bit','huge_mushroom_bits','minecraft:cardinal_direction','coral_direction'}
            if complex_keys&props.keys() or any(k in props for k in ('north','east','south','west')):
                raise ValueError('This block cannot represent the tilted orientation: '+str(block)+'. Disable block-state rotation to transform geometry')
        if not horizontal or up=='down':
            for key in ('facing','block_face','torch_facing_direction','minecraft:facing_direction','minecraft:block_face'):
                if key in props:props[key]=self.direction(props[key]) if not horizontal else ('down' if props[key]=='up' else 'up' if props[key]=='down' else props[key])
            for key in ('axis','pillar_axis'):
                if not horizontal and props.get(key) in ('x','y','z'):
                    v=self.direction({'x':'east','y':'up','z':'south'}[props[key]])
                    props[key]='x' if v in ('east','west') else 'y' if v in ('up','down') else 'z'
            if 'facing_direction' in props:
                order=('down','up','south','north','east','west') if edition=='Bedrock' and block.name=='minecraft:end_rod' else ('down','up','north','south','west','east');old=order[int(props['facing_direction'])]
                if not horizontal:props['facing_direction']=str(order.index(self.direction(old)))
                elif old in ('up','down'):props['facing_direction']=str(order.index('down' if old=='up' else 'up'))
            if 'multi_face_direction_bits' in props:
                bits=int(original_properties['multi_face_direction_bits']);order=('down','up','south','west','north','east')
                props['multi_face_direction_bits']=str(sum(1<<order.index(self.direction(side)) for i,side in enumerate(order) if bits&(1<<i)))
            if up=='down':
                for key in ('half','type'):
                    if props.get(key) in ('top','bottom'):props[key]='bottom' if props[key]=='top' else 'top'
                if 'upside_down_bit' in props:props['upside_down_bit']='false' if props['upside_down_bit']=='true' else 'true'
        return Block(block.name,tuple(props.items()),block.state_types)

    def entity(self,data,target,rotate_states=True,block=None):
        _,tag=nbt.loads(data);old=tuple(nbt.get(tag,axis) for axis in 'xyz')
        if any(type(v) is not int for v in old):raise ValueError('Invalid transformed block NBT coordinates')
        center=self.target(old)
        if 'pairx' in tag.value or 'pairz' in tag.value:
            pair=self.target((nbt.get(tag,'pairx',old[0]),old[1],nbt.get(tag,'pairz',old[2])))
            if pair[1]!=center[1]:raise ValueError('A paired chest cannot link vertically')
            for key,axis in (('pairx',0),('pairz',2)):tag.value[key]=nbt.Tag(nbt.INT,pair[axis]+target[axis]-center[axis])
        if rotate_states and 'Rot' in tag.value:
            value=tag.value['Rot'];tag.value['Rot']=nbt.Tag(value.kind,self.rotation16(value.value))
        if rotate_states and nbt.get(tag,'id')=='ShulkerBox' and 'facing' in tag.value:
            order=('down','up','north','south','west','east');value=tag.value['facing']
            if value.kind!=nbt.BYTE or not 0<=value.value<6:raise ValueError('Invalid Shulker Box facing byte')
            tag.value['facing']=nbt.Tag(nbt.BYTE,order.index(self.direction(order[value.value])))
        if rotate_states and nbt.get(tag,'id')=='Skull' and 'Rotation' in tag.value:
            if block is None:raise ValueError('Skull rotation requires its block mount state')
            if self.direction('up')!='up':raise ValueError('A tilted skull needs a mount/rotation migration; disable block-state rotation')
            if dict(block.properties).get('facing_direction')=='1':
                value=tag.value['Rotation']
                if value.kind!=nbt.FLOAT:raise ValueError('Invalid skull Rotation type')
                # Native rotations may be continuous in an unconverted world.
                angle=math.radians(value.value);x,_,z=vector(self.matrix,(-math.sin(angle),0,math.cos(angle)))
                rotation=math.degrees(math.atan2(-x,z))
                tag.value['Rotation']=nbt.Tag(nbt.FLOAT,integer(rotation))
        for axis,value in zip('xyz',target):tag.value[axis]=nbt.Tag(nbt.INT,value)
        return nbt.dumps(tag)


def transform_clipboard(clipboard,rotation=(0,0,0),scale=(1,1,1),rotate_states=True):
    from .model import Clipboard,MAX_OPERATION
    transform=Transform(clipboard.size,rotation,scale,MAX_OPERATION)
    if all(float(r)%360==0 for r in rotation) and all(float(v)==1 for v in scale):return clipboard
    blocks,entities,extras,palette={},{},{},{}
    def state(block):
        if block not in palette:
            value=transform.block(block,clipboard.edition,clipboard.edition=='Java' and clipboard.data_version is not None and clipboard.data_version<1451) if rotate_states else block
            if rotate_states:
                props=dict(value.properties)
                for key in ('rotation','ground_sign_direction'):
                    if key in props:props[key]=str(transform.rotation16(int(dict(block.properties)[key])))
                value=Block(value.name,tuple(props.items()),value.state_types)
            palette[block]=value
        return palette[block]
    for position in itertools.product(*(range(n) for n in transform.size)):
        source=transform.source(position)
        if source not in clipboard.blocks:continue
        blocks[position]=state(clipboard.blocks[source])
        if source in clipboard.extra_blocks:extras[position]=tuple(state(b) for b in clipboard.extra_blocks[source])
        if source in clipboard.entities:entities[position]=transform.entity(clipboard.entities[source],position,rotate_states,clipboard.blocks[source])
    return Clipboard(transform.size,blocks,clipboard.edition,transform.offset(clipboard.offset),entities,clipboard.data_version,extras,clipboard.game_version)
