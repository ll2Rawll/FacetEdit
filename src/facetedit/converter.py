"""Preflight and publish chunk conversion into a separate template-world copy.

Chunks are translated one section at a time and spooled to disk for review.
Source/template metadata and content hashes are rechecked before publication.
Template settings, seed, players and chunks outside the source footprint remain
the template's. Actors, scheduled ticks and unmapped block NBT block conversion.
"""
from dataclasses import dataclass
import ctypes
import os
import sys
from pathlib import Path
from importlib.resources import files
import json
import shutil
import struct
import tempfile
import zlib

from . import nbt, biomes, chunks
from .blocks import AIR
from .entities import relocate
from .formats import encode_bedrock, encode_java_section, encode_java_biomes
from .leveldb import write_database
from .model import Clipboard
from .region import decode_payload
from .registry import for_world
from .translation import TranslationReport, translate_clipboard
from .world import JavaWorld, BedrockWorld, snapshot, file_hash

JAVA_BIOMES=frozenset(json.loads(files('facetedit').joinpath('data','registries','java-1.21.4-biomes.json').read_text())['identifiers'])
BIOME_ALIASES={'mountains':'windswept_hills','snowy_tundra':'snowy_plains','giant_tree_taiga':'old_growth_pine_taiga',
    'giant_spruce_taiga':'old_growth_spruce_taiga','tall_birch_forest':'old_growth_birch_forest',
    'wooded_mountains':'windswept_forest','gravelly_mountains':'windswept_gravelly_hills','shattered_savanna':'windswept_savanna',
    'stone_shore':'stony_shore','jungle_edge':'sparse_jungle','wooded_badlands_plateau':'wooded_badlands'}


def biome_name(value, target):
    base=value.removeprefix('minecraft:')
    if isinstance(target,JavaWorld):
        value='minecraft:'+BIOME_ALIASES.get(base,base)
        if value not in JAVA_BIOMES:
            raise ValueError('No verified Java 1.21.4 biome mapping for '+value)
        return value
    reverse={v:k for k,v in BIOME_ALIASES.items()}
    value='minecraft:'+reverse.get(base,base)
    biomes.identifier(value,'Bedrock')
    return value


def check_cancel(cancelled):
    if cancelled():
        raise InterruptedError('World conversion cancelled; no output published')


def publish_directory(source, destination):
    """Publish a prepared directory atomically without replacing a racing path."""
    if sys.platform=='win32':
        os.rename(source,destination);return
    library=ctypes.CDLL(None,use_errno=True)
    if sys.platform=='darwin' and hasattr(library,'renamex_np'):
        function=library.renamex_np
        function.argtypes=[ctypes.c_char_p,ctypes.c_char_p,ctypes.c_uint];function.restype=ctypes.c_int
        result=function(os.fsencode(source),os.fsencode(destination),4)
    elif hasattr(library,'renameat2'):
        function=library.renameat2
        function.argtypes=[ctypes.c_int,ctypes.c_char_p,ctypes.c_int,ctypes.c_char_p,ctypes.c_uint];function.restype=ctypes.c_int
        result=function(-100,os.fsencode(source),-100,os.fsencode(destination),1)
    else:
        raise OSError('This platform lacks atomic exclusive directory publication')
    if result:
        error=ctypes.get_errno();raise OSError(error,os.strerror(error),str(destination))


def fingerprint(world, cancelled=lambda: False):
    signature = snapshot(world.path)
    if signature != world.signature:
        raise ValueError('World changed since opening: '+str(world.path))
    result = {}
    for name in signature:
        check_cancel(cancelled)
        result[name] = file_hash(world.path/name)
    if snapshot(world.path) != signature:
        raise ValueError('World changed while checking its files')
    return result


