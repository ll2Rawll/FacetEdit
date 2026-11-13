"""Measure bounded chunk imports with synthetic on-disk worlds; test tooling."""
from pathlib import Path
import json,shutil,statistics,struct,sys,tempfile,time
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'));sys.path.insert(0,str(ROOT))
from facetedit.chunks import empty_java
from facetedit.leveldb import load_database,write_database
from facetedit.model import Document,Selection
from facetedit.region import Region
from facetedit.world import open_world
from tests.fixtures import java_world,bedrock_world
from tests.test_chunks import bedrock_metadata


def measure(function):
    durations=[]
    for _ in range(5):
        start=time.perf_counter();function();durations.append((time.perf_counter()-start)*1000)
    return {'median_ms':round(statistics.median(durations),3),'min_ms':round(min(durations),3),'max_ms':round(max(durations),3),'runs':len(durations)}


with tempfile.TemporaryDirectory() as temporary:
    folder=Path(temporary)
    java=java_world(folder/'java-source');world=open_world(java)
    region=Region(path=java/'region/r.0.0.mca')
    for x in range(8):
        for z in range(8):region.put_payload(x,z,dict(empty_java(world,x,z,'overworld').records)[b'region'])
    region.write()
    target=open_world(java_world(folder/'java-target'))
    source=open_world(java)
    def import_java():
        doc=Document(target);doc.selection=Selection((0,0,0),(127,0,127));assert doc.import_chunks(source)==64;doc.undo();doc.redo()
    java_timing=measure(import_java)
    bedrock=bedrock_metadata(bedrock_world(folder/'bedrock-source'));values=load_database(bedrock/'db')
    base=bytes(8)
    for x in range(8):
        for z in range(8):
            prefix=struct.pack('<ii',x,z)
            for suffix in (b'/\0',b',',b'+'):values[prefix+suffix]=values[base+suffix]
    for i in range(20000):values[f'opaque-world-metadata-{i:06}'.encode()]=b'payload'
    shutil.rmtree(bedrock/'db');write_database(bedrock/'db',values)
    source_bedrock=open_world(bedrock);target_bedrock=open_world(bedrock_metadata(bedrock_world(folder/'bedrock-target')))
    def import_bedrock():
        doc=Document(target_bedrock);doc.selection=Selection((0,0,0),(127,0,127));assert doc.import_chunks(source_bedrock)==64;doc.undo();doc.redo()
    report={'java_import_undo_redo_64_empty_chunks':java_timing,
            'bedrock_import_undo_redo_64_chunks_20000_unrelated_source_records':measure(import_bedrock),
            'scope':'Synthetic fixtures, matching game metadata, this Linux host. Small cached-region/index measurements; not large-world throughput or Minecraft validation.'}
    print(json.dumps(report,indent=2))
