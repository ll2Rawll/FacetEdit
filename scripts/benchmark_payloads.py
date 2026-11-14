"""Repeatable small conversion benchmarks; standard library only."""
import json
from pathlib import Path
import statistics
import sys
import time
import tracemalloc

ROOT=Path(__file__).resolve().parents[1];sys.path[:0]=[str(ROOT/'src'),str(ROOT)]
from facetedit import nbt
from facetedit.model import Clipboard
from facetedit.payloads import root
from facetedit.registry import profile
from facetedit.translation import translate_clipboard
from tests.test_payload_translation import item


def measure(clipboard,target):
    def run():
        result,report=translate_clipboard(clipboard,target)
        assert report.ok,report.summary()
        assert len(result.blocks)==len(clipboard.blocks)
        return result
    run();times=[]
    for _ in range(3):
        start=time.perf_counter();result=run();times.append(time.perf_counter()-start)
    tracemalloc.start();run();peak=tracemalloc.get_traced_memory()[1];tracemalloc.stop()
    return result,{'blocks':len(clipboard.blocks),'median_ms':round(statistics.median(times)*1000,3),'peak_traced_bytes':peak,'timing_runs':3,'memory_runs':1}


def run(target_label='Bedrock 1.21.50'):
    java=profile('Java 1.21.4');bedrock=profile(target_label)
    blocks={(x,y,z):java.initial('minecraft:chest') for y in range(16) for z in range(16) for x in range(16)}
    inventory=nbt.Tag(nbt.LIST,nbt.ListValue(nbt.COMPOUND,[{**item('diamond_sword',**{'minecraft:damage':nbt.Tag(nbt.INT,17),
        'minecraft:enchantments':nbt.compound(levels=nbt.compound(**{'minecraft:sharpness':nbt.Tag(nbt.INT,3)}))}),'Slot':nbt.Tag(nbt.BYTE,5)}]))
    clip=Clipboard((16,16,16),blocks,entities={p:root('minecraft:chest',p,'Java',{'Items':inventory}) for p in blocks})
    native,forward=measure(clip,bedrock);restored,reverse=measure(native,java)
    assert restored.blocks==clip.blocks
    print(json.dumps({'scope':'4,096 synthetic single chests, each with a damaged enchanted sword. Input construction excluded; three timed runs after warm-up and one traced run. This host only, not a whole-world/game performance claim.',
                      'java_to_bedrock':forward,'bedrock_to_java':reverse,'source_blocks_roundtrip':'pass'},indent=2))


if __name__=='__main__':
    import argparse
    parser=argparse.ArgumentParser();parser.add_argument('--target',default='Bedrock 1.21.50');args=parser.parse_args()
    run(args.target)
