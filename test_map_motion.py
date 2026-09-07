import queue
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch
from types import SimpleNamespace
from atlas import Atlas


class MapLoadingTest(unittest.TestCase):
    def test_cached_tiles_precede_network(self):
        with tempfile.TemporaryDirectory() as directory:
            cache=Path(directory)/'map_cache'
            cache.mkdir()
            (cache/'osm_1_0_0.png').write_bytes(b'\x89PNGcached')
            events=queue.Queue()
            app=SimpleNamespace(map_tile_source='osm',tile_loading=False,
                root=SimpleNamespace(update_idletasks=lambda:None),
                canvas=SimpleNamespace(winfo_width=lambda:300,winfo_height=lambda:200),
                view_zoom=1,view_center=[0,0],tiles={},tile_times={},tile_queue=events,
                map_status=SimpleNamespace(set=lambda _:None))
            observed=[]
            def network(*args,**kwargs):
                observed.append(not events.empty())
                raise OSError('offline')
            with patch('atlas.__file__',str(Path(directory)/'atlas.py')),patch('atlas.urlopen',network):
                Atlas.load_map(app)
                deadline=time.monotonic()+3
                messages=[]
                while time.monotonic()<deadline:
                    message=events.get(timeout=3)
                    messages.append(message)
                    if message[0] in ('done','error'):break
            self.assertEqual(messages[0][0],'tile')
            self.assertTrue(observed)
            self.assertEqual(messages[-1][0],'done')

    def test_view_change_cancels_queued_downloads(self):
        import threading
        app=SimpleNamespace(map_tile_source='esri',tile_loading=True,
                            tile_cancel=threading.Event())
        Atlas.load_map(app)
        self.assertTrue(app.tile_cancel.is_set())
        self.assertTrue(app.tile_reload_pending)


if __name__=='__main__':unittest.main()
