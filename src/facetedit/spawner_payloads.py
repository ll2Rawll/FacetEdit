"""Shared natural-spawner fields; customized entity NBT stays an explicit gate."""
import struct
from . import nbt
from .payload_fields import Fields,compound_list

SPAWNS=frozenset('minecraft:'+name for name in ('pig','zombie','skeleton','spider','cave_spider','silverfish','blaze','magma_cube'))
TIMING={'Delay':20,'MinSpawnDelay':200,'MaxSpawnDelay':800,'SpawnCount':4,'MaxNearbyEntities':6,'RequiredPlayerRange':16,'SpawnRange':4}
DISPLAY={'DisplayEntityHeight':1.8,'DisplayEntityWidth':0.8,'DisplayEntityScale':1.0}


def spawn_type(value,path):
    f=Fields(value,path);entity=Fields(f.pop('entity',nbt.COMPOUND),path+'.entity');name=entity.pop('id',nbt.STRING)
    entity.finish();f.finish()
    if name not in SPAWNS:raise ValueError(path+'.entity.id: entity identity is outside the verified natural-spawner set')
    return name


def translate(f,out,edition):
    values={key:f.pop(key,nbt.SHORT,default) for key,default in TIMING.items()}
    if any(value<(-1 if key=='Delay' else 0) for key,value in values.items()) or values['MaxSpawnDelay']<max(1,values['MinSpawnDelay']):
        raise ValueError(f.path+': inconsistent spawner timing/range')
    out.update({key:nbt.Tag(nbt.SHORT,value) for key,value in values.items()})
    if edition=='Java':
        default={'entity':nbt.compound(id=nbt.Tag(nbt.STRING,'minecraft:pig'))}
        name=spawn_type(f.pop('SpawnData',nbt.COMPOUND,default),f.path+'.SpawnData')
        potentials=compound_list(f.pop('SpawnPotentials',nbt.LIST,nbt.ListValue(nbt.COMPOUND,[])),f.path+'.SpawnPotentials')
        if len(potentials)>1:raise ValueError(f.path+'.SpawnPotentials: mixed spawn pools require an entity-pool migration')
        if potentials:
            entry=Fields(potentials[0],f.path+'.SpawnPotentials[0]');weight=entry.pop('weight',nbt.INT)
            chosen=spawn_type(entry.pop('data',nbt.COMPOUND),entry.path+'.data');entry.finish()
            if weight!=1 or chosen!=name:raise ValueError(entry.path+': custom weighting/next-spawn identity cannot fit the native single-type spawner')
        out['EntityIdentifier']=nbt.Tag(nbt.STRING,name)
        out.update({key:nbt.Tag(nbt.FLOAT,value) for key,value in DISPLAY.items()})
    else:
        name=f.pop('EntityIdentifier',nbt.STRING,'')
        if name not in SPAWNS:raise ValueError(f.path+'.EntityIdentifier: entity identity is outside the verified natural-spawner set')
        for key,value in DISPLAY.items():
            # Compare the actual 32-bit representation rather than a double
            # literal; 0.8f and 1.8f are not exactly representable as doubles.
            f.default_only(key,nbt.FLOAT,struct.unpack('>f',struct.pack('>f',value))[0])
        entity=nbt.compound(entity=nbt.compound(id=nbt.Tag(nbt.STRING,name)))
        out['SpawnData']=entity
        out['SpawnPotentials']=nbt.Tag(nbt.LIST,nbt.ListValue(nbt.COMPOUND,[{'weight':nbt.Tag(nbt.INT,1),'data':entity}]))
