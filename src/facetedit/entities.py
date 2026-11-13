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


def transform(data,size,turns=0,mirror=False,block=None):
    if not turns%4 and not mirror:return data
    from .transforms import point
    name,tag=nbt.loads(data)
    position=tuple(nbt.get(tag,axis) for axis in 'xyz')
    if any(type(v) is not int for v in position):raise ValueError('Invalid block entity coordinates')
    if 'pairx' in tag.value or 'pairz' in tag.value:
        pair=(nbt.get(tag,'pairx',position[0]),position[1],nbt.get(tag,'pairz',position[2]))
        if any(type(v) is not int for v in pair):raise ValueError('Invalid paired-container coordinates')
        target=point(pair,size,turns,mirror)
        tag.value['pairx']=nbt.Tag(nbt.INT,target[0]);tag.value['pairz']=nbt.Tag(nbt.INT,target[2])
    for key in ('Rot',):
        if key in tag.value:
            old=tag.value[key]
            if old.kind in (nbt.BYTE,nbt.SHORT,nbt.INT):
                tag.value[key]=nbt.Tag(old.kind,((-old.value if mirror else old.value)+4*turns)%16)
    if nbt.get(tag,'id')=='ShulkerBox' and 'facing' in tag.value:
        from .transforms import horizontal
        order=('down','up','north','south','west','east');old=tag.value['facing']
        if old.kind!=nbt.BYTE or not 0<=old.value<6:raise ValueError('Invalid Shulker Box facing byte')
        tag.value['facing']=nbt.Tag(nbt.BYTE,order.index(horizontal(order[old.value],turns,mirror)))
    if nbt.get(tag,'id')=='Skull' and 'Rotation' in tag.value:
        if block is None:raise ValueError('Skull rotation requires its block mount state')
        if dict(block.properties).get('facing_direction')=='1':
            old=tag.value['Rotation']
            if old.kind!=nbt.FLOAT:raise ValueError('Invalid skull Rotation type')
            value=((-old.value if mirror else old.value)+90*turns)%360
            tag.value['Rotation']=nbt.Tag(nbt.FLOAT,value if value<=180 else value-360)
    for axis,value in zip('xyz',point(position,size,turns,mirror)):tag.value[axis]=nbt.Tag(nbt.INT,value)
    return nbt.dumps(tag,name)
