"""Small offline LevelDB snapshot codec, including Mojang's compression modes.

This is not a concurrent database implementation. The game must be closed.
Readers honour the current manifest, internal sequence numbers and tombstones.
Writers create a new database in an empty directory; never mutate an existing DB.
"""

from __future__ import annotations

from pathlib import Path
import struct
import zlib

from .nbt import FormatError

LIMIT = 256 * 1024 * 1024
BLOCK_SIZE = 32768
MAGIC = 0xDB4775248B80FB57


def _crc_table():
    values = []
    for i in range(256):
        crc = i
        for _ in range(8):
            crc = (crc >> 1) ^ (0x82F63B78 if crc & 1 else 0)
        values.append(crc)
    return values


_CRC = _crc_table()


def crc32c(data):
    crc = 0xFFFFFFFF
    for b in data:
        crc = _CRC[(crc ^ b) & 255] ^ (crc >> 8)
    return crc ^ 0xFFFFFFFF


def masked_crc(data):
    crc = crc32c(data)
    return (((crc >> 15) | (crc << 17)) + 0xA282EAD8) & 0xFFFFFFFF


def varint(value):
    if value < 0:
        raise ValueError("A varint cannot be negative")
    out = bytearray()
    while value >= 128:
        out.append((value & 127) | 128)
        value >>= 7
    out.append(value)
    return bytes(out)


class Cursor:
    def __init__(self, data):
        self.data, self.pos = data, 0

    def take(self, length):
        if length < 0 or length > len(self.data) - self.pos:
            raise FormatError("Truncated LevelDB data")
        result = self.data[self.pos:self.pos + length]
        self.pos += length
        return result

    def varint(self):
        value = 0
        for shift in range(0, 70, 7):
            byte = self.take(1)[0]
            if shift == 63 and byte > 1:
                raise FormatError("LevelDB varint exceeds 64 bits")
            value |= (byte & 127) << shift
            if byte < 128:
                return value
        raise FormatError("Invalid LevelDB varint")

    def blob(self):
        return self.take(self.varint())


def blob(data):
    return varint(len(data)) + data


def snappy_decode(data):
    reader = Cursor(data)
    size = reader.varint()
    if size > LIMIT:
        raise FormatError("Snappy output exceeds the memory limit")
    out = bytearray()
    while reader.pos < len(data):
        tag = reader.take(1)[0]
        kind = tag & 3
        if kind == 0:
            length = tag >> 2
            if length >= 60:
                length = int.from_bytes(reader.take(length - 59), "little")
            length += 1
            if len(out) + length > size:
                raise FormatError("Snappy literal exceeds declared length")
            out.extend(reader.take(length))
        else:
            if kind == 1:
                length = 4 + ((tag >> 2) & 7)
                offset = ((tag & 0xE0) << 3) | reader.take(1)[0]
            else:
                length = 1 + (tag >> 2)
                offset = int.from_bytes(reader.take(2 if kind == 2 else 4), "little")
            if not 0 < offset <= len(out) or len(out) + length > size:
                raise FormatError("Invalid Snappy copy offset/length")
            for _ in range(length):
                out.append(out[-offset])
    if len(out) != size:
        raise FormatError("Snappy output length mismatch")
    return bytes(out)


def log_records(data):
    offset = 0
    pending = None
    while offset < len(data):
        remaining = BLOCK_SIZE - offset % BLOCK_SIZE
        if remaining < 7:
            tail = data[offset:offset + remaining]
            if any(tail):
                raise FormatError("Invalid LevelDB log padding")
            offset += remaining
            continue
        if len(data) - offset < 7:
            raise FormatError("Incomplete LevelDB log header")
        checksum, size, kind = struct.unpack_from("<IHB", data, offset)
        if (checksum, size, kind) == (0, 0, 0):
            tail = data[offset:offset + remaining]
            if any(tail):
                raise FormatError("Unexpected zero LevelDB log record")
            offset += remaining
            continue
        if size + 7 > remaining or offset + size + 7 > len(data):
            raise FormatError("Incomplete LevelDB log record; close Minecraft first")
        payload = data[offset + 7:offset + 7 + size]
        if masked_crc(bytes([kind]) + payload) != checksum:
            raise FormatError("LevelDB log checksum mismatch")
        offset += size + 7
        if kind == 1:
            if pending is not None:
                raise FormatError("Interrupted LevelDB fragmented record")
            yield payload
        elif kind == 2 and pending is None:
            pending = bytearray(payload)
        elif kind in (3, 4) and pending is not None:
            pending.extend(payload)
            if len(pending) > LIMIT:
                raise FormatError("LevelDB log record exceeds the memory limit")
            if kind == 4:
                yield bytes(pending)
                pending = None
        else:
            raise FormatError("Invalid LevelDB log fragment sequence")
    if pending is not None:
        raise FormatError("Truncated LevelDB fragmented record")


