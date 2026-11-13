import json,tempfile,unittest,zipfile
from pathlib import Path
from facetedit import png
from facetedit.resources import ResourceStack
from facetedit.tints import TintSampler,rgb
from facetedit.model import Document,Selection
from facetedit.world import SampleWorld
from facetedit.blocks import Block
from tests.resource_fixture import pack


class TintTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.path,self.write=pack(self.temp.name);self.doc=Document(SampleWorld())

    def definition(self,name,value):
        path=self.path/'data/minecraft/worldgen/biome'/f'{name}.json';path.parent.mkdir(parents=True,exist_ok=True);path.write_text(json.dumps(value))

    def sampler(self):
        resources=ResourceStack([self.path]);self.addCleanup(resources.close);return TintSampler(resources,self.doc)

    def test_biome_override_and_staged_biome_edit(self):
        self.definition('plains',{'effects':{'grass_color':0x123456,'water_color':0x987654}})
        self.definition('forest',{'effects':{'grass_color':0xabcdef}})
        sampler=self.sampler();self.assertEqual(sampler.block(Block('grass_block'),(0,10,0)),rgb(0x123456))
        self.assertEqual(sampler.color('water',(0,10,0)),rgb(0x987654))
        self.doc.selection=Selection((0,8,0),(3,11,3));self.doc.set_biome('forest')
        self.assertEqual(self.sampler().block(Block('grass_block'),(0,10,0)),rgb(0xabcdef))

    def test_climate_colormap_temperature_and_rainfall(self):
        image=png.Image(2,2,bytes((255,0,0,255,0,255,0,255,0,0,255,255,255,255,255,255)))
        self.write('textures/colormap/grass.png',png.encode(image))
        self.definition('plains',{'temperature':0,'downfall':1,'effects':{}})
        self.assertEqual(self.sampler().color('grass',(0,0,0)),(1.,1.,1.))
        self.definition('plains',{'temperature':1,'downfall':1,'effects':{}})
        self.assertEqual(self.sampler().color('grass',(0,0,0)),(1.,0.,0.))

    def test_leaf_overrides_and_redstone_power(self):
        sample=self.sampler();self.assertEqual(sample.block(Block('birch_leaves'),(0,0,0)),rgb(0x80a755))
        self.assertEqual(sample.block(Block('spruce_leaves'),(0,0,0)),rgb(0x619961))
        self.assertGreater(sample.block(Block.parse('redstone_wire[power=15]'),(0,0,0))[0],sample.block(Block.parse('redstone_wire[power=0]'),(0,0,0))[0])

    def test_client_archive_reads_biome_data(self):
        self.definition('plains',{'effects':{'grass_color':0x102030}});archive=self.path/'pack.zip'
        with zipfile.ZipFile(archive,'w') as output:
            for path in self.path.rglob('*.json'):output.write(path,path.relative_to(self.path))
        resources=ResourceStack([archive]);self.addCleanup(resources.close)
        self.assertEqual(TintSampler(resources).color('grass',(0,0,0)),rgb(0x102030))
