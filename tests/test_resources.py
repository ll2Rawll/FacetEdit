import json,tempfile,unittest,zipfile
from pathlib import Path
from facetedit.blocks import Block
from facetedit.resources import ResourceStack,Pack,matches,NORMALS
from facetedit.scene import build_scene
from tests.resource_fixture import pack


class ResourceTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root,self.write=pack(Path(self.temp.name)/'pack');self.stack=ResourceStack([self.root]);self.addCleanup(self.stack.close)

    def test_cube_parent_and_texture_inheritance(self):
        model=self.stack.baked(Block('stone'))
        self.assertEqual(len(model.faces),6);self.assertEqual(model.occludes,frozenset(NORMALS.values()))
        self.assertEqual(model.faces[0].texture.frames[0].pixel(0,0),(242,72,61,255))
        self.assertIs(model,self.stack.baked(Block('stone')))

    def test_slab_variants_rotated_bounds_and_culling(self):
        bottom=self.stack.baked(Block.parse('stone_slab[type=bottom]'));top=self.stack.baked(Block.parse('stone_slab[type=top]'))
        self.assertEqual((min(v[1] for f in bottom.faces for v in f.vertices),max(v[1] for f in bottom.faces for v in f.vertices)),(0,.5))
        self.assertAlmostEqual(min(v[1] for f in top.faces for v in f.vertices),.5);self.assertAlmostEqual(max(v[1] for f in top.faces for v in f.vertices),1)
        self.assertEqual(bottom.occludes,frozenset({(0,-1,0)}));self.assertEqual(top.occludes,frozenset({(0,1,0)}))

    def test_multipart_logical_expressions(self):
        self.write('blockstates/fence.json',{'multipart':[{'apply':{'model':'block/slab'}},{'when':{'OR':[{'east':'true'},{'AND':[{'north':'true|maybe'},{'south':'!false'}]}]},'apply':{'model':'block/slab','x':180}}]})
        self.assertEqual(len(self.stack.baked(Block.parse('fence[east=true]')).faces),12)
        self.assertEqual(len(self.stack.baked(Block.parse('fence[east=false,north=false]')).faces),6)
        self.assertTrue(matches({'AND':[{'a':'x|y'},{'b':'!z'}]},{'a':'y','b':'x'}))

    def test_weighted_variants_are_deterministic_and_both_appear(self):
        self.write('blockstates/random.json',{'variants':{'':[{'model':'block/slab','weight':1},{'model':'block/base','weight':2}]}})
        bounds=[]
        for x in range(50):
            a=self.stack.baked(Block('random'),(x,0,0));b=self.stack.baked(Block('random'),(x,0,0));self.assertIs(a,b)
            bounds.append(max(v[1] for f in a.faces for v in f.vertices))
        self.assertEqual(set(bounds),{.5,1})

    def test_element_rotation_and_uv(self):
        self.write('models/block/tilted.json',{'textures':{'all':'block/checker'},'elements':[{'from':[0,0,0],'to':[16,16,16],'rotation':{'axis':'y','angle':45,'origin':[8,8,8]},'faces':{'up':{'texture':'#all','uv':[0,0,8,8],'rotation':90}}}]})
        self.write('blockstates/tilted.json',{'variants':{'':{'model':'block/tilted'}}})
        face=self.stack.baked(Block('tilted')).faces[0]
        self.assertEqual(face.uv,((0,.5),(0,0),(.5,0),(.5,.5)))
        self.assertAlmostEqual(face.normal[1],1);self.assertGreater(max(v[0] for v in face.vertices),1)

    def test_blockstate_uv_lock_keeps_top_texture_in_world_orientation(self):
        self.write('blockstates/locked.json',{'variants':{'locked=false':{'model':'block/base','y':90},'locked=true':{'model':'block/base','y':90,'uvlock':True}}})
        free=self.stack.baked(Block.parse('locked[locked=false]')).faces[0]
        locked=self.stack.baked(Block.parse('locked[locked=true]')).faces[0]
        self.assertEqual(free.vertices,locked.vertices);self.assertNotEqual(free.uv,locked.uv)
        for vertex,uv in zip(locked.vertices,locked.uv):
            self.assertAlmostEqual(vertex[0],uv[0]);self.assertAlmostEqual(vertex[2],uv[1])

    def test_animation_order_duration_and_interpolation(self):
        texture=self.stack.texture('block/animated')
        self.assertEqual(texture.frame_at(0)[1].pixel(0,0),(0,0,255,255))
        self.assertEqual(texture.frame_at(2)[1].pixel(0,0),(255,0,0,255))
        self.assertEqual(texture.frame_at(6)[1].pixel(0,0),(0,0,255,255))
        self.write('textures/block/animated.png.mcmeta',{'animation':{'frametime':2,'interpolate':True}})
        other=ResourceStack([self.root]);self.addCleanup(other.close)
        self.assertEqual(other.texture('block/animated').frame_at(1)[1].pixel(0,0),(128,0,128,255))

    def test_interpolated_cutout_frames_require_alpha_blending(self):
        from facetedit import png
        from facetedit.resources import Texture
        invisible=png.Image(1,1,bytes((100,200,50,0)));visible=png.Image(1,1,bytes((100,200,50,255)))
        animated=Texture((invisible,visible),(2,2),True)
        self.assertFalse(animated.opaque);self.assertTrue(animated.translucent)
        self.assertEqual(animated.frame_at(1)[1].pixel(0,0),(100,200,50,128))
        self.assertFalse(Texture((invisible,visible),(2,2),False).translucent)

    def test_pack_order_and_zip_client_jar(self):
        archive=Path(self.temp.name)/'client.jar'
        with zipfile.ZipFile(archive,'w') as stream:
            for path in self.root.rglob('*'):
                if path.is_file():stream.write(path,path.relative_to(self.root))
        zipped=ResourceStack([archive]);self.addCleanup(zipped.close)
        self.assertIn('minecraft:stone',zipped.block_names);self.assertEqual(len(zipped.baked(Block('stone')).faces),6)
        override=Path(self.temp.name)/'override';target=override/'assets/minecraft/models/block/base.json';target.parent.mkdir(parents=True)
        target.write_text(json.dumps({'parent':'block/slab'}))
        # A parent cycle is diagnosed and a usable fallback is returned.
        stacked=ResourceStack([archive,override]);self.addCleanup(stacked.close);stacked.baked(Block('stone'))
        self.assertIn('Cyclic',stacked.warnings['minecraft:stone'])

    def test_missing_resources_and_bad_data_fall_back(self):
        self.write('models/block/broken.json',{'textures':{'all':'#all'},'elements':[{'from':[0,0,0],'to':[16,16,16],'faces':{'up':{'texture':'#all'}}}]})
        self.write('blockstates/broken.json',{'variants':{'':{'model':'block/broken'}}})
        for name in ('broken','missing'):
            self.assertEqual(len(self.stack.baked(Block(name)).faces),6);self.assertIn('minecraft:'+name,self.stack.warnings)

    def test_inverted_element_and_bare_texture_map_key(self):
        self.write('models/block/inward.json',{'textures':{'paint':'block/checker'},'elements':[{'from':[16,16,16],'to':[0,0,0],'faces':{'up':{'texture':'paint'}}}]})
        self.write('blockstates/inward.json',{'variants':{'':{'model':'block/inward'}}})
        model=self.stack.baked(Block('inward'));self.assertEqual(len(model.faces),1)
        self.assertEqual(model.faces[0].normal,(0.,1.,0.));self.assertTrue(all(v[1]==0 for v in model.faces[0].vertices));self.assertFalse(self.stack.warnings)

    def test_malformed_models_remain_bounded_and_diagnosed(self):
        cases=({'elements':[None]}, {'elements':[{'from':[0,0,0],'to':[16,16,16],'faces':{'up':{'texture':'block/checker','tintindex':None}}}]}, {'parent':'block/bad'})
        for index,model in enumerate(cases):
            key='bad'+str(index);self.write('models/block/'+key+'.json',model);self.write('blockstates/'+key+'.json',{'variants':{'':{'model':'block/'+key}}})
            self.assertEqual(len(self.stack.baked(Block(key)).faces),6);self.assertIn('minecraft:'+key,self.stack.warnings)

    def test_path_traversal_and_symlinks_rejected(self):
        reader=Pack(self.root);self.addCleanup(reader.close)
        for path in ('../secret','/etc/passwd','assets/../../secret','assets\\secret','assets//secret'):
            with self.assertRaises(ValueError):reader.read(path)
        outside=Path(self.temp.name)/'outside';outside.write_text('secret')
        try:(self.root/'assets/escape').symlink_to(outside)
        except OSError:self.skipTest('Symlinks unavailable')
        with self.assertRaises(ValueError):reader.read('assets/escape')

    def test_only_full_opaque_faces_hide_neighbors(self):
        scene=build_scene({(0,0,0):Block('stone'),(1,0,0):Block('stone')},self.stack)
        self.assertEqual(len(scene.surfaces),10)
        scene=build_scene({(0,0,0):Block('stone'),(1,0,0):Block('glass')},self.stack)
        self.assertEqual(len(scene.surfaces),11)
        scene=build_scene({(0,0,0):Block('stone'),(1,0,0):Block.parse('stone_slab[type=bottom]')},self.stack)
        self.assertEqual(len(scene.surfaces),11)
