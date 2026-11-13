import base64
import json
from pathlib import Path
import stat
import tempfile
import unittest
import zipfile
from unittest import mock

from facetedit import nbt
from facetedit.archives import extract_world,export_mcworld
from facetedit.blocks import AIR,Block
from facetedit.formats import decode_java_biomes,encode_java_biomes
from facetedit.model import Clipboard,Document,Selection
from facetedit.nbt_edit import to_json,from_json
from facetedit.schematic import load_schematic,save_schematic
from facetedit.settings import Settings
from facetedit.structures import load_project,save_project
from facetedit.world import SampleWorld,open_world,file_hash
from tests.fixtures import java_world,bedrock_world


class ExpansionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.path = Path(self.temp.name)

    def tearDown(self):
        self.temp.cleanup()

    def export(self,doc,name="out"):
        target = self.path/name
        doc.world.export(target,doc.edits,entity_edits=doc.entity_edits,biome_edits=doc.biome_edits)
        return open_world(target)

    def test_dark_default_and_logo_packaged_resource(self):
        settings = Settings(self.path/'new.json')
        self.assertEqual(settings.data['theme'],'midnight')
        from importlib import resources
        self.assertTrue(resources.files('facetedit').joinpath('assets/logo-64.png').read_bytes().startswith(b'\x89PNG'))

    def test_luma_project_migration(self):
        doc=Document(SampleWorld())
        doc.apply('one',[((1,30,1),Block('glass'))])
        path=self.path/'old.luma'
        save_project(doc,path)
        data=json.loads(path.read_text());data['format']='luma-project';data['version']=1
        data.pop('biomes');data.pop('block_entities')
        path.write_text(json.dumps(data))
        self.assertEqual(load_project(path).edits,doc.edits)

    def test_legacy_preferences_migrate_without_overwrite(self):
        old=self.path/'Luma/settings.json';old.parent.mkdir()
        old.write_text('{"version":1,"radius":8,"grid":false,"recent":[]}')
        target=self.path/'FacetEdit/settings.json'
        with mock.patch('facetedit.settings.config_path',return_value=target):
            settings=Settings()
        self.assertEqual(settings.data['radius'],8)
        settings.save()
        self.assertEqual(json.loads(old.read_text())['radius'],8)
        self.assertEqual(json.loads(target.read_text())['theme'],'midnight')

    def test_biome_palette_singleton_and_growth(self):
        for size in (1,2,3,9,33,64):
            with self.subTest(size=size):
                values=['minecraft:test_'+str(i%size) for i in range(64)]
                section={};encode_java_biomes(section,values)
                self.assertEqual(decode_java_biomes(section),values)

    def test_biome_cell_alignment_undo_export_reopen(self):
        doc=Document(open_world(java_world(self.path/'java')))
        doc.selection=Selection((1,1,1),(4,4,4))
        self.assertEqual(doc.set_biome('minecraft:desert'),8)
        self.assertEqual(doc.get_biome(2,2,2),'minecraft:desert')
        doc.undo();self.assertEqual(doc.get_biome(2,2,2),'minecraft:plains')
        doc.redo()
        output=self.export(doc)
        self.assertEqual(output.get_biome(2,2,2),'minecraft:desert')
        self.assertEqual(output.get_biome(8,0,0),'minecraft:plains')
        self.assertEqual(output.get_block(2,2,2),Block('stone'))

    def test_negative_y_biomes(self):
        doc=Document(open_world(java_world(self.path/'java')))
        doc.selection=Selection((0,-35,0),(2,-34,2))
        doc.set_biome('minecraft:lush_caves')
        self.assertEqual(self.export(doc).get_biome(1,-35,1),'minecraft:lush_caves')

    def test_older_and_bedrock_biomes_refused(self):
        for kind,source in [('old',java_world(self.path/'old',2230)),('bedrock',bedrock_world(self.path/'bedrock'))]:
            with self.subTest(kind=kind):
                doc=Document(open_world(source));doc.selection=Selection((0,0,0),(1,1,1))
                with self.assertRaises(ValueError):doc.set_biome('desert')
                self.assertFalse(doc.biome_edits)

    def test_entity_nbt_java_and_bedrock_export(self):
        for name,maker in (('java',java_world),('bedrock',bedrock_world)):
            with self.subTest(edition=name):
                source=maker(self.path/name)
                signature={str(f.relative_to(source)):file_hash(f) for f in source.rglob('*') if f.is_file()}
                doc=Document(open_world(source))
                original=doc.get_entity(1,2,3)
                _,tag=nbt.loads(original)
                tag.value['CustomName']=nbt.Tag(nbt.STRING,'{"text":"Facet vault"}')
                tag.value['Items']=nbt.Tag(nbt.LIST,nbt.ListValue(nbt.COMPOUND,[{'Slot':nbt.Tag(nbt.BYTE,0),'Count':nbt.Tag(nbt.BYTE,7),'id':nbt.Tag(nbt.STRING,'minecraft:diamond')}]))
                doc.set_entity((1,2,3),tag)
                changed=doc.get_entity(1,2,3)
                self.assertNotEqual(original,changed)
                doc.undo();self.assertEqual(doc.get_entity(1,2,3),original)
                doc.redo()
                out=self.export(doc,name+'-out')
                self.assertEqual(out.get_block_entity(1,2,3),changed)
                self.assertEqual(signature,{str(f.relative_to(source)):file_hash(f) for f in source.rglob('*') if f.is_file()})

    def test_replace_block_removes_edited_entity_and_undo_restores_it(self):
        doc=Document(open_world(java_world(self.path/'java')))
        _,tag=nbt.loads(doc.get_entity(1,2,3));tag.value['Test']=nbt.Tag(nbt.INT,42)
        doc.set_entity((1,2,3),tag)
        updated=doc.get_entity(1,2,3)
        doc.apply('replace',[((1,2,3),Block('glass'))])
        self.assertIsNone(doc.get_entity(1,2,3))
        self.assertIsNone(self.export(doc,'deleted').get_block_entity(1,2,3))
        doc.undo()
        self.assertEqual(doc.get_entity(1,2,3),updated)
        self.assertEqual(self.export(doc,'restored').get_block_entity(1,2,3),updated)

    def test_entity_coordinate_validation(self):
        doc=Document(open_world(java_world(self.path/'java')))
        _,tag=nbt.loads(doc.get_entity(1,2,3));tag.value['x']=nbt.Tag(nbt.INT,99)
        with self.assertRaises(ValueError):doc.set_entity((1,2,3),tag)
        self.assertFalse(doc.entity_edits)

    def test_metadata_project_roundtrip(self):
        doc=Document(open_world(java_world(self.path/'java')))
        _,tag=nbt.loads(doc.get_entity(1,2,3));tag.value['Test']=nbt.Tag(nbt.LONG,2**50)
        doc.set_entity((1,2,3),tag)
        doc.selection=Selection((0,0,0),(3,3,3));doc.set_biome('desert')
        path=self.path/'metadata.facet';save_project(doc,path)
        loaded=load_project(path)
        self.assertEqual(loaded.entity_edits,doc.entity_edits)
        self.assertEqual(loaded.biome_edits,doc.biome_edits)
        self.assertEqual(self.export(loaded).get_biome(0,0,0),'minecraft:desert')

    def test_typed_nbt_json_preserves_arrays_lists_and_unicode(self):
        tag=nbt.compound(id=nbt.Tag(nbt.STRING,'minecraft:chest'),b=nbt.Tag(nbt.BYTE,-1),n=nbt.Tag(nbt.LONG,2**60),text=nbt.Tag(nbt.STRING,'世界 🪷'),raw=nbt.Tag(nbt.BYTE_ARRAY,b'\x00\xff'),ints=nbt.Tag(nbt.INT_ARRAY,[1,-2]),longs=nbt.Tag(nbt.LONG_ARRAY,[2**60]),list=nbt.Tag(nbt.LIST,nbt.ListValue(nbt.COMPOUND,[{'x':nbt.Tag(nbt.INT,2)}])),empty=nbt.Tag(nbt.LIST,nbt.ListValue(nbt.END,[])))
        self.assertEqual(from_json(to_json(tag)),tag)

    def test_typed_nbt_rejects_invalid_types_and_ranges(self):
        for text in ('{"type":"int","value":true}','{"type":"byte","value":999}','{"type":"string","value":1}','{"type":"list","value":{"element":"end","items":[1]}}'):
            with self.subTest(text=text),self.assertRaises((ValueError,TypeError,OverflowError)):
                from_json(text)

    def test_clone_captures_source_before_overlapping_writes(self):
        doc=Document(SampleWorld());doc.selection=Selection((0,40,0),(1,40,0))
        doc.apply('source',[((0,40,0),Block('stone')),((1,40,0),Block('glass'))])
        self.assertEqual(doc.clone((1,0,0),2),3)
        self.assertEqual(doc.get(2,40,0),Block('stone'))
        self.assertEqual(doc.get(3,40,0),Block('glass'))
        doc.undo();self.assertEqual(doc.get(1,40,0),Block('glass'));self.assertEqual(doc.get(3,40,0),AIR)

    def test_selection_nudge_and_shrink(self):
        doc=Document(SampleWorld());doc.selection=Selection((0,30,0),(2,32,2))
        doc.nudge_selection((3,0,-1));self.assertEqual(doc.selection.minimum,(3,30,-1))
        doc.expand_selection(-1);self.assertEqual(doc.selection.size,(1,1,1))
        with self.assertRaises(ValueError):doc.expand_selection(-1)

    def test_waterlog_only_supported_states(self):
        doc=Document(SampleWorld());doc.selection=Selection((0,30,0),(1,30,0))
        doc.apply('setup',[((0,30,0),Block.parse('oak_stairs[facing=north,waterlogged=false]')),((1,30,0),Block('stone'))])
        self.assertEqual(doc.waterlog(),1)
        self.assertIn(('waterlogged','true'),doc.get(0,30,0).properties)
        self.assertEqual(doc.get(1,30,0),Block('stone'))
        doc.undo();self.assertIn(('waterlogged','false'),doc.get(0,30,0).properties)

    def test_sponge_v2_v3_roundtrip(self):
        blocks={(x,y,z):Block('stone' if x%2 else 'glass') for x in range(3) for y in range(2) for z in range(4)}
        clip=Clipboard((3,2,4),blocks)
        for version in (2,3):
            with self.subTest(version=version):
                path=self.path/f'v{version}.schem';save_schematic(clip,path,version)
                self.assertEqual(load_schematic(path),clip)

    def test_sponge_v3_spec_layout_and_index_order(self):
        clip=Clipboard((2,1,2),{(0,0,0):Block('stone'),(1,0,0):Block('glass'),(0,0,1):Block('sand'),(1,0,1):Block('gold_block')})
        path=self.path/'layout.schem';save_schematic(clip,path)
        name,root=nbt.loads(path.read_bytes(),compressed=True)
        self.assertEqual(name,'');self.assertEqual(nbt.get(root.value['Schematic'],'Version'),3)
        self.assertEqual(nbt.get(root.value['Schematic'].value['Blocks'],'Data'),b'\x00\x01\x02\x03')

    def test_schematic_offset_applies_to_paste(self):
        clip=Clipboard((1,1,1),{(0,0,0):Block('glass')},offset=(3,2,-1))
        path=self.path/'offset.schem';save_schematic(clip,path)
        doc=Document(SampleWorld());doc.clipboard=load_schematic(path)
        doc.paste((0,30,0));self.assertEqual(doc.get(3,32,-1),Block('glass'))
        with self.assertRaises(ValueError):doc.paste((0,30,0),turns=1)

    def test_schematic_unknown_palette_index_and_entity_refused(self):
        clip=Clipboard((1,1,1),{(0,0,0):Block('stone')})
        path=self.path/'bad.schem';save_schematic(clip,path)
        _,root=nbt.loads(path.read_bytes(),compressed=True)
        root.value['Schematic'].value['Blocks'].value['Data']=nbt.Tag(nbt.BYTE_ARRAY,b'\x05')
        path.write_bytes(nbt.dumps(root,compressed=True))
        with self.assertRaises(ValueError):load_schematic(path)
        save_schematic(clip,path);_,root=nbt.loads(path.read_bytes(),compressed=True)
        root.value['Schematic'].value['Entities']=nbt.Tag(nbt.LIST,nbt.ListValue(nbt.COMPOUND,[{}]))
        path.write_bytes(nbt.dumps(root,compressed=True))
        with self.assertRaises(ValueError):load_schematic(path)

    def test_mcworld_export_import_reopen(self):
        doc=Document(open_world(bedrock_world(self.path/'bedrock')))
        doc.apply('edit',[((1,2,3),Block('gold_block'))])
        archive=self.path/'edited.mcworld'
        export_mcworld(doc.world,archive,doc.edits,entity_edits=doc.entity_edits)
        world=open_world(extract_world(archive,self.path/'imported'))
        self.assertEqual(world.get_block(1,2,3),Block('gold_block'))
        self.assertIsNone(world.get_block_entity(1,2,3))
        self.assertEqual(world.values[b'~local_player'],b'opaque player data')
        with self.assertRaises(FileExistsError):export_mcworld(doc.world,archive,{})

    def test_mcworld_wrapped_folder_supported(self):
        source=bedrock_world(self.path/'source');archive=self.path/'wrapped.mcworld'
        with zipfile.ZipFile(archive,'w') as z:
            for file in source.rglob('*'):
                if file.is_file():z.write(file,'wrapped/'+file.relative_to(source).as_posix())
        self.assertEqual(open_world(extract_world(archive,self.path/'unwrapped')).name,'Bedrock fixture')

    def test_mcworld_path_traversal_and_device_names_refused(self):
        for name in ('../evil','/absolute','C:/drive','db\\evil','CON','db/file.','db/aux.txt'):
            with self.subTest(name=name):
                archive=self.path/'bad.mcworld'
                with zipfile.ZipFile(archive,'w') as z:z.writestr(name,b'x')
                with self.assertRaises(ValueError):extract_world(archive,self.path/'out')
                self.assertFalse((self.path/'out').exists())

    def test_mcworld_symlink_and_case_conflict_refused(self):
        archive=self.path/'bad.mcworld'
        with zipfile.ZipFile(archive,'w') as z:
            link=zipfile.ZipInfo('level.dat');link.create_system=3;link.external_attr=(stat.S_IFLNK|0o777)<<16
            z.writestr(link,'/etc/passwd')
        with self.assertRaises(ValueError):extract_world(archive,self.path/'out')
        with zipfile.ZipFile(archive,'w') as z:
            z.writestr('level.dat',b'a');z.writestr('LEVEL.DAT',b'b')
        with self.assertRaises(ValueError):extract_world(archive,self.path/'out')

    def test_mcworld_size_limit_before_extraction(self):
        archive=self.path/'big.mcworld'
        with zipfile.ZipFile(archive,'w') as z:z.writestr('level.dat',b'a'*64)
        with mock.patch('facetedit.archives.MAX_ARCHIVE_BYTES',32),self.assertRaises(ValueError):
            extract_world(archive,self.path/'out')
        self.assertFalse(list(self.path.glob('.facetedit-import-*')))

    def test_mcworld_export_failure_never_publishes_partial(self):
        world=open_world(bedrock_world(self.path/'bedrock'))
        with mock.patch('facetedit.archives.os.link',side_effect=OSError('link failed')),self.assertRaises(OSError):
            export_mcworld(world,self.path/'out.mcworld',{})
        self.assertFalse((self.path/'out.mcworld').exists())
        self.assertFalse(list(self.path.glob('.facetedit-archive-*')))
