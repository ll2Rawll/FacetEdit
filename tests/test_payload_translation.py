import json
import unittest

from facetedit import nbt,text_components
from facetedit.item_translation import ItemTranslator,COLORS
from facetedit.registry import profile
from facetedit.translation import Translator,translate_clipboard
from facetedit.blocks import AIR,Block
from facetedit.model import Clipboard
from facetedit.payloads import root
from facetedit.payload_formats import PATTERNS,TEXT_RGB


def item(name,count=1,**components):
    result={'id':nbt.Tag(nbt.STRING,'minecraft:'+name),'count':nbt.Tag(nbt.INT,count)}
    if components:result['components']=nbt.Tag(nbt.COMPOUND,components)
    return result


class TextTranslationTests(unittest.TestCase):
    def test_unicode_nested_styles_and_inherited_component_array(self):
        raw=json.dumps([{'text':'Hi 世界 ','color':'red','bold':True},{'text':'builder','bold':False,'extra':[{'text':' 🌍','italic':True}]}])
        native=text_components.to_bedrock(raw)
        self.assertEqual(native,'§r§c§lHi 世界 §r§cbuilder§r§c§o 🌍')
        self.assertEqual(text_components.java_runs(text_components.from_bedrock(native)),text_components.java_runs(raw))

    def test_bedrock_color_codes_keep_styles_until_reset(self):
        result=text_components.java_runs(text_components.from_bedrock('§lBold §cRed §rPlain'))
        self.assertEqual(result,[('Bold ',{'bold':True}),('Red ',{'bold':True,'color':'red'}),('Plain',{})])

    def test_nested_array_inherits_its_first_component_style(self):
        self.assertEqual(text_components.java_runs('[[{"text":"a","color":"red"},"b"],"c"]'),[('abc',{'color':'red'})])

    def test_dynamic_events_unknown_styles_and_nested_budgets_refused(self):
        for value in ({'translate':'item.minecraft.diamond'},{'text':'x','clickEvent':{'action':'run_command','value':'/say test'}},
                      {'text':'x','underlined':True},{'text':'x','color':'#123456'},{'text':'§r'}):
            with self.subTest(value=value),self.assertRaises(ValueError):text_components.to_bedrock(json.dumps(value))
        for value in ('§','§zUnknown'):
            with self.assertRaises(ValueError):text_components.from_bedrock(value)
        value={'text':'x'}
        for _ in range(34):value={'text':'','extra':[value]}
        with self.assertRaisesRegex(ValueError,'nesting'):text_components.to_bedrock(json.dumps(value))


