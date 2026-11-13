"""Biome-aware resource colormaps and explicit color overrides.

Uses the chosen client's data/worldgen definitions when supplied. Climate is
sampled per stored biome cell; game lighting, altitude noise and blended biome
boundaries are separate features and are not approximated as exact Minecraft.
"""
import math


def rgb(value):return tuple((value>>shift&255)/255 for shift in (16,8,0))


class TintSampler:
    def __init__(self,resources,document=None):self.resources=resources;self.document=document;self.colors={};self.cells={}

    def biome(self,position):
        if self.document is None:return 'minecraft:plains'
        try:
            cell=self.document.view_world.biome_cell(*position,self.document.dimension)
            if cell not in self.cells:self.cells[cell]=self.document.get_biome(*position)
            return self.cells[cell]
        except (ValueError,OSError,AttributeError,NotImplementedError):return 'minecraft:plains'

    def color(self,kind,position):
        biome=self.biome(position);key=kind,biome
        if key in self.colors:return self.colors[key]
        try:
            definition=self.resources.json('worldgen/biome',biome,True,root='data') or {}
            effects=definition.get('effects',{});value=effects.get(kind+'_color')
            if type(value) is int and 0<=value<=0xffffff:color=rgb(value)
            elif kind=='water':color=rgb(0x3f76e4)
            else:
                temperature=float(definition.get('temperature',.8));rain=float(definition.get('downfall',.4))
                if not math.isfinite(temperature) or not math.isfinite(rain):raise ValueError('Invalid biome climate')
                temperature=max(0.,min(1.,temperature));rain=max(0.,min(1.,rain))*temperature
                image=self.resources.texture('minecraft:colormap/'+kind).frames[0]
                color=tuple(v/255 for v in image.pixel((1-temperature)*(image.width-1),(1-rain)*(image.height-1))[:3])
            if kind=='grass':
                modifier=effects.get('grass_color_modifier')
                if modifier=='dark_forest':color=tuple((int(v*255)+m)//2/255 for v,m in zip(color,(40,52,10)))
                elif modifier=='swamp':color=rgb(0x6a7039)
        except (ValueError,OSError,TypeError,AttributeError,KeyError):color=rgb(0x91bd59 if kind=='grass' else 0x77ab2f if kind=='foliage' else 0x3f76e4)
        self.colors[key]=color;return color

    def block(self,block,position):
        if block.name=='minecraft:redstone_wire':
            try:power=max(0,min(15,int(dict(block.properties).get('power','0'))))
            except (ValueError,TypeError):power=0
            return .3+.7*power/15,max(0,(power/15)**2*.7-.5),0.
        if block.name=='minecraft:spruce_leaves':return rgb(0x619961)
        if block.name=='minecraft:birch_leaves':return rgb(0x80a755)
        kind='foliage' if 'leaves' in block.name or block.name.endswith(':vine') else 'grass'
        return self.color(kind,position)
