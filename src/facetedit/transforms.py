"""Independent cardinal state transforms; state types are retained verbatim."""

DIRECTIONS=('north','east','south','west')
RAILS=('north_south','east_west','ascending_east','ascending_west','ascending_north','ascending_south','south_east','south_west','north_west','north_east')


def horizontal(value,turns,mirror):
    if value not in DIRECTIONS:return value
    index=DIRECTIONS.index(value)
    return DIRECTIONS[((-index if mirror else index)+turns)%4]


def point(position,size,turns=0,mirror=False):
    x,y,z=position;w,_,d=size
    if mirror:x=w-1-x
    for _ in range(turns%4):x,z,w,d=d-1-z,x,d,w
    return x,y,z


def state_properties(block,turns=0,mirror=False,edition='Java'):
    props=dict(block.properties);turns%=4
    direction=lambda value:horizontal(value,turns,mirror)
    for key in ('facing','block_face','torch_facing_direction','minecraft:cardinal_direction','minecraft:facing_direction'):
        if key in props:props[key]=direction(props[key])
    for key in ('axis','pillar_axis'):
        if turns%2 and props.get(key) in ('x','z'):props[key]='z' if props[key]=='x' else 'x'
    for key in ('rotation','ground_sign_direction'):
        if key in props:
            r=int(props[key]);props[key]=str(((-r if mirror else r)+4*turns)%16)
    if 'orientation' in props:props['orientation']='_'.join(direction(v) for v in props['orientation'].split('_'))
    def rail(value):
        if value.startswith('ascending_'):return 'ascending_'+direction(value[10:])
        parts={direction(p) for p in value.split('_')}
        return next((s for s in RAILS if set(s.split('_'))==parts),value)
    if 'shape' in props:
        shape=props['shape']
        if shape in RAILS:props['shape']=rail(shape)
        elif mirror and shape.endswith(('_left','_right')):
            prefix,side=shape.rsplit('_',1);props['shape']=prefix+('_right' if side=='left' else '_left')
    if mirror:
        for key in ('hinge','type'):
            if props.get(key) in ('left','right'):props[key]='right' if props[key]=='left' else 'left'
    if edition=='Bedrock':
        def numeric(key,values):
            if key in props:
                index=int(props[key])
                if not 0<=index<len(values):raise ValueError('Invalid directional block state '+key)
                props[key]=str(values.index(direction(values[index])))
        numeric('facing_direction',('down','up','north','south','west','east'))
        numeric('weirdo_direction',('east','west','south','north'))
        # Doors and trapdoors expose a different numeric order from repeaters.
        order=('east','south','west','north') if block.name.endswith('_door') else ('south','west','north','east')
        if block.name.endswith('trapdoor'):order=('east','west','south','north')
        numeric('direction',order)
        if 'rail_direction' in props:
            value=int(props['rail_direction'])
            if not 0<=value<len(RAILS):raise ValueError('Invalid rail direction')
            props['rail_direction']=str(RAILS.index(rail(RAILS[value])))
        if 'vine_direction_bits' in props:
            value=int(props['vine_direction_bits']);result=0;order=('south','west','north','east')
            for i,d in enumerate(order):
                if value&(1<<i):result|=1<<order.index(direction(d))
            props['vine_direction_bits']=str(result)
        if mirror and 'door_hinge_bit' in props:props['door_hinge_bit']='false' if props['door_hinge_bit']=='true' else 'true'
        if 'huge_mushroom_bits' in props and 1<=int(props['huge_mushroom_bits'])<=9:
            i=int(props['huge_mushroom_bits'])-1;x,z=i%3,i//3
            x,_,z=point((x,0,z),(3,1,3),turns,mirror);props['huge_mushroom_bits']=str(z*3+x+1)
    return {direction(k):v for k,v in props.items()},{direction(k):v for k,v in block.state_types}
