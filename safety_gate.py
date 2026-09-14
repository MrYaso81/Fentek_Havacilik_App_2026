"""Fail-closed preflight policy layered ahead of ArduPilot's own arming checks."""
import time


class SafetyGate:
    HEARTBEAT_MAX_AGE=3
    DATA_MAX_AGE=3
    ALERT_MAX_AGE=12
    EKF_ATTITUDE=1
    EKF_NAVIGATION=1|2|4|16|32
    EKF_UNINITIALIZED=1024
    BAD_SYSTEM_STATES={0,1,2,5,6,7,8}

    def __init__(self,state):self.state=state

    @staticmethod
    def action_for_mode(mode):
        mode=str(mode).upper()
        if mode=='AUTO':return 'auto'
        if mode=='RTL':return 'rtl'
        if mode in {'GUIDED','LOITER','POSHOLD','POSITION','FOLLOW','SMART_RTL','AUTO_RTL','QLOITER','QRTL',
                    'BRAKE','CIRCLE','DRIFT','THROW','ZIGZAG','AVOID_ADSB','TAKEOFF','QTAKEOFF'}:return 'navigation'
        return 'basic_mode'

    def recent_alerts(self,now):
        return [(severity,text) for stamp,severity,text in getattr(self.state,'alerts',())
                if now-stamp<=self.ALERT_MAX_AGE]

    def checks(self,now=None,action='telemetry'):
        now=time.monotonic() if now is None else now;s=self.state;errors=[]
        def add(condition,text):
            if condition and text not in errors:errors.append(text)
        heartbeat=getattr(s,'heartbeat_time',0)
        add(now-heartbeat>self.HEARTBEAT_MAX_AGE,'Heartbeat güncel değil')
        control=action in ('arm','auto','mission','navigation','rtl')
        if not control:return errors
        add(getattr(s,'autopilot',None)!=3,'Bağlı araç ArduPilot olarak doğrulanmadı')
        status=getattr(s,'system_status',None)
        add(status is None,'Uçuş kontrolcüsü çalışma durumu bilinmiyor')
        add(status in self.BAD_SYSTEM_STATES,f'Uçuş kontrolcüsü uygun durumda değil: {status}')
        battery=getattr(s,'battery',None)
        add(battery is None,'Batarya seviyesi bilinmiyor')
        add(battery is not None and battery<15,'Batarya kritik seviyede')
        add(now-getattr(s,'system_time',0)>self.DATA_MAX_AGE,'Sensör/güç durumu güncel değil')
        faults=getattr(s,'sensor_faults',None)
        add(faults is None,'Sensör sağlığı doğrulanmadı')
        add(bool(faults),f'Kart sensör sağlık hatası: 0x{faults:X}' if faults is not None else '')
        alerts=self.recent_alerts(now)
        add(bool(alerts),'Kart kritik uyarısı: '+alerts[-1][1] if alerts else '')
        fix=getattr(s,'fix',None)
        add(fix is None or fix<3,'GPS 3D fix yok')
        add(now-getattr(s,'fix_time',0)>self.DATA_MAX_AGE,'GPS verisi eski')
        flags=getattr(s,'ekf_flags',None)
        add(flags is None or now-getattr(s,'ekf_time',0)>self.DATA_MAX_AGE,'EKF durumu doğrulanmadı')
        if flags is not None:
            add(not flags&self.EKF_ATTITUDE or bool(flags&self.EKF_UNINITIALIZED),'EKF yönelim çözümü hazır değil')
        if getattr(s,'fence_breach',False):add(True,'Sanal çit ihlali etkin')
        if action=='arm':add(getattr(s,'armed',None) is not False,'DISARMED durumu doğrulanmadı')
        if action in ('auto','mission','navigation','rtl'):
            position=getattr(s,'position',None)
            add(position is None,'Küresel konum yok')
            add(now-getattr(s,'position_time',0)>self.DATA_MAX_AGE,'Konum verisi eski')
            if flags is not None:add((flags&self.EKF_NAVIGATION)!=self.EKF_NAVIGATION,'EKF konum/hız çözümü tam değil')
        if action in ('auto','mission','rtl'):
            add(getattr(s,'armed',None) is not True,'ARM durumu doğrulanmadı')
            add(getattr(s,'home',None) is None,'HOME konumu doğrulanmadı')
        return errors

    def allow(self,action,now=None):return not self.checks(now,action)

    def summary(self,now=None,action='arm'):
        errors=self.checks(now,action)
        return 'Yer istasyonu kontrolleri uygun • Son karar ArduPilot kartının' if not errors else 'BEKLE: '+' • '.join(errors)

    def checklist(self,now=None):
        now=time.monotonic() if now is None else now;s=self.state
        flags=getattr(s,'ekf_flags',None);battery=getattr(s,'battery',None);alerts=self.recent_alerts(now)
        connected=now-getattr(s,'heartbeat_time',0)<=self.HEARTBEAT_MAX_AGE and getattr(s,'autopilot',None)==3
        warnings_ok=connected and not alerts
        return [
            ('Bağlantı',now-getattr(s,'heartbeat_time',0)<=3,'Heartbeat güncel' if now-getattr(s,'heartbeat_time',0)<=3 else 'Veri eski veya yok'),
            ('Araç kimliği',getattr(s,'autopilot',None)==3,'ArduPilot' if getattr(s,'autopilot',None)==3 else 'Doğrulanmadı'),
            ('Kart durumu',getattr(s,'system_status',None) not in self.BAD_SYSTEM_STATES and getattr(s,'system_status',None) is not None,f"Durum {getattr(s,'system_status',None)}"),
            ('Batarya',battery is not None and battery>=15,'Bilinmiyor' if battery is None else f'%{battery}'),
            ('Sensörler',getattr(s,'sensor_faults',None)==0,'Doğrulanmadı' if getattr(s,'sensor_faults',None) is None else f"Hata maskesi 0x{getattr(s,'sensor_faults',0):X}"),
            ('GPS',getattr(s,'fix',None) is not None and s.fix>=3 and now-getattr(s,'fix_time',0)<=3,f"Fix {getattr(s,'fix',None)}"),
            ('EKF yönelim',flags is not None and bool(flags&1) and not flags&1024,f"Bayrak 0x{flags:X}" if flags is not None else 'Doğrulanmadı'),
            ('EKF navigasyon',flags is not None and (flags&self.EKF_NAVIGATION)==self.EKF_NAVIGATION,f"Gerekli 0x{self.EKF_NAVIGATION:X}"),
            ('HOME',getattr(s,'home',None) is not None,'Hazır' if getattr(s,'home',None) else 'Doğrulanmadı'),
            ('Sanal çit',getattr(s,'fence_breach',None) is False and now-getattr(s,'fence_time',0)<=self.DATA_MAX_AGE,
             'İhlal yok' if getattr(s,'fence_breach',None) is False and now-getattr(s,'fence_time',0)<=self.DATA_MAX_AGE else ('İHLAL' if getattr(s,'fence_breach',None) else 'Durum mesajı yok/eski')),
            ('Kart uyarıları',warnings_ok,
             'Güncel bağlantıda kritik uyarı yok' if warnings_ok else alerts[-1][1] if alerts else 'Cube bağlantısı bekleniyor'),
        ]
