"""Verify dependency/import boundaries, assets and the tested executable's hash."""
import ast,hashlib,json,sys,zipfile
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
archive=ROOT/'dist/FacetEdit.pyz'
with zipfile.ZipFile(archive) as package:
    modules=[name for name in package.namelist() if name.endswith('.py')]
    imports=set()
    for name in modules:
        tree=ast.parse(package.read(name),filename=name)
        for node in ast.walk(tree):
            if isinstance(node,ast.Import):imports.update(alias.name.split('.')[0] for alias in node.names)
            elif isinstance(node,ast.ImportFrom) and node.level==0 and node.module:imports.add(node.module.split('.')[0])
    unsupported=imports-(sys.stdlib_module_names|{'facetedit','__future__'})
    assert not unsupported,unsupported
    assets=[name for name in package.namelist() if name.endswith('.png')]
    assert len(assets)==3,assets
    assert not any('site-packages' in name or 'amulet' in name or '__pycache__' in name for name in package.namelist())
sys.path.insert(0,str(archive))
import facetedit
assert str(archive) in facetedit.__file__,facetedit.__file__
from facetedit.registry import profile
from facetedit.translation import LOGS, LEAVES, STATELESS
profiles={name:profile(name) for name in ('Java 1.21.4','Bedrock 1.21.50','Bedrock 1.21.60')}
assert len(profiles['Java 1.21.4'].blocks)==1095
assert len(profiles['Bedrock 1.21.50'].blocks)==1241
assert profiles['Bedrock 1.21.50'].palette_version==18163713
assert len(profiles['Bedrock 1.21.60'].blocks)==1241
assert profiles['Bedrock 1.21.60'].palette_version==18168865
assert 'minecraft:cardinal_direction' in dict(profiles['Bedrock 1.21.60'].initial('minecraft:wooden_door').state_types)
assert len(STATELESS)==307 and 'minecraft:mushroom_stem' not in LOGS
assert 'minecraft:oak_log' in LOGS and 'minecraft:oak_leaves' in LEAVES
from facetedit.state_facts import catalog
from facetedit.item_translation import JAVA_ITEMS,BEDROCK_ITEMS,item_catalog
from facetedit.payload_formats import COLORS,TEXT_RGB
facts=catalog();assert sum(len(block['states']) for block in facts['blocks'].values())==27866
assert tuple(facts['text_colors'][name] for name in COLORS)==TEXT_RGB
assert len(JAVA_ITEMS)==1385 and len(BEDROCK_ITEMS)==1370
assert len(item_catalog((1,21,60))[1])==1369 and 'minecraft:air' not in item_catalog((1,21,60))[1]
report={'version':facetedit.__version__,'module_origin':facetedit.__file__,'python_modules':len(modules),
        'third_party_imports':sorted(unsupported),'logo_assets':assets,
        'bundled_block_definitions':{name:len(value.blocks) for name,value in profiles.items()},
        'native_bedrock_palette_versions':{name:value.palette_version for name,value in profiles.items() if value.edition=='Bedrock'},
        'bundled_primary_state_facts':27866,'bundled_item_identities':{'Java':len(JAVA_ITEMS),'Bedrock 1.21.50':len(BEDROCK_ITEMS),'Bedrock 1.21.60':len(item_catalog((1,21,60))[1])},
        'bytes':archive.stat().st_size,'sha256':hashlib.sha256(archive.read_bytes()).hexdigest()}
print(json.dumps(report,indent=2))
