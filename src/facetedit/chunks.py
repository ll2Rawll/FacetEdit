"""Opaque chunk snapshots and edition-specific copy-on-write chunk adapters."""

from dataclasses import dataclass
import copy
from pathlib import Path
import struct
import zlib

from . import nbt
from .blocks import AIR
from .formats import encode_bedrock
from .region import Region,decode_payload

MAX_PAYLOAD = 32*1024*1024
MAX_CHUNK_COUNT = 65_536


@dataclass(frozen=True)
class ChunkState:
    kind: str
    records: tuple = ()

    def __post_init__(self):
        if self.kind not in ('source','deleted','replace'):
            raise ValueError('Invalid chunk state')
        if self.kind!='replace' and self.records:raise ValueError('Unexpected chunk payload')
        if any(not isinstance(key,bytes) or not isinstance(value,bytes) for key,value in self.records):
            raise ValueError('Chunk records must contain bytes')
        if len(dict(self.records))!=len(self.records):raise ValueError('Duplicate chunk record')
        if self.size>MAX_PAYLOAD:raise ValueError('Chunk snapshot exceeds 32 MiB')

    @property
    def size(self):return sum(len(k)+len(v) for k,v in self.records)


SOURCE = ChunkState('source')
DELETED = ChunkState('deleted')


def java_chunk_snapshot(world,cx,cz,dimension):
    records = []
    base = world.dimension_paths[dimension].parent
    for category in ('region','entities','poi'):
        relative=base/category/f'r.{cx//32}.{cz//32}.mca'
        path = world.path/relative
        if not path.exists():continue
        region = world.regions.obtain(str(relative),lambda:Region.read(path))
        payload = region.chunks.get(Region.index(cx,cz))
        if payload is None:continue
        key = category.encode()
        records.append((key,payload))
        if payload[0]&128:
            file = path.parent/f'c.{cx}.{cz}.mcc'
            if file.is_symlink() or file.stat().st_size>MAX_PAYLOAD:raise ValueError('External chunk exceeds snapshot limit')
            records.append((key+b'.mcc',file.read_bytes()))
    return ChunkState('replace',tuple(records)) if any(k==b'region' for k,_ in records) else DELETED


