"""Explicit native handlers for interactive and technical block entities.

Unknown runtime state is never copied into a foreign edition as opaque NBT.
These handlers share typed item/text conversion with ordinary containers.
"""
import math
import re

from . import nbt
from .item_translation import ItemTranslator,JAVA_ITEMS
from .payload_fields import Fields,compound_list,string_list

IDS={
    'bee_nest':('beehive','Beehive'),'beehive':('beehive','Beehive'),
    'bell':('bell','Bell'),'campfire':('campfire','Campfire'),'soul_campfire':('campfire','Campfire'),
    'chiseled_bookshelf':('chiseled_bookshelf','ChiseledBookshelf'),
    'command_block':('command_block','CommandBlock'),'chain_command_block':('command_block','CommandBlock'),
    'repeating_command_block':('command_block','CommandBlock'),
    'decorated_pot':('decorated_pot','DecoratedPot'),'ender_chest':('ender_chest','EnderChest'),
    'end_gateway':('end_gateway','EndGateway'),'jigsaw':('jigsaw','JigsawBlock'),
    'jukebox':('jukebox','Jukebox'),'lectern':('lectern','Lectern'),
    'piston':('piston','PistonArm'),'sticky_piston':('piston','PistonArm'),
    'sculk_sensor':('sculk_sensor','SculkSensor'),'calibrated_sculk_sensor':('calibrated_sculk_sensor','CalibratedSculkSensor'),
    'structure_block':('structure_block','StructureBlock'),
    'suspicious_sand':('brushable_block','BrushableBlock'),'suspicious_gravel':('brushable_block','BrushableBlock'),
    'trial_spawner':('trial_spawner','TrialSpawner'),'vault':('vault','Vault'),
    'comparator':('comparator','Comparator'),'unpowered_comparator':('comparator','Comparator'),
    'powered_comparator':('comparator','Comparator'),
    'enchanting_table':('enchanting_table','EnchantTable'),
    'conduit':('conduit','Conduit'),
    'brewing_stand':('brewing_stand','BrewingStand'),'crafter':('crafter','Crafter'),
    'beacon':('beacon','Beacon'),'end_portal':('end_portal','EndPortal'),
    'spore_blossom':('spore_blossom','SporeBlossom'),
    'spawner':('mob_spawner','MobSpawner'),'mob_spawner':('mob_spawner','MobSpawner'),
    'sculk_catalyst':('sculk_catalyst','SculkCatalyst'),'sculk_shrieker':('sculk_shrieker','SculkShrieker'),
    'creaking_heart':('creaking_heart','CreakingHeart'),
    **{name:('cauldron','Cauldron') for name in ('cauldron','water_cauldron','lava_cauldron','powder_snow_cauldron')},
}
COOKABLE=frozenset('minecraft:'+name for name in ('potato','beef','chicken','cod','mutton','porkchop','rabbit','salmon','kelp'))
BOOKS=frozenset('minecraft:'+name for name in ('book','writable_book','written_book','enchanted_book'))
BEACON_EFFECTS={'minecraft:speed':1,'minecraft:haste':3,'minecraft:strength':5,'minecraft:jump_boost':8,'minecraft:regeneration':10,'minecraft:resistance':11}
IDENTIFIER=re.compile(r'[a-z0-9_.-]+:[a-z0-9_./-]+\Z')


def handles(name):return name in IDS
def taglist(kind,values):return nbt.Tag(nbt.LIST,nbt.ListValue(kind,values))


def empty_list(f,key):
    value=f.pop(key,nbt.LIST,nbt.ListValue(nbt.COMPOUND,[]))
    if value.values:raise ValueError(f.path+'.'+key+': active entity/movement state requires further migration')


def optional_item(f,key,items,edition):
    value=f.pop(key,nbt.COMPOUND,{})
    if not value:return None
    return items.to_bedrock(value,f.path+'.'+key) if edition=='Java' else items.to_java(value,f.path+'.'+key)


