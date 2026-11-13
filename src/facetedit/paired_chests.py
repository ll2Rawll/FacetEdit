"""Validate native double-chest links against actual adjacent block cells."""
from . import nbt
from .blocks import Block
from .payload_fields import Fields

SIDES=('north','east','south','west')
DELTAS=((0,0,-1),(1,0,0),(0,0,1),(-1,0,0))


def paired_position(position,facing,side):
    delta=DELTAS[(SIDES.index(facing)+(1 if side=='left' else -1))%4]
    return tuple(a+b for a,b in zip(position,delta))


def link(f,position):
    present='pairx' in f.data or 'pairz' in f.data
    lead=f.flag('pairlead')
    if not present:
        if lead:raise ValueError(f.path+': pairlead requires both pair coordinates')
        return None,False
    return (f.pop('pairx',nbt.INT),position[1],f.pop('pairz',nbt.INT)),lead


def neighbour_link(data,position):
    if data is None:return None,False
    f=Fields(nbt.loads(data)[1],'Chest neighbour NBT')
    if f.pop('id',nbt.STRING)!='Chest':raise ValueError('Chest neighbour has a mismatched NBT identifier')
    for axis,value in zip('xyz',position):
        if f.pop(axis,nbt.INT,value)!=value:raise ValueError('Chest neighbour NBT coordinates disagree')
    return link(f,position)


def cached_link(translator,data,position):
    if data is None:return None,False
    key=position,data
    if key in translator.chest_links:return translator.chest_links[key]
    result=neighbour_link(data,position)
    # Cache only this translator's bounded context. The content is part of the
    # key, so a second caller cannot reuse an old link after editing the NBT.
    if len(translator.chest_links)<8192 and translator.chest_link_bytes+len(data)<=4*1024*1024:
        translator.chest_links[key]=result;translator.chest_link_bytes+=len(data)
    return result


def translate(translator,block,f,position,get,get_entity):
    p=dict(block.properties);out={}
    if translator.source.edition=='Java':
        side=p['type'];facing=p['facing']
        if side!='single':
            pair=paired_position(position,facing,side);other=get(pair) if get else None
            if other is None or other.name!=block.name:raise ValueError('Double chest translation requires both matching halves')
            other=translator.source.validate(other,defaults=True);q=dict(other.properties)
            if q['facing']!=facing or q['type']!=('right' if side=='left' else 'left'):
                raise ValueError('Double chest halves disagree on their facing or side')
            out.update(pairx=nbt.Tag(nbt.INT,pair[0]),pairz=nbt.Tag(nbt.INT,pair[2]),pairlead=nbt.Tag(nbt.BYTE,int(side=='right')))
        p['type']='single'
        base,layers=translator.block(Block(block.name,tuple(p.items())))
    else:
        facing=p['minecraft:cardinal_direction'];pair,lead=link(f,position)
        incoming=[]
        if get is not None and get_entity is not None:
            for delta in DELTAS:
                other_pos=tuple(a+b for a,b in zip(position,delta));other=get(other_pos)
                if other is not None and other.name==block.name:
                    target,_=cached_link(translator,get_entity(other_pos),other_pos)
                    if target==position:incoming.append(other_pos)
        if len(incoming)>1 or pair is not None and any(other!=pair for other in incoming):
            raise ValueError('Multiple or conflicting chest pair links')
        if pair is None and incoming:pair=incoming[0]
        side='single'
        if pair is not None:
            choices={paired_position(position,facing,s):s for s in ('left','right')}
            if pair not in choices:raise ValueError('Chest pair must be adjacent and perpendicular to its facing')
            side=choices[pair];other=get(pair) if get else None
            if other is None or other.name!=block.name:raise ValueError('Double chest translation requires both matching halves')
            q=dict(translator.source.validate(other).properties)
            if q['minecraft:cardinal_direction']!=facing:raise ValueError('Chest pair faces a different direction')
            backlink,other_lead=cached_link(translator,get_entity(pair) if get_entity else None,pair)
            if backlink is not None and backlink!=position:raise ValueError('Chest pair has a conflicting backlink')
            if backlink is None and not lead:raise ValueError('Chest pair has no leader or reciprocal link')
            if backlink is not None and lead==other_lead:raise ValueError('Chest pair must have exactly one leader')
        base,layers=translator.block(block)
        props=dict(base.properties);props['type']=side;base=translator.target.block(base.name,props)
    return base,layers,out
