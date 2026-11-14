"""Additional explicit native-state families for the pinned conversion profiles.

Helpers consume only states they implement. The caller validates every remaining
property and target schema. Context and block NBT are handled at the cell layer.
"""
SIX=('down','up','north','south','west','east')
END_ROD=('down','up','south','north','east','west')
HORIZONTAL=('south','west','north','east')
SIDES=('north','east','south','west')
ALIASES={'bricks':'brick_block','end_stone_bricks':'end_bricks','nether_bricks':'nether_brick',
         'red_nether_bricks':'red_nether_brick','melon':'melon_block','dead_bush':'deadbush',
         'lily_pad':'waterlily','terracotta':'hardened_clay','slime_block':'slime',
         'rooted_dirt':'dirt_with_roots','waxed_copper_block':'waxed_copper','nether_quartz_ore':'quartz_ore',
         'spawner':'mob_spawner','flowering_azalea_leaves':'azalea_leaves_flowered','stonecutter':'stonecutter_block',
         'light_gray_glazed_terracotta':'silver_glazed_terracotta'}
REVERSE={v:k for k,v in ALIASES.items()}
PLAIN_ALIASES=set(ALIASES)-{'flowering_azalea_leaves','stonecutter','light_gray_glazed_terracotta'}
WATER_ONLY={'barrier','conduit','hanging_roots','heavy_core','mangrove_roots'}
ALWAYS_WATER={'kelp','kelp_plant','seagrass','tall_seagrass','bubble_column'}
FACE_BLOCKS={'amethyst_cluster','small_amethyst_bud','medium_amethyst_bud','large_amethyst_bud'}
MULTIFACE={'glow_lichen','sculk_vein','resin_clump'}
FACE_BITS=('down','up','south','west','north','east')
AGE_MAPS={'sweet_berry_bush':('0','2','4','7'),'torchflower_crop':('0','1')}


def boolean(value):return str(bool(value)).lower()


