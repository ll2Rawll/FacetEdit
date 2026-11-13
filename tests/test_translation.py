import itertools
import unittest

from facetedit.blocks import AIR, Block
from facetedit.matching import BlockMatcher
from facetedit.model import Clipboard, Document, Selection
from facetedit.registry import profile
from facetedit.translation import Translator, translate_clipboard, STATELESS
from facetedit.world import SampleWorld


class TranslationTests(unittest.TestCase):
    def setUp(self):
        self.java=profile('Java 1.21.4');self.bedrock=profile('Bedrock 1.21.50')
        self.forward=Translator(self.java,self.bedrock);self.reverse=Translator(self.bedrock,self.java)

    def roundtrip(self, name, **props):
        block=self.java.block('minecraft:'+name,props,defaults=True)
        result,layers=self.forward.block(block)
        restored,extras=self.reverse.block(result,layers)
        self.assertEqual(restored,block)
        self.assertEqual(extras,())
        return result,layers

    def test_explicit_stateless_mapping_corpus(self):
        self.assertEqual(len(STATELESS),307)
        for name in STATELESS:
            self.roundtrip(name.removeprefix('minecraft:'))

    def test_axis_waterlogging_and_typed_state_vectors(self):
        for name,axis in itertools.product(('oak_log','stripped_cherry_log','quartz_pillar','deepslate','chain'),('x','y','z')):
            props={'axis':axis}
            if name=='chain':props['waterlogged']='true'
            result,layers=self.roundtrip(name,**props)
            self.assertEqual(dict(result.properties)['pillar_axis'],axis)
            self.assertEqual(dict(result.state_types)['pillar_axis'],8)
        result,layers=self.roundtrip('oak_stairs',facing='west',half='top',waterlogged='true')
        self.assertEqual(dict(result.properties),{'upside_down_bit':'true','weirdo_direction':'1'})
        self.assertEqual(dict(result.state_types),{'upside_down_bit':1,'weirdo_direction':3})
        self.assertEqual(layers,(self.bedrock.block('minecraft:water',{'liquid_depth':'0'}),))

    def test_copper_and_wood_slabs_all_native_variants(self):
        for name in self.java.blocks:
            if not name.endswith('_slab'):continue
            for half in ('bottom','top','double'):
                self.roundtrip(name.removeprefix('minecraft:'),type=half)

    def test_crop_fluid_rail_sign_wall_vectors(self):
        for n,p in [('wheat',{'age':'7'}),('beetroots',{'age':'2'}),('sugar_cane',{'age':'15'}),('farmland',{'moisture':'6'}),
                    ('water',{'level':'13'}),('lava',{'level':'4'}),('snow',{'layers':'8'}),('dark_oak_sign',{'rotation':'11'}),
                    ('dark_oak_wall_sign',{'facing':'west'}),('powered_rail',{'shape':'ascending_east','powered':'true'}),
                    ('cobblestone_wall',{'north':'low','south':'tall','up':'false','waterlogged':'true'}),('red_candle',{'candles':'4','lit':'true'})]:
            with self.subTest(n=n):self.roundtrip(n,**p)

    def test_building_controls_and_vegetation_vectors(self):
        for n,p in [('oak_trapdoor',{'facing':'north','half':'top','open':'true'}),('oak_fence_gate',{'facing':'west','open':'true'}),
                    ('stone_button',{'face':'ceiling','facing':'north','powered':'true'}),('oak_pressure_plate',{'powered':'true'}),
                    ('heavy_weighted_pressure_plate',{'power':'7'}),('wall_torch',{'facing':'east'}),('redstone_wall_torch',{'lit':'false','facing':'south'}),
                    ('bamboo',{'age':'1','stage':'1','leaves':'large'}),('tnt',{'unstable':'true'}),('cherry_sapling',{'stage':'1'}),
                    ('redstone_ore',{'lit':'true'}),('barrel',{'facing':'up','open':'true'})]:
            with self.subTest(n=n):self.roundtrip(n,**p)

    def test_door_pair_context_restores_shared_properties(self):
        blocks={(0,y,0):self.java.block('minecraft:oak_door',{'half':half,'facing':'west','hinge':'right','open':'true'},defaults=True) for y,half in enumerate(('lower','upper'))}
        clip=Clipboard((1,2,1),blocks)
        translated,report=translate_clipboard(clip,self.bedrock);self.assertTrue(report.ok,report.summary())
        self.assertEqual(dict(translated.blocks[0,1,0].properties)['direction'],'0')
        self.assertEqual(dict(translated.blocks[0,0,0].properties)['door_hinge_bit'],'false')
        restored,report=translate_clipboard(translated,self.java);self.assertTrue(report.ok,report.summary())
        self.assertEqual(restored.blocks,blocks)
        translated,report=translate_clipboard(Clipboard((1,1,1),{(0,0,0):blocks[0,0,0]}),self.bedrock)
        self.assertIsNone(translated);self.assertIn('both matching halves',report.summary())

    def test_leaf_distance_uses_source_neighbours_and_keeps_water_layer(self):
        leaf=self.bedrock.block('minecraft:oak_leaves',{'persistent_bit':'false','update_bit':'false'})
        log=self.bedrock.block('minecraft:oak_log',{'pillar_axis':'y'})
        clip=Clipboard((3,1,1),{(0,0,0):log,(1,0,0):leaf,(2,0,0):leaf},'Bedrock',data_version=None,game_version=self.bedrock.version,
            extra_blocks={(2,0,0):(self.bedrock.initial('minecraft:water'),)})
        translated,report=translate_clipboard(clip,self.java)
        self.assertTrue(report.ok,report.summary())
        self.assertEqual(dict(translated.blocks[1,0,0].properties)['distance'],'1')
        self.assertEqual(dict(translated.blocks[2,0,0].properties)['distance'],'2')
        self.assertEqual(dict(translated.blocks[2,0,0].properties)['waterlogged'],'true')
        isolated=Clipboard((1,1,1),{(0,0,0):leaf},'Bedrock',data_version=None,game_version=self.bedrock.version)
        translated,report=translate_clipboard(isolated,self.java,neighbour=lambda p:log if p==(-1,0,0) else AIR)
        self.assertEqual(dict(translated.blocks[0,0,0].properties)['distance'],'1')
        translated,report=translate_clipboard(isolated,self.java,neighbour=lambda p:Block('mushroom_stem') if p==(-1,0,0) else AIR)
        self.assertEqual(dict(translated.blocks[0,0,0].properties)['distance'],'7')

    def test_trapdoor_transform_uses_verified_native_direction_order(self):
        native,_=self.forward.block(self.java.block('minecraft:oak_trapdoor',{'facing':'north'},defaults=True))
        self.assertEqual(dict(native.properties)['direction'],'3')
        turned=native.transform(1,False,'Bedrock')
        self.assertEqual(dict(turned.properties)['direction'],'0')
        java,_=self.reverse.block(turned)
        self.assertEqual(dict(java.properties)['facing'],'east')

    def test_contextual_stair_corner_and_atomic_inconsistent_shape(self):
        a=self.java.block('minecraft:oak_stairs',{'facing':'east','shape':'outer_left'},defaults=True)
        b=self.java.block('minecraft:birch_stairs',{'facing':'north'},defaults=True)
        clip=Clipboard((2,1,1),{(0,0,0):a,(1,0,0):b})
        converted,report=translate_clipboard(clip,self.bedrock)
        self.assertTrue(report.ok,report.summary())
        restored,report=translate_clipboard(converted,self.java)
        self.assertEqual(restored.blocks,clip.blocks)
        isolated=Clipboard((1,1,1),{(0,0,0):a})
        result,report=translate_clipboard(isolated,self.bedrock)
        self.assertIsNone(result);self.assertIn('disagrees',report.summary())

    def test_unmapped_payload_and_invalid_layer_leave_input_unchanged(self):
        clip=Clipboard((2,1,1),{(0,0,0):Block('stone'),(1,0,0):Block('custom:machine')})
        original=dict(clip.blocks)
        result,report=translate_clipboard(clip,self.bedrock)
        self.assertIsNone(result);self.assertFalse(report.ok)
        self.assertEqual(clip.blocks,original)
        clip=Clipboard((1,1,1),{(0,0,0):Block('stone')},entities={(0,0,0):b'opaque payload'})
        result,report=translate_clipboard(clip,self.bedrock)
        self.assertIsNone(result);self.assertIn('NBT',report.summary())
        with self.assertRaisesRegex(ValueError,'cannot represent'):
            self.reverse.block(Block('stone'),(self.bedrock.initial('minecraft:water'),))

    def test_every_java_initial_mapping_reverses_or_reports_named_air_normalization(self):
        supported=0
        for name in self.java.blocks:
            block=self.java.initial(name)
            try:result,layers=self.forward.block(block)
            except ValueError:continue
            supported+=1
            restored,_=self.reverse.block(result,layers)
            self.assertEqual(restored,AIR if name in ('minecraft:cave_air','minecraft:void_air') else block,name)
        self.assertGreater(supported,600)

    def test_cancellation_and_explicit_air_normalization_note(self):
        clip=Clipboard((1,1,1),{(0,0,0):Block('cave_air')})
        result,report=translate_clipboard(clip,self.bedrock)
        self.assertEqual(result.blocks[(0,0,0)],AIR)
        self.assertIn('air subtype',report.summary())
        with self.assertRaises(InterruptedError):translate_clipboard(clip,self.bedrock,cancelled=lambda:True)

    def test_explicit_profile_cannot_relabel_known_clipboard_metadata(self):
        clip=Clipboard((1,1,1),{(0,0,0):Block('stone')})
        with self.assertRaisesRegex(ValueError,'edition'):
            translate_clipboard(clip,self.java,source=self.bedrock)
        clip.data_version=3839
        with self.assertRaisesRegex(ValueError,'DataVersion'):
            translate_clipboard(clip,self.bedrock,source=self.java)
        clip.edition='Bedrock';clip.data_version=None;clip.game_version=(1,20,0)
        with self.assertRaisesRegex(ValueError,'game version'):
            translate_clipboard(clip,self.java,source=self.bedrock)
        clip.game_version=None
        translated,report=translate_clipboard(clip,self.java,source=self.bedrock)
        self.assertTrue(report.ok);self.assertEqual(translated.blocks,clip.blocks)