def empty_java(world,cx,cz,dimension):
    minimum,maximum = world.bounds(dimension)
    sections = []
    for sy in range(minimum//16,maximum//16+1):
        section = {'Y':nbt.Tag(nbt.BYTE,sy)}
        palette = nbt.Tag(nbt.LIST,nbt.ListValue(nbt.COMPOUND,[{'Name':nbt.Tag(nbt.STRING,'minecraft:air')}]))
        if world.version>=2834:section['block_states'] = nbt.compound(palette=palette)
        else:section.update(Palette=palette,BlockStates=nbt.Tag(nbt.LONG_ARRAY,[0]*256))
        if world.version>=2834:
            biome = {'the_nether':'nether_wastes','the_end':'the_end'}.get(dimension,'plains')
            section['biomes'] = nbt.compound(palette=nbt.Tag(nbt.LIST,nbt.ListValue(nbt.STRING,['minecraft:'+biome])))
        sections.append(section)
    level = nbt.compound(xPos=nbt.Tag(nbt.INT,cx),zPos=nbt.Tag(nbt.INT,cz),
        LastUpdate=nbt.Tag(nbt.LONG,0),InhabitedTime=nbt.Tag(nbt.LONG,0),
        Status=nbt.Tag(nbt.STRING,'minecraft:full' if world.version>=2834 else 'full'),
        isLightOn=nbt.Tag(nbt.BYTE,0))
    modern = world.version>=2834
    level.value['sections' if modern else 'Sections'] = nbt.Tag(nbt.LIST,nbt.ListValue(nbt.COMPOUND,sections))
    level.value['block_entities' if modern else 'TileEntities'] = nbt.Tag(nbt.LIST,nbt.ListValue(nbt.COMPOUND,[]))
    if modern:
        level.value['yPos'] = nbt.Tag(nbt.INT,minimum//16)
        root = level
    else:
        level.value['Entities'] = nbt.Tag(nbt.LIST,nbt.ListValue(nbt.COMPOUND,[]))
        # Older chunks use 2D biome IDs; plains/Nether/End have stable legacy IDs.
        biome = {'the_nether':8,'the_end':9}.get(dimension,1)
        level.value['Biomes'] = nbt.Tag(nbt.INT_ARRAY,[biome]*1024 if world.version>=2203 else [biome]*256)
        root = nbt.compound(Level=level)
    root.value['DataVersion'] = nbt.Tag(nbt.INT,world.version)
    return ChunkState('replace',((b'region',b'\x02'+zlib.compress(nbt.dumps(root))),))


def validate_java_state(state,cx,cz):
    if state.kind!='replace':return
    records = dict(state.records)
    allowed = {b'region',b'entities',b'poi',b'region.mcc',b'entities.mcc',b'poi.mcc'}
    if not records.keys()<=allowed or b'region' not in records:raise ValueError('Invalid Java chunk snapshot')
    for kind in (b'region',b'entities',b'poi'):
        if kind not in records:
            if kind+b'.mcc' in records:raise ValueError('Orphan external chunk payload')
            continue
        payload = records[kind]
        if not payload or bool(payload[0]&128)!=(kind+b'.mcc' in records):
            raise ValueError('External chunk sidecar mismatch')
    _,root = nbt.loads(decode_payload(records[b'region'],records.get(b'region.mcc')))
    level = root.value.get('Level',root)
    if (nbt.get(level,'xPos'),nbt.get(level,'zPos'))!=(cx,cz):
        raise ValueError('Imported chunk coordinates disagree with the destination')
    version = nbt.get(root,'DataVersion',0)
    if not 1451<=version<=4189:raise ValueError('Imported chunk DataVersion is unsupported')


def write_java_chunks(world,stage,overrides):
    regions = {}
    for (dimension,cx,cz),state in overrides.items():
        records = dict(state.records)
        base = world.dimension_paths[dimension].parent
        for category in ('region','entities','poi'):
            path = Path(stage)/base/category/f'r.{cx//32}.{cz//32}.mca'
            if path not in regions:
                regions[path] = Region.read(path) if path.exists() else Region(path=path)
            region = regions[path]
            key = category.encode()
            if state.kind=='deleted' or key not in records:region.delete(cx,cz)
            else:region.put_payload(cx,cz,records[key],records.get(key+b'.mcc'))
    for path,region in regions.items():region.write(path)


def bedrock_key(key):
    """Return (dimension ID, X, Z, suffix) for the documented chunk-key lengths."""
    if len(key) in (9,10):cx,cz = struct.unpack_from('<ii',key);did=0;start=8
    elif len(key) in (13,14):cx,cz,did = struct.unpack_from('<iii',key);start=12
    else:return None
    if did not in (0,1,2) or abs(cx)>1_875_000 or abs(cz)>1_875_000:return None
    suffix = key[start:]
    if len(suffix)==2 and suffix[0]!=47:return None
    return did,cx,cz,suffix


def actor_ids(value):
    if len(value)%8:raise ValueError('Malformed Bedrock actor index')
    return {value[i:i+8] for i in range(0,len(value),8)}


def bedrock_chunk_snapshot(world,cx,cz,dimension):
    prefix = world.prefix(cx,cz,dimension)
    did = world.dimension_ids[dimension]
    world.chunk_positions(dimension)  # Builds the shared record index once.
    records = [(b'chunk:'+key[len(prefix):],world.values[key]) for key in world.chunk_record_index.get((did,cx,cz),())]
    if not records:return DELETED
    index = world.values.get(b'digp'+prefix)
    if index is not None:
        records.append((b'digp',index))
        for uid in sorted(actor_ids(index)):
            data = world.values.get(b'actorprefix'+uid)
            if data is None:raise ValueError('Bedrock actor index refers to missing actor data')
            records.append((b'actor:'+uid,data))
    return ChunkState('replace',tuple(records))


def validate_bedrock_state(state):
    if state.kind!='replace':return
    records = dict(state.records)
    actors = actor_ids(records.get(b'digp',b''))
    for key,value in records.items():
        if key.startswith(b'chunk:'):
            suffix = key[6:]
            if len(suffix)!=1 and not (len(suffix)==2 and suffix[0]==47):raise ValueError('Invalid Bedrock chunk record')
        elif key==b'digp':pass
        elif key.startswith(b'actor:') and len(key)==14:
            if key[6:] not in actors:raise ValueError('Unindexed actor in imported chunk')
        else:raise ValueError('Unknown Bedrock snapshot record')
    if not any(k in records for k in (b'chunk:,',b'chunk:v')):
        raise ValueError('Imported Bedrock chunk needs a version record')
    if any(b'actor:'+uid not in records for uid in actors):raise ValueError('Missing imported actor data')


def bedrock_with_chunks(world,overrides):
    values = dict(world.values)
    targets = {(world.dimension_ids[d],cx,cz):(d,cx,cz) for d,cx,cz in overrides}
    old_actors = set()
    for key in list(values):
        parsed = bedrock_key(key)
        if parsed and parsed[:3] in targets:del values[key]
    for dimension,cx,cz in overrides:
        old = values.pop(b'digp'+world.prefix(cx,cz,dimension),b'')
        old_actors.update(actor_ids(old))
    retained = set()
    for key,value in values.items():
        if key.startswith(b'digp') and len(key) in (12,16):retained.update(actor_ids(value))
    for uid in old_actors-retained:values.pop(b'actorprefix'+uid,None)
    for (dimension,cx,cz),state in overrides.items():
        if state.kind=='deleted':continue
        validate_bedrock_state(state)
        prefix = world.prefix(cx,cz,dimension)
        for key,value in state.records:
            if key.startswith(b'chunk:'):target = prefix+key[6:]
            elif key==b'digp':target = b'digp'+prefix
            else:
                target = b'actorprefix'+key[6:]
                if target in values and values[target]!=value:
                    raise ValueError('Imported actor ID collides with a retained actor')
            values[target] = value
    clone = copy.copy(world)
    clone.values = values
    return clone


def empty_bedrock(world,cx,cz,dimension):
    # Biome encodings vary by engine version. Reuse a same-dimension template
    # without interpreting palette IDs; the heightmap is reset for empty terrain.
    if not hasattr(world,'empty_templates'):world.empty_templates = {}
    if dimension in world.empty_templates:return world.empty_templates[dimension]
    template = None
    for tx,tz in sorted(world.chunk_positions(dimension)):
        prefix = world.prefix(tx,tz,dimension)
        if any(prefix+suffix in world.values for suffix in (b'+',b'-')):
            template = prefix;break
    if template is None:raise ValueError('An existing chunk with biome data is required to create empty Bedrock chunks')
    if world.game_version is None:raise ValueError('Empty Bedrock chunks require known lastOpenedWithVersion metadata')
    version_key = b',' if template+b',' in world.values else b'v'
    if template+version_key not in world.values:raise ValueError('Bedrock biome template has no chunk version record')
    records = [(b'chunk:'+version_key,world.values[template+version_key]),(b'chunk:6',struct.pack('<i',2))]
    for suffix in (b'+',b'-'):
        if template+suffix in world.values:
            data = world.values[template+suffix]
            if len(data)<512:raise ValueError('Truncated Bedrock biome/height template')
            records.append((b'chunk:'+suffix,b'\x00'*512+data[512:]))
    minimum,maximum = world.bounds(dimension)
    storage = 8 if world.game_version is not None and world.game_version<(1,18,0) else 9
    for sy in range(minimum//16,maximum//16+1):
        records.append((b'chunk:/'+struct.pack('b',sy),encode_bedrock(storage,sy,[[AIR]*4096])))
    result = ChunkState('replace',tuple(records))
    world.empty_templates[dimension] = result
    return result
