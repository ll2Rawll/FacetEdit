from pathlib import Path
import shutil
import struct
import tempfile
import unittest

from facetedit import nbt
from facetedit.converter import prepare_conversion,publish_conversion
from facetedit.formats import decode_bedrock,encode_bedrock
from facetedit.leveldb import load_database,write_database
from facetedit.model import Document,Selection
from facetedit.registry import for_world,profile
from facetedit.structures import export_structure,import_mcstructure
from facetedit.world import open_world
from tests.test_conversion import plain_java
from tests.test_workflows import hashes
from tests.version_fixture import bedrock_version,gallery


class VersionWorldTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.path=Path(self.temp.name)

    def convert(self,source,target,name):
        plan=prepare_conversion(source,target);self.addCleanup(plan.close)
        self.assertTrue(plan.report.ok,plan.report.summary())
        return Document(open_world(publish_conversion(plan,self.path/name)))

    def test_java_bedrock60_native_roundtrip_with_payloads_and_paired_doors(self):
        java=plain_java(self.path/'java');positions=gallery(java)
        template=open_world(bedrock_version(self.path/'bedrock60'));before=hashes(template.path),hashes(java.world.path)
        native=self.convert(java,template,'native');self.assertEqual(for_world(native.world).label,'Bedrock 1.21.60')
        self.assertEqual(dict(native.get(*positions['door_lower']).properties)['minecraft:cardinal_direction'],'north')
        self.assertEqual(dict(native.get(*positions['gate']).properties)['minecraft:cardinal_direction'],'east')
        self.assertEqual(dict(native.get(*positions['heart']).properties)['creaking_heart_state'],'dormant')
        chest=nbt.loads(native.get_entity(*positions['chest']))[1]
        desc=chest.value['Items'].value.values[0]['tag'].value['Items'].value.values[0]['Block'].value
        self.assertEqual(desc['version'],nbt.Tag(nbt.INT,18168865))
        restored=self.convert(native,java.world,'restored')
        for label,position in positions.items():self.assertEqual(restored.get(*position),java.get(*position),label)
        camp=nbt.loads(restored.get_entity(*positions['campfire']))[1]
        self.assertEqual(camp.value['CookingTimes'].value,[0,0,37,0])
        self.assertEqual((hashes(template.path),hashes(java.world.path)),before)

    def test_native50_60_migration_keeps_payloads_biome_voxels_and_versions(self):
        java=plain_java(self.path/'java');positions=gallery(java)
        old=self.convert(java,open_world(bedrock_version(self.path/'template50',(1,21,50))),'native50')
        old.selection=Selection((1,1,1),(1,1,1));old.set_biome('numeric:200')
        old_bytes=old.get_entity(*positions['chest'])
        modern=self.convert(old,open_world(bedrock_version(self.path/'template60')),'native60')
        self.assertEqual(modern.get_biome(1,1,1),'numeric:200');self.assertEqual(modern.get_biome(2,1,1),old.get_biome(2,1,1))
        restored=self.convert(modern,old.world,'native50-again')
        for label,position in positions.items():
            self.assertEqual(restored.get(*position),old.get(*position),label)
            self.assertEqual(restored.get_entity(*position),old.get_entity(*position),label)
        self.assertEqual(restored.get_entity(*positions['chest']),old_bytes)
        self.assertEqual(restored.get_biome(1,1,1),'numeric:200')
        modern.selection=Selection((0,15,0),(17,23,15));modern.copy()
        structure=self.path/'native60.mcstructure';export_structure(modern.clipboard,structure)
        root=nbt.loads(structure.read_bytes(),little=True)[1]
        tags=root.value['structure'].value['palette'].value['default'].value['block_palette'].value.values
        self.assertTrue(all(t['version'].value==18168865 for t in tags))
        loaded=import_mcstructure(structure);self.assertEqual(loaded.blocks,modern.clipboard.blocks);self.assertEqual(loaded.entities,modern.clipboard.entities)

    def test_mixed_palette_world_uses_entry_versions_and_keeps_original_bytes(self):
        path=bedrock_version(self.path/'mixed');values=load_database(path/'db');prefix=struct.pack('<ii',0,0)
        legacy=profile('Bedrock 1.21.50');gate=legacy.block('minecraft:fence_gate',{'direction':'2','in_wall_bit':'false','open_bit':'true'})
        raw=encode_bedrock(9,1,[[gate]*4096],palette_version=18163713);values[prefix+b'/\1']=raw
        shutil.rmtree(path/'db');write_database(path/'db',values);before=hashes(path)
        world=open_world(path);self.assertEqual(dict(world.get_block(1,17,1).properties)['minecraft:cardinal_direction'],'north')
        self.assertEqual(world.values[prefix+b'/\1'],raw);self.assertEqual(hashes(path),before)
        doc=Document(world);doc.selection=Selection((1,17,1),(1,17,1));doc.fill(profile('Bedrock 1.21.60').initial('minecraft:glass'))
        doc.world.export(self.path/'edited',doc.edits,**doc.export_metadata());edited=open_world(self.path/'edited')
        self.assertEqual(edited.get_block(2,17,1),world.get_block(2,17,1))
        native=decode_bedrock(edited.values[prefix+b'/\1'])
        self.assertTrue(all(nbt.get(t,'version')==18168865 for t in native[3][0]))

    def test_uprooted_heart_stops_native_downgrade_before_publication(self):
        source=Document(open_world(bedrock_version(self.path/'source60')))
        source.set_entity((1,2,3),None);source.selection=Selection((1,17,1),(1,17,1));source.fill(profile('Bedrock 1.21.60').initial('minecraft:creaking_heart'))
        target=open_world(bedrock_version(self.path/'target50',(1,21,50)));before=hashes(source.world.path),hashes(target.path)
        plan=prepare_conversion(source,target);self.addCleanup(plan.close)
        self.assertFalse(plan.report.ok);self.assertIn('Uprooted',plan.report.summary())
        with self.assertRaisesRegex(ValueError,'blocked'):publish_conversion(plan,self.path/'refused')
        self.assertFalse((self.path/'refused').exists());self.assertEqual((hashes(source.world.path),hashes(target.path)),before)
