"""Deterministic Cube/ArduCopter acceptance simulation; opens no physical port."""
from collections import deque
from types import SimpleNamespace
from pathlib import Path
import queue
import sys
import threading
import time

ROOT=Path(__file__).parent
sys.path.insert(0,str(ROOT/'vendor'))
sys.path.insert(0,str(ROOT))
from pymavlink import mavutil
from connection import Session
from live_position import PositionState
from safety_gate import SafetyGate


def message(kind,**values):
    values.setdefault('get_srcSystem',lambda:1)
    values.setdefault('get_srcComponent',lambda:1)
    values.setdefault('get_type',lambda:kind)
    return SimpleNamespace(**values)


def heartbeat(mode=0,armed=False,vehicle_type=None):
    m=mavutil.mavlink
    vehicle_type=m.MAV_TYPE_QUADROTOR if vehicle_type is None else vehicle_type
    return message('HEARTBEAT',type=vehicle_type,autopilot=m.MAV_AUTOPILOT_ARDUPILOTMEGA,
                   base_mode=m.MAV_MODE_FLAG_SAFETY_ARMED if armed else 0,custom_mode=mode,
                   system_status=m.MAV_STATE_ACTIVE)


def health_messages(armed=True,vehicle_type=None):
    channels={f'chan{i}_raw':1500+i for i in range(1,19)}
    servos={f'servo{i}_raw':1100+i*10 for i in range(1,17)}
    return [
        heartbeat(0,armed,vehicle_type),
        message('SYS_STATUS',onboard_control_sensors_present=0xFFFF,onboard_control_sensors_enabled=0xFFFF,onboard_control_sensors_health=0xFFFF,
                voltage_battery=16300,current_battery=123,battery_remaining=82,load=235),
        message('GPS_RAW_INT',fix_type=3,satellites_visible=18,eph=78,epv=115),
        message('GLOBAL_POSITION_INT',lat=408444442,lon=311584605,alt=101200,relative_alt=12500,
                vx=600,vy=800,hdg=9000),
        message('HOME_POSITION',latitude=408444442,longitude=311584605,altitude=88700),
        message('LOCAL_POSITION_NED',x=14.2,y=-3.1,z=-12.5),
        message('ATTITUDE',roll=.1,pitch=-.05,yaw=1.2),
        message('VFR_HUD',airspeed=14.2,groundspeed=10.0,climb=1.8,throttle=44),
        message('VIBRATION',vibration_x=8.1,vibration_y=7.4,vibration_z=9.0,clipping_0=0,clipping_1=0,clipping_2=0),
        message('RC_CHANNELS',rssi=210,**channels),
        message('SERVO_OUTPUT_RAW',port=0,**servos),
        message('BATTERY_STATUS',id=0,current_consumed=630,temperature=2875),
        message('EKF_STATUS_REPORT',flags=63,velocity_variance=.08,pos_horiz_variance=.12,
                pos_vert_variance=.16,compass_variance=.05),
        message('STATUSTEXT',severity=6,text='PreArm checks simulated OK'),
        message('MISSION_CURRENT',seq=2),
        message('FENCE_STATUS',breach_status=0),
    ]


class SimulatedMav:
    def __init__(self,vehicle):self.vehicle=vehicle
    def heartbeat_send(self,*args):pass
    def request_data_stream_send(self,*args):self.vehicle.stream_requested=True
    def set_mode_send(self,system,flag,custom_mode):
        self.vehicle.mode_ids.append(custom_mode);self.vehicle.mode=custom_mode
        self.vehicle.messages.put(heartbeat(custom_mode,self.vehicle.armed,self.vehicle.vehicle_type))
    def command_long_send(self,system,component,command,confirmation,*params):
        m=mavutil.mavlink;self.vehicle.commands.append(command)
        if command==m.MAV_CMD_COMPONENT_ARM_DISARM:
            self.vehicle.armed=bool(params[0]);self.vehicle.messages.put(message('COMMAND_ACK',command=command,result=0))
            self.vehicle.messages.put(heartbeat(self.vehicle.mode,self.vehicle.armed,self.vehicle.vehicle_type))
        elif command==m.MAV_CMD_MISSION_START:
            self.vehicle.messages.put(message('COMMAND_ACK',command=command,result=0))
    def param_request_list_send(self,system,component):
        for index,(name,(value,kind)) in enumerate(self.vehicle.parameters.items()):
            self.vehicle.messages.put(message('PARAM_VALUE',param_id=name,param_value=value,param_type=kind,
                                              param_index=index,param_count=len(self.vehicle.parameters)))
    def param_request_read_send(self,system,component,name,index):
        if index>=0:
            key=list(self.vehicle.parameters)[index]
        else:key=name.decode('ascii')
        value,kind=self.vehicle.parameters[key]
        self.vehicle.messages.put(message('PARAM_VALUE',param_id=key,param_value=value,param_type=kind,
                                          param_index=list(self.vehicle.parameters).index(key),param_count=len(self.vehicle.parameters)))
    def param_set_send(self,system,component,name,value,kind):
        key=name.decode('ascii');self.vehicle.parameters[key]=(float(value),kind)
        self.vehicle.messages.put(message('PARAM_VALUE',param_id=key,param_value=float(value),param_type=kind,
                                          param_index=list(self.vehicle.parameters).index(key),param_count=len(self.vehicle.parameters)))