class MatchingTests(unittest.TestCase):
    def test_name_subset_exact_and_pattern(self):
        block=profile('Java 1.21.4').initial('minecraft:oak_stairs')
        self.assertFalse(BlockMatcher.parse('oak_stairs').matches(block))
        self.assertTrue(BlockMatcher.parse('oak_stairs','name').matches(block))
        self.assertTrue(BlockMatcher.parse('oak_stairs[half=bottom]','subset').matches(block))
        self.assertTrue(BlockMatcher.parse('*_stairs[half=bottom]','pattern').matches(block))
        self.assertFalse(BlockMatcher.parse('*_stairs[half=top]','pattern').matches(block))
        self.assertTrue(BlockMatcher.parse(str(block)).matches(block))

    def test_replace_predicate_is_one_undo_step(self):
        doc=Document(SampleWorld());doc.selection=Selection((1,30,1),(2,30,1))
        doc.apply('setup',[((1,30,1),Block.parse('oak_log[axis=x]')),((2,30,1),Block.parse('birch_log[axis=y]'))])
        n=doc.fill(Block('glass'),replace=BlockMatcher.parse('*_log','pattern'))
        self.assertEqual(n,2)
        doc.undo();self.assertEqual(doc.get(1,30,1),Block.parse('oak_log[axis=x]'))
