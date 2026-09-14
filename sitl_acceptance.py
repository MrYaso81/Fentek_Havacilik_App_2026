"""Read-only ArduPilot SITL connection acceptance and local fault matrix."""
from __future__ import annotations

import copy
import sys
import time
from pathlib import Path
from types import SimpleNamespace

ROOT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT/'vendor'))
sys.path.insert(0,str(ROOT))

from live_position import PositionState
from safety_gate import SafetyGate


ALLOWED_ENDPOINTS=('tcp:127.0.0.1:5760','tcp:127.0.0.1:5762')


def validate_endpoint(endpoint):
    value=str(endpoint).strip().lower()
    if value not in ALLOWED_ENDPOINTS:raise ValueError('SITL testi yalnız yerel 127.0.0.1:5760 veya :5762 adresini kabul eder.')
    return value


def fault_matrix():
    now=100.0
    base=SimpleNamespace(heartbeat_time=now,autopilot=3,system_status=4,system_time=now,battery=80,
        sensor_faults=0,alerts=[],fix=3,fix_time=now,position={'lat':41,'lon':29},position_time=now,
        ekf_flags=63,ekf_time=now,fence_breach=False,fence_time=now,armed=True,home=(41,29,100))
    cases=(('GPS kaybı','fix',2),('Kritik batarya','battery',8),('Sensör hatası','sensor_faults',4),
           ('EKF navigasyon kaybı','ekf_flags',1),('HOME kaybı','home',None),('Sanal çit ihlali','fence_breach',True))
    results=[]
    for name,field,value in cases:
        state=copy.copy(base);setattr(state,field,value);blocked=not SafetyGate(state).allow('auto',now+1);results.append((name,blocked))
    return results


def run_sitl(endpoint='tcp:127.0.0.1:5760',timeout=12):
    endpoint=validate_endpoint(endpoint)
    from pymavlink import mavutil
    link=mavutil.mavlink_connection(endpoint,source_system=255,source_component=190,dialect='ardupilotmega',autoreconnect=False)
    state=PositionState();types=set();sitl_proven=False;start=time.monotonic();identity=None
    try:
        while time.monotonic()-start<min(timeout,6):
            msg=link.recv_match(type='HEARTBEAT',blocking=True,timeout=.5)
            if msg and msg.autopilot==mavutil.mavlink.MAV_AUTOPILOT_ARDUPILOTMEGA:
                identity=(msg.get_srcSystem(),msg.get_srcComponent());state.ingest(msg);types.add('HEARTBEAT');break
        if not identity:raise TimeoutError('Yerel ArduPilot SITL heartbeat bulunamadı. SITL önce başlatılmalı.')
        system,component=identity
        link.mav.param_request_read_send(system,component,b'SIM_SPEEDUP',-1)
        link.mav.request_data_stream_send(system,component,mavutil.mavlink.MAV_DATA_STREAM_ALL,5,1)
        deadline=time.monotonic()+timeout
        while time.monotonic()<deadline:
            msg=link.recv_match(blocking=True,timeout=.3)
            if msg is None:continue
            if (msg.get_srcSystem(),msg.get_srcComponent())!=identity:continue
            kind=msg.get_type();types.add(kind);state.ingest(msg)
            if kind=='PARAM_VALUE':
                name=msg.param_id.decode(errors='ignore').rstrip('\x00') if isinstance(msg.param_id,bytes) else str(msg.param_id).rstrip('\x00')
                if name=='SIM_SPEEDUP':sitl_proven=True
            if sitl_proven and {'HEARTBEAT','SYS_STATUS','GPS_RAW_INT','GLOBAL_POSITION_INT','ATTITUDE'}<=types:break
        if not sitl_proven:raise RuntimeError('Hedef SIM_SPEEDUP parametresiyle SITL olarak doğrulanmadı; test durduruldu.')
        required={'HEARTBEAT','SYS_STATUS','GPS_RAW_INT','GLOBAL_POSITION_INT','ATTITUDE'}
        missing=sorted(required-types)
        matrix=fault_matrix()
        return {'endpoint':endpoint,'identity':identity,'messages':sorted(types),'missing':missing,
                'faults':matrix,'passed':not missing and all(blocked for _,blocked in matrix)}
    finally:
        link.close()


def format_report(result):
    lines=[f"SITL: {result['endpoint']} • Araç {result['identity'][0]}/{result['identity'][1]}",
           'Mesajlar: '+', '.join(result['messages']),
           'Eksik kritik mesaj: '+(', '.join(result['missing']) if result['missing'] else 'yok'),'Hata enjeksiyonları:']
    lines += [f"• {name}: {'ENGELLENDİ' if blocked else 'HATA • engellenmedi'}" for name,blocked in result['faults']]
    lines.append('SONUÇ: '+('GEÇTİ' if result['passed'] else 'GEÇMEDİ'))
    return '\n'.join(lines)


if __name__=='__main__':
    try:print(format_report(run_sitl()))
    except Exception as exc:raise SystemExit('SITL testi başlatılamadı: '+str(exc))
