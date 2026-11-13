OPERATION={
    'name':'Checkerboard',
    'description':'Fill your selection with alternating materials. The entire pattern is one undo step.',
    'options':[
        {'name':'first','type':'block','default':'white_concrete'},
        {'name':'second','type':'block','default':'stone'},
        {'name':'cell_size','type':'int','default':2,'min':1,'max':128},
    ],
}


def run(context,options):
    size=options['cell_size']
    for position in context.positions():
        parity=sum(value//size for value in position)%2
        context.set_block(position,options['first' if parity==0 else 'second'])
