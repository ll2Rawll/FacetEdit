"""Transactional editing, bounded history and coordinate-correct clipboard."""

from dataclasses import dataclass, field

from .blocks import AIR
from . import nbt
from .entities import relocate

MAX_OPERATION = 65_536
MAX_HISTORY = 262_144
MAX_PENDING = 262_144


@dataclass(frozen=True)
class Selection:
    a: tuple[int, int, int]
    b: tuple[int, int, int]

    @property
    def minimum(self):
        return tuple(min(a, b) for a, b in zip(self.a, self.b))

    @property
    def maximum(self):
        return tuple(max(a, b) for a, b in zip(self.a, self.b))

    @property
    def size(self):
        return tuple(b - a + 1 for a, b in zip(self.minimum, self.maximum))

    @property
    def volume(self):
        x, y, z = self.size
        return x * y * z

    def positions(self):
        if self.volume > MAX_OPERATION:
            raise ValueError(f"Select at most {MAX_OPERATION:,} blocks per operation")
        lo, hi = self.minimum, self.maximum
        for y in range(lo[1], hi[1] + 1):
            for z in range(lo[2], hi[2] + 1):
                for x in range(lo[0], hi[0] + 1):
                    yield x, y, z


@dataclass
class Transaction:
    label: str
    dimension: str
    changes: list
    entity_changes: list = field(default_factory=list)
    biome_changes: list = field(default_factory=list)

    @property
    def count(self):
        return len(self.changes) + len(self.entity_changes) + len(self.biome_changes)


@dataclass
class Clipboard:
    size: tuple
    blocks: dict
    edition: str = "Java"
    offset: tuple = (0,0,0)
    entities: dict = field(default_factory=dict)
    data_version: int | None = 4189

    def transformed(self, turns=0, mirror=False):
        if self.entities and (turns%4 or mirror):
            raise ValueError("Block-entity rotation is not implemented; paste without rotation or mirroring")
        if self.offset != (0,0,0) and (turns%4 or mirror):
            raise ValueError("Rotation of a schematic with a nonzero paste offset is not implemented")
        result = {}
        width, height, depth = self.size
        for (x, y, z), block in self.blocks.items():
            if mirror:
                x = width - 1 - x
            w, d = width, depth
            for _ in range(turns % 4):
                x, z = d - 1 - z, x
                w, d = d, w
            result[(x, y, z)] = block.transform(turns, mirror)
        return Clipboard((depth, height, width) if turns % 2 else self.size, result, self.edition,self.offset,dict(self.entities),self.data_version)


