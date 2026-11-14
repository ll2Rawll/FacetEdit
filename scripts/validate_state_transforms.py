"""Exhaustive accepted palette states: translation/transform commutativity."""
import itertools,json,sys
from collections import Counter
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'src'))
from facetedit.registry import profile
from facetedit.translation import Translator

java=profile('Java 1.21.4');bedrock=profile('Bedrock 1.21.50');translator=Translator(java,bedrock)
count=0;states=0;failures=[];unrepresentable=Counter();mismatch_count=0;by_name=Counter();native_only=[]
for name,schema in java.blocks.items():
    props=schema['properties']
    for values in itertools.product(*(v[1] for v in props.values())):
        block=java.block(name,dict(zip(props,values)))
        try:native,layers=translator.block(block)
        except ValueError:continue
        states+=1
        for turns,mirror in itertools.product(range(4),(False,True)):
            try:
                expected,extra=translator.block(block.transform(turns,mirror,'Java'))
            except ValueError as exc:
                unrepresentable[str(exc)]+=1;continue
            count+=1
            try:
                actual=native.transform(turns,mirror,'Bedrock');actual_extra=tuple(b.transform(turns,mirror,'Bedrock') for b in layers)
                if (expected,extra)==(actual,actual_extra):continue
                if name=='minecraft:pumpkin':
                    # Java uncarved pumpkins lack an orientation; Bedrock's
                    # top-texture direction cannot commute across that loss.
                    native_only.append({'input':str(block),'turns':turns,'mirror':mirror,'native_orientation':str(actual),'java_canonical':str(expected)});continue
                error={'actual':str(actual),'expected':str(expected)}
            except ValueError as exc:error={'error':str(exc)}
            mismatch_count+=1
            by_name[name]+=1
            if by_name[name]<=2:failures.append({'input':str(block),'turns':turns,'mirror':mirror,**error})
print(json.dumps({'accepted_states':states,'comparable_transform_cases':count-len(native_only),'unrepresentable_transformed_states':dict(unrepresentable),'native_only_orientation_differences':native_only,
                  'mismatch_count':mismatch_count,'mismatch_blocks':dict(by_name),'examples_by_block':failures},indent=2))