class ItemTranslationTests(unittest.TestCase):
    def setUp(self):
        self.java=profile('Java 1.21.4');self.bedrock=profile('Bedrock 1.21.50')
        self.forward=ItemTranslator(Translator(self.java,self.bedrock));self.reverse=ItemTranslator(Translator(self.bedrock,self.java))

    def test_inventory_native_names_numeric_widths_and_count_limits(self):
        source=nbt.ListValue(nbt.COMPOUND,[{**item('diamond',99),'Slot':nbt.Tag(nbt.BYTE,4)}])
        native=self.forward.inventory(source,'Java',27)
        entry=native.value.values[0]
        self.assertEqual(entry['Name'],nbt.Tag(nbt.STRING,'minecraft:diamond'))
        self.assertEqual(entry['Count'],nbt.Tag(nbt.BYTE,99));self.assertEqual(entry['Damage'],nbt.Tag(nbt.SHORT,0))
        self.assertNotIn('id',entry);self.assertNotIn('count',entry)
        self.assertEqual(self.reverse.inventory(native.value,'Bedrock',27).value,source)
        for count in (0,100,127,-128,-1):
            entry['Count']=nbt.Tag(nbt.BYTE,count)
            with self.assertRaisesRegex(ValueError,'Count'):self.reverse.inventory(native.value,'Bedrock',27)

    def test_item_aliases_and_bed_banner_colors_are_bidirectional(self):
        for name in ('stone_stairs','cobblestone_stairs','nether_brick','nether_bricks','snow','snow_block','bricks',
                     *[c+'_bed' for c in COLORS],*[c+'_banner' for c in COLORS]):
            with self.subTest(name=name):
                value=item(name);self.assertEqual(self.reverse.to_java(self.forward.to_bedrock(value)),value)

    def test_tool_components_and_name_styles_retain_semantics(self):
        source=item('diamond_sword',**{'minecraft:damage':nbt.Tag(nbt.INT,67),'minecraft:repair_cost':nbt.Tag(nbt.INT,3),
            'minecraft:custom_name':nbt.Tag(nbt.STRING,'{"text":"Bright blade","color":"aqua","italic":true}'),
            'minecraft:lore':nbt.Tag(nbt.LIST,nbt.ListValue(nbt.STRING,['"Made here"'])),
            'minecraft:enchantments':nbt.compound(levels=nbt.compound(**{'minecraft:sharpness':nbt.Tag(nbt.INT,5),'minecraft:mending':nbt.Tag(nbt.INT,1)})),
            'minecraft:unbreakable':nbt.compound()})
        native=self.forward.to_bedrock(source);self.assertEqual(native['tag'].value['ench'].value.values[0]['id'],nbt.Tag(nbt.SHORT,9))
        restored=self.reverse.to_java(native)
        old=source['components'].value;new=restored['components'].value
        self.assertEqual(text_components.java_runs(new['minecraft:custom_name'].value),text_components.java_runs(old['minecraft:custom_name'].value))
        for key in old.keys()-{'minecraft:custom_name'}:self.assertEqual(new[key],old[key])

    def test_nested_shulker_contents_preserve_item_slots(self):
        source=item('red_shulker_box',**{'minecraft:container':nbt.Tag(nbt.LIST,nbt.ListValue(nbt.COMPOUND,[{
            'slot':nbt.Tag(nbt.INT,26),'item':nbt.Tag(nbt.COMPOUND,item('diamond',13))}]))})
        self.assertEqual(self.reverse.to_java(self.forward.to_bedrock(source)),source)

    def test_enchantment_levels_obey_the_primary_java_codec_in_both_directions(self):
        source=item('diamond_sword',**{'minecraft:enchantments':nbt.compound(levels=nbt.compound(**{'minecraft:sharpness':nbt.Tag(nbt.INT,255)}))})
        native=self.forward.to_bedrock(source);self.assertEqual(self.reverse.to_java(native),source)
        for level in (0,256,32767):
            source['components'].value['minecraft:enchantments'].value['levels'].value['minecraft:sharpness']=nbt.Tag(nbt.INT,level)
            with self.assertRaisesRegex(ValueError,'level from 1 to 255'):self.forward.to_bedrock(source)
            native['tag'].value['ench'].value.values[0]['lvl']=nbt.Tag(nbt.SHORT,level)
            with self.assertRaisesRegex(ValueError,'range 1–255'):self.reverse.to_java(native)

    def test_item_block_state_uses_typed_native_descriptor(self):
        source=item('oak_log',**{'minecraft:block_state':nbt.compound(axis=nbt.Tag(nbt.STRING,'x'))})
        native=self.forward.to_bedrock(source)
        self.assertEqual(native['Block'].value['version'].value,18163713)
        self.assertEqual(self.reverse.to_java(native),source)

    def test_unknown_data_bad_slots_and_unrepresentable_variants_fail_with_paths(self):
        cases=[item('custom_missing'),item('stone',256),item('filled_map'),item('potion'),
               item('diamond',**{'minecraft:custom_data':nbt.compound(important=nbt.Tag(nbt.INT,1))}),
               item('diamond_sword',**{'minecraft:enchantments':nbt.compound(levels=nbt.compound(**{'minecraft:sweeping_edge':nbt.Tag(nbt.INT,1)}))})]
        for value in cases:
            with self.subTest(value=value),self.assertRaisesRegex(ValueError,'item'):self.forward.to_bedrock(value)
        for slots in ((1,1),(27,)):
            value=nbt.ListValue(nbt.COMPOUND,[{**item('stone'),'Slot':nbt.Tag(nbt.BYTE,n)} for n in slots])
            with self.assertRaisesRegex(ValueError,'Slot'):self.forward.inventory(value,'Java',27)
        native=self.forward.to_bedrock(item('stone'));native['tag']=nbt.compound(unknown=nbt.Tag(nbt.INT,1))
        with self.assertRaisesRegex(ValueError,'tag.*unknown'):self.reverse.to_java(native)


