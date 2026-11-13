"""Block-entity relocation without changing payload types or inventory data."""

from . import nbt


def relocate(data, position):
    _, tag = nbt.loads(data)
    if tag.kind != nbt.COMPOUND or not isinstance(nbt.get(tag, "id"), str):
        raise ValueError("Block NBT requires a compound and a string id")
    old = tuple(nbt.get(tag, axis, position[i]) for i, axis in enumerate("xyz"))
    if any(type(v) is not int for v in old):
        raise ValueError("Invalid block-entity coordinates")
    # Bedrock double-chest links use absolute X/Z coordinates. Other opaque
    # payloads are retained; arbitrary embedded world references are not moved.
    for key, axis in (("pairx", 0), ("pairz", 2)):
        if key in tag.value:
            child = tag.value[key]
            if child.kind != nbt.INT:
                raise ValueError("Invalid paired-container coordinate")
            tag.value[key] = nbt.Tag(nbt.INT, child.value + position[axis] - old[axis])
    for axis, value in zip("xyz", position):
        tag.value[axis] = nbt.Tag(nbt.INT, value)
    return nbt.dumps(tag)


def validate_local(position, size, blocks, entities):
    if len(position) != 3 or any(type(n) is not int or not 0 <= n < size[i] for i, n in enumerate(position)):
        raise ValueError("Block entity lies outside the structure bounds")
    if position not in blocks or blocks[position].air or position in entities:
        raise ValueError("Block entity is duplicated or has no non-air block")
