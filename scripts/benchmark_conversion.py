"""Measure conversion throughput and old/new journal serialization memory."""
from pathlib import Path
import hashlib
import json
import statistics
import sys
import tempfile
import time
import tracemalloc

ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'src'));sys.path.insert(0,str(ROOT))
from facetedit.leveldb import LogWriter,write_log
from facetedit.converter import prepare_conversion,publish_conversion
from facetedit.world import open_world
from tests.test_conversion import plain_java,modern_bedrock


def measure(function):
    timings=[]
    for _ in range(3):
        start=time.perf_counter();function();timings.append((time.perf_counter()-start)*1000)
    tracemalloc.start();function();peak=tracemalloc.get_traced_memory()[1];tracemalloc.stop()
    return {'median_ms':round(statistics.median(timings),3),'peak_traced_bytes':peak,'timing_runs':3,'memory_runs':1}


with tempfile.TemporaryDirectory() as tmp:
    root=Path(tmp);records=[bytes([i])*1024*1024 for i in range(8)]
    before=measure(lambda:(root/'buffered.log').write_bytes(write_log(records)))
    def stream():
        with (root/'streamed.log').open('wb') as handle:
            writer=LogWriter(handle)
            for record in records:writer.record(record)
    after=measure(stream)
    assert (root/'buffered.log').read_bytes()==(root/'streamed.log').read_bytes()
    doc=plain_java(root/'java');target=open_world(modern_bedrock(root/'bedrock'))
    started=time.perf_counter();plan=prepare_conversion(doc,target);prepared=time.perf_counter()-started
    assert plan.report.ok,plan.report.summary()
    started=time.perf_counter();output=publish_conversion(plan,root/'output');published=time.perf_counter()-started
    assert open_world(output).get_block(512,0,0).name=='minecraft:stone'
    count=len(plan.entries);plan.close()
    print(json.dumps({'scope':'This Linux host. 8 MiB preallocated journal payload; traced memory measures serialization only, not the full world/database. Five synthetic sparse chunks; no game/native-platform throughput claim.',
        'journal_before':before,'journal_streamed':after,'identical_journal_bytes':True,'journal_sha256':hashlib.sha256((root/'streamed.log').read_bytes()).hexdigest(),
        'conversion':{'chunks':count,'prepare_seconds':round(prepared,3),'publish_seconds':round(published,3)}},indent=2))
