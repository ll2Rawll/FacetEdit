"""Run the optional primary Java metadata reporter; no server/game is started."""
import argparse
import gzip
import hashlib
import json
import os
from pathlib import Path
import subprocess
import tempfile
import zipfile

parser=argparse.ArgumentParser()
parser.add_argument('report_root',type=Path)
parser.add_argument('destination',type=Path)
parser.add_argument('--client',type=Path,required=True,help='Pinned official 1.21.4 client JAR containing primary block tags')
args=parser.parse_args()
root=args.report_root
server=root/'versions/1.21.4/server-1.21.4.jar'
blocks_path=root/'generated/reports/blocks.json'
blocks=json.loads(blocks_path.read_bytes())
maximum=max(s['id'] for b in blocks.values() for s in b['states'])
classpath=os.pathsep.join(str(p) for p in (server,*root.joinpath('libraries').rglob('*.jar')))
reporter=Path(__file__).with_name('PrimaryStateReport.java')
with zipfile.ZipFile(args.client) as archive:
    prefix='data/minecraft/tags/block/'
    tags={name[len(prefix):-5]:json.loads(archive.read(name))['values'] for name in archive.namelist() if name.startswith(prefix) and name.endswith('.json')}
def resolve(name,chain=()):
    if name in chain:raise ValueError('Recursive primary tag: '+name)
    result=set()
    for entry in tags[name]:
        value=entry['id'] if isinstance(entry,dict) else entry
        result.update(resolve(value.removeprefix('#minecraft:'),(*chain,name)) if value.startswith('#') else (value,))
    return result
members={name:[] for name in blocks}
for name in sorted(tags):
    for member in resolve(name):members[member].append('minecraft:'+name)
def first(name):return str(blocks['minecraft:'+name]['states'][0]['id'])
with tempfile.TemporaryDirectory(prefix='facetedit-primary-facts-') as scratch:
    tag_file=Path(scratch)/'tags.txt'
    tag_file.write_text('\n'.join(str(blocks[name]['states'][0]['id'])+' '+' '.join(values) for name,values in members.items()))
    run=subprocess.run(['java','--class-path',classpath,str(reporter),str(maximum),str(tag_file),first('oak_fence'),first('nether_brick_fence'),first('iron_bars')],cwd=scratch,capture_output=True,text=True)
    if run.returncode:raise RuntimeError(run.stdout[-5000:]+'\n'+run.stderr[-5000:])
facts={};colors={}
for line in run.stdout.splitlines():
    fields=line.split()
    if fields and fields[0]=='STATE':facts[int(fields[1])]=(int(fields[2]),fields[3]=='true',fields[4],*(int(v) for v in fields[5:8]),*(v=='true' for v in fields[8:11]),int(fields[11]),fields[12]=='true')
    elif fields and fields[0]=='COLOR':colors[fields[1]]=int(fields[2])
assert len(facts)==maximum+1,(len(facts),maximum)
result={'format':1,'edition':'Java','version':[1,21,4],'data_version':4189,
        'face_order':['down','up','north','south','west','east'],
        'context':'EmptyBlockGetter at BlockPos.ZERO after Bootstrap with official client block tags bound to each registry holder. Connection masks are native fence/pane predicates against each neighbour face.',
        'fields':['sturdy_faces','connection_exception','instrument','wooden_fence_faces','nether_fence_faces','pane_faces','redstone_conductor','signal_source','flammable','wire_connection_faces','wire_vertical_connection'],
        'server_sha256':hashlib.sha256(server.read_bytes()).hexdigest(),
        'client_sha256':hashlib.sha256(args.client.read_bytes()).hexdigest(),
        'blocks_input_sha256':hashlib.sha256(blocks_path.read_bytes()).hexdigest(),
        'reporter_sha256':hashlib.sha256(reporter.read_bytes()).hexdigest(),'text_colors':colors,'blocks':{}}
for name,data in sorted(blocks.items()):
    properties=sorted(data.get('properties',{}));entries={}
    for state in data['states']:
        key=','.join(state.get('properties',{}).get(p,'') for p in properties)
        entries[key]=facts[state['id']]
    result['blocks'][name]={'properties':properties,'states':entries}
args.destination.parent.mkdir(parents=True,exist_ok=True)
args.destination.write_bytes(gzip.compress(json.dumps(result,sort_keys=True,separators=(',',':')).encode(),mtime=0))
print(json.dumps({'block_types':len(blocks),'block_states':len(facts),'colors':colors,'output_bytes':args.destination.stat().st_size,
                  'input_sha256':result['blocks_input_sha256'],'reporter_sha256':result['reporter_sha256']},indent=2))
