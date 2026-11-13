"""Bounded Java LZ4Block stream reader and independent XXH32 checksum."""

import struct
from .nbt import FormatError,MAX_BYTES

MASK = 0xffffffff
P1,P2,P3,P4,P5 = 2654435761,2246822519,3266489917,668265263,374761393
SEED = 0x9747b28c


def _rot(value,bits):return ((value<<bits)|(value>>(32-bits)))&MASK


def xxh32(data,seed=0):
    pos,length = 0,len(data)
    if length>=16:
        accumulators = [(seed+P1+P2)&MASK,(seed+P2)&MASK,seed&MASK,(seed-P1)&MASK]
        while pos<=length-16:
            words = struct.unpack_from('<4I',data,pos)
            for i,word in enumerate(words):
                accumulators[i] = (_rot((accumulators[i]+word*P2)&MASK,13)*P1)&MASK
            pos += 16
        result = sum(_rot(v,r) for v,r in zip(accumulators,(1,7,12,18)))&MASK
    else:result = (seed+P5)&MASK
    result = (result+length)&MASK
    while pos<=length-4:
        result = (_rot((result+struct.unpack_from('<I',data,pos)[0]*P3)&MASK,17)*P4)&MASK
        pos += 4
    while pos<length:
        result = (_rot((result+data[pos]*P5)&MASK,11)*P1)&MASK
        pos += 1
    result ^= result>>15;result = (result*P2)&MASK
    result ^= result>>13;result = (result*P3)&MASK
    return (result^(result>>16))&MASK


def decode_block(data,expected):
    if not 0<=expected<=MAX_BYTES:raise FormatError('LZ4 output exceeds its size limit')
    out = bytearray();pos = 0
    def length(initial):
        nonlocal pos
        value = initial
        if initial==15:
            while True:
                if pos>=len(data):raise FormatError('Truncated LZ4 length')
                byte = data[pos];pos+=1;value+=byte
                if value>expected:raise FormatError('LZ4 sequence exceeds declared output')
                if byte!=255:break
        return value
    while pos<len(data):
        token = data[pos];pos+=1
        literals = length(token>>4)
        if pos+literals>len(data) or len(out)+literals>expected:
            raise FormatError('Invalid LZ4 literal length')
        out.extend(data[pos:pos+literals]);pos+=literals
        if pos==len(data):break
        if pos+2>len(data):raise FormatError('Truncated LZ4 match offset')
        offset = int.from_bytes(data[pos:pos+2],'little');pos+=2
        match = length(token&15)+4
        if not 1<=offset<=len(out) or len(out)+match>expected:
            raise FormatError('Invalid LZ4 back-reference')
        # Repeated patterns can overlap the destination. Doubling avoids a
        # Python iteration for every output byte in long homogeneous matches.
        pattern = bytes(out[-offset:])
        out.extend((pattern*((match+offset-1)//offset))[:match])
    if len(out)!=expected:raise FormatError('LZ4 decompressed length mismatch')
    return bytes(out)


def decompress_stream(data):
    out = bytearray();pos = 0
    while True:
        if pos+21>len(data) or data[pos:pos+8]!=b'LZ4Block':
            raise FormatError('Missing or truncated LZ4Block header')
        token = data[pos+8]
        compressed,decoded,checksum = struct.unpack_from('<III',data,pos+9)
        pos += 21
        method,limit = token&0xf0,1<<((token&15)+10)
        if method not in (0x10,0x20):raise FormatError('Unknown LZ4Block compression method')
        if compressed==decoded==0:
            if checksum or pos!=len(data):raise FormatError('Invalid LZ4Block end marker')
            return bytes(out)
        if not 0<decoded<=limit or not 0<compressed<=decoded or len(out)+decoded>MAX_BYTES:
            raise FormatError('LZ4Block lengths exceed the block/output limit')
        if pos+compressed>len(data):raise FormatError('Truncated LZ4Block payload')
        payload = data[pos:pos+compressed];pos+=compressed
        if method==0x10:
            if compressed!=decoded:raise FormatError('Raw LZ4Block lengths disagree')
            raw = payload
        else:raw = decode_block(payload,decoded)
        # lz4-java's StreamingXXHash32.asChecksum deliberately exposes 28 bits.
        # The stream wire value is not the full unsigned XXH32 digest.
        if (xxh32(raw,SEED)&0x0fffffff)!=checksum:raise FormatError('LZ4Block checksum mismatch')
        out.extend(raw)
