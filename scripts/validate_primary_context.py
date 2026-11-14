"""Compare original redstone geometry with the pinned official Java method."""
import argparse,itertools,json,os,subprocess,sys,tempfile
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'src'))
from facetedit.advanced_context import wire_connections
from facetedit.blocks import AIR
from facetedit.registry import profile
from facetedit import nbt


def snbt(tag):
    if tag.kind==nbt.COMPOUND:return '{'+','.join(json.dumps(k)+':'+snbt(v) for k,v in tag.value.items())+'}'
    if tag.kind==nbt.STRING:return json.dumps(tag.value,ensure_ascii=False)
    if tag.kind==nbt.LIST:return '['+','.join(snbt(nbt.Tag(tag.value.kind,v)) for v in tag.value.values)+']'
    if tag.kind in (nbt.BYTE_ARRAY,nbt.INT_ARRAY,nbt.LONG_ARRAY):
        kind,marker={nbt.BYTE_ARRAY:(nbt.BYTE,'B'),nbt.INT_ARRAY:(nbt.INT,'I'),nbt.LONG_ARRAY:(nbt.LONG,'L')}[tag.kind]
        return '['+marker+';'+','.join(snbt(nbt.Tag(kind,v if v<128 or kind!=nbt.BYTE else v-256)) for v in tag.value)+']'
    return str(tag.value)+{nbt.BYTE:'b',nbt.SHORT:'s',nbt.INT:'',nbt.LONG:'L',nbt.FLOAT:'f',nbt.DOUBLE:'d'}[tag.kind]

def run(root):
    java=profile('Java 1.21.4');raw=json.loads((root/'generated/reports/blocks.json').read_bytes())
    ids={};states={}
    for name,data in raw.items():
        for entry in data['states']:
            block=java.block(name,entry.get('properties',{}));ids[block]=entry['id'];states[entry['id']]=block
    def block(name,**props):return java.block('minecraft:'+name,props,defaults=True)
    wire=block('redstone_wire');cases=[]
    # All primary block states beside a wire: directional signal sources,
    # partial supports and conductors are checked in the actual context method.
    for candidate in states.values():cases.append({(1,0,0):candidate})
    for candidate in states.values():
        if candidate.name not in ('minecraft:stone','minecraft:glass','minecraft:hopper','minecraft:oak_trapdoor','minecraft:oak_slab','minecraft:oak_stairs','minecraft:glowstone','minecraft:snow'):continue
        for height,covered in itertools.product((-1,1),(False,True)):
            world={(1,0,0):candidate,(1,height,0):wire}
            if covered:world[0,1,0]=block('stone')
            cases.append(world)
    for mask in range(16):
        cases.append({p:wire for i,p in enumerate(((0,0,-1),(1,0,0),(0,0,1),(-1,0,0))) if mask&(1<<i)})
    inputs=[' '.join(map(str,(i,ids[wire],*(v for p,b in world.items() for v in (*p,ids[b]))))) for i,world in enumerate(cases)]
    books=[{'id':'minecraft:written_book','count':1,'components':{'minecraft:written_book_content':{
        'title':'Field notes','author':'Builder','generation':1,'resolved':True,'pages':['{"text":"Glass","color":"aqua"}','"世界"']}}},
        {'id':'minecraft:writable_book','count':1,'components':{'minecraft:writable_book_content':{'pages':['plain text',{'raw':'filtered','filtered':'filtered'}]}}}]
    from facetedit.potion_items import POTIONS,KINDS
    books.extend({'id':'minecraft:'+kind,'count':1,'components':{'minecraft:potion_contents':{'potion':'minecraft:'+potion}}} for kind,potion in itertools.product(KINDS,POTIONS))
    sys.path.insert(0,str(ROOT))
    from facetedit.translation import Translator
    from tests.advanced_fixture import gallery
    from tests.test_conversion import plain_java
    payload_inputs=[]
    with tempfile.TemporaryDirectory(prefix='facetedit-primary-payload-') as temporary:
        document=plain_java(Path(temporary)/'java');positions=gallery(document);bedrock=profile('Bedrock 1.21.50')
        forward,reverse=Translator(java,bedrock),Translator(bedrock,java)
        for name,pos in positions.items():
            source_block=document.get(*pos);data=document.get_entity(*pos)
            native,layers,entity=forward.cell(source_block,entity=data,position=pos)
            restored,_,entity=reverse.cell(native,layers,entity,position=pos)
            if entity is not None:payload_inputs.append(name+'\t'+str(ids[restored])+'\t'+snbt(nbt.loads(entity)[1]))
        for key in ('ExitPortal','exit_portal'):
            for value_name,value in (('array',nbt.Tag(nbt.INT_ARRAY,[-19,70,32])),('compound',nbt.compound(X=nbt.Tag(nbt.INT,-19),Y=nbt.Tag(nbt.INT,70),Z=nbt.Tag(nbt.INT,32))),('lower_compound',nbt.compound(x=nbt.Tag(nbt.INT,-19),y=nbt.Tag(nbt.INT,70),z=nbt.Tag(nbt.INT,32)))):
                payload_inputs.append('gateway_'+key+'_'+value_name+'\t'+str(ids[block('end_gateway')])+'\t'+snbt(nbt.compound(**{key:value,'ExactTeleport':nbt.Tag(nbt.BYTE,1)})))
    classpath=os.pathsep.join(str(p) for p in (root/'versions/1.21.4/server-1.21.4.jar',*root.joinpath('libraries').rglob('*.jar')))
    with tempfile.TemporaryDirectory(prefix='facetedit-context-oracle-') as temporary:
        path=Path(temporary);(path/'cases').write_text('\n'.join(inputs));(path/'books').write_text('\n'.join(json.dumps(b) for b in books));(path/'payloads').write_text('\n'.join(payload_inputs))
        result=subprocess.run(['java','--class-path',classpath,str(ROOT/'scripts/PrimaryContextReport.java'),str(path/'cases'),str(path/'books'),str(path/'payloads')],cwd=path,capture_output=True,text=True)
    if result.returncode:raise RuntimeError(result.stdout[-4000:]+'\n'+result.stderr[-4000:])
    mismatches=[];count=0;book_results=[];payload_results=[]
    for line in result.stdout.splitlines():
        if line.startswith('ITEM '):book_results.append(line)
        if line.startswith(('PAYLOAD ','PAYLOAD_ERROR ')):payload_results.append(line)
        if not line.startswith('WIRE '):continue
        _,index,state_id=line.split();index=int(index);expected={k:v for k,v in states[int(state_id)].properties if k!='power'}
        world=cases[index];actual=wire_connections((0,0,0),lambda p:world.get(p,AIR));count+=1
        if actual!=expected:mismatches.append({'world':{str(p):str(b) for p,b in world.items()},'expected':expected,'actual':actual})
    return {'reference':'Official Java 1.21.4 getConnectionState + ItemStack codec, synthetic BlockGetter; no game execution',
        'wire_cases':count,'mismatch_count':len(mismatches),'mismatches':mismatches[:50],'item_codec_vectors':len(book_results),
        'item_codec_failures':[line for line in book_results if 'DataResult.Success' not in line],
        'book_codec_results':book_results[:2],'primary_block_entity_reserialization':payload_results}

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('report_root',type=Path);args=parser.parse_args()
    print(json.dumps(run(args.report_root),indent=2))
