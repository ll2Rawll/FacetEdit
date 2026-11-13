"""Optional payload checks against isolated Amulet and independent native readers.

This is development code. None of the oracle packages or their translation
tables are imported or bundled by FacetEdit. Native readers validate storage,
not the behaviour of a running Minecraft game.
"""
import io
import itertools
import json
from pathlib import Path
import struct
import sys
import tempfile
import zlib

ROOT=Path(__file__).resolve().parents[1];sys.path[:0]=[str(ROOT/'src'),str(ROOT)]
from facetedit import nbt
from facetedit.blocks import Block
from facetedit.converter import prepare_conversion,publish_conversion
from facetedit.model import Document
from facetedit.payloads import identity_block
from facetedit.registry import profile
from facetedit.translation import Translator
from facetedit.world import open_world
from tests.payload_fixture import gallery
from tests.test_conversion import plain_java,modern_bedrock
from scripts.validate_translation_reference import canonical
import PyMCTranslate
from amulet import Block as ReferenceBlock
import amulet_nbt as reference_nbt
from amulet_nbt import ByteTag,IntTag,ShortTag,StringTag
import leveldb


def cell_audit():
    manager=PyMCTranslate.new_translation_manager();java=profile('Java 1.21.4');bedrock=profile('Bedrock 1.21.50')
    translator=Translator(java,bedrock);j=manager.get_version('java',java.version).block;b=manager.get_version('bedrock',bedrock.version).block
    count=0;types=set();failures=[];plant_versions=set();unavailable=[]
    for name,schema in java.blocks.items():
        if not identity_block(name,'Java'):continue
        properties=schema['properties']
        for values in itertools.product(*(entry[1] for entry in properties.values())):
            block=java.block(name,dict(zip(properties,values)))
            try:ours,layers,entity=translator.cell(block)
            except ValueError:continue
            count+=1;types.add(name)
            reference=ReferenceBlock(*name.split(':',1),{k:StringTag(v) for k,v in block.properties})
            universal,payload,_=j.to_universal(reference);expected,payload,_=b.from_universal(universal,payload)
            actual=Block(ours.name,ours.properties)
            if canonical(expected)!=actual:failures.append({'block':str(block),'field':'base','actual':str(actual),'reference':str(expected)})
            tag=nbt.loads(entity)[1].value if entity else {}
            if entity and tag['id'].value!=payload.base_name:failures.append({'block':str(block),'field':'id'})
            for key in ('color','Base','Type','facing','note','isMovable','SkullType','Rotation','MouthMoving','MouthTickCount'):
                if key in tag and key in payload.nbt.compound:
                    ref=payload.nbt.compound[key]
                    value=ref.py_float if tag[key].kind==nbt.FLOAT else ref.py_int
                    if tag[key].kind!=ref.tag_id or tag[key].value!=value:failures.append({'block':str(block),'field':key})
            if 'PlantBlock' in tag:
                if 'PlantBlock' not in payload.nbt.compound:
                    unavailable.append({'block':str(block),'field':'PlantBlock','reason':'The reference emitted no plant descriptor for this source block.'});continue
                ref=payload.nbt.compound['PlantBlock'];plant_versions.add(ref['version'].py_int)
                plant=ReferenceBlock(*ref['name'].py_str.split(':',1),dict(ref['states']))
                # The oracle embeds historical PlantBlock schemas. Normalize
                # through that declared version before comparing current states.
                universal,be,_=manager.get_version('bedrock',ref['version'].py_int).block.to_universal(plant)
                if universal.namespace!='universal_minecraft':
                    unavailable.append({'block':str(block),'field':'PlantBlock','reason':'The reference historical descriptor cannot translate through its own declared version.'});continue
                plant,_,_=b.from_universal(universal,be)
                from facetedit.formats import bedrock_block
                native=bedrock_block(tag['PlantBlock'])
                if Block(native.name,native.properties)!=canonical(plant):
                    failures.append({'block':str(block),'field':'PlantBlock','actual':str(native),'reference':str(plant)})
    return {'identity_block_types':len(types),'state_and_payload_vectors':count,'mismatch_count':len(failures),'mismatches':failures,
            'unavailable_reference_field_checks':unavailable,
            'historical_reference_plant_versions':sorted(plant_versions),'output_plant_version':bedrock.palette_version}


def read_bedrock(path):
    database=leveldb.LevelDB(str(path/'db'),create_if_missing=False);entities={}
    try:
        for key,value in database.items():
            if len(key)==9 and key[-1:]==b'1':
                cursor=0
                while cursor<len(value):
                    context=reference_nbt.ReadContext()
                    named=reference_nbt.load(value[cursor:],compressed=False,little_endian=True,read_context=context)
                    tag=named.compound;cursor+=context.offset
                    entities[tuple(tag[a].py_int for a in 'xyz')]=tag
    finally:database.close()
    return entities


