from pathlib import Path
import os
import struct
import tempfile
import unittest

from facetedit import nbt
from facetedit import biomes
from facetedit.blocks import Block
from facetedit.converter import prepare_conversion, publish_conversion, publish_directory
from facetedit.leveldb import load_database, write_database
from facetedit.model import Document, Selection
from facetedit.world import open_world
from tests.fixtures import java_world,bedrock_world
from tests.test_workflows import hashes


def modern_bedrock(path):
    path=bedrock_world(path)
    raw=(path/'level.dat').read_bytes();root=nbt.loads(raw[8:],little=True)[1]
    root.value['lastOpenedWithVersion']=nbt.Tag(nbt.LIST,nbt.ListValue(nbt.INT,[1,21,50,7,0]))
    raw=nbt.dumps(root,little=True);(path/'level.dat').write_bytes(struct.pack('<II',10,len(raw))+raw)
    (path/'levelname.txt').write_text('Bedrock fixture',encoding='utf-8')
    values=load_database(path/'db')
    for cx,cz in ((0,0),(-1,-1)):
        prefix=struct.pack('<ii',cx,cz)
        values.pop(prefix+b'1',None)
        values[prefix+b'+']=b'\0'*512+biomes.encode_section([1]*4096)*24
    import shutil
    shutil.rmtree(path/'db');write_database(path/'db',values)
    return path


def plain_java(path):
    doc=Document(open_world(java_world(path)))
    for cx,cz in doc.world.chunk_positions('overworld'):
        doc.set_entity((cx*16+1,2,cz*16+3),None)
        doc.set_entity((cx*16+2,2,cz*16+3),None)
    return doc


class WorldConversionTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.path=Path(self.temp.name)

    def tearDown(self):self.temp.cleanup()

    def test_in_memory_sample_is_not_a_saved_conversion_input(self):
        from facetedit.world import SampleWorld
        with self.assertRaisesRegex(ValueError,'saved Minecraft world'):
            prepare_conversion(Document(SampleWorld()),SampleWorld())
        doc=plain_java(self.path/'java')
        with self.assertRaisesRegex(ValueError,'saved target template'):
            prepare_conversion(doc,SampleWorld())

    def test_atomic_publication_refuses_even_an_existing_empty_directory(self):
        staged=self.path/'staged';staged.mkdir();(staged/'level.dat').write_bytes(b'prepared')
        destination=self.path/'destination';destination.mkdir()
        with self.assertRaises(FileExistsError):publish_directory(staged,destination)
        self.assertEqual(list(destination.iterdir()),[])
        self.assertEqual((staged/'level.dat').read_bytes(),b'prepared')
        destination.rmdir();publish_directory(staged,destination)
        self.assertEqual((destination/'level.dat').read_bytes(),b'prepared')

    def test_current_bedrock_edits_and_structures_tag_new_states_with_the_native_version(self):
        from facetedit.formats import decode_bedrock
        from facetedit.registry import profile
        from facetedit.structures import export_structure,import_mcstructure
        doc=Document(open_world(modern_bedrock(self.path/'bedrock')))
        slab=profile('Bedrock 1.21.50').block('minecraft:oak_slab',{'minecraft:vertical_half':'top'})
        doc.selection=Selection((1,5,2),(1,5,2));doc.fill(slab);doc.copy()
        structure=self.path/'top-slab.mcstructure';export_structure(doc.clipboard,structure)
        root=nbt.loads(structure.read_bytes(),little=True)[1]
        palette=root.value['structure'].value['palette'].value['default'].value['block_palette'].value.values
        self.assertEqual(palette[0]['version'].value,18163713)
        self.assertEqual(import_mcstructure(structure).blocks,doc.clipboard.blocks)
        output=self.path/'edited';doc.world.export(output,doc.edits,**doc.export_metadata())
        reopened=open_world(output)
        tags=decode_bedrock(reopened.values[struct.pack('<ii',0,0)+b'/\0'])[3][0]
        tagged={nbt.get(t,'name'):nbt.get(t,'version') for t in tags}
        self.assertEqual(tagged['minecraft:oak_slab'],18163713)
        self.assertEqual(tagged['minecraft:stone'],17959425)
        self.assertEqual(reopened.get_block(1,5,2),slab)

    def test_java_to_bedrock_staged_edits_biomes_and_source_hashes(self):
        doc=plain_java(self.path/'java');target=open_world(modern_bedrock(self.path/'bedrock'))
        doc.selection=Selection((1,12,1),(1,12,1));doc.fill(Block.parse('oak_log[axis=z]'));doc.set_biome('desert')
        before,template_before=hashes(doc.world.path),hashes(target.path)
        plan=prepare_conversion(doc,target)
        self.addCleanup(plan.close)
        self.assertTrue(plan.report.ok,plan.report.summary())
        self.assertEqual(len(plan.entries),5)
        output=publish_conversion(plan,self.path/'converted')
        reopened=open_world(output)
        self.assertEqual(reopened.get_block(1,12,1),Block('oak_log',(('pillar_axis','z'),),(('pillar_axis',8),)))
        self.assertEqual(reopened.get_biome(1,12,1),'minecraft:desert')
        self.assertEqual(reopened.get_block(512,0,0),Block('stone'))
        self.assertIsNone(reopened.get_block_entity(1,2,3))
        self.assertEqual(hashes(doc.world.path),before);self.assertEqual(hashes(target.path),template_before)
        self.assertEqual(reopened.values[b'~local_player'],target.values[b'~local_player'])

    def test_bedrock_to_java_blocks_biomes_and_target_template(self):
        doc=Document(open_world(modern_bedrock(self.path/'bedrock')));target=open_world(java_world(self.path/'java'))
        doc.selection=Selection((1,17,2),(1,17,2));doc.fill(Block('glass'));doc.set_biome('desert')
        plan=prepare_conversion(doc,target,biome_policy='sample');self.addCleanup(plan.close)
        self.assertTrue(plan.report.ok,plan.report.summary())
        output=publish_conversion(plan,self.path/'converted');reopened=open_world(output)
        self.assertEqual(reopened.get_block(1,17,2),Block('glass'))
        self.assertEqual(reopened.get_block(-16,1,-16),Block('stone'))
        self.assertEqual(reopened.get_block(512,1,0),Block('stone'))
        self.assertEqual((output/'extra.dat').read_bytes(),b'unrelated preserved bytes')

    def test_exact_biomes_refuse_resolution_loss(self):
        doc=Document(open_world(modern_bedrock(self.path/'bedrock')));target=open_world(java_world(self.path/'java'))
        doc.selection=Selection((1,1,1),(1,1,1));doc.set_biome('desert')
        plan=prepare_conversion(doc,target);self.addCleanup(plan.close)
        self.assertFalse(plan.report.ok)
        self.assertIn('Mixed Bedrock biome voxels',plan.report.summary())
        with self.assertRaisesRegex(ValueError,'blocked'):publish_conversion(plan,self.path/'out')
        self.assertFalse((self.path/'out').exists())

    def test_same_version_bedrock_conversion_preserves_individual_numeric_biome_voxels(self):
        doc=Document(open_world(modern_bedrock(self.path/'bedrock')))
        target=open_world(modern_bedrock(self.path/'template'))
        doc.selection=Selection((1,1,1),(1,1,1));doc.set_biome('desert')
        doc.selection=Selection((2,1,1),(2,1,1));doc.set_biome('numeric:200')
        plan=prepare_conversion(doc,target);self.addCleanup(plan.close)
        self.assertTrue(plan.report.ok,plan.report.summary())
        reopened=open_world(publish_conversion(plan,self.path/'converted'))
        self.assertEqual(reopened.get_biome(0,1,1),'minecraft:plains')
        self.assertEqual(reopened.get_biome(1,1,1),'minecraft:desert')
        self.assertEqual(reopened.get_biome(2,1,1),'numeric:200')

    def test_block_entity_and_unmapped_block_preflight_refuse_publication(self):
        doc=Document(open_world(java_world(self.path/'java')));target=open_world(modern_bedrock(self.path/'bedrock'))
        doc.selection=Selection((1,18,1),(1,18,1));doc.fill(Block('custom:machine'))
        plan=prepare_conversion(doc,target);self.addCleanup(plan.close)
        self.assertFalse(plan.report.ok)
        self.assertIn('NBT',plan.report.summary());self.assertIn('custom:machine',plan.report.summary())
        with self.assertRaises(ValueError):publish_conversion(plan,self.path/'out')
        self.assertFalse((self.path/'out').exists())

    def test_block_nbt_in_an_absent_terrain_section_still_blocks_cross_edition_conversion(self):
        from facetedit.region import Region
        import shutil
        entity=nbt.compound(id=nbt.Tag(nbt.STRING,'Chest'),x=nbt.Tag(nbt.INT,1),y=nbt.Tag(nbt.INT,80),z=nbt.Tag(nbt.INT,3))
        clean=plain_java(self.path/'java-seed');java=self.path/'java'
        clean.world.export(java,clean.edits,**clean.export_metadata())
        path=java/'region/r.0.0.mca';region=Region.read(path);root=nbt.loads(region.get(0,0))[1]
        root.value['block_entities']=nbt.Tag(nbt.LIST,nbt.ListValue(nbt.COMPOUND,[entity.value]))
        region.put(0,0,nbt.dumps(root));region.write()
        bedrock=modern_bedrock(self.path/'bedrock');values=load_database(bedrock/'db')
        values[b'\0'*8+b'1']=nbt.dumps(entity,little=True)
        shutil.rmtree(bedrock/'db');write_database(bedrock/'db',values)
        for source,target in ((java,bedrock),(bedrock,java)):
            plan=prepare_conversion(Document(open_world(source)),open_world(target));self.addCleanup(plan.close)
            self.assertFalse(plan.report.ok)
            examples=[p for values in plan.report.examples.values() for p in values]
            self.assertIn(('overworld',1,80,3),examples)
            self.assertIn('Block NBT: no cross-edition payload rule for minecraft:air',plan.report.summary())

    def test_cancel_changed_source_and_destination_collision(self):
        doc=plain_java(self.path/'java');target=open_world(modern_bedrock(self.path/'bedrock'))
        with self.assertRaises(InterruptedError):prepare_conversion(doc,target,cancelled=lambda:True)
        plan=prepare_conversion(doc,target);self.addCleanup(plan.close)
        with self.assertRaises(InterruptedError):publish_conversion(plan,self.path/'out',cancelled=lambda:True)
        self.assertFalse((self.path/'out').exists())
        occupied=self.path/'occupied';occupied.mkdir();(occupied/'keep').write_text('mine')
        with self.assertRaises(FileExistsError):publish_conversion(plan,occupied)
        self.assertEqual((occupied/'keep').read_text(),'mine')
        changed=doc.world.path/'extra.dat';stat=changed.stat();raw=changed.read_bytes()
        changed.write_bytes(b'!'+raw[1:]);os.utime(changed,ns=(stat.st_atime_ns,stat.st_mtime_ns))
        with self.assertRaisesRegex(ValueError,'changed'):publish_conversion(plan,self.path/'out')

    def test_prepared_chunk_corruption_removes_unpublished_stage(self):
        doc=plain_java(self.path/'java');target=open_world(modern_bedrock(self.path/'bedrock'))
        plan=prepare_conversion(doc,target);self.addCleanup(plan.close)
        (Path(plan.temporary.name)/plan.entries[0][3]).write_bytes(b'corrupt prepared chunk')
        with self.assertRaisesRegex(ValueError,'changed on disk'):publish_conversion(plan,self.path/'out')
        self.assertFalse((self.path/'out').exists());self.assertFalse(list(self.path.glob('.facetedit-convert-*')))

    def test_cancel_during_publish_removes_private_stage(self):
        doc=plain_java(self.path/'java');target=open_world(modern_bedrock(self.path/'bedrock'))
        plan=prepare_conversion(doc,target);self.addCleanup(plan.close)
        cancel=[False]
        def progress(message):
            if message.startswith('Writing chunk'):cancel[0]=True
        with self.assertRaises(InterruptedError):publish_conversion(plan,self.path/'out',lambda:cancel[0],progress)
        self.assertFalse((self.path/'out').exists());self.assertFalse(list(self.path.glob('.facetedit-convert-*')))
