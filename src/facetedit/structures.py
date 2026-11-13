"""Java structure interchange and FacetEdit's versioned project file."""

import json
import base64
import os
from pathlib import Path
import tempfile

from . import nbt
from .blocks import Block
from .formats import java_block, java_entry, bedrock_block, bedrock_entry
from .model import Clipboard, Document, MAX_OPERATION,Selection,SelectionGroup
from .chunks import ChunkState,MAX_PAYLOAD,MAX_CHUNK_COUNT
from .world import SampleWorld, open_world
from .entities import relocate, validate_local


def atomic_write(path, data):
    path = Path(path)
    handle, temporary = tempfile.mkstemp(prefix=".facetedit-", dir=path.parent)
    try:
        with os.fdopen(handle, "wb") as file:
            file.write(data)
            file.flush()
            os.fsync(file.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def export_structure(clipboard, path):
    if any(clipboard.offset):
        raise ValueError("This format cannot preserve schematic offsets; export as .schem")
    width,height,depth = clipboard.size
    if width*height*depth>MAX_OPERATION:
        raise ValueError('Structure bounding volume exceeds 65,536 blocks; export closer regions separately')
    if clipboard.edition == "Bedrock":
        return export_mcstructure(clipboard, path)
    if clipboard.data_version is None or clipboard.data_version<1451:raise ValueError('Export numeric Java blocks as .schematic')
    if clipboard.extra_blocks:raise ValueError('Java structures cannot store Bedrock extra layers')
    palette = list(dict.fromkeys(clipboard.blocks.values()))
    indexes = {block: i for i, block in enumerate(palette)}
    blocks = [{"pos": nbt.Tag(nbt.LIST, nbt.ListValue(nbt.INT, list(pos))),
               "state": nbt.Tag(nbt.INT, indexes[block])} for pos, block in sorted(clipboard.blocks.items())]
    for entry,position in zip(blocks,sorted(clipboard.blocks)):
        if position in clipboard.entities:
            entry["nbt"] = nbt.loads(relocate(clipboard.entities[position],position))[1]
    root = nbt.compound(
        DataVersion=nbt.Tag(nbt.INT, clipboard.data_version),
        size=nbt.Tag(nbt.LIST, nbt.ListValue(nbt.INT, list(clipboard.size))),
        palette=nbt.Tag(nbt.LIST, nbt.ListValue(nbt.COMPOUND, [java_entry(b) for b in palette])),
        blocks=nbt.Tag(nbt.LIST, nbt.ListValue(nbt.COMPOUND, blocks)),
        entities=nbt.Tag(nbt.LIST, nbt.ListValue(nbt.COMPOUND, [])),
    )
    atomic_write(path, nbt.dumps(root, compressed=True))


def import_structure(path):
    path = Path(path)
    if path.stat().st_size > 64 * 1024 * 1024:
        raise ValueError("Structure file exceeds 64 MiB")
    raw = path.read_bytes()
    _, root = nbt.loads(raw, compressed=raw[:2] == b"\x1f\x8b")
    size = nbt.get(root, "size")
    palette_tag = nbt.get(root, "palette")
    blocks_tag = nbt.get(root, "blocks")
    if size is None or palette_tag is None or blocks_tag is None:
        raise ValueError("Expected a Java structure NBT with size, palette and blocks")
    dims = tuple(size.values)
    if len(dims) != 3 or any(type(n) is not int or n <= 0 for n in dims):
        raise ValueError("Invalid structure dimensions")
    if dims[0] * dims[1] * dims[2] > MAX_OPERATION or len(blocks_tag.values) > MAX_OPERATION:
        raise ValueError(f"Structure exceeds {MAX_OPERATION:,} blocks")
    entities = nbt.get(root, "entities")
    if entities and entities.values:
        raise ValueError("Entity-bearing structures are not supported yet; export a blocks-only structure")
    version = nbt.get(root,"DataVersion")
    if type(version) is not int or not 1451 <= version <= 4189:
        raise ValueError("Structure needs a supported Java DataVersion")
    palette = [java_block(e) for e in palette_tag.values]
    blocks,block_entities = {},{}
    for entry in blocks_tag.values:
        pos = tuple(entry["pos"].value.values)
        state = entry["state"].value
        if len(pos) != 3 or any(type(v) is not int or not 0 <= v < dims[i] for i, v in enumerate(pos)):
            raise ValueError("Structure block lies outside its bounds")
        if pos in blocks or type(state) is not int or not 0 <= state < len(palette):
            raise ValueError("Invalid or duplicate structure block")
        blocks[pos] = palette[state]
        if "nbt" in entry:
            validate_local(pos,dims,blocks,block_entities)
            block_entities[pos] = relocate(nbt.dumps(entry["nbt"]),pos)
    return Clipboard(dims, blocks,entities=block_entities,data_version=version)


def export_mcstructure(clipboard, path):
    if any(clipboard.offset):
        raise ValueError("mcstructure cannot preserve schematic offsets")
    width, height, depth = clipboard.size
    volume = width * height * depth
    if volume > MAX_OPERATION:
        raise ValueError("Structure exceeds the block limit")
    if any(len(layers)>1 for layers in clipboard.extra_blocks.values()):
        raise ValueError('mcstructure supports two layers; this selection has more')
    from .registry import for_clipboard
    try:
        palette_version = for_clipboard(clipboard).palette_version or 17959425
    except ValueError:
        palette_version = 17959425
    palette = list(dict.fromkeys((*clipboard.blocks.values(),*(b for layers in clipboard.extra_blocks.values() for b in layers))))
    lookup = {block: i for i, block in enumerate(palette)}
    indices = [-1] * volume
    secondary=[-1]*volume
    for (x, y, z), block in clipboard.blocks.items():
        indices[x * height * depth + y * depth + z] = lookup[block]
    for (x,y,z),layers in clipboard.extra_blocks.items():
        if (x,y,z) not in clipboard.blocks:raise ValueError('Extra layer lies outside the selected block mask')
        if layers:secondary[x*height*depth+y*depth+z]=lookup[layers[0]]
    root = nbt.compound(
        format_version=nbt.Tag(nbt.INT, 1),
        size=nbt.Tag(nbt.LIST, nbt.ListValue(nbt.INT, list(clipboard.size))),
        structure_world_origin=nbt.Tag(nbt.LIST, nbt.ListValue(nbt.INT, [0, 0, 0])),
        structure=nbt.compound(
            block_indices=nbt.Tag(nbt.LIST, nbt.ListValue(nbt.LIST, [nbt.ListValue(nbt.INT, indices), nbt.ListValue(nbt.INT,secondary)])),
            entities=nbt.Tag(nbt.LIST, nbt.ListValue(nbt.COMPOUND, [])),
            palette=nbt.compound(default=nbt.compound(
                block_palette=nbt.Tag(nbt.LIST, nbt.ListValue(nbt.COMPOUND, [bedrock_entry(b, palette_version).value for b in palette])),
                block_position_data=nbt.Tag(nbt.COMPOUND,{
                    str(x*height*depth+y*depth+z): nbt.compound(block_entity_data=nbt.loads(relocate(data,(x,y,z)))[1])
                    for (x,y,z),data in clipboard.entities.items()
                }),
            )),
        ),
    )
    atomic_write(path, nbt.dumps(root, little=True))


def import_mcstructure(path):
    path = Path(path)
    if path.stat().st_size > 64 * 1024 * 1024:
        raise ValueError("Structure file exceeds 64 MiB")
    raw = path.read_bytes()
    _, root = nbt.loads(raw, little=True, compressed=raw[:2] == b"\x1f\x8b")
    if nbt.get(root, "format_version") != 1:
        raise ValueError("Unsupported mcstructure format version")
    size_tag = nbt.get(root, "size")
    dims = tuple(size_tag.values) if size_tag else ()
    if len(dims) != 3 or any(type(n) is not int or n <= 0 for n in dims):
        raise ValueError("Invalid mcstructure dimensions")
    width, height, depth = dims
    volume = width * height * depth
    if volume > MAX_OPERATION:
        raise ValueError("Structure exceeds the block limit")
    structure = root.value["structure"]
    palette_root = structure.value["palette"].value["default"]
    if nbt.get(structure, "entities").values:
        raise ValueError("Entity-bearing mcstructures are not supported yet")
    layers = nbt.get(structure, "block_indices").values
    if len(layers) != 2 or any(len(layer.values) != volume for layer in layers):
        raise ValueError("Invalid mcstructure block index array")
    palette = [bedrock_block(nbt.Tag(nbt.COMPOUND, e)) for e in nbt.get(palette_root, "block_palette").values]
    blocks = {}
    extra={}
    for index, state in enumerate(layers[0].values):
        if state == -1:
            continue
        if type(state) is not int or not 0 <= state < len(palette):
            raise ValueError("mcstructure palette index is invalid")
        x, rem = divmod(index, height * depth)
        y, z = divmod(rem, depth)
        blocks[(x, y, z)] = palette[state]
    for index,state in enumerate(layers[1].values):
        if state==-1:continue
        if type(state) is not int or not 0<=state<len(palette):raise ValueError('Invalid secondary palette index')
        x,rem=divmod(index,height*depth);y,z=divmod(rem,depth)
        if (x,y,z) not in blocks:raise ValueError('Secondary layer has no selected primary block')
        if not palette[state].air:extra[x,y,z]=(palette[state],)
    entities = {}
    for index,entry in nbt.get(palette_root,"block_position_data",{}).items():
        if not index.isdecimal() or not 0 <= int(index) < volume:
            raise ValueError("Invalid block-position-data index")
        if entry.kind != nbt.COMPOUND or set(entry.value) != {"block_entity_data"}:
            raise ValueError("Only block-entity data is supported; scheduled-tick metadata is not implemented")
        x,rem = divmod(int(index),height*depth)
        y,z = divmod(rem,depth)
        pos = (x,y,z)
        validate_local(pos,dims,blocks,entities)
        entities[pos] = relocate(nbt.dumps(entry.value["block_entity_data"]),pos)
    return Clipboard(dims, blocks, "Bedrock",entities=entities,data_version=None,extra_blocks=extra)


MAX_PROJECT_BYTES = 64*1024*1024


def project_data(document):
    world = document.world
    data = {
        "format": "facetedit-project", "version": 4,
        "source": str(world.path) if world.path else None,
        "source_signature": getattr(world, "signature", None),
        "sample_generator": world.generator if world.path is None else None,
        "dimension": document.dimension,
        "edits": [[dimension, x, y, z, {"name": block.name, "properties": list(block.properties), "state_types": list(block.state_types)}] for (dimension, x, y, z), block in sorted(document.edits.items())],
        "block_entities": [[*key,base64.b64encode(value).decode("ascii") if value is not None else None] for key,value in sorted(document.entity_edits.items())],
        "biomes": [[*key,value] for key,value in sorted(document.biome_edits.items())],
        "layers": [[*key,[{"name":b.name,"properties":b.properties,"state_types":b.state_types} for b in value]] for key,value in sorted(document.layer_edits.items())],
        "chunks": [[*key,state.kind,[[base64.b64encode(k).decode('ascii'),base64.b64encode(v).decode('ascii')] for k,v in state.records]] for key,state in sorted(document.chunk_edits.items())],
        "selection": [[list(box.a),list(box.b)] for box in document.selection.boxes] if document.selection else [],
    }
    return data


def write_project_data(data,path):
    raw = json.dumps(data,ensure_ascii=False,separators=(',',':')).encode('utf-8')
    if len(raw)>MAX_PROJECT_BYTES:raise ValueError('Project exceeds 64 MiB; export an edited world copy instead')
    atomic_write(path,raw)


def save_project(document,path):write_project_data(project_data(document),path)


def load_project(path):
    path = Path(path)
    if path.stat().st_size > MAX_PROJECT_BYTES:
        raise ValueError("Project file exceeds 64 MiB")
    data = json.loads(path.read_text("utf-8"))
    if data.get("format") not in ("facetedit-project","luma-project") or data.get("version") not in (1,2,3,4):
        raise ValueError("Unsupported FacetEdit project format")
    if data.get("source") is not None:
        world = open_world(data["source"])
        expected = {key: list(value) for key, value in world.signature.items()}
        if expected != data.get("source_signature"):
            raise ValueError("This project's source world has changed; its edits cannot safely be reapplied")
    else:
        if data.get("sample_generator") not in (1,2):
            raise ValueError("Unknown sample world generator")
        world = SampleWorld(data["sample_generator"])
    document = Document(world)
    chunk_rows = data.get('chunks',[])
    if not isinstance(chunk_rows,list) or len(chunk_rows)>MAX_CHUNK_COUNT:raise ValueError('Too many project chunks')
    total = 0
    for row in chunk_rows:
        if not isinstance(row,list) or len(row)!=5:raise ValueError('Invalid project chunk')
        dim,cx,cz,kind,records = row
        if dim not in world.dimensions or any(type(v) is not int or abs(v)>1_875_000 for v in (cx,cz)):
            raise ValueError('Invalid project chunk coordinate')
        if kind not in ('deleted','replace') or not isinstance(records,list):raise ValueError('Invalid chunk state')
        key = (dim,cx,cz)
        if key in document.chunk_edits:raise ValueError('Duplicate project chunk')
        state = ChunkState(kind,tuple((base64.b64decode(k,validate=True),base64.b64decode(v,validate=True)) for k,v in records))
        total += state.size
        if total>MAX_PAYLOAD:raise ValueError('Project chunk payload exceeds 32 MiB')
        document.chunk_edits[key] = state
    view = document.view_world
    edits = data.get("edits", [])
    if not isinstance(edits, list) or len(edits) > 262144:
        raise ValueError("Project contains too many edits")
    for row in edits:
        if not isinstance(row, list) or len(row) not in (5, 6):
            raise ValueError("Invalid project edit")
        dim, x, y, z, text = row[:5]
        if any(type(n) is not int for n in (x, y, z)):
            raise ValueError("Project coordinates must be integers")
        view.validate_edit((x, y, z), dim)
        key = (dim, x, y, z)
        if key in document.edits:
            raise ValueError("Duplicate project coordinate")
        if isinstance(text, dict):
            block = Block(text["name"], tuple(tuple(p) for p in text.get("properties", [])), tuple(tuple(p) for p in text.get("state_types", [])))
        else:
            block = Block.parse(text)
        if len(row) == 6:
            block = Block(block.name, block.properties, tuple(tuple(item) for item in row[5]))
        if block != view.get_block(x, y, z, dim):
            document.edits[key] = block
    if data.get("dimension") not in world.dimensions:
        raise ValueError("Invalid project dimension")
    for field,target in (("block_entities",document.entity_edits),("biomes",document.biome_edits),("layers",document.layer_edits)):
        rows = data.get(field,[])
        if not isinstance(rows,list) or len(rows)+document.pending_count > 262144:
            raise ValueError("Project exceeds the pending edit limit")
        for row in rows:
            if not isinstance(row,list) or len(row) != 5:
                raise ValueError("Invalid project metadata edit")
            dim,x,y,z,value = row
            if any(type(v) is not int for v in (x,y,z)):
                raise ValueError("Metadata coordinates must be integers")
            view.validate_edit((x,y,z),dim)
            key = (dim,x,y,z)
            if key in target:
                raise ValueError("Duplicate metadata coordinate")
            if field == "block_entities":
                from .world import validate_entity
                if value is not None:
                    value = base64.b64decode(value,validate=True)
                    validate_entity(value,(x,y,z))
                baseline = view.get_block_entity(x,y,z,dim)
            elif field=='biomes':
                if view.biome_cell(x,y,z,dim)!=(x,y,z):raise ValueError('Biome coordinates must align with their stored cells')
                value = view.biome_value(value,x,y,z,dim)
                baseline = view.get_biome(x,y,z,dim)
            else:
                if not world.edition.startswith('Bedrock') or not isinstance(value,list) or len(value)>7:raise ValueError('Invalid project block layers')
                value=tuple(Block(b['name'],tuple(tuple(p) for p in b.get('properties',[])),tuple(tuple(p) for p in b.get('state_types',[]))) for b in value)
                while value and value[-1].air:value=value[:-1]
                baseline=view.get_extra_blocks(x,y,z,dim)
            if value != baseline or (field == "block_entities" and value is not None and key in document.edits) or (field=='layers' and value and key in document.edits):
                target[key] = value
    document.dimension = data["dimension"]
    boxes = data.get('selection',[])
    if not isinstance(boxes,list) or len(boxes)>256:raise ValueError('Invalid project selection')
    if boxes:
        group = SelectionGroup(Selection(tuple(a),tuple(b)) for a,b in boxes)
        document.selection = group.boxes[0] if len(group.boxes)==1 else group
    if document.pending_count>262144:raise ValueError('Project exceeds its pending edit budget')
    return document
