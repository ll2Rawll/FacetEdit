from pathlib import Path
import tempfile
import unittest

from facetedit.camera import Camera
from facetedit.discovery import discover_worlds,standard_paths
from facetedit.navigation import DEFAULT_BINDINGS,validate_navigation
from facetedit.settings import Settings
from tests.fixtures import java_world,bedrock_world


class DiscoveryTests(unittest.TestCase):
    def test_roots_java_bedrock_recent_deduplication_and_corrupt_metadata(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);java=java_world(root/'java');bedrock=bedrock_world(root/'bedrock')
            (root/'broken').mkdir();(root/'broken/level.dat').write_bytes(b'invalid')
            worlds,errors=discover_worlds([root],[str(java)])
            self.assertEqual(len(worlds),2);self.assertEqual({w.edition for w in worlds},{'Java','Bedrock'})
            self.assertEqual(next(w.version for w in worlds if w.edition=='Java'),'1.21.4')
            self.assertEqual(len(errors),1)
            # No database is opened merely to discover a Bedrock world.
            (bedrock/'db/CURRENT').write_text('malformed')
            self.assertEqual(len(discover_worlds([root])[0]),2)

    def test_platform_paths_do_not_require_running_on_that_platform(self):
        root=Path('/example')
        self.assertIn(root/'.minecraft/saves',standard_paths(root,'linux',{}))
        self.assertIn(root/'Library/Application Support/minecraft/saves',standard_paths(root,'darwin',{}))
        paths=standard_paths(root,'win32',{'APPDATA':'/roaming','LOCALAPPDATA':'/local'})
        self.assertIn(Path('/roaming/.minecraft/saves'),paths)
        self.assertTrue(any('MinecraftUWP' in str(p) for p in paths))

    def test_cancel_and_symlinks(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);java_world(root/'source');(root/'linked').symlink_to(root/'source',target_is_directory=True)
            worlds,_=discover_worlds([root]);self.assertEqual(len(worlds),1)
            with self.assertRaises(InterruptedError):discover_worlds([root],cancelled=lambda:True)


class NavigationTests(unittest.TestCase):
    def test_validation_nan_conflicts_and_settings_roundtrip(self):
        for values in ({'fov':float('nan')},{'speed':0},{'sensitivity':10},{'boost':True},{'bindings':{**DEFAULT_BINDINGS,'forward':'s'}}):
            with self.assertRaises(ValueError):validate_navigation(values)
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'settings.json';settings=Settings(path)
            settings.data['navigation']=validate_navigation({'fov':90,'speed':16,'invert_y':True,'bindings':{**DEFAULT_BINDINGS,'forward':'i'}})
            settings.data['world_roots']=['/worlds'];settings.save();loaded=Settings(path)
            self.assertEqual(loaded.data['navigation'],settings.data['navigation'])
            self.assertEqual(loaded.data['world_roots'],['/worlds'])

    def test_camera_sensitivity_inversion_and_boost(self):
        a=Camera(pitch=0,sensitivity=2,invert_y=True,boost_factor=8,speed=10)
        a.look(10,10);self.assertAlmostEqual(a.yaw,.12);self.assertAlmostEqual(a.pitch,.12)
        a=Camera(position=[0,0,0],pitch=0,boost_factor=8,speed=10)
        a.move(1,0,0,.1,True);self.assertAlmostEqual(a.position[2],-8)
