"""Typed shared armor trim and dye fields for the pinned item profiles."""
from . import nbt
from .payload_fields import Fields

MATERIALS=frozenset(('quartz','iron','netherite','redstone','copper','gold','emerald','diamond','lapis','amethyst','resin'))
PATTERNS=frozenset(('sentry','dune','coast','wild','ward','eye','vex','tide','snout','rib','spire','wayfinder','shaper','silence','raiser','host','flow','bolt'))


def to_bedrock(components,tag,name):
    if 'minecraft:trim' in components.data:
        f=Fields(components.pop('minecraft:trim',nbt.COMPOUND),components.path+'.minecraft:trim');out={}
        if not name.endswith(('_helmet','_chestplate','_leggings','_boots')):raise ValueError(f.path+': trim requires wearable armor')
        for key,allowed in (('material',MATERIALS),('pattern',PATTERNS)):
            value=f.pop(key,nbt.STRING)
            if not value.startswith('minecraft:') or value[10:] not in allowed:raise ValueError(f.path+'.'+key+': no native trim identity')
            out[key.title()]=nbt.Tag(nbt.STRING,value[10:])
        f.default_only('show_in_tooltip',nbt.BYTE,1);f.finish();tag['Trim']=nbt.Tag(nbt.COMPOUND,out)
    if 'minecraft:dyed_color' in components.data:
        f=Fields(components.pop('minecraft:dyed_color',nbt.COMPOUND),components.path+'.minecraft:dyed_color')
        if not name.startswith('leather_'):raise ValueError(f.path+': dye requires leather equipment')
        value=f.pop('rgb',nbt.INT)
        if not 0<=value<=0xffffff:raise ValueError(f.path+'.rgb: outside 24-bit RGB')
        f.default_only('show_in_tooltip',nbt.BYTE,1);f.finish();tag['customColor']=nbt.Tag(nbt.INT,value-(1<<24))


def to_java(tag,components,name):
    if 'Trim' in tag.data:
        f=Fields(tag.pop('Trim',nbt.COMPOUND),tag.path+'.Trim');out={}
        if not name.endswith(('_helmet','_chestplate','_leggings','_boots')):raise ValueError(f.path+': trim requires wearable armor')
        for key,allowed in (('Material',MATERIALS),('Pattern',PATTERNS)):
            value=f.pop(key,nbt.STRING)
            if value not in allowed:raise ValueError(f.path+'.'+key+': no Java trim identity')
            out[key.lower()]=nbt.Tag(nbt.STRING,'minecraft:'+value)
        f.finish();components['minecraft:trim']=nbt.Tag(nbt.COMPOUND,out)
    if 'customColor' in tag.data:
        value=tag.pop('customColor',nbt.INT)
        if not name.startswith('leather_') or not -(1<<24)<=value<0:raise ValueError(tag.path+'.customColor: requires opaque ARGB on leather equipment')
        components['minecraft:dyed_color']=nbt.compound(rgb=nbt.Tag(nbt.INT,value+(1<<24)))
