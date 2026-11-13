OPERATION={
    'name':'Hollow shell',
    'description':'Outline every selection box, with an optional cleared interior. Overlapping regions are already normalized.',
    'options':[
        {'name':'material','type':'block','default':'glass'},
        {'name':'thickness','type':'int','default':1,'min':1,'max':64},
        {'name':'clear_interior','type':'bool','default':True},
    ],
}


def run(context,options):
    for box in context.selection.boxes:
        lo,hi=box.minimum,box.maximum
        for position in box.positions():
            context.check_cancelled()
            if any(min(v-a,b-v)<options['thickness'] for v,a,b in zip(position,lo,hi)):
                context.set_block(position,options['material'])
            elif options['clear_interior']:context.set_block(position,'air')