def to_bedrock(name,p,water=False):
    from .advanced_rules import to_bedrock as advanced
    result=advanced(name,p)
    if result is not None:return result
    target=ALIASES.get(name,name);out={}
    if name in PLAIN_ALIASES or name in WATER_ONLY or name.endswith('copper_grate'):
        pass
    elif name in ('chiseled_quartz_block','purpur_block'):
        out['pillar_axis']='y'
    elif name=='pumpkin':
        out['minecraft:cardinal_direction']='north'
    elif name in ('hay_block','bone_block'):
        out.update(pillar_axis=p.pop('axis'),deprecated='0')
    elif name=='flowering_azalea_leaves':
        p.pop('distance');out.update(persistent_bit=p.pop('persistent'),update_bit='false')
    elif name in FACE_BLOCKS:
        out['minecraft:block_face']=p.pop('facing')
    elif name in ('anvil','chipped_anvil','damaged_anvil','stonecutter'):
        out['minecraft:cardinal_direction']=p.pop('facing')
    elif name=='end_rod':out['facing_direction']=str(END_ROD.index(p.pop('facing')))
    elif name=='bamboo_sapling':out['age_bit']='false'
    elif name=='mangrove_propagule':
        if p.pop('stage')!='0':raise ValueError('Mangrove growth stage has no exact native state')
        out.update(hanging=p.pop('hanging'),propagule_stage=p.pop('age'))
    elif name.endswith('_fence') or name.endswith('_glass_pane') or name in ('glass_pane','iron_bars'):
        for side in SIDES:p.pop(side)
    elif name.endswith('_wall_hanging_sign'):
        target=name.replace('_wall_hanging_sign','_hanging_sign')
        out.update(attached_bit='false',facing_direction=str(SIX.index(p.pop('facing'))),ground_sign_direction='0',hanging='false')
    elif name.endswith('_hanging_sign'):
        attached=p.pop('attached');rotation=int(p.pop('rotation'))
        if attached=='false' and rotation%4:raise ValueError('Unattached hanging sign cannot retain a non-cardinal rotation in Bedrock')
        out.update(attached_bit=attached,ground_sign_direction=str(rotation) if attached=='true' else '0',hanging='true',
                   facing_direction='0' if attached=='true' else str(SIX.index(HORIZONTAL[rotation//4])))
    elif name.endswith('_glazed_terracotta'):
        out['facing_direction']=str(SIX.index(p.pop('facing')))
    elif name in ('dispenser','dropper'):
        out.update(facing_direction=str(SIX.index(p.pop('facing'))),triggered_bit=p.pop('triggered'))
    elif name=='hopper':
        out.update(facing_direction=str(SIX.index(p.pop('facing'))),toggle_bit=p.pop('enabled'))
    elif name=='brewing_stand':
        out={f'brewing_stand_slot_{letter}_bit':p.pop('has_bottle_'+str(i)) for i,letter in enumerate('abc')}
    elif name=='observer':
        out.update({'minecraft:facing_direction':p.pop('facing'),'powered_bit':p.pop('powered')})
    elif name in ('lantern','soul_lantern'):
        out['hanging']=p.pop('hanging')
    elif name=='lightning_rod':
        if p.pop('powered')!='false':raise ValueError('Powered lightning rod needs a target power payload')
        out['facing_direction']=str(SIX.index(p.pop('facing')))
    elif name=='end_portal_frame':
        out.update({'minecraft:cardinal_direction':p.pop('facing'),'end_portal_eye_bit':p.pop('eye')})
    elif name=='nether_portal':
        target='portal';out['portal_axis']=p.pop('axis')
    elif name=='cake':out['bite_counter']=p.pop('bites')
    elif name in ('chorus_flower','nether_wart','frosted_ice'):out['age']=p.pop('age')
    elif name in AGE_MAPS:out['growth']=AGE_MAPS[name][int(p.pop('age'))]
    elif name=='composter':out['composter_fill_level']=p.pop('level')
    elif name=='respawn_anchor':out['respawn_anchor_charge']=p.pop('charges')
    elif name=='sculk_catalyst':out['bloom']=p.pop('bloom')
    elif name=='sculk_shrieker':out.update(active=p.pop('shrieking'),can_summon=p.pop('can_summon'))
    elif name.endswith('copper_bulb'):out.update(lit=p.pop('lit'),powered_bit=p.pop('powered'))
    elif name=='creaking_heart':out.update(active=p.pop('active'),natural=p.pop('natural'),pillar_axis=p.pop('axis'))
    elif name=='crafter':out.update(crafting=p.pop('crafting'),orientation=p.pop('orientation'),triggered_bit=p.pop('triggered'))
    elif name in ('cauldron','water_cauldron','lava_cauldron','powder_snow_cauldron'):
        target='cauldron';out['cauldron_liquid']='water' if name=='cauldron' else name.removesuffix('_cauldron')
        out['fill_level']='0' if name=='cauldron' else '6' if name=='lava_cauldron' else str(int(p.pop('level'))*2)
    elif name=='daylight_detector':
        target='daylight_detector_inverted' if p.pop('inverted')=='true' else name
        out['redstone_signal']=p.pop('power')
    elif name=='repeater':
        if p.pop('locked')!='false':raise ValueError('Locked repeater state requires neighbour power translation')
        target=('powered_' if p.pop('powered')=='true' else 'unpowered_')+name
        out.update({'minecraft:cardinal_direction':p.pop('facing'),'repeater_delay':str(int(p.pop('delay'))-1)})
    elif name=='comparator':
        powered=p.pop('powered');target=('powered_' if powered=='true' else 'unpowered_')+name
        out.update({'minecraft:cardinal_direction':p.pop('facing'),'output_lit_bit':powered,'output_subtract_bit':boolean(p.pop('mode')=='subtract')})
    elif name in ('loom','cocoa','grindstone','tripwire_hook'):
        out['direction']=str(HORIZONTAL.index(p.pop('facing')))
        if name=='cocoa':out['age']=p.pop('age')
        elif name=='grindstone':out['attachment']={'floor':'standing','ceiling':'hanging','wall':'side'}[p.pop('face')]
        elif name=='tripwire_hook':out.update(attached_bit=p.pop('attached'),powered_bit=p.pop('powered'))
    elif name in ('sniffer_egg','turtle_egg'):
        out['cracked_state']=('no_cracks','cracked','max_cracked')[int(p.pop('hatch'))]
        if name=='turtle_egg':out['turtle_egg_count']=('one_egg','two_egg','three_egg','four_egg')[int(p.pop('eggs'))-1]
    elif name=='pointed_dripstone':
        out.update(hanging=boolean(p.pop('vertical_direction')=='down'),dripstone_thickness=p.pop('thickness').replace('tip_merge','merge'))
    elif name in MULTIFACE:
        out['multi_face_direction_bits']=str(sum(1<<i for i,side in enumerate(FACE_BITS) if p.pop(side)=='true'))
    elif name=='vine':
        if p.pop('up')!='false':raise ValueError('Upward vine attachment needs contextual translation')
        out['vine_direction_bits']=str(sum(1<<i for i,side in enumerate(HORIZONTAL) if p.pop(side)=='true'))
    elif name=='sea_pickle':
        if not water:raise ValueError('Dry sea-pickle native death-state semantics need further verification')
        out.update(cluster_count=str(int(p.pop('pickles'))-1),dead_bit='false')
    elif name in ('seagrass','tall_seagrass'):
        target='seagrass';out['sea_grass_type']='default' if name=='seagrass' else 'double_top' if p.pop('half')=='upper' else 'double_bot'
    elif name=='bubble_column':out['drag_down']=p.pop('drag')
    elif name=='soul_fire':out['age']='0'
    elif name=='target':
        if p.pop('power')!='0':raise ValueError('Powered target block needs a target power payload')
    elif name=='light':target='light_block_'+p.pop('level')
    elif name.endswith('_coral'):
        pass
    elif name.endswith('_coral_wall_fan'):
        out['coral_direction']=str(('west','east','north','south').index(p.pop('facing')))
    elif name.endswith('_coral_fan'):
        out['coral_fan_direction']='0'
    else:return None
    return target,out


def to_java(name,p):
    from .advanced_rules import to_java as advanced
    result=advanced(name,p)
    if result is not None:return result
    target=REVERSE.get(name,name);out={}
    if target in PLAIN_ALIASES or name in WATER_ONLY or name.endswith('copper_grate'):
        pass
    elif name in ('chiseled_quartz_block','purpur_block'):
        if p.pop('pillar_axis')!='y':raise ValueError('Oriented decorative block has no Java state')
    elif name=='pumpkin':
        if p.pop('minecraft:cardinal_direction')!='north':raise ValueError('Oriented uncarved pumpkin cannot retain its direction in Java')
    elif name in ('hay_block','bone_block'):
        out['axis']=p.pop('pillar_axis')
        if p.pop('deprecated')!='0':raise ValueError('Deprecated block state is not canonical')
    elif name=='azalea_leaves_flowered':
        p.pop('update_bit');out.update(persistent=p.pop('persistent_bit'),distance='7')
    elif name in FACE_BLOCKS:out['facing']=p.pop('minecraft:block_face')
    elif name in ('anvil','chipped_anvil','damaged_anvil','stonecutter_block'):out['facing']=p.pop('minecraft:cardinal_direction')
    elif name=='end_rod':out['facing']=END_ROD[int(p.pop('facing_direction'))]
    elif name=='bamboo_sapling':
        if p.pop('age_bit')!='false':raise ValueError('Aged bamboo sapling has no matching Java state')
    elif name=='mangrove_propagule':out.update(hanging=p.pop('hanging'),age=p.pop('propagule_stage'),stage='0')
    elif name.endswith('_fence') or name.endswith('_glass_pane') or name in ('glass_pane','iron_bars'):
        out={side:'false' for side in SIDES}
    elif name.endswith('_hanging_sign'):
        attached,hanging=p.pop('attached_bit'),p.pop('hanging');facing=int(p.pop('facing_direction'));rotation=p.pop('ground_sign_direction')
        if hanging=='true' and attached=='true':
            if facing!=0:raise ValueError('Attached hanging sign has a noncanonical facing direction')
            out.update(attached='true',rotation=rotation)
        else:
            if attached!='false' or rotation!='0' or facing<2:raise ValueError('Hanging sign contains unrepresentable native states')
            if hanging=='true':out.update(attached='false',rotation=str(HORIZONTAL.index(SIX[facing])*4))
            else:target=name.replace('_hanging_sign','_wall_hanging_sign');out['facing']=SIX[facing]
    elif name.endswith('_glazed_terracotta'):out['facing']=SIX[int(p.pop('facing_direction'))]
    elif name in ('dispenser','dropper'):out.update(facing=SIX[int(p.pop('facing_direction'))],triggered=p.pop('triggered_bit'))
    elif name=='hopper':out.update(facing=SIX[int(p.pop('facing_direction'))],enabled=p.pop('toggle_bit'))
    elif name=='brewing_stand':out={f'has_bottle_{i}':p.pop('brewing_stand_slot_'+letter+'_bit') for i,letter in enumerate('abc')}
    elif name=='observer':out.update(facing=p.pop('minecraft:facing_direction'),powered=p.pop('powered_bit'))
    elif name in ('lantern','soul_lantern'):out['hanging']=p.pop('hanging')
    elif name=='lightning_rod':out.update(facing=SIX[int(p.pop('facing_direction'))],powered='false')
    elif name=='end_portal_frame':out.update(facing=p.pop('minecraft:cardinal_direction'),eye=p.pop('end_portal_eye_bit'))
    elif name=='portal':target='nether_portal';out['axis']=p.pop('portal_axis')
    elif name=='cake':out['bites']=p.pop('bite_counter')
    elif name in ('chorus_flower','nether_wart','frosted_ice'):out['age']=p.pop('age')
    elif name in AGE_MAPS:
        growth=p.pop('growth')
        if growth not in AGE_MAPS[name]:raise ValueError('Intermediate growth cannot be preserved as a Java age')
        out['age']=str(AGE_MAPS[name].index(growth))
    elif name=='composter':out['level']=p.pop('composter_fill_level')
    elif name=='respawn_anchor':out['charges']=p.pop('respawn_anchor_charge')
    elif name=='sculk_catalyst':out['bloom']=p.pop('bloom')
    elif name=='sculk_shrieker':out.update(shrieking=p.pop('active'),can_summon=p.pop('can_summon'))
    elif name.endswith('copper_bulb'):out.update(lit=p.pop('lit'),powered=p.pop('powered_bit'))
    elif name=='creaking_heart':out.update(active=p.pop('active'),natural=p.pop('natural'),axis=p.pop('pillar_axis'))
    elif name=='crafter':out.update(crafting=p.pop('crafting'),orientation=p.pop('orientation'),triggered=p.pop('triggered_bit'))
    elif name=='cauldron':
        liquid,level=p.pop('cauldron_liquid'),int(p.pop('fill_level'))
        if level%2 or liquid=='lava' and level not in (0,6):raise ValueError('Partial native cauldron level cannot be preserved in Java')
        if level==0:
            if liquid!='water':raise ValueError('Empty non-water cauldron has no matching Java state')
        else:
            target=liquid+'_cauldron'
            if liquid!='lava':out['level']=str(level//2)
    elif name in ('daylight_detector','daylight_detector_inverted'):
        target='daylight_detector';out.update(inverted=boolean(name.endswith('_inverted')),power=p.pop('redstone_signal'))
    elif name in ('powered_repeater','unpowered_repeater'):
        target='repeater';out.update(powered=boolean(name.startswith('powered_')),facing=p.pop('minecraft:cardinal_direction'),delay=str(int(p.pop('repeater_delay'))+1),locked='false')
    elif name in ('powered_comparator','unpowered_comparator'):
        target='comparator';powered=boolean(name.startswith('powered_'))
        if p.pop('output_lit_bit')!=powered:raise ValueError('Comparator lit flag disagrees with its native identity')
        out.update(powered=powered,facing=p.pop('minecraft:cardinal_direction'),mode='subtract' if p.pop('output_subtract_bit')=='true' else 'compare')
    elif name in ('loom','cocoa','grindstone','tripwire_hook'):
        out['facing']=HORIZONTAL[int(p.pop('direction'))]
        if name=='cocoa':out['age']=p.pop('age')
        elif name=='grindstone':
            attachment=p.pop('attachment')
            if attachment=='multiple':raise ValueError('Multiple grindstone attachment cannot be represented')
            out['face']={'standing':'floor','hanging':'ceiling','side':'wall'}[attachment]
        elif name=='tripwire_hook':out.update(attached=p.pop('attached_bit'),powered=p.pop('powered_bit'))
    elif name in ('sniffer_egg','turtle_egg'):
        out['hatch']=str(('no_cracks','cracked','max_cracked').index(p.pop('cracked_state')))
        if name=='turtle_egg':out['eggs']=str(('one_egg','two_egg','three_egg','four_egg').index(p.pop('turtle_egg_count'))+1)
    elif name=='pointed_dripstone':out.update(vertical_direction='down' if p.pop('hanging')=='true' else 'up',thickness=p.pop('dripstone_thickness').replace('merge','tip_merge'))
    elif name in MULTIFACE:
        bits=int(p.pop('multi_face_direction_bits'));out={side:boolean(bits&(1<<i)) for i,side in enumerate(FACE_BITS)}
    elif name=='vine':
        bits=int(p.pop('vine_direction_bits'));out={side:boolean(bits&(1<<i)) for i,side in enumerate(HORIZONTAL)};out['up']='false'
    elif name=='sea_pickle':out.update(pickles=str(int(p.pop('cluster_count'))+1),waterlogged=boolean(p.pop('dead_bit')=='false'))
    elif name=='seagrass':
        kind=p.pop('sea_grass_type')
        if kind!='default':target='tall_seagrass';out['half']='upper' if kind=='double_top' else 'lower'
    elif name=='bubble_column':out['drag']=p.pop('drag_down')
    elif name=='soul_fire':
        if p.pop('age')!='0':raise ValueError('Soul fire age is not representable in Java')
    elif name=='target':out['power']='0'
    elif name.startswith('light_block_'):target='light';out['level']=name.removeprefix('light_block_')
    elif name.endswith('_coral'):pass
    elif name.endswith('_coral_wall_fan'):out['facing']=('west','east','north','south')[int(p.pop('coral_direction'))]
    elif name.endswith('_coral_fan'):
        if p.pop('coral_fan_direction')!='0':raise ValueError('Native coral fan orientation is not representable in Java')
    else:return None
    return target,out
