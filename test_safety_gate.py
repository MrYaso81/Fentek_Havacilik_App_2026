import unittest
from types import SimpleNamespace
from safety_gate import SafetyGate

class SafetyTests(unittest.TestCase):
    def state(self):return SimpleNamespace(heartbeat_time=10,fix_time=10,fix=3,position=(1,2),armed=False,battery=80)
    def test_healthy_telemetry(self):self.assertTrue(SafetyGate(self.state()).allow('telemetry',11))
    def test_stale_heartbeat_blocks_arm(self):
        s=self.state();s.heartbeat_time=1;self.assertFalse(SafetyGate(s).allow('arm',11))
    def test_bad_gps_blocks_arm(self):
        s=self.state();s.fix=2;self.assertFalse(SafetyGate(s).allow('arm',11))
    def test_low_battery_blocks_arm(self):
        s=self.state();s.battery=10;self.assertFalse(SafetyGate(s).allow('arm',11))

    def test_card_warnings_wait_until_cube_link_is_verified(self):
        s=self.state();s.heartbeat_time=0;s.autopilot=None;s.alerts=[]
        row=next(item for item in SafetyGate(s).checklist(11) if item[0]=='Kart uyarıları')
        self.assertFalse(row[1]);self.assertIn('bekleniyor',row[2])
    def test_auto_requires_armed(self):self.assertFalse(SafetyGate(self.state()).allow('auto',11))
    def test_mission_requires_armed_and_position(self):
        s=self.state();s.armed=True;s.position=None;self.assertFalse(SafetyGate(s).allow('mission',11))
    def test_already_armed_blocks_arm(self):
        s=self.state();s.armed=True;self.assertFalse(SafetyGate(s).allow('arm',11))
    def test_position_modes_use_navigation_gate(self):
        for mode in ('LOITER','BRAKE','CIRCLE','RTL','TAKEOFF'):
            self.assertNotEqual(SafetyGate.action_for_mode(mode),'basic_mode')

if __name__=='__main__':unittest.main()
