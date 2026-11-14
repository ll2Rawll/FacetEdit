import copy
import itertools
import unittest

from facetedit import nbt,text_components
from facetedit.advanced_context import wire_connections
from facetedit.blocks import AIR,Block
from facetedit.item_translation import ItemTranslator
from facetedit.model import Clipboard
from facetedit.payloads import root
from facetedit.registry import profile
from facetedit.translation import Translator,translate_clipboard

def tag(kind,value):return nbt.Tag(kind,value)
def sequence(kind,values):return tag(nbt.LIST,nbt.ListValue(kind,values))
def item(name,count=1,slot=None,components=None):
    value={'id':tag(nbt.STRING,'minecraft:'+name),'count':tag(nbt.INT,count)}
    if slot is not None:value['Slot']=tag(nbt.BYTE,slot)
    if components:value['components']=tag(nbt.COMPOUND,components)
    return value


class AdvancedTranslationTests(unittest.TestCase):
    def setUp(self):
        self.java=profile('Java 1.21.4');self.bedrock=profile('Bedrock 1.21.50')
        self.forward=Translator(self.java,self.bedrock);self.reverse=Translator(self.bedrock,self.java)

    def block(self,name,**p):return self.java.block('minecraft:'+name,p,defaults=True)

    def roundtrip(self,name,values,identifier=None,**props):
        block=self.block(name,**props);payload=root('minecraft:'+(identifier or name),(0,0,0),'Java',values)
        native,layers,encoded=self.forward.cell(block,entity=payload)
        restored,_,decoded=self.reverse.cell(native,layers,encoded)
        self.assertEqual(restored,block)
        return nbt.loads(encoded)[1].value,nbt.loads(decoded)[1].value if decoded else None

    def clip_roundtrip(self,size,blocks,**kwargs):
        clip=Clipboard(size,blocks);native,report=translate_clipboard(clip,self.bedrock,**kwargs)
        self.assertTrue(report.ok,report.summary());restored,report=translate_clipboard(native,self.java)
        self.assertTrue(report.ok,report.summary());self.assertEqual(restored.blocks,blocks)
        return native

    def test_vegetation_and_technical_native_state_vectors(self):
        cases=[('attached_pumpkin_stem',{'facing':'west'}),('melon_stem',{'age':'5'}),('beehive',{'facing':'east','honey_level':'4'}),
            ('big_dripleaf',{'facing':'west','tilt':'full','waterlogged':'true'}),('pink_petals',{'facing':'south','flower_amount':'4'}),
            ('jigsaw',{'orientation':'down_east'}),('structure_block',{'mode':'corner'}),('pale_moss_carpet',{'north':'tall','east':'low'}),
            ('small_dripleaf',{'half':'upper','facing':'south','waterlogged':'true'}),('piston_head',{'facing':'west','type':'sticky'}),
            ('trial_spawner',{'ominous':'true','trial_spawner_state':'ejecting_reward'}),('vault',{'facing':'west','vault_state':'unlocking'})]
        for name,p in cases:
            with self.subTest(name=name):
                block=self.block(name,**p);native,layers=self.forward.block(block);restored,_=self.reverse.block(native,layers);self.assertEqual(restored,block)

    def test_plant_body_terminal_and_age25_neighbour_roundtrips(self):
        for family in ('kelp','twisting_vines','weeping_vines'):
            for age in ('0','24','25'):
                head=0 if family=='weeping_vines' else 2
                blocks={(0,y,0):self.block(family,age=age) if y==head else self.block(family+'_plant') for y in range(3)}
                with self.subTest(family=family,age=age):self.clip_roundtrip((1,3,1),blocks)
        for berries in ('true','false'):
            blocks={(0,0,0):self.block('cave_vines',age='0',berries=berries),(0,1,0):self.block('cave_vines_plant',berries=berries)}
            self.clip_roundtrip((1,2,1),blocks)
        broken=Clipboard((1,1,1),{(0,0,0):self.block('cave_vines_plant')})
        result,report=translate_clipboard(broken,self.bedrock);self.assertIsNone(result);self.assertIn('continuation',report.summary())

    def test_plant_outside_clipboard_neighbours_restore_terminal(self):
        leaf=self.bedrock.block('minecraft:kelp',{'kelp_age':'25'})
        clip=Clipboard((1,1,1),{(0,0,0):leaf},'Bedrock',data_version=None,game_version=self.bedrock.version)
        single,report=translate_clipboard(clip,self.java);self.assertTrue(report.ok);self.assertEqual(single.blocks[0,0,0],self.block('kelp',age='25'))
        joined,report=translate_clipboard(clip,self.java,neighbour=lambda p:leaf if p==(0,1,0) else AIR)
        self.assertTrue(report.ok);self.assertEqual(joined.blocks[0,0,0],self.block('kelp_plant'))

    def test_fire_chorus_campfire_and_scaffolding_context(self):
        self.clip_roundtrip((2,1,1),{(0,0,0):self.block('fire',east='true'),(1,0,0):self.block('oak_planks')})
        self.clip_roundtrip((1,2,1),{(0,0,0):self.block('hay_block'),(0,1,0):self.block('campfire',signal_fire='true')})
        self.clip_roundtrip((1,3,1),{(0,0,0):self.block('end_stone'),(0,1,0):self.block('chorus_plant',up='true',down='true'),(0,2,0):self.block('chorus_flower')})
        self.clip_roundtrip((1,2,1),{(0,0,0):self.block('scaffolding',distance='7',bottom='true'),(0,1,0):self.block('scaffolding',distance='7',bottom='false')})

    def test_tripwire_links_hooks_and_native_support_flag(self):
        blocks={(0,0,0):self.block('stone'),(0,1,0):self.block('tripwire',east='true'),(1,1,0):self.block('tripwire_hook',facing='west')}
        native=self.clip_roundtrip((2,2,1),blocks)
        self.assertEqual(dict(native.blocks[0,1,0].properties)['suspended_bit'],'false')
        native=self.clip_roundtrip((1,1,1),{(0,0,0):self.block('tripwire')});self.assertEqual(dict(native.blocks[0,0,0].properties)['suspended_bit'],'true')

    def test_redstone_primary_predicates_vertical_steps_and_straight_arms(self):
        wire=self.block('redstone_wire');stone=self.block('stone')
        cases=[({},dict.fromkeys(('north','east','south','west'),'none')),
            ({(1,0,0):wire},{'north':'none','east':'side','south':'none','west':'side'}),
            ({(1,0,0):stone,(1,1,0):wire},{'north':'none','east':'up','south':'none','west':'side'}),
            ({(1,0,0):stone,(1,1,0):wire,(0,1,0):stone},dict.fromkeys(('north','east','south','west'),'none')),
            ({(1,-1,0):wire},{'north':'none','east':'side','south':'none','west':'side'})]
        for world,expected in cases:self.assertEqual(wire_connections((0,0,0),lambda p:world.get(p,AIR)),expected)
        for facing,expected in [('east','side'),('west','side'),('north','none'),('south','none')]:
            world={(1,0,0):self.block('repeater',facing=facing)}
            self.assertEqual(wire_connections((0,0,0),lambda p:world.get(p,AIR))['east'],expected)
        blocks={(0,0,0):self.block('redstone_wire',east='side',west='side'),(1,0,0):self.block('redstone_wire',east='side',west='side')}
        self.clip_roundtrip((2,1,1),blocks)

    def test_context_error_is_atomic_and_unknown_neighbour_is_named(self):
        clip=Clipboard((1,1,1),{(0,0,0):self.block('fire',north='true')});before=copy.deepcopy(clip)
        result,report=translate_clipboard(clip,self.bedrock);self.assertIsNone(result);self.assertIn('disagrees',report.summary());self.assertEqual(clip.blocks,before.blocks)
        result,report=translate_clipboard(clip,self.bedrock,neighbour=lambda p:Block('custom:unknown') if p==(0,-1,0) else AIR)
        self.assertIsNone(result);self.assertIn('custom:unknown',report.summary())

    def test_bell_event_toggle_is_not_misinterpreted_as_power(self):
        with self.assertRaisesRegex(ValueError,'ring events'):self.forward.block(self.block('bell',powered='true'))
        native,_=self.forward.block(self.block('bell'));p=dict(native.properties);p['toggle_bit']='true'
        with self.assertRaisesRegex(ValueError,'ring-event'):self.reverse.block(self.bedrock.block(native.name,p))
        native,_=self.roundtrip('bell',{});self.assertEqual(native['Direction'].kind,nbt.INT);self.assertEqual(native['Ticks'].kind,nbt.INT)

    def test_populated_campfire_retains_four_slots_and_cooking_progress(self):
        values={'Items':sequence(nbt.COMPOUND,[item('beef',slot=2),item('cod',slot=0)]),
            'CookingTimes':tag(nbt.INT_ARRAY,[599,0,37,0]),'CookingTotalTimes':tag(nbt.INT_ARRAY,[600,0,600,0])}
        native,back=self.roundtrip('campfire',values)
        self.assertEqual(native['ItemTime3'],tag(nbt.INT,37));self.assertEqual(native['Item1'].value['Name'].value,'minecraft:cod')
        self.assertNotIn('Slot',native['Item3'].value);self.assertEqual(back['CookingTimes'],values['CookingTimes']);self.assertEqual(back['CookingTotalTimes'],values['CookingTotalTimes'])
        self.assertEqual({e['Slot'].value:e['id'].value for e in back['Items'].value.values},{0:'minecraft:cod',2:'minecraft:beef'})
        values['CookingTotalTimes']=tag(nbt.INT_ARRAY,[200,0,600,0])
        with self.assertRaisesRegex(ValueError,'duration'):self.roundtrip('campfire',values)

    def test_bookshelf_inventory_and_last_slot_are_consistent(self):
        values={'Items':sequence(nbt.COMPOUND,[item('book',slot=5)]),'last_interacted_slot':tag(nbt.INT,5)}
        native,back=self.roundtrip('chiseled_bookshelf',values,slot_5_occupied='true')
        self.assertEqual(native['LastInteractedSlot'],tag(nbt.INT,6));self.assertEqual(back['last_interacted_slot'],values['last_interacted_slot'])
        self.assertEqual(back['Items'],values['Items'])
        with self.assertRaisesRegex(ValueError,'occupancy'):self.roundtrip('chiseled_bookshelf',values)

    def test_static_written_book_and_lectern_page_survive(self):
        content=nbt.compound(title=tag(nbt.STRING,'Field notes'),author=tag(nbt.STRING,'Builder'),generation=tag(nbt.INT,1),resolved=tag(nbt.BYTE,1),
            pages=sequence(nbt.STRING,['{"text":"Glass","color":"aqua"}','"世界"']))
        values={'Book':tag(nbt.COMPOUND,item('written_book',components={'minecraft:written_book_content':content})),'Page':tag(nbt.INT,1)}
        native,back=self.roundtrip('lectern',values,has_book='true')
        self.assertEqual(native['totalPages'],tag(nbt.INT,2));self.assertEqual(native['hasBook'],tag(nbt.BYTE,1));self.assertEqual(back['Page'],tag(nbt.INT,1))
        book=back['Book'].value['components'].value['minecraft:written_book_content'].value
        self.assertEqual(book['title'].value,'Field notes');self.assertEqual(book['author'].value,'Builder')
        self.assertEqual(text_components.java_runs(book['pages'].value.values[0]),text_components.java_runs(content.value['pages'].value.values[0]))

    def test_writable_book_filterable_pages_and_unsupported_photo(self):
        content=nbt.compound(pages=sequence(nbt.COMPOUND,[{'raw':tag(nbt.STRING,'line one\nline two'),'filtered':tag(nbt.STRING,'line one\nline two')}]))
        original=item('writable_book',components={'minecraft:writable_book_content':content});native=ItemTranslator(self.forward).to_bedrock(original)
        back=ItemTranslator(self.reverse).to_java(native)
        self.assertEqual(back['components'].value['minecraft:writable_book_content'].value['pages'].value.values,['line one\nline two'])
        native['tag'].value['pages'].value.values[0]['photoname']=tag(nbt.STRING,'photo.png')
        with self.assertRaisesRegex(ValueError,'photoname'):ItemTranslator(self.reverse).to_java(native)
        content.value['pages'].value.values[0]['filtered']=tag(nbt.STRING,'different')
        with self.assertRaisesRegex(ValueError,'filtered'):ItemTranslator(self.forward).to_bedrock(original)

    def test_book_required_fields_and_utf16_limits_preserve_input(self):
        content=nbt.compound(title=tag(nbt.STRING,'📘'*16),author=tag(nbt.STRING,'Builder'),pages=sequence(nbt.STRING,['"Notes"']))
        original=item('written_book',components={'minecraft:written_book_content':content})
        native=ItemTranslator(self.forward).to_bedrock(original)
        self.assertEqual(native['tag'].value['title'].value,'📘'*16)
        for missing in ('title','author'):
            malformed=copy.deepcopy(original);del malformed['components'].value['minecraft:written_book_content'].value[missing]
            unchanged=copy.deepcopy(malformed)
            with self.subTest(missing=missing),self.assertRaisesRegex(ValueError,missing):ItemTranslator(self.forward).to_bedrock(malformed)
            self.assertEqual(malformed,unchanged)
        content.value['title']=tag(nbt.STRING,'📘'*17)
        with self.assertRaisesRegex(ValueError,'32 UTF-16'):ItemTranslator(self.forward).to_bedrock(original)
        for length in (512,513):
            writable=item('writable_book',components={'minecraft:writable_book_content':nbt.compound(pages=sequence(nbt.STRING,['📘'*length]))})
            if length==512:
                native=ItemTranslator(self.forward).to_bedrock(writable)
                self.assertEqual(ItemTranslator(self.reverse).to_java(native),writable)
            else:
                with self.assertRaisesRegex(ValueError,'content limit'):ItemTranslator(self.forward).to_bedrock(writable)
                native['tag'].value['pages'].value.values[0]['text']=tag(nbt.STRING,'📘'*length)
                with self.assertRaisesRegex(ValueError,'content limit'):ItemTranslator(self.reverse).to_java(native)

    def test_potion_variants_and_tipped_arrows_use_native_metadata(self):
        from facetedit.potion_items import POTIONS,KINDS
        seen=set()
        for kind,potion in itertools.product(KINDS,POTIONS):
            original=item(kind,components={'minecraft:potion_contents':nbt.compound(potion=tag(nbt.STRING,'minecraft:'+potion))})
            native=ItemTranslator(self.forward).to_bedrock(original)
            key=(native['Name'].value,native['Damage'].value);self.assertNotIn(key,seen);seen.add(key)
            self.assertEqual(native['Damage'].kind,nbt.SHORT)
            self.assertEqual(ItemTranslator(self.reverse).to_java(native),original)
        native=ItemTranslator(self.forward).to_bedrock(item('splash_potion',components={'minecraft:potion_contents':nbt.compound(potion=tag(nbt.STRING,'minecraft:weakness'))}))
        self.assertEqual(native['Damage'],tag(nbt.SHORT,34))
        native['tag']=nbt.compound(Potion=tag(nbt.STRING,'minecraft:weakness'))
        self.assertEqual(ItemTranslator(self.reverse).to_java(native)['components'].value['minecraft:potion_contents'].value['potion'].value,'minecraft:weakness')
        for value in (2,36,99):
            native['Damage']=tag(nbt.SHORT,value)
            with self.assertRaisesRegex(ValueError,'variant'):ItemTranslator(self.reverse).to_java(native)
        with self.assertRaisesRegex(ValueError,'equivalent'):
            ItemTranslator(self.forward).to_bedrock(item('potion',components={'minecraft:potion_contents':nbt.compound(potion=tag(nbt.STRING,'minecraft:luck'))}))

    def test_armor_trim_and_rgb_dye_roundtrip_without_losing_widths(self):
        from facetedit.armor_items import MATERIALS,PATTERNS
        for material,pattern in itertools.product(MATERIALS,PATTERNS):
            original=item('diamond_chestplate',components={'minecraft:trim':nbt.compound(material=tag(nbt.STRING,'minecraft:'+material),pattern=tag(nbt.STRING,'minecraft:'+pattern))})
            native=ItemTranslator(self.forward).to_bedrock(original)
            self.assertEqual(native['tag'].value['Trim'].value['Material'].value,material)
            self.assertEqual(ItemTranslator(self.reverse).to_java(native),original)
        for color in (0,0xffffff,0x214365):
            original=item('leather_helmet',components={'minecraft:dyed_color':nbt.compound(rgb=tag(nbt.INT,color))})
            native=ItemTranslator(self.forward).to_bedrock(original)
            self.assertEqual(native['tag'].value['customColor'],tag(nbt.INT,color-(1<<24)))
            self.assertEqual(ItemTranslator(self.reverse).to_java(native),original)
        native['tag'].value['customColor']=tag(nbt.INT,0x102030)
        with self.assertRaisesRegex(ValueError,'ARGB'):ItemTranslator(self.reverse).to_java(native)

    def test_brewing_native_slot_order_progress_and_crafter_disable_mask(self):
        potion=item('potion',slot=2,components={'minecraft:potion_contents':nbt.compound(potion=tag(nbt.STRING,'minecraft:swiftness'))})
        values={'Items':sequence(nbt.COMPOUND,[potion,item('redstone',slot=3),item('blaze_powder',slot=4)]),'BrewTime':tag(nbt.SHORT,399),'Fuel':tag(nbt.BYTE,17)}
        native,back=self.roundtrip('brewing_stand',values,has_bottle_2='true')
        self.assertEqual(native['FuelAmount'],tag(nbt.SHORT,17));self.assertEqual(native['CookTime'],tag(nbt.SHORT,399))
        self.assertEqual({e['Slot'].value:e['Name'].value for e in native['Items'].value.values},{3:'minecraft:potion',0:'minecraft:redstone',4:'minecraft:blaze_powder'})
        self.assertEqual(back['Items'],values['Items']);self.assertEqual(back['Fuel'],values['Fuel'])
        values={'Items':sequence(nbt.COMPOUND,[item('iron_ingot',5,slot=8)]),'disabled_slots':tag(nbt.INT_ARRAY,[0,3,6]),'triggered':tag(nbt.INT,1)}
        native,back=self.roundtrip('crafter',values,triggered='true')
        self.assertEqual(native['disabled_slots'],tag(nbt.SHORT,73));self.assertEqual(back['disabled_slots'],values['disabled_slots']);self.assertEqual(back['triggered'],tag(nbt.INT,1))
        values['disabled_slots']=tag(nbt.INT_ARRAY,[8])
        with self.assertRaisesRegex(ValueError,'disabled crafter'):self.roundtrip('crafter',values,triggered='true')

    def test_beacon_effects_and_cauldron_native_payloads(self):
        native,back=self.roundtrip('beacon',{'primary_effect':tag(nbt.STRING,'minecraft:haste'),'secondary_effect':tag(nbt.STRING,'minecraft:regeneration')})
        self.assertEqual(native['primary'],tag(nbt.INT,3));self.assertEqual(native['secondary'],tag(nbt.INT,10));self.assertEqual(back['primary_effect'].value,'minecraft:haste')
        block=self.block('water_cauldron',level='2');native,layers,payload=self.forward.cell(block)
        self.assertEqual(nbt.loads(payload)[1].value['PotionId'],tag(nbt.SHORT,-1))
        restored,_,data=self.reverse.cell(native,layers,payload);self.assertEqual(restored,block);self.assertIsNone(data)
        value=nbt.loads(payload)[1];value.value['CustomColor']=tag(nbt.INT,-1)
        with self.assertRaisesRegex(ValueError,'CustomColor'):self.reverse.cell(native,layers,nbt.dumps(value))

    def test_natural_spawner_fields_and_custom_entity_refusal(self):
        for name in ('pig','zombie','skeleton','spider','cave_spider','silverfish','blaze','magma_cube'):
            spawn=nbt.compound(entity=nbt.compound(id=tag(nbt.STRING,'minecraft:'+name)))
            values={'SpawnData':spawn,'SpawnPotentials':sequence(nbt.COMPOUND,[{'weight':tag(nbt.INT,1),'data':spawn}]),'Delay':tag(nbt.SHORT,37)}
            native,back=self.roundtrip('spawner',values,identifier='mob_spawner')
            self.assertEqual(native['EntityIdentifier'].value,'minecraft:'+name);self.assertEqual(back['SpawnData'],spawn);self.assertEqual(back['Delay'],tag(nbt.SHORT,37))
        spawn.value['entity'].value['CustomName']=tag(nbt.STRING,'"Custom"')
        with self.assertRaisesRegex(ValueError,'CustomName'):self.roundtrip('spawner',values,identifier='mob_spawner')

    def test_passive_sculk_and_unlinked_heart_payloads(self):
        for name in ('sculk_sensor','calibrated_sculk_sensor','sculk_shrieker','sculk_catalyst','creaking_heart'):
            self.roundtrip(name,{})
        with self.assertRaisesRegex(ValueError,'creaking'):
            self.roundtrip('creaking_heart',{'creaking':tag(nbt.INT_ARRAY,[1,2,3,4])})
        with self.assertRaisesRegex(ValueError,'warning_level'):
            self.roundtrip('sculk_shrieker',{'warning_level':tag(nbt.INT,3)})
        native,back=self.roundtrip('sculk_sensor',{'listener':nbt.compound(selector=nbt.compound(tick=tag(nbt.LONG,-1)),event_delay=tag(nbt.INT,0))})
        self.assertEqual(back['listener'].value['selector'].value['tick'],tag(nbt.LONG,-1))

    def test_jukebox_and_pottery_translate_actual_item_records(self):
        native,back=self.roundtrip('jukebox',{'RecordItem':tag(nbt.COMPOUND,item('music_disc_cat'))},has_record='true')
        self.assertEqual(native['RecordItem'].value['Name'].value,'minecraft:music_disc_cat');self.assertEqual(back['RecordItem'].value,item('music_disc_cat'))
        sherds=sequence(nbt.STRING,['minecraft:brick','minecraft:archer_pottery_sherd','minecraft:prize_pottery_sherd','minecraft:arms_up_pottery_sherd'])
        values={'item':tag(nbt.COMPOUND,item('diamond',9)),'sherds':sherds}
        native,back=self.roundtrip('decorated_pot',values,facing='east')
        self.assertEqual(native['item'].value['Count'],tag(nbt.BYTE,9));self.assertEqual(back['sherds'],sherds);self.assertEqual(back['item'],values['item'])

    def test_stationary_piston_arms_in_both_states_and_all_directions(self):
        for name,face,extended in itertools.product(('piston','sticky_piston'),('down','up','north','east','south','west'),('false','true')):
            block=self.block(name,facing=face,extended=extended);native,layers,payload=self.forward.cell(block)
            fields=nbt.loads(payload)[1].value
            self.assertEqual(fields['State'].value,2 if extended=='true' else 0);self.assertEqual(fields['isMovable'],tag(nbt.BYTE,int(extended=='false')))
            restored,_,data=self.reverse.cell(native,layers,payload);self.assertEqual(restored,block);self.assertIsNone(data)

    def test_new_state_transforms_commute_with_native_conversion(self):
        cases=[('piston',{'facing':'west'}),('sticky_piston',{'facing':'north'}),('piston_head',{'facing':'east'}),
            ('jigsaw',{'orientation':'up_east'}),('jigsaw',{'orientation':'down_south'}),('jigsaw',{'orientation':'north_up'}),
            ('lever',{'face':'ceiling','facing':'north'}),('lever',{'face':'wall','facing':'west'}),
            ('nether_portal',{'axis':'x'}),('oak_hanging_sign',{'rotation':'4','attached':'false'}),('oak_wall_hanging_sign',{'facing':'west'}),
            ('oak_door',{'facing':'east','half':'upper','hinge':'right'}),('oak_door',{'facing':'east','half':'lower','hinge':'right'}),
            ('pale_moss_carpet',{'east':'low','south':'tall'}),('cobblestone_wall',{'north':'low','east':'tall'}),
            ('decorated_pot',{'facing':'north'}),('chiseled_bookshelf',{'slot_0_occupied':'true','slot_5_occupied':'true'})]
        from facetedit.affine import Transform
        for name,p in cases:
            block=self.block(name,**p);native,_=self.forward.block(block)
            for turn,mirror in itertools.product(range(4),(False,True)):
                expected,_=self.forward.block(block.transform(turn,mirror,'Java'))
                self.assertEqual(native.transform(turn,mirror,'Bedrock'),expected,(name,turn,mirror))
        for name in ('piston','sticky_piston','piston_head'):
            block=self.block(name,facing='up');native,_=self.forward.block(block)
            transform=Transform((1,1,1),rotation=(0,0,90))
            back,_=self.reverse.block(transform.block(native,'Bedrock'));self.assertEqual(dict(back.properties)['facing'],'west')
        block=self.block('jigsaw',orientation='up_north');native,_=self.forward.block(block)
        transform=Transform((1,1,1),rotation=(180,0,0))
        back,_=self.reverse.block(transform.block(native,'Bedrock'));self.assertEqual(back,transform.block(block,'Java'))
        portal=self.block('nether_portal',axis='x');native,_=self.forward.block(portal)
        upright=Transform((1,1,1),rotation=(0,0,90));back,_=self.reverse.block(upright.block(native,'Bedrock'));self.assertEqual(back,portal)
        with self.assertRaisesRegex(ValueError,'horizontal portal'):Transform((1,1,1),rotation=(90,0,0)).block(native,'Bedrock')

    def test_mirrored_bookshelf_moves_slots_and_payload_together(self):
        block=self.block('chiseled_bookshelf',slot_0_occupied='true')
        payload=root('minecraft:chiseled_bookshelf',(0,0,0),'Java',{'Items':sequence(nbt.COMPOUND,[item('book',slot=0)]),'last_interacted_slot':tag(nbt.INT,0)})
        clip=Clipboard((1,1,1),{(0,0,0):block},entities={(0,0,0):payload})
        native,report=translate_clipboard(clip,self.bedrock);self.assertTrue(report.ok,report.summary())
        for mirrored in (native.transformed(0,True),native.affine(scale=(-1,1,1))):
            restored,report=translate_clipboard(mirrored,self.java);self.assertTrue(report.ok,report.summary())
            self.assertEqual(dict(restored.blocks[0,0,0].properties)['slot_2_occupied'],'true')
            data=nbt.loads(restored.entities[0,0,0])[1].value
            self.assertEqual(data['Items'].value.values[0]['Slot'].value,2);self.assertEqual(data['last_interacted_slot'].value,2)
        self.assertEqual(native.transformed(0,True).transformed(0,True).blocks,native.blocks)

    def test_gateway_structure_command_and_brushable_fields(self):
        native,back=self.roundtrip('end_gateway',{'Age':tag(nbt.LONG,40),'exit_portal':tag(nbt.INT_ARRAY,[-19,70,32])})
        self.assertEqual(native['ExitPortal'],sequence(nbt.INT,[-19,70,32]));self.assertEqual(back['Age'],tag(nbt.LONG,40));self.assertEqual(back['exit_portal'],tag(nbt.INT_ARRAY,[-19,70,32]))
        values={'mode':tag(nbt.STRING,'SAVE'),'name':tag(nbt.STRING,'example:room'),'rotation':tag(nbt.STRING,'CLOCKWISE_90'),'mirror':tag(nbt.STRING,'LEFT_RIGHT'),
            'sizeX':tag(nbt.INT,12),'sizeY':tag(nbt.INT,7),'sizeZ':tag(nbt.INT,8),'integrity':tag(nbt.FLOAT,0.5),'seed':tag(nbt.LONG,42)}
        native,back=self.roundtrip('structure_block',values,mode='save')
        for key,value in values.items():self.assertEqual(back[key],value)
        self.assertEqual(native['data'],tag(nbt.INT,1))
        native,back=self.roundtrip('chain_command_block',{'Command':tag(nbt.STRING,'say Build complete'),'auto':tag(nbt.BYTE,1)},identifier='command_block',conditional='true')
        self.assertEqual(back['Command'].value,'say Build complete');self.assertEqual(native['conditionalMode'],tag(nbt.BYTE,1))
        native,back=self.roundtrip('suspicious_gravel',{'item':tag(nbt.COMPOUND,item('diamond'))},identifier='brushable_block')
        self.assertEqual(native['item'].value['Name'].value,'minecraft:diamond')

    def test_unknown_complex_payloads_fail_atomically_with_the_field(self):
        cases=[('campfire',{'Items':sequence(nbt.COMPOUND,[item('stone',slot=0)])},'campfire','recipe'),
            ('beehive',{'bees':sequence(nbt.COMPOUND,[{}])},'beehive','bees'),
            ('command_block',{'Command':tag(nbt.STRING,'execute as @a run say hello')},'command_block','Command'),
            ('end_gateway',{'ExactTeleport':tag(nbt.BYTE,1)},'end_gateway','ExactTeleport'),
            ('trial_spawner',{'registered_players':sequence(nbt.INT_ARRAY,[[1,2,3,4]])},'trial_spawner','registered_players'),
            ('vault',{'unexpected':tag(nbt.INT,4)},'vault','unexpected')]
        for name,values,identifier,field in cases:
            clip=Clipboard((1,1,1),{(0,0,0):self.block(name)},entities={(0,0,0):root('minecraft:'+identifier,(0,0,0),'Java',values)})
            before=copy.deepcopy(clip);result,report=translate_clipboard(clip,self.bedrock)
            with self.subTest(name=name):self.assertIsNone(result);self.assertIn(field,report.summary());self.assertEqual(clip.entities,before.entities)
