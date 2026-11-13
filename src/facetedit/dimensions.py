"""Resolve Java dimension heights from level metadata and enabled datapacks."""
import json,zipfile
from pathlib import Path
from . import nbt
from .blocks import Block

LIMIT=1024*1024


class Datapacks:
    def __init__(self,path,data):
        directory=Path(path)/'datapacks';configured=nbt.get(data,'DataPacks',{})
        enabled=configured.get('Enabled') if isinstance(configured,dict) else None
        if enabled is not None:
            names=[name[5:] for name in enabled.value.values if isinstance(name,str) and name.startswith('file/')]
            if any(Path(name).name!=name or name in ('.','..') for name in names):raise ValueError('Invalid enabled datapack filename')
            self.paths=[directory/name for name in names]
        else:self.paths=sorted(directory.iterdir()) if directory.is_dir() else []

    def read(self,category,location):
        resource=Block(location).name;namespace,path=resource.split(':',1)
        relative=f'data/{namespace}/{category}/{path}.json'
        for pack in reversed(self.paths):
            if pack.is_symlink():raise ValueError('Symbolic-link datapacks are not supported')
            if pack.is_dir():
                file=pack/relative
                if not file.is_file():continue
                if file.stat().st_size>LIMIT:raise ValueError('Dimension definition exceeds 1 MiB')
                raw=file.read_bytes()
            elif pack.is_file() and pack.suffix.lower()=='.zip':
                with zipfile.ZipFile(pack) as archive:
                    try:info=archive.getinfo(relative)
                    except KeyError:continue
                    if info.file_size>LIMIT:raise ValueError('Dimension definition exceeds 1 MiB')
                    raw=archive.read(info)
            else:continue
            result=json.loads(raw)
            if not isinstance(result,dict):raise ValueError('Dimension definition must be an object')
            return result
        return None


def _plain(tag):
    if tag.kind==nbt.COMPOUND:return {key:_plain(value) for key,value in tag.value.items()}
    if tag.kind==nbt.LIST:return list(tag.value.values)
    return tag.value


def java_bounds(path,data,version,dimension_names):
    default=(-64,319) if version>=2834 else (0,255)
    vanilla={'minecraft:overworld':default,'minecraft:overworld_caves':default,'minecraft:the_nether':(0,255),'minecraft:the_end':(0,255)}
    registry=nbt.get(data,'WorldGenSettings',{})
    registry=_plain(registry['dimensions']) if 'dimensions' in registry else {}
    packs=Datapacks(path,data);result={}
    for dimension in dimension_names:
        location='minecraft:'+dimension if dimension in ('overworld','the_nether','the_end') else dimension.replace('/',':',1)
        definition=registry.get(location) or packs.read('dimension',location) or {}
        kind=definition.get('type',location)
        if isinstance(kind,str):
            value=packs.read('dimension_type',kind)
            if value is None:
                result[dimension]=vanilla.get(kind)
                continue
        elif isinstance(kind,dict):value=kind
        else:raise ValueError('Invalid dimension type for '+dimension)
        if 'height' not in value and 'min_y' not in value and version<2709:
            result[dimension]=(0,255);continue
        minimum,height=value.get('min_y'),value.get('height')
        if type(minimum) is not int or type(height) is not int or minimum%16 or height%16 or not -2032<=minimum<=2031 or not 16<=height<=4064 or minimum+height>2032:
            raise ValueError('Invalid dimension height for '+dimension)
        result[dimension]=(minimum,minimum+height-1)
    return result
