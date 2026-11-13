import unittest
from facetedit import nbt
from facetedit.blocks import Block
from facetedit.model import Clipboard
from facetedit.transforms import RAILS


class ExtendedTransformTests(unittest.TestCase):
    def test_rails_rotate_and_reflect_all_shapes(self):
        for shape in RAILS:
            b=Block('rail',(('shape',shape),));r=b
            for _ in range(4):r=r.transform(1)
            self.assertEqual(r,b)
            self.assertEqual(b.transform(mirror=True).transform(mirror=True),b)
        self.assertEqual(dict(Block('rail',(('shape','north_east'),)).transform(1).properties)['shape'],'south_east')

    def test_handed_states_reflect_and_connections_rotate(self):
        for key,value,wanted in (('hinge','left','right'),('type','right','left'),('shape','inner_left','inner_right')):
            b=Block('oak_stairs',((key,value),('facing','east'))).transform(1,True)
            self.assertEqual(dict(b.properties)[key],wanted);self.assertEqual(dict(b.properties)['facing'],'north')
        b=Block('redstone_wire',(('north','side'),('west','up'))).transform(1)
        self.assertEqual(dict(b.properties),{'east':'side','north':'up'})

    def test_bedrock_numeric_states_keep_types_and_cycle(self):
        cases={'facing_direction':range(6),'weirdo_direction':range(4),'direction':range(4),'rail_direction':range(10),'vine_direction_bits':range(16),'ground_sign_direction':range(16),'huge_mushroom_bits':range(16)}
        for key,values in cases.items():
            for value in values:
                b=Block('test:fixture',((key,str(value)),),((key,nbt.INT),));rotated=b
                for _ in range(4):rotated=rotated.transform(1,edition='Bedrock')
                self.assertEqual(rotated,b,(key,value))
                self.assertEqual(b.transform(mirror=True,edition='Bedrock').transform(mirror=True,edition='Bedrock'),b)

    def test_paired_containers_and_typed_inventory_rotate_together(self):
        root=nbt.compound(id=nbt.Tag(nbt.STRING,'Chest'),x=nbt.Tag(nbt.INT,0),y=nbt.Tag(nbt.INT,0),z=nbt.Tag(nbt.INT,0),pairx=nbt.Tag(nbt.INT,1),pairz=nbt.Tag(nbt.INT,0),Items=nbt.Tag(nbt.LIST,nbt.ListValue(nbt.COMPOUND,[{'Count':nbt.Tag(nbt.BYTE,23)}])))
        clip=Clipboard((2,1,1),{(0,0,0):Block('chest'),(1,0,0):Block('chest')},'Bedrock',entities={(0,0,0):nbt.dumps(root)},data_version=None)
        turned=clip.transformed(1);tag=nbt.loads(turned.entities[0,0,0])[1]
        self.assertEqual((nbt.get(tag,'pairx'),nbt.get(tag,'pairz')),(0,1))
        self.assertEqual(tag.value['Items'],root.value['Items'])
        for _ in range(3):turned=turned.transformed(1)
        self.assertEqual(turned,clip)
