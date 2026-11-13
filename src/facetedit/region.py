"""Independent Anvil sector container; unchanged chunk bytes are retained."""

from pathlib import Path
import struct
import time
import zlib
import re

from .nbt import FormatError, decompress

SECTOR = 4096


class Region:
    def __init__(self, raw: bytes = b"",path=None):
        self.path = Path(path) if path is not None else None
        self.external = {}
        self.changed = set()
        self.chunks: dict[int, bytes] = {}
        self.timestamps = [0] * 1024
        if not raw:
            return
        if len(raw) < 8192 or len(raw) % SECTOR:
            raise FormatError("Anvil file is truncated or not sector aligned")
        occupied = {0, 1}
        for index in range(1024):
            location = int.from_bytes(raw[index * 4:index * 4 + 4], "big")
            self.timestamps[index] = struct.unpack_from(">I", raw, 4096 + index * 4)[0]
            if not location:
                continue
            offset, count = location >> 8, location & 255
            if offset < 2 or count == 0 or (offset + count) * SECTOR > len(raw):
                raise FormatError("Invalid Anvil chunk sector span")
            sectors = set(range(offset, offset + count))
            if sectors & occupied:
                raise FormatError("Overlapping Anvil chunk sectors")
            occupied.update(sectors)
            start = offset * SECTOR
            size = struct.unpack_from(">I", raw, start)[0]
            if size < 1 or size + 4 > count * SECTOR:
                raise FormatError("Invalid Anvil chunk byte length")
            self.chunks[index] = raw[start + 4:start + 4 + size]

    @classmethod
    def read(cls, path):
        path = Path(path)
        if path.stat().st_size > 256 * 1024 * 1024:
            raise FormatError("Region exceeds the 256 MiB safety limit")
        return cls(path.read_bytes(),path)

    @staticmethod
    def index(cx, cz):
        return (cx & 31) + (cz & 31) * 32

    def get(self, cx, cz):
        raw = self.chunks.get(self.index(cx, cz))
        if raw is None:
            return None
        external = self.external.get(self.index(cx,cz))
        if raw[0]&128 and external is None:
            if self.path is None:raise FormatError("External chunk needs its .mcc sidecar")
            file = self.path.parent/f"c.{cx}.{cz}.mcc"
            if file.is_symlink() or file.stat().st_size>64*1024*1024:
                raise FormatError("Unsafe or oversized external chunk")
            external = file.read_bytes()
        return decode_payload(raw,external)

    def put(self, cx, cz, data):
        raw = b"\x02" + zlib.compress(data, 6)
        if len(raw) + 4 > 255 * SECTOR:
            if self.path is None:raise FormatError("Oversized chunk needs a region path for its external sidecar")
            self.external[self.index(cx,cz)] = raw[1:]
            raw = b'\x82'
        else:self.external.pop(self.index(cx,cz),None)
        index = self.index(cx, cz)
        self.chunks[index] = raw
        self.changed.add(index)
        self.timestamps[index] = int(time.time())

    def delete(self,cx,cz):
        index = self.index(cx,cz)
        self.chunks.pop(index,None);self.external.pop(index,None)
        self.timestamps[index] = 0
        self.changed.add(index)

    def put_payload(self,cx,cz,payload,external=None):
        if not payload or payload[0]&128 and (len(payload)!=1 or external is None):
            raise FormatError('External chunk payload needs exactly one compression byte and its sidecar')
        if len(payload)+4>255*SECTOR:raise FormatError('Inline chunk exceeds Anvil capacity')
        index = self.index(cx,cz)
        self.chunks[index] = payload
        if external is not None:self.external[index] = external
        else:self.external.pop(index,None)
        self.changed.add(index);self.timestamps[index] = int(time.time())

    def write(self,path=None):
        path = Path(path) if path is not None else self.path
        if path is None:raise ValueError('A region output path is required')
        match = re.fullmatch(r'r\.(-?\d+)\.(-?\d+)\.mca',path.name)
        if not match:raise ValueError('Invalid region filename')
        rx,rz = map(int,match.groups())
        # Validate the container before publishing any sidecar. A copy to a new
        # directory also needs unchanged external payloads, not only edits.
        raw=self.dumps() if self.chunks else None
        sidecars={}
        for index,payload in self.chunks.items():
            if payload[0]&128 and (index in self.changed or path!=self.path):
                data=self.external.get(index)
                if data is None:
                    if self.path is None:raise FormatError('External chunk needs its source sidecar')
                    original=re.fullmatch(r'r\.(-?\d+)\.(-?\d+)\.mca',self.path.name)
                    if not original:raise FormatError('Invalid source region name')
                    ox,oz=map(int,original.groups())
                    source=self.path.parent/f'c.{ox*32+(index&31)}.{oz*32+(index>>5)}.mcc'
                    if source.is_symlink() or source.stat().st_size>64*1024*1024:raise FormatError('Unsafe or oversized external chunk')
                    data=source.read_bytes()
                sidecars[index]=data
        path.parent.mkdir(parents=True,exist_ok=True)
        for index in self.changed|sidecars.keys():
            file = path.parent/f'c.{rx*32+(index&31)}.{rz*32+(index>>5)}.mcc'
            if index in sidecars:
                file.write_bytes(sidecars[index])
            else:file.unlink(missing_ok=True)
        if self.chunks:path.write_bytes(raw)
        else:path.unlink(missing_ok=True)

    @classmethod
    def coordinates(cls,path):
        path = Path(path)
        match = re.fullmatch(r'r\.(-?\d+)\.(-?\d+)\.mca',path.name)
        if not match:return set()
        size = path.stat().st_size
        if size<8192 or size%SECTOR or size>256*1024*1024:raise FormatError('Invalid region file length')
        with path.open('rb') as file:header = file.read(4096)
        rx,rz = map(int,match.groups());result = set();occupied = {0,1}
        for index in range(1024):
            location = int.from_bytes(header[index*4:index*4+4],'big')
            if not location:continue
            offset,count = location>>8,location&255
            slots = set(range(offset,offset+count))
            if offset<2 or not count or (offset+count)*SECTOR>size or slots&occupied:
                raise FormatError('Invalid chunk allocation in region inventory')
            occupied.update(slots)
            result.add((rx*32+(index&31),rz*32+(index>>5)))
        return result

    def dumps(self):
        header = bytearray(8192)
        body = bytearray()
        for index, raw in sorted(self.chunks.items()):
            count = (len(raw) + 4 + SECTOR - 1) // SECTOR
            offset = 2 + len(body) // SECTOR
            if count > 255 or offset > 0xFFFFFF:
                raise FormatError("Anvil container limit exceeded")
            struct.pack_into(">I", header, index * 4, offset << 8 | count)
            struct.pack_into(">I", header, 4096 + index * 4, self.timestamps[index])
            body.extend(struct.pack(">I", len(raw)) + raw)
            body.extend(b"\x00" * (count * SECTOR - len(raw) - 4))
        return bytes(header + body)


def decode_payload(raw,external=None):
    if not raw:raise FormatError('Empty Anvil chunk payload')
    compression = raw[0]&127
    if raw[0]&128:
        if len(raw)!=1 or external is None:raise FormatError('External chunk is missing its sidecar')
        data = external
    else:data = raw[1:]
    if compression==4:
        from .lz4 import decompress_stream
        return decompress_stream(data)
    if compression not in (1,2,3):raise FormatError(f'Unsupported Anvil compression {compression}')
    return decompress(data,{1:'gzip',2:'zlib',3:'raw'}[compression])
