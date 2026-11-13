"""Capture the real desktop and measure warm redraws. Test tooling only.

Run on an X display with ImageMagick's `import` installed for screenshots.
Neither ImageMagick nor Xvfb is bundled or required by the application.
"""
from pathlib import Path
import json
import platform
import statistics
import subprocess
import sys
import tempfile
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from facetedit.ui import FacetEditApp


def capture(widget,name):
    widget.update()
    subprocess.run(['import','-window',str(widget.winfo_id()),str(ROOT/'artifacts'/name)],check=True)


with tempfile.TemporaryDirectory() as temporary:
    start = time.perf_counter()
    app = FacetEditApp(Path(temporary)/'settings.json')
    app.update();app.viewport.draw();app.update()
    ready = (time.perf_counter()-start)*1000
    capture(app,'workspace.png')
    timings = []
    for i in range(12):
        app.viewport.angle += .015
        app.viewport.draw()
        timings.append(app.viewport.last_ms)
    report = {
        'python':sys.version.split()[0],'platform':platform.platform(),
        'tk':app.tk.call('info','patchlevel'),'window':'1440x900','radius':app.viewport.radius,
        'window_ready_ms':round(ready,3),'visible_faces':app.viewport.face_count,
        'warm_redraw_ms':{'median':round(statistics.median(timings),3),'min':round(min(timings),3),'max':round(max(timings),3),'iterations':len(timings)},
        'scope':'Synthetic sample, CPU Tk Canvas, this Linux host only. No comparison with Amulet or native Windows/macOS.'
    }
    app.viewport.reset()
    app.geometry('1040x700');app.update();app.viewport.draw();app.update()
    capture(app,'compact.png')
    app.geometry('1440x900');app.update()
    app._pick((-6,8,-4),False);app._pick((-3,11,-1),True)
    app.block_var.set('minecraft:gold_block');app.fill();app.update();app.viewport.draw();app.update()
    capture(app,'selection.png')
    app.inspector_tabs.select(2);capture(app,'world-tools.png')
    app.inspector_tabs.select(3);capture(app,'history.png')
    app.destroy()
    (ROOT/'artifacts/renderer-benchmark.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report,indent=2))
