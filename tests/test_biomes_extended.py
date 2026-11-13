from pathlib import Path
import shutil,struct,tempfile,unittest
from facetedit import nbt
from facetedit.biomes import BedrockBiomes,encode_section,identifier,name
from facetedit.leveldb import load_database,write_database
from facetedit.model import Document,Selection
from facetedit.region import Region
from facetedit.structures import save_project,load_project
from facetedit.world import open_world
from tests.fixtures import java_world,bedrock_world
from tests.test_workflows import hashes


class BiomeCodecTests(unittest.TestCase):
    def test_singleton_and_inherited_golden_bytes(self):
        height=bytes(range(256))*2
        raw=height+b'\x01\x02\0\0\0'+b'\xff'*24
        biome=BedrockBiomes(raw,-64)
        self.assertEqual(biome.get(3,-51,7),2);self.assertEqual(biome.get(3,310,7),2)
        changed=biome.edited({(3,-51,7):1});loaded=BedrockBiomes(changed,-64)
        self.assertEqual(loaded.get(3,-51,7),1);self.assertEqual(loaded.get(3,-50,7),2)
        self.assertEqual(loaded.get(3,-35,7),2);self.assertEqual(changed[:512],height)

    def test_all_palette_widths_preserve_full_4096_cells(self):
        for count in (1,2,3,5,9,17,33,65,257):
            cells=[i%count for i in range(4096)];raw=b'\0'*512+encode_section(cells)
            self.assertEqual(BedrockBiomes(raw,0).sections[0],tuple(cells))

    def test_known_packed_bit_order_xzy(self):
        # width 1: index x=0,z=0,y=1 is bit 1 of the first little-endian word.
        raw=b'\0'*512+b'\x03'+struct.pack('<128I',2,*([0]*127))+struct.pack('<3I',2,1,2)
        decoded=BedrockBiomes(raw,0)
        self.assertEqual(decoded.get(0,1,0),2);self.assertEqual(decoded.get(1,0,0),1)
        self.assertEqual(decoded.get(0,0,1),1)

    def test_editing_two_adjacent_inherited_sections_keeps_third_unchanged(self):
        original=BedrockBiomes(b'\0'*512+b'\x01\x01\0\0\0'+b'\xff'*24,0)
        after=BedrockBiomes(original.edited({(2,3,4):2,(2,19,4):4}),0)
        self.assertEqual([after.get(2,y,4) for y in (3,19,35)],[2,4,1])
        self.assertEqual(after.raw[3:],original.raw[3:])

    def test_truncation_invalid_width_and_index_refused(self):
        for raw in (b'\0'*512,b'\0'*512+b'\x01\0',b'\0'*512+b'\x13'):
            with self.assertRaises(ValueError):BedrockBiomes(raw,0)
        raw=b'\0'*512+b'\x03'+struct.pack('<128I',1,*([0]*127))+struct.pack('<2I',1,1)
        with self.assertRaisesRegex(ValueError,'index'):BedrockBiomes(raw,0)
        with self.assertRaises(ValueError):BedrockBiomes(b'\0'*512+b'\xff',0).get(0,0,0)

    def test_edition_ids_and_unknown_identifiers_are_not_conflated(self):
        self.assertEqual(identifier('warm_ocean'),44);self.assertEqual(identifier('warm_ocean','Bedrock'),40)
        self.assertEqual(name(1234),'numeric:1234');self.assertEqual(identifier('numeric:1234'),1234)
        with self.assertRaises(ValueError):identifier('not_a_biome')
        with self.assertRaises(ValueError):identifier('numeric:-1')


