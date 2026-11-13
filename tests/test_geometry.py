import threading,time,unittest,tempfile,os
from pathlib import Path
from unittest import mock
from facetedit.geometry import GeometryStream,build,Geometry,Superseded
from facetedit.model import Document,Selection
from facetedit.blocks import Block
from facetedit.world import SampleWorld,open_world
from tests.fixtures import java_world


class GeometryStreamTests(unittest.TestCase):
    def wait(self,stream,key):
        end=time.monotonic()+3
        while time.monotonic()<end:
            result=stream.poll()
            if result is not None and result[0]==key:return result
            time.sleep(.002)
        self.fail('Geometry did not arrive')

    def test_latest_request_cancels_stale_result_and_coalesces_pending_work(self):
        stream=GeometryStream();started=threading.Event();release=threading.Event();calls=[]
        def slow(cancel):started.set();release.wait(2);return 'stale'
        try:
            stream.request('old',slow);self.assertTrue(started.wait(1))
            stream.request('skipped',lambda cancel:calls.append('skipped'))
            stream.request('new',lambda cancel:'latest');release.set()
            self.assertEqual(self.wait(stream,'new'),('new','latest',None));self.assertFalse(calls);self.assertGreaterEqual(stream.cancelled,1)
        finally:release.set();stream.close()

    def test_cache_reuse_two_entry_bound_and_error_delivery(self):
        stream=GeometryStream()
        try:
            for key in ('one','two','three'):stream.request(key,lambda cancel,k=key:k);self.wait(stream,key)
            self.assertEqual(len(stream._cache),2)
            stream.request('two',lambda cancel:self.fail('A cached mesh rebuilt'))
            self.assertEqual(self.wait(stream,'two')[1],'two');self.assertEqual(stream.cache_hits,1)
            def fail(cancel):raise ValueError('invalid terrain')
            stream.request('bad',fail);self.assertIsInstance(self.wait(stream,'bad')[2],ValueError)
        finally:stream.close()

    def test_closed_stream_discards_late_result_and_stops_worker(self):
        stream=GeometryStream();started=threading.Event();release=threading.Event()
        def work(cancel):started.set();release.wait(2);return 'late'
        stream.request('old',work);self.assertTrue(started.wait(1));stream.close();release.set();stream._thread.join(2)
        self.assertFalse(stream._thread.is_alive());self.assertIsNone(stream.poll())

    def test_cancelled_geometry_does_not_scan_world(self):
        cancel=threading.Event();cancel.set();doc=Document(SampleWorld())
        with mock.patch.object(doc,'get',side_effect=AssertionError('read after cancellation')),self.assertRaises(Superseded):build(doc,'orbit',(0,0),12,95,cancel)

    def test_sparse_section_hint_retains_staged_blocks_above_terrain(self):
        with tempfile.TemporaryDirectory() as temporary:
            doc=Document(open_world(java_world(Path(temporary)/'world')));doc.apply('high',[((1,300,1),Block('gold_block'))])
            result=build(doc,'orbit',(1,1),2,319,threading.Event())
            self.assertIn((1,300,1),{face[0] for face in result.faces})
            self.assertIn((0,15,0),{face[0] for face in result.faces})


@unittest.skipUnless(os.environ.get('FACETEDIT_GUI_TESTS')=='1','Desktop test flag required')
class GeometryDesktopTests(unittest.TestCase):
    def test_disk_geometry_does_not_block_tk_and_stale_world_is_discarded(self):
        from facetedit.ui import FacetEditApp
        with tempfile.TemporaryDirectory() as temporary:
            path=Path(temporary);app=FacetEditApp(path/'settings.json');app.update();started=threading.Event();release=threading.Event()
            def slow(*args):started.set();release.wait(2);return Geometry([],700)
            try:
                with mock.patch('facetedit.geometry.build',side_effect=slow):
                    app._attach(Document(open_world(java_world(path/'world'))))
                    began=time.monotonic();app.viewport.draw();app.update()
                    self.assertLess(time.monotonic()-began,.25);self.assertTrue(started.wait(1))
                    ran=[];app.after(0,lambda:ran.append(True));app.update();self.assertEqual(ran,[True])
                app._attach(Document(SampleWorld()));app.viewport.draw();release.set()
                end=time.monotonic()+.1
                while time.monotonic()<end:app.update();time.sleep(.002)
                self.assertNotEqual(app.viewport.height_origin,700);self.assertGreater(app.viewport.face_count,500)
            finally:release.set();app.destroy()

    def test_disk_geometry_arrives_and_polling_stops(self):
        from facetedit.ui import FacetEditApp
        with tempfile.TemporaryDirectory() as temporary:
            path=Path(temporary);app=FacetEditApp(path/'settings.json');app.update()
            try:
                app._attach(Document(open_world(java_world(path/'world'))));app.viewport.radius=6;app.viewport.draw()
                end=time.monotonic()+3
                while app.viewport._geometry_key!=app.viewport._requested_geometry and time.monotonic()<end:app.update();time.sleep(.003)
                app.viewport.draw();self.assertGreater(app.viewport.face_count,0);self.assertIsNone(app.viewport._geometry_poll)
            finally:app.destroy()
