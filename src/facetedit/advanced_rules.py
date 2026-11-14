"""Explicit remaining current-profile state families; contextual fields are
resolved by the cell/structure passes rather than embedded in block names."""
SIX=('down','up','north','south','west','east')
PISTON=('down','up','south','north','east','west')
HORIZONTAL=('south','west','north','east')
SIDES=('north','east','south','west')
PHASES=('inactive','active','cooldown')
TRIAL=('inactive','waiting_for_players','active','waiting_for_reward_ejection','ejecting_reward','cooldown')
GROWING={'kelp':'kelp_age','twisting_vines':'twisting_vines_age','weeping_vines':'weeping_vines_age'}
ALIASES={'frogspawn':'frog_spawn','small_dripleaf':'small_dripleaf_block','tripwire':'trip_wire','moving_piston':'moving_block'}
REVERSE={v:k for k,v in ALIASES.items()}


def flag(value):return str(bool(value)).lower()


def mushroom_faces(bits):
    if bits==0:return set()
    if 1<=bits<=9:
        row,col=divmod(bits-1,3);sides={'up'}
        if row!=1:sides.add('north' if row==0 else 'south')
        if col!=1:sides.add('west' if col==0 else 'east')
        return sides
    if bits==10:return set(SIDES)
    if bits in (14,15):return set(SIX)
    raise ValueError('Unused native mushroom face encoding')


def to_bedrock(name,p):
    target=ALIASES.get(name,name);out={}
    if name in ('frogspawn','end_gateway'):pass
    elif name in ('melon_stem','pumpkin_stem'):out.update(growth=p.pop('age'),facing_direction='0')
    elif name in ('attached_melon_stem','attached_pumpkin_stem'):
        target=name.removeprefix('attached_');out.update(growth='7',facing_direction=str(SIX.index(p.pop('facing'))))
    elif name in ('bee_nest','beehive'):out.update(direction=str(HORIZONTAL.index(p.pop('facing'))),honey_level=p.pop('honey_level'))
    elif name=='bell':
        if p.pop('powered')!='false':raise ValueError('Bell power requires redstone context; native toggle_bit records ring events, not power')
        out.update(direction=str(HORIZONTAL.index(p.pop('facing'))),toggle_bit='false',
                   attachment={'floor':'standing','ceiling':'hanging','single_wall':'side','double_wall':'multiple'}[p.pop('attachment')])
    elif name in ('big_dripleaf','big_dripleaf_stem'):
        target='big_dripleaf';out.update({'minecraft:cardinal_direction':p.pop('facing'),'big_dripleaf_head':flag(name=='big_dripleaf'),
            'big_dripleaf_tilt':{'none':'none','unstable':'unstable','partial':'partial_tilt','full':'full_tilt'}[p.pop('tilt','none')]})
    elif name in ('brown_mushroom_block','red_mushroom_block','mushroom_stem'):
        faces={side for side in SIX if p.pop(side)=='true'}
        choices=(10,15) if name=='mushroom_stem' else (*range(10),14)
        values=[bits for bits in choices if mushroom_faces(bits)==faces]
        if not values:raise ValueError('This mushroom face combination has no native Bedrock encoding')
        out['huge_mushroom_bits']=str(values[0])
    elif name in ('sculk_sensor','calibrated_sculk_sensor'):
        if p.pop('power')!='0':raise ValueError('Active sculk power requires vibration payload migration')
        out['sculk_sensor_phase']=str(PHASES.index(p.pop('sculk_sensor_phase')))
        if name.startswith('calibrated_'):out['minecraft:cardinal_direction']=p.pop('facing')
    elif name in ('campfire','soul_campfire'):
        p.pop('signal_fire');out.update({'minecraft:cardinal_direction':p.pop('facing'),'extinguished':flag(p.pop('lit')=='false')})
    elif name in ('cave_vines','cave_vines_plant'):
        berries=p.pop('berries')=='true';body=name.endswith('_plant')
        target='cave_vines_'+('body' if body else 'head')+'_with_berries' if berries else 'cave_vines'
        out['growing_plant_age']=p.pop('age','0')
    elif name in ('command_block','chain_command_block','repeating_command_block'):
        out.update(conditional_bit=p.pop('conditional'),facing_direction=str(SIX.index(p.pop('facing'))))
    elif name=='chiseled_bookshelf':
        out.update(direction=str(HORIZONTAL.index(p.pop('facing'))),books_stored=str(sum(1<<i for i in range(6) if p.pop(f'slot_{i}_occupied')=='true')))
    elif name=='chorus_plant':
        for side in SIX:p.pop(side)
    elif name=='decorated_pot':
        if p.pop('cracked')!='false':raise ValueError('Cracked decorated-pot state has no native Bedrock property')
        out['direction']=str(SIDES.index(p.pop('facing')))
    elif name=='ender_chest':out['minecraft:cardinal_direction']=p.pop('facing')
    elif name=='fire':
        out['age']=p.pop('age')
        for side in (*SIDES,'up'):p.pop(side)
    elif name=='jigsaw':
        front,top=p.pop('orientation').split('_');rotation=SIDES.index(top) if top!='up' else 0
        if front=='down':rotation=(-rotation)%4
        out.update(facing_direction=str(SIX.index(front)),rotation=str(rotation))
    elif name=='jukebox':
        if p.pop('has_record')!='false':raise ValueError('Jukebox record presence requires its item payload')
    elif name.removesuffix('_plant') in GROWING:
        target=name.removesuffix('_plant');out[GROWING[target]]=p.pop('age','25')
    elif name=='lectern':
        if p.pop('has_book')!='false':raise ValueError('Lectern book presence requires its item payload')
        out.update({'minecraft:cardinal_direction':p.pop('facing'),'powered_bit':p.pop('powered')})
    elif name=='lever':
        face,facing=p.pop('face'),p.pop('facing')
        out.update(open_bit=p.pop('powered'),lever_direction=facing if face=='wall' else ('up_' if face=='floor' else 'down_')+('north_south' if facing in ('north','south') else 'east_west'))
    elif name=='pale_hanging_moss':out['tip']=p.pop('tip')
    elif name=='pale_moss_carpet':
        out['upper_block_bit']=p.pop('bottom')
        out.update({'pale_moss_carpet_side_'+side:{'none':'none','low':'short','tall':'tall'}[p.pop(side)] for side in SIDES})
    elif name=='pink_petals':out.update({'minecraft:cardinal_direction':p.pop('facing'),'growth':str(int(p.pop('flower_amount'))-1)})
    elif name in ('piston','sticky_piston'):
        if p.pop('extended')!='false':raise ValueError('Extended piston requires its native arm payload')
        out['facing_direction']=str(PISTON.index(p.pop('facing')))
    elif name=='piston_head':
        if p.pop('short')!='false':raise ValueError('Short piston head requires active movement context')
        target=('sticky_' if p.pop('type')=='sticky' else '')+'piston_arm_collision';out['facing_direction']=str(PISTON.index(p.pop('facing')))
    elif name=='pitcher_crop':out.update(growth=p.pop('age'),upper_block_bit=flag(p.pop('half')=='upper'))
    elif name=='redstone_wire':
        out['redstone_signal']=p.pop('power')
        for side in SIDES:p.pop(side)
    elif name=='scaffolding':p.pop('bottom');out.update(stability=p.pop('distance'),stability_check='true')
    elif name=='small_dripleaf':out.update({'minecraft:cardinal_direction':p.pop('facing'),'upper_block_bit':flag(p.pop('half')=='upper')})
    elif name=='structure_block':out['structure_block_type']=p.pop('mode')
    elif name in ('suspicious_sand','suspicious_gravel'):out.update(brushed_progress=p.pop('dusted'),hanging='false')
    elif name=='trial_spawner':out.update(ominous=p.pop('ominous'),trial_spawner_state=str(TRIAL.index(p.pop('trial_spawner_state'))))
    elif name=='tripwire':
        out.update(attached_bit=p.pop('attached'),disarmed_bit=p.pop('disarmed'),powered_bit=p.pop('powered'),suspended_bit='true')
        for side in SIDES:p.pop(side)
    elif name=='vault':out.update({'minecraft:cardinal_direction':p.pop('facing'),'ominous':p.pop('ominous'),'vault_state':p.pop('vault_state')})
    else:return None
    return target,out


