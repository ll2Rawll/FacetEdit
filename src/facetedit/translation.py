"""Explicit, version-pinned Java/Bedrock translation with atomic diagnostics.

Rules operate on native states. Every input property must be consumed and every
output must validate against its pinned schema. Unsupported semantics are errors,
never air substitutions. This is a growing ruleset, not a universal registry.
"""
from collections import Counter, deque
from dataclasses import dataclass, field
from importlib.resources import files
import json

from .blocks import AIR, Block
from .model import Clipboard
from .registry import for_clipboard, profile
from . import native_rules

STATELESS = frozenset(json.loads(files('facetedit').joinpath('data','registries','stateless-1.21.json').read_text())['blocks'])
TAGS=json.loads(files('facetedit').joinpath('data','registries','java-1.21.4-tags.json').read_text())
LOGS,LEAVES=frozenset(TAGS['logs']),frozenset(TAGS['leaves'])
ALIASES = {'dirt_path':'grass_path', 'magma_block':'magma', 'cobweb':'web', 'sugar_cane':'reeds',
           'cobblestone_stairs':'stone_stairs', 'stone_stairs':'normal_stone_stairs',
           'end_stone_brick_stairs':'end_brick_stairs', 'prismarine_brick_stairs':'prismarine_bricks_stairs',
           'stone_slab':'normal_stone_slab', 'snow_block':'snow', 'snow':'snow_layer',
           'oak_sign':'standing_sign', 'oak_wall_sign':'wall_sign', 'powered_rail':'golden_rail',
           'dark_oak_sign':'darkoak_standing_sign','dark_oak_wall_sign':'darkoak_wall_sign'}
ALIASES.update(oak_door='wooden_door',oak_trapdoor='trapdoor',oak_button='wooden_button',
               oak_fence_gate='fence_gate',oak_pressure_plate='wooden_pressure_plate')
REVERSE = {v:k for k,v in ALIASES.items()}
FACING = {'0':'down','1':'up','2':'north','3':'south','4':'west','5':'east'}
STAIRS = {'0':'east','1':'west','2':'south','3':'north'}
SIDES = {'north':(0,0,-1),'east':(1,0,0),'south':(0,0,1),'west':(-1,0,0)}
OPPOSITE={'north':'south','south':'north','east':'west','west':'east'}
DOOR_FACING=('east','south','west','north')
GATE_FACING=('south','west','north','east')
RAILS = ('north_south','east_west','ascending_east','ascending_west','ascending_north','ascending_south','south_east','south_west','north_west','north_east')


@dataclass
class TranslationReport:
    source: str
    target: str
    blocks: int = 0
    translated: int = 0
    problems: Counter = field(default_factory=Counter)
    examples: dict = field(default_factory=dict)
    notes: set = field(default_factory=set)
    payloads: int = 0

    @property
    def ok(self):
        return not self.problems

    def issue(self, reason, position=None, count=1):
        if reason not in self.problems and len(self.problems)>=512:
            reason='Additional unsupported data (diagnostic limit reached)'
        self.problems[reason] += count
        examples = self.examples.setdefault(reason, [])
        if position is not None and len(examples) < 3:
            examples.append(position)
        return reason

    def summary(self):
        lines = [f'{self.source} → {self.target}', f'{self.translated:,} / {self.blocks:,} blocks translated']
        if self.payloads:lines.append(f'{self.payloads:,} block payload'+('s' if self.payloads!=1 else '')+' translated or generated')
        for reason, count in self.problems.most_common():
            lines.append(f'BLOCKED · {count:,} · {reason}')
            if self.examples[reason]:
                lines.append('  '+', '.join(map(str,self.examples[reason])))
        lines += sorted(self.notes)
        return '\n'.join(lines)


