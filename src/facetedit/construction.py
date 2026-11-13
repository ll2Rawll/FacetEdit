"""Independent, bounded codec for native-edition .construction version 0.

The format stores gzip NBT sections, a native block palette and a trailing NBT
index. It does not require Amulet's universal block representation. Moving
entities/universal-edition files are refused until their semantics are supported.
"""
import itertools
from pathlib import Path
import struct

from . import nbt
from .blocks import AIR, Block
from .entities import relocate
from .formats import bedrock_block, bedrock_entry
from .model import Clipboard, MAX_OPERATION
from .registry import JAVA_RELEASES
from .structures import atomic_write

MAGIC = b'constrct'
INDEX = struct.Struct('<iiibbbii')
LIMIT = 64 * 1024 * 1024


def field(tag, name, kind):
    result = tag.value.get(name) if tag.kind == nbt.COMPOUND else None
    if result is None or result.kind != kind:
        raise nbt.FormatError(f'Construction field {name} needs NBT type {kind}')
    return result.value


def positions(origin, shape):
    return itertools.product(*(range(p, p+n) for p, n in zip(origin, shape)))


def rectangles(points):
    """Cover an exact voxel mask with nonoverlapping rectangles within sections."""
    remaining = set(points)
    for start in sorted(points):
        if start not in remaining:
            continue
        x, y, z = start
        end = [x+1, y+1, z+1]
        for axis in (2, 1, 0):
            while end[axis] % 16:
                lo, hi = list(start), list(end)
                lo[axis] = end[axis]
                hi[axis] += 1
                plane = tuple(positions(lo, tuple(b-a for a, b in zip(lo, hi))))
                if not all(p in remaining for p in plane):
                    break
                end[axis] += 1
        shape = tuple(b-a for a, b in zip(start, end))
        remaining.difference_update(positions(start, shape))
        yield start, shape


def _palette_block(entry, edition, legacy):
    tag = nbt.Tag(nbt.COMPOUND, entry)
    namespace, name = field(tag, 'namespace', nbt.STRING), field(tag, 'blockname', nbt.STRING)
    props = field(tag, 'properties', nbt.COMPOUND)
    if edition == 'Bedrock':
        return bedrock_block(nbt.compound(name=nbt.Tag(nbt.STRING, namespace+':'+name), states=nbt.Tag(nbt.COMPOUND, props)))
    if legacy:
        if set(props) - {'block_data'} or ('block_data' in props and props['block_data'].kind != nbt.INT):
            raise nbt.FormatError('Unsupported numeric Java construction properties')
        value = props.get('block_data', nbt.Tag(nbt.INT, 0)).value
        block = Block(namespace+':'+name, (('legacy_data', str(value)),)) if value else Block(namespace+':'+name)
        from .legacy import identifier
        identifier(block)
        return block
    if any(value.kind != nbt.STRING for value in props.values()):
        raise nbt.FormatError('Modern Java construction properties must be strings')
    return Block(namespace+':'+name, tuple((k, v.value) for k, v in props.items()))