class BiomeWorldTests(unittest.TestCase):
    def setUp(self):self.temp=tempfile.TemporaryDirectory();self.path=Path(self.temp.name)
    def tearDown(self):self.temp.cleanup()

    def java(self,version,count,kind=nbt.INT_ARRAY):
        path=java_world(self.path/str(version),version);file=path/'region/r.0.0.mca';region=Region.read(file)
        title,root=nbt.loads(region.get(0,0));level=root.value.get('Level',root)
        level.value['Biomes']=nbt.Tag(kind,bytes([1]*count) if kind==nbt.BYTE_ARRAY else [1]*count)
        region.put(0,0,nbt.dumps(root,title));region.write();return Document(open_world(path))

    def bedrock(self,modern):
        path=bedrock_world(self.path/('modern' if modern else 'old'));values=load_database(path/'db')
        height=bytes(range(256))*2
        values[b'\0'*8+(b'+' if modern else b'-')]=height+(b'\x01\x01\0\0\0'+b'\xff'*24 if modern else bytes([1]*256))
        shutil.rmtree(path/'db');write_database(path/'db',values)
        return Document(open_world(path))

    def export(self,doc,label):
        doc.world.export(self.path/label,doc.edits,**doc.export_metadata());return open_world(self.path/label)

    def test_java_2d_int_array_column_persistence(self):
        doc=self.java(1451,256);before=hashes(doc.world.path);doc.selection=Selection((1,2,3),(1,5,3))
        self.assertEqual(doc.set_biome('desert'),1);self.assertEqual(doc.get_biome(1,99,3),'minecraft:desert')
        self.assertEqual(doc.get_biome(3,99,1),'minecraft:plains')
        self.assertEqual(self.export(doc,'out').get_biome(1,99,3),'minecraft:desert');self.assertEqual(hashes(doc.world.path),before)
        doc.undo();self.assertEqual(doc.get_biome(1,99,3),'minecraft:plains')

    def test_java_byte_array_and_unknown_numeric_ids(self):
        doc=self.java(1451,256,nbt.BYTE_ARRAY);doc.selection=Selection((2,0,1),(2,0,1))
        doc.set_biome('numeric:200');self.assertEqual(self.export(doc,'out').get_biome(2,4,1),'numeric:200')
        with self.assertRaises(ValueError):doc.set_biome('numeric:300')

    def test_java_3d_numeric_uses_quart_cells(self):
        doc=self.java(2230,1024);doc.selection=Selection((1,6,2),(1,6,2));doc.set_biome('desert')
        self.assertEqual(doc.get_biome(3,7,3),'minecraft:desert');self.assertEqual(doc.get_biome(3,8,3),'minecraft:plains')
        self.assertEqual(self.export(doc,'out').get_biome(3,7,3),'minecraft:desert')

    def test_java_column_mode_covers_vertical_cells(self):
        doc=self.java(2230,1024);doc.selection=Selection((1,4,2),(1,4,2))
        self.assertEqual(doc.set_biome('desert','column'),64);self.assertEqual(doc.get_biome(1,252,2),'minecraft:desert')

    def test_bedrock_2d_preserves_heightmap_and_neighbor(self):
        doc=self.bedrock(False);doc.selection=Selection((1,2,3),(1,2,3));doc.set_biome('desert');out=self.export(doc,'out')
        self.assertEqual(out.get_biome(1,80,3),'minecraft:desert');self.assertEqual(out.get_biome(3,80,1),'minecraft:plains')
        self.assertEqual(out.values[b'\0'*8+b'-'][:512],bytes(range(256))*2)

    def test_bedrock_3d_edits_one_block_and_preserves_inherited_neighbors(self):
        doc=self.bedrock(True);doc.selection=Selection((1,-50,3),(1,-50,3));doc.set_biome('desert');out=self.export(doc,'out')
        self.assertEqual(out.get_biome(1,-50,3),'minecraft:desert');self.assertEqual(out.get_biome(1,-49,3),'minecraft:plains')
        self.assertEqual(out.get_biome(1,-34,3),'minecraft:plains')
        doc.undo();self.assertEqual(doc.get_biome(1,-50,3),'minecraft:plains');doc.redo()
        file=self.path/'world.facet';save_project(doc,file);self.assertEqual(load_project(file).get_biome(1,-50,3),'minecraft:desert')

    def test_bedrock_column_edits_all_valid_heights_only(self):
        doc=self.bedrock(True);doc.selection=Selection((1,-50,3),(1,-50,3));self.assertEqual(doc.set_biome('desert','column'),384)
        out=self.export(doc,'out');self.assertEqual(out.get_biome(1,319,3),'minecraft:desert')
        self.assertEqual(out.get_biome(2,319,3),'minecraft:plains')
