"""Synthetic typed content for native conversion and desktop integration tests."""
from facetedit import nbt
from facetedit.model import Selection
from facetedit.payloads import root
from facetedit.registry import profile
from tests.test_payload_translation import item


def gallery(document):
    java=profile('Java 1.21.4');positions={}
    def put(label,position,name,identifier=None,payload=None,**props):
        positions[label]=position
        document.selection=Selection(position,position);document.fill(java.block('minecraft:'+name,props,defaults=True))
        if identifier:document.set_entity(position,nbt.loads(root('minecraft:'+identifier,position,'Java',payload or {}))[1])
    items=nbt.Tag(nbt.LIST,nbt.ListValue(nbt.COMPOUND,[{**item('diamond_sword',**{
        'minecraft:damage':nbt.Tag(nbt.INT,47),'minecraft:custom_name':nbt.Tag(nbt.STRING,'{"text":"Aurora","color":"aqua"}'),
        'minecraft:enchantments':nbt.compound(levels=nbt.compound(**{'minecraft:sharpness':nbt.Tag(nbt.INT,5)}))}),'Slot':nbt.Tag(nbt.BYTE,26)}]))
    put('chest',(2,16,2),'chest','chest',{'Items':items})
    messages=nbt.Tag(nbt.LIST,nbt.ListValue(nbt.STRING,['"Welcome 世界"','{"text":"FacetEdit","bold":true}','""','"Both editions"']))
    put('sign',(4,16,2),'cherry_wall_sign','sign',{'front_text':nbt.compound(messages=messages,color=nbt.Tag(nbt.STRING,'cyan'),has_glowing_text=nbt.Tag(nbt.BYTE,1)),
        'back_text':nbt.compound(messages=messages),'is_waxed':nbt.Tag(nbt.BYTE,1)},facing='south')
    put('bed',(6,16,2),'cyan_bed','bed',facing='west',part='head')
    put('banner',(8,16,2),'red_banner','banner',{'patterns':nbt.Tag(nbt.LIST,nbt.ListValue(nbt.COMPOUND,[{
        'pattern':nbt.Tag(nbt.STRING,'minecraft:stripe_bottom'),'color':nbt.Tag(nbt.STRING,'white')}]))},rotation='5')
    put('shulker',(10,16,2),'purple_shulker_box','shulker_box',{'Items':items},facing='east')
    put('pot',(12,16,2),'potted_mangrove_propagule')
    put('note',(14,16,2),'note_block',note='19',instrument='basedrum')
    put('left',(15,20,4),'chest','chest',{'Items':items},facing='north',type='left')
    put('right',(16,20,4),'chest','chest',{'Items':nbt.Tag(nbt.LIST,nbt.ListValue(nbt.COMPOUND,[{**item('diamond',23),'Slot':nbt.Tag(nbt.BYTE,4)}]))},facing='north',type='right')
    put('fence',(4,18,4),'oak_fence',east='true',waterlogged='true')
    put('support',(5,18,4),'stone')
    put('head',(2,20,6),'dragon_head','skull',rotation='11')
    return positions
