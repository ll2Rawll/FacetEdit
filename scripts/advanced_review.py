"""Capture real desktop conversion and book inspection for the expanded corpus."""
from pathlib import Path
import subprocess,sys,tempfile,time,tkinter as tk
ROOT=Path(__file__).resolve().parents[1];sys.path[:0]=[str(ROOT/'src'),str(ROOT)]
from facetedit.ui import FacetEditApp
from facetedit.model import Document,Selection
from facetedit.converter import prepare_conversion,publish_conversion
from facetedit.world import open_world
from tests.advanced_fixture import gallery
from tests.test_conversion import plain_java,modern_bedrock

def capture(widget,name):
    widget.update();subprocess.run(['import','-window',str(widget.winfo_id()),str(ROOT/'artifacts'/name)],check=True)

with tempfile.TemporaryDirectory(prefix='facetedit-advanced-review-') as temporary:
    path=Path(temporary);source=plain_java(path/'java');positions=gallery(source)
    source.selection=Selection((0,15,0),(17,25,11));source.copy()
    app=FacetEditApp(path/'settings.json');app.update();app._attach(source)
    app.translate_clipboard_dialog();app.update();window=next(w for w in app.winfo_children() if isinstance(w,tk.Toplevel))
    controls=window.conversion_controls;controls['target'].set('Bedrock 1.21.50');controls['preview']()
    deadline=time.monotonic()+30
    while app.busy and time.monotonic()<deadline:app.update();time.sleep(.005)
    assert controls['prepared'][0] is not None,controls['report'].get('1.0','end')
    capture(window,'advanced-conversion.png');window.destroy()
    plan=prepare_conversion(source,open_world(modern_bedrock(path/'template')))
    try:
        assert plan.report.ok,plan.report.summary();converted=publish_conversion(plan,path/'converted')
    finally:plan.close()
    app._attach(Document(open_world(converted)));app.document.selection=Selection(positions['lectern'],positions['lectern']);app.refresh()
    app.nbt_dialog();app.update();window=next(w for w in app.winfo_children() if isinstance(w,tk.Toplevel))
    def walk(parent):
        for child in parent.winfo_children():
            yield child;yield from walk(child)
    editor=next(w for w in walk(window) if isinstance(w,tk.Text));editor.yview(editor.search('"pages"','1.0'))
    capture(window,'advanced-book-inspector.png');window.destroy();app.destroy()
