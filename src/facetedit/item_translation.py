"""Typed Java 1.21.4 components ↔ Bedrock 1.21.50 inventory records.

Only explicitly represented fields are consumed. Unknown item data is a named
preflight error; no inventory entry is silently discarded or replaced.
"""
import gzip
from importlib.resources import files
import json

from . import nbt, text_components,book_items,armor_items,potion_items
from .blocks import Block
from .formats import bedrock_block,bedrock_entry
from .native_rules import ALIASES as BLOCK_ALIASES
from .payload_fields import Fields,compound_list,string_list
from .payload_formats import COLORS,patterns_to_bedrock,patterns_to_java

DATA=json.loads(gzip.decompress(files('facetedit').joinpath('data','registries','items-1.21.json.gz').read_bytes()))
JAVA_ITEMS=DATA['java']
# Signed books are a native inventory item omitted by the public item report.
BEDROCK_INTERNAL_ITEMS=frozenset(('minecraft:written_book',))
BEDROCK_ITEMS=frozenset(DATA['bedrock'])|BEDROCK_INTERNAL_ITEMS
ALIASES={**BLOCK_ALIASES,'dirt_path':'grass_path','magma_block':'magma','cobweb':'web','snow_block':'snow','snow':'snow_layer',
         'cobblestone_stairs':'stone_stairs','stone_stairs':'normal_stone_stairs','end_stone_brick_stairs':'end_brick_stairs',
         'prismarine_brick_stairs':'prismarine_bricks_stairs','stone_slab':'normal_stone_slab','oak_button':'wooden_button',
         'oak_door':'wooden_door','oak_trapdoor':'trapdoor','oak_fence_gate':'fence_gate','oak_pressure_plate':'wooden_pressure_plate',
         'powered_rail':'golden_rail','note_block':'noteblock','shulker_box':'undyed_shulker_box','nether_brick':'netherbrick',
         'small_dripleaf':'small_dripleaf_block','item_frame':'frame','glow_item_frame':'glow_frame','map':'empty_map',
         'light_gray_glazed_terracotta':'silver_glazed_terracotta','zombified_piglin_spawn_egg':'zombie_pigman_spawn_egg'}
REVERSE={v:k for k,v in ALIASES.items()}
UNMAPPED_VARIANTS={'filled_map'}
# Native Bedrock enchantment identifiers. Names are checked against the pinned
# primary metadata; these explicit numeric format identifiers are not code/data
# imported from Amulet. Java-only sweeping_edge has no native mapping.
ENCHANTMENTS=('protection','fire_protection','feather_falling','blast_protection','projectile_protection','thorns',
              'respiration','depth_strider','aqua_affinity','sharpness','smite','bane_of_arthropods','knockback','fire_aspect',
              'looting','efficiency','silk_touch','unbreaking','fortune','power','punch','flame','infinity','luck_of_the_sea',
              'lure','frost_walker','mending','binding_curse','vanishing_curse','impaling','riptide','loyalty','channeling',
              'multishot','piercing','quick_charge','soul_speed','swift_sneak','wind_burst','density','breach')


