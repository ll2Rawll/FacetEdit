import ctypes as C
import json,random,tempfile,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from facetedit.leveldb import load_database,write_database,snappy_decode
import argparse,ctypes.util
parser=argparse.ArgumentParser(description='Optional independent verification; native libraries are test tools only')
parser.add_argument('--leveldb',default=ctypes.util.find_library('leveldb'))
parser.add_argument('--snappy',default=ctypes.util.find_library('snappy'))
options=parser.parse_args()
if not options.leveldb or not options.snappy: parser.error('Provide --leveldb and --snappy paths to independently installed test libraries')
lib=C.CDLL(options.leveldb)
P=C.c_void_p; S=C.c_char_p; N=C.c_size_t
for name,args,result in [
 ('leveldb_options_create',[],P),('leveldb_options_set_create_if_missing',[P,C.c_ubyte],None),
 ('leveldb_options_destroy',[P],None),('leveldb_open',[P,S,C.POINTER(S)],P),('leveldb_close',[P],None),
 ('leveldb_readoptions_create',[],P),('leveldb_readoptions_destroy',[P],None),
 ('leveldb_writeoptions_create',[],P),('leveldb_writeoptions_destroy',[P],None),
 ('leveldb_get',[P,P,S,N,C.POINTER(N),C.POINTER(S)],P),('leveldb_free',[P],None),
 ('leveldb_put',[P,P,S,N,S,N,C.POINTER(S)],None),('leveldb_delete',[P,P,S,N,C.POINTER(S)],None),
 ('leveldb_compact_range',[P,S,N,S,N],None)]:
 f=getattr(lib,name);f.argtypes=args;f.restype=result

def check(err):
 if err.value: raise RuntimeError(err.value.decode())

def open_db(path,create=False):
 options=lib.leveldb_options_create();lib.leveldb_options_set_create_if_missing(options,int(create));error=S()
 db=lib.leveldb_open(options,str(path).encode(),C.byref(error));check(error);lib.leveldb_options_destroy(options);return db

report={}
with tempfile.TemporaryDirectory() as tmp:
 path=Path(tmp)/'ours';values={f'key{i:04}'.encode(): (b'value:'+bytes([i%255]))*100 for i in range(1000)}
 values[b'large']=b'abc'*50000
 write_database(path,values)
 db=open_db(path);readopts=lib.leveldb_readoptions_create()
 for k,v in values.items():
  size=N();error=S();pointer=lib.leveldb_get(db,readopts,k,len(k),C.byref(size),C.byref(error));check(error)
  assert C.string_at(pointer,size.value)==v,k
  lib.leveldb_free(pointer)
 lib.leveldb_readoptions_destroy(readopts);lib.leveldb_close(db)
 report['facetedit_snapshot_read_by_native_leveldb']={'keys_verified':len(values),'result':'pass'}
 path=Path(tmp)/'native';db=open_db(path,True);writeopts=lib.leveldb_writeoptions_create()
 for k,v in values.items():
  error=S();lib.leveldb_put(db,writeopts,k,len(k),v,len(v),C.byref(error));check(error)
 for k in list(values)[:100]:
  error=S();lib.leveldb_delete(db,writeopts,k,len(k),C.byref(error));check(error);del values[k]
 lib.leveldb_compact_range(db,None,0,None,0);lib.leveldb_writeoptions_destroy(writeopts);lib.leveldb_close(db)
 assert list(path.glob('*.ldb')),list(path.iterdir())
 assert load_database(path)==values
 report['native_snappy_sst_and_tombstones_read_by_facetedit']={'keys_verified':len(values),'result':'pass'}
snappy=C.CDLL(options.snappy)
snappy.snappy_max_compressed_length.argtypes=[N];snappy.snappy_max_compressed_length.restype=N
snappy.snappy_compress.argtypes=[S,N,P,C.POINTER(N)];snappy.snappy_compress.restype=C.c_int
rng=random.Random(5)
corpora=[b'',b'abcd'*100000,bytes(range(256))*1000,bytes(rng.randrange(256) for _ in range(100000)),b'x'*1000000]
for raw in corpora:
 size=N(snappy.snappy_max_compressed_length(len(raw)));out=C.create_string_buffer(size.value)
 assert snappy.snappy_compress(raw,len(raw),out,C.byref(size))==0
 assert snappy_decode(out.raw[:size.value])==raw
report['native_snappy_streams_read_by_facetedit']={'corpora':len(corpora),'result':'pass'}
report['scope']='Independent Debian LevelDB 1.23 / system Snappy verification only; not Minecraft-game validation. Native libraries are not application dependencies or bundled in FacetEdit.'
print(json.dumps(report,indent=2))