def write_log(records):
    result = bytearray()
    for data in records:
        offset, first = 0, True
        while first or offset < len(data):
            available = BLOCK_SIZE - len(result) % BLOCK_SIZE
            if available < 7:
                result.extend(b"\x00" * available)
                available = BLOCK_SIZE
            size = min(len(data) - offset, available - 7)
            last = offset + size == len(data)
            kind = (1 if last else 2) if first else (4 if last else 3)
            payload = data[offset:offset + size]
            result.extend(struct.pack("<IHB", masked_crc(bytes([kind]) + payload), size, kind))
            result.extend(payload)
            offset += size
            first = False
    return bytes(result)


def block_entries(data):
    if len(data) < 4:
        raise FormatError("Truncated LevelDB table block")
    restart_count = struct.unpack_from("<I", data, len(data) - 4)[0]
    boundary = len(data) - 4 - restart_count * 4
    if restart_count < 1 or boundary < 0:
        raise FormatError("Invalid LevelDB restart array")
    restarts = struct.unpack_from("<" + str(restart_count) + "I", data, boundary)
    if restarts[0] != 0 or any(r > boundary for r in restarts):
        raise FormatError("Invalid LevelDB restart offset")
    cursor = Cursor(data[:boundary])
    previous = b""
    while cursor.pos < boundary:
        shared, extra, value_size = cursor.varint(), cursor.varint(), cursor.varint()
        if shared > len(previous):
            raise FormatError("Invalid LevelDB shared key prefix")
        key = previous[:shared] + cursor.take(extra)
        value = cursor.take(value_size)
        yield key, value
        previous = key


def _table_block(data, handle):
    cursor = Cursor(handle)
    offset, length = cursor.varint(), cursor.varint()
    if offset + length + 5 > len(data) - 48:
        raise FormatError("LevelDB block points outside table")
    payload = data[offset:offset + length]
    kind = data[offset + length]
    checksum = struct.unpack_from("<I", data, offset + length + 1)[0]
    if checksum != masked_crc(payload + bytes([kind])):
        raise FormatError("LevelDB table checksum mismatch")
    if kind == 0:
        return payload
    if kind == 1:
        return snappy_decode(payload)
    if kind in (2, 4):
        try:
            decoder = zlib.decompressobj(15 if kind == 2 else -15)
            raw = decoder.decompress(payload, LIMIT + 1)
        except zlib.error as exc:
            raise FormatError("Invalid Bedrock compressed database block") from exc
        if len(raw) > LIMIT or not decoder.eof or decoder.unused_data:
            raise FormatError("Invalid or excessive compressed database block")
        return raw
    raise FormatError(f"Unsupported LevelDB compression {kind}")


def table_entries(data):
    if len(data) < 48 or struct.unpack_from("<Q", data, len(data) - 8)[0] != MAGIC:
        raise FormatError("Invalid LevelDB table footer")
    footer = Cursor(data[-48:-8])
    footer.varint(), footer.varint()  # metaindex, which is not needed to read values
    start = footer.pos
    footer.varint(), footer.varint()
    index = _table_block(data, footer.data[start:footer.pos])
    for _, handle in block_entries(index):
        yield from block_entries(_table_block(data, handle))


def _read(path):
    if path.stat().st_size > LIMIT:
        raise FormatError("Database file exceeds the 256 MiB offline limit")
    return path.read_bytes()


