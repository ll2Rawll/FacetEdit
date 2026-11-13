"""Color and banner format identifiers, plus typed pattern conversion."""
from . import nbt
from .payload_fields import Fields,compound_list

COLORS=('white','orange','magenta','light_blue','yellow','lime','pink','gray','light_gray','cyan','purple','blue','brown','green','red','black')
# Observed by the original reflection report against Mojang's official 1.21.4
# server: DyeColor.getTextColor(). Bedrock sign colors store these as ARGB ints.
TEXT_RGB=(16777215,16738335,16711935,10141901,16776960,12582656,16738740,8421504,
          13882323,65535,10494192,255,9127187,65280,16711680,0)
PATTERNS={'base':'b','square_bottom_left':'bl','square_bottom_right':'br','square_top_left':'tl','square_top_right':'tr',
          'stripe_bottom':'bs','stripe_top':'ts','stripe_left':'ls','stripe_right':'rs','stripe_center':'cs','stripe_middle':'ms',
          'stripe_downright':'drs','stripe_downleft':'dls','small_stripes':'ss','cross':'cr','straight_cross':'sc',
          'triangle_bottom':'bt','triangle_top':'tt','triangles_bottom':'bts','triangles_top':'tts','diagonal_left':'ld',
          'diagonal_up_right':'rud','diagonal_up_left':'lud','diagonal_right':'rd','circle':'mc','rhombus':'mr',
          'half_vertical':'vh','half_horizontal':'hh','half_vertical_right':'vhr','half_horizontal_bottom':'hhb',
          'border':'bo','curly_border':'cbo','gradient':'gra','gradient_up':'gru','bricks':'bri','globe':'glb',
          'creeper':'cre','skull':'sku','flower':'flo','mojang':'moj','piglin':'pig','flow':'flw','guster':'gus'}


def patterns_to_bedrock(value,path):
    entries=compound_list(value,path)
    if len(entries)>64:raise ValueError(path+': too many banner patterns')
    result=[]
    for index,entry in enumerate(entries):
        fields=Fields(entry,f'{path}[{index}]');name=fields.pop('pattern',nbt.STRING);color=fields.pop('color',nbt.STRING);fields.finish()
        if not name.startswith('minecraft:') or name[10:] not in PATTERNS or color not in COLORS:raise ValueError(fields.path+': unknown banner pattern/color')
        result.append({'Pattern':nbt.Tag(nbt.STRING,PATTERNS[name[10:]]),'Color':nbt.Tag(nbt.INT,15-COLORS.index(color))})
    return nbt.Tag(nbt.LIST,nbt.ListValue(nbt.COMPOUND,result))


def patterns_to_java(value,path):
    entries=compound_list(value,path);reverse={v:k for k,v in PATTERNS.items()}
    if len(entries)>64:raise ValueError(path+': too many banner patterns')
    result=[]
    for index,entry in enumerate(entries):
        fields=Fields(entry,f'{path}[{index}]');name=fields.pop('Pattern',nbt.STRING);color=fields.pop('Color',nbt.INT);fields.finish()
        if name not in reverse or not 0<=color<16:raise ValueError(fields.path+': unknown banner pattern/color')
        result.append({'pattern':nbt.Tag(nbt.STRING,'minecraft:'+reverse[name]),'color':nbt.Tag(nbt.STRING,COLORS[15-color])})
    return nbt.Tag(nbt.LIST,nbt.ListValue(nbt.COMPOUND,result))
