import math
import random
import unittest

from facetedit.camera import Camera,dot


class CameraMathTests(unittest.TestCase):
    def test_basis_is_orthonormal_at_arbitrary_orientation(self):
        rng=random.Random(19)
        for _ in range(100):
            basis=Camera(yaw=rng.uniform(-6,6),pitch=rng.uniform(-1.5,1.5)).basis()
            for i,a in enumerate(basis):
                for j,b in enumerate(basis):self.assertAlmostEqual(dot(a,b),int(i==j))

    def test_forward_right_and_up_directions(self):
        camera=Camera(position=[0.,0.,0.],pitch=0,speed=10)
        camera.move(1,0,0,.1);self.assertEqual(camera.position,[0.,0.,-1.])
        camera.move(0,1,0,.1);self.assertEqual(camera.position,[1.,0.,-1.])
        camera.move(0,0,1,.1);self.assertEqual(camera.position,[1.,1.,-1.])
        camera.yaw=math.pi/2;camera.move(1,0,0,.1);self.assertAlmostEqual(camera.position[0],2)

    def test_diagonal_speed_boost_and_time_clamp(self):
        for direction in ((1,0,0),(1,1,0),(1,1,1)):
            camera=Camera(position=[0.,0.,0.],pitch=0,speed=10)
            camera.move(*direction,1,boost=True)
            self.assertAlmostEqual(math.sqrt(dot(camera.position,camera.position)),4)

    def test_world_bounds_and_pitch_clamp(self):
        camera=Camera(position=[30_000_000.,575.,-30_000_000.],pitch=0)
        camera.move(1,1,1,.1,bounds=(-64,319));self.assertEqual(camera.position,[30_000_000.,575.,-30_000_000.])
        camera.look(100000,100000)
        self.assertTrue(0<=camera.yaw<math.tau);self.assertGreater(camera.pitch,-math.pi/2)
        self.assertFalse(camera.move(0,0,0,.1))

    def test_projection_known_points(self):
        frame=Camera(position=[0.,0.,0.],pitch=0,fov=90).frame(800,600)
        self.assertEqual(frame.project(frame.view((0,0,-3))),(400,300))
        self.assertAlmostEqual(frame.project(frame.view((3,0,-3)))[0],700)
        self.assertAlmostEqual(frame.project(frame.view((0,3,-3)))[1],0)

    def test_behind_camera_faces_and_segments_are_rejected(self):
        frame=Camera(position=[0.,0.,0.],pitch=0).frame(800,600)
        self.assertEqual(frame.polygon(((-1,0,1),(1,0,1),(1,1,2),(-1,1,2))),[])
        self.assertIsNone(frame.segment((-1,0,1),(1,1,3)))

    def test_crossing_near_plane_clips_finite_polygon(self):
        frame=Camera(position=[0.,0.,0.],pitch=0).frame(800,600)
        points=frame.polygon(((-1,-1,1),(1,-1,-2),(1,1,-2),(-1,1,1)))
        self.assertGreaterEqual(len(points),6)
        for x,y in zip(points[::2],points[1::2]):
            self.assertTrue(math.isfinite(x) and -1e-8<=x<=800+1e-8)
            self.assertTrue(math.isfinite(y) and -1e-8<=y<=600+1e-8)

    def test_segment_clip_intersects_viewport_edges(self):
        frame=Camera(position=[0.,0.,0.],pitch=0,fov=90).frame(800,600)
        segment=frame.segment((-100,0,-1),(100,0,-1))
        for actual,expected in zip(segment,(0,300,800,300)):self.assertAlmostEqual(actual,expected)
        self.assertIsNone(frame.segment((100,0,-1),(200,0,-1)))

    def test_camera_inside_block_culls_outward_faces(self):
        frame=Camera(position=[.5,.5,.5],pitch=0).frame(800,600)
        for normal in ((1,0,0),(-1,0,0),(0,1,0),(0,-1,0),(0,0,1),(0,0,-1)):
            self.assertFalse(frame.visible((0,0,0),normal))

    def test_random_near_plane_clipping_never_explodes(self):
        rng=random.Random(4)
        for _ in range(400):
            camera=Camera(position=[rng.uniform(-2,2) for _ in range(3)],yaw=rng.uniform(-3,3),pitch=rng.uniform(-1.5,1.5))
            frame=camera.frame(1000,700,(350,350))
            points=frame.polygon(((0,0,0),(1,0,0),(1,1,0),(0,1,0)))
            for x,y in zip(points[::2],points[1::2]):
                self.assertTrue(-1e-7<=x<=1000+1e-7 and -1e-7<=y<=700+1e-7)
