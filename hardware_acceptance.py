"""Read-only physical Cube acceptance checks used by the safety page."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class AcceptanceCheck:
    name: str
    ok: bool | None
    detail: str
    critical: bool = True


PARAMETERS=('ARMING_CHECK','BATT_MONITOR','FS_GCS_ENABLE')
BAD_SYSTEM_STATES={0,1,2,5,6,7,8}
EKF_NAVIGATION=1|2|4|16|32


def _param(params,name):
    item=params.get(name)
    return None if item is None else float(item[0])


def evaluate_acceptance(state,now,phase='USB yer testi',params=None,mode_names=()):
    """Return tri-state checks. None means data has not been proven yet."""
    params=params or {};telemetry=phase=='Kablosuz telemetri / uçuş öncesi'
    heartbeat_age=now-getattr(state,'heartbeat_time',0)
    system_age=now-getattr(state,'system_time',0)
    fix_age=now-getattr(state,'fix_time',0)
    position_age=now-getattr(state,'position_time',0)
    ekf_age=now-getattr(state,'ekf_time',0)
    radio_age=now-getattr(state,'radio_time',0)
    connected=heartbeat_age<=3
    rows=[
        AcceptanceCheck('MAVLink bağlantısı',connected,'Heartbeat %.1f sn' % heartbeat_age if connected else 'Güncel heartbeat yok'),
        AcceptanceCheck('Kart kimliği',getattr(state,'autopilot',None)==3 if connected else None,
                        'ArduPilot doğrulandı' if getattr(state,'autopilot',None)==3 else 'ArduPilot kimliği bekleniyor'),
        AcceptanceCheck('Yerde güvenlik',getattr(state,'armed',None) is False if connected else None,
                        'DISARMED' if getattr(state,'armed',None) is False else ('ARMED • testi durdurun' if getattr(state,'armed',None) else 'ARM durumu bekleniyor')),
    ]
    status=getattr(state,'system_status',None)
    rows.append(AcceptanceCheck('Kart çalışma durumu',None if status is None or system_age>3 else status not in BAD_SYSTEM_STATES,
                                'Durum bilinmiyor/eski' if status is None or system_age>3 else f'MAV_STATE {status}'))
    faults=getattr(state,'sensor_faults',None)
    rows.append(AcceptanceCheck('Sensör sağlığı',None if faults is None or system_age>3 else faults==0,
                                'SYS_STATUS bekleniyor' if faults is None or system_age>3 else ('Hata yok' if faults==0 else f'Hata maskesi 0x{faults:X}')))
    fix=getattr(state,'fix',None);sat=getattr(state,'satellites',None)
    rows.append(AcceptanceCheck('Here3 / GPS',None if fix is None or fix_age>3 else fix>=3,
                                'GPS verisi bekleniyor' if fix is None or fix_age>3 else f'Fix {fix} • uydu {sat if sat is not None else "?"}'))
    position=getattr(state,'position',None)
    rows.append(AcceptanceCheck('Canlı konum',None if position is None or position_age>3 else True,
                                'GLOBAL_POSITION_INT bekleniyor' if position is None or position_age>3 else 'WGS84 konumu güncel'))
    flags=getattr(state,'ekf_flags',None)
    ekf_ok=None if flags is None or ekf_age>3 else bool(flags&1) and not bool(flags&1024)
    rows.append(AcceptanceCheck('EKF yönelim',ekf_ok,'EKF verisi bekleniyor' if flags is None or ekf_age>3 else f'Bayrak 0x{flags:X}'))
    nav_ok=None if flags is None or ekf_age>3 else (flags&EKF_NAVIGATION)==EKF_NAVIGATION
    rows.append(AcceptanceCheck('EKF navigasyon',nav_ok,'EKF verisi bekleniyor' if flags is None or ekf_age>3 else f'Gerekli 0x{EKF_NAVIGATION:X}',telemetry))
    battery=getattr(state,'battery',None);voltage=getattr(state,'battery_voltage',None)
    battery_ok=None if battery is None or system_age>3 else battery>=20
    rows.append(AcceptanceCheck('Batarya monitörü',battery_ok,
                                'Canlı batarya yüzdesi bekleniyor' if battery is None or system_age>3 else f'%{battery} • {voltage:.2f} V' if voltage is not None else f'%{battery}',telemetry))
    home=getattr(state,'home',None)
    rows.append(AcceptanceCheck('HOME konumu',True if home is not None else None,'Hazır' if home is not None else 'HOME_POSITION bekleniyor',telemetry))
    arming=_param(params,'ARMING_CHECK')
    rows.append(AcceptanceCheck('ARMING_CHECK',None if arming is None else arming!=0,
                                'Parametre bekleniyor' if arming is None else f'Değer {arming:g}'))
    batt_monitor=_param(params,'BATT_MONITOR')
    rows.append(AcceptanceCheck('BATT_MONITOR',None if batt_monitor is None else batt_monitor>0,
                                'Parametre bekleniyor' if batt_monitor is None else f'Değer {batt_monitor:g}',telemetry))
    fs_gcs=_param(params,'FS_GCS_ENABLE')
    rows.append(AcceptanceCheck('Telemetri failsafe',None if fs_gcs is None else fs_gcs>0,
                                'FS_GCS_ENABLE bekleniyor' if fs_gcs is None else f'Değer {fs_gcs:g}',telemetry))
    modes={str(name).upper() for name in mode_names}
    mode_ok=True if {'STABILIZE','RTL'}<=modes else (False if modes else None)
    rows.append(AcceptanceCheck('Temel uçuş modları',mode_ok,
                                'STABILIZE ve RTL bulundu' if mode_ok else ('Mod tablosu bekleniyor' if not modes else 'STABILIZE veya RTL eksik'),telemetry))
    radio=getattr(state,'radio',{}) or {}
    radio_ok=None if not radio or radio_age>3 else all(radio.get(k) not in (None,255) for k in ('rssi','remrssi','noise','remnoise'))
    rows.append(AcceptanceCheck('SiK RADIO_STATUS',radio_ok,
                                'Radyo verisi bekleniyor' if radio_ok is None else ('Yer ve hava radyo verisi alındı' if radio_ok else 'Radyo alanları eksik'),telemetry))
    return rows


def acceptance_result(rows):
    critical=[row for row in rows if row.critical]
    if any(row.ok is False for row in critical):return 'BAŞARISIZ'
    if any(row.ok is None for row in critical):return 'BEKLİYOR'
    return 'UYGUN'
