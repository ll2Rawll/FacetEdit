"""Numeric Java biomes and full-resolution Bedrock biome storage.

Names below are format identifiers, not translation between game versions.
Unknown numeric IDs remain addressable as numeric:<unsigned integer>.
"""
import math
import struct
from . import nbt
from .formats import unpack_indices,pack_indices
from .blocks import Block

# Stable legacy IDs shared by the two formats; edition-specific IDs are separate.
COMMON={0:'ocean',1:'plains',2:'desert',3:'mountains',4:'forest',5:'taiga',6:'swamp',7:'river',8:'nether_wastes',9:'the_end',10:'frozen_ocean',11:'frozen_river',12:'snowy_tundra',13:'snowy_mountains',14:'mushroom_fields',15:'mushroom_field_shore',16:'beach',17:'desert_hills',18:'wooded_hills',19:'taiga_hills',20:'mountain_edge',21:'jungle',22:'jungle_hills',23:'jungle_edge',24:'deep_ocean',25:'stone_shore',26:'snowy_beach',27:'birch_forest',28:'birch_forest_hills',29:'dark_forest',30:'snowy_taiga',31:'snowy_taiga_hills',32:'giant_tree_taiga',33:'giant_tree_taiga_hills',34:'wooded_mountains',35:'savanna',36:'savanna_plateau',37:'badlands',38:'wooded_badlands_plateau',39:'badlands_plateau',127:'the_void',129:'sunflower_plains',130:'desert_lakes',131:'gravelly_mountains',132:'flower_forest',133:'taiga_mountains',134:'swamp_hills',140:'ice_spikes',149:'modified_jungle',151:'modified_jungle_edge',155:'tall_birch_forest',156:'tall_birch_hills',157:'dark_forest_hills',158:'snowy_taiga_mountains',160:'giant_spruce_taiga',161:'giant_spruce_taiga_hills',162:'modified_gravelly_mountains',163:'shattered_savanna',164:'shattered_savanna_plateau',165:'eroded_badlands',166:'modified_wooded_badlands_plateau',167:'modified_badlands_plateau',168:'bamboo_jungle',169:'bamboo_jungle_hills'}
JAVA={**COMMON,40:'small_end_islands',41:'end_midlands',42:'end_highlands',43:'end_barrens',44:'warm_ocean',45:'lukewarm_ocean',46:'cold_ocean',47:'deep_warm_ocean',48:'deep_lukewarm_ocean',49:'deep_cold_ocean',50:'deep_frozen_ocean',170:'soul_sand_valley',171:'crimson_forest',172:'warped_forest',173:'basalt_deltas'}
BEDROCK={**COMMON,40:'warm_ocean',41:'deep_warm_ocean',42:'lukewarm_ocean',43:'deep_lukewarm_ocean',44:'cold_ocean',45:'deep_cold_ocean',46:'deep_frozen_ocean',178:'soul_sand_valley',179:'crimson_forest',180:'warped_forest',181:'basalt_deltas'}


def name(identifier,edition='Java'):
    values=BEDROCK if edition=='Bedrock' else JAVA
    return 'minecraft:'+values[identifier] if identifier in values else f'numeric:{identifier}'


def identifier(value,edition='Java'):
    if isinstance(value,str) and value.startswith('numeric:'):
        number=int(value[8:])
        if not 0<=number<=0xffffffff:raise ValueError('Biome ID must fit an unsigned 32-bit integer')
        return number
    location=Block(value).name
    values=BEDROCK if edition=='Bedrock' else JAVA
    for number,entry in values.items():
        if location=='minecraft:'+entry:return number
    raise ValueError(f'No verified {edition} numeric biome ID for {location}; enter numeric:<ID>')


def numeric_java(level):
    tag=level.value.get('Biomes')
    if tag is None or tag.kind not in (nbt.BYTE_ARRAY,nbt.INT_ARRAY) or not (len(tag.value)==256 or tag.kind==nbt.INT_ARRAY and 64<=len(tag.value)<=16256 and len(tag.value)%64==0):
        raise nbt.FormatError('Expected a 256-entry column biome array or a bounded 3D numeric biome array')
    return tag


