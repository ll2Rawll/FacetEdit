"""Exercise the actual Tk model viewport with local assets; capture and profile."""
import argparse,json,platform,statistics,subprocess,sys,tempfile,time
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'src'))
from facetedit.ui import FacetEditApp
from facetedit.model import Document,Selection
from facetedit.world import SampleWorld
from facetedit.blocks import Block,AIR


class Gallery(SampleWorld):
    name='The material garden';spawn=(0,4,0)
    def __init__(self):
        super().__init__();self.name='The material garden';self.spawn=(0,4,0)
        self.blocks={(x,0,z):Block('smooth_stone') for x in range(-9,10) for z in range(-9,10)}
        def put(x,y,z,name):self.blocks[x,y,z]=Block.parse(name)
        for x in range(-6,0):
            for z in range(-5,1):put(x,0,z,'oak_planks')
        for x in range(2,7):
            for z in range(-5,0):put(x,0,z,'water[level=0]');put(x,-1,z,'sand')
        for x in range(2,7):put(x,1,-6,'glass')
        for x in range(-6,0):put(x,1,-2,'oak_stairs[facing=north,half=bottom,shape=straight,waterlogged=false]')
        for x in range(-5,-1):put(x,1,-4,'oak_fence[east=true,west=true,north=false,south=false,waterlogged=false]')
        for x in range(-7,8):
            put(x,0,4,'grass_block[snowy=false]')
            if x%2:put(x,1,4,'poppy')
        for x in (-5,0,5):
            for y in range(1,4):put(x,y,7,'oak_log[axis=y]')
            for a in range(x-1,x+2):
                for b in range(6,9):put(a,4,b,'oak_leaves[distance=1,persistent=true,waterlogged=false]')
        for x in range(-6,0):put(x,1,1,'stone_slab[type=bottom,waterlogged=false]')
        put(2,1,1,'heavy_core');put(4,1,1,'spawner')
        for half,y in (('lower',1),('upper',2)):put(-7,y,-4,'oak_door[facing=east,half='+half+',hinge=left,open=false,powered=false]')
        for x in range(1,7):put(x,1,3,'redstone_wire[east=side,west=side,north=none,south=none,power=15]')
    def get_block(self,x,y,z,dimension='overworld'):return self.blocks.get((x,y,z),AIR)


def capture(widget,name):
    widget.update();subprocess.run(['import','-window',str(widget.winfo_id()),str(ROOT/'artifacts'/name)],check=True)


parser=argparse.ArgumentParser();parser.add_argument('pack');parser.add_argument('--no-crop',action='store_true');args=parser.parse_args()
if args.no_crop:
    from facetedit.frames import FrameStream
    FrameStream._crop=staticmethod(lambda scene,view:((0,0),view))
with tempfile.TemporaryDirectory() as temporary:
    app=FacetEditApp(Path(temporary)/'settings.json');app.update();view=app.viewport;delays=[]
    def until(condition,timeout=40):
        deadline=time.monotonic()+timeout
        while time.monotonic()<deadline:
            start=time.perf_counter();app.update();delays.append((time.perf_counter()-start)*1000)
            if condition():return
            time.sleep(.002)
        raise RuntimeError('Render did not finish: '+str(view._frame_error))
    began=time.perf_counter();app.load_resources([args.pack]);until(lambda:view._display_frame is not None);view.draw();app.update()
    cold=(time.perf_counter()-began)*1000;capture(app,'textured-workspace.png')
    app._attach(Document(Gallery()));until(lambda:view._display_frame is not None);view.draw();capture(app,'model-gallery.png')
    report={'scope':'Linux/Xvfb, actual Tk viewport, local Java 1.21.4 assets. System Mesa software OpenGL on this host; no game/native Windows/macOS comparison. Screenshots depict the original editable gallery.',
            'python':sys.version.split()[0],'platform':platform.platform(),'backend':view._display_frame.backend,'window':'1440x900','radius':view.radius,'cold_sample_to_first_frame_ms':round(cold,3),'gallery_surfaces':len(view.scene.surfaces)}
    def profile(count=12):
        frames=[];latencies=[];tk_times=[]
        for _ in range(count):
            old=view._display_frame;start=time.perf_counter()
            if view.mode=='fly':view.camera.look(2.5,0)
            else:view.angle+=.02
            view.draw();tk_times.append(view.last_ms)
            until(lambda:view._display_frame is not old and view._frame_key==view._requested_frame)
            frames.append(view._display_frame.elapsed_ms);latencies.append((time.perf_counter()-start)*1000)
        frame=view._display_frame
        return {'iterations':count,'scene_surfaces':len(frame.scene.surfaces),'display_zoom':frame.zoom,'worker_frame_ms_median':round(statistics.median(frames),3),'worker_frame_ms_max':round(max(frames),3),'input_to_display_ms_median':round(statistics.median(latencies),3),'tk_draw_ms_median':round(statistics.median(tk_times),3)}
    report['orbit']=profile()
    app.document.selection=Selection((-6,0,-5),(-1,1,0));app.document.copy();view.preview=(app.document.clipboard,(0,2,0));view.draw();capture(app,'textured-selection.png');view.preview=None
    app.toggle_camera();view.camera.position=[12.,11.,14.];view.camera.yaw=-.65;view.camera.pitch=-.5;view.draw()
    until(lambda:view._display_frame is not None and view._display_frame.view.perspective and view._geometry_key==view._requested_geometry)
    view.draw();capture(app,'textured-flight.png');report['flight']=profile()
    app.resources_dialog();app.update();capture(app.resource_list.winfo_toplevel(),'resource-studio.png');app.resource_list.winfo_toplevel().destroy()
    app.geometry('1040x700');until(lambda:view._display_frame.view.width==view.winfo_width());view.draw();capture(app,'textured-compact.png')
    report['tk_update_ms_max']=round(max(delays),3)
    app.geometry('1440x900');app.toggle_camera();view.go_to(0,95,0);view.reset();app.document.selection=None;app.refresh()
    view.set_resources(view.resources,'software');until(lambda:view._display_frame is not None);view.draw();capture(app,'textured-software.png');report['portable_software']=profile(3)
    report['resource_diagnostics']=dict(view.resources.warnings)
    report['empty_border_cropping']=not args.no_crop
    app.destroy();(ROOT/'artifacts'/('textured-before-cropping.json' if args.no_crop else 'textured-benchmark.json')).write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))
