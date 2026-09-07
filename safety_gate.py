"""Conservative preflight gates for commands sent to an ArduPilot vehicle."""
import time


class SafetyGate:
    def __init__(self,state):self.state=state

    def checks(self,now=None,action='telemetry'):
        now=time.monotonic() if now is None else now;s=self.state;errors=[]
        if now-s.heartbeat_time>3:errors.append('Heartbeat güncel değil')
        if action in ('arm','auto','mission'):
            if s.fix is None or s.fix<3:errors.append('GPS 3D fix yok')
            if now-s.fix_time>3:errors.append('GPS verisi eski')
            if action in ('auto','mission') and s.position is None:errors.append('Küresel konum yok')
            if action=='arm' and s.armed:errors.append('Araç zaten ARM')
            if s.battery is not None and s.battery<15:errors.append('Batarya kritik seviyede')
        if action in ('mission','auto') and s.armed is not True:errors.append('AUTO için kartın ARM durumu doğrulanmadı')
        return errors

    def allow(self,action,now=None):return not self.checks(now,action)

    def summary(self,now=None):
        errors=self.checks(now,'telemetry')
        return 'GÜVENLİ' if not errors else 'BEKLE: '+' • '.join(errors)
