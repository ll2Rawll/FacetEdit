import itertools,math,unittest
from facetedit.affine import Transform
from facetedit.blocks import Block,AIR
from facetedit.model import Clipboard,Document,Selection
from facetedit.world import SampleWorld
from facetedit import nbt


class AffineTests(unittest.TestCase):
    def clip(self):
        size=(2,3,4)
        return Clipboard(size,{p:Block('test:block_'+''.join(map(str,p))) for p in itertools.product(*(range(n) for n in size))})

    def test_y_quarter_turns_match_existing_coordinate_and_state_contract(self):
        clip=self.clip();clip.offset=(3,-2,7);clip.blocks[0,0,0]=Block.parse('oak_stairs[facing=north,half=bottom,shape=inner_left]')
        for turns in range(4):
            for mirror in (False,True):self.assertEqual(clip.affine((0,turns*90,0),(-1 if mirror else 1,1,1)),clip.transformed(turns,mirror))

    def test_xyz_quarter_turns_have_independent_expected_positions(self):
        clip=self.clip()
        for rotation,size,point in (((90,0,0),(2,4,3),(1,0,2)),((0,90,0),(4,3,2),(0,2,1)),((0,0,90),(3,2,4),(0,1,3))):
            result=clip.affine(rotation)
            self.assertEqual(result.size,size);self.assertEqual(result.blocks[point],clip.blocks[1,2,3]);self.assertEqual(len(result.blocks),24)

    def test_four_quarter_turns_and_double_reflections_restore_clipboard(self):
        clip=self.clip()
        for axis in range(3):
            result=clip;rotation=tuple(90 if i==axis else 0 for i in range(3))
            for _ in range(4):result=result.affine(rotation)
            self.assertEqual(result,clip)
            scale=tuple(-1 if i==axis else 1 for i in range(3))
            self.assertEqual(clip.affine(scale=scale).affine(scale=scale),clip)

    def test_integer_scaling_replicates_cells_and_sparse_holes(self):
        clip=Clipboard((3,1,1),{(0,0,0):Block('stone'),(2,0,0):Block('glass')})
        result=clip.affine(scale=(2,3,1))
        self.assertEqual(result.size,(6,3,1));self.assertEqual(len(result.blocks),12)
        self.assertNotIn((2,0,0),result.blocks);self.assertNotIn((3,0,0),result.blocks)
        for x,y,z in result.blocks:self.assertEqual(result.blocks[x,y,z],Block('stone' if x<2 else 'glass'))

    def test_fractional_scale_samples_cell_centers(self):
        clip=Clipboard((4,1,1),{(x,0,0):Block('test:b'+str(x)) for x in range(4)})
        result=clip.affine(scale=(.5,1,1));self.assertEqual(result.size,(2,1,1))
        self.assertEqual(result.blocks,{(0,0,0):Block('test:b1'),(1,0,0):Block('test:b3')})

    def test_arbitrary_angle_inverse_sampling_matches_analytic_rotation(self):
        clip=Clipboard((4,1,3),{(x,0,z):Block('test:b'+str(x)+str(z)) for x in range(4) for z in range(3)})
        angle=math.radians(31);result=clip.affine((0,31,0));expected={}
        minimum_x=math.floor(-3*math.sin(angle))
        for x in range(result.size[0]):
            for z in range(result.size[2]):
                dx,dz=x+.5+minimum_x,z+.5
                sx,sz=math.cos(angle)*dx+math.sin(angle)*dz,-math.sin(angle)*dx+math.cos(angle)*dz
                if 0<=sx<4 and 0<=sz<3:expected[x,0,z]=clip.blocks[math.floor(sx),0,math.floor(sz)]
        self.assertEqual(result.blocks,expected)

    def test_vertical_facing_axis_and_typed_bedrock_states(self):
        clip=Clipboard((1,1,1),{(0,0,0):Block.parse('end_rod[facing=up]')})
        self.assertEqual(dict(next(iter(clip.affine((90,0,0)).blocks.values())).properties)['facing'],'south')
        clip.blocks[0,0,0]=Block.parse('oak_log[axis=y]')
        self.assertEqual(dict(clip.affine((90,0,0)).blocks[0,0,0].properties)['axis'],'z')
        clip.edition='Bedrock';clip.data_version=None;clip.blocks[0,0,0]=Block('piston',(('facing_direction','1'),),(('facing_direction',nbt.INT),))
        # Native pistons use west=5; their numeric order differs from chests.
        result=clip.affine((0,0,90)).blocks[0,0,0];self.assertEqual(dict(result.properties)['facing_direction'],'5');self.assertEqual(result.state_types,clip.blocks[0,0,0].state_types)

    def test_sign_rotation_uses_sixteen_steps_and_state_toggle(self):
        clip=Clipboard((1,1,1),{(0,0,0):Block.parse('oak_sign[rotation=0]')})
        result=clip.affine((0,22.5,0));self.assertTrue(result.blocks)
        self.assertEqual({dict(b.properties)['rotation'] for b in result.blocks.values()},{'1'})
        clip.blocks[0,0,0]=Block.parse('oak_stairs[facing=north,shape=straight,half=bottom]')
        with self.assertRaisesRegex(ValueError,'tilted'):clip.affine((90,0,0))
        self.assertEqual(clip.affine((90,0,0),rotate_states=False).blocks,clip.blocks)

    def test_scaled_container_nbt_layers_and_undo(self):
        data=nbt.dumps(nbt.compound(id=nbt.Tag(nbt.STRING,'minecraft:chest'),x=nbt.Tag(nbt.INT,0),y=nbt.Tag(nbt.INT,0),z=nbt.Tag(nbt.INT,0),CustomName=nbt.Tag(nbt.STRING,'Stored')))
        clip=Clipboard((1,1,1),{(0,0,0):Block('chest')},entities={(0,0,0):data})
        doc=Document(SampleWorld());doc.clipboard=clip;doc.paste((0,40,0),rotation=(0,0,0),scale=(2,1,1))
        self.assertEqual(len(doc.entity_edits),2)
        for x in (0,1):
            tag=nbt.loads(doc.get_entity(x,40,0))[1];self.assertEqual(nbt.get(tag,'x'),x);self.assertEqual(nbt.get(tag,'CustomName'),'Stored')
        doc.undo();self.assertFalse(doc.edits);self.assertFalse(doc.entity_edits)
        clip.edition='Bedrock';clip.extra_blocks={(0,0,0):(Block('water'),)}
        self.assertEqual(len(clip.affine(scale=(2,1,1)).extra_blocks),2)

    def test_invalid_nonfinite_or_oversized_transform_leaves_document_alone(self):
        doc=Document(SampleWorld());doc.clipboard=self.clip();doc.selection=Selection((0,40,0),(0,40,0))
        for scale in ((0,1,1),(float('nan'),1,1),(100,100,100)):
            with self.assertRaises(ValueError):doc.paste(rotation=(0,0,0),scale=scale)
        self.assertFalse(doc.edits)

    def test_offset_rotates_as_a_vector(self):
        clip=self.clip();clip.offset=(3,2,-5)
        self.assertEqual(clip.affine((0,90,0)).offset,(5,2,3))
