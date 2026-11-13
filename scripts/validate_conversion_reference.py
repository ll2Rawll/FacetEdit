"""Optional native-format interoperability check in an isolated Amulet install."""
from pathlib import Path
import json
import sys
import tempfile

ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'src'));sys.path.insert(0,str(ROOT))
from facetedit.blocks import Block
from facetedit import nbt
from facetedit.converter import prepare_conversion,publish_conversion
from facetedit.model import Document,Selection
from facetedit.world import open_world
from tests.test_conversion import plain_java,modern_bedrock
from tests.fixtures import java_world
import amulet
import numpy as np
from amulet.level.translators.chunk.java.java_blockstate_translator import JavaBlockstateTranslator


with tempfile.TemporaryDirectory(prefix='facetedit-reference-world-') as temporary:
    root=Path(temporary);results=[]
    for edition in ('Java','Bedrock'):
        if edition=='Java':
            doc=plain_java(root/'source-java');target=open_world(modern_bedrock(root/'target-bedrock'))
            block=Block.parse('oak_stairs[facing=west,half=top,shape=straight,waterlogged=true]')
            version=('bedrock',(1,21,50))
        else:
            doc=Document(open_world(modern_bedrock(root/'source-bedrock')))
            target_path=java_world(root/'target-java')
            metadata=nbt.loads((target_path/'level.dat').read_bytes(),compressed=True)[1]
            metadata.value['Data'].value['WorldGenSettings']=nbt.compound(dimensions=nbt.Tag(nbt.COMPOUND,{
                'minecraft:'+name:nbt.compound(type=nbt.Tag(nbt.STRING,'minecraft:'+name)) for name in ('overworld','the_nether','the_end')}))
            (target_path/'level.dat').write_bytes(nbt.dumps(metadata,compressed=True));target=open_world(target_path)
            from facetedit.registry import profile
            block=profile('Bedrock 1.21.50').block('minecraft:oak_stairs',{'weirdo_direction':'1','upside_down_bit':'true'})
            version=('java',(1,21,4))
        doc.selection=Selection((2,10,2),(2,10,2));doc.fill(block)
        if edition=='Bedrock':doc.waterlog()
        plan=prepare_conversion(doc,target)
        try:
            assert plan.report.ok,plan.report.summary()
            output=publish_conversion(plan,root/('converted-'+edition))
        finally:plan.close()
        reference=amulet.load_level(str(output))
        try:
            native,entity=reference.get_version_block(2,10,2,'minecraft:overworld',version)
            stone,_=reference.get_version_block(-16,1,-16,'minecraft:overworld',version)
            assert native.namespaced_name=='minecraft:oak_stairs',native
            assert stone.namespaced_name=='minecraft:stone',stone
            if edition=='Java':
                assert native.properties['weirdo_direction'].py_int==1,native
                assert native.properties['upside_down_bit'].py_int==1,native
                assert len(native.extra_blocks)==1,native
                assert native.extra_blocks[0].base_name in ('water','flowing_water'),native
            else:
                # get_version_block exposes separated fluid layers; Java's chunk
                # palette packer turns that reference representation into the
                # actual waterlogged property used on disk.
                native=JavaBlockstateTranslator()._pack_block_palette(reference.translation_manager.get_version(*version),np.array([native],dtype=object))[0]
                assert native.properties['facing'].py_str=='west',native
                assert native.properties['half'].py_str=='top',native
                assert native.properties['waterlogged'].py_str=='true',native
            results.append({'source':edition,'target':version[0],'native_reference_reopen':'pass','negative_chunk':'pass','direction_and_waterlogging':'pass'})
        finally:reference.close()
    from facetedit.registry import profile
    from facetedit.structures import export_structure
    doc=Document(open_world(modern_bedrock(root/'paint-source')))
    slab=profile('Bedrock 1.21.50').block('minecraft:oak_slab',{'minecraft:vertical_half':'top'})
    doc.selection=Selection((1,5,2),(1,5,2));doc.fill(slab);doc.copy()
    world_output=root/'painted';doc.world.export(world_output,doc.edits,**doc.export_metadata())
    structure_output=root/'painted.mcstructure';export_structure(doc.clipboard,structure_output)
    for path,position in ((world_output,(1,5,2)),(structure_output,(0,0,0))):
        reference=amulet.load_level(str(path))
        try:
            native,_=reference.get_version_block(*position,reference.dimensions[0],('bedrock',(1,21,50)))
            assert native.namespaced_name=='minecraft:oak_slab',native
            assert native.properties['minecraft:vertical_half'].py_str=='top',native
            results.append({'operation':'native Bedrock edit','format':path.suffix or 'LevelDB world',
                            'native_reference_reopen':'pass','current_palette_version_and_top_slab':'pass'})
        finally:reference.close()
    print(json.dumps({'reference':'Amulet-Core 1.9.41, native amulet-leveldb 1.0.7','game_execution':False,'cases':results},indent=2))