def item_identity(item,edition):return item['Name' if edition=='Bedrock' else 'id'].value
def item_count(item,edition):return item['Count' if edition=='Bedrock' else 'count'].value


def book_pages(item,edition):
    if edition=='Bedrock':return len(item.get('tag',nbt.compound()).value.get('pages',taglist(nbt.COMPOUND,[])).value.values)
    components=item.get('components',nbt.compound()).value
    content=components.get('minecraft:written_book_content',components.get('minecraft:writable_book_content',nbt.compound()))
    return len(content.value.get('pages',taglist(nbt.STRING,[])).value.values)


def campfire(f,out,items,edition):
    if edition=='Java':
        raw=f.pop('Items',nbt.LIST,nbt.ListValue(nbt.COMPOUND,[]))
        for entry in compound_list(raw,'Block NBT.Items'):
            identity=entry.get('id')
            if identity is None or identity.kind!=nbt.STRING or identity.value not in COOKABLE:
                raise ValueError('Block NBT.Items: campfire requires an item with a pinned vanilla recipe')
        inventory=items.inventory(raw,edition,4)
        times=f.pop('CookingTimes',nbt.INT_ARRAY,[0]*4);totals=f.pop('CookingTotalTimes',nbt.INT_ARRAY,[0]*4)
        if len(times)!=4 or len(totals)!=4:raise ValueError('Block NBT: campfire timing arrays must have four entries')
        occupied={}
        for item in inventory.value.values:
            slot=item.pop('Slot').value;occupied[slot]=item
            if item_count(item,'Bedrock')!=1:raise ValueError('Block NBT.Items: campfire requires one item per slot')
            out['Item'+str(slot+1)]=nbt.Tag(nbt.COMPOUND,item)
        for slot in range(4):
            if slot in occupied:
                if totals[slot]!=600 or not 0<=times[slot]<=600:raise ValueError('Block NBT.CookingTimes: custom recipe duration or invalid progress')
            elif times[slot] or totals[slot]:raise ValueError('Block NBT: empty campfire slot has nonzero timing')
            out['ItemTime'+str(slot+1)]=nbt.Tag(nbt.INT,times[slot])
    else:
        inventory=[];times=[];totals=[]
        for slot in range(4):
            item=optional_item(f,'Item'+str(slot+1),items,edition);time=f.pop('ItemTime'+str(slot+1),nbt.INT,0)
            if item:
                if item_identity(item,'Java') not in COOKABLE or item_count(item,'Java')!=1 or not 0<=time<=600:
                    raise ValueError('Block NBT: campfire item/progress has no pinned vanilla recipe')
                item['Slot']=nbt.Tag(nbt.BYTE,slot);inventory.append(item)
            elif time:raise ValueError('Block NBT: empty campfire slot has nonzero timing')
            times.append(time);totals.append(600 if item else 0)
        out.update(Items=taglist(nbt.COMPOUND,inventory),CookingTimes=nbt.Tag(nbt.INT_ARRAY,times),CookingTotalTimes=nbt.Tag(nbt.INT_ARRAY,totals))


