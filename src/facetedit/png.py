"""Bounded PNG decoding/encoding, independently implemented with the stdlib."""
from dataclasses import dataclass
import struct,zlib

SIGNATURE=b'\x89PNG\r\n\x1a\n'
MAX_PIXELS=4_194_304
MAX_BYTES=32*1024*1024
PASSES=((0,0,8,8),(4,0,8,8),(0,4,4,8),(2,0,4,4),(0,2,2,4),(1,0,2,2),(0,1,1,2))


@dataclass(frozen=True)
class Image:
    width:int
    height:int
    rgba:bytes

    def __post_init__(self):
        if type(self.width) is not int or type(self.height) is not int or min(self.width,self.height)<1 or self.width*self.height>MAX_PIXELS or len(self.rgba)!=self.width*self.height*4:
            raise ValueError('Invalid RGBA image dimensions')

    @property
    def opaque(self):return all(a==255 for a in self.rgba[3::4])

    def pixel(self,x,y):
        x=max(0,min(self.width-1,int(x)));y=max(0,min(self.height-1,int(y)));offset=(y*self.width+x)*4
        return tuple(self.rgba[offset:offset+4])

    def crop(self,x,y,width,height):
        if min(x,y)<0 or min(width,height)<1 or x+width>self.width or y+height>self.height:raise ValueError('Texture crop exceeds image')
        return Image(width,height,b''.join(self.rgba[((y+row)*self.width+x)*4:((y+row)*self.width+x+width)*4] for row in range(height)))


def _paeth(a,b,c):
    p=a+b-c;pa,pb,pc=abs(p-a),abs(p-b),abs(p-c)
    return a if pa<=pb and pa<=pc else b if pb<=pc else c


