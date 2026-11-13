import dataclasses,math,tempfile,threading,time,unittest
from pathlib import Path
from facetedit import png
from facetedit.blocks import Block
from facetedit.camera import Camera
from facetedit.resources import ResourceStack,Texture
from facetedit.scene import Scene,Surface,View,build_scene
from facetedit.software import Software
from facetedit.graphics import OpenGL,GraphicsUnavailable
from facetedit.frames import FrameStream
from facetedit.geometry import Superseded
from tests.resource_fixture import pack


def panel(texture,z=0,position=(0,0,0)):
    return Surface(position,((0,0,z),(1,0,z),(1,1,z),(0,1,z)),(0,0,-1),((0,1),(1,1),(1,0),(0,0)),texture)


def front_view(size=64):
    return View(size,size,(.5,.5,-2),(-1,0,0),(0,1,0),(0,0,1),size/2,size/2,size*.75,False)


class SceneTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        root,_=pack(Path(self.temp.name));self.resources=ResourceStack([root]);self.addCleanup(self.resources.close)

    def test_pick_through_texture_hole_and_slab_air(self):
        scene=Scene((panel(self.resources.texture('block/clear')),panel(self.resources.texture('block/checker'),1,(0,0,1))))
        self.assertEqual(scene.pick((.25,.5,-3),(0,0,1)),(0,0,1))
        self.assertEqual(scene.pick((.75,.5,-3),(0,0,1)),(0,0,0))
        slab=build_scene({(0,0,0):Block.parse('stone_slab[type=bottom]')},self.resources)
        self.assertIsNone(slab.pick((.5,.75,-3),(0,0,1)))
        self.assertEqual(slab.pick((.5,.25,-3),(0,0,1)),(0,0,0))

    def test_picking_overhang_backface_and_distance(self):
        face=panel(self.resources.texture('block/checker'),0,(5,0,0));scene=Scene((face,))
        self.assertEqual(scene.pick((.5,.5,-2),(0,0,1)),(5,0,0))
        self.assertIsNone(scene.pick((.5,.5,2),(0,0,-1)))
        self.assertIsNone(scene.pick((.5,.5,-2),(0,0,1),maximum=1))
        self.assertIsNone(scene.pick((.5,.5,-2),(0,0,0)))

    def test_orthographic_and_flight_rays_reach_projected_point(self):
        camera=Camera();camera.position=[3,4,5];camera.yaw=.7;camera.pitch=-.4
        for view in (front_view(),View.orbit(640,480,(4,3,7),.7,.6,20,(300,240)),View.flight(camera,640,480)):
            point=tuple(view.origin[i]+view.forward[i]*4+view.right[i]*.3+view.up[i]*.7 for i in range(3))
            x,y,_=view.project(point);origin,direction=view.ray(x,y)
            axis=max(range(3),key=lambda i:abs(direction[i]));t=(point[axis]-origin[axis])/direction[axis]
            for i in range(3):self.assertAlmostEqual(origin[i]+direction[i]*t,point[i])

    def test_cutout_depth_and_straight_alpha(self):
        front=panel(self.resources.texture('block/clear'));rear=panel(Texture((png.Image(1,1,bytes((255,0,0,255))),)),1)
        image=Software().render(Scene((rear,front)),front_view())
        self.assertEqual(image.pixel(44,32),(255,0,0,255));self.assertEqual(image.pixel(20,32),(30,220,230,255))
        translucent=panel(self.resources.texture('block/glass'))
        image=Software().render(Scene((translucent,)),front_view())
        self.assertEqual(image.pixel(32,32),(80,190,250,128))
        image=Software().render(Scene((translucent,rear)),front_view())
        self.assertEqual(image.pixel(32,32),(167,95,125,255))

    def test_near_plane_clipping_and_cancel(self):
        view=dataclasses.replace(front_view(),perspective=True,origin=(.5,.5,-.05))
        image=Software().render(Scene((panel(self.resources.texture('block/checker')),)),view)
        self.assertFalse(any(image.rgba))
        cancel=threading.Event();cancel.set()
        with self.assertRaises(Superseded):Software().render(Scene(()),view,cancel=cancel)


