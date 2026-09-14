"""Decode MAVLink coordinates without mixing simulated and measured samples."""
import math
import time


class PositionState:
    def __init__(self):
        self.position=None;self.ned=None;self.home=None
        self.position_time=0;self.ned_time=0;self.heartbeat_time=0
        self.fix=None;self.fix_time=0;self.satellites=None
        self.armed=None;self.mode='—';self.battery=None
        self.battery_voltage=None;self.battery_current=None;self.battery_consumed=None;self.battery_temperature=None
        self.attitude=None;self.attitude_time=0
        self.metrics={};self.messages=[];self.sensor_faults=None;self.system_time=0;self.ekf_flags=None;self.ekf_time=0
        self.sensor_present=None;self.sensor_enabled=None;self.sensor_health=None
        self.autopilot=None;self.vehicle_type=None;self.system_status=None
        self.fence_breach=None;self.fence_time=0;self.alerts=[]
        self.radio={};self.radio_time=0
        self.sequence_by_source={};self.packet_received=0;self.packet_lost=0

    def ingest(self,msg,now=None):
        now=time.monotonic() if now is None else now
        kind=msg.get_type()
        def metric(label,value,unit=''):
            if isinstance(value,(int,float)) and not math.isfinite(value):return
            self.metrics[label]=(value,unit,now)
        try:
            source=(msg.get_srcSystem(),msg.get_srcComponent())
            seq=int(msg.get_seq() if hasattr(msg,'get_seq') else msg._header.seq)
            previous=self.sequence_by_source.get(source)
            if previous is not None:
                self.packet_lost+=(seq-previous-1)%256
            self.sequence_by_source[source]=seq;self.packet_received+=1
            total=self.packet_received+self.packet_lost
            if total:metric('MAVLink tahmini paket kaybı',100*self.packet_lost/total,'%')
        except Exception:pass
        if kind=='SYS_STATUS':
            self.system_time=now
            self.sensor_present=msg.onboard_control_sensors_present
            self.sensor_enabled=msg.onboard_control_sensors_enabled
            self.sensor_health=msg.onboard_control_sensors_health
            self.sensor_faults=self.sensor_enabled & ~self.sensor_health
            if msg.voltage_battery!=65535:
                self.battery_voltage=msg.voltage_battery/1000;metric('Batarya voltajı',self.battery_voltage,'V')
            if msg.current_battery!=-1:
                self.battery_current=msg.current_battery/100;metric('Batarya akımı',self.battery_current,'A')
            metric('CPU yükü',msg.load/10,'%')
        elif kind=='VFR_HUD':
            for key,label,unit in [('airspeed','Hava hızı','m/s'),('groundspeed','Yer hızı','m/s'),('climb','Dikey hız','m/s'),('throttle','Gaz','%')]:metric(label,getattr(msg,key),unit)
        elif kind=='GPS_RAW_INT':
            for key,label in [('eph','GPS HDOP'),('epv','GPS VDOP')]:
                value=getattr(msg,key,65535)
                if value!=65535:metric(label,value/100)
        elif kind=='VIBRATION':
            for key in ('vibration_x','vibration_y','vibration_z','clipping_0','clipping_1','clipping_2'):metric(key,getattr(msg,key))
        elif kind=='RC_CHANNELS':
            for i in range(1,19):
                value=getattr(msg,f'chan{i}_raw',65535)
                if value!=65535:metric(f'RC {i}',value,'µs')
            if msg.rssi!=255:metric('RC RSSI',msg.rssi,'ham 0–254')
        elif kind=='SERVO_OUTPUT_RAW':
            for i in range(1,17):
                value=getattr(msg,f'servo{i}_raw',0)
                if value:metric(f'Çıkış {msg.port}:{i}',value,'µs')
        elif kind=='BATTERY_STATUS':
            if msg.current_consumed>=0:
                if msg.id==0:self.battery_consumed=msg.current_consumed
                metric(f'Batarya {msg.id} tüketim',msg.current_consumed,'mAh')
            if msg.temperature!=32767:
                if msg.id==0:self.battery_temperature=msg.temperature/100
                metric(f'Batarya {msg.id} sıcaklık',msg.temperature/100,'°C')
        elif kind=='EKF_STATUS_REPORT':
            self.ekf_flags=msg.flags;self.ekf_time=now
            metric('EKF bayrakları',msg.flags)
            for key in ('velocity_variance','pos_horiz_variance','pos_vert_variance','compass_variance'):metric(key,getattr(msg,key))
        elif kind=='STATUSTEXT':
            value=msg.text.decode(errors='replace') if isinstance(msg.text,bytes) else str(msg.text)
            self.messages.append((now,msg.severity,value.rstrip('\x00')));self.messages=self.messages[-100:]
            if msg.severity<=4:
                self.alerts.append((now,msg.severity,value.rstrip('\x00')));self.alerts=self.alerts[-30:]
        elif kind=='MISSION_CURRENT':metric('Aktif görev adımı',msg.seq)
        elif kind=='FENCE_STATUS':
            self.fence_breach=bool(msg.breach_status);self.fence_time=now;metric('Sanal çit ihlali',msg.breach_status)
        elif kind=='RADIO_STATUS':
            self.radio={key:getattr(msg,key,None) for key in ('rssi','remrssi','txbuf','noise','remnoise','rxerrors','fixed')}
            self.radio_time=now
            labels={'rssi':'SiK yerel RSSI','remrssi':'SiK uzak RSSI','txbuf':'SiK gönderim tamponu',
                    'noise':'SiK yerel gürültü','remnoise':'SiK uzak gürültü','rxerrors':'SiK alım hatası','fixed':'SiK düzeltilen paket'}
            for key,label in labels.items():
                value=self.radio.get(key)
                if value is not None and value!=255:metric(label,value,'%' if key=='txbuf' else '')
        if kind=='HEARTBEAT':
            self.heartbeat_time=now;self.armed=bool(msg.base_mode & 128)
            self.autopilot=getattr(msg,'autopilot',None);self.vehicle_type=getattr(msg,'type',None)
            self.system_status=getattr(msg,'system_status',None)
            self.mode=f'Mod {msg.custom_mode}'
            metric('ARM durumu',1 if self.armed else 0)
        elif kind=='GPS_RAW_INT':
            self.fix=msg.fix_type;self.fix_time=now
            self.satellites=None if msg.satellites_visible==255 else msg.satellites_visible
            metric('GPS fix',self.fix)
            if self.satellites is not None:metric('Uydu sayısı',self.satellites)
        elif kind=='GLOBAL_POSITION_INT':
            lat,lon=msg.lat/1e7,msg.lon/1e7
            # Zero/zero can be a real location. Fresh GPS fix distinguishes it from no fix.
            if not (-90<=lat<=90 and -180<=lon<=180) or self.fix is None or self.fix<3 or now-self.fix_time>3:return
            self.position=dict(lat=lat,lon=lon,altitude=msg.relative_alt/1000,
                               amsl=msg.alt/1000,speed=math.hypot(msg.vx,msg.vy)/100,
                               heading=None if msg.hdg==65535 else msg.hdg/100)
            self.position_time=now
            for key,label,unit in [('lat','Enlem','°'),('lon','Boylam','°'),('altitude','HOME üstü irtifa','m'),('amsl','Deniz seviyesi irtifa','m')]:metric(label,self.position[key],unit)
        elif kind=='LOCAL_POSITION_NED':
            values=(msg.x,msg.y,msg.z)
            if all(math.isfinite(v) for v in values):self.ned=values;self.ned_time=now
        elif kind=='HOME_POSITION':
            self.home=(msg.latitude/1e7,msg.longitude/1e7,msg.altitude/1000)
        elif kind=='ATTITUDE':
            if all(math.isfinite(v) for v in (msg.roll,msg.pitch,msg.yaw)):
                self.attitude=tuple(math.degrees(v) for v in (msg.roll,msg.pitch,msg.yaw));self.attitude_time=now
                for label,value in zip(('Yatış','Yunuslama','Yönelim'),self.attitude):metric(label,value,'°')
        elif kind=='SYS_STATUS':
            self.battery=None if msg.battery_remaining<0 else msg.battery_remaining
            if self.battery is not None:metric('Batarya seviyesi',self.battery,'%')

    def fresh(self,now=None):
        now=time.monotonic() if now is None else now
        return bool(self.position is not None and now-self.position_time<3 and now-self.heartbeat_time<3
                    and self.fix is not None and self.fix>=3 and now-self.fix_time<3)