class Translator:
    def __init__(self, source, target):
        self.source, self.target = source, target
        self.java, self.bedrock = profile('Java 1.21.4'), profile('Bedrock 1.21.50')
        self.cache = {}
        self.chest_links = {}
        self.chest_link_bytes = 0

    def cell(self,block,layers=(),entity=None,position=(0,0,0),neighbour=None,neighbour_entity=None):
        from .payloads import translate_cell
        return translate_cell(self,block,layers,entity,position,neighbour,neighbour_entity)

    def block(self, block, layers=()):
        key = block, tuple(layers)
        if key in self.cache:
            value = self.cache[key]
            if isinstance(value, str):
                raise ValueError(value)
            return value
        try:
            native = self.source.validate(block, defaults=self.source.edition == 'Java')
            if self.source.label == self.target.label:
                if self.source.edition == 'Java' and layers:
                    raise ValueError('Java blocks cannot have extra layers')
                result = native, tuple(self.target.validate(b) for b in layers)
            elif self.source.edition == self.target.edition:
                result = self.target.validate(native), tuple(self.target.validate(b) for b in layers)
            elif self.source.edition == 'Java':
                if layers:
                    raise ValueError('Java input has unexpected extra layers')
                result = self.to_bedrock(native)
            else:
                java = self.to_java(native)
                if native.name=='minecraft:sea_pickle' and bool(layers)!=(dict(native.properties)['dead_bit']=='false'):
                    raise ValueError('Sea-pickle death state disagrees with its secondary water layer')
                if layers:
                    if len(layers) != 1:
                        raise ValueError('Only one source-water layer can become Java waterlogging')
                    water = self.bedrock.validate(layers[0])
                    if water.name != 'minecraft:water' or dict(water.properties).get('liquid_depth') != '0':
                        raise ValueError('Extra layer is not source water')
                    props = dict(java.properties)
                    if 'waterlogged' not in props and java.name.removeprefix('minecraft:') not in native_rules.ALWAYS_WATER:
                        raise ValueError(f'{java.name} cannot represent the extra water layer')
                    if 'waterlogged' in props:props['waterlogged'] = 'true'
                    java = self.java.block(java.name, props)
                result = java, ()
        except ValueError as exc:
            if len(self.cache) < 32768:
                self.cache[key] = str(exc)
            raise
        if len(self.cache) < 32768:
            self.cache[key] = result
        return result

    def to_bedrock(self, block):
        name = block.name.removeprefix('minecraft:')
        p = dict(block.properties)
        water = p.pop('waterlogged', 'false') == 'true'
        target = ALIASES.get(name, name)
        out = {}
        extended=native_rules.to_bedrock(name,p,water)
        if extended is not None:
            target,out=extended
        elif block.name in STATELESS:
            pass
        elif name in ('cave_air','void_air'):
            target = 'air'
        elif name in ('dirt_path','magma_block','cobweb','snow_block'):
            pass
        elif name == 'bedrock':
            out['infiniburn_bit'] = 'false'
        elif name in ('grass_block','podzol','mycelium'):
            if p.pop('snowy') != 'false':
                raise ValueError('Snow-covered terrain needs contextual translation')
        elif name in ('quartz_block','smooth_quartz'):
            out['pillar_axis'] = 'y'
        elif set(p) == {'axis'} and 'minecraft:'+target in self.bedrock.blocks and set(self.bedrock.blocks['minecraft:'+target]['properties']) == {'pillar_axis'}:
            out['pillar_axis'] = p.pop('axis')
        elif name in ('water','lava'):
            out['liquid_depth'] = p.pop('level')
        elif name.endswith('_stairs'):
            out['weirdo_direction'] = {v:k for k,v in STAIRS.items()}[p.pop('facing')]
            out['upside_down_bit'] = str(p.pop('half') == 'top').lower()
            # Bedrock derives stair corner shape from neighbours; checked by the
            # caller against the original Java shape before mutation.
            p.pop('shape')
        elif name.endswith('_slab'):
            half = p.pop('type')
            if half == 'double':
                candidates = (target.replace('_slab','_double_slab'), target.replace('cut_copper_slab','double_cut_copper_slab'), 'double_'+target)
                target = next((s for s in candidates if 'minecraft:'+s in self.bedrock.blocks), '')
                if not target:
                    raise ValueError(f'No double-slab mapping for {name}')
            out['minecraft:vertical_half'] = half if half != 'double' else 'bottom'
        elif name.endswith('_wall') and not name.endswith('_wall_sign'):
            for side in SIDES:
                out['wall_connection_type_'+side] = {'none':'none','low':'short','tall':'tall'}[p.pop(side)]
            out['wall_post_bit'] = p.pop('up')
        elif name.endswith('_leaves'):
            p.pop('distance')
            out.update(persistent_bit=p.pop('persistent'),update_bit='false')
        elif name.endswith('_sapling') and set(p)=={'stage'}:
            out['age_bit']=str(p.pop('stage')=='1').lower()
        elif name.endswith('_trapdoor'):
            if p.pop('powered')!='false':raise ValueError('Powered trapdoor state has no independent Bedrock representation')
            out.update(direction={v:k for k,v in STAIRS.items()}[p.pop('facing')],open_bit=p.pop('open'),upside_down_bit=str(p.pop('half')=='top').lower())
        elif name.endswith('_door'):
            if p.pop('powered')!='false':raise ValueError('Powered door state has no independent Bedrock representation')
            upper=p.pop('half')=='upper';facing=p.pop('facing');opened=p.pop('open');hinge=p.pop('hinge')
            out.update(direction='0' if upper else str(DOOR_FACING.index(facing)),open_bit='false' if upper else opened,
                       door_hinge_bit=str(hinge=='right').lower() if upper else 'false',upper_block_bit=str(upper).lower())
        elif name.endswith('_fence_gate'):
            if p.pop('powered')!='false':raise ValueError('Powered gate state has no independent Bedrock representation')
            out.update(direction=str(GATE_FACING.index(p.pop('facing'))),in_wall_bit=p.pop('in_wall'),open_bit=p.pop('open'))
        elif name.endswith('_button'):
            face,facing=p.pop('face'),p.pop('facing')
            if face!='wall' and facing!='north':raise ValueError('Bedrock floor/ceiling buttons cannot preserve this horizontal orientation')
            out.update(button_pressed_bit=p.pop('powered'),facing_direction='1' if face=='floor' else '0' if face=='ceiling' else {v:k for k,v in FACING.items()}[facing])
        elif name.endswith('_pressure_plate'):
            out['redstone_signal']=p.pop('power') if 'power' in p else '1' if p.pop('powered')=='true' else '0'
        elif name in ('torch','wall_torch','soul_torch','soul_wall_torch','redstone_torch','redstone_wall_torch'):
            target=name.replace('wall_','')
            if p.pop('lit','true')=='false':target='unlit_redstone_torch'
            out['torch_facing_direction']=OPPOSITE[p.pop('facing')] if 'facing' in p else 'top'
        elif name in ('redstone_ore','deepslate_redstone_ore'):
            target='lit_'+name if p.pop('lit')=='true' else name
        elif name=='tnt':
            out['explode_bit']=p.pop('unstable')
        elif name=='bamboo':
            out.update(age_bit=str(p.pop('stage')=='1').lower(),bamboo_stalk_thickness='thick' if p.pop('age')=='1' else 'thin',
                       bamboo_leaf_size={'none':'no_leaves','small':'small_leaves','large':'large_leaves'}[p.pop('leaves')])
        elif name in ('chest','trapped_chest'):
            if p.pop('type')!='single':raise ValueError('Double chests need paired block-NBT translation')
            out['minecraft:cardinal_direction']=p.pop('facing')
        elif name=='barrel':
            out.update(facing_direction={v:k for k,v in FACING.items()}[p.pop('facing')],open_bit=p.pop('open'))
        elif name in ('wheat','carrots','potatoes','beetroots'):
            age = int(p.pop('age'))
            if name == 'beetroots':
                target='beetroot'; age = (0,2,4,7)[age]
            out['growth'] = str(age)
        elif name in ('sugar_cane','cactus'):
            out['age'] = p.pop('age')
        elif name == 'farmland':
            out['moisturized_amount'] = p.pop('moisture')
        elif name == 'snow':
            out.update(height=str(int(p.pop('layers'))-1), covered_bit='false')
        elif name in ('furnace','smoker','blast_furnace'):
            if p.pop('lit') == 'true':
                target = 'lit_'+name
            out['minecraft:cardinal_direction'] = p.pop('facing')
        elif name == 'redstone_lamp':
            target = 'lit_redstone_lamp' if p.pop('lit') == 'true' else name
        elif name in ('carved_pumpkin','jack_o_lantern'):
            target = 'lit_pumpkin' if name == 'jack_o_lantern' else name
            out['minecraft:cardinal_direction'] = p.pop('facing')
        elif name.endswith('_wall_sign') or name == 'ladder':
            out['facing_direction'] = {v:k for k,v in FACING.items()}[p.pop('facing')]
        elif name.endswith('_sign') and not name.endswith('_hanging_sign'):
            target = ALIASES.get(name, name.replace('_sign','_standing_sign'))
            out['ground_sign_direction'] = p.pop('rotation')
        elif name in ('rail','powered_rail','detector_rail','activator_rail'):
            out['rail_direction'] = str(RAILS.index(p.pop('shape')))
            if 'powered' in p:
                out['rail_data_bit'] = p.pop('powered')
        elif name.endswith('_candle') or name == 'candle':
            out.update(candles=str(int(p.pop('candles'))-1), lit=p.pop('lit'))
        elif name.endswith('_candle_cake') or name == 'candle_cake':
            out['lit'] = p.pop('lit')
        elif name in ('sunflower','lilac','rose_bush','peony','large_fern','tall_grass','pitcher_plant'):
            out['upper_block_bit'] = str(p.pop('half') == 'upper').lower()
        else:
            raise ValueError(f'No Java → Bedrock rule for {block.name}')
        if p:
            raise ValueError(f'Untranslated Java states on {block.name}: {sorted(p)}')
        result = self.bedrock.block('minecraft:'+target, out)
        extra = (self.bedrock.block('minecraft:water', {'liquid_depth':'0'}),) if water or name in native_rules.ALWAYS_WATER else ()
        return result, extra

    def to_java(self, block):
        name = block.name.removeprefix('minecraft:')
        target = REVERSE.get(name, name)
        p = dict(block.properties)
        out = {}
        extended=native_rules.to_java(name,p)
        if extended is not None:
            target,out=extended
        elif block.name in STATELESS or name in ('grass_path','magma','web','snow'):
            pass
        elif name == 'bedrock':
            if p.pop('infiniburn_bit') != 'false':
                raise ValueError('Bedrock infiniburn state has no Java block state')
        elif name in ('grass_block','podzol','mycelium'):
            out['snowy'] = 'false'
        elif name in ('quartz_block','smooth_quartz'):
            if p.pop('pillar_axis') != 'y':
                raise ValueError('Oriented Bedrock quartz has no matching Java state')
        elif set(p) == {'pillar_axis'} and 'minecraft:'+target in self.java.blocks and set(self.java.blocks['minecraft:'+target]['properties']) - {'waterlogged'} == {'axis'}:
            out['axis'] = p.pop('pillar_axis')
        elif name in ('water','lava','flowing_water','flowing_lava'):
            target = name.removeprefix('flowing_')
            out['level'] = p.pop('liquid_depth')
        elif name.endswith('_stairs'):
            out.update(facing=STAIRS[p.pop('weirdo_direction')], half='top' if p.pop('upside_down_bit') == 'true' else 'bottom', shape='straight')
        elif name.endswith('_slab'):
            double = 'double' in name
            if double:
                base = name.replace('_double_slab','_slab').replace('double_','')
                target = REVERSE.get(base, base)
            half = p.pop('minecraft:vertical_half')
            if double and half != 'bottom':
                raise ValueError('Noncanonical double slab vertical half cannot be preserved')
            out['type'] = 'double' if double else half
        elif name.endswith('_wall') and not name.endswith('_wall_sign'):
            for side in SIDES:
                out[side] = {'none':'none','short':'low','tall':'tall'}[p.pop('wall_connection_type_'+side)]
            out['up'] = p.pop('wall_post_bit')
        elif name.endswith('_leaves'):
            p.pop('update_bit')
            out.update(persistent=p.pop('persistent_bit'),distance='7')
        elif name.endswith('_sapling') and set(p)=={'age_bit'}:
            out['stage']='1' if p.pop('age_bit')=='true' else '0'
        elif name.endswith('trapdoor'):
            out.update(facing=STAIRS[p.pop('direction')],open=p.pop('open_bit'),half='top' if p.pop('upside_down_bit')=='true' else 'bottom',powered='false')
        elif name.endswith('_door'):
            out.update(facing=DOOR_FACING[int(p.pop('direction'))],open=p.pop('open_bit'),hinge='right' if p.pop('door_hinge_bit')=='true' else 'left',
                       half='upper' if p.pop('upper_block_bit')=='true' else 'lower',powered='false')
        elif name.endswith('fence_gate'):
            out.update(facing=GATE_FACING[int(p.pop('direction'))],open=p.pop('open_bit'),in_wall=p.pop('in_wall_bit'),powered='false')
        elif name.endswith('_button'):
            facing=FACING[p.pop('facing_direction')]
            out.update(face='floor' if facing=='up' else 'ceiling' if facing=='down' else 'wall',facing=facing if facing in SIDES else 'north',powered=p.pop('button_pressed_bit'))
        elif name.endswith('_pressure_plate'):
            power=p.pop('redstone_signal')
            if name in ('light_weighted_pressure_plate','heavy_weighted_pressure_plate'):out['power']=power
            else:
                if power not in ('0','1'):raise ValueError('Nonbinary pressure-plate state cannot fit a Java boolean state')
                out['powered']=str(power=='1').lower()
        elif name in ('torch','soul_torch','redstone_torch','unlit_redstone_torch'):
            side=p.pop('torch_facing_direction')
            if side=='unknown':raise ValueError('Unknown Bedrock torch facing cannot be represented')
            target=name.removeprefix('unlit_')
            if side!='top':target=target.replace('torch','wall_torch');out['facing']=OPPOSITE[side]
            if 'redstone' in name:out['lit']=str(name!='unlit_redstone_torch').lower()
        elif name.removeprefix('lit_') in ('redstone_ore','deepslate_redstone_ore'):
            target=name.removeprefix('lit_');out['lit']=str(name.startswith('lit_')).lower()
        elif name=='tnt':
            out['unstable']=p.pop('explode_bit')
        elif name=='bamboo':
            out.update(stage='1' if p.pop('age_bit')=='true' else '0',age='1' if p.pop('bamboo_stalk_thickness')=='thick' else '0',
                       leaves={'no_leaves':'none','small_leaves':'small','large_leaves':'large'}[p.pop('bamboo_leaf_size')])
        elif name in ('chest','trapped_chest'):
            out.update(facing=p.pop('minecraft:cardinal_direction'),type='single')
        elif name=='barrel':
            out.update(facing=FACING[p.pop('facing_direction')],open=p.pop('open_bit'))
        elif name in ('wheat','carrots','potatoes','beetroot'):
            age = int(p.pop('growth'))
            if name == 'beetroot':
                target = 'beetroots'
                if age not in (0,2,4,7):
                    raise ValueError('Intermediate Bedrock beetroot growth cannot be represented exactly')
                age = (0,2,4,7).index(age)
            out['age'] = str(age)
        elif name in ('reeds','cactus'):
            out['age'] = p.pop('age')
        elif name == 'farmland':
            out['moisture'] = p.pop('moisturized_amount')
        elif name == 'snow_layer':
            if p.pop('covered_bit') != 'false':
                raise ValueError('Covered Bedrock snow requires contextual translation')
            out['layers'] = str(int(p.pop('height'))+1)
        elif name.removeprefix('lit_') in ('furnace','smoker','blast_furnace'):
            target = name.removeprefix('lit_')
            out.update(lit=str(name.startswith('lit_')).lower(), facing=p.pop('minecraft:cardinal_direction'))
        elif name in ('redstone_lamp','lit_redstone_lamp'):
            target = 'redstone_lamp'; out['lit'] = str(name.startswith('lit_')).lower()
        elif name in ('carved_pumpkin','lit_pumpkin'):
            target = 'jack_o_lantern' if name == 'lit_pumpkin' else name
            out['facing'] = p.pop('minecraft:cardinal_direction')
        elif name == 'wall_sign' or name.endswith('_wall_sign') or name == 'ladder':
            out['facing'] = FACING[p.pop('facing_direction')]
        elif name == 'standing_sign' or name.endswith('_standing_sign'):
            target = REVERSE.get(name, name.replace('_standing_sign','_sign'))
            out['rotation'] = p.pop('ground_sign_direction')
        elif name in ('rail','golden_rail','detector_rail','activator_rail'):
            out['shape'] = RAILS[int(p.pop('rail_direction'))]
            if 'rail_data_bit' in p:
                out['powered'] = p.pop('rail_data_bit')
        elif name.endswith('_candle') or name == 'candle':
            out.update(candles=str(int(p.pop('candles'))+1), lit=p.pop('lit'))
        elif name.endswith('_candle_cake') or name == 'candle_cake':
            out['lit'] = p.pop('lit')
        elif name in ('sunflower','lilac','rose_bush','peony','large_fern','tall_grass','pitcher_plant'):
            out['half'] = 'upper' if p.pop('upper_block_bit') == 'true' else 'lower'
        else:
            raise ValueError(f'No Bedrock → Java rule for {block.name}')
        if p:
            raise ValueError(f'Untranslated Bedrock states on {block.name}: {sorted(p)}')
        return self.java.block('minecraft:'+target, out, defaults=True)