def structure(f,out,edition,props):
    modes=('data','save','load','corner');rotations=('NONE','CLOCKWISE_90','CLOCKWISE_180','COUNTERCLOCKWISE_90');mirrors=('NONE','LEFT_RIGHT','FRONT_BACK')
    if edition=='Java':
        f.default_only('author',nbt.STRING,'');f.default_only('showair',nbt.BYTE,0)
        mode=f.pop('mode',nbt.STRING,props['mode'].upper()).lower()
        if mode!=props['mode']:raise ValueError('Block NBT.mode disagrees with structure-block state')
        rotation=f.pop('rotation',nbt.STRING,'NONE');mirror=f.pop('mirror',nbt.STRING,'NONE')
        if rotation not in rotations or mirror not in mirrors:raise ValueError('Block NBT: invalid structure rotation/mirror')
        out.update(data=nbt.Tag(nbt.INT,modes.index(mode)),rotation=nbt.Tag(nbt.BYTE,rotations.index(rotation)),mirror=nbt.Tag(nbt.BYTE,mirrors.index(mirror)),
                   includePlayers=nbt.Tag(nbt.BYTE,0),removeBlocks=nbt.Tag(nbt.BYTE,0),redstoneSaveMode=nbt.Tag(nbt.INT,0))
    else:
        f.default_only('includePlayers',nbt.BYTE,0);f.default_only('removeBlocks',nbt.BYTE,0);f.default_only('redstoneSaveMode',nbt.INT,0)
        f.default_only('animationMode',nbt.BYTE,0);f.default_only('animationSeconds',nbt.FLOAT,0.0)
        mode=f.pop('data',nbt.INT,modes.index(props['structure_block_type']));rotation=f.pop('rotation',nbt.BYTE,0);mirror=f.pop('mirror',nbt.BYTE,0)
        if mode not in range(4) or rotation not in range(4) or mirror not in range(3):raise ValueError('Block NBT: unsupported structure mode/rotation/mirror')
        if modes[mode]!=props['structure_block_type']:raise ValueError('Block NBT.data disagrees with structure-block state')
        out.update(mode=nbt.Tag(nbt.STRING,modes[mode].upper()),rotation=nbt.Tag(nbt.STRING,rotations[rotation]),mirror=nbt.Tag(nbt.STRING,mirrors[mirror]),
                   author=nbt.Tag(nbt.STRING,''),showair=nbt.Tag(nbt.BYTE,0))
    pairs=[('name','structureName',nbt.STRING,''),('metadata','dataField',nbt.STRING,''),('ignoreEntities','ignoreEntities',nbt.BYTE,1),
           ('powered','isPowered',nbt.BYTE,0),('showboundingbox','showBoundingBox',nbt.BYTE,1),('integrity','integrity',nbt.FLOAT,1.0),('seed','seed',nbt.LONG,0)]
    pairs.extend(('pos'+axis,axis.lower()+'StructureOffset',nbt.INT,1 if axis=='Y' else 0) for axis in 'XYZ')
    pairs.extend(('size'+axis,axis.lower()+'StructureSize',nbt.INT,0) for axis in 'XYZ')
    for java,native,kind,default in pairs:
        value=f.pop(java if edition=='Java' else native,kind,default)
        if kind==nbt.BYTE and value not in (0,1):raise ValueError(f.path+': invalid structure boolean')
        if java=='integrity' and (not math.isfinite(value) or not 0<=value<=1):raise ValueError(f.path+'.integrity: outside 0–1')
        if java.startswith('size') and not 0<=value<=48:raise ValueError(f.path+': structure size outside the common 0–48 range')
        out[native if edition=='Java' else java]=nbt.Tag(kind,value)


