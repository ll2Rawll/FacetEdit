"""Optional independent test oracle; native libraries are never app dependencies."""
import ctypes
import ctypes.util
from pathlib import Path
import random
import struct
import sys

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from facetedit.lz4 import decode_block,decompress_stream,xxh32,SEED

lz4=ctypes.CDLL(ctypes.util.find_library('lz4'))
lz4.LZ4_compressBound.argtypes=[ctypes.c_int];lz4.LZ4_compressBound.restype=ctypes.c_int
lz4.LZ4_compress_default.argtypes=[ctypes.c_void_p,ctypes.c_void_p,ctypes.c_int,ctypes.c_int]
lz4.LZ4_compress_default.restype=ctypes.c_int
xx=ctypes.CDLL(ctypes.util.find_library('xxhash'))
xx.XXH32.argtypes=[ctypes.c_void_p,ctypes.c_size_t,ctypes.c_uint32];xx.XXH32.restype=ctypes.c_uint32
rng=random.Random(9876)
sizes=[0,1,3,15,16,17,255,256,4096,65535,65536,100_000]
checks=0
for size in sizes:
    for data in (rng.randbytes(size),(b'block:stone;block:air;'*((size+21)//21))[:size]):
        for seed in (0,1,SEED,0xffffffff):
            assert xxh32(data,seed)==xx.XXH32(data,len(data),seed);checks+=1
        target=ctypes.create_string_buffer(lz4.LZ4_compressBound(len(data)))
        length=lz4.LZ4_compress_default(data,target,len(data),len(target))
        payload=target.raw[:length]
        assert decode_block(payload,len(data))==data;checks+=1
        if data:
            checksum=xx.XXH32(data,len(data),SEED)&0x0fffffff
            # Real Java LZ4Block layout, independent checksum and compressor.
            method=0x27 if len(payload)<len(data) else 0x17
            body=payload if method==0x27 else data
            wire=b'LZ4Block'+bytes([method])+struct.pack('<III',len(body),len(data),checksum)+body+b'LZ4Block\x17'+b'\0'*12
            assert decompress_stream(wire)==data;checks+=1
print(f'{checks} independent checks passed against system liblz4 and libxxhash.')
