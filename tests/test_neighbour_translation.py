import unittest

from facetedit import nbt
from facetedit.affine import Transform
from facetedit.blocks import AIR
from facetedit.model import Clipboard
from facetedit.payloads import root
from facetedit.registry import profile
from facetedit.translation import Translator,translate_clipboard


class NeighbourTranslationTests(unittest.TestCase):
    def setUp(self):
        self.java=profile('Java 1.21.4');self.bedrock=profile('Bedrock 1.21.50')
        self.forward=Translator(self.java,self.bedrock);self.reverse=Translator(self.bedrock,self.java)

    def block(self,name,**props):return self.java.block('minecraft:'+name,props,defaults=True)

    def test_primary_connection_rules_include_tags_and_partial_faces(self):
        from facetedit.state_facts import connects
        fence=self.block('oak_fence');nether=self.block('nether_brick_fence');pane=self.block('glass_pane')
        cases=[('stone',{},True,True,True),('oak_leaves',{},False,False,False),('pumpkin',{},False,False,False),
               ('birch_fence',{},True,False,False),('nether_brick_fence',{},False,True,False),
               ('glass_pane',{},False,False,True),('iron_bars',{},False,False,True),
               ('oak_fence_gate',{'facing':'north'},True,True,False),('oak_fence_gate',{'facing':'east'},False,False,False),
               ('oak_slab',{'type':'top'},False,False,False),('oak_slab',{'type':'double'},True,True,True)]
        for name,props,*expected in cases:
            with self.subTest(name=name,props=props):self.assertEqual([connects(b,self.block(name,**props),'west') for b in (fence,nether,pane)],expected)

    def test_fence_pane_context_roundtrip_and_inconsistent_connection_refused(self):
        for name in ('oak_fence','nether_brick_fence','glass_pane','iron_bars','blue_stained_glass_pane'):
            clip=Clipboard((2,1,1),{(0,0,0):self.block(name,east='true',waterlogged='true'),(1,0,0):self.block('stone')})
            native,report=translate_clipboard(clip,self.bedrock);self.assertTrue(report.ok,report.summary())
            restored,report=translate_clipboard(native,self.java);self.assertTrue(report.ok,report.summary());self.assertEqual(restored.blocks,clip.blocks)
            missing=Clipboard((1,1,1),{(0,0,0):clip.blocks[0,0,0]})
            _,report=translate_clipboard(missing,self.bedrock);self.assertIn('disagrees',report.summary())
            # World callers can supply context outside a section's local mask.
            native,report=translate_clipboard(missing,self.bedrock,neighbour=lambda p:self.block('stone') if p==(1,0,0) else AIR)
            self.assertTrue(report.ok,report.summary())

    def test_unknown_context_and_conflicting_chest_links_block_whole_clipboard(self):
        native=self.bedrock.block('minecraft:oak_fence',{})
        clip=Clipboard((1,1,1),{(0,0,0):native},'Bedrock',data_version=None,game_version=self.bedrock.version)
        from facetedit.blocks import Block
        result,report=translate_clipboard(clip,self.java,neighbour=lambda p:Block('custom:machine') if p==(1,0,0) else AIR)
        self.assertIsNone(result);self.assertIn('custom:machine',report.summary())
        chest=self.bedrock.block('minecraft:chest',{'minecraft:cardinal_direction':'north'})
        positions=((0,0,0),(1,0,0),(2,0,0));blocks={p:chest for p in positions}
        entities={p:root('Chest',p,'Bedrock',{'pairx':nbt.Tag(nbt.INT,1 if p[0]!=1 else 0),'pairz':nbt.Tag(nbt.INT,0),'pairlead':nbt.Tag(nbt.BYTE,int(p[0]!=1))}) for p in positions}
        result,report=translate_clipboard(Clipboard((3,1,1),blocks,'Bedrock',entities=entities,data_version=None,game_version=self.bedrock.version),self.java)
        self.assertIsNone(result);self.assertIn('conflicting',report.summary())

    def test_new_native_orientations_match_java_under_rotation_and_mirror(self):
        for name,props in [('end_rod',{'facing':'north'}),('amethyst_cluster',{'facing':'east'}),('brain_coral_wall_fan',{'facing':'west'}),('glow_lichen',{'north':'true','up':'true'})]:
            source=self.block(name,**props);native,layers=self.forward.block(source)
            for turns in range(4):
                for mirror in (False,True):
                    changed=native.transform(turns,mirror,'Bedrock');restored,_=self.reverse.block(changed,layers)
                    self.assertEqual(restored,source.transform(turns,mirror,'Java'))
            if 'coral' not in name:
                transform=Transform((1,1,1),rotation=(90,0,0))
                native_changed=transform.block(native,'Bedrock');restored,_=self.reverse.block(native_changed,layers)
                if name=='glow_lichen':
                    self.assertEqual(dict(restored.properties)['south'],'true');self.assertEqual(dict(restored.properties)['up'],'true')
                else:self.assertEqual(restored,transform.block(source,'Java'))

    def test_native_hanging_sign_representability_and_sea_pickle_water_consistency(self):
        with self.assertRaisesRegex(ValueError,'non-cardinal'):self.forward.block(self.block('oak_hanging_sign',rotation='3'))
        for rotation in range(16):
            source=self.block('oak_hanging_sign',rotation=str(rotation),attached='true',waterlogged='true')
            native,layers=self.forward.block(source);restored,_=self.reverse.block(native,layers);self.assertEqual(restored,source)
        wet=self.bedrock.block('minecraft:sea_pickle',{'cluster_count':'0','dead_bit':'false'})
        with self.assertRaisesRegex(ValueError,'water layer'):self.reverse.block(wet)

    def test_pair_cache_respects_changed_nbt_at_the_same_coordinates(self):
        from facetedit.paired_chests import cached_link
        position=(0,0,0)
        first=root('Chest',position,'Bedrock',{'pairx':nbt.Tag(nbt.INT,1),'pairz':nbt.Tag(nbt.INT,0),'pairlead':nbt.Tag(nbt.BYTE,1)})
        second=root('Chest',position,'Bedrock',{'pairx':nbt.Tag(nbt.INT,-1),'pairz':nbt.Tag(nbt.INT,0),'pairlead':nbt.Tag(nbt.BYTE,1)})
        self.assertEqual(cached_link(self.reverse,first,position),((1,0,0),True))
        self.assertEqual(cached_link(self.reverse,second,position),((-1,0,0),True))
        self.reverse.chest_link_bytes=4*1024*1024
        cached_link(self.reverse,root('Chest',(0,0,1),'Bedrock',{}),(0,0,1))
        self.assertEqual(len(self.reverse.chest_links),2)

    def test_multiface_rotation_with_vertical_reflection_applies_each_axis_once(self):
        source=self.block('glow_lichen',north='true',up='true')
        native,layers=self.forward.block(source)
        for rotation,scale in (((0,90,0),(1,-1,1)),((180,90,0),(1,1,1))):
            transform=Transform((1,1,1),rotation=rotation,scale=scale)
            restored,_=self.reverse.block(transform.block(native,'Bedrock'),layers)
            actual={k for k,v in restored.properties if v=='true' and k!='waterlogged'}
            self.assertEqual(actual,{transform.direction('north'),transform.direction('up')})