def load_construction(path):
    path = Path(path)
    if path.stat().st_size > LIMIT:
        raise nbt.FormatError('Construction exceeds 64 MiB')
    raw = path.read_bytes()
    if len(raw) < 22 or raw[:8] != MAGIC or raw[-8:] != MAGIC or raw[8] != 0:
        raise nbt.FormatError('Expected construction version 0 header and footer')
    offset = struct.unpack('>I', raw[-12:-8])[0]
    if not 9 <= offset < len(raw)-12:
        raise nbt.FormatError('Construction metadata offset is out of bounds')
    budget = 0
    def decode(data):
        nonlocal budget
        data = nbt.decompress(data, 'gzip' if data[:2] == b'\x1f\x8b' else 'raw', LIMIT-budget)
        budget += len(data)
        return nbt.loads(data)[1]
    metadata = decode(raw[offset:-12])
    if field(metadata, 'section_version', nbt.BYTE) != 0:
        raise nbt.FormatError('Unsupported construction section version')
    export = nbt.Tag(nbt.COMPOUND, field(metadata, 'export_version', nbt.COMPOUND))
    edition = field(export, 'edition', nbt.STRING)
    if edition not in ('java', 'bedrock'):
        raise nbt.FormatError('Construction must declare a native java or bedrock edition')
    edition = edition.title()
    version = field(export, 'version', nbt.LIST)
    if version.kind != nbt.INT or len(version.values) not in (2,3,4) or any(v < 0 for v in version.values):
        raise nbt.FormatError('Invalid construction game version')
    game_version = tuple(version.values)
    normalized = (*game_version, 0)[:3] if len(game_version) == 2 else game_version[:3]
    data_version = next((dv for dv, release in JAVA_RELEASES.items() if release == normalized), None) if edition == 'Java' else None
    if edition == 'Java' and data_version is None:
        raise nbt.FormatError(f'Unknown Java construction release {game_version}')
    boxes = field(metadata, 'selection_boxes', nbt.INT_ARRAY)
    if not boxes or len(boxes) % 6 or len(boxes) > MAX_OPERATION*6:
        raise nbt.FormatError('Invalid construction selection boxes')
    selected = set()
    declared_volume = 0
    for i in range(0, len(boxes), 6):
        lo, hi = boxes[i:i+3], boxes[i+3:i+6]
        shape = tuple(b-a for a, b in zip(lo, hi))
        if min(shape) <= 0 or shape[0]*shape[1]*shape[2] > MAX_OPERATION:
            raise nbt.FormatError('Invalid or excessive construction selection')
        declared_volume += shape[0]*shape[1]*shape[2]
        if declared_volume > MAX_OPERATION:
            raise nbt.FormatError('Construction boxes exceed the cumulative block limit')
        selected.update(positions(lo, shape))
        if len(selected) > MAX_OPERATION:
            raise nbt.FormatError('Construction selection exceeds 65,536 blocks')
    minimum = tuple(min(p[a] for p in selected) for a in range(3))
    size = tuple(max(p[a] for p in selected)-minimum[a]+1 for a in range(3))
    palette = field(metadata, 'block_palette', nbt.LIST)
    if palette.kind != nbt.COMPOUND or not 1 <= len(palette.values) <= MAX_OPERATION*8:
        raise nbt.FormatError('Invalid construction palette')
    entries = [_palette_block(e, edition, data_version is not None and data_version < 1451) for e in palette.values]
    references = []
    for entry in palette.values:
        extra = field(nbt.Tag(nbt.COMPOUND, entry), 'extra_blocks', nbt.LIST)
        if extra.values and extra.kind != nbt.INT or len(extra.values) > 7 or any(not 0 <= i < len(entries) for i in extra.values):
            raise nbt.FormatError('Invalid construction extra layer reference')
        references.append(extra.values)
    if any(references[ref] for refs in references for ref in refs):
        raise nbt.FormatError('Nested or cyclic construction extra layers')
    if edition == 'Java' and any(references):
        raise nbt.FormatError('Native Java construction cannot contain extra layers')
    index = field(metadata, 'section_index_table', nbt.BYTE_ARRAY)
    if len(index) % INDEX.size or len(index)//INDEX.size > MAX_OPERATION:
        raise nbt.FormatError('Invalid construction section index size')
    blocks = {p: AIR for p in selected}
    extras, entities, visited, spans = {}, {}, set(), []
    for x, y, z, sx, sy, sz, begin, length in INDEX.iter_unpack(index):
        shape, origin = (sx, sy, sz), (x, y, z)
        if any(not 1 <= n <= 16 for n in shape) or any(p//16 != (p+n-1)//16 for p, n in zip(origin, shape)):
            raise nbt.FormatError('Construction section crosses subchunk bounds')
        if begin < 9 or length <= 0 or begin+length > offset:
            raise nbt.FormatError('Construction section payload lies outside the file')
        spans.append((begin, begin+length))
        section = decode(raw[begin:begin+length])
        actors = field(section, 'entities', nbt.LIST)
        if actors.values:
            raise nbt.FormatError('Moving entities in construction files are not implemented')
        array_type = field(section, 'blocks_array_type', nbt.BYTE)
        if array_type == -1:
            continue
        if array_type not in (nbt.BYTE_ARRAY, nbt.INT_ARRAY, nbt.LONG_ARRAY):
            raise nbt.FormatError('Invalid construction block array type')
        indices = field(section, 'blocks', array_type)
        if len(indices) != sx*sy*sz or any(not 0 <= i < len(entries) or array_type == nbt.BYTE_ARRAY and i > 127 for i in indices):
            raise nbt.FormatError('Invalid construction block indices')
        for pos, state in zip(positions(origin, shape), indices):
            if pos not in selected:
                continue
            if pos in visited:
                raise nbt.FormatError('Overlapping construction sections')
            visited.add(pos)
            blocks[pos] = entries[state]
            if references[state]:
                extras[pos] = tuple(entries[i] for i in references[state])
        block_entities = field(section, 'block_entities', nbt.LIST)
        if block_entities.values and block_entities.kind != nbt.COMPOUND:
            raise nbt.FormatError('Invalid construction block entities')
        for item in block_entities.values:
            wrapper = nbt.Tag(nbt.COMPOUND, item)
            pos = tuple(field(wrapper, axis, nbt.INT) for axis in 'xyz')
            if pos not in selected:
                continue
            if pos in entities or blocks[pos].air or any(not p <= v < p+n for v,p,n in zip(pos,origin,shape)):
                raise nbt.FormatError('Duplicate or misplaced construction block entity')
            data = nbt.Tag(nbt.COMPOUND, dict(field(wrapper, 'nbt', nbt.COMPOUND)))
            if 'id' not in data.value:
                ns, name = field(wrapper, 'namespace', nbt.STRING), field(wrapper, 'base_name', nbt.STRING)
                data.value['id'] = nbt.Tag(nbt.STRING, ns+':'+name if ns else name)
            entities[pos] = nbt.dumps(data)
    spans.sort()
    if any(b > c for (_, b), (c, _) in zip(spans, spans[1:])):
        raise nbt.FormatError('Overlapping construction payload ranges')
    def local(p):
        return tuple(a-b for a,b in zip(p, minimum))
    return Clipboard(size, {local(p): b for p,b in blocks.items()}, edition, minimum,
                     {local(p): relocate(b, local(p)) for p,b in entities.items()}, data_version,
                     {local(p): b for p,b in extras.items()}, normalized)


def save_construction(clip, path):
    if clip.edition not in ('Java', 'Bedrock'):
        raise ValueError('Construction export requires a native edition')
    version = JAVA_RELEASES.get(clip.data_version) if clip.edition == 'Java' else clip.game_version
    if not version:
        raise ValueError('Construction export needs a known game release version')
    if not clip.blocks or len(clip.blocks) > MAX_OPERATION:
        raise ValueError('Construction must contain 1–65,536 selected blocks')
    if any(len(p) != 3 or any(type(v) is not int or not 0 <= v < clip.size[a] for a,v in enumerate(p)) for p in clip.blocks):
        raise ValueError('Construction blocks lie outside the clipboard bounds')
    if not clip.entities.keys() <= clip.blocks.keys() or not clip.extra_blocks.keys() <= clip.blocks.keys():
        raise ValueError('Construction payload lies outside its selection mask')
    if clip.edition == 'Java' and clip.extra_blocks:
        raise ValueError('Java construction cannot contain extra layers')
    origin = clip.offset
    absolute = {tuple(a+b for a,b in zip(p, origin)): p for p in clip.blocks}
    if any(any(not -2**31 <= a < 2**31-16 for a in p) for p in absolute):
        raise ValueError('Construction coordinates exceed signed 32-bit bounds')
    palette, lookup = [], {}
    def entry(block, extra=()):
        key = (block, tuple(extra))
        if key in lookup:
            return lookup[key]
        if len(extra) > 7:
            raise ValueError('Construction supports at most eight block layers')
        refs = [entry(b) for b in extra]
        namespace, name = block.name.split(':', 1)
        if clip.edition == 'Bedrock':
            props = bedrock_entry(block).value['states']
        elif clip.data_version < 1451:
            from .legacy import identifier
            _, value = identifier(block)
            props = nbt.compound(block_data=nbt.Tag(nbt.INT, value))
        else:
            props = nbt.Tag(nbt.COMPOUND, {k: nbt.Tag(nbt.STRING, v) for k,v in block.properties})
        result = len(palette)
        palette.append({'namespace': nbt.Tag(nbt.STRING, namespace), 'blockname': nbt.Tag(nbt.STRING, name),
                        'properties': props, 'extra_blocks': nbt.Tag(nbt.LIST, nbt.ListValue(nbt.INT, refs))})
        lookup[key] = result
        return result
    # Resolve the full palette before choosing the smallest unsigned index array.
    states = {p: entry(b, clip.extra_blocks.get(p, ())) for p,b in clip.blocks.items()}
    kind = nbt.BYTE_ARRAY if len(palette) <= 128 else nbt.INT_ARRAY
    raw, index, boxes = bytearray(MAGIC+b'\0'), bytearray(), []
    for start, shape in rectangles(absolute):
        cells = list(positions(start, shape))
        values = [states[absolute[p]] for p in cells]
        entities = []
        for p in cells:
            local = absolute[p]
            if local not in clip.entities:
                continue
            if clip.blocks[local].air:
                raise ValueError('Construction block entity is attached to air')
            tag = nbt.loads(relocate(clip.entities[local], p))[1]
            identity = nbt.get(tag, 'id')
            ns, _, name = identity.rpartition(':')
            record = {'namespace': nbt.Tag(nbt.STRING, ns), 'base_name': nbt.Tag(nbt.STRING, name), 'nbt': tag}
            record.update({axis: nbt.Tag(nbt.INT, value) for axis,value in zip('xyz', p)})
            entities.append(record)
        section = nbt.compound(blocks_array_type=nbt.Tag(nbt.BYTE, kind), blocks=nbt.Tag(kind, bytes(values) if kind == nbt.BYTE_ARRAY else values),
            entities=nbt.Tag(nbt.LIST, nbt.ListValue(nbt.COMPOUND, [])), block_entities=nbt.Tag(nbt.LIST, nbt.ListValue(nbt.COMPOUND, entities)))
        payload = nbt.dumps(section, compressed=True)
        index.extend(INDEX.pack(*start, *shape, len(raw), len(payload)))
        raw.extend(payload)
        boxes.extend((*start, *(a+b for a,b in zip(start, shape))))
        if len(raw) > LIMIT:
            raise ValueError('Construction exceeds 64 MiB')
    metadata = nbt.compound(created_with=nbt.Tag(nbt.STRING, 'FacetEdit'), selection_boxes=nbt.Tag(nbt.INT_ARRAY, boxes),
        section_version=nbt.Tag(nbt.BYTE, 0), export_version=nbt.compound(edition=nbt.Tag(nbt.STRING, clip.edition.lower()), version=nbt.Tag(nbt.LIST, nbt.ListValue(nbt.INT, list(version)))),
        section_index_table=nbt.Tag(nbt.BYTE_ARRAY, bytes(index)), block_palette=nbt.Tag(nbt.LIST, nbt.ListValue(nbt.COMPOUND, palette)))
    offset = len(raw)
    raw.extend(nbt.dumps(metadata, compressed=True))
    raw.extend(struct.pack('>I', offset)+MAGIC)
    if len(raw) > LIMIT:
        raise ValueError('Construction exceeds 64 MiB')
    atomic_write(path, raw)
