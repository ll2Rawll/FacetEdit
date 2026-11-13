"""Consume typed native fields and reject every unhandled payload path."""
from . import nbt

MISSING=object()


class Fields:
    def __init__(self,compound,path):
        if isinstance(compound,nbt.Tag):
            if compound.kind!=nbt.COMPOUND:raise ValueError(path+': expected a compound')
            compound=compound.value
        if not isinstance(compound,dict):raise ValueError(path+': expected a compound')
        self.data=dict(compound);self.path=path

    def pop(self,key,kind,default=MISSING):
        tag=self.data.pop(key,None)
        if tag is None:
            if default is MISSING:raise ValueError(self.path+'.'+key+': required field is missing')
            return default
        if tag.kind!=kind:raise ValueError(self.path+'.'+key+': unexpected NBT type')
        return tag.value

    def flag(self,key,default=False):
        value=self.pop(key,nbt.BYTE,int(default))
        if value not in (0,1):raise ValueError(self.path+'.'+key+': expected a boolean byte')
        return bool(value)

    def default_only(self,key,kind,value):
        if self.pop(key,kind,value)!=value:
            raise ValueError(self.path+'.'+key+': non-default value has no supported target representation')

    def finish(self):
        if self.data:raise ValueError(self.path+': unsupported fields '+', '.join(sorted(self.data)))


def compound_list(value,path):
    if not isinstance(value,nbt.ListValue) or value.values and value.kind!=nbt.COMPOUND:
        raise ValueError(path+': expected a compound list')
    return value.values


def string_list(value,path):
    if not isinstance(value,nbt.ListValue) or value.values and value.kind!=nbt.STRING:
        raise ValueError(path+': expected a string list')
    return value.values