class CellTranslationTests(unittest.TestCase):
    def setUp(self):
        self.java=profile('Java 1.21.4');self.bedrock=profile('Bedrock 1.21.50')
        self.forward=Translator(self.java,self.bedrock);self.reverse=Translator(self.bedrock,self.java)

    def block(self,name,**props):return self.java.block('minecraft:'+name,props,defaults=True)

    def roundtrip(self,name,identifier=None,payload=None,**props):
        source=self.block(name,**props)
        data=root('minecraft:'+identifier,(0,0,0),'Java',payload or {}) if identifier else None
        native,layers,entity=self.forward.cell(source,entity=data)
        restored,extras,new_data=self.reverse.cell(native,layers,entity)
        self.assertEqual(restored,source);self.assertEqual(extras,())
        return native,nbt.loads(entity)[1] if entity else None,nbt.loads(new_data)[1] if new_data else None

    def test_all_bed_colors_orientations_and_halves(self):
        for color in COLORS:
            for facing in ('north','east','south','west'):
                for part in ('head','foot'):
                    _,native,_=self.roundtrip(color+'_bed','bed',facing=facing,part=part)
                    self.assertEqual(nbt.get(native,'id'),'Bed');self.assertEqual(native.value['color'],nbt.Tag(nbt.BYTE,COLORS.index(color)))

    def test_banner_all_patterns_colors_and_mountings(self):
        patterns=nbt.Tag(nbt.LIST,nbt.ListValue(nbt.COMPOUND,[{'pattern':nbt.Tag(nbt.STRING,'minecraft:'+name),'color':nbt.Tag(nbt.STRING,COLORS[i%16])} for i,name in enumerate(PATTERNS)]))
        for color in COLORS:
            for suffix,props in (('_banner',{'rotation':'13'}),('_wall_banner',{'facing':'west'})):
                _,native,restored=self.roundtrip(color+suffix,'banner',{'patterns':patterns},**props)
                self.assertEqual(nbt.get(native,'Base'),15-COLORS.index(color));self.assertEqual(restored.value['patterns'],patterns)

    def test_pots_generate_plant_descriptors_without_inventing_java_nbt(self):
        names=[name.removeprefix('minecraft:') for name in self.java.blocks if name.startswith('minecraft:potted_')]
        for name in ('flower_pot',*names):
            with self.subTest(name=name):
                _,native,restored=self.roundtrip(name)
                self.assertIsNone(restored)
                if name!='flower_pot':self.assertEqual(native.value['PlantBlock'].value['version'].value,18163713)

    def test_shulker_facing_and_inventory_follow_cardinal_and_tilted_transforms(self):
        from facetedit.entities import transform
        from facetedit.affine import Transform
        for facing in ('down','up','north','south','west','east'):
            for name in ('shulker_box','red_shulker_box'):
                _,native,restored=self.roundtrip(name,'shulker_box',facing=facing)
                data=nbt.dumps(native)
                for transform_value in (Transform((1,1,1),rotation=(90,0,0)),Transform((1,1,1),rotation=(0,90,0)),Transform((1,1,1),scale=(-1,1,1))):
                    turned=transform_value.entity(data,(0,0,0));block,_,_=self.reverse.cell(self.bedrock.block('minecraft:undyed_shulker_box' if name=='shulker_box' else 'minecraft:'+name,{}),entity=turned)
                    self.assertEqual(dict(block.properties)['facing'],transform_value.direction(facing))
                turned=transform(data,(1,1,1),1)
                self.assertEqual(nbt.loads(turned)[1].value['facing'].kind,nbt.BYTE)
                self.assertEqual(nbt.loads(transform(turned,(1,1,1),3))[1],native)

    def test_containers_translate_native_items_and_preserve_typed_slots(self):
        entries=nbt.Tag(nbt.LIST,nbt.ListValue(nbt.COMPOUND,[{**item('diamond',12),'Slot':nbt.Tag(nbt.BYTE,1)}]))
        for name in ('chest','trapped_chest','barrel','hopper','dispenser','dropper','furnace','smoker','blast_furnace'):
            with self.subTest(name=name):
                _,native,restored=self.roundtrip(name,'chest' if name=='trapped_chest' else name,{'Items':entries,'CustomName':nbt.Tag(nbt.STRING,'"Storage"')})
                self.assertEqual(native.value['Items'].value.values[0]['Name'].value,'minecraft:diamond')
                self.assertEqual(restored.value['Items'],entries);self.assertEqual(nbt.get(restored,'CustomName'),'"Storage"')

    def test_two_sided_sign_text_colors_glow_wax_and_native_widths(self):
        messages=nbt.Tag(nbt.LIST,nbt.ListValue(nbt.STRING,['{"text":"Hello","color":"aqua","bold":true}','"世界"','""','"Line four"']))
        for color in COLORS:
            front=nbt.compound(messages=messages,color=nbt.Tag(nbt.STRING,color),has_glowing_text=nbt.Tag(nbt.BYTE,1))
            payload={'front_text':front,'back_text':nbt.compound(messages=messages),'is_waxed':nbt.Tag(nbt.BYTE,1)}
            for name in ('oak_sign','cherry_wall_sign','bamboo_hanging_sign','oak_wall_hanging_sign'):
                _,native,restored=self.roundtrip(name,'hanging_sign' if 'hanging' in name else 'sign',payload)
                side=native.value['FrontText'].value
                self.assertEqual(side['SignTextColor'],nbt.Tag(nbt.INT,TEXT_RGB[COLORS.index(color)]-(1<<24)))
                self.assertEqual(nbt.get(native,'IsWaxed'),1)
                for key in ('front_text','back_text'):
                    self.assertEqual([text_components.java_runs(s) for s in restored.value[key].value['messages'].value.values],[text_components.java_runs(s) for s in messages.value.values])
                self.assertEqual(restored.value['front_text'].value['color'].value,color)

    def test_note_instrument_derived_from_neighbours_in_both_directions(self):
        for below,instrument in (('gold_block','bell'),('stone','basedrum'),('glass','hat'),('oak_planks','bass'),('clay','flute'),('packed_ice','chime'),('ice','harp'),('air','harp')):
            clip=Clipboard((1,2,1),{(0,0,0):self.block(below),(0,1,0):self.block('note_block',note='24',instrument=instrument)})
            translated,report=translate_clipboard(clip,self.bedrock);self.assertTrue(report.ok,report.summary())
            self.assertEqual(nbt.loads(translated.entities[0,1,0])[1].value['note'],nbt.Tag(nbt.BYTE,24))
            restored,report=translate_clipboard(translated,self.java);self.assertTrue(report.ok,report.summary());self.assertEqual(restored.blocks,clip.blocks)
        invalid=Clipboard((1,1,1),{(0,0,0):self.block('note_block',instrument='bell')})
        result,report=translate_clipboard(invalid,self.bedrock);self.assertIsNone(result);self.assertIn('instrument disagrees',report.summary())

    def test_head_identity_rotations_mounts_and_transforms_retain_float_nbt(self):
        from facetedit.payloads import HEADS
        for head in HEADS:
            for rotation in range(16):
                block,tag,_=self.roundtrip(head,'skull',rotation=str(rotation))
                self.assertEqual(tag.value['Rotation'].kind,nbt.FLOAT)
                clip=Clipboard((1,1,1),{(0,0,0):block},'Bedrock',entities={(0,0,0):nbt.dumps(tag)},data_version=None,game_version=self.bedrock.version)
                for turns,mirror in ((1,False),(2,True)):
                    changed=clip.transformed(turns,mirror)
                    restored,report=translate_clipboard(changed,self.java);self.assertTrue(report.ok,report.summary())
                    self.assertEqual(dict(restored.blocks[0,0,0].properties)['rotation'],str(((-rotation if mirror else rotation)+4*turns)%16))
                tilted=clip.affine(rotation=(0,90,0));restored,report=translate_clipboard(tilted,self.java)
                self.assertTrue(report.ok,report.summary());self.assertEqual(dict(restored.blocks[0,0,0].properties)['rotation'],str((rotation+4)%16))
            wall=head.replace('_skull','_wall_skull') if head.endswith('_skull') else head.replace('_head','_wall_head')
            for facing in ('north','east','south','west'):
                block,tag,_=self.roundtrip(wall,'skull',facing=facing)
                clip=Clipboard((1,1,1),{(0,0,0):block},'Bedrock',entities={(0,0,0):nbt.dumps(tag)},data_version=None,game_version=self.bedrock.version)
                restored,report=translate_clipboard(clip.transformed(1),self.java);self.assertTrue(report.ok,report.summary())
                self.assertEqual(restored.blocks[0,0,0],self.block(wall,facing=facing).transform(1))

    def test_custom_profiles_animation_and_continuous_head_angles_are_not_discarded(self):
        with self.assertRaisesRegex(ValueError,'profile'):
            self.forward.cell(self.block('player_head'),entity=root('minecraft:skull',(0,0,0),'Java',{'profile':nbt.compound(name=nbt.Tag(nbt.STRING,'Player'))}))
        with self.assertRaisesRegex(ValueError,'Powered'):self.forward.cell(self.block('dragon_head',powered='true'))
        block,_,data=self.forward.cell(self.block('dragon_head'));tag=nbt.loads(data)[1]
        tag.value['Rotation']=nbt.Tag(nbt.FLOAT,1.0)
        with self.assertRaisesRegex(ValueError,'16-step'):self.reverse.cell(block,entity=nbt.dumps(tag))

    def test_paired_chests_all_facings_and_reference_style_one_way_links(self):
        from facetedit.paired_chests import paired_position
        for facing in ('north','east','south','west'):
            a=(1,0,1);b=paired_position(a,facing,'right')
            blocks={a:self.block('chest',facing=facing,type='right'),b:self.block('chest',facing=facing,type='left')}
            entities={p:root('minecraft:chest',p,'Java',{'Items':nbt.Tag(nbt.LIST,nbt.ListValue(nbt.COMPOUND,[{**item('diamond',i+1),'Slot':nbt.Tag(nbt.BYTE,26)}]))}) for i,p in enumerate((a,b))}
            clip=Clipboard((3,1,3),blocks,entities=entities)
            translated,report=translate_clipboard(clip,self.bedrock);self.assertTrue(report.ok,report.summary())
            restored,report=translate_clipboard(translated,self.java);self.assertTrue(report.ok,report.summary());self.assertEqual(restored.blocks,blocks)
            for pos in entities:self.assertEqual(nbt.loads(restored.entities[pos])[1].value['Items'],nbt.loads(entities[pos])[1].value['Items'])
            # Amulet's writer can put a link only on the leading half.
            tag=nbt.loads(translated.entities[b])[1]
            for key in ('pairx','pairz','pairlead'):tag.value.pop(key)
            translated.entities[b]=nbt.dumps(tag)
            restored,report=translate_clipboard(translated,self.java);self.assertTrue(report.ok,report.summary());self.assertEqual(restored.blocks,blocks)

    def test_unknown_fields_wrong_ids_active_furnaces_and_incomplete_pairs_are_atomic(self):
        cases=[('chest','minecraft:chest',{'LootTable':nbt.Tag(nbt.STRING,'minecraft:chests/simple_dungeon')}),
               ('chest','minecraft:barrel',{}),('furnace','minecraft:furnace',{'BurnTime':nbt.Tag(nbt.SHORT,20)}),
               ('oak_sign','minecraft:sign',{'front_text':nbt.compound(messages=nbt.Tag(nbt.LIST,nbt.ListValue(nbt.STRING,['"x"']*5)))}),
               ('red_banner','minecraft:banner',{'extra_data':nbt.Tag(nbt.INT,7)})]
        for name,identifier,values in cases:
            clip=Clipboard((1,1,1),{(0,0,0):self.block(name)},entities={(0,0,0):root(identifier,(0,0,0),'Java',values)})
            original=dict(clip.entities);result,report=translate_clipboard(clip,self.bedrock)
            self.assertIsNone(result,report.summary());self.assertEqual(clip.entities,original)
        clip=Clipboard((1,1,1),{(0,0,0):self.block('chest',type='left')})
        result,report=translate_clipboard(clip,self.bedrock);self.assertIsNone(result);self.assertIn('both matching halves',report.summary())