def _samples(row,depth,count):
    if depth==8:return row
    if depth==16:return struct.unpack('>'+str(count)+'H',row)
    mask=(1<<depth)-1
    return [(row[i*depth//8]>>(8-depth-i*depth%8))&mask for i in range(count)]


def decode(raw):
    if not isinstance(raw,bytes) or len(raw)>MAX_BYTES or not raw.startswith(SIGNATURE):raise ValueError('Invalid PNG signature or file size')
    offset=8;header=None;palette=None;alpha=None;compressed=bytearray();finished=False;saw_data=False;data_ended=False
    while offset<len(raw):
        if offset+12>len(raw):raise ValueError('Truncated PNG chunk')
        length=struct.unpack_from('>I',raw,offset)[0];kind=raw[offset+4:offset+8];offset+=8
        if length>MAX_BYTES or offset+length+4>len(raw):raise ValueError('Truncated or oversized PNG chunk')
        data=raw[offset:offset+length];crc=struct.unpack_from('>I',raw,offset+length)[0];offset+=length+4
        if zlib.crc32(kind+data)&0xffffffff!=crc:raise ValueError('PNG checksum mismatch')
        if header is None and kind!=b'IHDR':raise ValueError('PNG must start with IHDR')
        if kind==b'IHDR':
            if header is not None or length!=13:raise ValueError('Invalid PNG header')
            header=struct.unpack('>IIBBBBB',data);width,height,depth,color,compression,filtering,interlace=header
            valid={0:(1,2,4,8,16),2:(8,16),3:(1,2,4,8),4:(8,16),6:(8,16)}
            if not 1<=width<=32768 or not 1<=height<=32768 or width*height>MAX_PIXELS or color not in valid or depth not in valid[color] or compression or filtering or interlace not in (0,1):raise ValueError('Unsupported or oversized PNG header')
        elif kind==b'PLTE':
            if saw_data or palette is not None or color in (0,4) or not 0<length<=768 or length%3:raise ValueError('Invalid PNG palette')
            palette=[tuple(data[i:i+3]) for i in range(0,length,3)]
        elif kind==b'tRNS':
            if saw_data or alpha is not None or (color==3 and (palette is None or not length)):raise ValueError('Invalid PNG transparency ordering')
            alpha=data
        elif kind==b'IDAT':
            if data_ended:raise ValueError('PNG IDAT chunks must be consecutive')
            saw_data=True;compressed.extend(data)
        elif kind==b'IEND':
            if length or not saw_data:raise ValueError('Invalid PNG ending')
            finished=True;break
        else:
            if saw_data:data_ended=True
            if not kind[0]&32:raise ValueError('Unknown critical PNG chunk')
    if not finished or offset!=len(raw):raise ValueError('Missing PNG ending or trailing data')
    channels={0:1,2:3,3:1,4:2,6:4}[color]
    if color==3 and (palette is None or len(palette)>1<<depth):raise ValueError('Missing or oversized indexed PNG palette')
    if alpha is not None:
        if (color==0 and len(alpha)!=2) or (color==2 and len(alpha)!=6) or (color==3 and (palette is None or len(alpha)>len(palette))) or color in (4,6):raise ValueError('Invalid PNG transparency data')
    passes=PASSES if interlace else ((0,0,1,1),)
    layouts=[];expected=0
    for x0,y0,dx,dy in passes:
        w=max(0,(width-x0+dx-1)//dx);h=max(0,(height-y0+dy-1)//dy)
        row_bytes=(w*channels*depth+7)//8
        if w and h:layouts.append((x0,y0,dx,dy,w,h,row_bytes));expected+=h*(row_bytes+1)
    decompressor=zlib.decompressobj()
    try:data=decompressor.decompress(bytes(compressed),expected+1)
    except zlib.error as exc:raise ValueError('Invalid PNG compression') from exc
    if len(data)!=expected or not decompressor.eof or decompressor.unused_data or decompressor.unconsumed_tail:raise ValueError('PNG decompressed size mismatch')
    output=bytearray(width*height*4);cursor=0;stride=max(1,(channels*depth+7)//8);maximum=(1<<depth)-1
    transparent=struct.unpack('>'+str(channels)+'H',alpha) if alpha is not None and color in (0,2) else None
    for x0,y0,dx,dy,w,h,row_bytes in layouts:
        previous=bytearray(row_bytes)
        for y in range(h):
            method=data[cursor];cursor+=1;row=bytearray(data[cursor:cursor+row_bytes]);cursor+=row_bytes
            if method>4:raise ValueError('Invalid PNG scanline filter')
            if method:
                for i in range(row_bytes):
                    a=row[i-stride] if i>=stride else 0;b=previous[i];c=previous[i-stride] if i>=stride else 0
                    predictor=a if method==1 else b if method==2 else (a+b)//2 if method==3 else _paeth(a,b,c)
                    row[i]=(row[i]+predictor)&255
            values=_samples(row,depth,w*channels)
            if color==6 and depth==8 and dx==1:
                at=((y0+y*dy)*width+x0)*4;output[at:at+w*4]=row;previous=row;continue
            for x in range(w):
                sample=values[x*channels:(x+1)*channels]
                if color==3:
                    index=sample[0]
                    if index>=len(palette):raise ValueError('PNG palette index out of range')
                    rgba=(*palette[index],alpha[index] if alpha is not None and index<len(alpha) else 255)
                else:
                    scaled=[(v*255+maximum//2)//maximum for v in sample]
                    if color==0:rgba=(scaled[0],)*3+(0 if transparent is not None and tuple(sample)==transparent else 255,)
                    elif color==2:rgba=(*scaled,0 if transparent is not None and tuple(sample)==transparent else 255)
                    elif color==4:rgba=(scaled[0],)*3+(scaled[1],)
                    else:rgba=scaled
                at=((y0+y*dy)*width+x0+x*dx)*4;output[at:at+4]=bytes(rgba)
            previous=row
    return Image(width,height,bytes(output))


def _chunk(kind,data):return struct.pack('>I',len(data))+kind+data+struct.pack('>I',zlib.crc32(kind+data)&0xffffffff)


def encode(image,compression=1):
    header=struct.pack('>IIBBBBB',image.width,image.height,8,6,0,0,0)
    rows=b''.join(b'\0'+image.rgba[y*image.width*4:(y+1)*image.width*4] for y in range(image.height))
    return SIGNATURE+_chunk(b'IHDR',header)+_chunk(b'IDAT',zlib.compress(rows,compression))+_chunk(b'IEND',b'')
