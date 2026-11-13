"""Bounded static Java text components and Bedrock section-code formatting.

Dynamic, event-bearing or unrepresentable formatting is rejected explicitly.
The result preserves text and supported styles, not the original JSON spelling.
"""
import json

COLORS=('black','dark_blue','dark_green','dark_aqua','dark_red','dark_purple','gold','gray',
        'dark_gray','blue','green','aqua','red','light_purple','yellow','white')
CODES={color:format(i,'x') for i,color in enumerate(COLORS)}
STYLES={'obfuscated':'k','bold':'l','italic':'o'}
LIMIT=262144


def java_runs(raw):
    if not isinstance(raw,str) or len(raw)>LIMIT:raise ValueError('Text component exceeds its size limit')
    try:root=json.loads(raw)
    except (ValueError,RecursionError) as exc:raise ValueError('Expected a JSON text component') from exc
    runs=[];characters=0
    def walk(value,inherited,depth):
        nonlocal characters
        if depth>32 or len(runs)>4096:raise ValueError('Text component nesting/run limit exceeded')
        style=dict(inherited)
        if isinstance(value,str):text=value;extra=()
        elif isinstance(value,list):
            if not value:return
            # Java component arrays treat the first element as the parent.
            walk(value[0],style,depth+1)
            first=value[0]
            while isinstance(first,list) and first:first=first[0]
            if isinstance(first,dict):style=attributes(first,style)
            for child in value[1:]:walk(child,style,depth+1)
            return
        elif isinstance(value,dict):
            allowed={'text','extra','color',*STYLES,'underlined','strikethrough'}
            unknown=set(value)-allowed
            if unknown:raise ValueError('Unsupported text component fields: '+', '.join(sorted(unknown)))
            if 'text' not in value or not isinstance(value['text'],str):raise ValueError('Only static text components can cross editions')
            style=attributes(value,style);text=value['text'];extra=value.get('extra',())
            if not isinstance(extra,(list,tuple)):raise ValueError('Text extra must be a list')
        else:raise ValueError('Invalid text component value')
        characters+=len(text)
        if characters>LIMIT:raise ValueError('Expanded text exceeds its size limit')
        if text:
            if '\u00a7' in text:raise ValueError('Literal section signs cannot be distinguished from Bedrock formatting')
            if runs and runs[-1][1]==style:runs[-1]=(runs[-1][0]+text,style)
            else:runs.append((text,style))
        for child in extra:walk(child,style,depth+1)
    def attributes(value,style):
        style=dict(style)
        if 'color' in value:
            if value['color'] not in CODES:raise ValueError('Text color has no exact supported Bedrock formatting code')
            style['color']=value['color']
        for name in (*STYLES,'underlined','strikethrough'):
            if name in value:
                if type(value[name]) is not bool:raise ValueError('Text style flags must be booleans')
                if name in ('underlined','strikethrough') and value[name]:raise ValueError(name+' has no Bedrock text equivalent')
                if value[name]:style[name]=True
                else:style.pop(name,None)
        return style
    walk(root,{},0)
    return runs


def to_bedrock(raw):
    result=[];previous={}
    for text,style in java_runs(raw):
        if style!=previous:
            result.append('\u00a7r')
            if 'color' in style:result.append('\u00a7'+CODES[style['color']])
            result.extend('\u00a7'+code for name,code in STYLES.items() if style.get(name))
        result.append(text);previous=style
    return ''.join(result)


def bedrock_runs(raw):
    if not isinstance(raw,str) or len(raw)>LIMIT:raise ValueError('Bedrock text exceeds its size limit')
    runs=[];style={};start=index=0
    while index<len(raw):
        if raw[index]!='\u00a7':index+=1;continue
        if start<index:runs.append((raw[start:index],dict(style)))
        if index+1>=len(raw):raise ValueError('Incomplete Bedrock formatting code')
        code=raw[index+1].lower()
        if code in '0123456789abcdef':
            # Unlike Java legacy color codes, Bedrock colors retain styles.
            style['color']=COLORS[int(code,16)]
        elif code=='r':style={}
        elif code in STYLES.values():style[next(name for name,c in STYLES.items() if c==code)]=True
        else:raise ValueError('Unsupported Bedrock formatting code: '+code)
        if len(runs)>4096:raise ValueError('Bedrock text has too many formatting runs')
        index+=2;start=index
    if start<len(raw):runs.append((raw[start:],dict(style)))
    return runs


def from_bedrock(raw):
    runs=bedrock_runs(raw)
    if not runs:return json.dumps('')
    if all(not style for _,style in runs):return json.dumps(''.join(t for t,_ in runs),ensure_ascii=False)
    return json.dumps({'text':'','extra':[{'text':text,**style} for text,style in runs]},ensure_ascii=False,separators=(',',':'))


def plain_java(raw):
    runs=java_runs(raw)
    if any(style for _,style in runs):raise ValueError('This field supports only plain text')
    return ''.join(text for text,_ in runs)
