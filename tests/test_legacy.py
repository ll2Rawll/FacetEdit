from pathlib import Path
import tempfile,unittest
from facetedit import legacy,nbt
from facetedit.blocks import Block
from facetedit.model import Clipboard,Document,Selection
from facetedit.world import open_world
from facetedit.formats import decode_java_section,encode_java_section
from facetedit.legacy_schematic import load_legacy_schematic,save_legacy_schematic
from facetedit.structures import save_project,load_project
from facetedit.region import Region
from tests.fixtures import java_world
from tests.test_workflows import hashes


class LegacyTests(unittest.TestCase):
    def setUp(self):self.temp=tempfile.TemporaryDirectory();self.path=Path(self.temp.name)
    def tearDown(self):self.temp.cleanup()

    def test_all_numeric_ids_and_metadata_roundtrip(self):
        for number in range(4096):
            for data in range(16):self.assertEqual(legacy.identifier(legacy.block(number,data)),(number,data))

    def test_nibble_golden_bytes_and_odd_counts(self):
        self.assertEqual(legacy.pack_nibbles([1,2,15,0,8]),b'\x21\x0f\x08')
        self.assertEqual(legacy.nibbles(b'\x21\x0f\x08',5),[1,2,15,0,8])
        with self.assertRaises(nbt.FormatError):legacy.nibbles(b'\x00',3)

    def test_section_extended_id_layout_is_y_z_x(self):
        low=bytearray(4096);data=bytearray(2048);high=bytearray(2048)
        index=5+16*7+256*3;low[index]=0xbc;data[index//2]=0xd0 if index%2 else 0x0d;high[index//2]=0xa0 if index%2 else 0x0a
        section={'Blocks':nbt.Tag(nbt.BYTE_ARRAY,bytes(low)),'Data':nbt.Tag(nbt.BYTE_ARRAY,bytes(data)),'Add':nbt.Tag(nbt.BYTE_ARRAY,bytes(high))}
        decoded=decode_java_section(section,1343);self.assertEqual(decoded[index],legacy.block(0xabc,13))
        encoded={};encode_java_section(encoded,decoded,1343);self.assertEqual(encoded,section)

    def test_numeric_world_edit_biome_project_and_export(self):
        for version in (0,1343):
            root=java_world(self.path/str(version),version);before=hashes(root);doc=Document(open_world(root))
            self.assertEqual(doc.get(3,4,5),Block('stone'))
            doc.selection=Selection((1,4,3),(2,4,3));doc.fill(legacy.block(300,12));doc.set_biome('desert')
            project=self.path/f'{version}.facet';save_project(doc,project);doc=load_project(project)
            output=self.path/f'out-{version}';doc.world.export(output,doc.edits,**doc.export_metadata())
            world=open_world(output);self.assertEqual(world.get_block(1,4,3),legacy.block(300,12));self.assertEqual(world.get_biome(1,4,3),'minecraft:desert')
            self.assertEqual(world.get_block(4,4,3),Block('stone'));self.assertEqual(hashes(root),before)

    def test_legacy_chunk_creation_and_undo(self):
        doc=Document(open_world(java_world(self.path/'old',1343)));doc.selection=Selection((160,0,160),(175,15,175))
        doc.create_chunks();self.assertTrue(doc.get(160,0,160).air)
        doc.fill(Block('glass'));out=self.path/'copy';doc.world.export(out,doc.edits,**doc.export_metadata())
        self.assertEqual(open_world(out).get_block(160,0,160),Block('glass'));doc.undo();doc.undo();self.assertNotIn((10,10),doc.chunk_positions())

    def test_unknown_legacy_block_or_modern_states_fail_before_commit(self):
        doc=Document(open_world(java_world(self.path/'old',1343)));doc.selection=Selection((1,4,3),(2,4,3))
        for value in ('minecraft:cherry_planks','minecraft:oak_log[axis=x]','legacy:5000','legacy:1[legacy_data=16]'):
            with self.assertRaises(ValueError):doc.fill(Block.parse(value))
        self.assertFalse(doc.edits)

    def test_schematic_golden_layout_and_high_ids(self):
        root=nbt.compound(Materials=nbt.Tag(nbt.STRING,'Alpha'),Width=nbt.Tag(nbt.SHORT,2),Height=nbt.Tag(nbt.SHORT,2),Length=nbt.Tag(nbt.SHORT,1),Blocks=nbt.Tag(nbt.BYTE_ARRAY,b'\x01\x02\xab\xff'),Data=nbt.Tag(nbt.BYTE_ARRAY,b'\0\x03\x0c\x0f'),AddBlocks=nbt.Tag(nbt.BYTE_ARRAY,b'\0\xfa'))
        file=self.path/'golden.schematic';file.write_bytes(nbt.dumps(root,compressed=True));clip=load_legacy_schematic(file)
        self.assertEqual(clip.blocks[0,1,0],legacy.block(0xaab,12));self.assertEqual(clip.blocks[1,1,0],legacy.block(4095,15))
        out=self.path/'again.schematic';save_legacy_schematic(clip,out);self.assertEqual(load_legacy_schematic(out),clip)

    def test_schematic_block_nbt_offset_and_paste(self):
        data=nbt.dumps(nbt.compound(id=nbt.Tag(nbt.STRING,'Chest'),x=nbt.Tag(nbt.INT,0),y=nbt.Tag(nbt.INT,0),z=nbt.Tag(nbt.INT,0),CustomName=nbt.Tag(nbt.STRING,'Legacy inventory')))
        clip=Clipboard((1,1,1),{(0,0,0):legacy.block(54,2)},offset=(1,0,-1),entities={(0,0,0):data},data_version=1343)
        file=self.path/'chest.schematic';save_legacy_schematic(clip,file);loaded=load_legacy_schematic(file)
        self.assertEqual(loaded,clip);doc=Document(open_world(java_world(self.path/'world',1343)));doc.clipboard=loaded;doc.paste((1,4,3))
        tag=nbt.loads(doc.get_entity(2,4,2))[1];self.assertEqual(nbt.get(tag,'CustomName'),'Legacy inventory');self.assertEqual(nbt.get(tag,'x'),2)
        doc.undo();self.assertEqual(doc.get(2,4,2),Block('stone'))

    def test_schematic_refuses_malformed_or_lossy_inputs(self):
        modern=Clipboard((1,1,1),{(0,0,0):Block('stone')})
        with self.assertRaises(ValueError):save_legacy_schematic(modern,self.path/'bad.schematic')
        root=nbt.compound(Width=nbt.Tag(nbt.SHORT,1),Height=nbt.Tag(nbt.SHORT,1),Length=nbt.Tag(nbt.SHORT,1),Blocks=nbt.Tag(nbt.BYTE_ARRAY,b'\x01'),Data=nbt.Tag(nbt.BYTE_ARRAY,b'\xff'))
        file=self.path/'bad.schematic';file.write_bytes(nbt.dumps(root))
        with self.assertRaises(ValueError):load_legacy_schematic(file)

    def test_mcregion_is_not_misreported_as_an_empty_anvil_world(self):
        root=java_world(self.path/'old',0);(root/'region/r.0.0.mcr').write_bytes(b'\0'*8192)
        self.assertEqual(open_world(root).get_block(0,0,0),Block('stone'))
        for file in (root/'region').glob('*.mca'):file.unlink()
        with self.assertRaisesRegex(nbt.FormatError,'McRegion'):open_world(root)
