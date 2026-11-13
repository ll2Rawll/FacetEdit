"""Bounded, type-preserving Named Binary Tag codec. No external packages."""

from __future__ import annotations

import gzip
import io
import struct
from dataclasses import dataclass
from typing import Any
import zlib

END, BYTE, SHORT, INT, LONG, FLOAT, DOUBLE, BYTE_ARRAY, STRING, LIST, COMPOUND, INT_ARRAY, LONG_ARRAY = range(13)
MAX_BYTES = 64 * 1024 * 1024
MAX_ITEMS = 4 * 1024 * 1024


class FormatError(ValueError):
    """Malformed, unsupported or excessively large input."""


@dataclass
class Tag:
    kind: int
    value: Any


@dataclass
class ListValue:
    kind: int
    values: list


def compound(**values: Tag) -> Tag:
    return Tag(COMPOUND, values)


def get(tag: Tag, key: str, default=None):
    item = tag.value.get(key) if tag.kind == COMPOUND else None
    return item.value if item is not None else default


def modified_utf8_encode(text: str) -> bytes:
    result = bytearray()
    raw = text.encode("utf-16-be", "surrogatepass")
    for (unit,) in struct.iter_unpack(">H", raw):
        if 1 <= unit <= 127:
            result.append(unit)
        elif unit < 2048:
            result.extend((0xC0 | unit >> 6, 0x80 | unit & 63))
        else:
            result.extend((0xE0 | unit >> 12, 0x80 | unit >> 6 & 63, 0x80 | unit & 63))
    return bytes(result)


def modified_utf8_decode(raw: bytes) -> str:
    # Java serialises UTF-16 code units; surrogatepass joins the resulting pairs.
    try:
        text = raw.replace(b"\xc0\x80", b"\x00").decode("utf-8", "surrogatepass")
        return text.encode("utf-16-be", "surrogatepass").decode("utf-16-be", "surrogatepass")
    except UnicodeError as exc:
        raise FormatError("Invalid NBT string") from exc


def decompress(raw: bytes, method: str, limit: int = MAX_BYTES) -> bytes:
    if method == "raw":
        if len(raw) > limit:
            raise FormatError("NBT exceeds the memory limit")
        return raw
    decoder = zlib.decompressobj(31 if method == "gzip" else 15)
    try:
        data = decoder.decompress(raw, limit + 1)
    except zlib.error as exc:
        raise FormatError("Invalid compressed data") from exc
    if len(data) > limit or decoder.unconsumed_tail:
        raise FormatError("Decompressed data exceeds the memory limit")
    if not decoder.eof or decoder.unused_data:
        raise FormatError("Truncated or trailing compressed data")
    return data


