"""Capture the actual new-profile preflight and native state controls."""
from pathlib import Path
import subprocess,sys,tempfile,time,tkinter as tk
ROOT=Path(__file__).resolve().parents[1];sys.path[:0]=[str(ROOT/'src'),str(ROOT)]
from facetedit.ui import FacetEditApp
from facetedit.model import Document,Selection
from facetedit.world import open_world
from tests.test_conversion import plain_java
from tests.version_fixture import bedrock_version,gallery


def capture(window,name):
    window.update();subprocess.run(['import','-window',str(window.winfo_id()),str(ROOT/'artifacts'/name)],check=True)


with tempfile.TemporaryDirectory(prefix='facetedit-versions-review-') as temporary:
    path=Path(temporary);source=plain_java(path/'java');gallery(source)
    source.selection=Selection((0,15,0),(17,25,15));source.copy()
    app=FacetEditApp(path/'settings.json');app.update()
    try:
        app._attach(source);app.translate_clipboard_dialog();app.update()
        window=next(w for w in app.winfo_children() if isinstance(w,tk.Toplevel));c=window.conversion_controls
        c['target'].set('Bedrock 1.21.60');c['preview']();deadline=time.monotonic()+30
        while app.busy and time.monotonic()<deadline:app.update();time.sleep(.005)
        assert c['prepared'][0] is not None,c['report'].get('1.0','end')
        capture(window,'versions-conversion.png');window.destroy()
        app._attach(Document(open_world(bedrock_version(path/'bedrock60'))));app.material_dialog();app.update()
        window=next(w for w in app.winfo_children() if isinstance(w,tk.Toplevel));c=window.material_controls
        assert c['profile'].get()=='Bedrock 1.21.60'
        c['search'].set('wooden_door');app.update();c['states']['minecraft:cardinal_direction'].set('north');app.update()
        capture(window,'versions-materials.png');window.destroy()
    finally:app.destroy()
