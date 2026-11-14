import copy
from dataclasses import replace
import itertools
import unittest

from facetedit import nbt
from facetedit.bedrock_versions import read_descriptor
from facetedit.item_translation import ItemTranslator,item_catalog
from facetedit.model import Clipboard
from facetedit.payloads import root
from facetedit.registry import for_version,profile
from facetedit.translation import Translator,translate_clipboard
from tests.test_advanced_translation import item,tag,sequence


class VersionTranslationTests(unittest.TestCase):
    def setUp(self):
        self.java=profile('Java 1.21.4');self.old=profile('Bedrock 1.21.50');self.new=profile('Bedrock 1.21.60')

    def test_primary_profile_is_distinct_and_typed(self):
        self.assertIs(for_version('Bedrock',game_version=(1,21,60)),self.new)
        self.assertEqual(len(self.new.blocks),1241);self.assertEqual(self.new.palette_version,18168865)
        for name in self.new.blocks:self.assertEqual(self.new.validate(self.new.initial(name)),self.new.initial(name))
        _,items=item_catalog(self.new.version)
        self.assertEqual(len(items),1369);self.assertNotIn('minecraft:air',items)
        self.assertIn('minecraft:air',item_catalog(self.old.version)[1])
        with self.assertRaises(ValueError):self.new.validate(self.old.initial('minecraft:wooden_door'))

    def test_all_changed_door_gate_combinations_migrate_both_directions(self):
        forward,reverse=Translator(self.old,self.new),Translator(self.new,self.old);families=0
        for name,schema in self.old.blocks.items():
            if not name.endswith(('_door','fence_gate')) or 'direction' not in schema['properties']:continue
            families+=1;keys=schema['properties']
            for values in itertools.product(*(v[1] for v in keys.values())):
                old=self.old.block(name,dict(zip(keys,values)));native,extra=forward.block(old)
                p=dict(native.properties);self.assertNotIn('direction',p)
                self.assertEqual(p['minecraft:cardinal_direction'],('south','west','north','east')[int(dict(old.properties)['direction'])])
                self.assertEqual(dict(native.state_types)['minecraft:cardinal_direction'],nbt.STRING)
                self.assertEqual(reverse.block(native,extra)[0],old)
        self.assertEqual(families,33)

    def test_paired_doors_cross_sections_and_all_horizontal_transforms(self):
        for facing,hinge,opened in itertools.product(('east','south','west','north'),('left','right'),('false','true')):
            blocks={(0,y,0):self.java.block('minecraft:oak_door',{'half':half,'facing':facing,'hinge':hinge,'open':opened},defaults=True)
                    for y,half in enumerate(('lower','upper'))}
            source=Clipboard((1,2,1),blocks);native,report=translate_clipboard(source,self.new)
            self.assertTrue(report.ok,report.summary())
            self.assertEqual(dict(native.blocks[0,0,0].properties)['minecraft:cardinal_direction'],{'east':'south','south':'west','west':'north','north':'east'}[facing])
            for turn,mirror in itertools.product(range(4),(False,True)):
                moved=native.transformed(turn,mirror);restored,report=translate_clipboard(moved,self.java)
                self.assertTrue(report.ok,report.summary());self.assertEqual(restored.blocks,source.transformed(turn,mirror).blocks)
                expected,report=translate_clipboard(source.transformed(turn,mirror),self.new)
                self.assertTrue(report.ok);self.assertEqual(moved.blocks,expected.blocks)
        lower=Clipboard((1,1,1),{(0,0,0):native.blocks[0,0,0]},'Bedrock',data_version=None,game_version=self.new.version)
        joined,report=translate_clipboard(lower,self.java,neighbour=lambda p:native.blocks.get(p))
        self.assertTrue(report.ok,report.summary());self.assertEqual(dict(joined.blocks[0,0,0].properties)['facing'],facing)

    def test_hearts_preserve_shared_states_and_refuse_uprooted_downgrades(self):
        for active,natural,axis in itertools.product(('false','true'),('false','true'),('x','y','z')):
            old=self.old.block('minecraft:creaking_heart',{'active':active,'natural':natural,'pillar_axis':axis})
            native,_=Translator(self.old,self.new).block(old)
            self.assertEqual(dict(native.properties)['creaking_heart_state'],'awake' if active=='true' else 'dormant')
            self.assertEqual(Translator(self.new,self.old).block(native)[0],old)
            java,_=Translator(self.new,self.java).block(native)
            self.assertEqual(Translator(self.java,self.new).block(java)[0],native)
        uprooted=self.new.initial('minecraft:creaking_heart')
        for target in (self.old,self.java):
            clip=Clipboard((2,1,1),{(0,0,0):self.new.initial('minecraft:stone'),(1,0,0):uprooted},'Bedrock',data_version=None,game_version=self.new.version)
            before=copy.deepcopy(clip);result,report=translate_clipboard(clip,target)
            self.assertIsNone(result);self.assertIn('Uprooted',report.summary());self.assertEqual(clip,before)
        result,report=translate_clipboard(Clipboard((1,1,1),{(0,0,0):uprooted},'Bedrock',data_version=None,game_version=self.new.version),self.new)
        self.assertTrue(report.ok);self.assertEqual(result.blocks[0,0,0],uprooted)

    def test_new_profile_item_names_and_declared_descriptor_version(self):
        old=ItemTranslator(Translator(self.java,self.old));new=ItemTranslator(Translator(self.java,self.new));reverse=ItemTranslator(Translator(self.new,self.java))
        source=item('oak_fence_gate',components={'minecraft:block_state':nbt.compound(facing=tag(nbt.STRING,'east'))})
        original=copy.deepcopy(source);native=old.to_bedrock(source)
        self.assertEqual(reverse.to_java(native),source)
        modern=new.to_bedrock(source);self.assertEqual(modern['Block'].value['version'],tag(nbt.INT,18168865))
        self.assertEqual(modern['Block'].value['states'].value['minecraft:cardinal_direction'],tag(nbt.STRING,'east'))
        self.assertEqual(reverse.to_java(modern),source);self.assertEqual(source,original)
        for entry in (item('air'),):
            with self.assertRaisesRegex(ValueError,'Bedrock 1.21.60 item'):new.to_bedrock(entry)
        native['Block'].value['version']=tag(nbt.INT,18168866)
        with self.assertRaisesRegex(ValueError,'unsupported embedded'):reverse.to_java(native)

    def test_descriptor_boolean_width_and_unknown_version_are_not_coerced(self):
        from facetedit.formats import bedrock_entry
        descriptor=bedrock_entry(self.new.initial('minecraft:fence_gate'),self.new.palette_version)
        descriptor.value['states'].value['open_bit']=tag(nbt.BYTE,2)
        with self.assertRaisesRegex(ValueError,'boolean byte'):read_descriptor(descriptor,self.new)

    def test_removed_native_item_is_blocked_during_same_edition_upgrade(self):
        data=root('Chest',(0,0,0),'Bedrock',{'Items':sequence(nbt.COMPOUND,[{'Name':tag(nbt.STRING,'minecraft:air'),
                    'Count':tag(nbt.BYTE,1),'Damage':tag(nbt.SHORT,0),'Slot':tag(nbt.BYTE,4)}])})
        clip=Clipboard((1,1,1),{(0,0,0):self.old.initial('minecraft:chest')},'Bedrock',entities={(0,0,0):data},data_version=None,game_version=self.old.version)
        before=copy.deepcopy(clip);result,report=translate_clipboard(clip,self.new)
        self.assertIsNone(result);self.assertIn('Items[0].Name',report.summary());self.assertIn('minecraft:air',report.summary());self.assertEqual(clip,before)

    def test_jigsaw_identifier_cannot_hide_a_changed_target_default(self):
        data=root('JigsawBlock',(0,0,0),'Bedrock',{'final_state':tag(nbt.STRING,'minecraft:creaking_heart')})
        clip=Clipboard((1,1,1),{(0,0,0):self.old.initial('minecraft:jigsaw')},'Bedrock',entities={(0,0,0):data},data_version=None,game_version=self.old.version)
        result,report=translate_clipboard(clip,self.new)
        self.assertIsNone(result);self.assertIn('final_state: target block default changed',report.summary())
        value=nbt.loads(data)[1];value.value['final_state']=tag(nbt.STRING,'minecraft:stone');clip.entities[0,0,0]=nbt.dumps(value)
        result,report=translate_clipboard(clip,self.new);self.assertTrue(report.ok,report.summary())
        self.assertEqual(nbt.loads(result.entities[0,0,0])[1].value['final_state'],tag(nbt.STRING,'minecraft:stone'))

    def test_nested_native_inventory_migration_rewrites_only_descriptors(self):
        gate=item('oak_fence_gate',components={'minecraft:block_state':nbt.compound(facing=tag(nbt.STRING,'west'))})
        box=item('blue_shulker_box',components={'minecraft:container':sequence(nbt.COMPOUND,[{'slot':tag(nbt.INT,26),'item':tag(nbt.COMPOUND,gate)}])})
        inventory=ItemTranslator(Translator(self.java,self.old)).inventory(nbt.ListValue(nbt.COMPOUND,[{**box,'Slot':tag(nbt.BYTE,12)}]),'Java',27)
        data=root('Chest',(0,0,0),'Bedrock',{'Items':inventory,'Findable':tag(nbt.BYTE,0)})
        old=Clipboard((1,1,1),{(0,0,0):self.old.initial('minecraft:chest')},'Bedrock',entities={(0,0,0):data},data_version=None,game_version=self.old.version)
        modern,report=translate_clipboard(old,self.new);self.assertTrue(report.ok,report.summary())
        restored,report=translate_clipboard(modern,self.old);self.assertTrue(report.ok,report.summary())
        self.assertEqual(nbt.loads(restored.entities[0,0,0]),nbt.loads(data))
        nested=nbt.loads(modern.entities[0,0,0])[1].value['Items'].value.values[0]['tag'].value['Items'].value.values[0]['Block'].value
        self.assertEqual(nested['version'],tag(nbt.INT,18168865));self.assertNotIn('direction',nested['states'].value)
        value=nbt.loads(data)[1];value.value['Items'].value.values[0]['Unsupported']=tag(nbt.INT,7)
        old.entities[0,0,0]=nbt.dumps(value);unchanged=copy.deepcopy(old)
        failed,report=translate_clipboard(old,self.new);self.assertIsNone(failed);self.assertIn('Unsupported',report.summary());self.assertEqual(old,unchanged)

    def test_same_edition_migration_preserves_multiple_native_layers(self):
        base=self.old.initial('minecraft:stone');gate=self.old.block('minecraft:fence_gate',{'direction':'3','open_bit':'true','in_wall_bit':'false'})
        clip=Clipboard((1,1,1),{(0,0,0):base},'Bedrock',data_version=None,extra_blocks={(0,0,0):(gate,self.old.initial('minecraft:water'),self.old.initial('minecraft:glass'))},game_version=self.old.version)
        modern,report=translate_clipboard(clip,self.new);self.assertTrue(report.ok,report.summary());self.assertEqual(len(modern.extra_blocks[0,0,0]),3)
        old,report=translate_clipboard(modern,self.old);self.assertTrue(report.ok);self.assertEqual(old,clip)

    def test_known_release_relabeling_and_unregistered_profile_are_refused(self):
        clip=Clipboard((1,1,1),{(0,0,0):self.old.initial('minecraft:stone')},'Bedrock',data_version=None,game_version=self.old.version)
        with self.assertRaisesRegex(ValueError,'known clipboard game version'):translate_clipboard(clip,self.java,source=self.new)
        with self.assertRaisesRegex(ValueError,'verified'):Translator(replace(self.new,version=(1,21,61)),self.java)
        with self.assertRaises(InterruptedError):translate_clipboard(clip,self.new,cancelled=lambda:True)

    def test_older_inactive_heart_mapping_is_disclosed(self):
        clip=Clipboard((1,1,1),{(0,0,0):self.java.initial('minecraft:creaking_heart')})
        native,report=translate_clipboard(clip,self.new);self.assertTrue(report.ok,report.summary());self.assertIn('becomes dormant',report.summary())