def stair_shape(position, block, get):
    """Vanilla corner rule: front outer corner, rear inner corner, side exclusion."""
    props = dict(block.properties)
    facing, half = props['facing'], props['half']
    directions = tuple(SIDES)
    index = directions.index(facing)
    def neighbour(side):
        delta = SIDES[side]
        return get(tuple(a+b for a,b in zip(position, delta)))
    def stairs(b):
        return b is not None and b.name.endswith('_stairs') and dict(b.properties).get('half') == half
    for offset, kind in ((0,'outer'), (2,'inner')):
        adjacent = neighbour(directions[(index+offset)%4])
        if not stairs(adjacent):
            continue
        turn = dict(adjacent.properties)['facing']
        if turn not in (directions[(index+1)%4], directions[(index-1)%4]):
            continue
        exclusion = directions[(directions.index(turn)+(2 if kind == 'outer' else 0))%4]
        beside = neighbour(exclusion)
        if stairs(beside) and dict(beside.properties)['facing'] == facing:
            continue
        return kind+('_left' if turn == directions[(index-1)%4] else '_right')
    return 'straight'


def leaf_distances(positions, get, cancelled=lambda:False):
    """Resolve distance to a log through up to six connected leaf cells."""
    adjacent=(*SIDES.values(),(0,1,0),(0,-1,0))
    leaves=set(positions);pending=deque((p,0) for p in leaves);distances={}
    cached={}
    def block_at(p):
        if p not in cached:cached[p]=get(p)
        return cached[p]
    while pending:
        if cancelled():raise InterruptedError('Leaf translation cancelled')
        position,depth=pending.popleft()
        for delta in adjacent:
            other=tuple(a+b for a,b in zip(position,delta));block=block_at(other)
            if block is None:continue
            if block.name in LOGS:
                distances[position]=1
            elif depth<5 and block.name in LEAVES and other not in leaves:
                leaves.add(other);pending.append((other,depth+1))
                if len(leaves)>262144:raise ValueError('Leaf neighbour search exceeds its bounded context budget')
    pending=deque(distances)
    while pending:
        if cancelled():raise InterruptedError('Leaf translation cancelled')
        position=pending.popleft();distance=distances[position]
        if distance>=6:continue
        for delta in adjacent:
            other=tuple(a+b for a,b in zip(position,delta))
            if other in leaves and distance+1<distances.get(other,7):
                distances[other]=distance+1;pending.append(other)
    return {p:distances.get(p,7) for p in positions}


