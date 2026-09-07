"""Read-only Cube/ArduPilot telemetry contract tests; no physical ports used."""
import queue
import threading
import unittest
from types import SimpleNamespace

from connection import Session
from live_position import PositionState


def message(kind, **values):
    values.setdefault('get_srcSystem', lambda: 1)
    values.setdefault('get_srcComponent', lambda: 1)
    values.setdefault('get_type', lambda: kind)
    return SimpleNamespace(**values)


class Mav:
    def __init__(self): self.streams=[]; self.heartbeats=[]
    def request_data_stream_send(self, *args): self.streams.append(args)
    def heartbeat_send(self, *args): self.heartbeats.append(args)


class Wire:
    def __init__(self, messages):
        self.mav=Mav(); self.messages=iter(messages); self.closed=False
    def recv_match(self, **kwargs):
        try:return next(self.messages)
        except StopIteration:return None
    def close(self):self.closed=True


class CubeTelemetryContract(unittest.TestCase):
    def test_session_identifies_ardupilot_and_requests_telemetry(self):
        stop=threading.Event(); events=queue.Queue()
        hb=message('HEARTBEAT',autopilot=3,base_mode=0,custom_mode=0)
        gps=message('GPS_RAW_INT',fix_type=3,satellites_visible=17,lat=410000000,lon=290000000)
        wire=Wire([hb,gps])
        session=Session(events,stop,'COM1',115200,reconnect=False)
        original_receive=wire.recv_match
        def receive(**kwargs):
            value=original_receive(**kwargs)
            if value is None:stop.set()
            return value
        wire.recv_match=receive
        session.listen(wire, SimpleNamespace(mavlink=SimpleNamespace(MAV_TYPE_GCS=6,MAV_AUTOPILOT_INVALID=8,MAV_DATA_STREAM_ALL=0,MAV_AUTOPILOT_ARDUPILOTMEGA=3)))
        self.assertEqual(wire.mav.streams,[(1,1,0,2,1)])
        received=[item[1] for item in list(events.queue) if item[0]=='message']
        self.assertIn(gps,received)

    def test_live_coordinate_contract(self):
        state=PositionState(); now=50
        state.ingest(message('HEARTBEAT',base_mode=128,custom_mode=4),now)
        state.ingest(message('GPS_RAW_INT',fix_type=3,satellites_visible=19),now)
        state.ingest(message('GLOBAL_POSITION_INT',lat=408444442,lon=311584605,
                             alt=101200,relative_alt=12500,vx=600,vy=800,hdg=9000),now)
        state.ingest(message('LOCAL_POSITION_NED',x=14.2,y=-3.1,z=-12.5),now)
        self.assertTrue(state.fresh(now+1))
        self.assertEqual((state.position['lat'],state.position['lon']),(40.8444442,31.1584605))
        self.assertEqual((state.position['altitude'],state.position['amsl']),(12.5,101.2))
        self.assertEqual(state.ned,(14.2,-3.1,-12.5))
        self.assertEqual(state.position['heading'],90)

    def test_other_system_messages_are_not_accepted_as_vehicle_data(self):
        state=PositionState();now=10
        state.ingest(message('HEARTBEAT',base_mode=0,custom_mode=0),now)
        state.ingest(message('GPS_RAW_INT',fix_type=3,satellites_visible=12),now)
        state.ingest(message('GLOBAL_POSITION_INT',lat=410000000,lon=290000000,
                             alt=1,relative_alt=1,vx=0,vy=0,hdg=65535),now)
        self.assertTrue(state.fresh(now+1))
        self.assertFalse(state.fresh(now+4))


if __name__=='__main__':unittest.main()
