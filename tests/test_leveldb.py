from pathlib import Path
import struct
import io
import tempfile
import unittest
import zlib

from facetedit.leveldb import Cursor, MAGIC, LogWriter, blob, block_entries, crc32c, load_database, log_records, masked_crc, snappy_decode, table_entries, varint, write_database, write_log
from facetedit.nbt import FormatError


def table_block(entries):
    data = b"".join(varint(0) + varint(len(k)) + varint(len(v)) + k + v for k, v in entries)
    return data + struct.pack("<II", 0, 1)


def make_table(key, value, compression=0):
    raw = table_block([(key, value)])
    if compression == 2:
        payload = zlib.compress(raw)
    elif compression == 4:
        compressor = zlib.compressobj(wbits=-15)
        payload = compressor.compress(raw) + compressor.flush()
    else:
        payload = raw
    data_block = payload + bytes([compression]) + struct.pack("<I", masked_crc(payload + bytes([compression])))
    handle = varint(0) + varint(len(payload))
    index = table_block([(key, handle)])
    index_offset = len(data_block)
    index_block = index + b"\x00" + struct.pack("<I", masked_crc(index+b"\x00"))
    footer = varint(0) + varint(0) + varint(index_offset) + varint(len(index))
    return data_block + index_block + footer.ljust(40, b"\x00") + struct.pack("<Q", MAGIC)


class LevelDBTests(unittest.TestCase):
    def test_streamed_log_matches_buffered_fragments_at_block_boundaries(self):
        records=[b'a'*32761,b'b'*32762,b'',b'c'*65536,b'd'*32758,b'end']
        output=io.BytesIO();writer=LogWriter(output)
        for record in records:writer.record(record)
        self.assertEqual(output.getvalue(),write_log(records))
        self.assertEqual(list(log_records(output.getvalue())),records)

    def test_crc32c_independent_known_vectors(self):
        self.assertEqual(crc32c(b"123456789"), 0xE3069283)
        self.assertEqual(crc32c(b""), 0)
        self.assertEqual(crc32c(b"\x00"*32), 0x8A9136AA)
        self.assertEqual(masked_crc(b""), 0xA282EAD8)

    def test_varint_golden(self):
        self.assertEqual(varint(300), b"\xac\x02")
        self.assertEqual(Cursor(b"\xac\x02").varint(), 300)
        for number in (0, 127, 128, 2**32, 2**64-1):
            with self.subTest(number=number):
                self.assertEqual(Cursor(varint(number)).varint(), number)
        with self.assertRaises(FormatError):
            Cursor(b"\xff"*11).varint()

    def test_snappy_literals_and_overlapping_copy(self):
        # output length 10, literal "ab", COPY_2 length 8 / offset 2.
        self.assertEqual(snappy_decode(b"\x0a\x04ab\x1e\x02\x00"), b"ababababab")
        self.assertEqual(snappy_decode(b"\x05\x10hello"), b"hello")

    def test_snappy_copy1_and_copy4(self):
        self.assertEqual(snappy_decode(bytes([5, 0])+b"x"+bytes([1, 1])), b"xxxxx")
        self.assertEqual(snappy_decode(bytes([5, 0])+b"x"+bytes([15, 1, 0, 0, 0])), b"xxxxx")

    def test_snappy_invalid_offsets_and_size(self):
        for raw in (b"\x01\x02\x00\x00", b"\x02\x10hello", b"\x05\x00x", b"\x02\xfc"):
            with self.subTest(raw=raw), self.assertRaises(FormatError):
                snappy_decode(raw)

    def test_log_fragment_boundaries(self):
        records = [b"", b"a"*32750, b"b"*65536, b"c"*2, b"d"*32761, b"e"*32762]
        raw = write_log(records)
        self.assertEqual(list(log_records(raw)), records)

    def test_log_checksum_and_truncation(self):
        raw = bytearray(write_log([b"record"]))
        raw[-1] ^= 1
        with self.assertRaises(FormatError):
            list(log_records(raw))
        raw = write_log([b"x"*40000])
        with self.assertRaises(FormatError):
            list(log_records(raw[:-1]))

    def test_table_reads_all_supported_zlib_modes(self):
        key = b"mykey" + struct.pack("<Q", 257)
        for compression in (0, 2, 4):
            with self.subTest(compression=compression):
                self.assertEqual(list(table_entries(make_table(key, b"value", compression))), [(key, b"value")])

    def test_table_checksum_failure(self):
        data = bytearray(make_table(b"hello", b"world"))
        data[5] ^= 1
        with self.assertRaises(FormatError):
            list(table_entries(data))

    def test_restart_block_shared_prefix(self):
        raw = bytes([0, 3, 1]) + b"abc1" + bytes([2, 1, 1]) + b"d2" + struct.pack("<II", 0, 1)
        self.assertEqual(list(block_entries(raw)), [(b"abc", b"1"), (b"abd", b"2")])

    def test_database_snapshot_round_trip(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "db"
            values = {b"key"+str(i).encode(): b"v"*(i % 1000) for i in range(1600)}
            values[b"large"] = b"x"*100000
            write_database(path, values)
            self.assertEqual(load_database(path), values)
            with self.assertRaises(FileExistsError):
                write_database(path, values)

    def test_empty_snapshot(self):
        with tempfile.TemporaryDirectory() as tmp:
            write_database(tmp, {})
            self.assertEqual(load_database(tmp), {})

    def test_manifest_selects_live_files_and_wal_wins(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp)
            key = b"key"
            table = make_table(key+struct.pack("<Q", (4 << 8) | 1), b"old")
            (path / "000003.ldb").write_bytes(table)
            (path / "000004.ldb").write_bytes(b"obsolete corrupt table, must not be read")
            manifest = varint(1)+blob(b"leveldb.BytewiseComparator")+varint(2)+varint(5)
            for number, size in ((4, 9), (3, len(table))):
                manifest += varint(7)+varint(0)+varint(number)+varint(size)+blob(key)+blob(key)
            manifest += varint(6)+varint(0)+varint(4)
            (path / "MANIFEST-000001").write_bytes(write_log([manifest]))
            (path / "CURRENT").write_text("MANIFEST-000001\n")
            batch = struct.pack("<QI", 5, 1)+b"\x01"+blob(key)+blob(b"new")
            (path / "000005.log").write_bytes(write_log([batch]))
            (path / "000002.log").write_bytes(b"obsolete corrupt log")
            self.assertEqual(load_database(path), {key: b"new"})
            deletion = struct.pack("<QI", 6, 1)+b"\x00"+blob(key)
            (path / "000005.log").write_bytes(write_log([batch, deletion]))
            self.assertEqual(load_database(path), {})

    def test_bad_current_path_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp) / "CURRENT").write_text("../../secrets")
            with self.assertRaises(FormatError):
                load_database(tmp)
