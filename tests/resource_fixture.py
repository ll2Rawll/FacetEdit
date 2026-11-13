"""Small original resource pack: no Minecraft assets or renderer code copied."""
import json
from pathlib import Path
from facetedit import png


def pack(root):
    root=Path(root)
    def write(path,value):
        target=root/'assets/minecraft'/path;target.parent.mkdir(parents=True,exist_ok=True)
        target.write_bytes(value if isinstance(value,bytes) else json.dumps(value).encode())
    # Four deliberately distinct quadrants test texture orientation and UVs.
    pixels=bytes(c for y in range(16) for x in range(16) for c in ((242,72,61,255) if x<8 and y<8 else (45,220,160,255) if y<8 else (62,120,240,255) if x<8 else (245,206,65,255)))
    write('textures/block/checker.png',png.encode(png.Image(16,16,pixels)))
    write('textures/block/clear.png',png.encode(png.Image(2,1,bytes((255,255,255,0,30,220,230,255)))))
    write('textures/block/glass.png',png.encode(png.Image(1,1,bytes((80,190,250,128)))))
    write('textures/block/animated.png',png.encode(png.Image(1,2,bytes((255,0,0,255,0,0,255,255)))))
    write('textures/block/animated.png.mcmeta',{'animation':{'frametime':2,'frames':[1,{'index':0,'time':4}]}})
    faces={name:{'texture':'#all','cullface':name} for name in ('up','down','east','west','south','north')}
    write('models/block/base.json',{'textures':{'all':'minecraft:block/checker'},'elements':[{'from':[0,0,0],'to':[16,16,16],'faces':faces}]})
    write('models/block/slab.json',{'parent':'minecraft:block/base','elements':[{'from':[0,0,0],'to':[16,8,16],'faces':faces}]})
    for block in ('stone','gold_block','grass_block','oak_log','oak_leaves','dirt','sand','cobblestone','oak_planks'):
        write('blockstates/'+block+'.json',{'variants':{'':{'model':'minecraft:block/base'}}})
    for block,texture in (('glass','glass'),('cutout','clear'),('animated','animated')):
        write('models/block/'+block+'.json',{'parent':'minecraft:block/base','textures':{'all':'minecraft:block/'+texture}})
        write('blockstates/'+block+'.json',{'variants':{'':{'model':'minecraft:block/'+block}}})
    write('blockstates/stone_slab.json',{'variants':{'type=bottom':{'model':'minecraft:block/slab'},'type=top':{'model':'minecraft:block/slab','x':180},'type=double':{'model':'minecraft:block/base'}}})
    return root,write
