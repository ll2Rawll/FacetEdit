"""Native block cells whose semantics include typed block-entity payloads."""
import json
import math

from . import nbt,text_components
from .blocks import AIR,Block
from .formats import bedrock_block,bedrock_entry
from .item_translation import ItemTranslator
from .native_rules import SIX,HORIZONTAL
from .payload_fields import Fields,compound_list,string_list
from .payload_formats import COLORS,TEXT_RGB,patterns_to_bedrock,patterns_to_java

CONTAINERS={'chest':('Chest',27),'trapped_chest':('Chest',27),'barrel':('Barrel',27),
            'dispenser':('Dispenser',9),'dropper':('Dropper',9),'hopper':('Hopper',5),
            'furnace':('Furnace',3),'blast_furnace':('BlastFurnace',3),'smoker':('Smoker',3)}
HEADS={'skeleton_skull','wither_skeleton_skull','zombie_head','player_head','creeper_head','dragon_head','piglin_head'}


def head_name(name):return name.replace('_wall_skull','_skull').replace('_wall_head','_head')


def identity_block(name,edition):
    base=name.removeprefix('minecraft:')
    if head_name(base) in HEADS:return True
    if edition=='Java':return base.endswith(('_bed','_banner','_shulker_box')) or base in ('shulker_box','flower_pot','note_block') or base.startswith('potted_')
    return base in ('bed','standing_banner','wall_banner','flower_pot','noteblock','undyed_shulker_box') or base.endswith('_shulker_box')


def fields(data,edition,expected,position):
    if data is None:result=Fields({},'Block NBT')
    else:
        try:tag=nbt.loads(data)[1]
        except ValueError as exc:raise ValueError('Block NBT: '+str(exc)) from exc
        result=Fields(tag,'Block NBT')
        identifier=result.pop('id',nbt.STRING)
        if identifier not in expected:raise ValueError(f'Block NBT.id: {identifier} does not match this block ({", ".join(expected)})')
    for axis,value in zip('xyz',position):
        if result.pop(axis,nbt.INT,value)!=value:raise ValueError('Block NBT coordinates disagree with the selected position')
    if edition=='Java':
        result.default_only('keepPacked',nbt.BYTE,0)
        result.default_only('components',nbt.COMPOUND,{})
    else:result.default_only('isMovable',nbt.BYTE,1)
    return result


def root(identifier,position,edition,values):
    values={'id':nbt.Tag(nbt.STRING,identifier),**{axis:nbt.Tag(nbt.INT,v) for axis,v in zip('xyz',position)},**values}
    if edition=='Bedrock':values['isMovable']=nbt.Tag(nbt.BYTE,1)
    return nbt.dumps(nbt.Tag(nbt.COMPOUND,values))


def custom_name(f,out,edition):
    if 'CustomName' in f.data:
        text=f.pop('CustomName',nbt.STRING)
        out['CustomName']=nbt.Tag(nbt.STRING,text_components.to_bedrock(text) if edition=='Java' else text_components.from_bedrock(text))


def sign_side(value,edition,path):
    f=Fields(value,path)
    if edition=='Java':
        messages=string_list(f.pop('messages',nbt.LIST,nbt.ListValue(nbt.STRING,['""']*4)),path+'.messages')
        if len(messages)!=4:raise ValueError(path+': signs require exactly four lines')
        filtered=string_list(f.pop('filtered_messages',nbt.LIST,nbt.ListValue(nbt.STRING,messages)),path+'.filtered_messages')
        if filtered!=messages:raise ValueError(path+': differing filtered text cannot be retained')
        color=f.pop('color',nbt.STRING,'black');glow=f.flag('has_glowing_text')
        if color not in COLORS:raise ValueError(path+': unknown sign dye')
        lines=[text_components.to_bedrock(text) for text in messages]
        if any('\n' in line or '\r' in line for line in lines):raise ValueError(path+': embedded line breaks cannot retain the four-line sign layout')
        out={'Text':nbt.Tag(nbt.STRING,'\n§r'.join(lines)),'SignTextColor':nbt.Tag(nbt.INT,TEXT_RGB[COLORS.index(color)]-(1<<24)),
             'IgnoreLighting':nbt.Tag(nbt.BYTE,int(glow)),'PersistFormatting':nbt.Tag(nbt.BYTE,1),'TextOwner':nbt.Tag(nbt.STRING,'')}
    else:
        text=f.pop('Text',nbt.STRING,'');color=f.pop('SignTextColor',nbt.INT,-16777216);glow=f.flag('IgnoreLighting')
        f.default_only('TextOwner',nbt.STRING,'')
        persist=f.flag('PersistFormatting',True)
        if color+(1<<24) not in TEXT_RGB:raise ValueError(path+': custom ARGB sign color has no exact Java dye')
        lines=text.split('\n')
        if len(lines)>4 or '\r' in text:raise ValueError(path+': sign text does not fit four Java lines')
        # Formatting can continue across native line breaks. Parse the complete
        # string once, then divide runs so Java's independent lines retain it.
        parts=[[] for _ in range(4)];line=0
        for content,style in text_components.bedrock_runs(text):
            segments=content.split('\n')
            for index,segment in enumerate(segments):
                if index:line+=1
                if line>=4:raise ValueError(path+': sign text exceeds four lines')
                if segment:parts[line].append({'text':segment,**style})
        if not persist:
            parts=[]
            for line in lines+['']*(4-len(lines)):
                parts.append([{'text':t,**style} for t,style in text_components.bedrock_runs(line)])
        messages=[json.dumps({'text':'','extra':runs},ensure_ascii=False,separators=(',',':')) if runs else '""' for runs in parts]
        out={'messages':nbt.Tag(nbt.LIST,nbt.ListValue(nbt.STRING,messages)),
             'color':nbt.Tag(nbt.STRING,COLORS[TEXT_RGB.index(color+(1<<24))]),'has_glowing_text':nbt.Tag(nbt.BYTE,int(glow))}
    f.finish();return nbt.Tag(nbt.COMPOUND,out)