class Document:
    def __init__(self, world):
        self.world = world
        self.dimension = world.dimensions[0]
        self.edits = {}
        self.entity_edits = {}
        self.biome_edits = {}
        self.undo_stack = []
        self.redo_stack = []
        self.clipboard = None
        self.selection = None
        self.revision = 0

    @property
    def pending_count(self):
        return len(self.edits) + len(self.entity_edits) + len(self.biome_edits)

    def get_entity(self, x, y, z):
        key = (self.dimension,x,y,z)
        if key in self.entity_edits:
            return self.entity_edits[key]
        if key in self.edits:
            return None
        return self.world.get_block_entity(x,y,z,self.dimension)

    def get_biome(self, x, y, z):
        x,y,z = (v//4*4 for v in (x,y,z))
        key = (self.dimension,x,y,z)
        return self.biome_edits[key] if key in self.biome_edits else self.world.get_biome(x,y,z,self.dimension)

    def get(self, x, y, z):
        key = (self.dimension, x, y, z)
        if key in self.edits:
            return self.edits[key]
        return self.world.get_block(x, y, z, self.dimension)

    def apply(self, label, requested, entity_updates=()):
        changes = []
        seen = set()
        for position, after in requested:
            if len(seen) >= MAX_OPERATION:
                raise ValueError(f"Operation exceeds {MAX_OPERATION:,} blocks")
            if position in seen:
                raise ValueError("Duplicate coordinate in transaction")
            seen.add(position)
            self.world.validate_edit(position, self.dimension)
            before = self.get(*position)
            if not after.state_types and (after.name, after.properties) == (before.name, before.properties):
                after = before  # Preserve Bedrock's typed metadata for a textual no-op.
            if before != after:
                changes.append((position, before, after))
        entities = {}
        changed_positions = {position for position,_,_ in changes}
        for position, _, _ in changes:
            before = self.get_entity(*position)
            if before is not None:
                entities[position] = (position,before,None)
        for position, after in entity_updates:
            if position not in seen:
                raise ValueError("Entity update must accompany a requested block")
            if after is not None:
                from .world import validate_entity
                validate_entity(after,position)
            before = self.get_entity(*position)
            if before != after or (after is not None and position in changed_positions):
                entities[position] = (position,before,after)
            else:
                entities.pop(position,None)
        transaction = Transaction(label, self.dimension, changes, list(entities.values()))
        return self._commit(transaction)

    def _commit(self, transaction):
        if transaction.count == 0:
            return 0
        self._apply(transaction, forward=True)
        self.undo_stack.append(transaction)
        self.redo_stack.clear()
        while sum(t.count for t in self.undo_stack) > MAX_HISTORY:
            self.undo_stack.pop(0)
        return len(transaction.changes) or len(transaction.entity_changes) or len(transaction.biome_changes)

    def _apply(self, transaction, forward):
        # Baselines are loaded before changing the edit map, keeping undo atomic.
        updates = []
        final_blocks = {}
        explicit_entity = object()
        for changes,target,getter in ((transaction.changes,self.edits,self.world.get_block),
                                      (transaction.entity_changes,self.entity_edits,self.world.get_block_entity),
                                      (transaction.biome_changes,self.biome_edits,self.world.get_biome)):
            for pos, before, after in changes:
                value = after if forward else before
                baseline = getter(*pos, transaction.dimension)
                key = (transaction.dimension,*pos)
                if target is self.edits:
                    final_blocks[key] = value != baseline
                elif target is self.entity_edits and value is not None and final_blocks.get(key,key in self.edits):
                    # Replacing a block erases its original NBT. An explicit
                    # replacement is required even when its bytes are unchanged.
                    baseline = explicit_entity
                updates.append((target,key,value,baseline))
        resulting_size = self.pending_count
        for target,key,value,baseline in updates:
            resulting_size += int(value != baseline) - int(key in target)
        if resulting_size > MAX_PENDING:
            raise ValueError(f"This project exceeds {MAX_PENDING:,} pending blocks. Export a copy and reopen it to continue")
        for target,key,value,baseline in updates:
            if value == baseline:
                target.pop(key, None)
            else:
                target[key] = value
        self.revision += 1

    def undo(self):
        if not self.undo_stack:
            return None
        transaction = self.undo_stack[-1]
        self._apply(transaction, False)
        self.undo_stack.pop()
        self.redo_stack.append(transaction)
        return transaction.label

    def redo(self):
        if not self.redo_stack:
            return None
        transaction = self.redo_stack[-1]
        self._apply(transaction, True)
        self.redo_stack.pop()
        self.undo_stack.append(transaction)
        return transaction.label

    def require_selection(self):
        if self.selection is None:
            raise ValueError("Select two corners in the viewport or enter coordinates first")
        return self.selection

    def fill(self, block, replace=None):
        positions = self.require_selection().positions()
        def matches(position):
            if replace is None:
                return True
            current = self.get(*position)
            if replace.state_types:
                return current == replace
            return (current.name, current.properties) == (replace.name, replace.properties)
        return self.apply("Replace blocks" if replace else "Fill selection", (
            (pos, block) for pos in positions if matches(pos)
        ))

    def delete(self):
        return self.apply("Delete selection", ((p, AIR) for p in self.require_selection().positions()))

    def copy(self):
        selection = self.require_selection()
        origin = selection.minimum
        blocks,entities = {},{}
        for p in selection.positions():
            if (self.dimension,*p) not in self.edits:
                self.world.validate_copy(p,self.dimension)
            local = tuple(p[i]-origin[i] for i in range(3))
            blocks[local] = self.get(*p)
            entity = self.get_entity(*p)
            if entity is not None:
                entities[local] = relocate(entity,local)
        bedrock = self.world.edition.startswith("Bedrock")
        self.clipboard = Clipboard(selection.size,blocks,"Bedrock" if bedrock else "Java",entities=entities,data_version=None if bedrock else getattr(self.world,"version",4189))
        return len(blocks)

    def cut(self):
        self.copy()
        return self.apply("Cut selection", ((p, AIR) for p in self.selection.positions()))

    def paste(self, origin=None, turns=0, mirror=False, include_air=False):
        if self.clipboard is None:
            raise ValueError("Copy a selection or import a structure first")
        edition = "Bedrock" if self.world.edition.startswith("Bedrock") else "Java"
        if self.clipboard.edition != edition:
            raise ValueError("Cross-edition clipboard translation is not implemented")
        if edition=="Java" and self.clipboard.data_version != getattr(self.world,"version",4189):
            raise ValueError("Cross-version block translation is not implemented; the structure and world must have the same Java DataVersion")
        if edition == "Bedrock" and (turns % 4 or mirror):
            raise ValueError("Bedrock directional-state transforms are not implemented; paste without rotation or mirroring")
        origin = origin or self.require_selection().minimum
        clip = self.clipboard.transformed(turns, mirror)
        origin = tuple(origin[i]+clip.offset[i] for i in range(3))
        blocks,entities = [],[]
        for pos,block in clip.blocks.items():
            if include_air or not block.air:
                target = tuple(pos[i]+origin[i] for i in range(3))
                blocks.append((target,block))
                data = clip.entities.get(pos)
                entities.append((target,relocate(data,target) if data is not None else None))
        return self.apply("Paste structure",blocks,entities)

    def set_entity(self, position, tag):
        self.world.validate_edit(position,self.dimension)
        if tag is None:
            data = None
        else:
            if tag.kind != nbt.COMPOUND or not isinstance(nbt.get(tag,"id"),str):
                raise ValueError("A block entity must be a compound with a string id")
            if tuple(nbt.get(tag,axis) for axis in "xyz") != tuple(position):
                raise ValueError("Block entity x/y/z must match the selected block")
            if any(tag.value[axis].kind != nbt.INT for axis in "xyz"):
                raise ValueError("Block entity coordinates must be INT tags")
            data = nbt.dumps(tag)
        before = self.get_entity(*position)
        changes = [(position,before,data)] if before != data else []
        return self._commit(Transaction("Edit block NBT",self.dimension,[],changes))

    def set_biome(self, name):
        from .blocks import Block
        name = Block(name).name  # Same resource-location syntax as biome names.
        selection = self.require_selection()
        if selection.volume > MAX_OPERATION:
            raise ValueError(f"Select at most {MAX_OPERATION:,} blocks per operation")
        lo,hi = selection.minimum,selection.maximum
        changes = []
        for y in range(lo[1]//4*4,hi[1]//4*4+1,4):
            for z in range(lo[2]//4*4,hi[2]//4*4+1,4):
                for x in range(lo[0]//4*4,hi[0]//4*4+1,4):
                    self.world.validate_edit((x,y,z),self.dimension)
                    before = self.get_biome(x,y,z)
                    if before != name:
                        changes.append(((x,y,z),before,name))
        return self._commit(Transaction("Set biome",self.dimension,[],biome_changes=changes))

    def waterlog(self, enabled=True):
        from .blocks import Block
        if self.world.edition.startswith("Bedrock"):
            raise ValueError("Bedrock secondary-layer waterlogging is not implemented")
        changes = []
        for pos in self.require_selection().positions():
            block = self.get(*pos)
            props = dict(block.properties)
            if "waterlogged" in props:
                props["waterlogged"] = "true" if enabled else "false"
                changes.append((pos,Block(block.name,tuple(props.items()),block.state_types)))
        return self.apply("Waterlog blocks" if enabled else "Remove waterlogging",changes)

    def clone(self, offset, repeats=1, include_air=False):
        if len(offset) != 3 or any(type(v) is not int for v in offset) or not any(offset):
            raise ValueError("Clone offset must contain three integers and move at least one block")
        selection = self.require_selection()
        if type(repeats) is not int or repeats < 1 or repeats * selection.volume > MAX_OPERATION:
            raise ValueError("Clone exceeds the operation size limit")
        # Capture once, so overlapping repetitions never read their own writes.
        source = []
        for pos in selection.positions():
            if (self.dimension,*pos) not in self.edits:
                self.world.validate_copy(pos,self.dimension)
            source.append((pos,self.get(*pos),self.get_entity(*pos)))
        changes,entities = {},{}
        for repeat in range(1,repeats+1):
            for pos,block,entity in source:
                if include_air or not block.air:
                    target = tuple(pos[i]+offset[i]*repeat for i in range(3))
                    changes[target] = block
                    entities[target] = relocate(entity,target) if entity is not None else None
        return self.apply("Clone selection",changes.items(),entities.items())

    def nudge_selection(self, offset):
        selection = self.require_selection()
        self.selection = Selection(tuple(selection.a[i]+offset[i] for i in range(3)),tuple(selection.b[i]+offset[i] for i in range(3)))

    def expand_selection(self, amount):
        selection = self.require_selection()
        lo = tuple(v-amount for v in selection.minimum)
        hi = tuple(v+amount for v in selection.maximum)
        if any(a>b for a,b in zip(lo,hi)):
            raise ValueError("Selection cannot shrink below one block")
        self.selection = Selection(lo,hi)