class NativeRenderingTests(unittest.TestCase):
    # These compare independent implementations at selected interior pixels;
    # drivers may apply different fixed-point rules at triangle boundaries.
    def setUp(self):
        SceneTests.setUp(self)
        try:self.gl=OpenGL()
        except (GraphicsUnavailable,OSError,AttributeError) as exc:self.skipTest(str(exc))
        self.addCleanup(self.gl.close)

    def test_native_texture_orientation_alpha_and_depth(self):
        for name in ('checker','glass','clear'):
            with self.subTest(texture=name):
                scene=Scene((panel(self.resources.texture('block/'+name)),));view=front_view()
                native=self.gl.render(scene,view);portable=Software().render(scene,view)
                for p in ((20,20),(44,20),(20,44),(44,44),(32,32)):
                    for a,b in zip(native.pixel(*p),portable.pixel(*p)):self.assertLessEqual(abs(a-b),1)

    def test_native_flight_rotation_and_large_coordinates(self):
        for base in ((0,0,0),(29_999_900,192,-29_999_900)):
            scene=build_scene({base:Block('stone')},self.resources)
            view=View(96,96,tuple(base[i]+v for i,v in enumerate((.5,.5,-2))),(-1,0,0),(0,1,0),(0,0,1),48,48,130,True)
            a=self.gl.render(scene,view);b=Software().render(scene,view)
            for p in ((30,30),(60,30),(30,60),(60,60)):
                for x,y in zip(a.pixel(*p),b.pixel(*p)):self.assertLessEqual(abs(x-y),1)
            self.assertTrue(any(a.rgba))

    def test_native_transparency_sort_and_repeat_resize(self):
        scene=Scene((panel(self.resources.texture('block/glass')),panel(self.resources.texture('block/checker'),1)))
        for size in (64,128,48,64):
            view=front_view(size);a=self.gl.render(scene,view);b=Software().render(scene,view)
            for x,y in zip(a.pixel(size//3,size//3),b.pixel(size//3,size//3)):self.assertLessEqual(abs(x-y),1)

    def test_native_context_rejects_wrong_thread(self):
        errors=[]
        def other():
            try:self.gl.render(Scene(()),front_view())
            except Exception as exc:errors.append(exc)
        thread=threading.Thread(target=other);thread.start();thread.join(2)
        self.assertIsInstance(errors[0],RuntimeError)

    def test_closing_one_context_keeps_other_owner_context_usable(self):
        ready=threading.Event();release=threading.Event();errors=[];images=[]
        scene=Scene((panel(self.resources.texture('block/checker')),))
        def other():
            renderer=None
            try:
                renderer=OpenGL();ready.set();release.wait(3);images.append(renderer.render(scene,front_view()))
            except Exception as exc:errors.append(exc);ready.set()
            finally:
                if renderer is not None:renderer.close()
        worker=threading.Thread(target=other);worker.start()
        try:
            self.assertTrue(ready.wait(3));self.gl.close();release.set();worker.join(3)
            self.assertFalse(worker.is_alive());self.assertFalse(errors);self.assertTrue(any(images[0].rgba))
        finally:release.set();worker.join(3)


class StreamTests(unittest.TestCase):
    def result(self,stream,timeout=5):
        deadline=time.monotonic()+timeout
        while time.monotonic()<deadline:
            value=stream.poll()
            if value is not None:return value
            time.sleep(.005)
        self.fail('Frame worker did not finish')

    def test_latest_frame_and_owner_thread_cleanup(self):
        started=threading.Event();release=threading.Event();owners=[]
        class Renderer:
            name='test'
            def __init__(self):owners.append(threading.get_ident())
            def render(self,scene,view,ticks,cancel):
                owners.append(threading.get_ident());started.set();release.wait(2)
                if cancel.is_set():raise Superseded()
                return png.Image(view.width,view.height,bytes(view.width*view.height*4))
            def close(self):owners.append(threading.get_ident())
        stream=FrameStream(factory=Renderer);self.addCleanup(stream.close)
        stream.request('old',Scene(()),front_view());self.assertTrue(started.wait(2))
        stream.request('middle',Scene(()),front_view());stream.request('latest',Scene(()),front_view());release.set()
        key,frame,error=self.result(stream);self.assertEqual(key,'latest');self.assertIsNone(error);self.assertEqual(frame.backend,'test')
        stream.close();stream.join(2);self.assertFalse(stream._thread.is_alive());self.assertEqual(len(set(owners)),1);self.assertNotEqual(owners[0],threading.get_ident())

    def test_native_failure_falls_back_to_software(self):
        class Broken:
            name='broken'
            def render(self,*args):raise GraphicsUnavailable('test native failure')
            def close(self):pass
        stream=FrameStream(factory=Broken);self.addCleanup(stream.close)
        stream.request(1,Scene(()),front_view());_,frame,error=self.result(stream)
        self.assertIsNone(error);self.assertIn('software',frame.backend);self.assertEqual(frame.fallback_reason,'test native failure')

    def test_software_frame_size_is_bounded(self):
        stream=FrameStream('software');self.addCleanup(stream.close)
        view=dataclasses.replace(front_view(),width=1401,height=899)
        stream.request(1,Scene(()),view);_,frame,error=self.result(stream)
        self.assertIsNone(error);image=png.decode(frame.data);self.assertLessEqual(image.width*image.height,Software.pixel_budget)
        self.assertEqual(frame.view,view);self.assertEqual(frame.offset,(0,0));self.assertEqual((image.width,image.height),(1,1))

    def test_crop_preserves_projection_and_avoids_empty_framebuffer_area(self):
        texture=Texture((png.Image(1,1,bytes((100,150,200,255))),));scene=Scene((panel(texture),));view=front_view(256)
        offset,cropped=FrameStream._crop(scene,view)
        self.assertLess(cropped.width*cropped.height,view.width*view.height)
        for vertex in scene.surfaces[0].vertices:
            full=view.project(vertex);local=cropped.project(vertex)
            self.assertAlmostEqual(full[0],local[0]+offset[0]);self.assertAlmostEqual(full[1],local[1]+offset[1])
        image=Software().render(scene,cropped);full=Software().render(scene,view)
        self.assertEqual(image.pixel(128-offset[0],128-offset[1]),full.pixel(128,128))
        near=dataclasses.replace(view,perspective=True,origin=(.5,.5,0))
        self.assertEqual(FrameStream._crop(scene,near),((0,0),near))

    def test_camera_updates_do_not_starve_active_software_frame(self):
        ready=threading.Event();release=threading.Event();ticks=[]
        class Renderer:
            name='test'
            def render(self,scene,view,tick,cancel):
                ticks.append(tick)
                if tick==1:
                    ready.set();release.wait(2)
                    if cancel.is_set():raise AssertionError('Camera movement cancelled an in-progress frame')
                return png.Image(view.width,view.height,bytes(view.width*view.height*4))
            def close(self):pass
        stream=FrameStream(factory=Renderer);self.addCleanup(stream.close);scene=Scene(())
        stream.request(1,scene,front_view(),1);self.assertTrue(ready.wait(2))
        stream.request(2,scene,front_view(),2);stream.request(3,scene,front_view(),3);release.set()
        deadline=time.monotonic()+3;last=None
        while time.monotonic()<deadline:
            result=stream.poll()
            if result is not None:last=result
            if last is not None and last[0]==3:break
            time.sleep(.002)
        self.assertEqual(ticks,[1,3]);self.assertIsNone(last[2])