def translate_cell(translator,block,layers,data,position,neighbour=None,neighbour_entity=None):
    source,target=translator.source,translator.target
    if source.label==target.label:
        base,extra=translator.block(block,layers);return base,extra,data
    if source.edition==target.edition:
        if data is not None:raise ValueError('Block NBT: cross-version payload migration is not implemented')
        base,extra=translator.block(block,layers);return base,extra,None
    name=block.name.removeprefix('minecraft:');edition=source.edition
    identity=identity_block(block.name,edition)
    container=name.removeprefix('lit_')
    is_sign=name.endswith('_sign') or name in ('standing_sign','wall_sign')
    if not identity and container not in CONTAINERS and not is_sign:
        if data is not None:raise ValueError('Block NBT: no cross-edition payload rule for '+block.name)
        base,extra=translator.block(block,layers);return base,extra,None
    block=source.validate(block,defaults=edition=='Java');p=dict(block.properties)
    chest=container in ('chest','trapped_chest')
    if not identity and not chest:
        base,extra=translator.block(block,layers)
    elif identity:
        if layers:raise ValueError('Block NBT: this payload block cannot represent extra storage layers')
        extra=()
    out={};out_id=None
    if container in CONTAINERS:
        native,capacity=CONTAINERS[container];java_id='chest' if container=='trapped_chest' else container
        f=fields(data,edition,('minecraft:'+java_id,) if edition=='Java' else (native,),position)
        if chest:
            from .paired_chests import translate
            base,extra,pairs=translate(translator,block,f,position,neighbour,neighbour_entity)
            out.update(pairs)
            if edition=='Bedrock' and layers:
                wet,_=translator.block(block,layers);props=dict(base.properties);props['waterlogged']=dict(wet.properties)['waterlogged'];base=target.block(base.name,props)
            elif edition=='Java' and layers:raise ValueError('Java input has unexpected extra layers')
        out_id=native if edition=='Java' else 'minecraft:'+java_id
        out['Items']=ItemTranslator(translator).inventory(f.pop('Items',nbt.LIST,nbt.ListValue(nbt.COMPOUND,[])),edition,capacity)
        custom_name(f,out,edition)
        if edition=='Java':f.default_only('Lock',nbt.STRING,'')
        else:f.default_only('Findable',nbt.BYTE,0)
        if container=='hopper':out['TransferCooldown']=nbt.Tag(nbt.INT,f.pop('TransferCooldown',nbt.INT,0))
        if container in ('furnace','smoker','blast_furnace'):
            for key in ('BurnTime','CookTime'):
                value=f.pop(key,nbt.SHORT,0)
                if value!=0:raise ValueError('Block NBT.'+key+': active furnace timing needs a verified fuel/recipe migration')
                out[key]=nbt.Tag(nbt.SHORT,0)
            if edition=='Java':
                total=f.pop('CookTimeTotal',nbt.SHORT,200)
                if total not in (0,200):raise ValueError('Block NBT.CookTimeTotal: custom recipe duration is unsupported')
                f.default_only('RecipesUsed',nbt.COMPOUND,{})
                out.update(BurnDuration=nbt.Tag(nbt.SHORT,0),StoredXP=nbt.Tag(nbt.FLOAT,0.0))
            else:
                f.default_only('BurnDuration',nbt.SHORT,0);f.default_only('StoredXP',nbt.FLOAT,0.0)
                out.update(CookTimeTotal=nbt.Tag(nbt.SHORT,200),RecipesUsed=nbt.compound())
    elif is_sign:
        hanging='hanging_sign' in name;java_id='hanging_sign' if hanging else 'sign';native_id='HangingSign' if hanging else 'Sign'
        f=fields(data,edition,('minecraft:'+java_id,) if edition=='Java' else (native_id,),position)
        out_id=native_id if edition=='Java' else 'minecraft:'+java_id
        for java,native in (('front_text','FrontText'),('back_text','BackText')):
            key=java if edition=='Java' else native
            out[native if edition=='Java' else java]=sign_side(f.pop(key,nbt.COMPOUND,{}),edition,'Block NBT.'+key)
        out['IsWaxed' if edition=='Java' else 'is_waxed']=nbt.Tag(nbt.BYTE,int(f.flag('is_waxed' if edition=='Java' else 'IsWaxed')))
    elif name.endswith('_bed') or name=='bed':
        f=fields(data,edition,('minecraft:bed',) if edition=='Java' else ('Bed',),position)
        if edition=='Java':
            color=name[:-4]
            if color not in COLORS:raise ValueError('Unknown bed color')
            base=target.block('minecraft:bed',{'direction':str(HORIZONTAL.index(p['facing'])),'head_piece_bit':str(p['part']=='head').lower(),'occupied_bit':p['occupied']})
            out['color']=nbt.Tag(nbt.BYTE,COLORS.index(color));out_id='Bed'
        else:
            color=f.pop('color',nbt.BYTE,14)
            if not 0<=color<16:raise ValueError('Block NBT.color: invalid bed color')
            base=target.block('minecraft:'+COLORS[color]+'_bed',{'facing':HORIZONTAL[int(p['direction'])],'part':'head' if p['head_piece_bit']=='true' else 'foot','occupied':p['occupied_bit']})
            out_id='minecraft:bed'
    elif name.endswith('_banner') or name in ('standing_banner','wall_banner'):
        f=fields(data,edition,('minecraft:banner',) if edition=='Java' else ('Banner',),position)
        custom_name(f,out,edition)
        if edition=='Java':
            wall=name.endswith('_wall_banner');color=name.removesuffix('_wall_banner' if wall else '_banner')
            if color not in COLORS:raise ValueError('Unknown banner base color')
            base=target.block('minecraft:wall_banner' if wall else 'minecraft:standing_banner',{'facing_direction':str(SIX.index(p['facing']))} if wall else {'ground_sign_direction':p['rotation']})
            out.update(Base=nbt.Tag(nbt.INT,15-COLORS.index(color)),Type=nbt.Tag(nbt.INT,0))
            out['Patterns']=patterns_to_bedrock(f.pop('patterns',nbt.LIST,nbt.ListValue(nbt.COMPOUND,[])),'Block NBT.patterns');out_id='Banner'
        else:
            color=f.pop('Base',nbt.INT,15);f.default_only('Type',nbt.INT,0)
            if not 0<=color<16:raise ValueError('Block NBT.Base: invalid banner base color')
            wall=name=='wall_banner';base=target.block('minecraft:'+COLORS[15-color]+('_wall_banner' if wall else '_banner'),{'facing':SIX[int(p['facing_direction'])]} if wall else {'rotation':p['ground_sign_direction']})
            out['patterns']=patterns_to_java(f.pop('Patterns',nbt.LIST,nbt.ListValue(nbt.COMPOUND,[])),'Block NBT.Patterns');out_id='minecraft:banner'
    elif name.endswith('_shulker_box') or name=='shulker_box':
        f=fields(data,edition,('minecraft:shulker_box',) if edition=='Java' else ('ShulkerBox',),position)
        if edition=='Java':
            base=target.block('minecraft:undyed_shulker_box' if name=='shulker_box' else block.name,{})
            out['facing']=nbt.Tag(nbt.BYTE,SIX.index(p['facing']));out_id='ShulkerBox';f.default_only('Lock',nbt.STRING,'')
        else:
            facing=f.pop('facing',nbt.BYTE,1)
            if not 0<=facing<6:raise ValueError('Block NBT.facing: invalid shulker direction')
            base=target.block('minecraft:shulker_box' if name=='undyed_shulker_box' else block.name,{'facing':SIX[facing]})
            out_id='minecraft:shulker_box';f.default_only('Findable',nbt.BYTE,0)
        custom_name(f,out,edition)
        out['Items']=ItemTranslator(translator).inventory(f.pop('Items',nbt.LIST,nbt.ListValue(nbt.COMPOUND,[])),edition,27)
    elif head_name(name) in HEADS:
        f=fields(data,edition,('minecraft:skull',) if edition=='Java' else ('Skull',),position)
        if edition=='Java':
            f.default_only('profile',nbt.COMPOUND,{})
            f.default_only('note_block_sound',nbt.STRING,'')
            if p['powered']!='false':raise ValueError('Powered head animation has no verified native migration')
            wall='_wall_' in name;rotation=0 if wall else int(p['rotation'])
            base=target.block('minecraft:'+head_name(name),{'facing_direction':str(SIX.index(p['facing'])) if wall else '1'})
            out.update(Rotation=nbt.Tag(nbt.FLOAT,(rotation if rotation<=8 else rotation-16)*22.5),SkullType=nbt.Tag(nbt.BYTE,0),
                       MouthMoving=nbt.Tag(nbt.BYTE,0),MouthTickCount=nbt.Tag(nbt.INT,0));out_id='Skull'
        else:
            f.default_only('SkullType',nbt.BYTE,0);f.default_only('MouthMoving',nbt.BYTE,0);f.default_only('MouthTickCount',nbt.INT,0)
            rotation=f.pop('Rotation',nbt.FLOAT,0.0);face=int(p['facing_direction'])
            if not math.isfinite(rotation) or rotation%22.5:raise ValueError('Head rotation does not fit a Java 16-step rotation')
            if face==1:props={'rotation':str(round(rotation/22.5)%16),'powered':'false'};java_name=name
            elif 2<=face<6 and rotation==0:
                java_name=name.replace('_skull','_wall_skull') if name.endswith('_skull') else name.replace('_head','_wall_head')
                props={'facing':SIX[face],'powered':'false'}
            else:raise ValueError('Head mount/rotation has no matching Java state')
            base=target.block('minecraft:'+java_name,props);out_id='minecraft:skull'
    elif name=='flower_pot' or name.startswith('potted_'):
        f=fields(data,edition,('minecraft:flower_pot',) if edition=='Java' else ('FlowerPot',),position)
        if edition=='Java':
            base=target.block('minecraft:flower_pot',{'update_bit':'false'});out_id='FlowerPot'
            if name.startswith('potted_'):
                plant=name[7:];plant={'azalea_bush':'azalea','flowering_azalea_bush':'flowering_azalea'}.get(plant,plant)
                value=source.initial('minecraft:'+plant);native,water=translator.block(value)
                if water:raise ValueError('Flower-pot plant cannot require an extra water layer')
                out['PlantBlock']=bedrock_entry(native,target.palette_version)
        else:
            if p['update_bit']!='false':raise ValueError('Flower-pot update state is not representable in Java')
            java_name='flower_pot'
            if 'PlantBlock' in f.data:
                plant=f.pop('PlantBlock',nbt.COMPOUND);descriptor=Fields(plant,'Block NBT.PlantBlock')
                descriptor.pop('name',nbt.STRING);descriptor.pop('states',nbt.COMPOUND);descriptor.pop('version',nbt.INT);descriptor.finish()
                value,_=translator.block(bedrock_block(nbt.Tag(nbt.COMPOUND,plant)))
                if value!=target.initial(value.name):raise ValueError('Flower-pot plant state has no Java potted-block equivalent')
                plant_name=value.name.removeprefix('minecraft:');plant_name={'azalea':'azalea_bush','flowering_azalea':'flowering_azalea_bush'}.get(plant_name,plant_name)
                java_name='potted_'+plant_name
            base=target.block('minecraft:'+java_name,{});out_id=None
    elif name in ('note_block','noteblock'):
        f=fields(data,edition,('minecraft:noteblock',) if edition=='Java' else ('Music',),position)
        from .state_facts import instrument
        def java_at(delta):
            point=tuple(a+b for a,b in zip(position,delta));other=neighbour(point) if neighbour else None
            if other is None:return AIR
            if edition=='Java':return source.validate(other,defaults=True)
            if other.name=='minecraft:noteblock':return target.initial('minecraft:note_block')
            return translator.cell(other,entity=neighbour_entity(point) if neighbour_entity else None,position=point)[0]
        expected=instrument(java_at((0,-1,0)),java_at((0,1,0)))
        if expected in ('skeleton','wither_skeleton','zombie','creeper','dragon','piglin','custom_head'):
            raise ValueError('Head instrument semantics require further cross-edition verification')
        if edition=='Java':
            if p['powered']!='false':raise ValueError('Powered note block has no verified native power payload')
            if p['instrument']!=expected:raise ValueError('Note-block instrument disagrees with its neighbours')
            base=target.block('minecraft:noteblock',{});out['note']=nbt.Tag(nbt.BYTE,int(p['note']));out_id='Music'
        else:
            note=f.pop('note',nbt.BYTE,0)
            if not 0<=note<=24:raise ValueError('Block NBT.note: note is outside 0–24')
            base=target.block('minecraft:note_block',{'note':str(note),'powered':'false','instrument':expected});out_id=None
    else:raise ValueError('Block NBT: no cell rule for '+block.name)
    f.finish()
    return base,extra,root(out_id,position,target.edition,out) if out_id is not None else None