def translate(translator,block,layers,data,position,neighbour=None,neighbour_entity=None):
    from .payloads import fields,root,custom_name
    source,target=translator.source,translator.target;edition=source.edition
    block=source.validate(block,defaults=edition=='Java');name=block.name.removeprefix('minecraft:');p=dict(block.properties)
    java_id,native_id=IDS[name];piston=name in ('piston','sticky_piston')
    f=fields(data,edition,('minecraft:'+java_id,) if edition=='Java' else (native_id,),position,movable=None if piston else 1)
    base_source=block
    if edition=='Java':
        state=dict(p)
        for key in ('has_book','has_record','extended'):
            if key in state:state[key]='false'
        base_source=source.block(block.name,state)
    base,extra=translator.block(base_source,layers);out={};out_id=native_id if edition=='Java' else 'minecraft:'+java_id
    items=ItemTranslator(translator)
    if name in ('spawner','mob_spawner'):
        from .spawner_payloads import translate as spawner
        spawner(f,out,edition)
    elif name=='sculk_catalyst':
        empty_list(f,'cursors');out['cursors']=taglist(nbt.COMPOUND,[])
    elif name=='creaking_heart':
        if edition=='Java':out['Cooldown']=nbt.Tag(nbt.INT,0)
        else:f.default_only('Cooldown',nbt.INT,0)
    elif name in ('end_portal','spore_blossom'):
        if name=='spore_blossom' and edition=='Bedrock':out_id=None
    elif name in ('cauldron','water_cauldron','lava_cauldron','powder_snow_cauldron'):
        if edition=='Java':out.update(Items=taglist(nbt.COMPOUND,[]),PotionId=nbt.Tag(nbt.SHORT,-1),PotionType=nbt.Tag(nbt.SHORT,-1))
        else:
            empty_list(f,'Items');f.default_only('PotionId',nbt.SHORT,-1);f.default_only('PotionType',nbt.SHORT,-1);out_id=None
    elif name=='beacon':
        custom_name(f,out,edition)
        if edition=='Java':
            f.default_only('Lock',nbt.STRING,'')
            if 'Levels' in f.data:
                levels=0
                for depth in range(1,5):
                    supported=True
                    for dx in range(-depth,depth+1):
                        for dz in range(-depth,depth+1):
                            b=neighbour((position[0]+dx,position[1]-depth,position[2]+dz)) if neighbour else None
                            if b is None or b.name not in ('minecraft:iron_block','minecraft:gold_block','minecraft:diamond_block','minecraft:emerald_block','minecraft:netherite_block'):supported=False
                    if not supported:break
                    levels=depth
                if f.pop('Levels',nbt.INT)!=levels:raise ValueError('Block NBT.Levels: beacon pyramid context is missing or inconsistent')
            for key in ('primary','secondary'):
                effect=f.pop(key+'_effect',nbt.STRING,'')
                if effect and effect not in BEACON_EFFECTS:raise ValueError('Block NBT.'+key+'_effect: effect has no verified beacon equivalent')
                out[key]=nbt.Tag(nbt.INT,BEACON_EFFECTS.get(effect,0))
        else:
            for key in ('primary','secondary'):
                effect=f.pop(key,nbt.INT,0)
                if effect:
                    inverse={v:k for k,v in BEACON_EFFECTS.items()}
                    if effect not in inverse:raise ValueError('Block NBT.'+key+': native effect has no verified beacon equivalent')
                    out[key+'_effect']=nbt.Tag(nbt.STRING,inverse[effect])
    elif name in ('brewing_stand','crafter'):
        brewing=name=='brewing_stand';capacity=5 if brewing else 9
        inventory=items.inventory(f.pop('Items',nbt.LIST,nbt.ListValue(nbt.COMPOUND,[])),edition,capacity)
        if brewing:
            # Native Bedrock slot 0 is the ingredient; 1–3 hold bottles.
            mapping=(1,2,3,0,4) if edition=='Java' else (3,0,1,2,4)
            source_slots={entry['Slot'].value for entry in inventory.value.values}
            for i,letter in enumerate('abc'):
                expected=str((i if edition=='Java' else i+1) in source_slots).lower()
                if p['has_bottle_'+str(i) if edition=='Java' else 'brewing_stand_slot_'+letter+'_bit']!=expected:raise ValueError('Block NBT.Items disagrees with brewing-stand bottle states')
            for entry in inventory.value.values:entry['Slot']=nbt.Tag(nbt.BYTE,mapping[entry['Slot'].value])
            time=f.pop('BrewTime' if edition=='Java' else 'CookTime',nbt.SHORT,0)
            fuel=f.pop('Fuel' if edition=='Java' else 'FuelAmount',nbt.BYTE if edition=='Java' else nbt.SHORT,0)
            if not 0<=time<=400 or not 0<=fuel<=20:raise ValueError('Block NBT: brewing progress/fuel outside vanilla range')
            out['CookTime' if edition=='Java' else 'BrewTime']=nbt.Tag(nbt.SHORT,time)
            out['FuelAmount' if edition=='Java' else 'Fuel']=nbt.Tag(nbt.SHORT if edition=='Java' else nbt.BYTE,fuel)
            if edition=='Java':out['FuelTotal']=nbt.Tag(nbt.SHORT,20 if fuel else 0)
            elif f.pop('FuelTotal',nbt.SHORT,20 if fuel else 0) not in ((20,) if fuel else (0,20)):raise ValueError('Block NBT.FuelTotal: custom fuel duration')
        else:
            if edition=='Java':
                disabled=f.pop('disabled_slots',nbt.INT_ARRAY,[])
                if len(disabled)!=len(set(disabled)) or any(i not in range(9) for i in disabled):raise ValueError('Block NBT.disabled_slots: invalid or duplicate slot')
                bits=sum(1<<i for i in disabled);f.default_only('crafting_ticks_remaining',nbt.INT,0)
                if f.pop('triggered',nbt.INT,int(p['triggered']=='true'))!=int(p['triggered']=='true'):raise ValueError('Block NBT.triggered disagrees with crafter state')
                out['disabled_slots']=nbt.Tag(nbt.SHORT,bits)
            else:
                bits=f.pop('disabled_slots',nbt.SHORT,0)
                if not 0<=bits<512:raise ValueError('Block NBT.disabled_slots: invalid slot mask')
                disabled=[i for i in range(9) if bits&(1<<i)];out['disabled_slots']=nbt.Tag(nbt.INT_ARRAY,disabled)
                out.update(crafting_ticks_remaining=nbt.Tag(nbt.INT,0),triggered=nbt.Tag(nbt.INT,int(p['triggered_bit']=='true')))
            if any(entry['Slot'].value in disabled for entry in inventory.value.values):raise ValueError('Block NBT.Items occupies a disabled crafter slot')
        out['Items']=inventory;custom_name(f,out,edition)
        if edition=='Java':f.default_only('Lock',nbt.STRING,'')
        else:f.default_only('Findable',nbt.BYTE,0)
    elif name in ('ender_chest','enchanting_table'):
        custom_name(f,out,edition)
        if edition=='Bedrock':
            f.default_only('Findable',nbt.BYTE,0)
            if name=='enchanting_table':f.default_only('rott',nbt.FLOAT,0.0)
        elif name=='ender_chest':out['Findable']=nbt.Tag(nbt.BYTE,0)
    elif 'comparator' in name:
        value=f.pop('OutputSignal',nbt.INT,0)
        if not 0<=value<=15:raise ValueError('Block NBT.OutputSignal: outside 0–15')
        out['OutputSignal']=nbt.Tag(nbt.INT,value)
    elif name=='conduit':
        if edition=='Java':f.default_only('Target',nbt.INT_ARRAY,[]);out.update(Active=nbt.Tag(nbt.BYTE,0),Target=nbt.Tag(nbt.LONG,-1))
        else:f.default_only('Active',nbt.BYTE,0);f.default_only('Target',nbt.LONG,-1)
    elif name in ('bee_nest','beehive'):
        empty_list(f,'bees' if edition=='Java' else 'Occupants')
        if edition=='Java':out['ShouldSpawnBees']=nbt.Tag(nbt.BYTE,0);out['Occupants']=taglist(nbt.COMPOUND,[])
        else:f.default_only('ShouldSpawnBees',nbt.BYTE,0);out['bees']=taglist(nbt.COMPOUND,[])
    elif name=='bell':
        if edition=='Java':out.update(Direction=nbt.Tag(nbt.INT,0),Ringing=nbt.Tag(nbt.BYTE,0),Ticks=nbt.Tag(nbt.INT,0))
        else:
            f.default_only('Ringing',nbt.BYTE,0)
            for key in ('Direction','Ticks'):
                value=f.data.pop(key,nbt.Tag(nbt.INT,0))
                if value.kind not in (nbt.BYTE,nbt.INT) or value.value:raise ValueError('Block NBT.'+key+': ringing state has no Java saved equivalent')
    elif name in ('campfire','soul_campfire'):campfire(f,out,items,edition)
    elif name=='chiseled_bookshelf':
        inventory=items.inventory(f.pop('Items',nbt.LIST,nbt.ListValue(nbt.COMPOUND,[])),edition,6)
        occupied={entry['Slot'].value for entry in inventory.value.values}
        for item in inventory.value.values:
            if item_identity(item,target.edition) not in BOOKS or item_count(item,target.edition)!=1:raise ValueError('Block NBT.Items: a bookshelf slot requires a single book')
        expected=sum(1<<slot for slot in occupied)
        actual=sum(1<<i for i in range(6) if p[f'slot_{i}_occupied']=='true') if edition=='Java' else int(p['books_stored'])
        if expected!=actual:raise ValueError('Block NBT.Items disagrees with bookshelf occupancy states')
        last=f.pop('last_interacted_slot' if edition=='Java' else 'LastInteractedSlot',nbt.INT,-1 if edition=='Java' else 0)
        if edition=='Bedrock':last-=1
        if not -1<=last<6:raise ValueError('Block NBT: invalid last interacted bookshelf slot')
        out['Items']=inventory;out['LastInteractedSlot' if edition=='Java' else 'last_interacted_slot']=nbt.Tag(nbt.INT,last+1 if edition=='Java' else last)
    elif name in ('jukebox','lectern'):
        lectern=name=='lectern';java_key='Book' if lectern else 'RecordItem';native_key='book' if lectern else 'RecordItem'
        item=optional_item(f,java_key if edition=='Java' else native_key,items,edition);present=item is not None
        if item:
            identity=item_identity(item,target.edition)
            if item_count(item,target.edition)!=1 or (identity not in ('minecraft:written_book','minecraft:writable_book') if lectern else not identity.startswith('minecraft:music_disc_')):
                raise ValueError('Block NBT.'+java_key+': unexpected item kind/count')
            out[native_key if edition=='Java' else java_key]=nbt.Tag(nbt.COMPOUND,item)
        property_name='has_book' if lectern else 'has_record'
        if edition=='Java':
            if (p[property_name]=='true')!=present:raise ValueError('Block NBT.'+java_key+' disagrees with '+property_name)
            if not lectern:
                if 'ticks_since_song_started' in f.data:raise ValueError('Block NBT.ticks_since_song_started: active song timing has no Bedrock saved equivalent')
        else:
            state=dict(base.properties);state[property_name]=str(present).lower();base=target.block(base.name,state)
        if lectern:
            count=book_pages(item,target.edition) if item else 0;page=f.pop('Page' if edition=='Java' else 'page',nbt.INT,0)
            if not 0<=page<max(1,count):raise ValueError('Block NBT: lectern page is outside the book')
            if edition=='Bedrock':
                if f.flag('hasBook',present)!=present or f.pop('totalPages',nbt.INT,count)!=count:raise ValueError('Block NBT: lectern book metadata disagrees with contents')
            else:out.update(hasBook=nbt.Tag(nbt.BYTE,int(present)),totalPages=nbt.Tag(nbt.INT,count))
            out['page' if edition=='Java' else 'Page']=nbt.Tag(nbt.INT,page)
    elif name=='decorated_pot':
        sherds=string_list(f.pop('sherds',nbt.LIST,nbt.ListValue(nbt.STRING,['minecraft:brick']*4)),'Block NBT.sherds')
        if len(sherds)!=4 or any(v!='minecraft:brick' and (v not in JAVA_ITEMS or not v.endswith('_pottery_sherd')) for v in sherds):raise ValueError('Block NBT.sherds: expected four pottery sherd/brick identities')
        out['sherds']=taglist(nbt.STRING,list(sherds));item=optional_item(f,'item',items,edition)
        if item:out['item']=nbt.Tag(nbt.COMPOUND,item)
        if edition=='Bedrock':f.default_only('animation',nbt.BYTE,0)
    elif name=='end_gateway':
        age=f.data.pop('Age',nbt.Tag(nbt.LONG if edition=='Java' else nbt.INT,0))
        if age.kind not in ((nbt.LONG,) if edition=='Java' else (nbt.INT,nbt.LONG)) or not 0<=age.value<=2147483647:raise ValueError('Block NBT.Age: outside the shared gateway age range')
        out['Age']=nbt.Tag(nbt.INT if edition=='Java' else nbt.LONG,age.value)
        if edition=='Java':
            f.default_only('ExactTeleport',nbt.BYTE,0)
            if 'exit_portal' in f.data:
                xyz=f.pop('exit_portal',nbt.INT_ARRAY)
                if len(xyz)!=3:raise ValueError('Block NBT.exit_portal: expected three integer coordinates')
                out['ExitPortal']=taglist(nbt.INT,list(xyz))
        elif 'ExitPortal' in f.data:
            portal=f.pop('ExitPortal',nbt.LIST)
            if portal.kind!=nbt.INT or len(portal.values)!=3:raise ValueError('Block NBT.ExitPortal: expected three integer coordinates')
            out['exit_portal']=nbt.Tag(nbt.INT_ARRAY,list(portal.values))
    elif name=='jigsaw':
        for key in ('name','target','pool'):
            native='target_pool' if key=='pool' else key;value=f.pop(key if edition=='Java' else native,nbt.STRING,'minecraft:empty')
            if not IDENTIFIER.fullmatch(value):raise ValueError('Block NBT.'+key+': invalid resource identifier')
            out[native if edition=='Java' else key]=nbt.Tag(nbt.STRING,value)
        joint=f.pop('joint',nbt.STRING,'rollable')
        if joint not in ('rollable','aligned'):raise ValueError('Block NBT.joint: invalid joint')
        final=f.pop('final_state',nbt.STRING,'minecraft:air')
        # Bedrock jigsaw final_state is an identifier, without a Java block-state
        # parser. Explicit non-default properties/embedded SNBT cannot fit it.
        if not IDENTIFIER.fullmatch(final):raise ValueError('Block NBT.final_state: native jigsaw requires a block identifier')
        converted,fluid=translator.block(source.initial(final))
        if fluid or converted!=target.initial(converted.name):raise ValueError('Block NBT.final_state: target requires properties or a fluid layer')
        out.update(joint=nbt.Tag(nbt.STRING,joint),final_state=nbt.Tag(nbt.STRING,converted.name))
        for key in ('selection_priority','placement_priority'):f.default_only(key,nbt.INT,0)
    elif name=='structure_block':structure(f,out,edition,p)
    elif name.endswith('command_block'):
        command=f.pop('Command',nbt.STRING,'')
        if command and (not command.startswith('say ') or '@' in command):raise ValueError('Block NBT.Command: cross-edition command grammar supports literal say commands only')
        out['Command']=nbt.Tag(nbt.STRING,command);custom_name(f,out,edition)
        for key in ('auto','conditionMet','powered','TrackOutput'):
            out[key]=nbt.Tag(nbt.BYTE,int(f.flag(key,key=='TrackOutput')))
        out['SuccessCount']=nbt.Tag(nbt.INT,f.pop('SuccessCount',nbt.INT,0))
        if edition=='Java':
            f.default_only('UpdateLastExecution',nbt.BYTE,1);f.default_only('LastExecution',nbt.LONG,0)
            if f.pop('LastOutput',nbt.STRING,'') not in ('','""'):raise ValueError('Block NBT.LastOutput: command output components require verified localization conversion')
            out.update(ExecuteOnFirstTick=nbt.Tag(nbt.BYTE,0),LastExecution=nbt.Tag(nbt.LONG,0),LastOutput=nbt.Tag(nbt.STRING,''),
                LastOutputParams=taglist(nbt.STRING,[]),LPCommandMode=nbt.Tag(nbt.INT,0),LPCondionalMode=nbt.Tag(nbt.BYTE,0),
                LPRedstoneMode=nbt.Tag(nbt.BYTE,0),TickDelay=nbt.Tag(nbt.INT,0),Version=nbt.Tag(nbt.INT,42),conditionalMode=nbt.Tag(nbt.BYTE,int(p['conditional']=='true')))
        else:
            for key,kind,default in (('ExecuteOnFirstTick',nbt.BYTE,0),('LastExecution',nbt.LONG,0),('LastOutput',nbt.STRING,''),
                ('LPCommandMode',nbt.INT,0),('LPCondionalMode',nbt.BYTE,0),('LPRedstoneMode',nbt.BYTE,0),('TickDelay',nbt.INT,0),('Version',nbt.INT,42)):
                f.default_only(key,kind,default)
            empty_list(f,'LastOutputParams')
            if f.flag('conditionalMode',p['conditional_bit']=='true')!=(p['conditional_bit']=='true'):raise ValueError('Block NBT.conditionalMode disagrees with block state')
    elif piston:
        if edition=='Java':
            extended=p['extended']=='true';out_id='PistonArm'
            out.update(AttachedBlocks=taglist(nbt.INT,[]),BreakBlocks=taglist(nbt.INT,[]),LastProgress=nbt.Tag(nbt.FLOAT,float(extended)),
                       Progress=nbt.Tag(nbt.FLOAT,float(extended)),State=nbt.Tag(nbt.BYTE,2 if extended else 0),NewState=nbt.Tag(nbt.BYTE,2 if extended else 0),
                       Sticky=nbt.Tag(nbt.BYTE,int(name=='sticky_piston')),isMovable=nbt.Tag(nbt.BYTE,int(not extended)))
        else:
            state=f.pop('State',nbt.BYTE,0);next_state=f.pop('NewState',nbt.BYTE,state)
            if state not in (0,2) or state!=next_state:raise ValueError('Block NBT.State: active piston needs movement assembly conversion')
            extended=state==2;progress=float(extended)
            f.default_only('Progress',nbt.FLOAT,progress);f.default_only('LastProgress',nbt.FLOAT,progress)
            empty_list(f,'AttachedBlocks');empty_list(f,'BreakBlocks')
            if f.flag('Sticky',name=='sticky_piston')!=(name=='sticky_piston'):raise ValueError('Block NBT.Sticky disagrees with piston identity')
            f.default_only('isMovable',nbt.BYTE,int(not extended));props=dict(base.properties);props['extended']=str(extended).lower();base=target.block(base.name,props);out_id=None
    elif name in ('sculk_sensor','calibrated_sculk_sensor','sculk_shrieker'):
        key='warning_level' if name=='sculk_shrieker' else 'last_vibration_frequency'
        if edition=='Java':
            f.default_only(key,nbt.INT,0)
            listener=Fields(f.pop('listener',nbt.COMPOUND,{}),'Block NBT.listener')
            selector=Fields(listener.pop('selector',nbt.COMPOUND,{}),listener.path+'.selector');selector.default_only('tick',nbt.LONG,-1);selector.finish()
            listener.default_only('event_delay',nbt.INT,0);listener.finish()
            out['VibrationListener']=nbt.compound(selector=nbt.compound())
        else:
            listener=Fields(f.pop('VibrationListener',nbt.COMPOUND,{}),'Block NBT.VibrationListener');listener.default_only('selector',nbt.COMPOUND,{});listener.default_only('ticks',nbt.INT,0);listener.finish()
            out['listener']=nbt.compound(selector=nbt.compound(tick=nbt.Tag(nbt.LONG,-1)),event_delay=nbt.Tag(nbt.INT,0));out[key]=nbt.Tag(nbt.INT,0)
    elif name in ('suspicious_sand','suspicious_gravel'):
        item=optional_item(f,'item',items,edition)
        if item:out['item']=nbt.Tag(nbt.COMPOUND,item)
        if edition=='Bedrock':
            f.default_only('Findable',nbt.BYTE,0);f.default_only('brush_count',nbt.INT,0);f.default_only('brush_direction',nbt.BYTE,6);f.default_only('type',nbt.STRING,block.name)
        else:out.update(Findable=nbt.Tag(nbt.BYTE,0),brush_count=nbt.Tag(nbt.INT,0),brush_direction=nbt.Tag(nbt.BYTE,6),type=nbt.Tag(nbt.STRING,block.name))
    elif name not in ('trial_spawner','vault'):raise ValueError('Block NBT: missing advanced handler')
    f.finish()
    return base,extra,root(out_id,position,target.edition,out) if out_id else None
