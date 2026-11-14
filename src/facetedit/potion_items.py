"""Pinned native potion metadata values, independent of translation libraries."""
from . import nbt
from .payload_fields import Fields

# Native inventory format IDs; gaps 2 (extended mundane) and 36 (decay)
# have no exact Java 1.21.4 potion identity. Java luck is not native ID 2.
NAMES=('water','mundane',None,'thick','awkward','night_vision','long_night_vision',
    'invisibility','long_invisibility','leaping','long_leaping','strong_leaping',
    'fire_resistance','long_fire_resistance','swiftness','long_swiftness','strong_swiftness',
    'slowness','long_slowness','water_breathing','long_water_breathing','healing','strong_healing',
    'harming','strong_harming','poison','long_poison','strong_poison','regeneration','long_regeneration',
    'strong_regeneration','strength','long_strength','strong_strength','weakness','long_weakness',None,
    'turtle_master','long_turtle_master','strong_turtle_master','slow_falling','long_slow_falling',
    'strong_slowness','wind_charged','weaving','oozing','infested')
POTIONS={name:index for index,name in enumerate(NAMES) if name is not None}
KINDS=('potion','splash_potion','lingering_potion','tipped_arrow')


def to_bedrock(base,components):
    f=Fields(components.pop('minecraft:potion_contents',nbt.COMPOUND),components.path+'.minecraft:potion_contents')
    potion=f.pop('potion',nbt.STRING)
    if not potion.startswith('minecraft:') or potion[10:] not in POTIONS:raise ValueError(f.path+'.potion: no native Bedrock equivalent for '+potion)
    effects=f.pop('custom_effects',nbt.LIST,nbt.ListValue(nbt.COMPOUND,[]))
    if effects.values:raise ValueError(f.path+'.custom_effects: custom effects have no native potion variant')
    f.finish();value=POTIONS[potion[10:]]
    return ('arrow',value+1) if base=='tipped_arrow' else (base,value)


def to_java(base,aux,path):
    value=aux-1 if base=='arrow' else aux
    if not 0<=value<len(NAMES) or NAMES[value] is None:raise ValueError(path+'.Damage: native potion variant has no Java equivalent')
    return ('tipped_arrow' if base=='arrow' else base),nbt.compound(potion=nbt.Tag(nbt.STRING,'minecraft:'+NAMES[value]))