def read_java(path):
    entities={}
    for region in path.joinpath('region').glob('*.mca'):
        data=region.read_bytes()
        for index in range(1024):
            offset=int.from_bytes(data[index*4:index*4+3],'big')*4096
            if not offset:continue
            length=struct.unpack_from('>I',data,offset)[0];assert data[offset+4]==2
            tag=reference_nbt.load(zlib.decompress(data[offset+5:offset+4+length]),compressed=False).compound
            for entity in tag.get('block_entities',[]):entities[tuple(entity[a].py_int for a in 'xyz')]=entity
    return entities


def native_world_audit():
    with tempfile.TemporaryDirectory(prefix='facetedit-payload-reference-') as temporary:
        root=Path(temporary);source=plain_java(root/'source');positions=gallery(source)
        plan=prepare_conversion(source,open_world(modern_bedrock(root/'template')))
        try:
            assert plan.report.ok,plan.report.summary();output=publish_conversion(plan,root/'bedrock')
        finally:plan.close()
        bedrock=read_bedrock(output)
        chest=bedrock[positions['chest']];entry=chest['Items'][0]
        assert chest['id'].py_str=='Chest' and isinstance(entry['Count'],ByteTag) and entry['Count'].py_int==1
        assert entry['Slot'].py_int==26 and isinstance(entry['Damage'],ShortTag) and entry['Damage'].py_int==0
        assert entry['Name'].py_str=='minecraft:diamond_sword'
        assert isinstance(entry['tag']['Damage'],IntTag) and entry['tag']['Damage'].py_int==47
        enchant=entry['tag']['ench'][0];assert isinstance(enchant['id'],ShortTag) and enchant['id'].py_int==9 and enchant['lvl'].py_int==5
        assert entry['tag']['display']['Name'].py_str=='§r§bAurora'
        sign=bedrock[positions['sign']];assert sign['FrontText']['SignTextColor'].py_int==-16711681
        assert sign['FrontText']['IgnoreLighting'].py_int==1 and sign['IsWaxed'].py_int==1
        assert '世界' in sign['FrontText']['Text'].py_str and '§lFacetEdit' in sign['BackText']['Text'].py_str
        assert bedrock[positions['bed']]['color'].py_int==9
        banner=bedrock[positions['banner']];assert banner['Base'].py_int==1 and banner['Patterns'][0]['Pattern'].py_str=='bs' and banner['Patterns'][0]['Color'].py_int==15
        assert bedrock[positions['shulker']]['facing'].py_int==5
        assert bedrock[positions['pot']]['PlantBlock']['name'].py_str=='minecraft:mangrove_propagule'
        assert bedrock[positions['pot']]['PlantBlock']['version'].py_int==18163713
        assert bedrock[positions['note']]['note'].py_int==19
        assert bedrock[positions['head']]['Rotation'].py_float==-112.5
        assert bedrock[positions['left']]['pairx'].py_int==16 and bedrock[positions['right']]['pairx'].py_int==15
        assert bedrock[positions['left']]['pairlead'].py_int==0 and bedrock[positions['right']]['pairlead'].py_int==1
        plan=prepare_conversion(Document(open_world(output)),source.world)
        try:
            assert plan.report.ok,plan.report.summary();output=publish_conversion(plan,root/'java')
        finally:plan.close()
        java=read_java(output);entry=java[positions['chest']]['Items'][0]
        assert entry['id'].py_str=='minecraft:diamond_sword' and isinstance(entry['count'],IntTag)
        assert isinstance(entry['Slot'],ByteTag) and entry['Slot'].py_int==26
        assert entry['components']['minecraft:damage'].py_int==47
        assert entry['components']['minecraft:enchantments']['levels']['minecraft:sharpness'].py_int==5
        sign=java[positions['sign']];assert sign['front_text']['color'].py_str=='cyan' and sign['front_text']['has_glowing_text'].py_int==1
        assert sign['is_waxed'].py_int==1 and positions['pot'] not in java and positions['note'] not in java
        return {'bedrock_payloads_read':len(bedrock),'java_payloads_read':len(java),'typed_inventory_sign_color_pattern_direction_note_and_pair_checks':'pass',
                'bedrock_reader':'native amulet-leveldb 1.0.7 + amulet-nbt 2.1.8','java_reader':'independent Anvil sector reader + amulet-nbt 2.1.8'}


if __name__=='__main__':
    print(json.dumps({'cell_reference':cell_audit(),'native_worlds':native_world_audit(),'game_execution':False},indent=2))
