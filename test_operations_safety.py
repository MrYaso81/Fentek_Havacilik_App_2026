import unittest
import queue
import threading
from types import SimpleNamespace
from parameter_store import checked_value,validate_safety_parameter
from live_position import PositionState
from safety_gate import SafetyGate
from connection import Session

class OperationsSafetyTests(unittest.TestCase):
    def healthy(self):
        return SimpleNamespace(heartbeat_time=10,fix_time=10,fix=3,position=(1,2),position_time=10,
                               armed=False,battery=80,system_time=10,sensor_faults=0,ekf_time=10,ekf_flags=63,
                               autopilot=3,system_status=4,home=(1,2,3),alerts=[],fence_breach=False,fence_time=10)
    def test_unknown_sensor_blocks(self):
        s=self.healthy();s.sensor_faults=None;self.assertFalse(SafetyGate(s).allow('arm',11))
    def test_healthy_checks_do_not_claim_flight_certification(self):
        s=self.healthy();self.assertTrue(SafetyGate(s).allow('arm',11));self.assertIn('Son karar ArduPilot kartının',SafetyGate(s).summary(11))
    def test_stale_position_blocks_auto(self):
        s=self.healthy();s.armed=True;s.position_time=2;self.assertFalse(SafetyGate(s).allow('auto',11))
    def test_ekf_uninitialized_blocks(self):
        s=self.healthy();s.ekf_flags=1025;self.assertFalse(SafetyGate(s).allow('arm',11))
    def test_unsafe_parameter_numbers(self):
        for v,t in [(float('nan'),9),(float('inf'),9),(1.5,6),(256,1),(16777217,6)]:
            with self.assertRaises(ValueError):checked_value(v,t)
    def test_valid_parameter(self):self.assertEqual(checked_value(5000,6),5000)
    def test_prearm_bypass_parameters_are_blocked(self):
        with self.assertRaises(ValueError):validate_safety_parameter('ARMING_CHECK',0)
        with self.assertRaises(ValueError):validate_safety_parameter('ARMING_SKIPCHK',1)
        self.assertEqual(validate_safety_parameter('ARMING_CHECK',1),1)
    def test_critical_card_state_blocks_arm(self):
        s=self.healthy();s.system_status=6;self.assertFalse(SafetyGate(s).allow('arm',11))
    def test_recent_critical_alert_blocks_arm(self):
        s=self.healthy();s.alerts=[(10,2,'PreArm: sensor failure')];self.assertFalse(SafetyGate(s).allow('arm',11))
    def test_gps_unknown_accuracy_not_zero(self):
        s=PositionState();s.ingest(SimpleNamespace(get_type=lambda:'GPS_RAW_INT',fix_type=3,satellites_visible=10,eph=65535,epv=65535),10)
        self.assertNotIn('GPS HDOP',s.metrics)
    def parameter_exchange(self,armed=False,reply=5200):
        stop=threading.Event();events=queue.Queue();session=Session(events,stop,'COM1',115200)
        sent=[]
        def msg(kind,**data):return SimpleNamespace(get_type=lambda:kind,get_srcSystem=lambda:1,get_srcComponent=lambda:1,**data)
        heartbeat=msg('HEARTBEAT',base_mode=128 if armed else 0,autopilot=3,custom_mode=0)
        param=lambda value:msg('PARAM_VALUE',param_id='BATT_CAPACITY',param_value=value,param_type=6,param_index=0,param_count=1)
        packets=iter([heartbeat,param(5000),param(reply)])
        def receive(**kwargs):
            try:
                result=next(packets)
                if result.get_type()=='PARAM_VALUE' and result.param_value==5000:session.commands.put(('param_set','BATT_CAPACITY',5200))
                return result
            except StopIteration:stop.set();return None
        mav=SimpleNamespace(heartbeat_send=lambda *a:None,request_data_stream_send=lambda *a:None,param_set_send=lambda *a:sent.append(a))
        constants=SimpleNamespace(MAV_TYPE_GCS=6,MAV_AUTOPILOT_INVALID=8,MAV_DATA_STREAM_ALL=0)
        session.listen(SimpleNamespace(mav=mav,recv_match=receive),SimpleNamespace(mavlink=constants))
        return sent,[value for kind,value in list(events.queue) if kind=='param_result']
    def test_parameter_write_preserves_type_and_verifies(self):
        sent,results=self.parameter_exchange();self.assertEqual(sent[0][-1],6);self.assertTrue(results[0][1])
    def test_armed_parameter_write_never_sent(self):
        sent,results=self.parameter_exchange(armed=True);self.assertEqual(sent,[]);self.assertFalse(results[0][1])
    def test_parameter_mismatch_is_failure(self):
        sent,results=self.parameter_exchange(reply=5100);self.assertFalse(results[0][1])

if __name__=='__main__':unittest.main()
