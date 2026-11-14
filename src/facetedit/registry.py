"""Version-pinned block schemas generated from primary Minecraft metadata.

Bedrock's public metadata lists global property domains, not default permutations
or every per-block restriction. `initial` is an explicit starting selection there,
never a claim about the game's default. Translation rules supply their own states.
"""
from dataclasses import dataclass
from functools import lru_cache
import gzip
from importlib.resources import files
import json

from .blocks import Block

JAVA_RELEASES = {
    1139: (1,12,0), 1241: (1,12,1), 1343: (1,12,2), 1519: (1,13,0), 1628: (1,13,1), 1631: (1,13,2),
    1952: (1,14,0), 1957: (1,14,1), 1963: (1,14,2), 1968: (1,14,3), 1976: (1,14,4),
    2225: (1,15,0), 2227: (1,15,1), 2230: (1,15,2), 2566: (1,16,0), 2567: (1,16,1),
    2578: (1,16,2), 2580: (1,16,3), 2584: (1,16,4), 2586: (1,16,5),
    2724: (1,17,0), 2730: (1,17,1), 2860: (1,18,0), 2865: (1,18,1), 2975: (1,18,2),
    3105: (1,19,0), 3117: (1,19,1), 3120: (1,19,2), 3218: (1,19,3), 3337: (1,19,4),
    3463: (1,20,0), 3465: (1,20,1), 3578: (1,20,2), 3698: (1,20,3), 3700: (1,20,4),
    3837: (1,20,5), 3839: (1,20,6), 3953: (1,21,0), 3955: (1,21,1),
    4080: (1,21,2), 4082: (1,21,3), 4189: (1,21,4),
}
PROFILE_FILES = {'Java 1.21.4': 'java-1.21.4.json.gz', 'Bedrock 1.21.50': 'bedrock-1.21.50.json.gz',
                 'Bedrock 1.21.60':'bedrock-1.21.60.json.gz'}
# Native internal storage blocks omitted by the public placeable-block report.
# Their empty state compounds are cross-checked against the isolated native
# translation oracle; in-game validation remains a separate acceptance item.
BEDROCK_INTERNAL=('minecraft:end_gateway','minecraft:moving_block')


@dataclass(frozen=True)
class Profile:
    edition: str
    version: tuple
    data_version: int | None
    blocks: dict
    palette_version: int | None = None

    @property
    def label(self):
        return self.edition + ' ' + '.'.join(map(str, self.version))

    def initial(self, name):
        schema = self.blocks[name]
        properties = schema['default']
        if properties is None:
            properties = {k: domain[0] for k, (_, domain) in schema['properties'].items()}
        return self.block(name, properties)

    def block(self, name, properties, *, defaults=False):
        if name not in self.blocks:
            raise ValueError(f'{name} is not in the {self.label} block schema')
        schema = self.blocks[name]
        props = dict(schema['default'] or {}) if defaults else {}
        props.update(properties)
        expected = schema['properties']
        if props.keys() != expected.keys():
            missing = sorted(expected.keys() - props.keys())
            unknown = sorted(props.keys() - expected.keys())
            raise ValueError(f'{name}: missing states {missing}; unknown states {unknown}')
        for key, value in props.items():
            if value not in expected[key][1]:
                raise ValueError(f'{name}: {key}={value} is outside the {self.label} state domain')
        types = tuple((k, expected[k][0]) for k in props) if self.edition == 'Bedrock' else ()
        return Block(name, tuple(props.items()), types)

    def validate(self, block, *, defaults=False):
        result = self.block(block.name, dict(block.properties), defaults=defaults)
        if block.state_types and dict(block.state_types) != dict(result.state_types):
            raise ValueError(f'{block.name}: state NBT types do not match {self.label}')
        return result


@lru_cache(maxsize=16)
def profile(label):
    if label not in PROFILE_FILES:
        raise ValueError(f'No verified block schema for {label}')
    raw = files('facetedit').joinpath('data', 'registries', PROFILE_FILES[label]).read_bytes()
    data = json.loads(gzip.decompress(raw))
    if data['format'] != 1:
        raise ValueError('Unsupported registry format')
    if data['edition']=='Bedrock' and tuple(data['version']) in ((1,21,50),(1,21,60)):
        for name in BEDROCK_INTERNAL:data['blocks'].setdefault(name,{'default':{},'properties':{}})
    return Profile(data['edition'], tuple(data['version']), data['data_version'], data['blocks'], data.get('palette_version'))


def for_version(edition, data_version=None, game_version=None):
    for label in PROFILE_FILES:
        candidate = profile(label)
        if candidate.edition == edition and (candidate.data_version == data_version if edition == 'Java' else candidate.version == tuple(game_version or ())):
            return candidate
    raise ValueError(f'No verified {edition} translation schema for version {data_version if edition == "Java" else game_version}')


def for_world(world):
    edition = 'Bedrock' if world.edition.startswith('Bedrock') else 'Java'
    return for_version(edition, getattr(world, 'version', 4189), getattr(world, 'game_version', None))


def for_clipboard(clip):
    return for_version(clip.edition, clip.data_version, clip.game_version)
