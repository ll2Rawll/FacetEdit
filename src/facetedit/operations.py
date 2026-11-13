"""Original trusted-Python operations API with staged edits and atomic commits.

Scripts execute only after an explicit Run action. This is not a security
sandbox. Cancellation is cooperative through context helpers/check_cancelled.
"""
import ast
from dataclasses import dataclass
from pathlib import Path
import threading

from .blocks import Block
from .model import MAX_OPERATION,SelectionGroup
from . import nbt


class Cancelled(Exception):pass


@dataclass(frozen=True)
class OperationSpec:
    name:str
    description:str
    options:tuple
    source:str
    filename:str

    @classmethod
    def parse(cls,source,filename='<operation>'):
        if len(source.encode('utf-8'))>256*1024:raise ValueError('Operation script exceeds 256 KiB')
        tree=ast.parse(source,filename=filename)
        metadata=None
        for item in tree.body:
            if isinstance(item,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='OPERATION' for t in item.targets):
                metadata=ast.literal_eval(item.value)
        if not isinstance(metadata,dict) or not isinstance(metadata.get('name'),str) or not 1<=len(metadata['name'])<=80:
            raise ValueError('An operation needs a literal OPERATION dictionary with a name')
        description=metadata.get('description','')
        if not isinstance(description,str) or len(description)>2000:raise ValueError('Invalid operation description')
        options=metadata.get('options',[])
        if not isinstance(options,list) or len(options)>16:raise ValueError('An operation supports up to 16 options')
        names=set()
        for option in options:
            if not isinstance(option,dict) or not isinstance(option.get('name'),str) or not option['name'].isidentifier() or option['name'] in names:
                raise ValueError('Invalid or duplicated operation option')
            names.add(option['name'])
            if option.get('type','text') not in ('text','int','bool','block','choice'):raise ValueError('Unsupported operation option type')
            if option.get('type')=='choice' and (not isinstance(option.get('choices'),list) or not option['choices'] or len(option['choices'])>100):raise ValueError('Choice options require a bounded list')
        if not any(isinstance(node,ast.FunctionDef) and node.name=='run' for node in tree.body):raise ValueError('Operation must define run(context, options)')
        return cls(metadata['name'],description,tuple(options),source,filename)

    @classmethod
    def read(cls,path):
        path=Path(path)
        if path.stat().st_size>256*1024:raise ValueError('Operation script exceeds 256 KiB')
        return cls.parse(path.read_text('utf-8'),str(path))

    def values(self,options):
        output={}
        allowed={item['name'] for item in self.options}
        if set(options)-allowed:raise ValueError('Unknown operation option')
        for item in self.options:
            name=item['name'];value=options.get(name,item.get('default',''));kind=item.get('type','text')
            if kind=='int':
                if type(value) is bool:raise ValueError('An integer option cannot be boolean')
                value=int(value)
                if not item.get('min',-30_000_000)<=value<=item.get('max',30_000_000):raise ValueError('Option outside bounds: '+name)
            elif kind=='block':value=value if isinstance(value,Block) else Block.parse(value)
            elif kind=='bool':
                if value in ('true','True','1'):value=True
                elif value in ('false','False','0'):value=False
                if type(value) is not bool:raise ValueError('Boolean option required: '+name)
            elif kind=='choice':
                if value not in item['choices']:raise ValueError('Unknown choice: '+name)
            else:
                if not isinstance(value,str) or len(value)>4096:raise ValueError('Text option too long: '+name)
            output[name]=value
        return output


@dataclass(frozen=True)
class OperationResult:
    name:str
    identity:int
    revision:int
    dimension:str
    blocks:tuple
    entities:tuple
    layers:tuple

    def commit(self,document):
        if id(document)!=self.identity or document.revision!=self.revision or document.dimension!=self.dimension:
            raise ValueError('Workspace changed while the operation was running; run it again')
        return document.apply(self.name,self.blocks,self.entities,self.layers)


class OperationContext:
    def __init__(self,document,cancel=None,progress=lambda value:None):
        self._doc=document.snapshot()
        self.selection=SelectionGroup(document.require_selection().boxes)
        self.dimension=document.dimension
        self.edition='Bedrock' if document.world.edition.startswith('Bedrock') else 'Java'
        self._cancel=cancel or threading.Event();self._progress=progress
        self._blocks={};self._entities={};self._layers={}

    def check_cancelled(self):
        if self._cancel.is_set():raise Cancelled('Operation cancelled; no edits were applied')

    def positions(self):
        total=self.selection.volume
        for i,position in enumerate(self.selection.positions()):
            self.check_cancelled()
            if i%256==0:self._progress(i/max(1,total))
            yield position

    def get_block(self,position):
        self.check_cancelled()
        position=tuple(position)
        return self._blocks[position] if position in self._blocks else self._doc.get(*position)

    def get_extra_blocks(self,position):
        self.check_cancelled();position=tuple(position)
        return self._layers[position] if position in self._layers else self._doc.get_extra_blocks(*position)

    def get_nbt(self,position):
        self.check_cancelled();position=tuple(position)
        return self._entities[position] if position in self._entities else self._doc.get_entity(*position)

    def _touch(self,position):
        self.check_cancelled();position=tuple(position)
        if len(position)!=3 or any(type(v) is not int or abs(v)>30_000_000 for v in position):raise ValueError('Operation coordinate is invalid')
        if position not in self._blocks and len(self._blocks)>=MAX_OPERATION:raise ValueError('Operation exceeds 65,536 block positions')
        self._blocks.setdefault(position,self._doc.get(*position))
        self._layers.setdefault(position,self._doc.get_extra_blocks(*position))
        return position

    def set_block(self,position,block,preserve_layers=False):
        position=self._touch(position);block=Block.parse(block) if isinstance(block,str) else block
        if self._blocks[position]!=block:self._entities[position]=None
        self._blocks[position]=block
        if not isinstance(self._blocks[position],Block):raise ValueError('set_block needs a block or block string')
        if not preserve_layers:self._layers[position]=()

    def set_extra_blocks(self,position,layers):
        position=self._touch(position);self._layers[position]=tuple(layers)

    def set_nbt(self,position,data):
        position=self._touch(position)
        self._entities[position]=nbt.dumps(data) if isinstance(data,nbt.Tag) else data

    def progress(self,fraction):
        self.check_cancelled();self._progress(max(0.,min(1.,float(fraction))))


def run_operation(spec,document,options=None,cancel=None,progress=lambda value:None):
    identity,revision,dimension=id(document),document.revision,document.dimension
    values=spec.values(options or {})
    context=OperationContext(document,cancel,progress);context.check_cancelled()
    namespace={'__name__':'facetedit_user_operation','__file__':spec.filename}
    try:
        exec(compile(spec.source,spec.filename,'exec'),namespace)
        context.check_cancelled()
        result=namespace['run'](context,values)
        if result is not None:
            for fraction in result:context.progress(fraction)
    except (SystemExit,KeyboardInterrupt) as exc:
        # A script's exit must reach the worker's error callback, rather than
        # terminating the worker and leaving its busy indicator stuck forever.
        raise ValueError('Operation stopped without applying edits: '+type(exc).__name__) from exc
    context.check_cancelled();context.progress(1.)
    return OperationResult(spec.name,identity,revision,dimension,tuple(context._blocks.items()),tuple(context._entities.items()),tuple(context._layers.items()))