def to_java(name,p):
    target=REVERSE.get(name,name);out={}
    if name in ('frog_spawn','end_gateway'):pass
    elif name in ('melon_stem','pumpkin_stem'):
        growth,face=p.pop('growth'),int(p.pop('facing_direction'))
        if face==0:out['age']=growth
        elif face>=2 and growth=='7':target='attached_'+name;out['facing']=SIX[face]
        else:raise ValueError('Stem attachment and growth are inconsistent')
    elif name in ('bee_nest','beehive'):out.update(facing=HORIZONTAL[int(p.pop('direction'))],honey_level=p.pop('honey_level'))
    elif name=='bell':
        if p.pop('toggle_bit')!='false':raise ValueError('Bell ring-event toggle has no equivalent Java saved state')
        out.update(facing=HORIZONTAL[int(p.pop('direction'))],powered='false',attachment={'standing':'floor','hanging':'ceiling','side':'single_wall','multiple':'double_wall'}[p.pop('attachment')])
    elif name=='big_dripleaf':
        head=p.pop('big_dripleaf_head')=='true';tilt=p.pop('big_dripleaf_tilt');out['facing']=p.pop('minecraft:cardinal_direction')
        if head:out['tilt']={'none':'none','unstable':'unstable','partial_tilt':'partial','full_tilt':'full'}[tilt]
        elif tilt=='none':target='big_dripleaf_stem'
        else:raise ValueError('A dripleaf stem cannot retain a head tilt')
    elif name in ('brown_mushroom_block','red_mushroom_block','mushroom_stem'):
        bits=int(p.pop('huge_mushroom_bits'));faces=mushroom_faces(bits)
        if name=='mushroom_stem' and bits not in (10,15):raise ValueError('Noncanonical native mushroom-stem face encoding')
        if bits in (10,15):target='mushroom_stem'
        out={side:flag(side in faces) for side in SIX}
    elif name in ('sculk_sensor','calibrated_sculk_sensor'):
        out.update(power='0',sculk_sensor_phase=PHASES[int(p.pop('sculk_sensor_phase'))])
        if name.startswith('calibrated_'):out['facing']=p.pop('minecraft:cardinal_direction')
    elif name in ('campfire','soul_campfire'):out.update(facing=p.pop('minecraft:cardinal_direction'),lit=flag(p.pop('extinguished')=='false'),signal_fire='false')
    elif name in ('cave_vines','cave_vines_head_with_berries','cave_vines_body_with_berries'):
        age=p.pop('growing_plant_age');body=name=='cave_vines_body_with_berries';target='cave_vines_plant' if body else 'cave_vines';out['berries']=flag(name!='cave_vines')
        if not body:out['age']=age
        elif age!='0':raise ValueError('Cave-vine body age has no Java property')
    elif name in ('command_block','chain_command_block','repeating_command_block'):out.update(conditional=p.pop('conditional_bit'),facing=SIX[int(p.pop('facing_direction'))])
    elif name=='chiseled_bookshelf':
        bits=int(p.pop('books_stored'));out.update(facing=HORIZONTAL[int(p.pop('direction'))],**{f'slot_{i}_occupied':flag(bits&(1<<i)) for i in range(6)})
    elif name=='chorus_plant':out={side:'false' for side in SIX}
    elif name=='decorated_pot':out.update(cracked='false',facing=SIDES[int(p.pop('direction'))])
    elif name=='ender_chest':out['facing']=p.pop('minecraft:cardinal_direction')
    elif name=='fire':out.update(age=p.pop('age'),**{side:'false' for side in (*SIDES,'up')})
    elif name=='jigsaw':
        front=SIX[int(p.pop('facing_direction'))];rotation=int(p.pop('rotation'))
        if front in ('up','down'):top=SIDES[rotation if front=='up' else (-rotation)%4]
        elif rotation==0:top='up'
        else:raise ValueError('Horizontal jigsaw rotation has no matching Java orientation')
        out['orientation']=front+'_'+top
    elif name=='jukebox':out['has_record']='false'
    elif name in GROWING:
        age=p.pop(GROWING[name])
        if age=='25':target=name+'_plant'
        else:out['age']=age
    elif name=='lectern':out.update(facing=p.pop('minecraft:cardinal_direction'),powered=p.pop('powered_bit'),has_book='false')
    elif name=='lever':
        direction=p.pop('lever_direction');out['powered']=p.pop('open_bit')
        if direction in SIDES:out.update(face='wall',facing=direction)
        else:out.update(face='floor' if direction.startswith('up_') else 'ceiling',facing='north' if direction.endswith('north_south') else 'east')
    elif name=='pale_hanging_moss':out['tip']=p.pop('tip')
    elif name=='pale_moss_carpet':out.update(bottom=p.pop('upper_block_bit'),**{side:{'none':'none','short':'low','tall':'tall'}[p.pop('pale_moss_carpet_side_'+side)] for side in SIDES})
    elif name=='pink_petals':out.update(facing=p.pop('minecraft:cardinal_direction'),flower_amount=str(int(p.pop('growth'))+1))
    elif name in ('piston','sticky_piston'):out.update(facing=PISTON[int(p.pop('facing_direction'))],extended='false')
    elif name in ('piston_arm_collision','sticky_piston_arm_collision'):target='piston_head';out.update(facing=PISTON[int(p.pop('facing_direction'))],short='false',type='sticky' if name.startswith('sticky_') else 'normal')
    elif name=='pitcher_crop':out.update(age=p.pop('growth'),half='upper' if p.pop('upper_block_bit')=='true' else 'lower')
    elif name=='redstone_wire':out.update(power=p.pop('redstone_signal'),**{side:'none' for side in SIDES})
    elif name=='scaffolding':
        out.update(distance=p.pop('stability'),bottom='false')
        if p.pop('stability_check')!='true':raise ValueError('Scaffolding with disabled stability checks has no Java state')
    elif name=='small_dripleaf_block':out.update(facing=p.pop('minecraft:cardinal_direction'),half='upper' if p.pop('upper_block_bit')=='true' else 'lower')
    elif name=='structure_block':out['mode']=p.pop('structure_block_type')
    elif name in ('suspicious_sand','suspicious_gravel'):
        out['dusted']=p.pop('brushed_progress')
        if p.pop('hanging')!='false':raise ValueError('Falling brushable block requires moving-entity context')
    elif name=='trial_spawner':out.update(ominous=p.pop('ominous'),trial_spawner_state=TRIAL[int(p.pop('trial_spawner_state'))])
    elif name=='trip_wire':
        p.pop('suspended_bit');out.update(attached=p.pop('attached_bit'),disarmed=p.pop('disarmed_bit'),powered=p.pop('powered_bit'),**{side:'false' for side in SIDES})
    elif name=='vault':out.update(facing=p.pop('minecraft:cardinal_direction'),ominous=p.pop('ominous'),vault_state=p.pop('vault_state'))
    else:return None
    return target,out
