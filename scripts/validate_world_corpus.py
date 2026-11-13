"""Read/edit/export/reopen published world fixtures without bundling them.

Usage: PYTHONPATH=src python scripts/validate_world_corpus.py --fixtures PATH
Fixtures: Amulet-Core tag 1.9.41, tests/data/worlds_src/{edition}/vanilla/...
Only level.dat, selected region files and DB records are required. This script
uses our implementation only. Passing it does not mean reopening in Minecraft.
"""
import argparse,hashlib,json,sys,tempfile,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'src'))
from facetedit.blocks import Block
from facetedit.model import Document,Selection
from facetedit.world import open_world,file_hash,snapshot
from facetedit.worldsave import save_original

parser=argparse.ArgumentParser();parser.add_argument('--fixtures',type=Path,required=True);args=parser.parse_args()
report={'fixture_source':'https://github.com/Amulet-Team/Amulet-Core/tree/1.9.41/tests/data/worlds_src','worlds':[],
        'scope':'Published Minecraft world fixtures read, edited, exported and reopened by FacetEdit; no Minecraft game/server execution, no Amulet runtime imports. Fixtures are outside the distribution.'}
with tempfile.TemporaryDirectory() as temporary:
    for metadata in sorted(args.fixtures.rglob('level.dat')):
        start=time.perf_counter();path=metadata.parent;world=open_world(path);doc=Document(world)
        before={p:file_hash(path/p).hex() for p in snapshot(path)}
        chunks=sorted(world.chunk_positions('overworld'));cx,cz=chunks[len(chunks)//2];x,z=cx*16+3,cz*16+7
        low,high=world.bounds('overworld');y=max(low,min(high,60))
        original=doc.get(x,y,z);old_biome=doc.get_biome(x,y,z)
        doc.selection=Selection((x,y,z),(x,y,z));doc.fill(Block('gold_block'));doc.set_biome('desert')
        if world.edition.startswith('Bedrock'):doc.waterlog()
        output=Path(temporary)/str(len(report['worlds']));world.export(output,doc.edits,**doc.export_metadata());reopened=open_world(output)
        assert reopened.get_block(x,y,z)==Block('gold_block')
        assert reopened.get_biome(x,y,z)=='minecraft:desert'
        if world.edition.startswith('Bedrock'):assert reopened.get_extra_blocks(x,y,z)[0].name=='minecraft:water'
        after={p:file_hash(path/p).hex() for p in snapshot(path)};assert after==before
        entry={'world':str(path.relative_to(args.fixtures)),'edition':world.edition,'stored_chunks':len(chunks),'position':[x,y,z],
               'original_block':str(original),'original_biome':old_biome,'source_files':len(before),'source_unchanged':True,
               'block_biome_layers_roundtrip':'pass','seconds':round(time.perf_counter()-start,3)}
        report['worlds'].append(entry)
print(json.dumps(report,indent=2))
