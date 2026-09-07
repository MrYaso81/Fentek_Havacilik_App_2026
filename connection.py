"""Transport validation and reconnecting MAVLink session; no UI dependencies."""
import queue
import time

class PriorityCommands:
    """Emergency MAVLink actions bypass slow mission/parameter traffic."""
    def __init__(self): self._q=queue.PriorityQueue();self._seq=0
    def put(self,action):
        self._seq+=1; kind=action[0] if isinstance(action,tuple) and action else ''
        priority=0 if (kind=='mode' and str(action[1]).upper() in ('RTL','LAND','LOITER')) or kind=='arm' or (kind=='mission' and action[1]=='stop') else 10
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
        position = None
        active = False
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
            try:
                action = self.commands.get_nowait()
            except queue.Empty:
                action = None
            if action:
                if isinstance(action,tuple) and action and action[0]=='mission':
                    command=300 if action[1]=='start' else 176
                    if action[1]=='start' and (armed or hb.autopilot != m.MAV_AUTOPILOT_ARDUPILOTMEGA):
                        self.events.put(('control','Görev başlatma için ArduPilot ve güvenli durum gerekli.'))
                    else:
                        if command==300:link.mav.command_long_send(system,component,command,0,0,0,0,0,0,0,0)
                        else:link.mav.set_mode_send(system,m.MAV_MODE_FLAG_CUSTOM_MODE_ENABLED,(mavutil.mode_mapping_apm() or {}).get('LOITER',5))
                        self.events.put(('control','Görev başlatma/durdurma komutu gönderildi.'))
                elif isinstance(action,tuple) and action and action[0]=='param_read':
                    for name in action[1]:link.mav.param_request_read_send(system,component,str(name).encode('ascii'),-1)
                    self.events.put(('control','Failsafe parametreleri isteniyor…'))
                elif isinstance(action,tuple) and action and action[0]=='param_set':
                    name,value=action[1],float(action[2])
                    if name not in ('FS_GCS_ENABLE','FS_GCS_TIMEOUT','FS_THR_ENABLE','FS_EKF_ACTION','FS_BATT_ENABLE'):
                        self.events.put(('param_error','Parametre güvenlik listesinde değil.'))
                    else:
                        link.mav.param_set_send(system,component,str(name).encode('ascii'),value,9)
                        self.events.put(('control',f'{name} yazılıyor; kart doğrulaması bekleniyor…'))
                elif isinstance(action,tuple) and action and action[0]=='mode':
                    requested=str(action[1]).upper()
                    mapping=mavutil.mode_mapping_apm() or {}
                    if requested not in mapping:self.events.put(('control',f'Uçuş modu desteklenmiyor: {requested}'))
                    elif now-last_hb>2 or hb.autopilot != m.MAV_AUTOPILOT_ARDUPILOTMEGA:self.events.put(('control','Uçuş modu isteği güvenlik koşullarını sağlamadı.'))
                    elif pending:self.events.put(('control','Önceki komutun yanıtı bekleniyor.'))
                    else:
                        link.mav.set_mode_send(system,m.MAV_MODE_FLAG_CUSTOM_MODE_ENABLED,mapping[requested])
                        pending=(m.MAV_CMD_DO_SET_MODE,now)
                        self.events.put(('control',f'{requested} modu gönderildi; kart doğrulaması bekleniyor.'))
                elif isinstance(action,tuple) and action and action[0]=='arm':
                    if now-last_hb>2 or hb.autopilot != m.MAV_AUTOPILOT_ARDUPILOTMEGA or (action[1] and armed):
                        self.events.put(('control','ARM isteği güvenlik koşullarını sağlamadı.'))
                    elif pending:
                        self.events.put(('control','Önceki komutun yanıtı bekleniyor.'))
                    else:
                        link.mav.command_long_send(system,component,m.MAV_CMD_COMPONENT_ARM_DISARM,0,1 if action[1] else 0,0,0,0,0,0,0)
                        pending=(m.MAV_CMD_COMPONENT_ARM_DISARM,now)
                        self.events.put(('control',('ARM' if action[1] else 'DISARM')+' komutu gönderildi; kart yanıtı bekleniyor.'))
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
            if kind == 'HEARTBEAT':
                last_hb, hb, armed = time.monotonic(), msg, bool(msg.base_mode & 128)
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
                self.events.put(('param',(name,float(msg.param_value))))
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
