"""Real Tk screenshots of material, conversion, discovery and navigation flows."""
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import tkinter as tk

ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'src'));sys.path.insert(0,str(ROOT))
from facetedit.ui import FacetEditApp
from facetedit.model import Clipboard
from facetedit.blocks import Block
from tests.test_conversion import plain_java,modern_bedrock


def capture(widget,name):
    widget.update()
    subprocess.run(['import','-window',str(widget.winfo_id()),str(ROOT/'artifacts'/name)],check=True)


with tempfile.TemporaryDirectory() as temporary:
    root=Path(temporary);app=FacetEditApp(root/'settings.json');app.update()
    def wait():
        deadline=time.monotonic()+30
        while app.busy and time.monotonic()<deadline:app.update();time.sleep(.005)
        assert not app.busy
        app.update()
    def dialog():
        app.update();return next(w for w in app.winfo_children() if isinstance(w,tk.Toplevel))
    app.material_dialog();window=dialog();window.material_controls['search'].set('cut_copper_stairs');app.update()
    capture(window,'material-studio.png');capture(app,'material-workspace.png')
    window.geometry('680x520');window.material_controls['search'].set('cobblestone_wall');app.update()
    window.material_controls['state_canvas'].yview_moveto(1);app.update()
    capture(window,'material-states-compact.png');window.destroy()
    app.document.clipboard=Clipboard((3,1,1),{(0,0,0):Block.parse('oak_log[axis=x]'),(1,0,0):Block('gold_block'),(2,0,0):Block.parse('oak_stairs[facing=north,half=top,shape=straight,waterlogged=true]')})
    app.translate_clipboard_dialog();window=dialog();window.conversion_controls['target'].set('Bedrock 1.21.50');window.conversion_controls['preview']();wait()
    capture(window,'clipboard-translation.png');window.destroy()
    app.navigation_dialog();window=dialog();capture(window,'navigation-controls.png');window.destroy()
    source=plain_java(root/'saves/Java sculpture');target=modern_bedrock(root/'saves/Bedrock template')
    app.settings.data['world_roots']=[str(root/'saves')]
    app.world_library();window=dialog();wait();capture(window,'world-library.png');window.destroy()
    app._attach(source);app.convert_world_dialog();window=dialog();window.conversion_controls['template'].set(str(target))
    window.conversion_controls['preview']();wait();capture(window,'world-conversion.png')
    window.conversion_controls['plan'][0].close();window.destroy()
    app.destroy()