def load_database(path):
    path = Path(path)
    current = (path / "CURRENT").read_text("ascii").strip()
    if not current.startswith("MANIFEST-") or not current[9:].isdigit():
        raise FormatError("Invalid LevelDB CURRENT manifest name")
    live = {}
    log_number = previous_log = 0
    comparator = b"leveldb.BytewiseComparator"
    for record in log_records(_read(path / current)):
        cursor = Cursor(record)
        while cursor.pos < len(record):
            tag = cursor.varint()
            if tag == 1:
                comparator = cursor.blob()
            elif tag in (2, 3, 4, 9):
                value = cursor.varint()
                if tag == 2:
                    log_number = value
                elif tag == 9:
                    previous_log = value
            elif tag == 5:
                cursor.varint(), cursor.blob()
            elif tag == 6:
                cursor.varint()
                live.pop(cursor.varint(), None)
            elif tag == 7:
                cursor.varint()
                number, size = cursor.varint(), cursor.varint()
                cursor.blob(), cursor.blob()
                live[number] = size
            else:
                raise FormatError(f"Unsupported LevelDB manifest field {tag}")
    if comparator != b"leveldb.BytewiseComparator":
        raise FormatError("Unsupported LevelDB key comparator")
    records = {}
    memory = 0

    def apply(key, sequence, value):
        nonlocal memory
        previous = records.get(key)
        if previous is None or sequence >= previous[0]:
            memory += len(key) + len(value or b"") + 96
            if previous is not None:
                memory -= len(key) + len(previous[1] or b"") + 96
            if memory > LIMIT:
                raise FormatError("World database exceeds FacetEdit's 256 MiB snapshot budget")
            records[key] = (sequence, value)

    for number, expected_size in live.items():
        file = path / f"{number:06d}.ldb"
        if not file.exists():
            file = path / f"{number:06d}.sst"
        if file.stat().st_size != expected_size:
            raise FormatError("Database table size differs from manifest")
        for internal, value in table_entries(_read(file)):
            if len(internal) < 8:
                raise FormatError("Truncated LevelDB internal key")
            packed = struct.unpack("<Q", internal[-8:])[0]
            kind = packed & 255
            if kind not in (0, 1):
                raise FormatError("Unsupported LevelDB internal value type")
            apply(internal[:-8], packed >> 8, value if kind else None)
    logs = sorted(path.glob("*.log"))
    for file in logs:
        if not file.stem.isdigit():
            continue
        number = int(file.stem)
        if number < log_number and number != previous_log:
            continue
        for record in log_records(_read(file)):
            cursor = Cursor(record)
            sequence, count = struct.unpack("<QI", cursor.take(12))
            if count > 4_000_000:
                raise FormatError("Excessive LevelDB write batch")
            for index in range(count):
                kind = cursor.take(1)[0]
                if kind not in (0, 1):
                    raise FormatError("Invalid LevelDB write operation")
                key = cursor.blob()
                apply(key, sequence + index, cursor.blob() if kind else None)
            if cursor.pos != len(record):
                raise FormatError("Trailing LevelDB write batch bytes")
    return {key: value for key, (_, value) in records.items() if value is not None}


class LogWriter:
    """Bounded LevelDB journal output with fragment alignment across batches."""
    def __init__(self, handle):
        self.handle = handle
        self.position = 0

    def write(self, data):
        self.handle.write(data)
        self.position += len(data)

    def record(self, data):
        offset, first = 0, True
        while first or offset < len(data):
            available = BLOCK_SIZE - self.position % BLOCK_SIZE
            if available < 7:
                self.write(b'\0'*available)
                available = BLOCK_SIZE
            size = min(len(data)-offset, available-7)
            last = offset+size == len(data)
            kind = (1 if last else 2) if first else (4 if last else 3)
            payload = data[offset:offset+size]
            self.write(struct.pack('<IHB', masked_crc(bytes([kind])+payload), size, kind))
            self.write(payload)
            offset += size
            first = False


def write_database(path, values, cancelled=lambda: False):
    path = Path(path)
    path.mkdir(parents=True, exist_ok=True)
    if any(path.iterdir()):
        raise FileExistsError("Database snapshot destination must be empty")
    sequence = 1
    batch = []
    batch_bytes = 0
    with (path / '000002.log').open('wb') as output:
        writer = LogWriter(output)
        for key in sorted(values):
            if cancelled():
                raise InterruptedError('Database output cancelled')
            value = values[key]
            encoded = b'\x01'+blob(key)+blob(value)
            batch.append(encoded)
            batch_bytes += len(encoded)
            if len(batch) >= 512 or batch_bytes >= 1024*1024:
                writer.record(struct.pack('<QI', sequence, len(batch))+b''.join(batch))
                sequence += len(batch)
                batch.clear()
                batch_bytes = 0
        if batch:
            writer.record(struct.pack('<QI', sequence, len(batch))+b''.join(batch))
            sequence += len(batch)
    manifest = (varint(1) + blob(b"leveldb.BytewiseComparator") + varint(2) + varint(2)
                + varint(3) + varint(3) + varint(4) + varint(sequence - 1) + varint(9) + varint(0))
    (path / "MANIFEST-000001").write_bytes(write_log([manifest]))
    (path / "CURRENT").write_text("MANIFEST-000001\n", encoding="ascii")
