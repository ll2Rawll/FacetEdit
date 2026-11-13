"""Inclusive box algebra. Union and subtraction never duplicate voxels."""

from dataclasses import dataclass

MAX_BLOCKS = 65_536
MAX_BOXES = 256
MAX_CHUNKS = 65_536


@dataclass(frozen=True)
class Selection:
    a: tuple[int,int,int]
    b: tuple[int,int,int]

    def __post_init__(self):
        if any(len(p)!=3 or any(type(v) is not int or abs(v)>30_000_000 for v in p) for p in (self.a,self.b)):
            raise ValueError("Selection coordinates must be three integers within ±30,000,000")

    @property
    def minimum(self):return tuple(min(a,b) for a,b in zip(self.a,self.b))

    @property
    def maximum(self):return tuple(max(a,b) for a,b in zip(self.a,self.b))

    @property
    def size(self):return tuple(b-a+1 for a,b in zip(self.minimum,self.maximum))

    @property
    def volume(self):
        x,y,z = self.size
        return x*y*z

    @property
    def boxes(self):return (self,)

    def contains(self,position):
        return all(a<=v<=b for a,v,b in zip(self.minimum,position,self.maximum))

    def positions(self):
        if self.volume>MAX_BLOCKS:
            raise ValueError(f"Select at most {MAX_BLOCKS:,} blocks per operation")
        lo,hi = self.minimum,self.maximum
        for y in range(lo[1],hi[1]+1):
            for z in range(lo[2],hi[2]+1):
                for x in range(lo[0],hi[0]+1):yield x,y,z

    def intersection(self,other):
        lo = tuple(max(a,b) for a,b in zip(self.minimum,other.minimum))
        hi = tuple(min(a,b) for a,b in zip(self.maximum,other.maximum))
        return Selection(lo,hi) if all(a<=b for a,b in zip(lo,hi)) else None

    def subtract(self,other):
        overlap = self.intersection(other)
        if overlap is None:return (self,)
        lo,hi = list(self.minimum),list(self.maximum)
        result = []
        # Peel off up to six non-overlapping slabs around the intersection.
        for axis in range(3):
            if lo[axis]<overlap.minimum[axis]:
                end = hi.copy();end[axis] = overlap.minimum[axis]-1
                result.append(Selection(tuple(lo),tuple(end)))
                lo[axis] = overlap.minimum[axis]
            if hi[axis]>overlap.maximum[axis]:
                start = lo.copy();start[axis] = overlap.maximum[axis]+1
                result.append(Selection(tuple(start),tuple(hi)))
                hi[axis] = overlap.maximum[axis]
        return tuple(result)

    def chunks(self):return chunk_coordinates(self.boxes)


class SelectionGroup:
    """An immutable union of normalized disjoint boxes, capped before explosion."""
    def __init__(self,boxes=()):
        result = []
        for box in boxes:
            if not isinstance(box,Selection):raise ValueError("A selection group contains boxes")
            pending = [box]
            for existing in result:
                pending = [piece for item in pending for piece in item.subtract(existing)]
                if len(result)+len(pending)>MAX_BOXES:
                    raise ValueError(f"Selection exceeds {MAX_BOXES} disjoint boxes")
            result.extend(pending)
            if len(result)>MAX_BOXES:raise ValueError(f"Selection exceeds {MAX_BOXES} boxes")
        self.boxes = tuple(sorted(result,key=lambda b:(b.minimum,b.maximum)))

    def __eq__(self,other):return isinstance(other,SelectionGroup) and self.boxes==other.boxes
    def __bool__(self):return bool(self.boxes)

    @property
    def minimum(self):
        if not self.boxes:raise ValueError("The selection is empty")
        return tuple(min(b.minimum[i] for b in self.boxes) for i in range(3))

    @property
    def maximum(self):
        if not self.boxes:raise ValueError("The selection is empty")
        return tuple(max(b.maximum[i] for b in self.boxes) for i in range(3))

    @property
    def a(self):return self.minimum
    @property
    def b(self):return self.maximum
    @property
    def size(self):return tuple(b-a+1 for a,b in zip(self.minimum,self.maximum))
    @property
    def volume(self):return sum(b.volume for b in self.boxes)

    def contains(self,position):return any(b.contains(position) for b in self.boxes)

    def positions(self):
        if self.volume>MAX_BLOCKS:raise ValueError(f"Select at most {MAX_BLOCKS:,} blocks per operation")
        for box in self.boxes:yield from box.positions()

    def union(self,other):return SelectionGroup((*self.boxes,*other.boxes))

    def subtract(self,other):
        boxes = self.boxes
        for cutter in other.boxes:
            boxes = tuple(piece for box in boxes for piece in box.subtract(cutter))
            if len(boxes)>MAX_BOXES:raise ValueError(f"Selection exceeds {MAX_BOXES} disjoint boxes")
        return SelectionGroup(boxes)

    def chunks(self):return chunk_coordinates(self.boxes)


def chunk_coordinates(boxes):
    result = set()
    for box in boxes:
        lo,hi = box.minimum,box.maximum
        width,depth = hi[0]//16-lo[0]//16+1,hi[2]//16-lo[2]//16+1
        if width*depth>MAX_CHUNKS:raise ValueError(f"Select at most {MAX_CHUNKS:,} chunks")
        for z in range(lo[2]//16,hi[2]//16+1):
            for x in range(lo[0]//16,hi[0]//16+1):
                result.add((x,z))
                if len(result)>MAX_CHUNKS:raise ValueError(f"Select at most {MAX_CHUNKS:,} chunks")
    return result
