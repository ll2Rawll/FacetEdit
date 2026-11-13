from pathlib import Path
import json
import shutil
import struct
import tempfile
import unittest
from unittest import mock

from facetedit import nbt
from facetedit.blocks import AIR,Block
from facetedit.chunks import ChunkState,DELETED
from facetedit.leveldb import load_database,write_database
from facetedit.model import Document,Selection,SelectionGroup
from facetedit.region import Region
from facetedit.structures import save_project,load_project
from facetedit.world import open_world
from tests.fixtures import java_world,bedrock_world
from tests.test_workflows import hashes


def bedrock_metadata(path,version=(1,21,50),actors=False):
    file=path/'level.dat';raw=file.read_bytes();root=nbt.loads(raw[8:],little=True)[1]
    root.value['lastOpenedWithVersion']=nbt.Tag(nbt.LIST,nbt.ListValue(nbt.INT,list(version)+[0,0]))
    raw=nbt.dumps(root,little=True);file.write_bytes(struct.pack('<II',10,len(raw))+raw)
    values=load_database(path/'db');prefix=b'\0'*8
    # A source-template palette is intentionally opaque to empty-chunk creation.
    values[prefix+b'+']=b'\0'*512+b'opaque biome palette from same dimension'
    values[prefix+b'?']=b'unknown per-chunk record'
    if actors:
        a,b=struct.pack('<q',1),struct.pack('<q',2)
        values[b'digp'+prefix]=a+b
        values[b'digp'+struct.pack('<ii',-1,-1)]=b
        values[b'actorprefix'+a]=nbt.dumps(nbt.compound(identifier=nbt.Tag(nbt.STRING,'minecraft:pig')),little=True)
        values[b'actorprefix'+b]=nbt.dumps(nbt.compound(identifier=nbt.Tag(nbt.STRING,'minecraft:sheep')),little=True)
        values[prefix+b'2']=b'legacy entity record'
    shutil.rmtree(path/'db');write_database(path/'db',values)
    return path


def java_auxiliary(path):
    for category in ('entities','poi'):
        region=Region()
        for cx in (0,1):
            root=nbt.compound(DataVersion=nbt.Tag(nbt.INT,4189),
                Position=nbt.Tag(nbt.INT_ARRAY,[cx,0]),
                Unknown=nbt.Tag(nbt.STRING,category+'-preserve'),
                Entities=nbt.Tag(nbt.LIST,nbt.ListValue(nbt.COMPOUND,[{'UUID':nbt.Tag(nbt.INT_ARRAY,[1,2,3,cx])}])))
            region.put(cx,0,nbt.dumps(root))
        (path/category).mkdir();(path/category/'r.0.0.mca').write_bytes(region.dumps())
    return path


class ChunkWorkflowTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.path=Path(self.temp.name)
    def tearDown(self):self.temp.cleanup()

    def select(self,doc,*positions):
        boxes=[Selection((x*16,0,z*16),(x*16+15,0,z*16+15)) for x,z in positions]
        doc.selection=boxes[0] if len(boxes)==1 else SelectionGroup(boxes)

    def export(self,doc,name='out'):
        path=self.path/name
        doc.world.export(path,doc.edits,**doc.export_metadata())
        return open_world(path)

    def test_java_delete_terrain_entities_poi_preserves_neighbor_and_source(self):
        source=java_auxiliary(java_world(self.path/'java'));before=hashes(source)
        neighbors={kind:Region.read(source/kind/'r.0.0.mca').chunks[1] for kind in ('region','entities','poi')}
        doc=Document(open_world(source));self.select(doc,(0,0))
        self.assertEqual(doc.delete_chunks(),1);self.assertEqual(doc.get(1,2,3),AIR)
        out=self.export(doc)
        self.assertNotIn((0,0),out.chunk_positions('overworld'))
        for category in neighbors:
            region=Region.read(out.path/category/'r.0.0.mca')
            self.assertNotIn(0,region.chunks);self.assertEqual(region.chunks[1],neighbors[category])
        self.assertEqual(hashes(source),before)
        doc.undo();self.assertEqual(doc.get(1,2,3),Block('stone'))
        doc.redo();self.assertEqual(doc.get(1,2,3),AIR)

    def test_chunk_delete_undo_restores_block_entity_and_biome_edits(self):
        doc=Document(open_world(java_world(self.path/'java')))
        doc.apply('gold',[((4,2,3),Block('gold_block'))])
        tag=nbt.loads(doc.get_entity(1,2,3))[1];tag.value['Name']=nbt.Tag(nbt.STRING,'keep')
        doc.set_entity((1,2,3),tag)
        doc.selection=Selection((0,0,0),(3,3,3));doc.set_biome('desert')
        prior=(dict(doc.edits),dict(doc.entity_edits),dict(doc.biome_edits))
        self.select(doc,(0,0));doc.delete_chunks()
        self.assertFalse(doc.edits);self.assertFalse(doc.entity_edits);self.assertFalse(doc.biome_edits)
        doc.undo();self.assertEqual((doc.edits,doc.entity_edits,doc.biome_edits),prior)
        self.assertEqual(doc.get(4,2,3),Block('gold_block'))
        self.assertEqual(self.export(doc).get_biome(0,0,0),'minecraft:desert')

    def test_empty_java_chunk_edit_export_undo_both_layouts(self):
        for version in (1451,2230,4189):
            with self.subTest(version=version):
                doc=Document(open_world(java_world(self.path/str(version),version)))
                self.select(doc,(2,0));self.assertEqual(doc.create_chunks(),1)
                self.assertIn((2,0),doc.chunk_positions());self.assertEqual(doc.get(33,3,2),AIR)
                doc.apply('glass',[((33,3,2),Block('glass'))])
                self.assertEqual(self.export(doc,str(version)+'-out').get_block(33,3,2),Block('glass'))
                doc.undo();doc.undo();self.assertNotIn((2,0),doc.chunk_positions())
                doc.redo();doc.redo();self.assertEqual(doc.get(33,3,2),Block('glass'))

    def test_create_existing_chunks_is_noop(self):
        doc=Document(open_world(java_world(self.path/'java')));self.select(doc,(0,0))
        self.assertEqual(doc.create_chunks(),0);self.assertFalse(doc.undo_stack)

    def test_java_prune_respects_disjoint_selection(self):
        doc=Document(open_world(java_world(self.path/'java')));self.select(doc,(-1,-1),(32,0))
        self.assertEqual(doc.delete_chunks(prune=True),3)
        self.assertEqual(doc.chunk_positions(),{(-1,-1),(32,0)})
        self.assertEqual(self.export(doc).chunk_positions('overworld'),doc.chunk_positions())
        doc.undo();self.assertEqual(len(doc.chunk_positions()),5)

    def test_import_java_chunks_retains_auxiliary_and_source_metadata(self):
        source=java_auxiliary(java_world(self.path/'source'))
        region=Region.read(source/'region/r.0.0.mca');root=nbt.loads(region.get(0,0))[1]
        root.value['CustomUnknown']=nbt.Tag(nbt.STRING,'imported metadata');region.put(0,0,nbt.dumps(root));region.write()
        doc=Document(open_world(java_world(self.path/'target')));self.select(doc,(0,0))
        imported=open_world(source);before=hashes(source)
        self.assertEqual(doc.import_chunks(imported),1)
        out=self.export(doc)
        self.assertEqual(nbt.get(nbt.loads(Region.read(out.path/'region/r.0.0.mca').get(0,0))[1],'CustomUnknown'),'imported metadata')
        for category in ('entities','poi'):
            self.assertEqual(Region.read(out.path/category/'r.0.0.mca').get(0,0),Region.read(source/category/'r.0.0.mca').get(0,0))
        self.assertEqual(hashes(source),before)

    def test_reimport_identical_chunk_clears_later_edits_and_undo_restores(self):
        source=open_world(java_world(self.path/'source'));doc=Document(open_world(java_world(self.path/'target')))
        self.select(doc,(0,0));doc.import_chunks(source)
        doc.apply('gold',[((3,2,1),Block('gold_block'))])
        self.assertEqual(doc.import_chunks(source),1);self.assertEqual(doc.get(3,2,1),Block('stone'))
        doc.undo();self.assertEqual(doc.get(3,2,1),Block('gold_block'))

    def test_cross_edition_or_version_import_refused_atomically(self):
        doc=Document(open_world(java_world(self.path/'java')));self.select(doc,(0,0))
        for world in (open_world(java_world(self.path/'old',2230)),open_world(bedrock_world(self.path/'bedrock'))):
            with self.assertRaises(ValueError):doc.import_chunks(world)
        self.assertFalse(doc.chunk_edits);self.assertFalse(doc.undo_stack)

    def test_chunk_projects_preserve_imported_and_deleted_states_and_selection(self):
        doc=Document(open_world(java_world(self.path/'java')))
        self.select(doc,(0,0));doc.delete_chunks();self.select(doc,(2,0));doc.create_chunks()
        doc.apply('glass',[((33,3,2),Block('glass'))]);self.select(doc,(2,0),(32,0))
        file=self.path/'chunks.facet';save_project(doc,file);loaded=load_project(file)
        self.assertEqual(loaded.chunk_edits,doc.chunk_edits);self.assertEqual(loaded.selection,doc.selection)
        self.assertEqual(self.export(loaded).get_block(33,3,2),Block('glass'))

    def test_invalid_chunk_snapshot_is_rejected_without_losing_edits(self):
        doc=Document(open_world(java_world(self.path/'java')))
        doc.apply('gold',[((1,2,3),Block('gold_block'))]);before=dict(doc.edits)
        malformed=ChunkState('replace',((b'region',b'\x03invalid NBT'),))
        with self.assertRaises(ValueError):doc._chunk_transaction('invalid',[((0,0),malformed)])
        self.assertEqual(doc.edits,before);self.assertFalse(doc.chunk_edits)

    def test_chunk_export_failure_leaves_no_destination(self):
        doc=Document(open_world(java_world(self.path/'java')));self.select(doc,(0,0));doc.delete_chunks()
        before=hashes(doc.world.path)
        with mock.patch('facetedit.chunks.write_java_chunks',side_effect=OSError('disk full')),self.assertRaises(OSError):self.export(doc)
        self.assertFalse((self.path/'out').exists());self.assertEqual(hashes(doc.world.path),before)

    def test_bedrock_delete_prunes_unshared_actor_and_keeps_shared_actor(self):
        source=bedrock_metadata(bedrock_world(self.path/'bedrock'),actors=True);before=hashes(source)
        doc=Document(open_world(source));self.select(doc,(0,0));doc.delete_chunks();out=self.export(doc)
        a,b=struct.pack('<q',1),struct.pack('<q',2)
        self.assertNotIn(b'actorprefix'+a,out.values);self.assertIn(b'actorprefix'+b,out.values)
        self.assertNotIn(b'digp'+b'\0'*8,out.values)
        self.assertNotIn(b'\0'*8+b'?',out.values);self.assertNotIn(b'\0'*8+b'2',out.values)
        self.assertEqual(out.values[b'unrelated-key'],b'keep this payload')
        self.assertEqual(out.chunk_positions('overworld'),{(-1,-1)})
        self.assertEqual(hashes(source),before)
        doc.undo();self.assertIn(b'actorprefix'+a,doc.view_world.values)

    def test_bedrock_prune_all_shared_actor_references_removes_actor(self):
        doc=Document(open_world(bedrock_metadata(bedrock_world(self.path/'bedrock'),actors=True)))
        self.select(doc,(100,100));self.assertEqual(doc.delete_chunks(prune=True),2)
        self.assertFalse(any(k.startswith(b'actorprefix') for k in doc.view_world.values))
        doc.undo();self.assertEqual(len(doc.chunk_positions()),2)

    def test_empty_bedrock_chunk_template_edit_and_export(self):
        doc=Document(open_world(bedrock_metadata(bedrock_world(self.path/'bedrock'))))
        self.select(doc,(1,0));self.assertEqual(doc.create_chunks(),1)
        doc.apply('glass',[((17,-50,2),Block('glass'))]);out=self.export(doc)
        self.assertEqual(out.get_block(17,-50,2),Block('glass'))
        self.assertTrue(out.values[struct.pack('<ii',1,0)+b'+'].endswith(b'opaque biome palette from same dimension'))
        doc.undo();doc.undo();self.assertNotIn((1,0),doc.chunk_positions())

    def test_empty_bedrock_without_biome_template_refused(self):
        doc=Document(open_world(bedrock_world(self.path/'bedrock')));self.select(doc,(1,0))
        with self.assertRaisesRegex(ValueError,'biome data'):doc.create_chunks()
        self.assertFalse(doc.chunk_edits)

    def test_empty_bedrock_requires_known_game_version_and_valid_metadata(self):
        source=bedrock_metadata(bedrock_world(self.path/'unknown-version'))
        file=source/'level.dat';root=nbt.loads(file.read_bytes()[8:],little=True)[1]
        del root.value['lastOpenedWithVersion']
        raw=nbt.dumps(root,little=True);file.write_bytes(struct.pack('<II',10,len(raw))+raw)
        doc=Document(open_world(source));self.select(doc,(1,0))
        with self.assertRaisesRegex(ValueError,'lastOpenedWithVersion'):doc.create_chunks()
        self.assertFalse(doc.chunk_edits)
        root.value['lastOpenedWithVersion']=nbt.Tag(nbt.LIST,nbt.ListValue(nbt.STRING,['1','21','50']))
        raw=nbt.dumps(root,little=True);file.write_bytes(struct.pack('<II',10,len(raw))+raw)
        with self.assertRaisesRegex(ValueError,'lastOpenedWithVersion'):open_world(source)

    def test_bedrock_import_retains_actor_payload_and_chunk_metadata(self):
        source=open_world(bedrock_metadata(bedrock_world(self.path/'source'),actors=True))
        doc=Document(open_world(bedrock_metadata(bedrock_world(self.path/'target'))));self.select(doc,(0,0))
        self.assertEqual(doc.import_chunks(source),1);out=self.export(doc)
        self.assertEqual(out.values[b'digp'+b'\0'*8],source.values[b'digp'+b'\0'*8])
        self.assertEqual(out.values[b'\0'*8+b'?'],b'unknown per-chunk record')
        for key in source.values:
            if key.startswith(b'actorprefix'):self.assertEqual(out.values[key],source.values[key])

    def test_bedrock_actor_collision_refused_atomically(self):
        source=open_world(bedrock_metadata(bedrock_world(self.path/'source'),actors=True))
        source.values[b'actorprefix'+struct.pack('<q',2)]=b'conflicting actor'
        doc=Document(open_world(bedrock_metadata(bedrock_world(self.path/'target'),actors=True)))
        self.select(doc,(0,0))
        with self.assertRaisesRegex(ValueError,'collides'):doc.import_chunks(source)
        self.assertFalse(doc.chunk_edits);self.assertFalse(doc.undo_stack)

    def test_bedrock_game_versions_must_match(self):
        source=open_world(bedrock_metadata(bedrock_world(self.path/'source'),version=(1,20,0)))
        doc=Document(open_world(bedrock_metadata(bedrock_world(self.path/'target'))));self.select(doc,(0,0))
        with self.assertRaisesRegex(ValueError,'lastOpenedWithVersion'):doc.import_chunks(source)

    def test_bedrock_chunk_project_and_mcworld_reopen(self):
        from facetedit.archives import export_mcworld,extract_world
        doc=Document(open_world(bedrock_metadata(bedrock_world(self.path/'bedrock'),actors=True)))
        self.select(doc,(0,0));doc.delete_chunks()
        file=self.path/'bedrock.facet';save_project(doc,file);loaded=load_project(file)
        archive=self.path/'result.mcworld';export_mcworld(loaded.world,archive,loaded.edits,**loaded.export_metadata())
        reopened=open_world(extract_world(archive,self.path/'extracted'))
        self.assertEqual(reopened.chunk_positions('overworld'),{(-1,-1)})

    def test_pending_budget_failure_is_atomic(self):
        doc=Document(open_world(java_world(self.path/'java')));self.select(doc,(2,0))
        with mock.patch('facetedit.model.MAX_PAYLOAD',1),self.assertRaises(ValueError):doc.create_chunks()
        self.assertFalse(doc.chunk_edits);self.assertFalse(doc.undo_stack)

    def test_history_budget_failure_preserves_all_pending_edits(self):
        doc=Document(open_world(java_world(self.path/'java')))
        doc.apply('gold',[((1,4,3),Block('gold_block')),((2,4,3),Block('gold_block'))])
        self.select(doc,(0,0));before=dict(doc.edits);history=list(doc.undo_stack)
        with mock.patch('facetedit.model.MAX_HISTORY',2),self.assertRaisesRegex(ValueError,'undo budget'):doc.delete_chunks()
        self.assertEqual(doc.edits,before);self.assertEqual(doc.undo_stack,history);self.assertFalse(doc.chunk_edits)

    def test_java_external_chunks_edit_import_delete_and_preserve_neighbor(self):
        import zlib
        from tests.test_region_extensions import stream
        source=java_auxiliary(java_world(self.path/'external'))
        for category in ('region','entities','poi'):
            region=Region.read(source/category/'r.0.0.mca')
            raw=region.get(0,0)
            region.put_payload(0,0,b'\x84',stream(raw))
            raw_neighbor=region.get(1,0)
            region.put_payload(1,0,b'\x82',zlib.compress(raw_neighbor));region.write()
        before=hashes(source)
        doc=Document(open_world(source));self.select(doc,(0,0));self.assertEqual(doc.get(1,4,3),Block('stone'))
        doc.apply('gold',[((1,4,3),Block('gold_block'))]);edited=self.export(doc,'external-edited')
        self.assertEqual(edited.get_block(1,4,3),Block('gold_block'))
        self.assertFalse((edited.path/'region/c.0.0.mcc').exists())
        for category in ('region','entities','poi'):
            self.assertEqual((edited.path/category/'c.1.0.mcc').read_bytes(),(source/category/'c.1.0.mcc').read_bytes())
        target=Document(open_world(java_world(self.path/'target')));self.select(target,(0,0));target.import_chunks(open_world(source))
        out=self.export(target,'imported-external')
        for category in ('region','entities','poi'):
            self.assertEqual((out.path/category/'c.0.0.mcc').read_bytes(),(source/category/'c.0.0.mcc').read_bytes())
        self.assertEqual(out.get_block(1,4,3),Block('stone'))
        doc.delete_chunks();deleted=self.export(doc,'external-deleted')
        for category in ('region','entities','poi'):self.assertFalse((deleted.path/category/'c.0.0.mcc').exists())
        self.assertEqual(hashes(source),before)

    def test_java_chunk_dimension_isolation(self):
        source=java_world(self.path/'dimensions')
        shutil.copytree(source/'region',source/'DIM-1/region')
        doc=Document(open_world(source));doc.dimension='the_nether';self.select(doc,(0,0));doc.delete_chunks()
        out=self.export(doc)
        self.assertIn((0,0),out.chunk_positions('overworld'));self.assertNotIn((0,0),out.chunk_positions('the_nether'))
        doc.undo();self.assertIn((0,0),doc.chunk_positions())

    def test_bedrock_chunk_dimension_isolation(self):
        source=bedrock_metadata(bedrock_world(self.path/'bedrock-dimensions'))
        values=load_database(source/'db')
        values[struct.pack('<iii',0,0,1)+b'/\x00']=values[b'\0'*8+b'/\x00']
        values[struct.pack('<iii',0,0,1)+b',']=b'\x29'
        shutil.rmtree(source/'db');write_database(source/'db',values)
        doc=Document(open_world(source));doc.dimension='the_nether';self.select(doc,(0,0));doc.delete_chunks()
        out=self.export(doc)
        self.assertIn((0,0),out.chunk_positions('overworld'));self.assertNotIn((0,0),out.chunk_positions('the_nether'))

    def test_chunk_project_rejects_bad_coordinates_and_duplicate_records(self):
        doc=Document(open_world(java_world(self.path/'java')));self.select(doc,(0,0));doc.delete_chunks()
        file=self.path/'bad.facet';save_project(doc,file);data=json.loads(file.read_text())
        data['chunks'][0][1]=True;file.write_text(json.dumps(data))
        with self.assertRaises(ValueError):load_project(file)
        with self.assertRaises(ValueError):ChunkState('replace',((b'x',b'1'),(b'x',b'2')))
