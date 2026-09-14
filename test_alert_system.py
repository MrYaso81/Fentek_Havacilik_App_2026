import unittest
from types import SimpleNamespace
from alert_system import evaluate_alerts,play_alarm_pattern


def state(**values):
    defaults=dict(heartbeat_time=100,fix=3,fix_time=100,armed=False,battery=80,fence_breach=False,fence_time=0,
                  radio={},radio_time=0,packet_received=0,packet_lost=0,alerts=[])
    defaults.update(values);return SimpleNamespace(**defaults)


class AlertTests(unittest.TestCase):
    def test_classic_alarm_is_three_short_beeps(self):
        tones=[];pauses=[]
        play_alarm_pattern('warning',lambda frequency,duration:tones.append((frequency,duration)),pauses.append)
        self.assertEqual(len(tones),3)
        self.assertEqual(len(pauses),2)
        self.assertTrue(all(duration<=220 for _,duration in tones))

    def test_healthy(self):
        self.assertEqual(evaluate_alerts(state(),101,True,90),[])

    def test_battery_levels(self):
        self.assertEqual(evaluate_alerts(state(battery=20),101)[0][1],'warning')
        self.assertEqual(evaluate_alerts(state(battery=10),101)[0][1],'critical')

    def test_gps_and_link_loss(self):
        keys={a[0] for a in evaluate_alerts(state(heartbeat_time=90,fix_time=90),101,True,80)}
        self.assertIn('telemetry',keys)
        keys={a[0] for a in evaluate_alerts(state(fix=2),101,True,80)}
        self.assertIn('gps',keys)

    def test_fence_and_radio(self):
        s=state(fence_breach=True,fence_time=100,radio={'rssi':80,'noise':70,'remrssi':75,'remnoise':70},radio_time=100)
        keys={a[0] for a in evaluate_alerts(s,101,True,80)}
        self.assertEqual(keys,{'fence','radio'})


if __name__=='__main__':unittest.main()
