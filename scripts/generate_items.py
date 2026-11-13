"""Generate compact item identity facts from the two pinned primary reports."""
import argparse
import gzip
import hashlib
import json
from pathlib import Path

parser=argparse.ArgumentParser()
parser.add_argument('java',type=Path)
parser.add_argument('bedrock',type=Path)
parser.add_argument('destination',type=Path)
args=parser.parse_args()
java=json.loads(args.java.read_bytes());bedrock=json.loads(args.bedrock.read_bytes())
result={'format':1,'java_version':[1,21,4],'bedrock_version':[1,21,50],
        'java':{name:{'stack':data['components']['minecraft:max_stack_size'],
                      'durability':data['components'].get('minecraft:max_damage',0)} for name,data in sorted(java.items())},
        'bedrock':sorted(entry['serialization_name'] for entry in bedrock['data_items']),
        'input_sha256':{edition:hashlib.sha256(path.read_bytes()).hexdigest() for edition,path in (('java',args.java),('bedrock',args.bedrock))}}
args.destination.parent.mkdir(parents=True,exist_ok=True)
args.destination.write_bytes(gzip.compress(json.dumps(result,sort_keys=True,separators=(',',':')).encode(),mtime=0))
print(json.dumps({'java_items':len(result['java']),'bedrock_items':len(result['bedrock']),
                  'shared_identifiers':len(set(result['java'])&set(result['bedrock'])),'input_sha256':result['input_sha256']},indent=2))