class SimulatedCube:
    def __init__(self,stop,actions,vehicle_type):
        self.stop=stop;self.actions=deque(actions);self.messages=queue.Queue();self.empty_cycles=0
        self.vehicle_type=vehicle_type;self.mode=0;self.armed=False;self.mode_ids=[];self.commands=[];self.stream_requested=False
        self.parameters={'BATT_CAPACITY':(5000.,6),'FS_GCS_ENABLE':(1.,6),'RTL_ALT':(1500.,6),'ARMING_CHECK':(1.,6)}
        self.mav=SimulatedMav(self)
        self.messages.put(heartbeat(vehicle_type=vehicle_type))
        for item in health_messages(False,vehicle_type)[1:]:self.messages.put(item)
    def recv_match(self,**kwargs):
        try:
            item=self.messages.get_nowait();self.empty_cycles=0;return item
        except queue.Empty:
            if self.actions:
                self.session.commands.put(self.actions.popleft());return None
            if self.session.commands.empty():
                self.empty_cycles+=1
                if self.empty_cycles>3:self.stop.set()
            return None


def run_protocol_simulation(vehicle_type):
    m=mavutil.mavlink;mapping=mavutil.mode_mapping_byname(vehicle_type)
    actions=[('arm',True)]+[('mode',name) for name in sorted(mapping,key=mapping.get)]
    actions += [('mode','GEÇERSİZ_MOD'),('mission','start'),('mission','stop'),('arm',False),('param_list',),
                ('param_set','BATT_CAPACITY',5200),('param_set','ARMING_CHECK',0)]
    events=queue.Queue();stop=threading.Event();session=Session(events,stop,'SIMULATED',115200,reconnect=False)
    vehicle=SimulatedCube(stop,actions,vehicle_type);vehicle.session=session
    session.listen(vehicle,mavutil)
    results=list(events.queue);controls=[v for k,v in results if k=='control']
    verified=[v for v in controls if 'modu kart tarafından doğrulandı' in v]
    param_results=[v for k,v in results if k=='param_result']
    assert vehicle.stream_requested
    assert set(vehicle.mode_ids)>=set(mapping.values())
    assert len(verified)==len(mapping),(len(verified),len(mapping))
    assert m.MAV_CMD_COMPONENT_ARM_DISARM in vehicle.commands and m.MAV_CMD_MISSION_START in vehicle.commands
    assert vehicle.armed is False
    assert vehicle.parameters['BATT_CAPACITY'][0]==5200
    assert vehicle.parameters['ARMING_CHECK'][0]==1
    assert any(name=='BATT_CAPACITY' and ok for name,ok,note in param_results)
    assert any(name=='ARMING_CHECK' and not ok and 'engeller' in note for name,ok,note in param_results)
    assert any('Parametre listesi tamamlandı' in value for value in controls)
    assert any('Uçuş modu desteklenmiyor' in value for value in controls)
    assert not [v for k,v in results if k in ('error','lost','param_error')]
    return len(mapping),len(results)


def run_telemetry_simulation():
    now=100.;state=PositionState()
    for msg in health_messages(True):state.ingest(msg,now)
    required={'Enlem','Boylam','HOME üstü irtifa','Batarya voltajı','Batarya akımı','GPS HDOP','GPS VDOP',
              'Hava hızı','Dikey hız','CPU yükü','EKF bayrakları','vibration_x','RC 18','Çıkış 0:16',
              'Batarya 0 tüketim','Aktif görev adımı','Sanal çit ihlali'}
    assert required<=state.metrics.keys(),required-state.metrics.keys()
    assert state.fresh(now+1) and SafetyGate(state).allow('auto',now+1)
    assert not SafetyGate(state).allow('auto',now+4)
    scenarios=[]
    for name,change in [
        ('GPS 2D',lambda s:setattr(s,'fix',2)),('Düşük batarya',lambda s:setattr(s,'battery',10)),
        ('Sensör arızası',lambda s:setattr(s,'sensor_faults',4)),('EKF başlatılmadı',lambda s:setattr(s,'ekf_flags',1025)),
        ('DISARMED AUTO',lambda s:setattr(s,'armed',False)),
        ('Kritik kart durumu',lambda s:setattr(s,'system_status',6)),
        ('Eski sensör verisi',lambda s:setattr(s,'system_time',1)),
        ('Kritik PreArm mesajı',lambda s:setattr(s,'alerts',[(now,2,'PreArm: sensor failure')])),
        ('Sanal çit ihlali',lambda s:setattr(s,'fence_breach',True)),
        ('HOME bilinmiyor',lambda s:setattr(s,'home',None)),
        ('EKF navigasyon eksik',lambda s:setattr(s,'ekf_flags',1))]:
        clone=SimpleNamespace(**state.__dict__);change(clone)
        assert not SafetyGate(clone).allow('auto',now+1),name;scenarios.append(name)
    return len(required),len(scenarios)+1


if __name__=='__main__':
    m=mavutil.mavlink
    copter_modes,copter_events=run_protocol_simulation(m.MAV_TYPE_QUADROTOR)
    plane_modes,plane_events=run_protocol_simulation(m.MAV_TYPE_FIXED_WING)
    metrics,blocked=run_telemetry_simulation()
    print(f'PASS | Copter {copter_modes} mod | Plane {plane_modes} mod | {metrics} kritik telemetri alanı | '
          f'{blocked} arıza senaryosu | {copter_events+plane_events} MAVLink olayı')
