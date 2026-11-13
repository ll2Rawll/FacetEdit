"""Capture the real desktop payload conversion and inventory inspection flows."""
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import tkinter as tk

ROOT=Path(__file__).resolve().parents[1];sys.path[:0]=[str(ROOT/'src'),str(ROOT)]
from facetedit.ui import FacetEditApp
from facetedit.model import Document,Selection
from facetedit.converter import prepare_conversion,publish_conversion
from facetedit.world import open_world
from tests.test_conversion import plain_java,modern_bedrock
from tests.payload_fixture import gallery


def capture(widget,name):
    widget.update();subprocess.run(['import','-window',str(widget.winfo_id()),str(ROOT/'artifacts'/name)],check=True)


with tempfile.TemporaryDirectory(prefix='facetedit-payload-review-') as temporary:
    path=Path(temporary);source=plain_java(path/'java');gallery(source)
    source.selection=Selection((0,15,0),(17,21,7));source.copy()
    target=open_world(modern_bedrock(path/'bedrock'))
    app=FacetEditApp(path/'settings.json');app.update();app._attach(source)
    app.translate_clipboard_dialog();app.update();window=next(w for w in app.winfo_children() if isinstance(w,tk.Toplevel))
    controls=window.conversion_controls;controls['target'].set('Bedrock 1.21.50');controls['preview']()
    deadline=time.monotonic()+30
    while app.busy and time.monotonic()<deadline:app.update();time.sleep(.005)
    assert controls['prepared'][0] is not None,controls['report'].get('1.0','end')
    capture(window,'payload-conversion.png');window.destroy()
    plan=prepare_conversion(source,target)
    try:
        assert plan.report.ok,plan.report.summary();converted=publish_conversion(plan,path/'converted')
    finally:plan.close()
    app._attach(Document(open_world(converted)));app.document.selection=Selection((2,16,2),(2,16,2));app.refresh()
    app.nbt_dialog();app.update();window=next(w for w in app.winfo_children() if isinstance(w,tk.Toplevel))
    def text_widgets(parent):
        for child in parent.winfo_children():
            if isinstance(child,tk.Text):yield child
            yield from text_widgets(child)
    editor=next(text_widgets(window));editor.yview(editor.search('"Items"','1.0'))
    capture(window,'payload-inspector.png');window.destroy();app.destroy()
