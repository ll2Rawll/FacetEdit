"""Native book content conversion, with explicit text/filtering constraints."""
from . import nbt,text_components
from .payload_fields import Fields

WRITABLE='minecraft:writable_book_content'
WRITTEN='minecraft:written_book_content'


def units(text):return len(text.encode('utf-16-be','surrogatepass'))//2


def filterable(tag,path):
    if tag.kind==nbt.STRING:return tag.value
    f=Fields(tag,path);raw=f.pop('raw',nbt.STRING)
    if f.pop('filtered',nbt.STRING,raw)!=raw:raise ValueError(path+': different filtered text cannot be retained')
    f.finish();return raw


def to_bedrock(components,tag,name):
    key=WRITTEN if name=='written_book' else WRITABLE
    if not any(k in components.data for k in (WRITABLE,WRITTEN)):return
    if name not in ('writable_book','written_book') or key not in components.data:
        raise ValueError(components.path+': book content does not match the item kind')
    f=Fields(components.pop(key,nbt.COMPOUND),components.path+'.'+key)
    pages=f.pop('pages',nbt.LIST,nbt.ListValue(nbt.STRING,[]))
    if pages.values and pages.kind not in (nbt.STRING,nbt.COMPOUND):raise ValueError(f.path+'.pages: invalid page list type')
    if len(pages.values)>100:raise ValueError(f.path+'.pages: more than 100 pages')
    out=[]
    for i,value in enumerate(pages.values):
        raw=filterable(nbt.Tag(pages.kind,value),f'{f.path}.pages[{i}]')
        if units(raw)>(32767 if name=='written_book' else 1024):raise ValueError(f.path+'.pages: page exceeds the Java content limit')
        content=text_components.to_bedrock(raw) if name=='written_book' else raw
        out.append({'text':nbt.Tag(nbt.STRING,content),'photoname':nbt.Tag(nbt.STRING,'')})
    tag['pages']=nbt.Tag(nbt.LIST,nbt.ListValue(nbt.COMPOUND,out))
    if name=='written_book':
        title_tag=f.data.pop('title',None)
        if title_tag is None:raise ValueError(f.path+'.title: required field is missing')
        title=filterable(title_tag,f.path+'.title')
        if units(title)>32:raise ValueError(f.path+'.title: more than 32 UTF-16 units')
        generation=f.pop('generation',nbt.INT,0)
        if not 0<=generation<=2:raise ValueError(f.path+'.generation: Bedrock represents book generations 0–2')
        # Dynamic components are rejected by text conversion. Resolution is
        # consequently idempotent; Java's resolved marker has no Bedrock field.
        f.flag('resolved')
        tag.update(title=nbt.Tag(nbt.STRING,title),author=nbt.Tag(nbt.STRING,f.pop('author',nbt.STRING)),generation=nbt.Tag(nbt.INT,generation))
    f.finish()


def to_java(tag,components,name):
    keys={'pages','title','author','generation','xuid'}
    if not keys.intersection(tag.data):return
    if name not in ('writable_book','written_book'):raise ValueError(tag.path+': native book fields require a book item')
    pages=tag.pop('pages',nbt.LIST,nbt.ListValue(nbt.COMPOUND,[]))
    if len(pages.values)>100 or pages.values and pages.kind!=nbt.COMPOUND:raise ValueError(tag.path+'.pages: invalid book page list')
    out=[]
    for i,page in enumerate(pages.values):
        f=Fields(page,f'{tag.path}.pages[{i}]');raw=f.pop('text',nbt.STRING,'');f.default_only('photoname',nbt.STRING,'');f.finish()
        content=text_components.from_bedrock(raw) if name=='written_book' else raw
        if units(content)>(32767 if name=='written_book' else 1024):raise ValueError(f.path+': page exceeds the Java content limit')
        out.append(content)
    result={'pages':nbt.Tag(nbt.LIST,nbt.ListValue(nbt.STRING,out))}
    if name=='written_book':
        title=tag.pop('title',nbt.STRING,'');generation=tag.pop('generation',nbt.INT,0)
        if units(title)>32 or not 0<=generation<=2:raise ValueError(tag.path+': invalid title length or generation')
        tag.default_only('xuid',nbt.STRING,'')
        result.update(title=nbt.Tag(nbt.STRING,title),author=nbt.Tag(nbt.STRING,tag.pop('author',nbt.STRING,'')),
                      generation=nbt.Tag(nbt.INT,generation),resolved=nbt.Tag(nbt.BYTE,1))
    components[WRITTEN if name=='written_book' else WRITABLE]=nbt.Tag(nbt.COMPOUND,result)
