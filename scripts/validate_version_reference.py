"""Independent state/native-reader checks for the additional Bedrock profile.

Optional Amulet/NumPy/native LevelDB packages are development oracles only.
This script does not generate mappings and never starts a Minecraft game.
"""
import argparse,hashlib,itertools,json,shutil,sys,tempfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path[:0]=[str(ROOT/'src'),str(ROOT)]
from facetedit import nbt
from facetedit.blocks import Block
from facetedit.converter import prepare_conversion,publish_conversion
from facetedit.model import Document,Selection
from facetedit.registry import profile
from facetedit.translation import Translator
from facetedit.structures import export_structure
from facetedit.world import open_world
from tests.test_conversion import plain_java
from tests.version_fixture import bedrock_version,gallery
from scripts.validate_translation_reference import canonical
from scripts.validate_payload_reference import read_bedrock,read_java
import PyMCTranslate,amulet
from amulet import Block as ReferenceBlock
from amulet_nbt import ByteTag,IntTag,StringTag


def metadata_audit(root):
    changes={}
    for kind,key in (('blocks','name'),('items','serialization_name'),('biomes','name'),('entities','name'),('enchantments','name')):
        data=[json.loads((root/f'bedrock-1.21.{minor}-{kind}.json').read_bytes()) for minor in (50,60)]
        a,b=({v[key]:v for v in d['data_items']} for d in data)
        changes[kind]={'added':sorted(b.keys()-a.keys()),'removed':sorted(a.keys()-b.keys()),
                       'changed':sorted(k for k in a.keys()&b.keys() if a[k]!=b[k])}
    assert len(changes['blocks']['changed'])==34
    assert changes['items']['removed']==['minecraft:air']
    return {'primary_tag':'Mojang/bedrock-samples v1.21.60.10','profile_changes':changes}


def state_audit():
    manager=PyMCTranslate.new_translation_manager();reports=[]
    for source_label,target_label in (('Bedrock 1.21.50','Bedrock 1.21.60'),('Bedrock 1.21.60','Bedrock 1.21.50')):
        source,target=profile(source_label),profile(target_label);translator=Translator(source,target);reverse=Translator(target,source)
        a=manager.get_version('bedrock',source.version).block;b=manager.get_version('bedrock',target.version).block
        assert manager.get_version('bedrock',source.version).data_version==source.palette_version
        cases=compared=ignored=blocked=0;mismatches=[]
        for name,schema in source.blocks.items():
            if not (name.endswith(('_door','fence_gate')) or name=='minecraft:creaking_heart'):continue
            keys=schema['properties']
            for values in itertools.product(*(v[1] for v in keys.values())):
                native=source.block(name,dict(zip(keys,values)));p=dict(native.properties);cases+=1
                try:actual,_=translator.block(native)
                except ValueError:
                    assert p.get('creaking_heart_state')=='uprooted',native
                    blocked+=1;continue
                assert reverse.block(actual)[0]==native,native
                if p.get('upper_block_bit')=='true':ignored+=1;continue
                fields={k:(ByteTag(v=='true') if dict(native.state_types)[k]==1 else IntTag(int(v)) if dict(native.state_types)[k]==3 else StringTag(v)) for k,v in native.properties}
                universal,entity,_=a.to_universal(ReferenceBlock(*name.split(':',1),fields));expected,_,_=b.from_universal(universal,entity)
                ours,reference=dict(actual.properties),dict(canonical(expected).properties)
                # Lower door hinge bits and upper orientation/open flags are
                # ignored native storage. Keep them on migration and in exact
                # inverse checks rather than comparing a canonicalized oracle.
                if name.endswith('_door'):
                    ours.pop('door_hinge_bit',None);reference.pop('door_hinge_bit',None)
                compared+=1
                if ours!=reference:mismatches.append({'input':str(native),'actual':ours,'reference':reference})
        reports.append({'source':source_label,'target':target_label,'native_vectors':cases,'reference_comparisons':compared,
                        'ignored_upper_storage_vectors_preserved':ignored,'unrepresentable_uprooted_states_blocked':blocked,
                        'exact_inverse_checks':cases-blocked,'mismatch_count':len(mismatches),'mismatches':mismatches[:30]})
    return reports


