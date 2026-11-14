"""Synthetic native worlds with interactive payloads and boundary context."""
from facetedit import nbt
from facetedit.model import Selection
from facetedit.payloads import root
from facetedit.registry import profile
from tests.test_advanced_translation import tag,sequence,item


def gallery(document):
    java=profile('Java 1.21.4');positions={}
    def put(label,position,name,identifier=None,payload=None,**props):
        positions[label]=position;document.selection=Selection(position,position)
        document.fill(java.block('minecraft:'+name,props,defaults=True))
        if identifier:document.set_entity(position,nbt.loads(root('minecraft:'+identifier,position,'Java',payload or {}))[1])
    book=item('written_book',components={'minecraft:written_book_content':nbt.compound(title=tag(nbt.STRING,'Builder notes'),author=tag(nbt.STRING,'FacetEdit'),
        generation=tag(nbt.INT,0),resolved=tag(nbt.BYTE,1),pages=sequence(nbt.STRING,['{"text":"Keep building","color":"aqua"}','"世界"']))})
    put('lectern',(2,20,2),'lectern','lectern',{'Book':tag(nbt.COMPOUND,book),'Page':tag(nbt.INT,1)},has_book='true',facing='south')
    put('bookshelf',(4,20,2),'chiseled_bookshelf','chiseled_bookshelf',{'Items':sequence(nbt.COMPOUND,[{**book,'Slot':tag(nbt.BYTE,5)},item('book',slot=0)]),
        'last_interacted_slot':tag(nbt.INT,5)},slot_0_occupied='true',slot_5_occupied='true')
    put('jukebox',(6,20,2),'jukebox','jukebox',{'RecordItem':tag(nbt.COMPOUND,item('music_disc_cat'))},has_record='true')
    put('pot',(8,20,2),'decorated_pot','decorated_pot',{'item':tag(nbt.COMPOUND,item('diamond',9)),
        'sherds':sequence(nbt.STRING,['minecraft:brick','minecraft:archer_pottery_sherd','minecraft:arms_up_pottery_sherd','minecraft:prize_pottery_sherd'])},facing='east')
    put('brushable',(10,20,2),'suspicious_sand','brushable_block',{'item':tag(nbt.COMPOUND,item('emerald',3))})
    put('command',(12,20,2),'chain_command_block','command_block',{'Command':tag(nbt.STRING,'say Build complete'),'auto':tag(nbt.BYTE,1)},facing='west')
    put('gateway',(14,20,2),'end_gateway','end_gateway',{'Age':tag(nbt.LONG,40),'exit_portal':tag(nbt.INT_ARRAY,[-19,70,32])})
    put('campfire',(15,16,4),'campfire','campfire',{'Items':sequence(nbt.COMPOUND,[item('beef',slot=2)]),
        'CookingTimes':tag(nbt.INT_ARRAY,[0,0,37,0]),'CookingTotalTimes':tag(nbt.INT_ARRAY,[0,0,600,0])},signal_fire='true')
    put('hay',(15,15,4),'hay_block')
    put('piston',(15,20,6),'sticky_piston',extended='true',facing='east')
    put('piston_head',(16,20,6),'piston_head',type='sticky',facing='east')
    for x in (15,16):put('wire'+str(x),(x,24,8),'redstone_wire',east='side',west='side')
    put('vines',(16,15,10),'twisting_vines_plant');put('vine_top',(16,16,10),'twisting_vines',age='25')
    put('structure',(2,20,6),'structure_block','structure_block',{'mode':tag(nbt.STRING,'SAVE'),'name':tag(nbt.STRING,'example:room'),
        'sizeX':tag(nbt.INT,8),'sizeY':tag(nbt.INT,5),'sizeZ':tag(nbt.INT,9),'rotation':tag(nbt.STRING,'CLOCKWISE_90')},mode='save')
    put('bell',(4,20,6),'bell','bell')
    potion=item('splash_potion',slot=0,components={'minecraft:potion_contents':nbt.compound(potion=tag(nbt.STRING,'minecraft:weakness'))})
    put('brewing',(6,20,6),'brewing_stand','brewing_stand',{'Items':sequence(nbt.COMPOUND,[potion,item('redstone',slot=3),item('blaze_powder',slot=4)]),
        'BrewTime':tag(nbt.SHORT,123),'Fuel':tag(nbt.BYTE,7)},has_bottle_0='true')
    put('crafter',(8,20,6),'crafter','crafter',{'Items':sequence(nbt.COMPOUND,[item('diamond',3,slot=0)]),'disabled_slots':tag(nbt.INT_ARRAY,[2,5,8])})
    put('cauldron',(10,20,6),'water_cauldron',level='2')
    put('beacon',(12,20,6),'beacon','beacon',{'primary_effect':tag(nbt.STRING,'minecraft:speed'),'secondary_effect':tag(nbt.STRING,'minecraft:regeneration')})
    spawn=nbt.compound(entity=nbt.compound(id=tag(nbt.STRING,'minecraft:skeleton')))
    put('spawner',(2,20,10),'spawner','mob_spawner',{'SpawnData':spawn,'SpawnPotentials':sequence(nbt.COMPOUND,[{'weight':tag(nbt.INT,1),'data':spawn}]),'Delay':tag(nbt.SHORT,37)})
    put('sensor',(4,20,10),'sculk_sensor','sculk_sensor',{'listener':nbt.compound(selector=nbt.compound())})
    put('shrieker',(6,20,10),'sculk_shrieker','sculk_shrieker',{'listener':nbt.compound(selector=nbt.compound()),'warning_level':tag(nbt.INT,0)})
    put('catalyst',(8,20,10),'sculk_catalyst','sculk_catalyst',{'cursors':sequence(nbt.COMPOUND,[])})
    put('heart',(10,20,10),'creaking_heart','creaking_heart')
    return positions
