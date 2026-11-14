"""Independent native readers and official Java reserialization checks.

Optional development dependencies are isolated outside the shipped application.
These checks verify bytes and field acceptance, not execution in Minecraft.
"""
import argparse,json,sys,tempfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path[:0]=[str(ROOT/'src'),str(ROOT)]
from facetedit.converter import prepare_conversion,publish_conversion
from facetedit.model import Document
from facetedit.world import open_world
from tests.test_conversion import plain_java,modern_bedrock
from tests.advanced_fixture import gallery
from scripts.validate_payload_reference import read_bedrock,read_java
import amulet_nbt as reference


def primary_audit(path):
    report=json.loads(path.read_bytes());assert report['mismatch_count']==0
    assert report['wire_cases']==28566 and report['item_codec_vectors']==182 and not report['item_codec_failures']
    tags={}
    for row in report['primary_block_entity_reserialization']:
        status,name,snbt=row.split(' ',2);assert status=='PAYLOAD',row
        assert name not in tags,name
        tags[name]=reference.from_snbt(snbt)
    actual={name for name in tags if not name.startswith('gateway_')}
    assert actual=={'lectern','bookshelf','jukebox','pot','brushable','command','gateway','campfire','structure','bell',
                    'brewing','crafter','beacon','spawner','sensor','shrieker','catalyst','heart'},actual
    gateway=tags['gateway'];assert list(gateway['exit_portal'].py_data)==[-19,70,32] and gateway['Age'].py_int==40
    assert isinstance(gateway['exit_portal'],reference.IntArrayTag)
    assert list(tags['campfire']['CookingTimes'].py_data)==[0,0,37,0]
    assert tags['campfire']['Items'][0]['Slot'].py_int==2
    assert tags['lectern']['Page'].py_int==1
    assert tags['lectern']['Book']['components']['minecraft:written_book_content']['title']['raw'].py_str=='Builder notes'
    assert tags['bookshelf']['last_interacted_slot'].py_int==5 and len(tags['bookshelf']['Items'])==2
    assert tags['jukebox']['RecordItem']['id'].py_str=='minecraft:music_disc_cat'
    assert tags['pot']['item']['count'].py_int==9 and tags['pot']['sherds'][2].py_str=='minecraft:arms_up_pottery_sherd'
    assert tags['brushable']['item']['id'].py_str=='minecraft:emerald' and tags['brushable']['item']['count'].py_int==3
    assert tags['command']['Command'].py_str=='say Build complete' and tags['command']['auto'].py_int==1
    assert tags['structure']['rotation'].py_str=='CLOCKWISE_90' and tags['structure']['sizeZ'].py_int==9
    assert not tags['bell']
    assert tags['brewing']['BrewTime'].py_int==123 and tags['brewing']['Fuel'].py_int==7
    assert list(tags['crafter']['disabled_slots'].py_data)==[2,5,8] and isinstance(tags['crafter']['triggered'],reference.IntTag)
    assert tags['beacon']['primary_effect'].py_str=='minecraft:speed'
    assert tags['spawner']['SpawnData']['entity']['id'].py_str=='minecraft:skeleton' and tags['spawner']['Delay'].py_int==37
    assert tags['sensor']['listener']['selector']['tick'].py_int==-1
    assert tags['shrieker']['warning_level'].py_int==0
    assert len(tags['catalyst']['cursors'])==0 and len(tags['heart'])==0
    for name,value in tags.items():
        if name.startswith('gateway_'):
            self_retains=name=='gateway_exit_portal_array'
            assert ('exit_portal' in value)==self_retains
    assert len(tags)-len(actual)==6
    return {'official_java_block_entity_records_checked':len(actual),'gateway_shape_cases':len(tags)-len(actual),'wire_context_vectors':report['wire_cases'],'item_codec_vectors':report['item_codec_vectors'],'lost_checked_fields':0}


def native_audit():
    with tempfile.TemporaryDirectory(prefix='facetedit-advanced-native-') as temporary:
        path=Path(temporary);source=plain_java(path/'source');positions=gallery(source)
        plan=prepare_conversion(source,open_world(modern_bedrock(path/'template')))
        try:
            assert plan.report.ok,plan.report.summary();native_path=publish_conversion(plan,path/'bedrock')
        finally:plan.close()
        native=read_bedrock(native_path)
        def get(name):return native[positions[name]]
        assert get('lectern')['book']['Name'].py_str=='minecraft:written_book'
        assert get('lectern')['book']['tag']['pages'][1]['text'].py_str.endswith('世界')
        assert get('lectern')['page'].py_int==1 and get('lectern')['totalPages'].py_int==2
        assert get('bookshelf')['LastInteractedSlot'].py_int==6
        assert get('campfire')['ItemTime3'].py_int==37 and get('campfire')['Item3']['Name'].py_str=='minecraft:beef'
        assert get('piston')['State'].py_int==2 and isinstance(get('piston')['isMovable'],reference.ByteTag) and get('piston')['isMovable'].py_int==0
        assert isinstance(get('bell')['Direction'],reference.IntTag) and isinstance(get('bell')['Ticks'],reference.IntTag)
        assert isinstance(get('gateway')['Age'],reference.IntTag) and get('gateway')['Age'].py_int==40
        assert [v.py_int for v in get('gateway')['ExitPortal']]==[-19,70,32]
        brew=get('brewing');assert isinstance(brew['FuelAmount'],reference.ShortTag) and brew['FuelAmount'].py_int==7
        slots={v['Slot'].py_int:v for v in brew['Items']};assert slots[1]['Damage'].py_int==34 and slots[0]['Name'].py_str=='minecraft:redstone'
        assert isinstance(get('crafter')['disabled_slots'],reference.ShortTag) and get('crafter')['disabled_slots'].py_int==292
        assert get('cauldron')['PotionId'].py_int==-1
        assert get('spawner')['EntityIdentifier'].py_str=='minecraft:skeleton' and get('spawner')['Delay'].py_int==37
        assert get('sensor')['VibrationListener']['selector']==reference.CompoundTag()
        plan=prepare_conversion(Document(open_world(native_path)),source.world)
        try:
            assert plan.report.ok,plan.report.summary();java_path=publish_conversion(plan,path/'java')
        finally:plan.close()
        java=read_java(java_path)
        assert list(java[positions['gateway']]['exit_portal'].py_data)==[-19,70,32]
        assert java[positions['bookshelf']]['last_interacted_slot'].py_int==5
        assert positions['piston'] not in java and positions['cauldron'] not in java
        return {'bedrock_block_entities':len(native),'java_block_entities':len(java),'independent_typed_field_checks':'pass',
            'readers':'native amulet-leveldb 1.0.7 and amulet-nbt 2.1.8; independent Anvil-sector traversal'}

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--primary-context',type=Path,required=True);args=parser.parse_args()
    print(json.dumps({'primary':primary_audit(args.primary_context),'native_worlds':native_audit(),'minecraft_game_execution':False},indent=2))
