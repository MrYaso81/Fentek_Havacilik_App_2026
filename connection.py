"""Transport validation and reconnecting MAVLink session; no UI dependencies."""
import queue
import time
import math
from parameter_store import checked_value,validate_safety_parameter
from live_position import PositionState
from safety_gate import SafetyGate

class PriorityCommands:
    """Emergency MAVLink actions bypass slow mission/parameter traffic."""
    def __init__(self): self._q=queue.PriorityQueue();self._seq=0
    def put(self,action):
        self._seq+=1; kind=action[0] if isinstance(action,tuple) and action else ''
        priority=0 if (kind=='mode' and str(action[1]).upper() in ('RTL','LAND','LOITER')) or kind=='arm' or (kind=='mission' and action[1] in ('stop','pause')) or kind in ('manual_control','output_stop') else 10
        self._q.put((priority,self._seq,action))
    def get_nowait(self): return self._q.get_nowait()[2]
    def empty(self): return self._q.empty()


def endpoint(kind, address, baud):
    address = address.strip()
    if kind == 'Seri / USB':
        if not address or not address.upper().startswith('COM') or not address[3:].isdigit():
            raise ValueError('Geçerli bir COM portu seçin (örnek COM5).')
        if int(baud) not in (9600, 19200, 38400, 57600, 115200, 230400, 460800, 921600):
            raise ValueError('Listeden bağlantı hızını seçin.')
        return address.upper()
    prefixes = {'UDP dinle': 'udpin', 'UDP gönder': 'udpout', 'TCP': 'tcp'}
    if kind not in prefixes:
        raise ValueError('Bağlantı türü bilinmiyor.')
    host, sep, port = address.rpartition(':')
    if not sep or not host or ':' in host or not port.isdigit() or not 1 <= int(port) <= 65535:
        raise ValueError('Adres bilgisayar:port biçiminde olmalı (örnek 127.0.0.1:14550).')
    return f'{prefixes[kind]}:{host}:{int(port)}'


