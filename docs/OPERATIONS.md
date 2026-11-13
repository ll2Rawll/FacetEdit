# FacetEdit operation API

World → Custom operations loads a `.py` file, displays its literal metadata and
option fields, and runs it only after **Run operation**. Loading/discovery uses
AST parsing and does not execute imports or top-level code. Execution is trusted
Python with the user's account privileges, not a sandbox. No Amulet, NumPy or wx
runtime or compatibility shim is supplied.

```python
OPERATION = {
    'name': 'My fill',
    'description': 'Replace the selection with a chosen block.',
    'options': [{'name': 'material', 'type': 'block', 'default': 'stone'}],
}

def run(context, options):
    for position in context.positions():
        context.set_block(position, options['material'])
```

`run` may return `None` or yield progress fractions between zero and one. Typed
options are `int` (optional min/max), `bool`, `block`, `choice` (choices list) and
`text`. A block option becomes `facetedit.blocks.Block`; other options retain
their corresponding primitive values. Scripts are limited to 256 KiB and 16
option definitions. Original checkerboard and hollow-shell examples are included.

| Context API | Behavior |
| --- | --- |
| `selection` | SelectionGroup with boxes, inclusive bounds and unique positions |
| `dimension`, `edition` | Current dimension and Java/Bedrock identifier |
| `positions()` | Unique selected coordinates; checks cancellation and reports progress |
| `get_block(position)` | Block at an integer coordinate, including staged script changes |
| `set_block(position, block, preserve_layers=False)` | Stage a Block or block string; replacing the primary block clears its NBT |
| `get_extra_blocks(position)` | Tuple of additional Bedrock layers |
| `set_extra_blocks(position, layers)` | Stage extra layers; validated before commit |
| `get_nbt(position)` | Typed big-endian NBT bytes or None, including staged script changes |
| `set_nbt(position, tag_or_bytes_or_none)` | Stage block NBT; xyz and id validated at commit |
| `progress(fraction)` | Report progress and check cancellation |
| `check_cancelled()` | Raise Cancelled when the user cancels |

The operation sees a snapshot of staged workspace edits and reads its own
proposals. Use only the public API, not private document/world internals. At most
65,536 unique block positions may be proposed; proposals may lie outside the
selection but must pass world bounds/chunk validation. Execution exceptions,
SystemExit, KeyboardInterrupt, cancellation and failed validation discard the
proposals. A changed workspace rejects stale results. A successful run commits
as one undoable transaction, including block NBT and layers.

Cancellation is cooperative: call `positions`, progress or `check_cancelled`
inside long loops. The editor cannot forcibly stop arbitrary Python code or
undo filesystem/network changes a trusted script makes outside this API.
