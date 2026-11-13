import math
import struct
import unittest
import zlib

from facetedit import nbt


class NBTTests(unittest.TestCase):
    def test_known_java_bytes(self):
        raw = bytes.fromhex("0a00000300036167650000002a0800046e616d650003426f6200")
        name, root = nbt.loads(raw)
        self.assertEqual(name, "")
        self.assertEqual(nbt.get(root, "age"), 42)
        self.assertEqual(nbt.get(root, "name"), "Bob")
        self.assertEqual(nbt.dumps(root), raw)

    def test_known_little_endian_bytes(self):
        raw = bytes.fromhex("0a00000303006167652a00000000")
        _, root = nbt.loads(raw, little=True)
        self.assertEqual(nbt.get(root, "age"), 42)
        self.assertEqual(nbt.dumps(root, little=True), raw)

    def test_every_type_both_orders(self):
        root = nbt.compound(
            byte=nbt.Tag(nbt.BYTE, -128), short=nbt.Tag(nbt.SHORT, 32767),
            integer=nbt.Tag(nbt.INT, -2147483648), long=nbt.Tag(nbt.LONG, 9223372036854775807),
            float=nbt.Tag(nbt.FLOAT, 1.25), double=nbt.Tag(nbt.DOUBLE, -1.25e200),
            bytes=nbt.Tag(nbt.BYTE_ARRAY, b"\x00\xff\x7f"),
            ints=nbt.Tag(nbt.INT_ARRAY, [0, -1, 2147483647]),
            longs=nbt.Tag(nbt.LONG_ARRAY, [-9223372036854775808, 12]),
            string=nbt.Tag(nbt.STRING, "Hello 世界 🪷\0"),
            list=nbt.Tag(nbt.LIST, nbt.ListValue(nbt.INT, [1, 2, 3])),
            empty=nbt.Tag(nbt.LIST, nbt.ListValue(nbt.COMPOUND, [])),
            compound=nbt.compound(nested=nbt.Tag(nbt.STRING, "yes")),
        )
        for little in (False, True):
            with self.subTest(little=little):
                self.assertEqual(nbt.loads(nbt.dumps(root, "世界", little), little), ("世界", root))

    def test_modified_utf8_golden(self):
        self.assertEqual(nbt.modified_utf8_encode("\0😀"), bytes.fromhex("c080eda0bdedb880"))
        self.assertEqual(nbt.modified_utf8_decode(bytes.fromhex("c080eda0bdedb880")), "\0😀")

    def test_compression(self):
        root = nbt.compound(value=nbt.Tag(nbt.STRING, "FacetEdit"))
        self.assertEqual(nbt.loads(nbt.dumps(root, compressed=True), compressed=True)[1], root)

    def test_truncation_at_every_byte(self):
        raw = nbt.dumps(nbt.compound(list=nbt.Tag(nbt.LIST, nbt.ListValue(nbt.STRING, ["a", "b"])) ))
        for length in range(len(raw)):
            with self.subTest(length=length), self.assertRaises(nbt.FormatError):
                nbt.loads(raw[:length])

    def test_negative_length_rejected(self):
        with self.assertRaises(nbt.FormatError):
            nbt.loads(bytes.fromhex("070000ffffffff"))

    def test_duplicate_compound_key_rejected(self):
        with self.assertRaises(nbt.FormatError):
            nbt.loads(bytes.fromhex("0a00000100017801010001780200"))

    def test_trailing_bytes_rejected(self):
        with self.assertRaises(nbt.FormatError):
            nbt.loads(nbt.dumps(nbt.compound()) + b"x")

    def test_decompression_bomb_limit(self):
        with self.assertRaises(nbt.FormatError):
            nbt.decompress(zlib.compress(b"a"*4096), "zlib", 1024)

    def test_deep_nesting_rejected(self):
        root = nbt.compound()
        for _ in range(70):
            root = nbt.compound(child=root)
        with self.assertRaises(nbt.FormatError):
            nbt.dumps(root)

    def test_unknown_type_rejected(self):
        with self.assertRaises(nbt.FormatError):
            nbt.loads(b"\x0d\x00\x00")
