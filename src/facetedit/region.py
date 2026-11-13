"""Independent Anvil sector container; unchanged chunk bytes are retained."""

from pathlib import Path
import struct
import time
import zlib

from .nbt import FormatError, decompress

SECTOR = 4096


class Region:
    def __init__(self, raw: bytes = b""):
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
        return cls(path.read_bytes())

    @staticmethod
    def index(cx, cz):
        return (cx & 31) + (cz & 31) * 32

    def get(self, cx, cz):
        raw = self.chunks.get(self.index(cx, cz))
        if raw is None:
            return None
        compression = raw[0]
        if compression & 128:
            raise FormatError("External .mcc chunks are not supported for editing yet")
        if compression not in (1, 2, 3):
            raise FormatError(f"Unsupported Anvil compression {compression}")
        return decompress(raw[1:], {1: "gzip", 2: "zlib", 3: "raw"}[compression])

    def put(self, cx, cz, data):
        raw = b"\x02" + zlib.compress(data, 6)
        if len(raw) + 4 > 255 * SECTOR:
            raise FormatError("Edited chunk exceeds inline Anvil capacity")
        index = self.index(cx, cz)
        self.chunks[index] = raw
        self.timestamps[index] = int(time.time())

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
