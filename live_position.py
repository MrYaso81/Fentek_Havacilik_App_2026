"""Decode MAVLink coordinates without mixing simulated and measured samples."""
import math
import time


class PositionState:
    def __init__(self):
        self.position=None;self.ned=None;self.home=None
        self.position_time=0;self.ned_time=0;self.heartbeat_time=0
        self.fix=None;self.fix_time=0;self.satellites=None
        self.armed=None;self.mode='—';self.battery=None
        self.attitude=None;self.attitude_time=0

    def ingest(self,msg,now=None):
        now=time.monotonic() if now is None else now
        kind=msg.get_type()
        if kind=='HEARTBEAT':
            self.heartbeat_time=now;self.armed=bool(msg.base_mode & 128)
            self.mode=f'Mod {msg.custom_mode}'
        elif kind=='GPS_RAW_INT':
            self.fix=msg.fix_type;self.fix_time=now
            self.satellites=None if msg.satellites_visible==255 else msg.satellites_visible
        elif kind=='GLOBAL_POSITION_INT':
            lat,lon=msg.lat/1e7,msg.lon/1e7
            # Zero/zero can be a real location. Fresh GPS fix distinguishes it from no fix.
            if not (-90<=lat<=90 and -180<=lon<=180) or self.fix is None or self.fix<3 or now-self.fix_time>3:return
            self.position=dict(lat=lat,lon=lon,altitude=msg.relative_alt/1000,
                               amsl=msg.alt/1000,speed=math.hypot(msg.vx,msg.vy)/100,
                               heading=None if msg.hdg==65535 else msg.hdg/100)
            self.position_time=now
        elif kind=='LOCAL_POSITION_NED':
            values=(msg.x,msg.y,msg.z)
            if all(math.isfinite(v) for v in values):self.ned=values;self.ned_time=now
        elif kind=='HOME_POSITION':
            self.home=(msg.latitude/1e7,msg.longitude/1e7,msg.altitude/1000)
        elif kind=='ATTITUDE':
            if all(math.isfinite(v) for v in (msg.roll,msg.pitch,msg.yaw)):
                self.attitude=tuple(math.degrees(v) for v in (msg.roll,msg.pitch,msg.yaw));self.attitude_time=now
        elif kind=='SYS_STATUS':self.battery=None if msg.battery_remaining<0 else msg.battery_remaining

    def fresh(self,now=None):
        now=time.monotonic() if now is None else now
        return bool(self.position is not None and now-self.position_time<3 and now-self.heartbeat_time<3
                    and self.fix is not None and self.fix>=3 and now-self.fix_time<3)
