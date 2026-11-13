"""Paletted Java sections and persistent Bedrock subchunks, written independently."""

import math
import struct

from .blocks import AIR, Block
from .nbt import BYTE, COMPOUND, INT, LIST, LONG_ARRAY, STRING, FormatError, ListValue, Reader, Tag, dumps, get


def unpack_indices(words, bits, count=4096, width=64, padded=True):
    if bits == 0:
        return [0] * count
    per_word = width // bits
    needed = math.ceil(count / per_word) if padded else math.ceil(count * bits / width)
    if len(words) != needed:
        raise FormatError(f"Packed palette has {len(words)} words, expected {needed}")
    mask = (1 << bits) - 1
    unsigned = [w & ((1 << width) - 1) for w in words]
    result = []
    for index in range(count):
        if padded:
            result.append(unsigned[index // per_word] >> ((index % per_word) * bits) & mask)
        else:
            start = index * bits
            word, shift = divmod(start, width)
            value = unsigned[word] >> shift
            if shift + bits > width:
                value |= unsigned[word + 1] << (width - shift)
            result.append(value & mask)
    return result


def pack_indices(indices, bits, width=64, padded=True):
    if bits == 0:
        return []
    per_word = width // bits
    count = math.ceil(len(indices) / per_word) if padded else math.ceil(len(indices) * bits / width)
    words = [0] * count
    for i, value in enumerate(indices):
        if not 0 <= value < 1 << bits:
            raise FormatError("Palette index exceeds storage width")
        if padded:
            words[i // per_word] |= value << ((i % per_word) * bits)
        else:
            word, shift = divmod(i * bits, width)
            words[word] |= value << shift
            if shift + bits > width:
                words[word + 1] |= value >> (width - shift)
    mask = (1 << width) - 1
    return [(w & mask) - (1 << width) if (w & (1 << (width - 1))) else w & mask for w in words]


def java_block(entry):
    tag = Tag(COMPOUND, entry)
    name = get(tag, "Name")
    if not isinstance(name, str):
        raise FormatError("Java palette entry has no Name")
    props = get(tag, "Properties", {})
    if any(v.kind != STRING for v in props.values()):
        raise FormatError("Java block properties must be strings")
    return Block(name, tuple((k, v.value) for k, v in props.items()))


def java_entry(block):
    entry = {"Name": Tag(STRING, block.name)}
    if block.properties:
        entry["Properties"] = Tag(COMPOUND, {k: Tag(STRING, v) for k, v in block.properties})
    return entry


def decode_java_section(section, version):
    if version<1451:
        from .legacy import decode_section
        return decode_section(section)
    modern = version >= 2834
    section = Tag(COMPOUND, section)
    states = section.value.get("block_states") if modern else section
    if states is None:
        return [AIR] * 4096
    palette_tag = states.value.get("palette" if modern else "Palette")
    if palette_tag is None:
        return [AIR] * 4096
    if palette_tag.kind != LIST or palette_tag.value.kind != COMPOUND:
        raise FormatError("Invalid Java block palette")
    palette = [java_block(e) for e in palette_tag.value.values]
    if not palette or len(palette) > 4096:
        raise FormatError("Invalid Java palette size")
    words = get(states, "data" if modern else "BlockStates", [])
    if len(palette) == 1 and not words:
        return palette * 4096
    bits = max(4, (len(palette) - 1).bit_length())
    indexes = unpack_indices(words, bits, padded=version >= 2529)
    if max(indexes) >= len(palette):
        raise FormatError("Java block palette index out of range")
    return [palette[i] for i in indexes]


def encode_java_section(section, blocks, version):
    if len(blocks) != 4096:
        raise ValueError("A chunk section has 4096 blocks")
    if version<1451:
        from .legacy import encode_section
        return encode_section(section,blocks)
    palette = list(dict.fromkeys(blocks))
    lookup = {block: i for i, block in enumerate(palette)}
    bits = max(4, (len(palette) - 1).bit_length())
    words = pack_indices([lookup[b] for b in blocks], bits, padded=version >= 2529)
    palette_tag = Tag(LIST, ListValue(COMPOUND, [java_entry(b) for b in palette]))
    if version >= 2834:
        states = {"palette": palette_tag}
        if len(palette) > 1:
            states["data"] = Tag(LONG_ARRAY, words)
        section["block_states"] = Tag(COMPOUND, states)
    else:
        section["Palette"] = palette_tag
        section["BlockStates"] = Tag(LONG_ARRAY, words)
    section.pop("BlockLight", None)
    section.pop("SkyLight", None)


def decode_java_biomes(section):
    states = section.get("biomes")
    if states is None:
        return ["minecraft:plains"] * 64
    palette = get(states,"palette")
    if palette is None or palette.kind != STRING or not 1 <= len(palette.values) <= 64:
        raise FormatError("Invalid Java biome palette")
    entries = palette.values
    words = get(states,"data",[])
    if len(entries) == 1 and not words:
        return entries * 64
    indices = unpack_indices(words,max(1,(len(entries)-1).bit_length()),count=64)
    if max(indices) >= len(entries):
        raise FormatError("Java biome palette index is out of range")
    return [entries[i] for i in indices]


def encode_java_biomes(section, biomes):
    if len(biomes) != 64:
        raise ValueError("A modern Java section contains 64 biome cells")
    palette = list(dict.fromkeys(biomes))
    lookup = {name:i for i,name in enumerate(palette)}
    data = {"palette": Tag(LIST,ListValue(STRING,palette))}
    if len(palette) > 1:
        data["data"] = Tag(LONG_ARRAY,pack_indices([lookup[b] for b in biomes],max(1,(len(palette)-1).bit_length())))
    section["biomes"] = Tag(COMPOUND,data)


def bedrock_block(tag):
    name = get(tag, "name")
    if not isinstance(name, str):
        raise FormatError("Bedrock palette entry has no name")
    states = get(tag, "states", {})
    properties = []
    for k, v in states.items():
        if v.kind not in (BYTE, INT, STRING):
            raise FormatError("Unsupported Bedrock block state type")
        value = ("true" if v.value else "false") if v.kind == BYTE else str(v.value)
        properties.append((k, value))
    return Block(name, tuple(properties), tuple((k, v.kind) for k, v in states.items()))


def bedrock_entry(block, version=17959425):
    states = {}
    types = dict(block.state_types)
    for key, val in block.properties:
        if types.get(key) == STRING:
            states[key] = Tag(STRING, val)
        elif types.get(key) == INT:
            states[key] = Tag(INT, int(val))
        elif val in ("true", "false"):
            states[key] = Tag(BYTE, int(val == "true"))
        else:
            try:
                states[key] = Tag(INT, int(val))
            except ValueError:
                states[key] = Tag(STRING, val)
    return Tag(COMPOUND, {"name": Tag(STRING, block.name), "states": Tag(COMPOUND, states), "version": Tag(INT, version)})


def decode_bedrock(raw):
    reader = Reader(raw, little=True)
    version = reader.number("B")
    if version not in (8, 9):
        raise FormatError(f"Bedrock subchunk version {version} is not supported; expected 8 or 9")
    count = reader.number("B")
    if not 1 <= count <= 8:
        raise FormatError("Invalid Bedrock storage layer count")
    y = reader.number("b") if version == 9 else None
    layers = []
    palettes = []
    for _ in range(count):
        header = reader.number("B")
        bits = header >> 1
        if header & 1 or bits not in (0, 1, 2, 3, 4, 5, 6, 8, 16):
            raise FormatError("Unsupported runtime or inherited Bedrock palette")
        word_count = math.ceil(4096 / (32 // bits)) if bits else 0
        words = [reader.number("i") for _ in range(word_count)]
        # The singleton (zero-bit) persistent encoding omits palette length.
        palette_count = reader.number("i") if bits else 1
        if not 1 <= palette_count <= 4096:
            raise FormatError("Invalid Bedrock palette length")
        palette_tags = [reader.root()[1] for _ in range(palette_count)]
        palette = [bedrock_block(tag) for tag in palette_tags]
        indexes = unpack_indices(words, bits, width=32)
        if max(indexes) >= len(palette):
            raise FormatError("Bedrock palette index out of range")
        layers.append([palette[i] for i in indexes])
        palettes.append(palette_tags)
    if reader.pos != len(raw):
        raise FormatError("Trailing Bedrock subchunk data")
    return version, y, layers, palettes


def encode_bedrock(version, y, layers, original_palettes=()):
    out = bytearray((version, len(layers)))
    if version == 9:
        out.extend(struct.pack("b", y))
    for layer_index, blocks in enumerate(layers):
        if len(blocks) != 4096:
            raise ValueError("Bedrock storage must contain 4096 blocks")
        palette = list(dict.fromkeys(blocks))
        lookup = {block: i for i, block in enumerate(palette)}
        required = (len(palette) - 1).bit_length()
        bits = next(b for b in (0, 1, 2, 3, 4, 5, 6, 8, 16) if b >= required)
        out.append(bits << 1)
        words = pack_indices([lookup[b] for b in blocks], bits, width=32)
        out.extend(struct.pack("<" + str(len(words)) + "i", *words))
        if bits:
            out.extend(struct.pack("<i", len(palette)))
        originals = original_palettes[layer_index] if layer_index < len(original_palettes) else []
        tags = {bedrock_block(t): t for t in originals}
        block_version = max((get(t, "version", 17959425) for t in originals), default=17959425)
        for block in palette:
            out.extend(dumps(tags.get(block, bedrock_entry(block, block_version)), little=True))
    return bytes(out)