def java_index(x,y,z,count,minimum=0,three_d=None):
    if three_d is None:three_d=count!=256
    return max(0,min(count//16-1,(y-minimum)//4))*16+((z//4)&3)*4+((x//4)&3) if three_d else (z&15)*16+(x&15)


class BedrockBiomes:
    def __init__(self,data,minimum):
        if len(data)<513:raise nbt.FormatError('Truncated Bedrock 3D biome data')
        self.height=data[:512];self.minimum=minimum//16
        self.sections=[];self.raw=[];offset=512
        def take(count):
            nonlocal offset
            if offset+count>len(data):raise nbt.FormatError('Truncated biome palette')
            out=data[offset:offset+count];offset+=count;return out
        while offset<len(data):
            if len(self.sections)>=128:raise nbt.FormatError('Too many Bedrock biome sections')
            start=offset;header=take(1)[0]
            if header==255:cells=None
            else:
                bits=header>>1
                if bits not in (0,1,2,3,4,5,6,8,16):raise nbt.FormatError('Unknown biome palette bit width')
                if bits:
                    count=math.ceil(4096/(32//bits));words=struct.unpack('<'+str(count)+'i',take(count*4))
                    indexes=unpack_indices(words,bits,width=32)
                    length=struct.unpack('<I',take(4))[0]
                    if not 1<=length<=4096:raise nbt.FormatError('Invalid biome palette length')
                    palette=struct.unpack('<'+str(length)+'I',take(length*4))
                    if max(indexes)>=length:raise nbt.FormatError('Biome palette index out of range')
                    cells=tuple(palette[index] for index in indexes)
                else:cells=(struct.unpack('<I',take(4))[0],)*4096
            self.sections.append(cells);self.raw.append(data[start:offset])
        self.effective=[];prior=None
        for cells in self.sections:
            if cells is not None:prior=cells
            self.effective.append(prior)

    def get(self,x,y,z):
        index=y//16-self.minimum
        if not 0<=index<len(self.effective) or self.effective[index] is None:
            raise nbt.FormatError('No biome palette for this vertical section')
        return self.effective[index][((x&15)<<8)|((z&15)<<4)|(y&15)]

    def edited(self,changes):
        touched={}
        for (x,y,z),value in changes.items():
            index=y//16-self.minimum
            self.get(x,y,z)
            if index not in touched:touched[index]=list(self.effective[index])
            touched[index][((x&15)<<8)|((z&15)<<4)|(y&15)]=value
        # An inherited successor must keep the old values when its predecessor
        # changes. Materialize that first successor; further inheritance is safe.
        for index in list(touched):
            if index+1<len(self.sections) and self.sections[index+1] is None and index+1 not in touched:
                touched[index+1]=self.effective[index+1]
        raw=list(self.raw)
        for index,cells in touched.items():raw[index]=encode_section(cells)
        return self.height+b''.join(raw)


def encode_section(cells):
    if len(cells)!=4096:raise ValueError('A Bedrock biome section contains 4096 cells')
    palette=list(dict.fromkeys(cells))
    if any(type(i) is not int or not 0<=i<=0xffffffff for i in palette):raise ValueError('Invalid biome ID')
    if len(palette)==1:return b'\x01'+struct.pack('<I',palette[0])
    required=(len(palette)-1).bit_length();bits=next(b for b in (1,2,3,4,5,6,8,16) if b>=required)
    lookup={value:i for i,value in enumerate(palette)};words=pack_indices([lookup[i] for i in cells],bits,width=32)
    return bytes([(bits<<1)|1])+struct.pack('<'+str(len(words))+'i',*words)+struct.pack('<I',len(palette))+struct.pack('<'+str(len(palette))+'I',*palette)