def translate_clipboard(clip, target, source=None, neighbour=None, cancelled=lambda: False, neighbour_entity=None):
    source = source or for_clipboard(clip)
    if source.edition != clip.edition:
        raise ValueError('Source profile does not match the clipboard edition')
    if clip.edition == 'Java' and clip.data_version is not None and source.data_version != clip.data_version:
        raise ValueError('Source profile does not match the known clipboard DataVersion')
    if clip.game_version is not None and tuple(clip.game_version) != source.version:
        raise ValueError('Source profile does not match the known clipboard game version')
    translator = Translator(source, target)
    report = TranslationReport(source.label, target.label, len(clip.blocks))
    blocks, extra, entities = {}, {}, {}
    def source_at(pos):
        return clip.blocks.get(pos) if pos in clip.blocks else neighbour(pos) if neighbour is not None else None
    def entity_at(pos):
        return clip.entities.get(pos) if pos in clip.blocks else neighbour_entity(pos) if neighbour_entity is not None else None
    for pos in clip.entities.keys()-clip.blocks.keys():report.issue('Block NBT lies outside the clipboard block mask',pos)
    for pos in clip.extra_blocks.keys()-clip.blocks.keys():report.issue('Extra block layer lies outside the clipboard block mask',pos)
    for index, (pos, block) in enumerate(clip.blocks.items()):
        if index % 256 == 0 and cancelled():
            raise InterruptedError('Translation cancelled')
        try:
            blocks[pos], layers, entity = translator.cell(block, clip.extra_blocks.get(pos, ()),clip.entities.get(pos),pos,source_at,entity_at)
            if layers:
                extra[pos] = layers
            if entity is not None:
                entities[pos]=entity;report.payloads+=1
            report.translated += 1
        except (ValueError, KeyError, IndexError) as exc:
            report.issue(str(exc), pos)
    cross = source.edition != target.edition
    if cross and any(b.name in ('minecraft:cave_air','minecraft:void_air') for b in clip.blocks.values()):
        report.notes.add('Java cave/void air becomes Bedrock air; Bedrock has no separate air subtype.')
    if cross and any(b.name in ('minecraft:flowing_water','minecraft:flowing_lava') for b in clip.blocks.values()):
        report.notes.add('Bedrock flowing-fluid identifiers become Java fluid blocks with the same depth.')
    if cross:
        canonical = blocks if target.edition == 'Java' else {p: source.validate(b, defaults=True) for p,b in clip.blocks.items() if p in blocks}
        def get(pos):
            if pos in canonical:
                return canonical[pos]
            if neighbour is not None:
                other = neighbour(pos)
                if other is not None:
                    if not other.name.endswith('_stairs'):
                        return AIR
                    return translator.to_java(source.validate(other)) if source.edition == 'Bedrock' else source.validate(other, defaults=True)
            return AIR
        for pos, block in canonical.items():
            if block.name.endswith(('_fence','_glass_pane')) or block.name in ('minecraft:glass_pane','minecraft:iron_bars'):
                from .state_facts import connects
                try:
                    props=dict(block.properties)
                    for side,delta in SIDES.items():
                        other_pos=tuple(a+b for a,b in zip(pos,delta))
                        other=canonical.get(other_pos)
                        if other is None:
                            native=source_at(other_pos)
                            other=AIR if native is None else translator.cell(native,entity=entity_at(other_pos),position=other_pos)[0] if source.edition=='Bedrock' else source.validate(native,defaults=True)
                        connected=str(connects(block,other,OPPOSITE[side])).lower()
                        if target.edition=='Java':props[side]=connected
                        elif props[side]!=connected:raise ValueError('Java '+side+' connection disagrees with neighbours; Bedrock would change it')
                    if target.edition=='Java':blocks[pos]=target.block(block.name,props)
                except (ValueError,KeyError,IndexError) as exc:report.issue('Connection neighbour: '+str(exc),pos)
            if block.name.endswith('_door'):
                props=dict(block.properties);lower=pos if props['half']=='lower' else (pos[0],pos[1]-1,pos[2]);upper=(lower[0],lower[1]+1,lower[2])
                bottom,top=source_at(lower),source_at(upper)
                if bottom is None or top is None or bottom.name!=top.name:
                    report.issue('Door translation requires both matching halves',pos);continue
                if source.edition=='Bedrock':
                    try:a,b=dict(source.validate(bottom).properties),dict(source.validate(top).properties)
                    except ValueError as exc:report.issue('Door neighbour: '+str(exc),pos);continue
                    if a.get('upper_block_bit')!='false' or b.get('upper_block_bit')!='true':
                        report.issue('Door half metadata is inconsistent',pos);continue
                    props.update(facing=DOOR_FACING[int(a['direction'])],open=a['open_bit'],hinge='right' if b['door_hinge_bit']=='true' else 'left')
                    blocks[pos]=target.block(block.name,props)
                else:
                    a,b=dict(source.validate(bottom,defaults=True).properties),dict(source.validate(top,defaults=True).properties)
                    if a['half']!='lower' or b['half']!='upper' or any(a[k]!=b[k] for k in ('facing','open','hinge','powered')):
                        report.issue('Java door halves disagree; Bedrock cannot preserve both states',pos)
            if not block.name.endswith('_stairs'):
                continue
            try:
                shape = stair_shape(pos, block, get)
                props = dict(block.properties)
                if target.edition == 'Java':
                    props['shape'] = shape
                    blocks[pos] = target.block(block.name, props)
                elif props['shape'] != shape:
                    report.issue('Java stair shape disagrees with neighbours; Bedrock would change it', pos)
            except (ValueError, KeyError) as exc:
                report.issue('Stair neighbour: '+str(exc), pos)
        leaves=[p for p,b in canonical.items() if b.name.endswith('_leaves')]
        if leaves:
            report.notes.add('Leaf distance is derived from available structure/world neighbours; Bedrock has no Java distance field.')
            if target.edition=='Java':
                try:
                    for pos,distance in leaf_distances(leaves,source_at,cancelled).items():
                        block=blocks[pos];props=dict(block.properties);props['distance']=str(distance)
                        blocks[pos]=target.block(block.name,props)
                except ValueError as exc:report.issue(str(exc))
    if not report.ok:
        return None, report
    result = Clipboard(clip.size, blocks, target.edition, clip.offset, entities, target.data_version, extra, target.version)
    return result, report