class ItemTranslator:
    def __init__(self,translator):
        self.translator=translator;self.visited=0

    def _budget(self,depth):
        self.visited+=1
        if depth>8 or self.visited>4096:raise ValueError('Inventory nesting/item budget exceeded')

    def inventory(self,value,edition,capacity,path='Items',depth=0):
        result=[];seen=set()
        for index,item in enumerate(compound_list(value,path)):
            field=Fields(item,f'{path}[{index}]');slot=field.pop('Slot',nbt.BYTE)
            if not 0<=slot<capacity or slot in seen:raise ValueError(field.path+'.Slot: duplicate or outside the container')
            seen.add(slot)
            translated=self.to_bedrock(field.data,field.path,depth) if edition=='Java' else self.to_java(field.data,field.path,depth)
            translated['Slot']=nbt.Tag(nbt.BYTE,slot);result.append(translated)
        return nbt.Tag(nbt.LIST,nbt.ListValue(nbt.COMPOUND,result))

    def to_bedrock(self,data,path='item',depth=0):
        self._budget(depth);f=Fields(data,path)
        name=f.pop('id',nbt.STRING)
        if name not in JAVA_ITEMS:raise ValueError(path+'.id: unknown Java item '+name)
        count=f.pop('count',nbt.INT,1)
        if not 1<=count<=99:raise ValueError(path+'.count: the Java 1.21.4 item codec requires a count from 1 to 99')
        components=Fields(f.pop('components',nbt.COMPOUND,{}),path+'.components');f.finish()
        base=name.removeprefix('minecraft:');aux=0
        if base in UNMAPPED_VARIANTS:raise ValueError(path+': item variant/world-reference translation is not implemented for '+name)
        if base in potion_items.KINDS:target,aux=potion_items.to_bedrock(base,components)
        elif base.endswith('_bed') and base[:-4] in COLORS:target='bed';aux=COLORS.index(base[:-4])
        elif base.endswith('_banner') and base[:-7] in COLORS:target='banner';aux=15-COLORS.index(base[:-7])
        else:target=ALIASES.get(base,base)
        target='minecraft:'+target
        if target not in BEDROCK_ITEMS:raise ValueError(path+'.id: no Bedrock item identity for '+name)
        result={'Name':nbt.Tag(nbt.STRING,target),'Count':nbt.Tag(nbt.BYTE,count if count<128 else count-256),'Damage':nbt.Tag(nbt.SHORT,aux)}
        tag={};display={}
        for source,destination in (('minecraft:damage','Damage'),('minecraft:repair_cost','RepairCost')):
            if source in components.data:
                value=components.pop(source,nbt.INT)
                if value<0:raise ValueError(components.path+'.'+source+': negative value')
                if source=='minecraft:damage' and not JAVA_ITEMS[name]['durability']:raise ValueError(path+': damage on a non-durable item is not representable')
                tag[destination]=nbt.Tag(nbt.INT,value)
        if 'minecraft:custom_name' in components.data:
            display['Name']=nbt.Tag(nbt.STRING,text_components.to_bedrock(components.pop('minecraft:custom_name',nbt.STRING)))
        if 'minecraft:lore' in components.data:
            lines=string_list(components.pop('minecraft:lore',nbt.LIST),components.path+'.minecraft:lore')
            if len(lines)>256:raise ValueError(path+': too many lore lines')
            display['Lore']=nbt.Tag(nbt.LIST,nbt.ListValue(nbt.STRING,[text_components.to_bedrock(s) for s in lines]))
        if display:tag['display']=nbt.Tag(nbt.COMPOUND,display)
        if 'minecraft:banner_patterns' in components.data:
            if not base.endswith('_banner'):raise ValueError(path+': banner patterns require a banner item')
            tag['Patterns']=patterns_to_bedrock(components.pop('minecraft:banner_patterns',nbt.LIST),components.path+'.minecraft:banner_patterns')
        enchant_keys=[key for key in ('minecraft:enchantments','minecraft:stored_enchantments') if key in components.data]
        if len(enchant_keys)>1:raise ValueError(path+': Bedrock cannot preserve both stored and applied enchantments')
        if enchant_keys:
            key=enchant_keys[0]
            if (key=='minecraft:stored_enchantments')!=(base=='enchanted_book'):raise ValueError(path+': enchantment component does not match the native item kind')
            enchant=Fields(components.pop(key,nbt.COMPOUND),components.path+'.'+key)
            levels=enchant.pop('levels',nbt.COMPOUND,{});enchant.default_only('show_in_tooltip',nbt.BYTE,1);enchant.finish()
            entries=[]
            for identifier,level in levels.items():
                if not identifier.startswith('minecraft:') or identifier[10:] not in ENCHANTMENTS:raise ValueError(path+': no Bedrock enchantment for '+identifier)
                if level.kind!=nbt.INT or not 1<=level.value<=255:raise ValueError(path+': the Java enchantment codec requires a level from 1 to 255')
                entries.append({'id':nbt.Tag(nbt.SHORT,ENCHANTMENTS.index(identifier[10:])),'lvl':nbt.Tag(nbt.SHORT,level.value)})
            tag['ench']=nbt.Tag(nbt.LIST,nbt.ListValue(nbt.COMPOUND,entries))
        if 'minecraft:unbreakable' in components.data:
            flag=Fields(components.pop('minecraft:unbreakable',nbt.COMPOUND),components.path+'.minecraft:unbreakable')
            flag.default_only('show_in_tooltip',nbt.BYTE,1);flag.finish();tag['Unbreakable']=nbt.Tag(nbt.BYTE,1)
        if 'minecraft:block_state' in components.data:
            states=components.pop('minecraft:block_state',nbt.COMPOUND)
            if any(v.kind!=nbt.STRING for v in states.values()):raise ValueError(path+': block-state component must contain strings')
            native=self.translator.java.block(name,{k:v.value for k,v in states.items()},defaults=True)
            block,layers=self.translator.block(native)
            if layers:raise ValueError(path+': an item cannot retain a secondary fluid layer')
            result['Block']=bedrock_entry(block,self.translator.bedrock.palette_version)
        if 'minecraft:container' in components.data:
            if 'shulker_box' not in base:raise ValueError(path+': only shulker container-item payloads are supported')
            entries=compound_list(components.pop('minecraft:container',nbt.LIST),components.path+'.minecraft:container')
            items=[];seen=set()
            for index,entry in enumerate(entries):
                child=Fields(entry,f'{components.path}.minecraft:container[{index}]');slot=child.pop('slot',nbt.INT)
                if not 0<=slot<27 or slot in seen:raise ValueError(child.path+': invalid or duplicate slot')
                seen.add(slot);item=self.to_bedrock(child.pop('item',nbt.COMPOUND),child.path+'.item',depth+1);child.finish()
                item['Slot']=nbt.Tag(nbt.BYTE,slot);items.append(item)
            tag['Items']=nbt.Tag(nbt.LIST,nbt.ListValue(nbt.COMPOUND,items))
        book_items.to_bedrock(components,tag,base)
        armor_items.to_bedrock(components,tag,base)
        components.finish()
        if tag:result['tag']=nbt.Tag(nbt.COMPOUND,tag)
        return result

    def to_java(self,data,path='item',depth=0):
        self._budget(depth);f=Fields(data,path)
        name=f.pop('Name',nbt.STRING)
        if name not in BEDROCK_ITEMS:raise ValueError(path+'.Name: unknown Bedrock item '+name)
        count=f.pop('Count',nbt.BYTE)&255
        if not 1<=count<=99:raise ValueError(path+'.Count: the Java 1.21.4 item codec requires a count from 1 to 99')
        aux=f.pop('Damage',nbt.SHORT,0);base=name.removeprefix('minecraft:')
        if base in UNMAPPED_VARIANTS:raise ValueError(path+': item variant/world-reference translation is not implemented for '+name)
        potion=None
        if base in potion_items.KINDS or base=='arrow' and aux:
            target,potion=potion_items.to_java(base,aux,path);aux=0
        elif base=='bed':
            if not 0<=aux<16:raise ValueError(path+': invalid bed item color')
            target=COLORS[aux]+'_bed';aux=0
        elif base=='banner':
            if not 0<=aux<16:raise ValueError(path+': invalid banner item color')
            target=COLORS[15-aux]+'_banner';aux=0
        else:target=REVERSE.get(base,base)
        target='minecraft:'+target
        if target not in JAVA_ITEMS:raise ValueError(path+': no Java item identity for '+name)
        if aux:raise ValueError(path+'.Damage: legacy item variant has no explicit conversion rule')
        f.default_only('WasPickedUp',nbt.BYTE,0)
        tag=Fields(f.pop('tag',nbt.COMPOUND,{}),path+'.tag');components={}
        if potion is not None:
            components['minecraft:potion_contents']=potion
            tag.default_only('Potion',nbt.STRING,potion.value['potion'].value)
        for source,destination in (('Damage','minecraft:damage'),('RepairCost','minecraft:repair_cost')):
            if source in tag.data:
                value=tag.pop(source,nbt.INT)
                if value<0 or source=='Damage' and not JAVA_ITEMS[target]['durability']:raise ValueError(tag.path+'.'+source+': invalid durability/repair data')
                components[destination]=nbt.Tag(nbt.INT,value)
        if 'display' in tag.data:
            display=Fields(tag.pop('display',nbt.COMPOUND),tag.path+'.display')
            if 'Name' in display.data:components['minecraft:custom_name']=nbt.Tag(nbt.STRING,text_components.from_bedrock(display.pop('Name',nbt.STRING)))
            if 'Lore' in display.data:
                lines=string_list(display.pop('Lore',nbt.LIST),display.path+'.Lore')
                if len(lines)>256:raise ValueError(path+': too many lore lines')
                components['minecraft:lore']=nbt.Tag(nbt.LIST,nbt.ListValue(nbt.STRING,[text_components.from_bedrock(s) for s in lines]))
            display.finish()
        if 'Patterns' in tag.data:
            if not target.endswith('_banner'):raise ValueError(path+': native banner patterns require a banner item')
            components['minecraft:banner_patterns']=patterns_to_java(tag.pop('Patterns',nbt.LIST),tag.path+'.Patterns')
        if 'ench' in tag.data:
            levels={}
            for index,entry in enumerate(compound_list(tag.pop('ench',nbt.LIST),tag.path+'.ench')):
                field=Fields(entry,f'{tag.path}.ench[{index}]');identifier=field.pop('id',nbt.SHORT);level=field.pop('lvl',nbt.SHORT);field.finish()
                if not 0<=identifier<len(ENCHANTMENTS) or not 1<=level<=255:raise ValueError(path+': native enchantment ID or level is outside the supported Java range 1–255')
                key='minecraft:'+ENCHANTMENTS[identifier]
                if key in levels:raise ValueError(path+': duplicate native enchantment')
                levels[key]=nbt.Tag(nbt.INT,level)
            key='minecraft:stored_enchantments' if target=='minecraft:enchanted_book' else 'minecraft:enchantments'
            components[key]=nbt.compound(levels=nbt.Tag(nbt.COMPOUND,levels))
        if 'Unbreakable' in tag.data and tag.flag('Unbreakable'):
            components['minecraft:unbreakable']=nbt.compound()
        if 'Block' in f.data:
            descriptor=Fields(f.pop('Block',nbt.COMPOUND),path+'.Block')
            block_name=descriptor.pop('name',nbt.STRING);states=descriptor.pop('states',nbt.COMPOUND)
            descriptor.pop('version',nbt.INT);descriptor.finish()
            native=bedrock_block(nbt.compound(name=nbt.Tag(nbt.STRING,block_name),states=nbt.Tag(nbt.COMPOUND,states)))
            block,_=self.translator.block(native)
            if block.name!=target:raise ValueError(path+': item identity disagrees with its native block descriptor')
            defaults=dict(self.translator.java.initial(target).properties)
            changed={k:nbt.Tag(nbt.STRING,v) for k,v in block.properties if defaults.get(k)!=v}
            if changed:components['minecraft:block_state']=nbt.Tag(nbt.COMPOUND,changed)
        if 'Items' in tag.data:
            if 'shulker_box' not in target:raise ValueError(path+': only shulker container-item payloads are supported')
            converted=self.inventory(tag.pop('Items',nbt.LIST),'Bedrock',27,tag.path+'.Items',depth+1)
            entries=[]
            for item in converted.value.values:
                slot=item.pop('Slot').value
                entries.append({'slot':nbt.Tag(nbt.INT,slot),'item':nbt.Tag(nbt.COMPOUND,item)})
            components['minecraft:container']=nbt.Tag(nbt.LIST,nbt.ListValue(nbt.COMPOUND,entries))
        book_items.to_java(tag,components,target.removeprefix('minecraft:'))
        armor_items.to_java(tag,components,target.removeprefix('minecraft:'))
        tag.finish();f.finish()
        result={'id':nbt.Tag(nbt.STRING,target),'count':nbt.Tag(nbt.INT,count)}
        if components:result['components']=nbt.Tag(nbt.COMPOUND,components)
        return result
