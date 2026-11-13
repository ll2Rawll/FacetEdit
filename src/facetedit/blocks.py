"""Original block identities, state transforms and illustrative colors."""

from dataclasses import dataclass
import hashlib
import re


@dataclass(frozen=True, slots=True)
class Block:
    name: str
    properties: tuple[tuple[str, str], ...] = ()
    state_types: tuple[tuple[str, int], ...] = ()

    def __post_init__(self):
        name = self.name if ":" in self.name else "minecraft:" + self.name
        if not re.fullmatch(r"[a-z0-9_.-]+:[a-z0-9_./-]+", name):
            raise ValueError("Block names look like minecraft:stone")
        if any(part in (".", "..", "") for part in name.split(":", 1)[1].split("/")):
            raise ValueError("Block names cannot contain empty or dot path components")
        object.__setattr__(self, "name", name)
        object.__setattr__(self, "properties", tuple(sorted(self.properties)))
        if len(dict(self.properties)) != len(self.properties) or any(not isinstance(k, str) or not isinstance(v, str) for k, v in self.properties):
            raise ValueError("Block properties must have unique string keys and values")
        types = dict(self.state_types)
        if len(types) != len(self.state_types) or any(k not in dict(self.properties) or t not in (1, 3, 8) for k, t in types.items()):
            raise ValueError("Invalid Bedrock state type metadata")
        object.__setattr__(self, "state_types", tuple(sorted(self.state_types)))

    @property
    def air(self):
        return self.name in ("minecraft:air", "minecraft:cave_air", "minecraft:void_air")

    @property
    def label(self):
        return self.name.split(":", 1)[1].replace("_", " ").title()

    def __str__(self):
        suffix = "[" + ",".join(k + "=" + v for k, v in self.properties) + "]" if self.properties else ""
        return self.name + suffix

    @classmethod
    def parse(cls, text):
        name, sep, rest = text.strip().partition("[")
        if not sep:
            return cls(name)
        if not rest.endswith("]"):
            raise ValueError("Block properties must end with ]")
        properties = []
        for pair in rest[:-1].split(","):
            key, eq, val = pair.partition("=")
            if not eq or not key.strip() or not val.strip():
                raise ValueError("Use properties like axis=y,facing=north")
            properties.append((key.strip(), val.strip()))
        if len(dict(properties)) != len(properties):
            raise ValueError("Duplicate block property")
        return cls(name, tuple(properties))

    def transform(self, turns=0, mirror=False):
        props = dict(self.properties)
        directions = ["north", "east", "south", "west"]
        def direction(value):
            if value not in directions:
                return value
            index = directions.index(value)
            if mirror:
                index = -index % 4
            return directions[(index + turns) % 4]
        if "facing" in props:
            props["facing"] = direction(props["facing"])
        if turns % 2 and props.get("axis") in ("x", "z"):
            props["axis"] = "z" if props["axis"] == "x" else "x"
        if "rotation" in props:
            try:
                r = int(props["rotation"])
                props["rotation"] = str(((-r if mirror else r) + turns * 4) % 16)
            except ValueError:
                pass
        props = {direction(k): v for k, v in props.items()}
        return Block(self.name, tuple(props.items()), tuple((direction(k), v) for k, v in self.state_types))


AIR = Block("air")
COLORS = {
    "grass_block": "#8eaf75", "grass": "#8eaf75", "dirt": "#a58b72",
    "stone": "#adb4ba", "cobblestone": "#929ba4", "deepslate": "#626979",
    "water": "#79b6db", "sand": "#e6d8ac", "oak_log": "#a58a65",
    "oak_leaves": "#709269", "oak_planks": "#c9ac7f", "glass": "#bce0e7",
    "white_concrete": "#edf0ed", "bricks": "#bd8472", "gold_block": "#ebcd79",
    "diamond_block": "#80d8d1", "snow_block": "#edf3f7", "terracotta": "#c68f78",
    "bedrock": "#515963", "air": "#eff4f7", "lava": "#ea9d5c",
}
PALETTE = [Block(name) for name in COLORS if name != "air"]


def color(block):
    name = block.name.split(":", 1)[1]
    if name in COLORS:
        return COLORS[name]
    digest = hashlib.blake2b(block.name.encode(), digest_size=3).digest()
    return "#" + "".join(f"{100 + c % 100:02x}" for c in digest)


def shade(hex_color, factor):
    return "#" + "".join(f"{max(0, min(255, int(int(hex_color[i:i+2], 16) * factor))):02x}" for i in (1, 3, 5))
