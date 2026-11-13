import threading,unittest
from facetedit.blocks import Block,AIR
from facetedit.resources import ResourceStack
from facetedit.scene import build_scene
from facetedit.geometry import build,Superseded
from facetedit.model import Document
from facetedit.world import SampleWorld


class FluidTests(unittest.TestCase):
    def setUp(self):self.resources=ResourceStack();self.addCleanup(self.resources.close)

    def test_adjacent_source_water_has_shared_corners_and_no_internal_faces(self):
        scene=build_scene({(0,0,0):Block('water'),(1,0,0):Block('water')},self.resources)
        self.assertEqual(len(scene.surfaces),10)
        a=next(f for f in scene.surfaces if f.position==(0,0,0) and f.normal[1]>.5)
        b=next(f for f in scene.surfaces if f.position==(1,0,0) and f.normal[1]>.5)
        self.assertEqual({v for v in a.vertices if v[0]==1},{v for v in b.vertices if v[0]==1})
        self.assertTrue(all(0<v[1]<1 for v in a.vertices))

    def test_stacked_falling_fluid_and_level_change_height(self):
        scene=build_scene({(0,0,0):Block('water'),(0,1,0):Block.parse('water[level=8]')},self.resources)
        self.assertFalse(any(f.normal[1]>.5 and f.position==(0,0,0) for f in scene.surfaces))
        bottom=[v[1] for f in scene.surfaces if f.position==(0,0,0) for v in f.vertices]
        self.assertIn(1.,bottom)
        shallow=build_scene({(0,0,0):Block.parse('water[level=7]')},self.resources)
        self.assertLess(max(v[1] for f in shallow.surfaces for v in f.vertices),.2)

    def test_opaque_neighbor_hides_fluid_face_and_liquid_is_pickable(self):
        scene=build_scene({(0,0,0):Block('water'),(1,0,0):Block('stone')},self.resources)
        self.assertFalse(any(f.position==(0,0,0) and f.normal==(1.,0.,0.) for f in scene.surfaces))
        self.assertEqual(scene.pick((.5,2,.5),(0,-1,0)),(0,0,0))

    def test_waterlogged_solid_does_not_add_exposed_liquid_faces(self):
        scene=build_scene({(0,0,0):Block.parse('stone[waterlogged=true]')},self.resources)
        self.assertEqual(len(scene.surfaces),6)

    def test_fluid_in_secondary_bedrock_layer_is_visible(self):
        class Doc:
            def get_extra_blocks(self,*position):return (Block.parse('water[liquid_depth=2]'),)
        scene=build_scene({(0,0,0):AIR},self.resources,Doc())
        self.assertEqual(len(scene.surfaces),6);self.assertEqual(scene.pick((.5,2,.5),(0,-1,0)),(0,0,0))

    def test_geometry_finds_secondary_fluid_above_air_primary_layer(self):
        class LayerWorld(SampleWorld):
            def get_block(self,*args):return AIR
            def get_extra_blocks(self,x,y,z,dimension='overworld'):return (Block('water'),) if (x,y,z)==(0,80,0) else ()
        doc=Document(LayerWorld());geometry=build(doc,'orbit',(0,0),1,95,threading.Event(),self.resources)
        self.assertEqual(geometry.height_origin,78);self.assertEqual(len(geometry.scene.surfaces),6)
        self.assertEqual(geometry.scene.pick((.5,82,.5),(0,-1,0)),(0,80,0))

    def test_procedural_missing_geometry_shows_diagnostic_marker(self):
        from tests.resource_fixture import pack
        import tempfile
        with tempfile.TemporaryDirectory() as folder:
            path,write=pack(folder);write('blockstates/chest.json',{'variants':{'':{'model':'block/chest'}}});write('models/block/chest.json',{'textures':{'particle':'block/checker'}})
            with_resources=ResourceStack([path])
            try:
                self.assertEqual(len(with_resources.baked(Block('chest')).faces),6);self.assertIn('procedural',with_resources.warnings['minecraft:chest'])
            finally:with_resources.close()
