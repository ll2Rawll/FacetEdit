"""Neighbour-derived states absent from the other edition's native palette."""
from .blocks import AIR
from .state_facts import facts,FACES
from .advanced_rules import GROWING

DELTAS={'down':(0,-1,0),'up':(0,1,0),'north':(0,0,-1),'east':(1,0,0),'south':(0,0,1),'west':(-1,0,0)}
SIDES=('north','east','south','west')
OPPOSITE={'north':'south','south':'north','east':'west','west':'east'}
CONTEXT_BLOCKS=frozenset('minecraft:'+name for name in ('campfire','soul_campfire','chorus_plant','fire','redstone_wire','tripwire',
    'scaffolding','cave_vines','cave_vines_plant',*GROWING,*(name+'_plant' for name in GROWING)))


def shifted(position,side):return tuple(a+b for a,b in zip(position,DELTAS[side]))
def sturdy(block,side):return bool(facts(block)[0]&(1<<FACES.index(side)))
def flammable(block):return facts(block)[8]


def wire_connections(position,get):
    result={};open_above=not facts(get(shifted(position,'up')))[6]
    for side in SIDES:
        adjacent=shifted(position,side);block=get(adjacent);data=facts(block)
        support=sturdy(block,'up') or block.name=='minecraft:hopper'
        if open_above and (block.name.endswith('trapdoor') or support) and facts(get(shifted(adjacent,'up')))[10]:
            result[side]='up' if sturdy(block,OPPOSITE[side]) else 'side'
        elif data[9]&(1<<FACES.index(side)):result[side]='side'
        elif not data[6] and facts(get(shifted(adjacent,'down')))[10]:result[side]='side'
        else:result[side]='none'
    # One connection renders a line; perpendicular junctions retain only their
    # occupied arms. An isolated wire retains Java's dot representation.
    ns=any(result[s]!='none' for s in ('north','south'))
    ew=any(result[s]!='none' for s in ('east','west'))
    if ns and not ew:
        for side in ('north','south'):
            if result[side]=='none':result[side]='side'
    elif ew and not ns:
        for side in ('east','west'):
            if result[side]=='none':result[side]='side'
    return result


def apply_context(translator,clip,blocks,extras,entities,source_at,entity_at,report,cancelled,canonical=None):
    source,target=translator.source,translator.target
    if canonical is None:canonical=blocks if target.edition=='Java' else {p:source.validate(clip.blocks[p],defaults=True) for p in blocks}
    pending=[(p,b) for p,b in canonical.items() if b.name in CONTEXT_BLOCKS]
    if not pending:return
    cache={}
    def get(position):
        if position in canonical:return canonical[position]
        if position not in cache:
            native=source_at(position)
            value=AIR if native is None else source.validate(native,defaults=True) if source.edition=='Java' else translator.cell(native,entity=entity_at(position),position=position)[0]
            if len(cache)<16384:cache[position]=value
            return value
        return cache[position]
    for index,(pos,block) in enumerate(pending):
        if index%256==0 and cancelled():raise InterruptedError('Neighbour translation cancelled')
        name=block.name.removeprefix('minecraft:');props=dict(block.properties);changed={};new_name=name
        try:
            if name in ('campfire','soul_campfire'):
                changed['signal_fire']=str(get(shifted(pos,'down')).name=='minecraft:hay_block').lower()
            elif name=='chorus_plant':
                for side in DELTAS:
                    other=get(shifted(pos,side)).name
                    changed[side]=str(other in ('minecraft:chorus_plant','minecraft:chorus_flower') or side=='down' and other=='minecraft:end_stone').lower()
            elif name=='fire':
                below=get(shifted(pos,'down'));supported=sturdy(below,'up') or flammable(below)
                changed={side:str(not supported and flammable(get(shifted(pos,side)))).lower() for side in (*SIDES,'up')}
            elif name=='redstone_wire':changed=wire_connections(pos,get)
            elif name=='tripwire':
                for side in SIDES:
                    other=get(shifted(pos,side));p=dict(other.properties)
                    changed[side]=str(other.name=='minecraft:tripwire' or other.name=='minecraft:tripwire_hook' and p.get('facing')==OPPOSITE[side]).lower()
                if target.edition=='Bedrock':
                    native=blocks[pos];p=dict(native.properties);p['suspended_bit']=str(not sturdy(get(shifted(pos,'down')),'up')).lower()
                    blocks[pos]=target.block(native.name,p)
            elif name=='scaffolding':changed['bottom']=str(props['distance']!='0' and get(shifted(pos,'down')).name!='minecraft:scaffolding').lower()
            elif name.removesuffix('_plant') in GROWING:
                family=name.removesuffix('_plant');side='down' if family=='weeping_vines' else 'up'
                other=get(shifted(pos,side));body=other.name.removeprefix('minecraft:').removesuffix('_plant')==family
                if source.edition=='Bedrock':
                    native_props=dict(clip.blocks[pos].properties)
                    if native_props[GROWING[family]]=='25':
                        new_name=family+'_plant' if body else family;props={} if body else {'age':'25'}
                elif name.endswith('_plant') or props.get('age')=='25':
                    if body!=name.endswith('_plant'):raise ValueError('Plant terminal/body state needs matching growth-direction neighbours')
                report.notes.add('Plant terminal/body forms are derived from available neighbours where native encodings coincide.')
            elif name in ('cave_vines','cave_vines_plant'):
                native=clip.blocks[pos] if source.edition=='Bedrock' else blocks[pos]
                if native.name=='minecraft:cave_vines' and dict(native.properties)['growing_plant_age']=='0':
                    body=get(shifted(pos,'down')).name in ('minecraft:cave_vines','minecraft:cave_vines_plant')
                    if source.edition=='Bedrock':new_name='cave_vines_plant' if body else 'cave_vines';props={'berries':'false',**({} if body else {'age':'0'})}
                    elif body!=(name=='cave_vines_plant'):raise ValueError('Cave-vine body state needs its continuation below')
                report.notes.add('Unfruited cave-vine bodies are derived from available neighbours where native encodings coincide.')
            else:continue
            if target.edition=='Java':
                props.update(changed);blocks[pos]=target.block('minecraft:'+new_name,props)
            elif any(props[key]!=value for key,value in changed.items()):
                raise ValueError(name+' state disagrees with its neighbours: '+', '.join(key for key,value in changed.items() if props[key]!=value))
        except (ValueError,KeyError,IndexError) as exc:report.issue('Context: '+str(exc),pos)
