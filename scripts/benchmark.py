"""Reproducible core benchmarks. Run with PYTHONPATH=src."""
from pathlib import Path
import json
import platform
import statistics
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from facetedit import nbt
from facetedit.blocks import Block
from facetedit.formats import decode_java_section, encode_java_section
from facetedit.leveldb import crc32c
from facetedit.model import Document, Selection
from facetedit.world import SampleWorld


def measure(function, iterations=7):
    values = []
    for _ in range(iterations):
        start = time.perf_counter()
        function()
        values.append((time.perf_counter()-start)*1000)
    return {"median_ms": round(statistics.median(values), 3), "min_ms": round(min(values), 3), "max_ms": round(max(values), 3), "iterations": iterations}


blocks = [Block("test:block_"+str(i % 37)) for i in range(4096)]
section = {}
encode_java_section(section, blocks, 4189)
tag = nbt.compound(values=nbt.Tag(nbt.LONG_ARRAY, list(range(65536))))
raw = nbt.dumps(tag)


def edit():
    document = Document(SampleWorld())
    document.selection = Selection((0,30,0),(31,61,31))
    document.fill(Block("glass"))
    document.undo()
    document.redo()


results = {
    "machine": {"python": sys.version.split()[0], "system": platform.system(), "machine": platform.machine()},
    "nbt_decode_65536_longs": measure(lambda: nbt.loads(raw)),
    "palette_decode_4096_blocks_37_states": measure(lambda: decode_java_section(section, 4189)),
    "palette_encode_4096_blocks_37_states": measure(lambda: encode_java_section({}, blocks, 4189)),
    "crc32c_1MiB": measure(lambda: crc32c(b"x"*1048576), 3),
    "fill_undo_redo_32768_blocks": measure(edit, 3),
}
print(json.dumps(results, indent=2))
