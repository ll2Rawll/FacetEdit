"""Explicit block matching modes for replace operations."""
from dataclasses import dataclass
from fnmatch import fnmatchcase
from .blocks import Block


@dataclass(frozen=True)
class BlockMatcher:
    name: str
    properties: tuple = ()
    mode: str = 'exact'

    def __post_init__(self):
        if self.mode not in ('exact', 'name', 'subset', 'pattern'):
            raise ValueError('Unknown block matching mode')
        if len(self.name) > 256:
            raise ValueError('Block pattern is too long')

    @classmethod
    def parse(cls, text, mode='exact'):
        name, separator, rest = text.strip().partition('[')
        block = Block.parse('minecraft:stone'+separator+rest) if mode == 'pattern' else Block.parse(text)
        if mode != 'pattern':
            name = block.name
        elif ':' not in name:
            name = 'minecraft:'+name
        return cls(name, block.properties, mode)

    def matches(self, block):
        if not (fnmatchcase(block.name, self.name) if self.mode == 'pattern' else block.name == self.name):
            return False
        if self.mode == 'name':
            return True
        if self.mode == 'exact':
            return block.properties == self.properties
        props = dict(block.properties)
        return all(props.get(k) == v for k,v in self.properties)