class Session:
    def __init__(self, events, stop, address, baud, reconnect=True, calibration=False, factory=None):
        self.events, self.stop = events, stop
        self.address, self.baud = address, baud
        self.reconnect, self.calibration = reconnect, calibration
        self.factory = factory
        self.commands = PriorityCommands()
        self.identity = None
        self.link = None

    def run(self):
        try:
            from pymavlink import mavutil
        except ImportError:
            self.events.put(('error', 'Gerekli paketler eksik. KUR.bat dosyasını çalıştırın.'))
            self.events.put(('done', None))
            return
        attempts = 0
        while not self.stop.is_set():
            link = None
            try:
                self.events.put(('status', f'Bağlanıyor: {self.address}'))
                factory = self.factory or mavutil.mavlink_connection
                link = factory(self.address, baud=self.baud, source_system=255, source_component=190, dialect='ardupilotmega')
                self.link = link
                self.listen(link, mavutil)
            except Exception as exc:
                self.events.put(('lost', str(exc)))
            finally:
                if link:
                    link.close()
                self.link = None
                # Calibration commands must never replay after a reconnect.
                while not self.commands.empty():
                    self.commands.get_nowait()
            if self.stop.is_set() or not self.reconnect:
                break
            attempts += 1
            delay = min(10, 2 * attempts)
            self.events.put(('status', f'Bağlantı yok • {delay} saniye sonra yeniden deneniyor'))
            self.stop.wait(delay)
        self.events.put(('done', None))

    def listen(self, link, mavutil):
        m = mavutil.mavlink
        deadline = time.monotonic() + 12
        hb = None
        while not self.stop.is_set() and time.monotonic() < deadline:
            link.mav.heartbeat_send(m.MAV_TYPE_GCS, m.MAV_AUTOPILOT_INVALID, 0, 0, 0)
            candidate = link.recv_match(type='HEARTBEAT', blocking=True, timeout=.5)
            if candidate and candidate.autopilot != m.MAV_AUTOPILOT_INVALID:
                identity = (candidate.get_srcSystem(), candidate.get_srcComponent())
                if self.identity is None or identity == self.identity:
                    hb = candidate
                    break
        if self.stop.is_set():
            return
        if hb is None:
            raise TimeoutError('12 saniye içinde araç yaşam sinyali alınamadı.')
        self.identity = (hb.get_srcSystem(), hb.get_srcComponent())
        system, component = self.identity
        link.mav.request_data_stream_send(system, component, m.MAV_DATA_STREAM_ALL, 2, 1)
        self.events.put(('online', f'Bağlı • Araç {system} • {self.address}'))
        last_hb = last_sent = time.monotonic()
        armed = bool(hb.base_mode & 128)
        self.events.put(('message', hb))
        pending = None
        pending_mode = None
        pending_current = None
        state=PositionState();state.ingest(hb)
        parameters={};parameter_pending=None
        list_started=None;list_count=0;list_indices=set();list_retry=0
        position = None
        active = False
        active_servo=None
        while not self.stop.is_set():
            now = time.monotonic()
            if now - last_hb > 6:
                raise TimeoutError('Yaşam sinyali kesildi. Son konum güncel değildir.')
            if now - last_sent >= 1:
                link.mav.heartbeat_send(m.MAV_TYPE_GCS, m.MAV_AUTOPILOT_INVALID, 0, 0, 0)
                last_sent = now
            if pending and now - pending[1] > 15:
                self.events.put(('cal', 'Komut yanıtı alınamadı. Sonuç bilinmiyor; kart mesajlarını kontrol edin.'))
                pending = None
            if pending_mode and now - pending_mode[2] > 8:
                self.events.put(('control', f'{pending_mode[0]} modu kart yaşam sinyalinde doğrulanamadı.'))
                pending_mode = None
            if pending_current and now-pending_current[1]>8:
                self.events.put(('control',f'Görev adımı {pending_current[0]} karttan doğrulanamadı.'))
                pending_current=None
            if parameter_pending and now-parameter_pending[2]>6:
                self.events.put(('param_result',(parameter_pending[0],False,'Karttan doğrulama gelmedi')))
                parameter_pending=None
            if active_servo and now>=active_servo[2]:
                channel,neutral,_=active_servo
                link.mav.command_long_send(system,component,getattr(m,'MAV_CMD_DO_SET_SERVO',183),0,channel,neutral,0,0,0,0,0)
                active_servo=None;self.events.put(('ground','Servo güvenli nötr değere döndürüldü.'))
            if list_started is not None:
                if list_count and len(list_indices)==list_count:
                    self.events.put(('control',f'Parametre listesi tamamlandı: {list_count} kayıt.'));list_started=None
                elif now-list_started>45:
                    self.events.put(('control',f'Parametre listesi eksik: {len(list_indices)}/{list_count}. Yeniden oku ile tamamlayın.'));list_started=None
                elif now-list_retry>2 and list_count:
                    missing=[i for i in range(list_count) if i not in list_indices][:8]
                    for i in missing:link.mav.param_request_read_send(system,component,b'',i)
                    list_retry=now
            try:
                action = self.commands.get_nowait()
            except queue.Empty:
                action = None
            if action:
                if isinstance(action,tuple) and action and action[0]=='param_list':
                    parameters.clear();link.mav.param_request_list_send(system,component)
                    list_started=now;list_count=0;list_indices.clear();list_retry=now
                    self.events.put(('control','Tüm parametreler isteniyor; eksik liste tamamlandı sayılmaz.'))
                elif isinstance(action,tuple) and action and action[0]=='mission':
                    operation=action[1]
                    command=m.MAV_CMD_MISSION_START if operation=='start' else getattr(m,'MAV_CMD_DO_PAUSE_CONTINUE',193) if operation in ('pause','resume') else m.MAV_CMD_DO_SET_MODE
                    mapping=mavutil.mode_mapping_byname(hb.type) or {}
                    requires_mission=operation in ('start','resume','jump')
                    if now-last_hb>2 or hb.autopilot != m.MAV_AUTOPILOT_ARDUPILOTMEGA or (requires_mission and not SafetyGate(state).allow('mission',now)):
                        self.events.put(('control',SafetyGate(state).summary(now,'mission') if requires_mission else 'Görev kontrolü bağlantı koşullarını sağlamadı.'))
                    elif operation=='start':
                        if pending or pending_mode:
                            self.events.put(('control','Önceki komut yanıtı bekleniyor.'));continue
                        link.mav.command_long_send(system,component,command,0,0,0,0,0,0,0,0)
                        pending=(command,now)
                        self.events.put(('control','Görev başlatma komutu gönderildi.'))
                    elif operation in ('pause','resume'):
                        if pending or pending_mode:
                            self.events.put(('control','Önceki komut yanıtı bekleniyor.'));continue
                        link.mav.command_long_send(system,component,command,0,0 if operation=='pause' else 1,0,0,0,0,0,0)
                        pending=(command,now)
                        self.events.put(('control',('Görev duraklatma' if operation=='pause' else 'Göreve devam')+' komutu gönderildi.'))
                    elif operation=='jump':
                        try:seq=int(action[2])
                        except (TypeError,ValueError):seq=-1
                        if not 0<=seq<=65535:self.events.put(('control','Görev adımı 0–65535 arasında olmalı.'))
                        else:
                            link.mav.mission_set_current_send(system,component,seq)
                            pending_current=(seq,now)
                            self.events.put(('control',f'Görev adımı {seq} istendi; kart geri bildirimi bekleniyor.'))
                    elif 'LOITER' in mapping:
                        link.mav.set_mode_send(system,m.MAV_MODE_FLAG_CUSTOM_MODE_ENABLED,mapping['LOITER'])
                        self.events.put(('control','LOITER ile görev durdurma komutu gönderildi.'))
                    else:self.events.put(('control','Bu araç türünde LOITER modu bulunamadı.'))
                elif isinstance(action,tuple) and action and action[0]=='manual_control':
                    try:
                        x,y,z,r=(int(v) for v in action[1:5])
                        if now-last_hb>2 or hb.autopilot != m.MAV_AUTOPILOT_ARDUPILOTMEGA or not armed:
                            raise ValueError('Doğrudan kontrol için güncel, ARMED ArduPilot bağlantısı gerekir.')
                        if not all(-1000<=v<=1000 or v==32767 for v in (x,y,z,r)):
                            raise ValueError('Doğrudan kontrol eksen değeri geçersiz.')
                        link.mav.manual_control_send(system,x,y,z,r,0)
                    except (ValueError,TypeError) as exc:self.events.put(('control',str(exc)))
                elif isinstance(action,tuple) and action and action[0]=='param_read':
                    for name in action[1]:link.mav.param_request_read_send(system,component,str(name).encode('ascii'),-1)
                    self.events.put(('control','Failsafe parametreleri isteniyor…'))
                elif isinstance(action,tuple) and action and action[0]=='param_set':
                    name=action[1]
                    try:
                        if armed or now-last_hb>2 or hb.autopilot!=3:raise ValueError('Yazma için güncel DISARMED ArduPilot bağlantısı gerekli.')
                        if parameter_pending:raise ValueError('Önceki parametre doğrulaması bekleniyor.')
                        if name not in parameters:raise ValueError('Parametre önce bu bağlantıda karttan okunmalı.')
                        value=checked_value(action[2],parameters[name][1])
                        validate_safety_parameter(name,value)
                        link.mav.param_set_send(system,component,name.encode('ascii'),value,parameters[name][1])
                        parameter_pending=(name,value,now)
                        self.events.put(('control',f'{name} gönderildi; kart değeri bekleniyor.'))
                    except (ValueError,TypeError) as exc:self.events.put(('param_result',(name,False,str(exc))))
                elif isinstance(action,tuple) and action and action[0]=='mode':
                    requested=str(action[1]).upper()
                    mapping=mavutil.mode_mapping_byname(hb.type) or {}
                    if requested not in mapping:self.events.put(('control',f'Uçuş modu desteklenmiyor: {requested}'))
                    elif now-last_hb>2 or hb.autopilot != m.MAV_AUTOPILOT_ARDUPILOTMEGA:self.events.put(('control','Uçuş modu isteği güvenlik koşullarını sağlamadı.'))
                    elif SafetyGate.action_for_mode(requested)!='basic_mode' and not SafetyGate(state).allow(SafetyGate.action_for_mode(requested),now):
                        self.events.put(('control',SafetyGate(state).summary(now,SafetyGate.action_for_mode(requested))))
                    elif pending or pending_mode:self.events.put(('control','Önceki komutun yanıtı bekleniyor.'))
                    else:
                        link.mav.set_mode_send(system,m.MAV_MODE_FLAG_CUSTOM_MODE_ENABLED,mapping[requested])
                        pending_mode=(requested,mapping[requested],now)
                        self.events.put(('control',f'{requested} modu gönderildi; kart doğrulaması bekleniyor.'))
                elif isinstance(action,tuple) and action and action[0]=='arm':
                    if now-last_hb>2 or hb.autopilot != m.MAV_AUTOPILOT_ARDUPILOTMEGA or (action[1] and not SafetyGate(state).allow('arm',now)):
                        self.events.put(('control',SafetyGate(state).summary(now,'arm')))
                    elif pending or pending_mode:
                        self.events.put(('control','Önceki komutun yanıtı bekleniyor.'))
                    else:
                        link.mav.command_long_send(system,component,m.MAV_CMD_COMPONENT_ARM_DISARM,0,1 if action[1] else 0,0,0,0,0,0,0)
                        pending=(m.MAV_CMD_COMPONENT_ARM_DISARM,now)
                        self.events.put(('control',('ARM' if action[1] else 'DISARM')+' komutu gönderildi; kart yanıtı bekleniyor.'))
                elif isinstance(action,tuple) and action and action[0]=='motor_test':
                    try:
                        motor,percent,seconds=int(action[1]),float(action[2]),float(action[3])
                        if not self.calibration or armed or now-last_hb>2 or hb.autopilot!=m.MAV_AUTOPILOT_ARDUPILOTMEGA:raise ValueError('Motor testi için USB yer kurulumu, güncel DISARMED ArduPilot gerekir.')
                        if not 1<=motor<=12 or not 1<=percent<=30 or not .5<=seconds<=5:raise ValueError('Motor 1–12, gaz %1–30 ve süre 0,5–5 sn olmalı.')
                        command=getattr(m,'MAV_CMD_DO_MOTOR_TEST',209)
                        link.mav.command_long_send(system,component,command,0,motor,0,percent,seconds,0,0,0)
                        pending=(command,now);self.events.put(('ground',f'Motor {motor} testi: %{percent:g}, {seconds:g} sn • ACK bekleniyor.'))
                    except (ValueError,TypeError) as exc:self.events.put(('ground',str(exc)))
                elif isinstance(action,tuple) and action and action[0]=='servo_test':
                    try:
                        channel,pwm,seconds,neutral=int(action[1]),int(action[2]),float(action[3]),int(action[4])
                        if not self.calibration or armed or now-last_hb>2 or hb.autopilot!=m.MAV_AUTOPILOT_ARDUPILOTMEGA:raise ValueError('Servo testi için USB yer kurulumu, güncel DISARMED ArduPilot gerekir.')
                        if not 1<=channel<=16 or not 1000<=pwm<=2000 or not .5<=seconds<=3 or not 1000<=neutral<=2000:raise ValueError('Servo 1–16, PWM/nötr 1000–2000 ve süre 0,5–3 sn olmalı.')
                        command=getattr(m,'MAV_CMD_DO_SET_SERVO',183)
                        link.mav.command_long_send(system,component,command,0,channel,pwm,0,0,0,0,0)
                        active_servo=(channel,neutral,now+seconds);pending=(command,now)
                        self.events.put(('ground',f'Servo {channel}: {pwm} µs, {seconds:g} sn; sonra {neutral} µs nötr.'))
                    except (ValueError,TypeError) as exc:self.events.put(('ground',str(exc)))
                elif isinstance(action,tuple) and action and action[0]=='output_stop':
                    if active_servo:
                        channel,neutral,_=active_servo;link.mav.command_long_send(system,component,getattr(m,'MAV_CMD_DO_SET_SERVO',183),0,channel,neutral,0,0,0,0,0);active_servo=None
                    for motor in range(1,13):link.mav.command_long_send(system,component,getattr(m,'MAV_CMD_DO_MOTOR_TEST',209),0,motor,0,0,0,0,0,0)
                    self.events.put(('ground','ACİL DURDURMA • Motor testleri %0, aktif servo nötr.'))
                elif isinstance(action,tuple) and action and action[0]=='gimbal':
                    try:
                        pitch,yaw=float(action[1]),float(action[2])
                        if now-last_hb>2 or hb.autopilot!=m.MAV_AUTOPILOT_ARDUPILOTMEGA:raise ValueError('Gimbal için güncel ArduPilot bağlantısı gerekir.')
                        if not -90<=pitch<=30 or not -180<=yaw<=180:raise ValueError('Gimbal pitch -90…30, yaw -180…180 olmalı.')
                        command=getattr(m,'MAV_CMD_DO_MOUNT_CONTROL',205)
                        link.mav.command_long_send(system,component,command,0,pitch,0,yaw,0,0,0,2);pending=(command,now)
                        self.events.put(('control',f'Gimbal hedefi gönderildi: pitch {pitch:g}°, yaw {yaw:g}°.'))
                    except (ValueError,TypeError) as exc:self.events.put(('control',str(exc)))
                elif isinstance(action,tuple) and action and action[0]=='camera_trigger':
                    if now-last_hb>2 or hb.autopilot!=m.MAV_AUTOPILOT_ARDUPILOTMEGA:self.events.put(('control','Kamera tetikleme için güncel ArduPilot bağlantısı gerekir.'))
                    elif pending:self.events.put(('control','Önceki komutun yanıtı bekleniyor.'))
                    else:
                        command=getattr(m,'MAV_CMD_IMAGE_START_CAPTURE',2000)
                        link.mav.command_long_send(system,component,command,0,0,0,1,0,0,0,0);pending=(command,now)
                        self.events.put(('control','MAVLink tek fotoğraf tetikleme komutu gönderildi; kamera bileşeni onayı bekleniyor.'))
                elif not self.calibration or armed or now - last_hb > 2 or hb.autopilot != m.MAV_AUTOPILOT_ARDUPILOTMEGA:
                    self.events.put(('cal', 'Kalibrasyon için kablolu kurulum, güncel DISARMED durumu ve ArduPilot gerekir.'))
                elif pending:
                    self.events.put(('cal', 'Önceki komutun yanıtı bekleniyor.'))
                else:
                    params = [0] * 7
                    command = None
                    if action == 'accel' and not active:
                        command, params[4], active = 241, 1, True
                    elif action == 'gyro' and not active:
                        command, params[0] = 241, 1
                    elif action == 'level' and not active:
                        command, params[4] = 241, 2
                    elif action == 'compass' and not active:
                        command,params[1]=241,1
                    elif action == 'rc' and not active:
                        command,params[3]=241,1
                    elif action == 'airspeed' and not active:
                        command,params[5]=241,1
                    elif action == 'esc' and not active:
                        command,params[6]=241,1
                    elif action == 'position' and position in range(1, 7):
                        command, params[0] = 42429, position
                        position = None
                        self.events.put(('position', None))
                    if command:
                        link.mav.command_long_send(system, component, command, 0, *params)
                        pending = (command, now)
                        self.events.put(('cal', 'Komut gönderildi; kartın sonucu bekleniyor.'))
                    else:
                        self.events.put(('cal', 'Aktif kalibrasyon adımını tamamlayın; kart yeni yön isteyene kadar bekleyin.'))
            msg = link.recv_match(blocking=True, timeout=.2)
            if msg is None or (msg.get_srcSystem(), msg.get_srcComponent()) != self.identity:
                continue
            kind = msg.get_type()
            state.ingest(msg)
            if kind == 'HEARTBEAT':
                last_hb, hb, armed = time.monotonic(), msg, bool(msg.base_mode & 128)
                if pending_mode and int(msg.custom_mode)==pending_mode[1]:
                    self.events.put(('control',f'{pending_mode[0]} modu kart tarafından doğrulandı.'))
                    pending_mode=None
            elif kind == 'COMMAND_ACK' and pending and msg.command == pending[0]:
                result = msg.result
                label = {0: 'Kabul edildi', 1: 'Geçici olarak reddedildi', 2: 'Reddedildi', 3: 'Desteklenmiyor', 4: 'Başarısız', 5: 'İşlem sürüyor', 6: 'İptal edildi'}.get(result, f'Sonuç {result}')
                self.events.put(('cal', label + (' • Kartın yön talimatlarını izleyin.' if active and result in (0, 5) else '')))
                if result != 5:
                    pending = None
                else:
                    pending = (pending[0], time.monotonic())
                if result not in (0, 5):
                    active, position = False, None
                    self.events.put(('position', None))
            elif kind == 'PARAM_VALUE':
                name=msg.param_id.decode(errors='ignore').rstrip('\x00') if isinstance(msg.param_id,bytes) else str(msg.param_id).rstrip('\x00')
                parameters[name]=(float(msg.param_value),msg.param_type)
                if list_started is not None and 0<msg.param_count<=65535:
                    if list_count and list_count!=msg.param_count:list_indices.clear()
                    list_count=msg.param_count
                    if 0<=msg.param_index<list_count:list_indices.add(msg.param_index)
                self.events.put(('parameter',(name,float(msg.param_value),msg.param_type,msg.param_index,msg.param_count)))
                if parameter_pending and parameter_pending[0]==name:
                    ok=math.isclose(float(msg.param_value),parameter_pending[1],rel_tol=1e-6,abs_tol=1e-7)
                    self.events.put(('param_result',(name,ok,'Kart değeri doğrulandı' if ok else 'Kart farklı değer bildirdi')))
                    parameter_pending=None
                self.events.put(('param',(name,float(msg.param_value))))
            elif kind == 'MISSION_CURRENT' and pending_current:
                if int(msg.seq)==pending_current[0]:
                    self.events.put(('control',f'Görev adımı {msg.seq} kart tarafından doğrulandı.'))
                    pending_current=None
            elif kind == 'COMMAND_LONG' and msg.command == 42429 and active:
                if msg.target_system not in (0, 255) or msg.target_component not in (0, 190):
                    continue
                value = int(msg.param1)
                pending = None
                if value in range(1, 7):
                    position = value
                    self.events.put(('position', value))
                elif value in (16777215, 16777216):
                    active, position = False, None
                    self.events.put(('position', None))
                    self.events.put(('cal', 'İvmeölçer kalibrasyonu başarılı.' if value == 16777215 else 'İvmeölçer kalibrasyonu başarısız.'))
            self.events.put(('message', msg))