@dataclass
class PreparedConversion:
    source: object
    template: object
    source_hashes: dict
    template_hashes: dict
    temporary: object
    entries: list
    report: TranslationReport

    def close(self):
        self.temporary.cleanup()

    def read(self, entry):
        dimension, cx, cz, name, digest = entry
        path = Path(self.temporary.name)/name
        if file_hash(path) != digest:
            raise ValueError('Prepared conversion chunk changed on disk')
        root = nbt.loads(path.read_bytes())[1]
        records = tuple((e['key'].value, e['value'].value) for e in nbt.get(root,'records').values)
        return (dimension,cx,cz), chunks.ChunkState('replace', records)


def _audit_chunk(doc, cx, cz, report):
    state = doc.view_world.chunk_snapshot(cx,cz,doc.dimension)
    records = dict(state.records)
    entity_sections,seen=set(),set()
    def inspect_entity(tag):
        position=tuple(nbt.get(tag,axis) for axis in 'xyz')
        if any(type(v) is not int for v in position) or position[0]//16!=cx or position[2]//16!=cz:
            report.issue('Block NBT has invalid or foreign chunk coordinates',(doc.dimension,cx,cz));return
        if doc.get_entity(*position) is not None:
            if position in seen:
                report.issue('Duplicate block NBT coordinates',(doc.dimension,*position))
            seen.add(position);entity_sections.add(position[1]//16)
    if isinstance(doc.world, JavaWorld):
        for category in (b'region',b'entities'):
            if category not in records:
                continue
            root = nbt.loads(decode_payload(records[category], records.get(category+b'.mcc')))[1]
            level = root.value.get('Level',root)
            for key in ('Entities','entities','TileTicks','LiquidTicks','block_ticks','fluid_ticks'):
                payload = nbt.get(level,key)
                if isinstance(payload, nbt.ListValue) and payload.values:
                    report.issue('Source '+key+' payload requires a conversion rule', (doc.dimension,cx,cz))
            for key in ('block_entities','TileEntities'):
                payload=nbt.get(level,key)
                if payload is not None:
                    if not isinstance(payload,nbt.ListValue) or payload.values and payload.kind!=nbt.COMPOUND:
                        raise ValueError('Invalid block NBT list')
                    for entry in payload.values:
                        inspect_entity(nbt.Tag(nbt.COMPOUND,entry))
    else:
        for key in (b'digp',b'chunk:2',b'chunk:3'):
            if records.get(key):
                report.issue('Source Bedrock actor/tick records require a conversion rule', (doc.dimension,cx,cz))
        raw=records.get(b'chunk:1',b'');reader=nbt.Reader(raw,little=True)
        while reader.pos<len(raw):
            inspect_entity(reader.root()[1])
    return entity_sections


def _merge_report(total, part, base, dimension):
    total.blocks += part.blocks
    total.translated += part.translated
    total.notes.update(part.notes)
    for reason, count in part.problems.items():
        key=total.issue(reason, count=count)
        for local in part.examples.get(reason, ()):
            if len(total.examples[key]) < 3:
                total.examples[key].append((dimension,*(a+b for a,b in zip(base,local))))


def _biome_section(doc, cx, sy, cz, target, policy):
    """Exact preservation refuses mixed Bedrock voxels in a Java 4³ cell."""
    default = {'the_nether':'nether_wastes','the_end':'the_end'}.get(doc.dimension,'plains')
    if policy == 'dimension_default':
        return ['minecraft:'+default]*64
    low, high = doc.world.bounds(doc.dimension)
    result = []
    for y in range(0,16,4):
        for z in range(0,16,4):
            for x in range(0,16,4):
                px,py,pz = cx*16+x,sy*16+y,cz*16+z
                value = doc.get_biome(px, max(low,min(high,py)), pz)
                if value.startswith('numeric:'):
                    raise ValueError('Unknown numeric biome cannot cross editions: '+value)
                if policy == 'preserve' and isinstance(doc.world,BedrockWorld) and isinstance(target,JavaWorld):
                    for dy in range(4):
                        for dz in range(4):
                            for dx in range(4):
                                if doc.get_biome(px+dx,max(low,min(high,py+dy)),pz+dz) != value:
                                    raise ValueError('Mixed Bedrock biome voxels do not fit a Java 4×4×4 biome cell; choose sampling explicitly')
                result.append(biome_name(value,target))
    return result


def _convert_chunk(doc, target, source_profile, target_profile, cx, cz, policy, report, cancelled):
    sections = _audit_chunk(doc,cx,cz,report)
    low, high = target.bounds(doc.dimension)
    sections.update(doc.view_world.stored_sections(cx,cz,doc.dimension) or ())
    for mapping in (doc.edits,doc.layer_edits,doc.entity_edits):
        sections.update(y//16 for (d,x,y,z) in mapping if d==doc.dimension and x//16==cx and z//16==cz)
    converted, entities = {}, {}
    for sy in sorted(sections):
        check_cancel(cancelled)
        base = cx*16,sy*16,cz*16
        blocks, extras, block_entities = {}, {}, {}
        for y in range(16):
            for z in range(16):
                for x in range(16):
                    pos=(x,y,z); absolute=(base[0]+x,base[1]+y,base[2]+z)
                    block = doc.get(*absolute)
                    if not low <= absolute[1] <= high:
                        if not block.air or doc.get_extra_blocks(*absolute) or doc.get_entity(*absolute):
                            report.issue('Block or payload lies outside target dimension height', (doc.dimension,*absolute))
                        continue
                    blocks[pos] = block
                    extra = doc.get_extra_blocks(*absolute)
                    if extra:
                        extras[pos] = extra
                    entity = doc.get_entity(*absolute)
                    if entity is not None:
                        block_entities[pos] = relocate(entity,pos)
        if not blocks:
            continue
        clip = Clipboard((16,16,16),blocks,source_profile.edition,entities=block_entities,data_version=source_profile.data_version,extra_blocks=extras,game_version=source_profile.version)
        def neighbour(pos):
            return doc.get(*(a+b for a,b in zip(pos,base)))
        result, part = translate_clipboard(clip,target_profile,source_profile,neighbour,cancelled)
        _merge_report(report,part,base,doc.dimension)
        if result is not None:
            converted[sy] = result
            for pos,data in result.entities.items():
                absolute=tuple(a+b for a,b in zip(pos,base))
                entities[absolute] = relocate(data,absolute)
    java_sections, bedrock_sections, biome_sections = [], [], []
    heights = [low]*256
    for sy in range(low//16,high//16+1):
        check_cancel(cancelled)
        clip = converted.get(sy)
        native_biomes = isinstance(doc.world,BedrockWorld) and isinstance(target,BedrockWorld) and policy=='preserve'
        biome_values = None if native_biomes else _biome_section(doc,cx,sy,cz,target,policy)
        if isinstance(target, JavaWorld):
            section={'Y':nbt.Tag(nbt.BYTE,sy)}
            blocks=[clip.blocks.get((i&15,i>>8,(i>>4)&15),AIR) if clip else AIR for i in range(4096)]
            encode_java_section(section,blocks,target.version)
            encode_java_biomes(section,biome_values)
            java_sections.append(section)
        else:
            if native_biomes:
                # Same-version Bedrock copies retain every biome voxel, including
                # numeric IDs. Passing through a Java-size cell would lose data.
                values = [biomes.identifier(doc.get_biome(cx*16+x,sy*16+y,cz*16+z),'Bedrock')
                          for x in range(16) for z in range(16) for y in range(16)]
            else:
                palette = [biomes.identifier(name,'Bedrock') for name in biome_values]
                values = [palette[(x//4)+(z//4)*4+(y//4)*16] for x in range(16) for z in range(16) for y in range(16)]
            biome_sections.append(biomes.encode_section(values))
            if clip:
                cells = [(x,y,z) for x in range(16) for z in range(16) for y in range(16)]
                depth = max((len(v) for v in clip.extra_blocks.values()),default=0)
                layers = [[clip.blocks.get(p,AIR) for p in cells]]
                layers += [[clip.extra_blocks.get(p,())[i] if len(clip.extra_blocks.get(p,()))>i else AIR for p in cells] for i in range(depth)]
                for (x,y,z),block in clip.blocks.items():
                    if not block.air:
                        heights[z*16+x] = max(heights[z*16+x],sy*16+y+1)
                bedrock_sections.append((b'chunk:/'+struct.pack('b',sy),encode_bedrock(9,sy,layers,palette_version=target_profile.palette_version)))
    if isinstance(target,JavaWorld):
        root=nbt.compound(DataVersion=nbt.Tag(nbt.INT,target.version),xPos=nbt.Tag(nbt.INT,cx),zPos=nbt.Tag(nbt.INT,cz),yPos=nbt.Tag(nbt.INT,low//16),
            Status=nbt.Tag(nbt.STRING,'minecraft:full'),LastUpdate=nbt.Tag(nbt.LONG,0),InhabitedTime=nbt.Tag(nbt.LONG,0),isLightOn=nbt.Tag(nbt.BYTE,0),
            sections=nbt.Tag(nbt.LIST,nbt.ListValue(nbt.COMPOUND,java_sections)),
            block_entities=nbt.Tag(nbt.LIST,nbt.ListValue(nbt.COMPOUND,[nbt.loads(v)[1].value for v in entities.values()])))
        return chunks.ChunkState('replace',((b'region',b'\x02'+zlib.compress(nbt.dumps(root))),))
    # Height values are unsigned distances from the dimension minimum.
    height=struct.pack('<256H',*(h-low for h in heights))
    records=[(b'chunk:,',b'\x29'),(b'chunk:6',struct.pack('<i',2)),(b'chunk:+',height+b''.join(biome_sections)),*bedrock_sections]
    if entities:
        records.append((b'chunk:1',b''.join(nbt.dumps(nbt.loads(v)[1],little=True) for v in entities.values())))
    return chunks.ChunkState('replace',tuple(records))


def prepare_conversion(document, template, biome_policy='preserve', cancelled=lambda: False, progress=lambda text: None):
    if biome_policy not in ('preserve','sample','dimension_default'):
        raise ValueError('Unknown conversion biome policy')
    if getattr(document.world,'path',None) is None:
        raise ValueError('Open a saved Minecraft world before whole-world conversion')
    if getattr(template,'path',None) is None:
        raise ValueError('Choose a saved target template world')
    source = document.world
    source_profile,target_profile = for_world(source),for_world(template)
    if source.path.resolve() == template.path.resolve():
        raise ValueError('Choose a separate target template world')
    report=TranslationReport(source_profile.label,target_profile.label)
    report.notes.add('Template supplies world settings, seed, players and chunks outside the converted footprint. Source players, maps, structure starts, POI and auxiliary world/chunk metadata are not migrated. Target lighting is marked for recalculation.')
    if biome_policy == 'dimension_default':
        report.notes.add('Biome policy: replace source biomes with plains / Nether wastes / End defaults.')
    elif biome_policy == 'sample':
        report.notes.add('Biome policy: sample the minimum corner of each 4×4×4 cell; finer biome detail may change.')
    progress('Checking source and template fingerprints…')
    before, target_before = fingerprint(source,cancelled),fingerprint(template,cancelled)
    temporary=tempfile.TemporaryDirectory(prefix='facetedit-conversion-')
    plan=PreparedConversion(source,template,before,target_before,temporary,[],report)
    try:
        doc=document.snapshot()
        inventory=[]
        for dimension in source.dimensions:
            positions=sorted(doc.view_world.chunk_positions(dimension),key=lambda p:(p[0]//32,p[1]//32,p))
            if not positions:
                continue
            if dimension not in template.dimensions:
                report.issue('Target template has no dimension '+dimension,count=len(positions));continue
            inventory.extend((dimension,cx,cz) for cx,cz in positions)
        if len(inventory)>chunks.MAX_CHUNK_COUNT:
            raise ValueError('Conversion exceeds 65,536 chunks')
        for index,(dimension,cx,cz) in enumerate(inventory):
            check_cancel(cancelled)
            progress(f'Translating chunk {index+1:,} / {len(inventory):,} · {dimension} · {cx}, {cz}')
            doc.dimension=dimension
            try:
                state=_convert_chunk(doc,template,source_profile,target_profile,cx,cz,biome_policy,report,cancelled)
            except (ValueError, KeyError, IndexError) as exc:
                report.issue(str(exc),(dimension,cx,cz));continue
            root=nbt.compound(records=nbt.Tag(nbt.LIST,nbt.ListValue(nbt.COMPOUND,[{'key':nbt.Tag(nbt.BYTE_ARRAY,k),'value':nbt.Tag(nbt.BYTE_ARRAY,v)} for k,v in state.records])))
            name=f'{index}.nbt'; path=Path(temporary.name)/name;path.write_bytes(nbt.dumps(root))
            plan.entries.append((dimension,cx,cz,name,file_hash(path)))
        if fingerprint(source,cancelled)!=before or fingerprint(template,cancelled)!=target_before:
            raise ValueError('World content changed during conversion preflight')
        return plan
    except BaseException:
        plan.close();raise


def publish_conversion(plan, destination, cancelled=lambda: False, progress=lambda text: None):
    if not plan.report.ok:
        raise ValueError('Resolve blocked conversion data before publishing')
    destination=Path(destination).resolve()
    if destination.exists():
        raise FileExistsError('Conversion destination must be a new folder')
    for world in (plan.source,plan.template):
        if destination.is_relative_to(world.path.resolve()):
            raise ValueError('Conversion destination must be outside the source and template')
    if fingerprint(plan.source,cancelled)!=plan.source_hashes or fingerprint(plan.template,cancelled)!=plan.template_hashes:
        raise ValueError('Source or template changed since preflight')
    stage=Path(tempfile.mkdtemp(prefix='.facetedit-convert-',dir=destination.parent))
    try:
        progress('Copying the target template…')
        def copy_file(source,target):
            check_cancel(cancelled)
            return shutil.copy2(source,target)
        shutil.copytree(plan.template.path,stage,dirs_exist_ok=True,copy_function=copy_file)
        if {name:file_hash(stage/name) for name in plan.template_hashes} != plan.template_hashes:
            raise ValueError('Template changed during the output snapshot')
        template=plan.template
        batch={}
        for index,entry in enumerate(plan.entries):
            check_cancel(cancelled)
            key,state=plan.read(entry);batch[key]=state
            progress(f'Writing chunk {index+1:,} / {len(plan.entries):,}')
            if len(batch)>=64 or index==len(plan.entries)-1:
                if isinstance(template,JavaWorld):
                    chunks.write_java_chunks(template,stage,batch)
                else:
                    template=chunks.bedrock_with_chunks(template,batch)
                    template.inventory_cache=None;template.chunk_record_index=None
                batch.clear()
        if isinstance(template,BedrockWorld):
            from .leveldb import LIMIT
            if sum(len(k)+len(v) for k,v in template.values.items()) > LIMIT:
                raise ValueError('Converted Bedrock database exceeds the current 256 MiB adapter limit')
            shutil.rmtree(stage/'db')
            write_database(stage/'db',template.values,cancelled)
        check_cancel(cancelled)
        if fingerprint(plan.source,cancelled)!=plan.source_hashes or fingerprint(plan.template,cancelled)!=plan.template_hashes:
            raise ValueError('World changed before output publication')
        if destination.exists():
            raise FileExistsError('Conversion destination appeared while writing')
        check_cancel(cancelled)
        publish_directory(stage,destination)
        progress('Converted world copy saved')
        return destination
    finally:
        if stage.exists():
            shutil.rmtree(stage)
