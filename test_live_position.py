import unittest
from types import SimpleNamespace
from live_position import PositionState

def msg(kind,**kw):return SimpleNamespace(get_type=lambda:kind,**kw)

class PositionTests(unittest.TestCase):
    def prepare(self):
        state=PositionState()
        state.ingest(msg('HEARTBEAT',base_mode=128,custom_mode=3),10)
        state.ingest(msg('GPS_RAW_INT',fix_type=3,satellites_visible=18),10)
        return state
    def global_msg(self,lat=410123456):
        return msg('GLOBAL_POSITION_INT',lat=lat,lon=290987654,alt=152350,relative_alt=42350,vx=300,vy=400,hdg=12345)
    def test_coordinate_units(self):
        s=self.prepare();s.ingest(self.global_msg(),10)
        self.assertAlmostEqual(s.position['lat'],41.0123456)
        self.assertAlmostEqual(s.position['lon'],29.0987654)
        self.assertEqual(s.position['altitude'],42.35)
        self.assertEqual(s.position['amsl'],152.35)
        self.assertEqual(s.position['speed'],5)
        self.assertEqual(s.position['heading'],123.45)
        self.assertTrue(s.fresh(11))
    def test_ned_keeps_axes_and_sign(self):
        s=self.prepare();s.ingest(msg('LOCAL_POSITION_NED',x=12.5,y=-8,z=-40),10)
        self.assertEqual(s.ned,(12.5,-8,-40))
    def test_no_fix_and_stale_fix(self):
        s=PositionState();s.ingest(self.global_msg(),10);self.assertIsNone(s.position)
        s=self.prepare();s.ingest(self.global_msg(),14);self.assertIsNone(s.position)
    def test_position_expiry_not_masked_by_heartbeat(self):
        s=self.prepare();s.ingest(self.global_msg(),10)
        s.ingest(msg('HEARTBEAT',base_mode=0,custom_mode=0),14)
        self.assertFalse(s.fresh(14));self.assertIsNotNone(s.position)
    def test_new_position_updates(self):
        s=self.prepare();s.ingest(self.global_msg(),10);s.ingest(self.global_msg(410223456),11)
        self.assertAlmostEqual(s.position['lat'],41.0223456)
    def test_unknown_heading(self):
        s=self.prepare();m=self.global_msg();m.hdg=65535;s.ingest(m,10)
        self.assertIsNone(s.position['heading'])

if __name__=='__main__':unittest.main()
