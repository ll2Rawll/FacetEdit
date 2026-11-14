"""Lazy primary Java state facts used by bounded neighbour translation.

The bundled data is metadata produced by our optional reporter against the
pinned official server, with official block tags bound. No server code runs in
the editor. Support/fence/pane masks describe the neighbour's face. Wire masks
use the direction from the wire to its neighbour, matching the primary method.
"""
from functools import lru_cache
import gzip
from importlib.resources import files
import json

FACES=('down','up','north','south','west','east')


@lru_cache(maxsize=1)
def catalog():
    return json.loads(gzip.decompress(files('facetedit').joinpath('data','registries','java-1.21.4-state-facts.json.gz').read_bytes()))


@lru_cache(maxsize=8192)
def facts(block):
    schema=catalog()['blocks'].get(block.name)
    if schema is None:raise ValueError('No primary neighbour facts for '+block.name)
    properties=dict(block.properties)
    try:return tuple(schema['states'][','.join(properties[k] for k in schema['properties'])])
    except KeyError as exc:raise ValueError('Neighbour state is incomplete or unsupported: '+str(block)) from exc


def connects(block,neighbour,face):
    index=4 if block.name=='minecraft:nether_brick_fence' else 3 if block.name.endswith('_fence') else 5
    return bool(facts(neighbour)[index] & (1<<FACES.index(face)))


def instrument(below,above):
    # Head instruments are selected only by a head above the note block.
    heads={'minecraft:'+name:instrument for name,instrument in (
        ('skeleton_skull','skeleton'),('wither_skeleton_skull','wither_skeleton'),
        ('zombie_head','zombie'),('creeper_head','creeper'),('dragon_head','dragon'),
        ('piglin_head','piglin'),('player_head','custom_head'))}
    if above.name in heads:return heads[above.name]
    return facts(below)[2]
