import gzip
import random
import struct
import unittest
import zlib

from facetedit import nbt
from facetedit.blocks import AIR, Block
from facetedit.formats import decode_bedrock, encode_bedrock, decode_java_section, encode_java_section, pack_indices, unpack_indices, bedrock_entry
from facetedit.region import Region


class PaletteTests(unittest.TestCase):
    def test_known_little_packed_words(self):
        self.assertEqual(pack_indices([1, 2, 3, 4], 4, width=32), [0x4321])
        self.assertEqual(unpack_indices([0x4321], 4, count=4, width=32), [1, 2, 3, 4])

    def test_random_palette_widths(self):
        rng = random.Random(807)
        for width in (32, 64):
            for bits in (1, 2, 3, 4, 5, 6, 8, 9, 12, 16):
                for padded in (True, False):
                    values = [rng.randrange(1 << bits) for _ in range(4096)]
                    with self.subTest(width=width, bits=bits, padded=padded):
                        self.assertEqual(unpack_indices(pack_indices(values, bits, width, padded), bits, width=width, padded=padded), values)

    def test_java_palette_growth_versions(self):
        blocks = [Block("test:block_" + str(i % 37)) for i in range(4096)]
        for version in (1451, 2230, 2529, 2865, 4189):
            with self.subTest(version=version):
                section = {"Y": nbt.Tag(nbt.BYTE, -1)}
                encode_java_section(section, blocks, version)
                self.assertEqual(decode_java_section(section, version), blocks)

    def test_java_singleton(self):
        section = {}
        encode_java_section(section, [AIR]*4096, 4189)
        self.assertNotIn("data", section["block_states"].value)
        self.assertEqual(decode_java_section(section, 4189), [AIR]*4096)

    def test_java_properties_preserved(self):
        block = Block.parse("minecraft:oak_stairs[facing=east,half=top,waterlogged=false]")
        section = {}
        encode_java_section(section, [block]*4096, 4189)
        self.assertEqual(decode_java_section(section, 4189)[0], block)

    def test_bedrock_singleton_golden_layout(self):
        entry = bedrock_entry(Block("stone"))
        raw = bytes((9, 1, 255, 0)) + nbt.dumps(entry, little=True)
        version, y, layers, palettes = decode_bedrock(raw)
        self.assertEqual((version, y), (9, -1))
        self.assertEqual(layers, [[Block("stone")]*4096])
        self.assertEqual(encode_bedrock(version, y, layers, palettes), raw)

    def test_bedrock_palette_growth_multilayer(self):
        for version in (8, 9):
            for size in (2, 3, 5, 17, 33, 65, 300):
                with self.subTest(version=version, size=size):
                    blocks = [Block("test:b"+str(i % size)) for i in range(4096)]
                    raw = encode_bedrock(version, 3, [blocks, [AIR]*4096])
                    self.assertEqual(decode_bedrock(raw)[2], [blocks, [AIR]*4096])

    def test_bedrock_state_types_preserved(self):
        original = nbt.compound(name=nbt.Tag(nbt.STRING, "test:block"), states=nbt.compound(a=nbt.Tag(nbt.BYTE, 1), b=nbt.Tag(nbt.INT, 1), c=nbt.Tag(nbt.STRING, "1")), version=nbt.Tag(nbt.INT, 18163713))
        raw = bytes((9, 1, 0, 0)) + nbt.dumps(original, little=True)
        version, y, layers, palettes = decode_bedrock(raw)
        self.assertEqual(encode_bedrock(version, y, layers, palettes), raw)

    def test_bad_palette_index(self):
        section = {"block_states": nbt.compound(palette=nbt.Tag(nbt.LIST, nbt.ListValue(nbt.COMPOUND, [{"Name": nbt.Tag(nbt.STRING, "minecraft:air")}])) , data=nbt.Tag(nbt.LONG_ARRAY, [-1]*256))}
        with self.assertRaises(nbt.FormatError):
            decode_java_section(section, 4189)

    def test_bedrock_runtime_palette_rejected(self):
        with self.assertRaises(nbt.FormatError):
            decode_bedrock(bytes((9, 1, 0, 3)))


class RegionTests(unittest.TestCase):
    def test_negative_coordinates_slots(self):
        self.assertEqual(Region.index(-1, -1), 1023)
        region = Region()
        region.put(-1, -1, b"hello")
        self.assertEqual(Region(region.dumps()).get(-1, -1), b"hello")

    def test_neighbor_untouched(self):
        region = Region()
        region.put(0, 0, b"a"*100)
        region.put(1, 0, b"b"*100)
        original = region.chunks[1]
        reopened = Region(region.dumps())
        reopened.put(0, 0, b"c"*100000)
        self.assertEqual(Region(reopened.dumps()).chunks[1], original)

    def test_all_compression_methods(self):
        for method, data in ((1, gzip.compress(b"abc")), (2, zlib.compress(b"abc")), (3, b"abc")):
            with self.subTest(method=method):
                region = Region()
                region.chunks[0] = bytes([method]) + data
                self.assertEqual(Region(region.dumps()).get(0, 0), b"abc")

    def test_overlapping_sectors_rejected(self):
        region = Region()
        region.put(0, 0, b"abc")
        raw = bytearray(region.dumps())
        raw[4:8] = raw[:4]
        with self.assertRaises(nbt.FormatError):
            Region(raw)

    def test_bad_header_and_length(self):
        for raw in (b"x", b"\x00"*8193, bytes.fromhex("00000101") + b"\x00"*(8192-4)):
            with self.subTest(length=len(raw)), self.assertRaises(nbt.FormatError):
                Region(raw)

    def test_external_chunk_refused(self):
        region = Region()
        region.chunks[0] = b"\x82"
        with self.assertRaises(nbt.FormatError):
            region.get(0, 0)
