import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent / 'vendor'))
import queue
import threading
import unittest
from types import SimpleNamespace
from unittest.mock import patch
from connection import endpoint, Session
from app import gps_values
from pymavlink import mavutil


def heartbeat(armed=False):
    msg = mavutil.mavlink.MAVLink_heartbeat_message(1, 3, 128 if armed else 0, 0, 3, 3)
    msg._header.srcSystem, msg._header.srcComponent = 1, 1
    return msg


class Wire:
    def __init__(self, stop, armed=False, follow=None):
        self.stop, self.follow = stop, follow
        self.hb = heartbeat(armed)
        self.mav = self
        self.sent = []
        self.manual = []
        self.reads = 0
    def heartbeat_send(self, *args): pass
    def request_data_stream_send(self, *args): self.stream = args
    def command_long_send(self, *args): self.sent.append(args)
    def manual_control_send(self,*args):self.manual.append(args)
    def mission_set_current_send(self,*args):self.current=args
    def close(self): self.closed = True
    def recv_match(self, **kwargs):
        self.reads += 1
        if self.reads == 1:
            return self.hb
        if self.follow:
            return self.follow(self)
        self.stop.set()
        return None


class Tests(unittest.TestCase):
    def test_addresses(self):
        self.assertEqual(endpoint('Seri / USB', 'com8', 57600), 'COM8')
        self.assertEqual(endpoint('UDP dinle', '0.0.0.0:14550', 1), 'udpin:0.0.0.0:14550')
        self.assertEqual(endpoint('UDP gönder', '192.168.1.2:14551', 1), 'udpout:192.168.1.2:14551')
        self.assertEqual(endpoint('TCP', 'localhost:5760', 1), 'tcp:localhost:5760')
        for kind, addr in [('TCP', 'host:0'), ('TCP', 'host:65536'), ('UDP dinle', 'bad'), ('Seri / USB', 'COMx')]:
            with self.assertRaises(ValueError): endpoint(kind, addr, 115200)

    def test_gps(self):
        m = SimpleNamespace(lat=-330000000, lon=290000000, fix_type=3, satellites_visible=12, alt=-1200, vel=1000)
        valid, lat, lon, values = gps_values(m)
        self.assertTrue(valid)
        self.assertEqual((lat, lon), (-33, 29))
        self.assertEqual(values['Hız'], '36.0 km/sa')
        self.assertEqual(values['GPS irtifası'], '-1.2 m')
        m.fix_type = 2
        self.assertFalse(gps_values(m)[0])
        m.fix_type, m.vel, m.satellites_visible = 3, 65535, 255
        self.assertEqual(gps_values(m)[3]['Hız'], '—')
        self.assertEqual(gps_values(m)[3]['Uydu'], 'Bilinmiyor')

    def execute(self, action, armed=False, setup=True):
        events, stop = queue.Queue(), threading.Event()
        session = Session(events, stop, 'COM5', 115200, calibration=setup)
        session.commands.put(action)
        wire = Wire(stop, armed)
        session.listen(wire, mavutil)
        return wire, events

    def test_accel_command(self):
        wire, _ = self.execute('accel')
        self.assertEqual(wire.sent[0], (1, 1, 241, 0, 0, 0, 0, 0, 1, 0, 0))

    def test_extended_ground_calibration_commands(self):
        positions={'compass':1,'rc':3,'airspeed':5,'esc':6}
        for action,index in positions.items():
            wire,_=self.execute(action)
            self.assertEqual(wire.sent[0][2],241)
            self.assertEqual(wire.sent[0][4+index],1)

    def test_guarded_motor_and_servo_outputs(self):
        wire,_=self.execute(('motor_test',2,15,2))
        self.assertEqual(wire.sent[0][2],getattr(mavutil.mavlink,'MAV_CMD_DO_MOTOR_TEST',209))
        self.assertEqual(wire.sent[0][4:8],(2,0,15.0,2.0))
        wire,_=self.execute(('servo_test',3,1600,1,1500))
        self.assertEqual(wire.sent[0][2],getattr(mavutil.mavlink,'MAV_CMD_DO_SET_SERVO',183))
        self.assertEqual(wire.sent[0][4:6],(3,1600))

    def test_ground_outputs_blocked_outside_usb_setup(self):
        self.assertEqual(self.execute(('motor_test',1,10,1),setup=False)[0].sent,[])
        self.assertEqual(self.execute(('servo_test',1,1500,1,1500),armed=True)[0].sent,[])

    def test_gimbal_command_range(self):
        wire,_=self.execute(('gimbal',-30,45),setup=False)
        self.assertEqual(wire.sent[0][2],getattr(mavutil.mavlink,'MAV_CMD_DO_MOUNT_CONTROL',205))
        self.assertEqual(wire.sent[0][4:7],(-30.0,0,45.0))

    def test_camera_trigger_command(self):
        wire,_=self.execute(('camera_trigger',),setup=False)
        self.assertEqual(wire.sent[0][2],getattr(mavutil.mavlink,'MAV_CMD_IMAGE_START_CAPTURE',2000))
        self.assertEqual(wire.sent[0][6],1)

    def test_pause_and_manual_control(self):
        wire,_=self.execute(('mission','pause'),armed=True,setup=False)
        self.assertEqual(wire.sent[0][2],getattr(mavutil.mavlink,'MAV_CMD_DO_PAUSE_CONTINUE',193))
        with patch('connection.SafetyGate.allow',return_value=True):wire,_=self.execute(('mission','resume'),armed=True,setup=False)
        self.assertEqual(wire.sent[0][4],1)
        wire,_=self.execute(('manual_control',250,0,32767,-150),armed=True,setup=False)
        self.assertEqual(wire.manual[0],(1,250,0,32767,-150,0))

    def test_select_mission_step(self):
        with patch('connection.SafetyGate.allow',return_value=True):wire,_=self.execute(('mission','jump',7),armed=True,setup=False)
        self.assertEqual(wire.current,(1,1,7))

    def test_armed_and_telemetry_block_calibration(self):
        self.assertEqual(self.execute('accel', armed=True)[0].sent, [])
        self.assertEqual(self.execute('accel', setup=False)[0].sent, [])

    def test_position_requires_request(self):
        self.assertEqual(self.execute('position')[0].sent, [])

    def test_calibration_exchange(self):
        events, stop = queue.Queue(), threading.Event()
        session = Session(events, stop, 'COM5', 115200, calibration=True)
        session.commands.put('accel')
        def follow(wire):
            if wire.reads == 2:
                session.commands.put('position')
                msg = mavutil.mavlink.MAVLink_command_long_message(255, 190, 42429, 0, 2, 0, 0, 0, 0, 0, 0)
                msg._header.srcSystem, msg._header.srcComponent = 1, 1
                return msg
            stop.set()
        wire = Wire(stop, follow=follow)
        session.listen(wire, mavutil)
        self.assertEqual(wire.sent[1][2], 42429)
        self.assertEqual(wire.sent[1][4], 2)

    def test_disconnect_closes_and_drops_commands(self):
        events, stop = queue.Queue(), threading.Event()
        wire = Wire(stop)
        session = Session(events, stop, 'COM5', 115200, reconnect=False, factory=lambda *a, **kw: wire)
        def broken(*args):
            session.commands.put('accel')
            raise OSError('unplugged')
        session.listen = broken
        session.run()
        self.assertTrue(wire.closed)
        self.assertTrue(session.commands.empty())
        kinds = [item[0] for item in list(events.queue)]
        self.assertIn('lost', kinds)
        self.assertEqual(kinds[-1], 'done')

    def test_reconnect(self):
        events, stop = queue.Queue(), threading.Event()
        class NoWait:
            def is_set(self): return stop.is_set()
            def wait(self, delay): return False
        calls = []
        def factory(*args, **kwargs):
            calls.append(1)
            if len(calls) == 1: raise OSError('offline')
            return Wire(stop)
        session = Session(events, NoWait(), 'COM5', 115200, factory=factory)
        session.run()
        self.assertEqual(len(calls), 2)
        self.assertTrue(any(k == 'online' for k, _ in list(events.queue)))


if __name__ == '__main__':
    unittest.main()
