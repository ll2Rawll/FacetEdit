"""Bounded native version-migration benchmark; standard library only."""
import json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path[:0]=[str(ROOT/'src'),str(ROOT)]
from facetedit import nbt
from facetedit.model import Clipboard
from facetedit.payloads import root
from facetedit.registry import profile
from scripts.benchmark_payloads import measure

old,new=profile('Bedrock 1.21.50'),profile('Bedrock 1.21.60')
blocks={(x,y,z):old.initial('minecraft:chest') for y in range(16) for z in range(16) for x in range(16)}
items=nbt.Tag(nbt.LIST,nbt.ListValue(nbt.COMPOUND,[{'Name':nbt.Tag(nbt.STRING,'minecraft:diamond_sword'),
    'Count':nbt.Tag(nbt.BYTE,1),'Damage':nbt.Tag(nbt.SHORT,0),'Slot':nbt.Tag(nbt.BYTE,5)}]))
clip=Clipboard((16,16,16),blocks,'Bedrock',entities={p:root('Chest',p,'Bedrock',{'Items':items}) for p in blocks},data_version=None,game_version=old.version)
modern,forward=measure(clip,new);restored,reverse=measure(modern,old)
assert restored==clip
print(json.dumps({'scope':'4,096 synthetic native single chests with one sword each. Three timed runs after warm-up and one traced run; input construction excluded. This host only; no large-world/game speed claim.',
                  '50_to_60':forward,'60_to_50':reverse,'native_fields_roundtrip':'exact'},indent=2))
