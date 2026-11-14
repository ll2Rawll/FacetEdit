"""Independent cardinal state transforms; state types are retained verbatim."""

DIRECTIONS=('north','east','south','west')
RAILS=('north_south','east_west','ascending_east','ascending_west','ascending_north','ascending_south','south_east','south_west','north_west','north_east')
PISTON_FACING=frozenset('minecraft:'+n for n in ('end_rod','piston','sticky_piston','piston_arm_collision','sticky_piston_arm_collision'))


def native_facing_order(block):
    return ('down','up','south','north','east','west') if block.name in PISTON_FACING else ('down','up','north','south','west','east')


def jigsaw_axes(props,edition):
    if edition=='Java':return props['orientation'].split('_')
    front=('down','up','north','south','west','east')[int(props['facing_direction'])];rotation=int(props['rotation'])
    if front in ('up','down'):return front,DIRECTIONS[rotation if front=='up' else -rotation%4]
    if rotation!=0:raise ValueError('Horizontal jigsaw rotation has no canonical orientation')
    return front,'up'


def jigsaw_states(front,top,edition):
    if not (front in ('up','down') and top in DIRECTIONS or front in DIRECTIONS and top=='up'):
        raise ValueError('This jigsaw cannot represent the tilted front/top orientation')
    if edition=='Java':return {'orientation':front+'_'+top}
    rotation=DIRECTIONS.index(top) if top in DIRECTIONS else 0
    return {'facing_direction':str(('down','up','north','south','west','east').index(front)),
            'rotation':str(-rotation%4 if front=='down' else rotation)}


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
    if block.name=='minecraft:jigsaw':
        front,top=jigsaw_axes(props,edition)
        return jigsaw_states(direction(front),direction(top),edition),dict(block.state_types)
    for key in ('facing','block_face','torch_facing_direction','minecraft:cardinal_direction','minecraft:facing_direction','minecraft:block_face'):
        if key in props:props[key]=direction(props[key])
    for key in ('axis','pillar_axis','portal_axis'):
        if turns%2 and props.get(key) in ('x','z'):props[key]='z' if props[key]=='x' else 'x'
    for key in ('rotation','ground_sign_direction'):
        if key in props:
            if key=='ground_sign_direction' and edition=='Bedrock' and block.name.endswith('_hanging_sign') and props.get('attached_bit')=='false':continue
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
        if block.name=='minecraft:chiseled_bookshelf':
            old=dict(props)
            if edition=='Java':
                for i in range(6):props[f'slot_{i}_occupied']=old[f'slot_{i//3*3+2-i%3}_occupied']
            elif 'books_stored' in props:
                bits=int(props['books_stored']);props['books_stored']=str(sum(1<<(i//3*3+2-i%3) for i in range(6) if bits&(1<<i)))
    if edition=='Bedrock':
        def numeric(key,values):
            if key in props:
                index=int(props[key])
                if not 0<=index<len(values):raise ValueError('Invalid directional block state '+key)
                props[key]=str(values.index(direction(values[index])))
        numeric('facing_direction',native_facing_order(block))
        numeric('coral_direction',('west','east','north','south'))
        numeric('weirdo_direction',('east','west','south','north'))
        # Doors and trapdoors expose a different numeric order from repeaters.
        order=('east','south','west','north') if block.name.endswith('_door') else ('south','west','north','east')
        if block.name.endswith('trapdoor'):order=('east','west','south','north')
        if block.name=='minecraft:decorated_pot':order=DIRECTIONS
        if not (block.name.endswith('_door') and props.get('upper_block_bit')=='true'):numeric('direction',order)
        if 'lever_direction' in props:
            lever=props['lever_direction']
            if lever in DIRECTIONS:props['lever_direction']=direction(lever)
            elif turns%2:
                prefix='up_' if lever.startswith('up_') else 'down_'
                props['lever_direction']=prefix+('east_west' if lever.endswith('north_south') else 'north_south')
        for prefix in ('wall_connection_type_','pale_moss_carpet_side_'):
            values={side:props[prefix+side] for side in DIRECTIONS if prefix+side in props}
            for side,value in values.items():props[prefix+direction(side)]=value
        if 'rail_direction' in props:
            value=int(props['rail_direction'])
            if not 0<=value<len(RAILS):raise ValueError('Invalid rail direction')
            props['rail_direction']=str(RAILS.index(rail(RAILS[value])))
        if 'vine_direction_bits' in props:
            value=int(props['vine_direction_bits']);result=0;order=('south','west','north','east')
            for i,d in enumerate(order):
                if value&(1<<i):result|=1<<order.index(direction(d))
            props['vine_direction_bits']=str(result)
        if 'multi_face_direction_bits' in props:
            value=int(props['multi_face_direction_bits']);order=('down','up','south','west','north','east')
            props['multi_face_direction_bits']=str(sum(1<<order.index(direction(side)) for i,side in enumerate(order) if value&(1<<i)))
        if mirror and 'door_hinge_bit' in props and props.get('upper_block_bit')!='false':props['door_hinge_bit']='false' if props['door_hinge_bit']=='true' else 'true'
        if 'huge_mushroom_bits' in props and 1<=int(props['huge_mushroom_bits'])<=9:
            i=int(props['huge_mushroom_bits'])-1;x,z=i%3,i//3
            x,_,z=point((x,0,z),(3,1,3),turns,mirror);props['huge_mushroom_bits']=str(z*3+x+1)
    return {direction(k):v for k,v in props.items()},{direction(k):v for k,v in block.state_types}
