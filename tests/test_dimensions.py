import json,tempfile,unittest,zipfile
from pathlib import Path
from facetedit import nbt
from facetedit.world import open_world
from facetedit.model import Document,Selection
from facetedit.blocks import Block
from facetedit.region import Region
from tests.fixtures import java_world


class DimensionTests(unittest.TestCase):
    def setUp(self):self.temp=tempfile.TemporaryDirectory();self.path=Path(self.temp.name)
    def tearDown(self):self.temp.cleanup()
    def metadata(self,path,types,enabled=None):
        _,root=nbt.loads((path/'level.dat').read_bytes(),compressed=True);data=root.value['Data']
        data.value['WorldGenSettings']=nbt.compound(dimensions=nbt.Tag(nbt.COMPOUND,{key:nbt.compound(type=value) for key,value in types.items()}))
        if enabled is not None:data.value['DataPacks']=nbt.compound(Enabled=nbt.Tag(nbt.LIST,nbt.ListValue(nbt.STRING,enabled)))
        (path/'level.dat').write_bytes(nbt.dumps(root,compressed=True))

    def test_inline_custom_height_and_legacy_3d_biomes_at_negative_y(self):
        root=java_world(self.path/'world',2730)
        self.metadata(root,{'minecraft:overworld':nbt.compound(min_y=nbt.Tag(nbt.INT,-64),height=nbt.Tag(nbt.INT,384))})
        path=root/'region/r.0.0.mca';region=Region.read(path);_,tag=nbt.loads(region.get(0,0));level=tag.value['Level']
        level.value['Biomes']=nbt.Tag(nbt.INT_ARRAY,[1]*1536);region.put(0,0,nbt.dumps(tag));region.write()
        doc=Document(open_world(root));self.assertEqual(doc.world.bounds('overworld'),(-64,319))
        doc.selection=Selection((1,-63,2),(1,-63,2));doc.fill(Block('gold_block'));doc.set_biome('desert')
        doc.selection=Selection((1,318,2),(1,318,2));doc.fill(Block('diamond_block'));doc.set_biome('forest')
        out=self.path/'copy';doc.world.export(out,doc.edits,**doc.export_metadata());world=open_world(out)
        self.assertEqual(world.get_block(1,-63,2),Block('gold_block'));self.assertEqual(world.get_block(1,318,2),Block('diamond_block'))
        self.assertEqual(world.get_biome(1,-63,2),'minecraft:desert');self.assertEqual(world.get_biome(1,-59,2),'minecraft:plains');self.assertEqual(world.get_biome(1,318,2),'minecraft:forest')

    def test_datapack_dimension_type_and_enabled_pack_priority(self):
        root=java_world(self.path/'world');(root/'dimensions/example/tall/region').mkdir(parents=True)
        self.metadata(root,{'example:tall':nbt.Tag(nbt.STRING,'example:tall_type')},['vanilla','file/first','file/last.zip'])
        file=root/'datapacks/first/data/example/dimension_type/tall_type.json';file.parent.mkdir(parents=True);file.write_text('{"min_y":0,"height":256}')
        with zipfile.ZipFile(root/'datapacks/last.zip','w') as archive:archive.writestr('data/example/dimension_type/tall_type.json','{"min_y":-128,"height":512}')
        world=open_world(root);self.assertEqual(world.bounds('example/tall'),(-128,383));self.assertEqual(world.bounds('overworld'),(-64,319))

    def test_dimension_definition_can_come_from_datapack(self):
        root=java_world(self.path/'world');(root/'dimensions/example/deep/region').mkdir(parents=True)
        file=root/'datapacks/test/data/example/dimension/deep.json';file.parent.mkdir(parents=True);file.write_text('{"type":{"min_y":-256,"height":512}}')
        self.assertEqual(open_world(root).bounds('example/deep'),(-256,255))

    def test_unresolved_custom_height_is_refused_instead_of_guessed(self):
        root=java_world(self.path/'world');(root/'dimensions/example/missing/region').mkdir(parents=True)
        world=open_world(root)
        with self.assertRaisesRegex(ValueError,'datapack'):world.get_block(0,0,0,'example/missing')

    def test_invalid_heights_and_resource_paths_are_rejected(self):
        for index,(minimum,height) in enumerate(((1,256),(-64,0),(-2048,256),(0,4096))):
            root=java_world(self.path/str(index));self.metadata(root,{'minecraft:overworld':nbt.compound(min_y=nbt.Tag(nbt.INT,minimum),height=nbt.Tag(nbt.INT,height))})
            with self.assertRaises(ValueError):open_world(root)
        self.metadata(root,{'minecraft:overworld':nbt.Tag(nbt.STRING,'test:../../outside')})
        with self.assertRaises(ValueError):open_world(root)

    def test_disabled_datapacks_do_not_override_vanilla(self):
        root=java_world(self.path/'world');self.metadata(root,{},['vanilla'])
        file=root/'datapacks/disabled/data/minecraft/dimension_type/overworld.json';file.parent.mkdir(parents=True);file.write_text('{"min_y":0,"height":512}')
        self.assertEqual(open_world(root).bounds('overworld'),(-64,319))

    def test_custom_empty_chunk_uses_matching_biome_height(self):
        root=java_world(self.path/'world',2730);self.metadata(root,{'minecraft:overworld':nbt.compound(min_y=nbt.Tag(nbt.INT,-64),height=nbt.Tag(nbt.INT,384))})
        doc=Document(open_world(root));doc.selection=Selection((160,-64,160),(175,-64,175));doc.create_chunks();doc.fill(Block('glass'));doc.set_biome('desert')
        out=self.path/'copy';doc.world.export(out,doc.edits,**doc.export_metadata());world=open_world(out)
        self.assertEqual(world.get_block(160,-64,160),Block('glass'));self.assertEqual(world.get_biome(160,-64,160),'minecraft:desert');self.assertEqual(world.get_biome(160,300,160),'minecraft:plains')

    def test_short_custom_height_distinguishes_3d_256_array_from_2d(self):
        root=java_world(self.path/'short',2730);self.metadata(root,{'minecraft:overworld':nbt.compound(min_y=nbt.Tag(nbt.INT,-16),height=nbt.Tag(nbt.INT,64))})
        doc=Document(open_world(root));doc.selection=Selection((160,-16,160),(160,-16,160));doc.create_chunks();doc.set_biome('desert')
        out=self.path/'short-copy';doc.world.export(out,doc.edits,**doc.export_metadata());world=open_world(out)
        self.assertEqual(world.biome_grid(160,-16,160),(4,4,4));self.assertEqual(world.get_biome(160,-16,160),'minecraft:desert');self.assertEqual(world.get_biome(160,-12,160),'minecraft:plains')

    def test_upgraded_world_keeps_old_numeric_chunk_biome_origin(self):
        root=java_world(self.path/'mixed',2730);path=root/'region/r.0.0.mca';region=Region.read(path);_,chunk=nbt.loads(region.get(0,0))
        values=[1]*1024;values[0]=2;values[256]=4;chunk.value['Level'].value['Biomes']=nbt.Tag(nbt.INT_ARRAY,values)
        region.put(0,0,nbt.dumps(chunk));region.write()
        _,metadata=nbt.loads((root/'level.dat').read_bytes(),compressed=True);metadata.value['Data'].value['DataVersion']=nbt.Tag(nbt.INT,4189);(root/'level.dat').write_bytes(nbt.dumps(metadata,compressed=True))
        doc=Document(open_world(root));self.assertEqual(doc.get_biome(0,0,0),'minecraft:desert');self.assertEqual(doc.get_biome(0,64,0),'minecraft:forest')
        doc.selection=Selection((0,64,0),(0,64,0));doc.set_biome('swamp');out=self.path/'mixed-copy';doc.world.export(out,doc.edits,**doc.export_metadata())
        world=open_world(out);self.assertEqual(world.get_biome(0,0,0),'minecraft:desert');self.assertEqual(world.get_biome(0,64,0),'minecraft:swamp')
