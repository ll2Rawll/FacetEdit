"""Normalize primary-source Minecraft block schemas; no game code is packaged.

Inputs: Java's official `net.minecraft.data.Main --reports` blocks.json and the
pinned Mojang bedrock-samples mojang-blocks.json. See data/registries/SOURCES.json.
"""
import argparse
import gzip
import hashlib
import json
from pathlib import Path


def generate(edition, version, source, destination, data_version=None, palette_version=None):
    raw = Path(source).read_bytes()
    data = json.loads(raw)
    blocks = {}
    if edition == 'Java':
        for name, entry in sorted(data.items()):
            default = next(s for s in entry['states'] if s.get('default'))
            blocks[name] = {'properties': {k: [8, v] for k, v in entry.get('properties', {}).items()},
                            'default': default.get('properties', {})}
    else:
        properties = {}
        for prop in data['block_properties']:
            kind = {'bool': 1, 'int': 3, 'string': 8}[prop['type']]
            values = [str(v['value']).lower() if kind == 1 else str(v['value']) for v in prop['values']]
            properties[prop['name']] = [kind, values]
        for entry in sorted(data['data_items'], key=lambda e: e['name']):
            blocks[entry['name']] = {'properties': {p['name']: properties[p['name']] for p in entry['properties']},
                                      'default': None}
    result = {'format': 1, 'edition': edition, 'version': list(version), 'data_version': data_version,
              'palette_version': palette_version,
              'source_sha256': hashlib.sha256(raw).hexdigest(), 'blocks': blocks}
    Path(destination).parent.mkdir(parents=True, exist_ok=True)
    Path(destination).write_bytes(gzip.compress(json.dumps(result, sort_keys=True, separators=(',', ':')).encode(), mtime=0))
    return {'blocks': len(blocks), 'sha256': result['source_sha256']}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('edition', choices=['Java', 'Bedrock'])
    parser.add_argument('version')
    parser.add_argument('source')
    parser.add_argument('destination')
    parser.add_argument('--data-version', type=int)
    parser.add_argument('--palette-version', type=int)
    args = parser.parse_args()
    print(json.dumps(generate(args.edition, tuple(map(int, args.version.split('.'))), args.source, args.destination, args.data_version, args.palette_version)))
