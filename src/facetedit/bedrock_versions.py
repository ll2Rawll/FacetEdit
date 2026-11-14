"""Explicit native dialect changes between the two pinned Bedrock profiles.

The modern cardinal names retain the old SWNE numeric encoding, including
doors whose native direction describes a different face from Java's facing.
No unregistered version is treated as compatible with these migrations.
"""
from . import nbt
from .formats import bedrock_block,bedrock_entry
from .payload_fields import Fields
from .registry import profile

LEGACY=(1,21,50)
CARDINAL=(1,21,60)
VERSIONS=frozenset((LEGACY,CARDINAL))
CARDINAL_ORDER=('south','west','north','east')
PALETTES={18163713:'Bedrock 1.21.50',18168865:'Bedrock 1.21.60'}


def to_legacy(block,source):
    native=source.validate(block)
    if source.edition!='Bedrock' or source.version not in VERSIONS:
        raise ValueError('No verified native migration for '+source.label)
    if source.version==LEGACY:return native
    p=dict(native.properties)
    if native.name.endswith(('_door','fence_gate')) and 'minecraft:cardinal_direction' in p:
        p['direction']=str(CARDINAL_ORDER.index(p.pop('minecraft:cardinal_direction')))
    if native.name=='minecraft:creaking_heart':
        state=p.pop('creaking_heart_state')
        if state=='uprooted':
            raise ValueError('Uprooted creaking-heart state has no exact representation in Bedrock 1.21.50 or Java 1.21.4')
        p['active']='true' if state=='awake' else 'false'
    return profile('Bedrock 1.21.50').block(native.name,p)


def from_legacy(block,target):
    if target.edition!='Bedrock' or target.version not in VERSIONS:
        raise ValueError('No verified native migration for '+target.label)
    native=profile('Bedrock 1.21.50').validate(block)
    if target.version==LEGACY:return native
    p=dict(native.properties)
    if native.name.endswith(('_door','fence_gate')) and 'direction' in p:
        p['minecraft:cardinal_direction']=CARDINAL_ORDER[int(p.pop('direction'))]
    if native.name=='minecraft:creaking_heart':
        p['creaking_heart_state']='awake' if p.pop('active')=='true' else 'dormant'
    return target.block(native.name,p)


def migrate_block(block,source,target):
    if source.label==target.label:return target.validate(block)
    return from_legacy(to_legacy(block,source),target)


def world_palette_mapper(target):
    """Normalize supported mixed native palettes without relabeling their bytes."""
    def normalize(block,tag):
        version=nbt.get(tag,'version')
        if version not in PALETTES or version==target.palette_version:return block
        source=profile(PALETTES[version])
        if block.name not in source.blocks:return block
        return migrate_block(block,source,target)
    return normalize


def read_descriptor(value,target,path='Block descriptor'):
    """An embedded descriptor's storage version takes precedence over its world."""
    f=Fields(value,path)
    name=f.pop('name',nbt.STRING);states=f.pop('states',nbt.COMPOUND);version=f.pop('version',nbt.INT);f.finish()
    if version not in PALETTES:raise ValueError(path+'.version: unsupported embedded Bedrock palette version '+str(version))
    for key,tag in states.items():
        if tag.kind==nbt.BYTE and tag.value not in (0,1):raise ValueError(path+'.states.'+key+': expected a boolean byte')
    native=bedrock_block(nbt.compound(name=nbt.Tag(nbt.STRING,name),states=nbt.Tag(nbt.COMPOUND,states)))
    return migrate_block(native,profile(PALETTES[version]),target)


def migrate_payload(translator,block,data,position,neighbour,neighbour_entity):
    """Audit known native payloads, then retain their types and native fields.

    The existing typed cell handlers validate the represented payload subset.
    Their Java result is discarded: text, item order, counters and native-only
    fields that passed validation retain their original native representation.
    Embedded descriptors need different states/storage identifiers. Identifier-
    only jigsaw final states must also retain the source block's default state.
    """
    if translator.migration_validator is None:
        from .translation import Translator
        translator.migration_validator=Translator(translator.source,profile('Java 1.21.4'))
    translator.migration_validator.cell(block,(),data,position,neighbour,neighbour_entity)
    name,root=nbt.loads(data)
    if nbt.get(root,'id')=='JigsawBlock' and 'final_state' in root.value:
        identifier=nbt.get(root,'final_state')
        source_default=translator.source.initial(identifier)
        if migrate_block(source_default,translator.source,translator.target)!=translator.target.initial(identifier):
            raise ValueError('Block NBT.final_state: target block default changed; an identifier alone cannot preserve this state')
    from .item_translation import item_catalog
    target_items=item_catalog(translator.target.version)[1]
    def walk(tag,path):
        if tag.kind==nbt.COMPOUND:
            if 'Name' in tag.value and 'Count' in tag.value and tag.value['Name'].value not in target_items:
                raise ValueError(path+'.Name: no '+translator.target.label+' item identity for '+tag.value['Name'].value)
            for key,value in tuple(tag.value.items()):
                child_path=path+'.'+key
                if key in ('Block','PlantBlock') and value.kind==nbt.COMPOUND:
                    native=read_descriptor(value,translator.target,child_path)
                    tag.value[key]=bedrock_entry(native,translator.target.palette_version)
                else:walk(value,child_path)
        elif tag.kind==nbt.LIST:
            for index,value in enumerate(tag.value.values):walk(nbt.Tag(tag.value.kind,value),f'{path}[{index}]')
    walk(root,'Block NBT')
    return nbt.dumps(root,name)
