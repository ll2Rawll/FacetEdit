"""Independent Sponge Schematic v2/v3 block interchange (Java)."""

from pathlib import Path

from . import nbt
from .blocks import AIR, Block
from .leveldb import Cursor, varint
from .model import Clipboard, MAX_OPERATION
from .structures import atomic_write
from .entities import relocate, validate_local


def load_schematic(path):
    path = Path(path)
    if path.stat().st_size > nbt.MAX_BYTES:
        raise ValueError("Schematic exceeds 64 MiB")
    raw = path.read_bytes()
    _, root = nbt.loads(raw, compressed=raw[:2] == b"\x1f\x8b")
    root = root.value.get("Schematic", root)
    version = nbt.get(root, "Version")
    if version not in (2, 3):
        raise ValueError("Supported Sponge schematic versions are 2 and 3")
    data_version = nbt.get(root,"DataVersion")
    if type(data_version) is not int or not 1451 <= data_version <= 4189:
        raise ValueError("Schematic DataVersion is outside the implemented Java range")
    if any(root.value.get(name,nbt.Tag(nbt.END,None)).kind != nbt.SHORT for name in ("Width","Height","Length")):
        raise ValueError("Schematic dimensions must be SHORT tags")
    size = tuple(nbt.get(root, name, 0)&0xffff for name in ("Width", "Height", "Length"))
    if any(type(n) is not int or n <= 0 for n in size):
        raise ValueError("Invalid schematic dimensions")
    width, height, depth = size
    volume = width * height * depth
    if volume > MAX_OPERATION:
        raise ValueError(f"Schematic exceeds {MAX_OPERATION:,} blocks")
    block_root = root.value["Blocks"] if version == 3 else root
    offset_tag = root.value.get("Offset",nbt.Tag(nbt.INT_ARRAY,[0,0,0]))
    if offset_tag.kind != nbt.INT_ARRAY or len(offset_tag.value) != 3:
        raise ValueError("Schematic Offset must contain three INT_ARRAY values")
    if "Biomes" in root.value or "BiomeData" in root.value:
        raise ValueError("Schematic biome interchange is not implemented; import a blocks-only schematic")
    palette_data = nbt.get(block_root, "Palette", {})
    palette = {}
    for name, value in palette_data.items():
        if value.kind != nbt.INT or not 0 <= value.value < MAX_OPERATION or value.value in palette:
            raise ValueError("Invalid schematic palette")
        palette[value.value] = Block.parse(name)
    entity_list = nbt.get(root,"Entities")
    if entity_list and entity_list.values:
        raise ValueError("Moving-entity schematics are not supported")
    data = nbt.get(block_root, "Data" if version == 3 else "BlockData")
    if not isinstance(data, bytes):
        raise ValueError("Schematic has no block data")
    cursor = Cursor(data)
    blocks = {}
    for index in range(volume):
        state = cursor.varint()
        if state not in palette:
            raise ValueError("Schematic references an unknown palette entry")
        y, horizontal = divmod(index, width * depth)
        z, x = divmod(horizontal, width)
        blocks[(x,y,z)] = palette[state]
    if cursor.pos != len(data):
        raise ValueError("Trailing schematic block data")
    entities = {}
    for entry in nbt.get(block_root,"BlockEntities",nbt.ListValue(nbt.COMPOUND,[])).values:
        pos_tag = entry.get("Pos")
        id_tag = entry.get("Id")
        if not pos_tag or pos_tag.kind != nbt.INT_ARRAY or not id_tag or id_tag.kind != nbt.STRING:
            raise ValueError("Schematic block entities need Pos and Id")
        pos = tuple(pos_tag.value)
        validate_local(pos,size,blocks,entities)
        if version == 3:
            payload = entry.get("Data",nbt.compound())
            if payload.kind != nbt.COMPOUND:
                raise ValueError("Invalid block-entity Data compound")
            payload = dict(payload.value)
        else:
            payload = {key:value for key,value in entry.items() if key not in ("Id","Pos")}
        payload["id"] = id_tag
        entities[pos] = relocate(nbt.dumps(nbt.Tag(nbt.COMPOUND,payload)),pos)
    return Clipboard(size, blocks, "Java",tuple(offset_tag.value),entities,data_version)


def save_schematic(clipboard, path, version=3):
    if clipboard.edition != "Java" or version not in (2,3):
        raise ValueError("Sponge schematic export requires a Java clipboard and version 2 or 3")
    width, height, depth = clipboard.size
    if width * height * depth > MAX_OPERATION or any(not 0 < n <= 65535 for n in clipboard.size):
        raise ValueError("Schematic dimensions exceed the export limits")
    palette = {}
    data = bytearray()
    for y in range(height):
        for z in range(depth):
            for x in range(width):
                block = clipboard.blocks.get((x,y,z), AIR)
                index = palette.setdefault(str(block), len(palette))
                data.extend(varint(index))
    root = nbt.compound(
        Version=nbt.Tag(nbt.INT, version), DataVersion=nbt.Tag(nbt.INT, clipboard.data_version),
        Width=nbt.Tag(nbt.SHORT, width if width<32768 else width-65536), Height=nbt.Tag(nbt.SHORT, height if height<32768 else height-65536), Length=nbt.Tag(nbt.SHORT, depth if depth<32768 else depth-65536),
        Offset=nbt.Tag(nbt.INT_ARRAY, list(clipboard.offset)),
        Metadata=nbt.compound(Name=nbt.Tag(nbt.STRING, "FacetEdit selection")),
        Entities=nbt.Tag(nbt.LIST, nbt.ListValue(nbt.COMPOUND, [])),
    )
    block_data = {
        "Palette": nbt.Tag(nbt.COMPOUND, {name: nbt.Tag(nbt.INT, index) for name, index in palette.items()}),
        "BlockEntities": nbt.Tag(nbt.LIST, nbt.ListValue(nbt.COMPOUND, [])),
        "Data" if version == 3 else "BlockData": nbt.Tag(nbt.BYTE_ARRAY, bytes(data)),
    }
    for position,data in clipboard.entities.items():
        validate_local(position,clipboard.size,clipboard.blocks,{})
        tag = nbt.loads(relocate(data,position))[1]
        payload = {key:value for key,value in tag.value.items() if key not in ("id","x","y","z")}
        entity = {"Id":tag.value["id"],"Pos":nbt.Tag(nbt.INT_ARRAY,list(position))}
        if version == 3:
            entity["Data"] = nbt.Tag(nbt.COMPOUND,payload)
        else:
            if "Id" in payload or "Pos" in payload:
                raise ValueError("Sponge v2 cannot preserve block NBT named Id or Pos; choose v3")
            entity.update(payload)
        block_data["BlockEntities"].value.values.append(entity)
    if version == 3:
        root.value["Blocks"] = nbt.Tag(nbt.COMPOUND, block_data)
        root = nbt.compound(Schematic=root)
    else:
        root.value.update(block_data)
        root.value["PaletteMax"] = nbt.Tag(nbt.INT, len(palette))
    atomic_write(path, nbt.dumps(root, name="Schematic" if version == 2 else "", compressed=True))
