import unittest
from types import SimpleNamespace
from hardware_acceptance import evaluate_acceptance,acceptance_result


def state(**changes):
    values=dict(heartbeat_time=100,autopilot=3,armed=False,system_status=4,system_time=100,
                sensor_faults=0,fix=3,fix_time=100,satellites=15,position={'lat':41,'lon':29},position_time=100,
                ekf_flags=55,ekf_time=100,battery=75,battery_voltage=15.8,home=(41,29,100),
                radio={'rssi':180,'remrssi':170,'noise':110,'remnoise':105},radio_time=100)
    values.update(changes);return SimpleNamespace(**values)


class AcceptanceTests(unittest.TestCase):
    def params(self):return {'ARMING_CHECK':(1,9),'BATT_MONITOR':(4,9),'FS_GCS_ENABLE':(1,9)}
    def test_usb_phase_passes_with_core_data(self):
        rows=evaluate_acceptance(state(radio={},radio_time=0,battery=None),101,'USB yer testi',self.params(),('STABILIZE',))
        self.assertEqual(acceptance_result(rows),'UYGUN')
    def test_telemetry_requires_radio_battery_home_and_modes(self):
        rows=evaluate_acceptance(state(),101,'Kablosuz telemetri / uçuş öncesi',self.params(),('STABILIZE','RTL'))
        self.assertEqual(acceptance_result(rows),'UYGUN')
        rows=evaluate_acceptance(state(radio={},radio_time=0),101,'Kablosuz telemetri / uçuş öncesi',self.params(),('STABILIZE','RTL'))
        self.assertEqual(acceptance_result(rows),'BEKLİYOR')
    def test_armed_or_bad_sensor_fails(self):
        rows=evaluate_acceptance(state(armed=True,sensor_faults=4),101,'USB yer testi',self.params())
        self.assertEqual(acceptance_result(rows),'BAŞARISIZ')
    def test_stale_data_never_passes(self):
        rows=evaluate_acceptance(state(),110,'USB yer testi',self.params())
        self.assertEqual(acceptance_result(rows),'BAŞARISIZ')


if __name__=='__main__':unittest.main()