class Reader:
    def __init__(self, data: bytes, little: bool = False):
        if len(data) > MAX_BYTES:
            raise FormatError("NBT exceeds 64 MiB")
        self.data = memoryview(data)
        self.pos = 0
        self.endian = "<" if little else ">"
        self.little = little
        self.budget = MAX_ITEMS

    def take(self, count: int) -> bytes:
        if count < 0 or count > len(self.data) - self.pos:
            raise FormatError("Truncated NBT payload")
        result = self.data[self.pos:self.pos + count].tobytes()
        self.pos += count
        return result

    def number(self, fmt: str):
        return struct.unpack(self.endian + fmt, self.take(struct.calcsize(fmt)))[0]

    def string(self) -> str:
        raw = self.take(self.number("H"))
        try:
            return raw.decode("utf-8") if self.little else modified_utf8_decode(raw)
        except UnicodeError as exc:
            raise FormatError("Invalid UTF-8 in Bedrock NBT") from exc

    def length(self) -> int:
        length = self.number("i")
        if not 0 <= length <= self.budget:
            raise FormatError("Invalid or excessive NBT collection length")
        self.budget -= length
        return length

    def payload(self, kind: int, depth: int = 0) -> Tag:
        if depth > 64:
            raise FormatError("NBT nesting exceeds 64 levels")
        if kind in (BYTE, SHORT, INT, LONG, FLOAT, DOUBLE):
            return Tag(kind, self.number({BYTE: "b", SHORT: "h", INT: "i", LONG: "q", FLOAT: "f", DOUBLE: "d"}[kind]))
        if kind == STRING:
            return Tag(kind, self.string())
        if kind == BYTE_ARRAY:
            return Tag(kind, self.take(self.length()))
        if kind in (INT_ARRAY, LONG_ARRAY):
            count = self.length()
            fmt = "i" if kind == INT_ARRAY else "q"
            return Tag(kind, list(struct.unpack(self.endian + str(count) + fmt, self.take(count * struct.calcsize(fmt)))))
        if kind == LIST:
            subtype, count = self.number("B"), self.length()
            if subtype not in range(13) or (subtype == END and count):
                raise FormatError("Invalid NBT list type")
            return Tag(LIST, ListValue(subtype, [self.payload(subtype, depth + 1).value for _ in range(count)]))
        if kind == COMPOUND:
            result = {}
            while True:
                subtype = self.number("B")
                if subtype == END:
                    return Tag(COMPOUND, result)
                name = self.string()
                self.budget -= 1
                if self.budget < 0 or name in result:
                    raise FormatError("Excessive or duplicate NBT compound members")
                result[name] = self.payload(subtype, depth + 1)
        raise FormatError(f"Unknown NBT type {kind}")

    def root(self) -> tuple[str, Tag]:
        kind = self.number("B")
        if kind == END:
            raise FormatError("NBT root may not be TAG_End")
        name = self.string()
        return name, self.payload(kind)


def loads(data: bytes, little: bool = False, compressed: bool = False) -> tuple[str, Tag]:
    if compressed:
        data = decompress(data, "gzip")
    reader = Reader(data, little)
    result = reader.root()
    if reader.pos != len(data):
        raise FormatError("Trailing NBT bytes")
    return result


def dumps(root: Tag, name: str = "", little: bool = False, compressed: bool = False) -> bytes:
    out = io.BytesIO()
    endian = "<" if little else ">"

    def number(fmt, value):
        out.write(struct.pack(endian + fmt, value))

    def string(value):
        raw = value.encode("utf-8") if little else modified_utf8_encode(value)
        if len(raw) > 65535:
            raise FormatError("NBT string exceeds 65535 encoded bytes")
        number("H", len(raw))
        out.write(raw)

    def payload(tag, depth=0):
        if depth > 64:
            raise FormatError("NBT nesting exceeds 64 levels")
        kind, value = tag.kind, tag.value
        if kind in (BYTE, SHORT, INT, LONG, FLOAT, DOUBLE):
            number({BYTE: "b", SHORT: "h", INT: "i", LONG: "q", FLOAT: "f", DOUBLE: "d"}[kind], value)
        elif kind == STRING:
            string(value)
        elif kind == BYTE_ARRAY:
            number("i", len(value))
            out.write(value)
        elif kind in (INT_ARRAY, LONG_ARRAY):
            number("i", len(value))
            out.write(struct.pack(endian + str(len(value)) + ("i" if kind == INT_ARRAY else "q"), *value))
        elif kind == LIST:
            number("B", value.kind)
            number("i", len(value.values))
            for item in value.values:
                payload(Tag(value.kind, item), depth + 1)
        elif kind == COMPOUND:
            for key, item in value.items():
                number("B", item.kind)
                string(key)
                payload(item, depth + 1)
            number("B", END)
        else:
            raise FormatError(f"Invalid NBT type {kind}")

    number("B", root.kind)
    string(name)
    payload(root)
    data = out.getvalue()
    if len(data) > MAX_BYTES:
        raise FormatError("NBT exceeds 64 MiB")
    return gzip.compress(data, mtime=0) if compressed else data
