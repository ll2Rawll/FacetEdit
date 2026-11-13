from pathlib import Path
import tempfile
import unittest

from facetedit import nbt,text_components
from facetedit.converter import prepare_conversion,publish_conversion
from facetedit.model import Document,Selection
from facetedit.structures import export_structure,import_mcstructure
from facetedit.world import open_world
from tests.payload_fixture import gallery
from tests.test_conversion import plain_java,modern_bedrock
from tests.test_workflows import hashes


class PayloadWorldTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.path=Path(self.temp.name)
        self.source=plain_java(self.path/'java');self.positions=gallery(self.source)
        self.target=open_world(modern_bedrock(self.path/'bedrock'))

    def tearDown(self):self.temp.cleanup()

    def converted(self):
        plan=prepare_conversion(self.source,self.target)
        self.addCleanup(plan.close);self.assertTrue(plan.report.ok,plan.report.summary())
        self.assertEqual(plan.report.payloads,10)
        return open_world(publish_conversion(plan,self.path/'converted'))

    def test_world_payloads_cross_chunk_pair_context_and_reverse_native_save(self):
        before,template=hashes(self.source.world.path),hashes(self.target.path)
        bedrock=self.converted()
        for label,identifier in (('chest','Chest'),('sign','Sign'),('bed','Bed'),('banner','Banner'),('shulker','ShulkerBox'),('pot','FlowerPot'),('note','Music'),('head','Skull')):
            self.assertEqual(nbt.loads(bedrock.get_block_entity(*self.positions[label]))[1].value['id'].value,identifier)
        left=nbt.loads(bedrock.get_block_entity(*self.positions['left']))[1]
        self.assertEqual(nbt.get(left,'pairx'),16);self.assertEqual(nbt.get(left,'pairlead'),0)
        plan=prepare_conversion(Document(bedrock),self.source.world);self.addCleanup(plan.close)
        self.assertTrue(plan.report.ok,plan.report.summary())
        java=open_world(publish_conversion(plan,self.path/'restored'))
        for label,pos in self.positions.items():
            self.assertEqual(java.get_block(*pos),self.source.get(*pos),label)
            original=self.source.get_entity(*pos);restored=java.get_block_entity(*pos)
            if original is None:self.assertIsNone(restored,label);continue
            old,new=nbt.loads(original)[1].value,nbt.loads(restored)[1].value
            if 'Items' in old:
                a,b=old['Items'].value.values,new['Items'].value.values;self.assertEqual(len(a),len(b))
                for source,target in zip(a,b):
                    self.assertEqual(source['id'],target['id']);self.assertEqual(source['count'],target['count']);self.assertEqual(source['Slot'],target['Slot'])
                    if 'components' in source:
                        ca,cb=source['components'].value,target['components'].value
                        self.assertEqual(ca['minecraft:damage'],cb['minecraft:damage']);self.assertEqual(ca['minecraft:enchantments'],cb['minecraft:enchantments'])
                        self.assertEqual(text_components.java_runs(ca['minecraft:custom_name'].value),text_components.java_runs(cb['minecraft:custom_name'].value))
        self.assertEqual(hashes(self.source.world.path),before);self.assertEqual(hashes(self.target.path),template)

    def test_translated_payloads_survive_structure_relocation_paste_undo_and_export(self):
        world=self.converted();doc=Document(world)
        doc.selection=Selection((2,16,2),(16,20,4));doc.copy()
        path=self.path/'gallery.mcstructure';export_structure(doc.clipboard,path)
        doc.clipboard=import_mcstructure(path)
        doc.paste((2,40,2));data=doc.get_entity(15,44,4);tag=nbt.loads(data)[1]
        self.assertEqual(nbt.get(tag,'pairx'),16);self.assertEqual(nbt.get(tag,'y'),44)
        self.assertEqual(nbt.get(nbt.loads(doc.get_entity(2,40,2))[1],'id'),'Chest')
        doc.undo();self.assertIsNone(doc.get_entity(15,44,4));self.assertTrue(doc.get(15,44,4).air)
        doc.redo();self.assertEqual(doc.get_entity(15,44,4),data)
        output=self.path/'pasted';world.export(output,doc.edits,**doc.export_metadata())
        self.assertEqual(open_world(output).get_block_entity(15,44,4),data)

    def test_unknown_inventory_component_leaves_sources_and_destination_untouched(self):
        pos=self.positions['chest'];tag=nbt.loads(self.source.get_entity(*pos))[1]
        tag.value['Items'].value.values[0]['components'].value['minecraft:custom_data']=nbt.compound(keep=nbt.Tag(nbt.INT,123))
        self.source.set_entity(pos,tag);before=hashes(self.source.world.path)
        plan=prepare_conversion(self.source,self.target);self.addCleanup(plan.close)
        self.assertFalse(plan.report.ok);self.assertIn('Items[0].components',plan.report.summary());self.assertIn('minecraft:custom_data',plan.report.summary())
        with self.assertRaises(ValueError):publish_conversion(plan,self.path/'blocked')
        self.assertFalse((self.path/'blocked').exists());self.assertEqual(hashes(self.source.world.path),before)
