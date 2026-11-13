import struct,unittest,zlib
from facetedit import png


def chunk(kind,data):return struct.pack('>I',len(data))+kind+data+struct.pack('>I',zlib.crc32(kind+data)&0xffffffff)
def file(width,height,depth,color,rows,extra=b'',interlace=0):
    return b'\x89PNG\r\n\x1a\n'+chunk(b'IHDR',struct.pack('>IIBBBBB',width,height,depth,color,0,0,interlace))+extra+chunk(b'IDAT',zlib.compress(rows))+chunk(b'IEND',b'')


class PNGTests(unittest.TestCase):
    def test_rgba_roundtrip_and_crop(self):
        image=png.Image(2,2,bytes(range(16)))
        self.assertEqual(png.decode(png.encode(image)),image)
        self.assertEqual(image.crop(1,0,1,2).rgba,bytes((4,5,6,7,12,13,14,15)))
        with self.assertRaises(ValueError):image.crop(0,0,3,1)

    def test_all_filters_with_independent_rows(self):
        # First RGB row [10,20,30,40,50,60]; second [11,22,33,44,55,66].
        filtered={0:[11,22,33,44,55,66],1:[11,22,33,33,33,33],2:[1,2,3,4,5,6],3:[6,12,18,19,19,20],4:[1,2,3,4,5,6]}
        for kind,row in filtered.items():
            with self.subTest(filter=kind):
                decoded=png.decode(file(2,2,8,2,b'\0'+bytes((10,20,30,40,50,60))+bytes((kind,*row))))
                self.assertEqual(decoded.pixel(0,1),(11,22,33,255));self.assertEqual(decoded.pixel(1,1),(44,55,66,255))

    def test_packed_grayscale_depths(self):
        for depth,raw,expected in ((1,b'\x60',(0,255,255,0)),(2,b'\x1b',(0,85,170,255)),(4,b'\x05\xaf',(0,85,170,255))):
            with self.subTest(depth=depth):
                image=png.decode(file(4,1,depth,0,b'\0'+raw))
                self.assertEqual(tuple(image.pixel(i,0)[0] for i in range(4)),expected)

    def test_indexed_alpha(self):
        extra=chunk(b'PLTE',bytes((255,0,0,0,255,0,0,0,255)))+chunk(b'tRNS',bytes((0,100)))
        image=png.decode(file(3,1,2,3,b'\0\x18',extra))
        self.assertEqual(image.rgba,bytes((255,0,0,0,0,255,0,100,0,0,255,255)))

    def test_sixteen_bit_transparency_compares_original_samples(self):
        image=png.decode(file(2,1,16,0,b'\0\x80\x00\x80\x01',chunk(b'tRNS',b'\x80\x00')))
        self.assertEqual(image.pixel(0,0),(128,128,128,0));self.assertEqual(image.pixel(1,0),(128,128,128,255))
        image=png.decode(file(1,1,16,6,b'\0'+struct.pack('>4H',65535,32768,0,32768)))
        self.assertEqual(image.pixel(0,0),(255,128,0,128))
        self.assertEqual(png.decode(file(1,1,16,4,b'\0'+struct.pack('>2H',32768,16384))).rgba,bytes((128,128,128,64)))
        self.assertEqual(png.decode(file(1,1,16,2,b'\0'+struct.pack('>3H',65535,32768,0))).rgba,bytes((255,128,0,255)))

    def test_gray_alpha_and_rgb_transparency(self):
        self.assertEqual(png.decode(file(1,1,8,4,b'\0\x80\x40')).rgba,bytes((128,128,128,64)))
        self.assertEqual(png.decode(file(1,1,8,2,b'\0\x01\x02\x03',chunk(b'tRNS',struct.pack('>3H',1,2,3)))).rgba,bytes((1,2,3,0)))

    def test_adam7_with_odd_dimensions(self):
        w,h=9,7;pixels=[bytes((x*20,y*30,(x+y)*10,255)) for y in range(h) for x in range(w)];rows=bytearray()
        # Explicit standard Adam7 coordinate grids, independent of decoder constants.
        for xs,ys in ((range(0,w,8),range(0,h,8)),(range(4,w,8),range(0,h,8)),(range(0,w,4),range(4,h,8)),(range(2,w,4),range(0,h,4)),(range(0,w,2),range(2,h,4)),(range(1,w,2),range(0,h,2)),(range(w),range(1,h,2))):
            for y in ys:
                rows.append(0)
                for x in xs:rows.extend(pixels[y*w+x])
        self.assertEqual(png.decode(file(w,h,8,6,bytes(rows),interlace=1)).rgba,b''.join(pixels))

    def test_corruption_limits_and_trailing_compression(self):
        valid=file(1,1,8,6,b'\0\x01\x02\x03\xff')
        bad=bytearray(valid);bad[-5]^=1
        for raw in (valid[:-1],bytes(bad),valid+b'x',file(1,1,8,6,b'\0'+b'x'*10000),file(32768,32768,8,6,b''),file(1,1,8,6,b'\5\0\0\0\0')):
            with self.subTest(length=len(raw)),self.assertRaises(ValueError):png.decode(raw)

    def test_invalid_palette_and_ordering(self):
        for raw in (file(1,1,1,3,b'\0\x80'),file(1,1,1,3,b'\0\x80',chunk(b'PLTE',b'\0\0\0')),file(1,1,8,6,b'\0\0\0\0\0',chunk(b'tRNS',b'\0'))):
            with self.assertRaises(ValueError):png.decode(raw)