def worlds_audit():
    with tempfile.TemporaryDirectory(prefix='facetedit-version-reference-') as temporary:
        path=Path(temporary);source=plain_java(path/'java');positions=gallery(source);rows=[]
        templates={minor:open_world(bedrock_version(path/f'template{minor}',(1,21,minor))) for minor in (50,60)}
        def convert(doc,target,label):
            plan=prepare_conversion(doc,target)
            try:
                assert plan.report.ok,plan.report.summary();output=publish_conversion(plan,path/label)
            finally:plan.close()
            return Document(open_world(output))
        old=convert(source,templates[50],'native50');modern=convert(source,templates[60],'native60')
        upgraded=convert(old,templates[60],'upgraded');downgraded=convert(modern,templates[50],'downgraded')
        restored=convert(modern,source.world,'java-restored')
        for label,doc,minor in (('java_to_60',modern,60),('50_to_60',upgraded,60),('60_to_50',downgraded,50)):
            audit=path/('audit-'+label);shutil.copytree(doc.world.path,audit)
            tags=read_bedrock(audit)
            assert tags[positions['chest']]['Items'][0]['tag']['Items'][0]['Block']['version'].py_int==profile(f'Bedrock 1.21.{minor}').palette_version
            assert tags[positions['plant']]['PlantBlock']['version'].py_int==profile(f'Bedrock 1.21.{minor}').palette_version
            assert tags[positions['lectern']]['book']['tag']['title'].py_str=='Builder notes'
            assert tags[positions['campfire']]['ItemTime3'].py_int==37
            assert tags[positions['brewing']]['CookTime'].py_int==123
            reference=amulet.load_level(str(audit))
            try:
                version=('bedrock',(1,21,minor))
                lower,_=reference.get_version_block(*positions['door_lower'],'minecraft:overworld',version)
                gate,_=reference.get_version_block(*positions['gate'],'minecraft:overworld',version)
                stone,_=reference.get_version_block(-16,1,-16,'minecraft:overworld',version)
                assert stone.namespaced_name=='minecraft:stone'
                if minor==60:
                    assert lower.properties['minecraft:cardinal_direction'].py_str=='north',lower
                    assert gate.properties['minecraft:cardinal_direction'].py_str=='east',gate
                else:assert lower.properties['direction'].py_int==2 and gate.properties['direction'].py_int==3
            finally:reference.close()
            rows.append({'route':label,'native_payloads':len(tags),'native_LevelDB_NBT_fields':'pass','Amulet_native_block_reopen':'pass','negative_chunk':'pass'})
        java_tags=read_java(restored.world.path)
        assert list(java_tags[positions['gateway']]['exit_portal'].py_data)==[-19,70,32]
        for name,p in positions.items():assert restored.get(*p)==source.get(*p),(name,restored.get(*p),source.get(*p))
        rows.append({'route':'60_to_java','native_payloads':len(java_tags),'independent_Anvil_NBT_fields':'pass','all_gallery_blocks':'pass'})
        modern.selection=Selection((0,15,0),(17,23,15));modern.copy();structure=path/'gallery60.mcstructure';export_structure(modern.clipboard,structure)
        reference=amulet.load_level(str(structure))
        try:
            block,_=reference.get_version_block(15,0,14,reference.dimensions[0],('bedrock',(1,21,60)))
            assert block.properties['minecraft:cardinal_direction'].py_str=='north',block
        finally:reference.close()
        rows.append({'route':'60_mcstructure','independent_native_reopen':'pass','cardinal_door':'pass'})
        return rows


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--metadata-dir',type=Path,required=True);args=parser.parse_args()
    print(json.dumps({'metadata':metadata_audit(args.metadata_dir),'changed_native_states':state_audit(),
                      'worlds':worlds_audit(),'minecraft_game_execution':False},indent=2))
