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
report={'version':facetedit.__version__,'module_origin':facetedit.__file__,'python_modules':len(modules),
        'third_party_imports':sorted(unsupported),'logo_assets':assets,
        'bytes':archive.stat().st_size,'sha256':hashlib.sha256(archive.read_bytes()).hexdigest()}
print(json.dumps(report,indent=2))
