"""Small, verified ArduPilot parameter client used by safety settings screens."""
import math
import time


FAILSAFE_PARAMETERS=('FS_GCS_ENABLE','FS_GCS_TIMEOUT','FS_THR_ENABLE','FS_EKF_ACTION','FS_BATT_ENABLE')


class ParameterClient:
    def __init__(self,link,system,component=1,stop=None,report=lambda text:None):
        self.link=link;self.system=system;self.component=component
        self.stop=stop;self.report=report

    def _wait(self, names, timeout=5):
        deadline=time.monotonic()+timeout
        wanted=set(names);values={}
        while time.monotonic()<deadline:
            if self.stop and self.stop.is_set():raise RuntimeError('Parametre işlemi iptal edildi.')
            msg=self.link.recv_match(blocking=True,timeout=.25)
            if msg is None or msg.get_type()!='PARAM_VALUE':continue
            if msg.get_srcSystem()!=self.system or msg.get_srcComponent()!=self.component:continue
            name=msg.param_id.decode(errors='ignore').rstrip('\x00') if isinstance(msg.param_id,bytes) else str(msg.param_id).rstrip('\x00')
            if name in wanted:values[name]=float(msg.param_value)
            if len(values)==len(wanted):return values
        missing=', '.join(sorted(wanted-set(values)))
        raise TimeoutError(f'Kart parametre yanıtı vermedi: {missing}')

    def read_failsafes(self):
        for name in FAILSAFE_PARAMETERS:
            self.link.mav.param_request_read_send(self.system,self.component,name.encode('ascii'),-1)
        values=self._wait(FAILSAFE_PARAMETERS,timeout=8)
        self.report(f'{len(values)} failsafe parametresi karttan okundu.')
        return values

    def set_failsafe(self,name,value):
        if name not in FAILSAFE_PARAMETERS:raise ValueError('Bu parametre güvenlik listesinde değil.')
        if not math.isfinite(float(value)):raise ValueError('Parametre değeri sayı olmalı.')
        # Parameter writes are intentionally limited to the allow-list above.
        self.link.mav.param_set_send(self.system,self.component,name.encode('ascii'),float(value),9)
        values=self._wait((name,),timeout=5)
        if abs(values[name]-float(value))>.001:raise RuntimeError(f'Kart {name} değerini doğrulamadı.')
        self.report(f'{name} kartta doğrulandı: {values[name]:g}')
        return values[name]
