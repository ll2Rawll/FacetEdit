"""Capture the real desktop and measure redraws. Optional ImageMagick/X display.

These test tools are neither bundled nor required by the application.
"""
from pathlib import Path
import json
import platform
import statistics
import subprocess
import sys
import tempfile
import time

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'));sys.path.insert(0,str(ROOT))
from facetedit.ui import FacetEditApp
from facetedit.model import Document,Selection,SelectionGroup
from facetedit.world import open_world
from tests.fixtures import java_world


def capture(widget,name):
    widget.update()
    subprocess.run(['import','-window',str(widget.winfo_id()),str(ROOT/'artifacts'/name)],check=True)


def draws(view,flight=False):
    values=[]
    for _ in range(12):
        if flight:view.camera.look(2.5,0)
        else:view.angle+=.015
        view.draw();values.append(view.last_ms)
    return {'median':round(statistics.median(values),3),'min':round(min(values),3),'max':round(max(values),3),'iterations':len(values),'last_visible_faces':view.face_count}


with tempfile.TemporaryDirectory() as temporary:
    start=time.perf_counter();app=FacetEditApp(Path(temporary)/'settings.json')
    app.update();app.viewport.draw();app.update();ready=(time.perf_counter()-start)*1000
    capture(app,'workspace.png')
    report={'python':sys.version.split()[0],'platform':platform.platform(),'tk':app.tk.call('info','patchlevel'),
            'window':'1440x900','radius':app.viewport.radius,'window_ready_ms':round(ready,3),
            'orbit_warm_redraw_ms':draws(app.viewport),
            'scope':'Synthetic sample, CPU Tk Canvas, this Linux host only. No Amulet or native Windows/macOS comparison.'}
    app.viewport.reset();app.toggle_camera();app.update();app.viewport.draw();capture(app,'flight.png')
    report['perspective_warm_redraw_ms']=draws(app.viewport,True)
    start=time.perf_counter();app.viewport.camera.position[0]+=8;app.viewport.draw()
    report['perspective_new_volume_draw_ms']=round((time.perf_counter()-start)*1000,3)
    app.geometry('1040x700');app.update();app.viewport.draw();capture(app,'flight-compact.png')
    app.toggle_camera();app.viewport.center_x=app.viewport.center_z=0;app.viewport.reset();app.update();app.viewport.draw();capture(app,'compact.png')
    app.geometry('1440x900');app.update()
    app._pick((-6,8,-4),False);app._pick((-3,11,-1),True)
    app.block_var.set('minecraft:gold_block');app.fill();app.update();app.viewport.draw();capture(app,'selection.png')
    app.document.selection=SelectionGroup((app.document.selection,Selection((3,9,-4),(6,12,-1))))
    app.regions_dialog();app.update();dialog=app.region_list.winfo_toplevel();capture(dialog,'regions.png');dialog.destroy()
    app.inspector_tabs.select(2);capture(app,'world-tools.png')
    app.inspector_tabs.select(3);capture(app,'history.png')
    app._autosave_tick(reschedule=False)
    while app._recovery_inflight:app.update();time.sleep(.005)
    app.recovery_dialog();app.update();dialog=app.recovery_list.winfo_toplevel();capture(dialog,'recovery.png');dialog.destroy()
    app._attach(Document(open_world(java_world(Path(temporary)/'world'))));app.chunks_dialog();app.update()
    while app.busy:app.update();time.sleep(.005)
    app.document.selection=Selection((0,0,0),(31,0,15));app.refresh();dialog=app.chunk_map.winfo_toplevel();capture(dialog,'chunks.png');dialog.destroy()
    app.destroy()
    (ROOT/'artifacts/renderer-benchmark.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))
