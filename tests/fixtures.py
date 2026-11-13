"""Small worlds assembled from documented binary layouts, not game assets."""
from pathlib import Path
import struct

from facetedit import nbt
from facetedit.leveldb import write_database
from facetedit.region import Region


def java_world(path, version=4189):
    path = Path(path)
    (path / "region").mkdir(parents=True)
    metadata = nbt.compound(Data=nbt.compound(
        DataVersion=nbt.Tag(nbt.INT, version), LevelName=nbt.Tag(nbt.STRING, "Test meadow"),
        SpawnX=nbt.Tag(nbt.INT, 4), SpawnY=nbt.Tag(nbt.INT, 16), SpawnZ=nbt.Tag(nbt.INT, 4),
        RandomSeed=nbt.Tag(nbt.LONG, 918273645),
    ))
    (path / "level.dat").write_bytes(nbt.dumps(metadata, compressed=True))
    regions = {}
    for cx, cz in ((-1, -1), (0, 0), (1, 0), (31, 0), (32, 0)):
        section = {"Y": nbt.Tag(nbt.BYTE, 0)}
        palette = nbt.Tag(nbt.LIST, nbt.ListValue(nbt.COMPOUND, [{"Name": nbt.Tag(nbt.STRING, "minecraft:stone")}]))
        if version >= 2834:
            section["block_states"] = nbt.compound(palette=palette)
            section["biomes"] = nbt.compound(palette=nbt.Tag(nbt.LIST, nbt.ListValue(nbt.STRING, ["minecraft:plains"])))
        elif version>=1451:
            section["Palette"] = palette
            section["BlockStates"] = nbt.Tag(nbt.LONG_ARRAY, [0] * 256)
        else:
            section['Blocks']=nbt.Tag(nbt.BYTE_ARRAY,b'\x01'*4096)
            section['Data']=nbt.Tag(nbt.BYTE_ARRAY,b'\0'*2048)
        data = nbt.compound(
            xPos=nbt.Tag(nbt.INT, cx), zPos=nbt.Tag(nbt.INT, cz),
            Status=nbt.Tag(nbt.STRING, "minecraft:full" if version >= 2834 else "full"),
            InhabitedTime=nbt.Tag(nbt.LONG, 12345),
            CustomUnknown=nbt.Tag(nbt.STRING, "preserve me"),
            isLightOn=nbt.Tag(nbt.BYTE, 1),
        )
        data.value["sections" if version >= 2834 else "Sections"] = nbt.Tag(nbt.LIST, nbt.ListValue(nbt.COMPOUND, [section]))
        if version<1451:data.value['Biomes']=nbt.Tag(nbt.BYTE_ARRAY,b'\x01'*256)
        data.value["block_entities" if version >= 2834 else "TileEntities"] = nbt.Tag(nbt.LIST, nbt.ListValue(nbt.COMPOUND, [
            {"id": nbt.Tag(nbt.STRING, "minecraft:chest"), "x": nbt.Tag(nbt.INT, cx*16+1), "y": nbt.Tag(nbt.INT, 2), "z": nbt.Tag(nbt.INT, cz*16+3)},
            {"id": nbt.Tag(nbt.STRING, "minecraft:chest"), "x": nbt.Tag(nbt.INT, cx*16+2), "y": nbt.Tag(nbt.INT, 2), "z": nbt.Tag(nbt.INT, cz*16+3)},
        ]))
        if version >= 2834:
            root = data
            root.value["DataVersion"] = nbt.Tag(nbt.INT, version)
        else:
            root = nbt.compound(DataVersion=nbt.Tag(nbt.INT, version), Level=data)
        rkey = (cx//32, cz//32)
        region = regions.setdefault(rkey, Region())
        region.put(cx, cz, nbt.dumps(root))
    for (rx, rz), region in regions.items():
        (path / "region" / f"r.{rx}.{rz}.mca").write_bytes(region.dumps())
    (path / "extra.dat").write_bytes(b"unrelated preserved bytes")
    return path


def bedrock_world(path):
    path = Path(path)
    path.mkdir(parents=True)
    root = nbt.compound(LevelName=nbt.Tag(nbt.STRING, "Bedrock fixture"), SpawnX=nbt.Tag(nbt.INT, 4), SpawnY=nbt.Tag(nbt.INT, 16), SpawnZ=nbt.Tag(nbt.INT, 4))
    raw = nbt.dumps(root, little=True)
    (path / "level.dat").write_bytes(struct.pack("<II", 10, len(raw)) + raw)
    entry = nbt.compound(name=nbt.Tag(nbt.STRING, "minecraft:stone"), states=nbt.compound(), version=nbt.Tag(nbt.INT, 17959425))
    # v9, one storage, y=0, singleton persistent palette, little-endian NBT.
    subchunk = bytes((9, 1, 0, 0)) + nbt.dumps(entry, little=True)
    values = {b"unrelated-key": b"keep this payload", b"~local_player": b"opaque player data"}
    for cx, cz in ((0, 0), (-1, -1)):
        prefix = struct.pack("<ii", cx, cz)
        values[prefix + b"/\x00"] = subchunk
        values[prefix + b","] = b"\x29"
    entity = nbt.compound(id=nbt.Tag(nbt.STRING, "Chest"), x=nbt.Tag(nbt.INT, 1), y=nbt.Tag(nbt.INT, 2), z=nbt.Tag(nbt.INT, 3))
    values[b"\x00"*8 + b"1"] = nbt.dumps(entity, little=True)
    write_database(path / "db", values)
    return path
