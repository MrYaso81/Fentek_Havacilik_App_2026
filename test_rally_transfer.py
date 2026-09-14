import threading
import unittest
from types import SimpleNamespace
from rally_transfer import RallyTransfer, validate_rally_points


def msg(kind, **fields):
    return SimpleNamespace(get_type=lambda: kind, get_srcSystem=lambda: 1, get_srcComponent=lambda: 1, **fields)


class Mav:
    def __init__(self): self.calls = []
    def __getattr__(self, name): return lambda *args: self.calls.append((name, args))


class RallyTests(unittest.TestCase):
    def test_validation(self):
        self.assertEqual(len(validate_rally_points([(41, 29, 50)])), 1)
        for points in ([], [(91, 29, 50)], [(41, 29, 0)]):
            with self.assertRaises(ValueError): validate_rally_points(points)

    def test_upload_and_readback(self):
        messages = [msg('HEARTBEAT', autopilot=3, base_mode=0), msg('MISSION_REQUEST_INT', seq=0),
                    msg('MISSION_ACK', type=0), msg('MISSION_COUNT', count=1),
                    msg('MISSION_ITEM_INT', x=410000000, y=290000000, z=50)]
        mav = Mav()
        link = SimpleNamespace(mav=mav, mavlink20=lambda: True,
                               recv_match=lambda **kw: messages.pop(0) if messages else None)
        report = []
        RallyTransfer(link, 1, threading.Event(), report.append).run([(41, 29, 50)])
        self.assertTrue(report[-1].startswith('DOĞRULANDI'))
        self.assertTrue(any(name == 'mission_count_send' and args[-1] == 2 for name, args in mav.calls))


if __name__ == '__main__':
    unittest.main()
