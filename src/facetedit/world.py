"""Read-only world adapters and transactional export to a separate folder."""

from __future__ import annotations

from collections import OrderedDict, defaultdict
import copy
import hashlib
import math
from pathlib import Path
import shutil
import struct
import tempfile
import threading

from .blocks import AIR, Block
from . import nbt
from .formats import decode_bedrock, decode_java_section, encode_bedrock, encode_java_section, decode_java_biomes, encode_java_biomes
from .leveldb import load_database, write_database
from .region import Region,decode_payload
from . import chunks
from . import biomes


class Cache(OrderedDict):
    def __init__(self, limit=96):
        super().__init__()
        self.limit = limit
        self._lock = threading.RLock()

    def obtain(self, key, loader):
        with self._lock:
            if key in self:
                self.move_to_end(key)
                return self[key]
            value = loader()
            self[key] = value
            if len(self) > self.limit:
                self.popitem(last=False)
            return value


def snapshot(path):
    result = {}
    for file in sorted(Path(path).rglob("*")):
        if file.is_symlink():
            raise ValueError("World folders with symbolic links are not supported")
        if file.is_file():
            stat = file.stat()
            result[str(file.relative_to(path))] = (stat.st_size, stat.st_mtime_ns)
    return result


class World:
    name = "Untitled"
    edition = "Sample"
    dimensions = ("overworld",)
    minimum_y, maximum_y = -64, 319
    spawn = (0, 70, 0)
    path = None

    def stored_sections(self,cx,cz,dimension):return None

    def get_block_entity(self, x,y,z,dimension="overworld"):
        return None

    def get_extra_blocks(self,x,y,z,dimension='overworld'):
        return ()

    def get_biome(self,x,y,z,dimension="overworld"):
        raise ValueError("Biome editing currently supports modern Java worlds and the sample")

    def biome_grid(self,x,y,z,dimension='overworld'):return 4,4,4

    def biome_cell(self,x,y,z,dimension='overworld'):
        grid=self.biome_grid(x,y,z,dimension)
        return tuple(v//step*step if step else self.bounds(dimension)[0] for v,step in zip((x,y,z),grid))

    def biome_value(self,value,x,y,z,dimension='overworld'):return Block(value).name

    def validate_copy(self,position,dimension):
        """Refuse payloads the clipboard cannot preserve."""

    def bounds(self, dimension):
        if dimension == "the_nether":
            return 0, 127
        if dimension == "the_end":
            return 0, 255
        return self.minimum_y, self.maximum_y

    def validate_edit(self, pos, dimension):
        if dimension not in self.dimensions:
            raise ValueError("Unknown world dimension")
        minimum, maximum = self.bounds(dimension)
        if not minimum <= pos[1] <= maximum:
            raise ValueError(f"Y must be between {minimum} and {maximum} in {dimension}")

    def export(self, destination, edits, progress=lambda message: None, **metadata):
        raise ValueError("Save the sample as a FacetEdit project or export a structure")

    def chunk_positions(self,dimension):
        raise ValueError('Chunk management requires an opened Java or Bedrock world')

    def with_chunks(self,overrides):
        if overrides:raise ValueError('The sample does not store disk chunks')
        return self


class SampleWorld(World):
    name = "Willow Bay"
    minimum_y, maximum_y = 0, 95
    spawn = (0, 14, 0)

    def get_biome(self,x,y,z,dimension="overworld"):
        return "minecraft:plains"

    def __init__(self,generator=2):
        self.generator = generator
        self.heights = {}
        self.materials = {name: Block(name) for name in ("sand", "water", "grass_block", "dirt", "stone")}
        self.log = Block("oak_log", (("axis", "y"),))
        self.leaves = Block("oak_leaves", (("persistent", "true"),))
        self.tree_columns = {}
        trees = ((-9,-6),(10,4),(-10,10),(12,-10),(-19,-16),(18,19)) if generator==1 else ((-8,-6),(8,5),(-8,8),(8,-8),(-19,-16),(18,19))
        for tx, tz in trees:
            base = self.height(tx, tz)
            for x in range(tx - 2, tx + 3):
                for z in range(tz - 2, tz + 3):
                    if abs(x-tx) + abs(z-tz) < 4:
                        self.tree_columns.setdefault((x,z), []).append((tx, tz, base))

    def height(self, x, z):
        key = (x, z)
        if key not in self.heights:
            self.heights[key] = round(8 + 2.5 * math.sin(x * .14) + 2 * math.cos(z * .18) + 1.6 * math.sin((x + z) * .22))
        return self.heights[key]

    def get_block(self, x, y, z, dimension="overworld"):
        h = self.height(x, z)
        if y < 0 or y > 95:
            return AIR
        # Original procedural terrain, with a river and stylised trees.
        river = abs(x - 7 * math.sin(z * .10)) < 3
        if river:
            if y <= 4:
                return self.materials["sand"]
            return self.materials["water"] if y <= 7 else AIR
        if y <= h:
            return self.materials["grass_block" if y == h else "dirt" if y > h - 3 else "stone"]
        for tx, tz, base in self.tree_columns.get((x, z), ()):
            if x == tx and z == tz and base < y <= base + 4:
                return self.log
            if abs(x - tx) <= 2 and abs(z - tz) <= 2 and base + 3 <= y <= base + 5:
                if abs(x - tx) + abs(z - tz) < 4:
                    return self.leaves
        return AIR


class DiskWorld(World):
    def __init__(self, path):
        self.path = Path(path).expanduser().resolve()
        self.signature = snapshot(self.path)

    def export(self, destination, edits, progress=lambda message: None, entity_edits=None, biome_edits=None,chunk_edits=None,layer_edits=None):
        destination = Path(destination).expanduser().resolve()
        if destination.exists():
            raise FileExistsError("Choose a new folder; FacetEdit never overwrites an existing world")
        if self.path == destination or self.path in destination.parents:
            raise ValueError("Export outside the source world folder")
        if not destination.parent.is_dir():
            raise ValueError("The destination's parent folder must exist")
        if snapshot(self.path) != self.signature:
            raise ValueError("The source world changed. Close Minecraft and reopen the world in FacetEdit")
        stage = Path(tempfile.mkdtemp(prefix=".facetedit-export-", dir=destination.parent))
        try:
            progress("Copying the source world…")
            shutil.copytree(self.path, stage, dirs_exist_ok=True)
            if snapshot(self.path) != self.signature:
                raise ValueError("The source changed during copying; export was cancelled")
            # Verify copied bytes against the source; timestamps alone are insufficient.
            for relative in self.signature:
                a, b = self.path / relative, stage / relative
                if file_hash(a) != file_hash(b):
                    raise ValueError("Source changed during snapshot verification")
            progress("Writing edited chunks…")
            writer = self.with_chunks(chunk_edits or {})
            if chunk_edits and isinstance(self,JavaWorld):
                chunks.write_java_chunks(self,stage,chunk_edits)
            writer._write_edits(stage, edits, entity_edits or {}, biome_edits or {},layer_edits or {})
            if snapshot(self.path) != self.signature:
                raise ValueError("Source changed during export; close Minecraft before retrying")
            if destination.exists():
                raise FileExistsError("Destination appeared during export")
            stage.rename(destination)
            progress("World copy saved")
        finally:
            if stage.exists():
                shutil.rmtree(stage)


def file_hash(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.digest()


def read_metadata(path):
    if path.stat().st_size > nbt.MAX_BYTES:
        raise nbt.FormatError("World metadata exceeds 64 MiB")
    return path.read_bytes()


class JavaWorld(DiskWorld):
    edition = "Java"

    def stored_sections(self,cx,cz,dimension):
        chunk=self._chunk(cx,cz,dimension)
        return tuple(chunk[4]) if chunk else ()

    def bounds(self, dimension):
        bounds=self.dimension_bounds.get(dimension)
        if bounds is None:raise ValueError('Cannot resolve build height for '+dimension+'; its dimension type datapack is required')
        return bounds

    def __init__(self, path):
        super().__init__(path)
        _, root = nbt.loads(read_metadata(self.path / "level.dat"), compressed=True)
        data = root.value.get("Data", root)
        self.version = nbt.get(data, "DataVersion", 0)
        if type(self.version) is not int or not 0 <= self.version <= 4189:
            raise nbt.FormatError(f"Java DataVersion {self.version} is outside the implemented Anvil range 0–4189")
        self.minimum_y, self.maximum_y = (-64, 319) if self.version >= 2834 else (0, 255)
        self.name = nbt.get(data, "LevelName", self.path.name)
        self.spawn = tuple(nbt.get(data, "Spawn" + axis, default) for axis, default in zip("XYZ", (0, 70, 0)))
        self.dimension_paths = {"overworld": Path("region")}
        for name, folder in (("the_nether", "DIM-1"), ("the_end", "DIM1")):
            if (self.path / folder / "region").is_dir():
                self.dimension_paths[name] = Path(folder) / "region"
        dimensions = self.path / "dimensions"
        if dimensions.is_dir():
            for region in dimensions.rglob("region"):
                if region.is_dir():
                    self.dimension_paths[str(region.parent.relative_to(dimensions))] = region.relative_to(self.path)
        self.dimensions = tuple(self.dimension_paths)
        from .dimensions import java_bounds
        self.dimension_bounds=java_bounds(self.path,data,self.version,self.dimensions)
        self.dimension_bounds.setdefault('the_nether',(0,255));self.dimension_bounds.setdefault('the_end',(0,255))
        self.minimum_y,self.maximum_y=self.bounds('overworld')
        if any(any((self.path/folder).glob('*.mcr')) and not any((self.path/folder).glob('*.mca')) for folder in self.dimension_paths.values()):
            raise nbt.FormatError('McRegion .mcr worlds require conversion to Anvil before opening')
        self.cache = Cache(96)
        self.regions = Cache(4)
        self.entity_cache = Cache(96)
        self.chunk_overrides = {}
        self.inventory_cache = {}

    def chunk_positions(self,dimension):
        if dimension not in self.dimensions:raise ValueError('Unknown dimension')
        if dimension not in self.inventory_cache:
            positions = set()
            for file in sorted((self.path/self.dimension_paths[dimension]).glob('r.*.*.mca')):
                positions.update(Region.coordinates(file))
            self.inventory_cache[dimension] = frozenset(positions)
        result = set(self.inventory_cache[dimension])
        for (dim,cx,cz),state in self.chunk_overrides.items():
            if dim==dimension:
                if state.kind=='deleted':result.discard((cx,cz))
                else:result.add((cx,cz))
        return result

    def chunk_snapshot(self,cx,cz,dimension):
        state = self.chunk_overrides.get((dimension,cx,cz))
        return state if state is not None else chunks.java_chunk_snapshot(self,cx,cz,dimension)

    def empty_chunk(self,cx,cz,dimension):return chunks.empty_java(self,cx,cz,dimension)

    def with_chunks(self,overrides):
        if not overrides:return self
        clone = copy.copy(self)
        clone.chunk_overrides = dict(overrides)
        clone.cache,clone.entity_cache = Cache(96),Cache(96)
        for (dimension,cx,cz),state in overrides.items():
            if dimension not in self.dimensions:raise ValueError('Unknown chunk dimension')
            chunks.validate_java_state(state,cx,cz)
        return clone

    def _region(self, cx, cz, dimension):
        relative = self.dimension_paths[dimension] / f"r.{cx // 32}.{cz // 32}.mca"
        def load():
            file = self.path / relative
            return Region.read(file) if file.exists() else Region()
        return self.regions.obtain(str(relative), load)

    def _chunk(self, cx, cz, dimension):
        def load():
            state = self.chunk_overrides.get((dimension,cx,cz))
            if state is not None:
                if state.kind=='deleted':return None
                records = dict(state.records)
                raw = decode_payload(records[b'region'],records.get(b'region.mcc'))
            else:raw = self._region(cx, cz, dimension).get(cx, cz)
            if raw is None:
                return None
            name, root = nbt.loads(raw)
            version = nbt.get(root, "DataVersion", self.version)
            if type(version) is not int or not 0 <= version <= 4189:
                raise nbt.FormatError(f"Chunk DataVersion {version} is unsupported")
            level = root.value.get("Level", root)
            section_list = nbt.get(level, "sections" if version >= 2834 else "Sections", nbt.ListValue(nbt.COMPOUND, []))
            if any('Blocks' in section for section in section_list.values):version=min(version,1343)
            sections = {}
            raw_sections = {}
            for section in section_list.values:
                sy = section["Y"].value
                raw_sections[sy] = section
                sections[sy] = decode_java_section(section, version)
            return name, root, level, version, sections, raw_sections
        return self.cache.obtain((dimension, cx, cz), load)

    def get_block(self, x, y, z, dimension="overworld"):
        minimum,maximum=self.bounds(dimension)
        if not minimum <= y <= maximum:
            return AIR
        chunk = self._chunk(x // 16, z // 16, dimension)
        if chunk is None:
            return AIR
        section = chunk[4].get(y // 16)
        return AIR if section is None else section[(x & 15) | ((z & 15) << 4) | ((y & 15) << 8)]

    def validate_edit(self, pos, dimension):
        super().validate_edit(pos, dimension)
        if self._chunk(pos[0] // 16, pos[2] // 16, dimension) is None:
            raise ValueError("This chunk does not exist. Create it in the chunk manager first")

    def get_block_entity(self,x,y,z,dimension="overworld"):
        def load():
            chunk = self._chunk(x//16,z//16,dimension)
            entries = {}
            if chunk is not None:
                entities = nbt.get(chunk[2],"block_entities" if chunk[3]>=2834 else "TileEntities")
                for entity in entities.values if entities else ():
                    tag = nbt.Tag(nbt.COMPOUND,entity)
                    entries[tuple(nbt.get(tag,axis) for axis in "xyz")] = nbt.dumps(tag)
            return entries
        return self.entity_cache.obtain((dimension,x//16,z//16),load).get((x,y,z))

    def get_biome(self,x,y,z,dimension="overworld"):
        chunk = self._chunk(x//16,z//16,dimension)
        if chunk is None:
            raise ValueError("Cannot inspect a biome in an ungenerated chunk")
        if chunk[3] < 2834:
            tag=biomes.numeric_java(chunk[2])
            minimum,three_d=self._numeric_biome_layout(chunk,dimension)
            return biomes.name(tag.value[biomes.java_index(x,y,z,len(tag.value),minimum,three_d)])
        section = chunk[5].get(y//16,{})
        cells = decode_java_biomes(section)
        return cells[((x//4)&3) | (((z//4)&3)<<2) | (((y//4)&3)<<4)]

    def _numeric_biome_layout(self,chunk,dimension):
        tag=biomes.numeric_java(chunk[2]);three_d=tag.kind==nbt.INT_ARRAY and chunk[3]>=2203
        low,high=self.bounds(dimension)
        # Old chunks left in an upgraded world still index their 256-block
        # biome columns from Y=0, independent of the new dimension's minimum.
        minimum=low if chunk[3]>=2709 and len(tag.value)==(high-low+1)*4 else 0
        return minimum,three_d

    def biome_grid(self,x,y,z,dimension='overworld'):
        chunk=self._chunk(x//16,z//16,dimension)
        if chunk is None:raise ValueError('Cannot edit biomes in an ungenerated chunk')
        if chunk[3]<2834 and not self._numeric_biome_layout(chunk,dimension)[1]:return 1,0,1
        return 4,4,4

    def biome_cell(self,x,y,z,dimension='overworld'):
        cell=super().biome_cell(x,y,z,dimension)
        chunk=self._chunk(x//16,z//16,dimension)
        if chunk[3]<2834:
            length=len(biomes.numeric_java(chunk[2]).value);minimum,three_d=self._numeric_biome_layout(chunk,dimension)
            return cell[0],max(minimum,min(minimum+length//4-4,cell[1])) if three_d else self.bounds(dimension)[0],cell[2]
        return cell

    def biome_value(self,value,x,y,z,dimension='overworld'):
        chunk=self._chunk(x//16,z//16,dimension)
        if chunk is None:raise ValueError('Cannot edit biomes in an ungenerated chunk')
        if chunk[3]<2834:
            tag=biomes.numeric_java(chunk[2]);number=biomes.identifier(value)
            if number>(255 if tag.kind==nbt.BYTE_ARRAY else 0x7fffffff):raise ValueError('Biome ID exceeds this storage format')
            return biomes.name(number)
        return Block(value).name

    def _write_edits(self, stage, edits, entity_edits=None, biome_edits=None,layer_edits=None):
        if layer_edits:raise ValueError('Java does not store extra block layers')
        entity_edits,biome_edits = entity_edits or {},biome_edits or {}
        groups = defaultdict(dict)
        for (dimension, x, y, z), block in edits.items():
            groups[(dimension, x // 16, z // 16)][(x, y, z)] = block
        entity_groups,biome_groups = defaultdict(dict),defaultdict(dict)
        for source,target in ((entity_edits,entity_groups),(biome_edits,biome_groups)):
            for (dimension,x,y,z),value in source.items():
                key = (dimension,x//16,z//16)
                groups.setdefault(key,{})
                target[key][(x,y,z)] = value
        regions = {}
        for (dimension, cx, cz), changes in groups.items():
            name, root, level, version, sections, raw_sections = copy.deepcopy(self._chunk(cx, cz, dimension))
            touched = set()
            for (x, y, z), block in changes.items():
                sy = y // 16
                section = sections.setdefault(sy, [AIR] * 4096)
                section[(x & 15) | ((z & 15) << 4) | ((y & 15) << 8)] = block
                touched.add(sy)
            for sy in touched:
                raw = raw_sections.setdefault(sy, {"Y": nbt.Tag(nbt.BYTE, sy)})
                if version >= 2834 and "biomes" not in raw:
                    raw["biomes"] = nbt.Tag(nbt.COMPOUND, {"palette": nbt.Tag(nbt.LIST, nbt.ListValue(nbt.STRING, ["minecraft:plains"]))})
                encode_java_section(raw, sections[sy], version)
            biome_sections = {}
            for (x,y,z),biome in biome_groups[(dimension,cx,cz)].items():
                if version < 2834:
                    tag=biomes.numeric_java(level);value=biomes.identifier(biome)
                    minimum,three_d=self._numeric_biome_layout((name,root,level,version),dimension)
                    numbers=list(tag.value);numbers[biomes.java_index(x,y,z,len(numbers),minimum,three_d)]=value
                    level.value['Biomes']=nbt.Tag(tag.kind,bytes(numbers) if tag.kind==nbt.BYTE_ARRAY else numbers)
                    continue
                raw = raw_sections.setdefault(y//16,{"Y":nbt.Tag(nbt.BYTE,y//16)})
                if y//16 not in biome_sections:
                    biome_sections[y//16] = decode_java_biomes(raw)
                cells = biome_sections[y//16]
                cells[((x//4)&3)|(((z//4)&3)<<2)|(((y//4)&3)<<4)] = biome
            for sy,cells in biome_sections.items():
                encode_java_biomes(raw_sections[sy],cells)
            section_key = "sections" if version >= 2834 else "Sections"
            level.value[section_key] = nbt.Tag(nbt.LIST, nbt.ListValue(nbt.COMPOUND, [raw_sections[k] for k in sorted(raw_sections)]))
            # Clear stale block entity data only at positions whose block changed.
            entity_key = "block_entities" if version >= 2834 else "TileEntities"
            entity_list = nbt.get(level, entity_key)
            if entity_list:
                entity_list.values[:] = [e for e in entity_list.values if tuple(e.get(axis, nbt.Tag(nbt.INT, 0)).value for axis in "xyz") not in changes]
            replacements = entity_groups[(dimension,cx,cz)]
            if replacements:
                old = entity_list.values if entity_list else []
                entries = [e for e in old if tuple(nbt.get(nbt.Tag(nbt.COMPOUND,e),axis) for axis in "xyz") not in replacements]
                for position,value in replacements.items():
                    if value is not None:
                        tag = validate_entity(value,position)
                        entries.append(tag.value)
                level.value[entity_key] = nbt.Tag(nbt.LIST,nbt.ListValue(nbt.COMPOUND,entries))
            if changes:
                level.value["isLightOn"] = nbt.Tag(nbt.BYTE, 0)
                if version<1451:level.value['LightPopulated']=nbt.Tag(nbt.BYTE,0)
                level.value.pop("Heightmaps", None)
                level.value.pop("HeightMap", None)
            relative = self.dimension_paths[dimension] / f"r.{cx // 32}.{cz // 32}.mca"
            if relative not in regions:
                regions[relative] = Region.read(stage / relative) if (stage/relative).exists() else Region(path=stage/relative)
            regions[relative].put(cx, cz, nbt.dumps(root, name))
        for relative, region in regions.items():
            region.write(stage/relative)


class BedrockWorld(DiskWorld):
    edition = "Bedrock · experimental export"
    dimension_ids = {"overworld": 0, "the_nether": 1, "the_end": 2}

    def __init__(self, path):
        super().__init__(path)
        raw = read_metadata(self.path / "level.dat")
        if len(raw) < 8:
            raise nbt.FormatError("Truncated Bedrock level.dat")
        _, size = struct.unpack_from("<II", raw)
        if size != len(raw) - 8:
            raise nbt.FormatError("Bedrock level.dat length mismatch")
        _, data = nbt.loads(raw[8:], little=True)
        opened_version = nbt.get(data,'lastOpenedWithVersion')
        self.game_version = tuple(opened_version.values[:3]) if isinstance(opened_version,nbt.ListValue) and len(opened_version.values)>=3 else None
        if self.game_version is not None and any(type(v) is not int or v<0 for v in self.game_version):
            raise nbt.FormatError('Invalid Bedrock lastOpenedWithVersion metadata')
        if self.game_version is not None and self.game_version<(1,18,0):
            self.minimum_y,self.maximum_y = 0,255
        self.name = nbt.get(data, "LevelName", self.path.name)
        self.spawn = tuple(nbt.get(data, "Spawn" + axis, default) for axis, default in zip("XYZ", (0, 70, 0)))
        self.values = load_database(self.path / "db")
        self.dimensions = tuple(self.dimension_ids)
        self.cache = Cache(96)
        self.entity_cache = Cache(96)
        self.biome_cache=Cache(32)
        self.inventory_cache = None
        self.chunk_record_index = None

    def chunk_positions(self,dimension):
        if dimension not in self.dimensions:raise ValueError('Unknown dimension')
        if self.inventory_cache is None:
            inventory = {did:set() for did in self.dimension_ids.values()}
            records=defaultdict(list)
            for key in self.values:
                parsed = chunks.bedrock_key(key)
                if parsed:
                    did,cx,cz,_ = parsed
                    records[did,cx,cz].append(key)
                    if parsed[3] in (b',',b'v') or parsed[3].startswith(b'/'):inventory[did].add((cx,cz))
            self.chunk_record_index=dict(records)
            self.inventory_cache = inventory
        return set(self.inventory_cache[self.dimension_ids[dimension]])

    def chunk_snapshot(self,cx,cz,dimension):return chunks.bedrock_chunk_snapshot(self,cx,cz,dimension)

    def empty_chunk(self,cx,cz,dimension):return chunks.empty_bedrock(self,cx,cz,dimension)

    def with_chunks(self,overrides):
        if not overrides:return self
        clone = chunks.bedrock_with_chunks(self,overrides)
        clone.cache,clone.entity_cache = Cache(96),Cache(96)
        clone.biome_cache=Cache(32)
        clone.inventory_cache = None
        clone.chunk_record_index = None
        clone.empty_templates = {}
        return clone

    def prefix(self, cx, cz, dimension):
        did = self.dimension_ids[dimension]
        return struct.pack("<ii", cx, cz) + (struct.pack("<i", did) if did else b"")

    def _section(self, cx, sy, cz, dimension):
        def load():
            raw = self.values.get(self.prefix(cx, cz, dimension) + b"/" + struct.pack("b", sy))
            if raw is None:
                return None
            section = decode_bedrock(raw)
            if section[0] == 9 and section[1] != sy:
                raise nbt.FormatError("Bedrock subchunk Y disagrees with its key")
            return section
        return self.cache.obtain((dimension, cx, sy, cz), load)

    def get_block(self, x, y, z, dimension="overworld"):
        if not self.minimum_y <= y <= self.maximum_y:
            return AIR
        section = self._section(x // 16, y // 16, z // 16, dimension)
        if section is None:
            return AIR
        index = ((x & 15) << 8) | ((z & 15) << 4) | (y & 15)
        return section[2][0][index]

    def get_extra_blocks(self,x,y,z,dimension='overworld'):
        if not self.minimum_y <= y <= self.maximum_y:
            return ()
        section = self._section(x//16,y//16,z//16,dimension)
        index = ((x&15)<<8)|((z&15)<<4)|(y&15)
        extra=tuple(layer[index] for layer in section[2][1:]) if section else ()
        while extra and extra[-1].air:extra=extra[:-1]
        return extra

    def validate_edit(self, pos, dimension):
        super().validate_edit(pos, dimension)
        prefix = self.prefix(pos[0] // 16, pos[2] // 16, dimension)
        if not any(prefix + suffix in self.values for suffix in (b",", b"v")) and not any(
            prefix + b"/" + struct.pack("b", sy) in self.values for sy in range(-4, 20)
        ):
            raise ValueError("This Bedrock chunk has not been generated")

    def get_block_entity(self,x,y,z,dimension="overworld"):
        prefix = self.prefix(x//16,z//16,dimension)
        def load():
            raw = self.values.get(prefix+b"1",b"")
            reader = nbt.Reader(raw,little=True)
            entries = {}
            while reader.pos < len(raw):
                _,tag = reader.root()
                entries[tuple(nbt.get(tag,axis) for axis in "xyz")] = nbt.dumps(tag)
            return entries
        return self.entity_cache.obtain(prefix,load).get((x,y,z))

    def biome_grid(self,x,y,z,dimension='overworld'):
        prefix=self.prefix(x//16,z//16,dimension)
        if prefix+b'+' in self.values:return 1,1,1
        if prefix+b'-' in self.values:return 1,0,1
        raise ValueError('This chunk has no stored biome data')

    def _biomes(self,x,z,dimension):
        prefix=self.prefix(x//16,z//16,dimension)
        return self.biome_cache.obtain(prefix,lambda:biomes.BedrockBiomes(self.values[prefix+b'+'],self.bounds(dimension)[0]))

    def get_biome(self,x,y,z,dimension='overworld'):
        grid=self.biome_grid(x,y,z,dimension)
        if grid[1]:value=self._biomes(x,z,dimension).get(x,y,z)
        else:
            raw=self.values[self.prefix(x//16,z//16,dimension)+b'-']
            if len(raw)!=768:raise nbt.FormatError('Expected 768-byte Bedrock 2D biome record')
            value=raw[512+(z&15)*16+(x&15)]
        return biomes.name(value,'Bedrock')

    def biome_value(self,value,x,y,z,dimension='overworld'):
        number=biomes.identifier(value,'Bedrock')
        if self.biome_grid(x,y,z,dimension)[1]==0 and number>255:raise ValueError('2D biome IDs must fit one byte')
        return biomes.name(number,'Bedrock')

    def _write_edits(self, stage, edits, entity_edits=None, biome_edits=None,layer_edits=None):
        entity_edits = entity_edits or {}
        values = dict(self.values)
        biome_groups=defaultdict(dict)
        for (dimension,x,y,z),value in (biome_edits or {}).items():
            biome_groups[dimension,x//16,z//16][x,y,z]=biomes.identifier(value,'Bedrock')
        for (dimension,cx,cz),changes in biome_groups.items():
            prefix=self.prefix(cx,cz,dimension)
            if prefix+b'+' in values:values[prefix+b'+']=self._biomes(cx*16,cz*16,dimension).edited(changes)
            else:
                raw=bytearray(values[prefix+b'-'])
                if len(raw)!=768:raise nbt.FormatError('Invalid Bedrock 2D biome record')
                for (x,y,z),value in changes.items():raw[512+(z&15)*16+(x&15)]=value
                values[prefix+b'-']=bytes(raw)
        groups = defaultdict(dict)
        for (dimension, x, y, z), block in edits.items():
            groups[(dimension, x // 16, y // 16, z // 16)][(x, y, z)] = block
        layer_groups=defaultdict(dict)
        for (dimension,x,y,z),extra in (layer_edits or {}).items():
            key=(dimension,x//16,y//16,z//16)
            groups.setdefault(key,{})
            layer_groups[key][x,y,z]=extra
        changed_chunks = defaultdict(set)
        for (dimension, cx, sy, cz), changes in groups.items():
            section = copy.deepcopy(self._section(cx, sy, cz, dimension))
            version, _, layers, palettes = section if section else (9, sy, [[AIR] * 4096], [])
            for (x, y, z), block in changes.items():
                index = ((x & 15) << 8) | ((z & 15) << 4) | (y & 15)
                layers[0][index] = block
                # Do not leave water/secondary storage inside a replaced block.
                for layer in layers[1:]:
                    layer[index] = AIR
            for (x,y,z),extra in layer_groups[dimension,cx,sy,cz].items():
                if len(extra)>7:raise ValueError('Too many extra block layers')
                index=((x&15)<<8)|((z&15)<<4)|(y&15)
                while len(layers)<=len(extra):layers.append([AIR]*4096)
                for i,layer in enumerate(layers[1:]):layer[index]=extra[i] if i<len(extra) else AIR
            prefix = self.prefix(cx, cz, dimension)
            values[prefix + b"/" + struct.pack("b", sy)] = encode_bedrock(version, sy, layers, palettes)
            changed_chunks[prefix].update(changes)
        replacements = defaultdict(dict)
        for (dimension,x,y,z),value in entity_edits.items():
            prefix = self.prefix(x//16,z//16,dimension)
            changed_chunks[prefix].add((x,y,z))
            replacements[prefix][(x,y,z)] = value
        for prefix, positions in changed_chunks.items():
            key = prefix + b"1"  # concatenated block entity NBT roots
            kept = bytearray()
            if key in values:
                reader = nbt.Reader(values[key], little=True)
                while reader.pos < len(reader.data):
                    name, tag = reader.root()
                    position = tuple(nbt.get(tag, axis, 0) for axis in "xyz")
                    if position not in positions:
                        kept.extend(nbt.dumps(tag, name, little=True))
            for position,value in replacements[prefix].items():
                if value is not None:
                    kept.extend(nbt.dumps(validate_entity(value,position),little=True))
            values[key] = bytes(kept)
        shutil.rmtree(stage / "db")
        write_database(stage / "db", values)


def open_world(path):
    path = Path(path).expanduser().resolve()
    if not (path / "level.dat").is_file():
        raise ValueError("Choose a world folder containing level.dat")
    if (path / "db" / "CURRENT").is_file():
        return BedrockWorld(path)
    return JavaWorld(path)


def validate_entity(value,position):
    _,tag = nbt.loads(value)
    if tag.kind != nbt.COMPOUND or not isinstance(nbt.get(tag,"id"),str):
        raise ValueError("Invalid block entity NBT")
    if tuple(nbt.get(tag,axis) for axis in "xyz") != tuple(position):
        raise ValueError("Block entity coordinates disagree with their target")
    return tag
