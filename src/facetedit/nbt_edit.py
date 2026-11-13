"""Lossless, typed JSON representation for NBT inspection and editing."""

import base64
import json
import math
import struct

from . import nbt

NAMES = ("end","byte","short","int","long","float","double","bytes","string","list","compound","ints","longs")


def to_json(tag):
    def convert(tag):
        value = tag.value
        if tag.kind == nbt.COMPOUND:
            value = {key: convert(child) for key, child in value.items()}
        elif tag.kind == nbt.LIST:
            value = {"element": NAMES[value.kind], "items": [convert(nbt.Tag(value.kind, item))["value"] for item in value.values]}
        elif tag.kind == nbt.BYTE_ARRAY:
            value = base64.b64encode(value).decode("ascii")
        elif tag.kind in (nbt.FLOAT, nbt.DOUBLE) and not math.isfinite(value):
            value = repr(value)
        return {"type": NAMES[tag.kind], "value": value}
    return json.dumps(convert(tag), indent=2, ensure_ascii=False)


def from_json(text):
    if len(text) > 4 * 1024 * 1024:
        raise ValueError("NBT editor text exceeds 4 MiB")
    data = json.loads(text)
    budget = [100_000]
    def convert(value, depth=0):
        budget[0] -= 1
        if depth > 48 or budget[0] < 0:
            raise ValueError("NBT editor nesting or item limit exceeded")
        if not isinstance(value, dict) or set(value) != {"type", "value"} or value["type"] not in NAMES[1:]:
            raise ValueError("Every tag needs a valid type and value")
        kind = NAMES.index(value["type"])
        value = value["value"]
        if kind == nbt.COMPOUND:
            if not isinstance(value, dict):
                raise ValueError("Compound values must be objects")
            value = {k: convert(v, depth+1) for k,v in value.items()}
        elif kind == nbt.LIST:
            if not isinstance(value, dict) or set(value) != {"element","items"} or value["element"] not in NAMES:
                raise ValueError("List values need element and items")
            if not isinstance(value["items"],list) or (value["element"] == "end" and value["items"]):
                raise ValueError("Invalid typed list")
            subtype = value["element"]
            value = nbt.ListValue(NAMES.index(subtype), [convert({"type":subtype,"value":v},depth+1).value for v in value["items"]])
        elif kind == nbt.BYTE_ARRAY:
            value = base64.b64decode(value, validate=True)
        elif kind in (nbt.BYTE,nbt.SHORT,nbt.INT,nbt.LONG):
            if type(value) is not int:
                raise ValueError("Integer tags require integers, not booleans or strings")
        elif kind in (nbt.FLOAT,nbt.DOUBLE):
            if type(value) not in (int,float) and value not in ("nan","inf","-inf"):
                raise ValueError("Invalid floating-point tag")
            value = float(value)
        elif kind == nbt.STRING:
            if not isinstance(value,str):
                raise ValueError("String tags require text")
        elif kind in (nbt.INT_ARRAY,nbt.LONG_ARRAY):
            if not isinstance(value,list) or any(type(v) is not int for v in value):
                raise ValueError("Array tags require a list of integers")
        return nbt.Tag(kind,value)
    tag = convert(data)
    # Binary serialization performs exact integer range and encoded string checks.
    try:
        nbt.dumps(tag)
    except (struct.error, OverflowError) as exc:
        raise ValueError("NBT number is outside its tag's range") from exc
    return tag
