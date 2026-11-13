"""Compare independent native-state rules with an isolated Amulet oracle.

No reference code or translation table is imported by the application. This
optional development script checks our supported rules; it does not generate
runtime mappings or establish parity for unsupported blocks/versions/NBT.
"""
from collections import Counter
import json
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'src'))
from facetedit.blocks import Block
from facetedit.registry import profile
from facetedit.translation import Translator
import PyMCTranslate
import numpy as np
from amulet import Block as ReferenceBlock
from amulet.api.chunk import Chunk
from amulet.level.translators.chunk.java.java_blockstate_translator import JavaBlockstateTranslator
from amulet_nbt import ByteTag,IntTag,StringTag


def canonical(block):
    props=[]
    for name,value in block.properties.items():
        if name=='__version__':continue
        if isinstance(value,ByteTag):value='true' if value.py_int else 'false'
        elif isinstance(value,IntTag):value=str(value.py_int)
        else:value=value.py_str
        props.append((name,value))
    name=block.namespaced_name.replace('minecraft:flowing_','minecraft:')
    return Block(name,tuple(props))


def run():
    manager=PyMCTranslate.new_translation_manager()
    source=profile('Java 1.21.4');target=profile('Bedrock 1.21.50');translator=Translator(source,target)
    reference_java=manager.get_version('java',source.version).block
    reference_bedrock=manager.get_version('bedrock',target.version).block
    supported=[];unsupported=[];mismatches=[];vectors=0;contexts=0
    for name,schema in source.blocks.items():
        initial=source.initial(name)
        try:translator.block(initial)
        except ValueError:unsupported.append(name);continue
        supported.append(name);cases={initial}
        for key,(_,domain) in schema['properties'].items():
            for value in domain:cases.add(source.block(name,{key:value},defaults=True))
        for block in sorted(cases,key=str):
            try:ours,layers=translator.block(block)
            except ValueError:continue
            vectors+=1
            namespace,base=block.name.split(':',1)
            native=ReferenceBlock(namespace,base,{k:StringTag(v) for k,v in block.properties})
            chunk=Chunk(0,0)
            JavaBlockstateTranslator._unpack_blocks(manager,('java',source.version),chunk,np.array([native],dtype=object))
            parts=[];needs=extra=False
            for layer in chunk.block_palette[0].block_tuple:
                universal,entity,requested=reference_java.to_universal(layer)
                translated,_,requested_target=reference_bedrock.from_universal(universal,entity)
                needs|=requested;extra|=requested_target;parts.append(translated)
            expected=parts[0]
            for layer in parts[1:]:expected=expected+layer
            contexts+=int(needs or extra)
            expected_base=canonical(expected)
            actual_base=Block(ours.name.replace('minecraft:flowing_','minecraft:'),ours.properties)
            expected_extra=tuple(canonical(b) for b in expected.extra_blocks)
            actual_extra=tuple(Block(b.name.replace('minecraft:flowing_','minecraft:'),b.properties) for b in layers)
            if (actual_base,actual_extra)!=(expected_base,expected_extra):
                mismatches.append({'input':str(block),'ours':str(actual_base),'expected':str(expected_base),
                    'ours_layers':list(map(str,actual_extra)),'expected_layers':list(map(str,expected_extra)),'context_or_nbt_requested':bool(needs or extra)})
    return {'reference':'Amulet-Core 1.9.41 / PyMCTranslate 1.2.53','source':source.label,'target':target.label,
            'supported_initial_block_types':len(supported),'unsupported_initial_block_types':len(unsupported),
            'state_vectors':vectors,'reference_requested_context_or_nbt':contexts,'mismatch_count':len(mismatches),
            'normalization':'Reference Java chunk unpacker supplies waterlogged layers. Bedrock flowing_water/flowing_lava are compared to water/lava with matching depth; __version__ is checked separately as palette metadata.',
            'mismatches':mismatches,'unsupported':unsupported}


if __name__=='__main__':print(json.dumps(run(),indent=2))
