"""Constructed native version fixtures; these are not game-generated saves."""
from pathlib import Path
import struct

from facetedit import nbt
from facetedit.model import Selection
from facetedit.payloads import root
from facetedit.registry import profile
from tests.advanced_fixture import gallery as advanced_gallery
from tests.test_conversion import modern_bedrock
from tests.test_advanced_translation import item,tag,sequence


def bedrock_version(path,version=(1,21,60)):
    path=Path(modern_bedrock(path));data=nbt.loads((path/'level.dat').read_bytes()[8:],little=True)[1]
    data.value['lastOpenedWithVersion']=sequence(nbt.INT,[*version,10,0])
    raw=nbt.dumps(data,little=True);(path/'level.dat').write_bytes(struct.pack('<II',10,len(raw))+raw)
    return path


def gallery(document):
    positions=advanced_gallery(document);java=profile('Java 1.21.4')
    def put(label,pos,name,payload=None,**props):
        positions[label]=pos;document.selection=Selection(pos,pos);document.fill(java.block('minecraft:'+name,props,defaults=True))
        if payload is not None:document.set_entity(pos,nbt.loads(root('minecraft:'+name,pos,'Java',payload))[1])
    for y,half in ((15,'lower'),(16,'upper')):
        put('door_'+half,(15,y,14),'oak_door',half=half,facing='west',hinge='right',open='true')
    put('gate',(17,22,14),'pale_oak_fence_gate',facing='east',open='true')
    put('plant',(5,22,14),'potted_bamboo')
    gate=item('oak_fence_gate',components={'minecraft:block_state':nbt.compound(facing=tag(nbt.STRING,'west'),open=tag(nbt.STRING,'true'))})
    shulker=item('blue_shulker_box',components={'minecraft:container':sequence(nbt.COMPOUND,[{'slot':tag(nbt.INT,26),'item':tag(nbt.COMPOUND,gate)}])})
    put('chest',(3,22,14),'chest',{'Items':sequence(nbt.COMPOUND,[{**shulker,'Slot':tag(nbt.BYTE,12)}])})
    return positions
