import random
from pathlib import Path
import struct
import tempfile
import unittest
from unittest import mock

from facetedit import nbt
from facetedit.lz4 import decode_block,decompress_stream,xxh32,SEED
from facetedit.region import Region


def stream(raw):
    # Independent framing: 8-byte magic, method/size nibble, three LE uint32s.
    blocks=[]
    for offset in range(0,len(raw),65536):
        part=raw[offset:offset+65536]
        blocks.append(b'LZ4Block\x16'+struct.pack('<III',len(part),len(part),xxh32(part,SEED)&0x0fffffff)+part)
    return b''.join(blocks)+b'LZ4Block\x16'+b'\x00'*12


class LZ4Tests(unittest.TestCase):
    def test_xxh32_known_vectors(self):
        for raw,expected in ((b'',0x02cc5d05),(b'a',0x550d7456),(b'abc',0x32d153ff),(b'message digest',0x7c948494)):
            self.assertEqual(xxh32(raw),expected)

    def test_literal_and_overlapping_match(self):
        self.assertEqual(decode_block(b'\x30abc',3),b'abc')
        payload=b'\x36abc\x03\x00\x50defgh'
        expected=b'abcabcabcabcadefgh'
        self.assertEqual(decode_block(payload,len(expected)),expected)
        framed=b'LZ4Block\x20'+struct.pack('<III',len(payload),len(expected),xxh32(expected,SEED)&0x0fffffff)+payload+b'LZ4Block\x10'+b'\0'*12
        self.assertEqual(decompress_stream(framed),expected)

    def test_stream_raw_multiple_blocks_and_empty(self):
        for raw in (b'',b'hello',b'a'*200_000):self.assertEqual(decompress_stream(stream(raw)),raw)

    def test_truncation_checksum_unknown_method_and_limits(self):
        valid=stream(b'abcdef')
        for offset in range(len(valid)):
            with self.subTest(offset=offset),self.assertRaises(nbt.FormatError):decompress_stream(valid[:offset])
        broken=bytearray(valid);broken[17]^=1
        with self.assertRaisesRegex(nbt.FormatError,'checksum'):decompress_stream(broken)
        broken=bytearray(valid);broken[8]=0x30
        with self.assertRaises(nbt.FormatError):decompress_stream(broken)
        with mock.patch('facetedit.lz4.MAX_BYTES',2),self.assertRaises(nbt.FormatError):decompress_stream(valid)
        for raw in (b'\x10a\x00\x00',b'\x10a\x02\x00',b'\xf0',b'\x30a'):
            with self.subTest(raw=raw),self.assertRaises(nbt.FormatError):decode_block(raw,10)

    def test_java_checksum_uses_28_bits(self):
        raw=b'abc';full=xxh32(raw,SEED)
        self.assertNotEqual(full,full&0x0fffffff)
        invalid=b'LZ4Block\x10'+struct.pack('<III',3,3,full)+raw+b'LZ4Block\x10'+b'\0'*12
        with self.assertRaisesRegex(nbt.FormatError,'checksum'):decompress_stream(invalid)


class ExternalRegionTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.path=Path(self.temp.name)/'r.-1.0.mca'
    def tearDown(self):self.temp.cleanup()

    def test_external_read_edit_and_sidecar_cleanup(self):
        region=Region(path=self.path);region.put_payload(-1,0,b'\x82',__import__('zlib').compress(b'abc'))
        region.write();sidecar=self.path.parent/'c.-1.0.mcc'
        self.assertTrue(sidecar.is_file());self.assertEqual(Region.read(self.path).get(-1,0),b'abc')
        loaded=Region.read(self.path);loaded.put(-1,0,b'edited');loaded.write()
        self.assertFalse(sidecar.exists());self.assertEqual(Region.read(self.path).get(-1,0),b'edited')

    def test_oversized_edit_spills_and_roundtrips(self):
        raw=random.Random(18).randbytes(1_100_000)
        region=Region(path=self.path);region.put(-1,0,raw);region.write()
        self.assertEqual(Region.read(self.path).chunks[31],b'\x82')
        self.assertEqual(Region.read(self.path).get(-1,0),raw)
        self.assertLess(self.path.stat().st_size,16_384)

    def test_lz4_inline_and_external_regions(self):
        for external in (False,True):
            raw=stream(b'NBT payload');region=Region(path=self.path)
            region.put_payload(-1,0,b'\x84' if external else b'\x04'+raw,raw if external else None)
            region.write();self.assertEqual(Region.read(self.path).get(-1,0),b'NBT payload')

    def test_copy_region_carries_unchanged_sidecar(self):
        region=Region(path=self.path);region.put_payload(-1,0,b'\x84',stream(b'payload'));region.write()
        target=self.path.parent/'copy'/self.path.name
        Region.read(self.path).write(target)
        self.assertEqual(Region.read(target).get(-1,0),b'payload')

    def test_delete_keeps_neighbor_payload_exact(self):
        region=Region(path=self.path);region.put(-1,0,b'one');region.put(-2,0,b'two')
        original=region.chunks[30];region.write();loaded=Region.read(self.path)
        loaded.delete(-1,0);loaded.write()
        self.assertEqual(Region.read(self.path).chunks[30],original)
        self.assertEqual(Region.coordinates(self.path),{(-2,0)})
        loaded.delete(-2,0);loaded.write();self.assertFalse(self.path.exists())

    def test_missing_or_inconsistent_external_payload_refused(self):
        region=Region(path=self.path);region.chunks[0]=b'\x82';self.path.write_bytes(region.dumps())
        with self.assertRaises(FileNotFoundError):Region.read(self.path).get(-32,0)
        with self.assertRaises(nbt.FormatError):region.put_payload(-32,0,b'\x82abc',b'data')
