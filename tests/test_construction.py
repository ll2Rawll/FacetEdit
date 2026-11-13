"""Native construction interoperability, sparse masks and hostile offset checks."""
from pathlib import Path
import struct
import tempfile
import unittest

from facetedit import nbt
from facetedit.blocks import AIR, Block
from facetedit.construction import INDEX, MAGIC, load_construction, save_construction
from facetedit.model import Clipboard
from facetedit.registry import profile


class ConstructionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.path = Path(self.temp.name)/'test.construction'

    def tearDown(self):
        self.temp.cleanup()

    def rewrite(self, edit):
        raw = self.path.read_bytes()
        offset = struct.unpack('>I', raw[-12:-8])[0]
        root = nbt.loads(raw[offset:-12], compressed=True)[1]
        edit(root)
        self.path.write_bytes(raw[:offset]+nbt.dumps(root, compressed=True)+raw[-12:])

    def test_sparse_mask_negative_offset_air_and_block_nbt(self):
        tag = nbt.compound(id=nbt.Tag(nbt.STRING, 'minecraft:chest'), x=nbt.Tag(nbt.INT, 0), y=nbt.Tag(nbt.INT, 0), z=nbt.Tag(nbt.INT, 0), CustomName=nbt.Tag(nbt.STRING, 'Treasure 世界'))
        clip = Clipboard((33,2,3), {(0,0,0): Block('chest'), (1,0,0): AIR, (32,1,2): Block('diamond_block')}, offset=(-17,-2,30), entities={(0,0,0): nbt.dumps(tag)})
        save_construction(clip, self.path)
        loaded = load_construction(self.path)
        self.assertEqual(loaded.blocks, clip.blocks)
        self.assertEqual(loaded.size, clip.size)
        self.assertEqual(loaded.offset, clip.offset)
        self.assertEqual(loaded.entities, clip.entities)
        self.assertEqual(loaded.data_version, 4189)

    def test_bedrock_typed_states_three_layers_and_transforms(self):
        b = profile('Bedrock 1.21.50')
        clip = Clipboard((2,1,1), {(0,0,0): b.initial('minecraft:oak_stairs'), (1,0,0): AIR}, 'Bedrock', data_version=None,
                         extra_blocks={(0,0,0): (b.initial('minecraft:water'), b.initial('minecraft:glass'))}, game_version=(1,21,50))
        save_construction(clip, self.path)
        loaded = load_construction(self.path)
        self.assertEqual(loaded.blocks, clip.blocks)
        self.assertEqual(loaded.extra_blocks, clip.extra_blocks)
        self.assertEqual(loaded.game_version, (1,21,50))
        self.assertEqual(loaded.transformed(1).game_version, loaded.game_version)
        self.assertEqual(loaded.affine((0,90,0)).game_version, loaded.game_version)

    def test_full_16_cube_uses_one_section_and_z_fast_order(self):
        clip = Clipboard((16,16,16), {(x,y,z): Block('stone' if z%2 else 'glass') for x in range(16) for y in range(16) for z in range(16)})
        save_construction(clip, self.path)
        self.assertEqual(load_construction(self.path).blocks, clip.blocks)
        raw = self.path.read_bytes(); offset = struct.unpack('>I', raw[-12:-8])[0]
        root = nbt.loads(raw[offset:-12], compressed=True)[1]
        self.assertEqual(len(nbt.get(root, 'section_index_table')), INDEX.size)
        self.assertLess(len(raw), 600)

    def test_more_than_256_palette_entries_uses_int_array(self):
        clip = Clipboard((17,1,17), {(x,0,z): Block('custom:block_'+str(x*17+z)) for x in range(17) for z in range(17)})
        save_construction(clip, self.path)
        self.assertEqual(load_construction(self.path).blocks, clip.blocks)

    def test_numeric_java_metadata_roundtrip(self):
        clip = Clipboard((1,1,1), {(0,0,0): Block('wool', (('legacy_data', '14'),))}, data_version=1343)
        save_construction(clip, self.path)
        self.assertEqual(load_construction(self.path).blocks, clip.blocks)

    def test_footer_range_and_section_overlap_are_rejected(self):
        clip = Clipboard((1,1,1), {(0,0,0): AIR})
        save_construction(clip, self.path)
        self.rewrite(lambda root: root.value.__setitem__('section_index_table', nbt.Tag(nbt.BYTE_ARRAY, INDEX.pack(0,0,0,1,1,1,0,8))))
        with self.assertRaisesRegex(ValueError, 'outside'):
            load_construction(self.path)
        save_construction(clip, self.path)
        self.rewrite(lambda root: root.value.__setitem__('section_index_table', nbt.Tag(nbt.BYTE_ARRAY, nbt.get(root, 'section_index_table')*2)))
        with self.assertRaisesRegex(ValueError, 'Overlapping'):
            load_construction(self.path)

    def test_palette_cycles_and_universal_edition_are_rejected(self):
        clip = Clipboard((1,1,1), {(0,0,0): AIR})
        save_construction(clip, self.path)
        def cycle(root):
            nbt.get(root, 'block_palette').values[0]['extra_blocks'] = nbt.Tag(nbt.LIST, nbt.ListValue(nbt.INT, [0]))
        self.rewrite(cycle)
        with self.assertRaisesRegex(ValueError, 'cyclic'):
            load_construction(self.path)
        save_construction(clip, self.path)
        self.rewrite(lambda root: root.value['export_version'].value.__setitem__('edition', nbt.Tag(nbt.STRING, 'universal')))
        with self.assertRaisesRegex(ValueError, 'native'):
            load_construction(self.path)

    def test_invalid_export_keeps_existing_destination(self):
        self.path.write_bytes(b'previous data')
        clip = Clipboard((1,1,1), {(0,0,0): AIR}, 'Bedrock', data_version=None)
        with self.assertRaisesRegex(ValueError, 'known game'):
            save_construction(clip, self.path)
        self.assertEqual(self.path.read_bytes(), b'previous data')

    def test_hand_assembled_raw_nbt_fixture_and_signed_byte_index(self):
        # Independent envelope: no use of the exporter or its palette builder.
        palette = [{'namespace': nbt.Tag(8, 'minecraft'), 'blockname': nbt.Tag(8, 'stone' if i == 100 else 'air'),
                    'properties': nbt.compound(), 'extra_blocks': nbt.Tag(9, nbt.ListValue(1, []))} for i in range(201)]
        section = nbt.dumps(nbt.compound(blocks_array_type=nbt.Tag(1,7), blocks=nbt.Tag(7,b'\x64'), entities=nbt.Tag(9,nbt.ListValue(1,[])), block_entities=nbt.Tag(9,nbt.ListValue(1,[]))))
        metadata = nbt.dumps(nbt.compound(section_version=nbt.Tag(1,0), selection_boxes=nbt.Tag(11,[-1,0,2,0,1,3]),
            export_version=nbt.compound(edition=nbt.Tag(8,'java'), version=nbt.Tag(9,nbt.ListValue(3,[1,21,4]))),
            section_index_table=nbt.Tag(7,struct.pack('<iiibbbii',-1,0,2,1,1,1,9,len(section))), block_palette=nbt.Tag(9,nbt.ListValue(10,palette))))
        self.path.write_bytes(b'constrct\0'+section+metadata+struct.pack('>I',9+len(section))+b'constrct')
        clip = load_construction(self.path)
        self.assertEqual(clip.blocks, {(0,0,0): Block('stone')})
        self.assertEqual(clip.offset, (-1,0,2))
