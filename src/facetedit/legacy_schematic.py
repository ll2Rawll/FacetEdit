"""Independent Alpha .schematic interchange for numeric Java Anvil worlds."""
from pathlib import Path
from . import nbt,legacy
from .model import Clipboard,MAX_OPERATION
from .entities import relocate,validate_local
from .structures import atomic_write


def load_legacy_schematic(path,data_version=None):
    path=Path(path)
    if path.stat().st_size>nbt.MAX_BYTES:raise ValueError('Schematic exceeds 64 MiB')
    raw=path.read_bytes();_,root=nbt.loads(raw,compressed=raw[:2]==b'\x1f\x8b')
    if nbt.get(root,'Materials','Alpha')!='Alpha':raise ValueError('Only Alpha numeric schematics are supported')
    size=tuple(nbt.get(root,key,0) for key in ('Width','Height','Length'))
    if any(type(n) is not int or not 0<n<=32767 for n in size):raise ValueError('Invalid legacy schematic dimensions')
    width,height,depth=size;count=width*height*depth
    if count>MAX_OPERATION:raise ValueError('Schematic exceeds 65,536 blocks')
    low=nbt.get(root,'Blocks');data=nbt.get(root,'Data')
    if not isinstance(low,bytes) or not isinstance(data,bytes) or len(low)!=count or len(data)!=count or any(v>15 for v in data):
        raise ValueError('Invalid legacy schematic Blocks/Data arrays')
    high=legacy.nibbles(root.value['AddBlocks'].value,count) if 'AddBlocks' in root.value else [0]*count
    for key in ('Entities','TileTicks'):
        values=nbt.get(root,key)
        if values and values.values:raise ValueError('Legacy schematic '+key+' interchange is not implemented')
    if 'Add' in root.value or 'SchematicaMapping' in root.value:
        raise ValueError('Alternative modded schematic ID mappings are not supported')
    blocks={}
    for index in range(count):
        y,horizontal=divmod(index,width*depth);z,x=divmod(horizontal,width)
        blocks[x,y,z]=legacy.block(low[index]|(high[index]<<8),data[index])
    entities={}
    for entry in nbt.get(root,'TileEntities',nbt.ListValue(nbt.COMPOUND,[])).values:
        tag=nbt.Tag(nbt.COMPOUND,entry);pos=tuple(nbt.get(tag,axis) for axis in 'xyz')
        validate_local(pos,size,blocks,entities);entities[pos]=relocate(nbt.dumps(tag),pos)
    offset=tuple(nbt.get(root,'WEOffset'+axis,0) for axis in 'XYZ')
    if any(type(v) is not int or abs(v)>30_000_000 for v in offset):raise ValueError('Invalid schematic offset')
    version=nbt.get(root,'DataVersion',1343 if data_version is None else data_version)
    if type(version) is not int or not 0<=version<1451:raise ValueError('Legacy schematic requires a pre-flattening Java DataVersion')
    return Clipboard(size,blocks,'Java',offset,entities,version)


def save_legacy_schematic(clipboard,path):
    if clipboard.edition!='Java' or type(clipboard.data_version) is not int or not 0<=clipboard.data_version<1451:
        raise ValueError('Legacy schematic export requires numeric Java blocks; modern version translation is not implemented')
    size=clipboard.size;width,height,depth=size;count=width*height*depth
    if any(not 0<n<=32767 for n in size) or count>MAX_OPERATION or len(clipboard.blocks)!=count:raise ValueError('Legacy schematics require a bounded rectangular selection without gaps')
    if clipboard.extra_blocks:raise ValueError('Legacy schematics cannot store extra block layers')
    values=[legacy.identifier(clipboard.blocks[x,y,z]) for y in range(height) for z in range(depth) for x in range(width)]
    root=nbt.compound(Materials=nbt.Tag(nbt.STRING,'Alpha'),DataVersion=nbt.Tag(nbt.INT,clipboard.data_version),
        Blocks=nbt.Tag(nbt.BYTE_ARRAY,bytes(number&255 for number,_ in values)),
        Data=nbt.Tag(nbt.BYTE_ARRAY,bytes(data for _,data in values)),
        Entities=nbt.Tag(nbt.LIST,nbt.ListValue(nbt.COMPOUND,[])),
        TileEntities=nbt.Tag(nbt.LIST,nbt.ListValue(nbt.COMPOUND,[])))
    for key,value in zip(('Width','Height','Length'),size):root.value[key]=nbt.Tag(nbt.SHORT,value)
    for axis,value in zip('XYZ',clipboard.offset):root.value['WEOffset'+axis]=nbt.Tag(nbt.INT,value)
    if any(number>255 for number,_ in values):root.value['AddBlocks']=nbt.Tag(nbt.BYTE_ARRAY,legacy.pack_nibbles([number>>8 for number,_ in values]))
    for position,data in clipboard.entities.items():
        validate_local(position,size,clipboard.blocks,{})
        root.value['TileEntities'].value.values.append(nbt.loads(relocate(data,position))[1].value)
    atomic_write(path,nbt.dumps(root,'Schematic',compressed=True))
