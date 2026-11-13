"""Measure queue latency and visible completion for real disk-backed geometry."""
import json,statistics,sys,tempfile,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'src'));sys.path.insert(0,str(ROOT))
from facetedit.ui import FacetEditApp
from facetedit.model import Document
from facetedit.world import open_world
from tests.fixtures import java_world

with tempfile.TemporaryDirectory() as temporary:
    path=Path(temporary);app=FacetEditApp(path/'settings.json');app.update()
    world=open_world(Path(sys.argv[1])) if len(sys.argv)>1 else open_world(java_world(path/'world'))
    app._attach(Document(world));view=app.viewport;view.radius=12
    queue_ms=[];ready_ms=[]
    try:
        for x,z in ((4,4),(12,4),(20,4),(12,4),(20,4),(12,4)):
            view.center_x,view.center_z=x,z
            start=time.perf_counter();view.draw();queue_ms.append((time.perf_counter()-start)*1000)
            deadline=time.monotonic()+20
            while view._geometry_key!=view._requested_geometry:
                if time.monotonic()>deadline:raise TimeoutError('Geometry did not complete')
                app.update();time.sleep(.002)
            app.update();ready_ms.append((time.perf_counter()-start)*1000)
        stream=view._geometry_stream
        result={'python':sys.version.split()[0],'world':world.name,'edition':world.edition,'radius':view.radius,
                'ui_enqueue_ms':queue_ms,'visible_completion_ms':ready_ms,
                'median_ui_enqueue_ms':statistics.median(queue_ms),'builds':stream.builds,'cache_hits':stream.cache_hits,
                'cached_meshes':len(stream._cache),'idle_poll_stopped':view._geometry_poll is None,
                'scope':'Linux Tk on this host. Disk-backed geometry, six camera requests; includes cached draws. No Amulet comparison or large-world throughput claim.'}
        print(json.dumps(result,indent=2))
    finally:app.destroy()
