"""Audit externally supplied Java assets; no game assets are redistributed."""
import argparse,hashlib,json,sys,time
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'src'))
from facetedit.resources import ResourceStack
from facetedit.blocks import Block
from facetedit.scene import build_scene

parser=argparse.ArgumentParser();parser.add_argument('pack');parser.add_argument('--output',default=str(ROOT/'artifacts/resource-corpus.json'));args=parser.parse_args()
started=time.perf_counter();stack=ResourceStack([args.pack]);references=0;faces=0;empty=set();failures=[];variants=0
for name in stack.block_names:
    state=stack.json('blockstates',name);choices=[]
    for condition,entries in state.get('variants',{}).items():
        choices.extend(entries if isinstance(entries,list) else [entries]);variants+=1
        props=dict(pair.split('=',1) for pair in condition.split(',')) if condition else {}
        props={key:value.split('|')[0] for key,value in props.items()}
        block=Block(name,tuple(sorted(props.items())));stack.baked(block)
    for part in state.get('multipart',[]):
        entries=part.get('apply',[]);choices.extend(entries if isinstance(entries,list) else [entries])
    for choice in choices:
        references+=1
        try:
            model=stack._bake(choice);faces+=len(model)
            if not model:empty.add(name)
        except Exception as exc:failures.append({'block':name,'model':choice.get('model'),'error':str(exc)})
fluid_scene=build_scene({(0,0,0):Block('water'),(2,0,0):Block('lava')},stack)
source=Path(args.pack)
report={'scope':'Read-only external asset parsing/model baking. No game execution, pixel comparison with Minecraft, universal state translation or native Windows/macOS validation.',
        'source_file':source.name,'sha256':hashlib.sha256(source.read_bytes()).hexdigest() if source.is_file() else None,
        'blockstate_files':len(stack.block_names),'variant_conditions':variants,'model_references':references,'baked_faces':faces,
        'empty_json_models':sorted(empty),'model_parse_failures':failures,'fluid_scene_faces':len(fluid_scene.surfaces),
        'seconds':round(time.perf_counter()-started,3)}
Path(args.output).write_text(json.dumps(report,indent=2)+'\n');stack.close()
print(json.dumps({key:value for key,value in report.items() if key not in ('empty_json_models','model_parse_failures')},indent=2))
print('Empty JSON models:',len(empty),'Parsing failures:',len(failures))
for failure in failures[:10]:print(failure)
if failures:raise SystemExit(1)
