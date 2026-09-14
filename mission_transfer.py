"""ArduPilot mission upload with bounded retries and full read-back verification."""
import math
import time

MAX_MAVLINK_MISSION_ITEMS=65535


def validate_points(points):
    if not points:raise ValueError('En az 1 görev noktası gerekli.')
    if len(points)>MAX_MAVLINK_MISSION_ITEMS-2:
        raise ValueError('Nokta sayısı MAVLink görev protokolünün kapasitesini aşıyor.')
    result=[]
    for lat,lon,alt in points:
        if not all(math.isfinite(v) for v in (lat,lon,alt)) or not (-90<=lat<=90 and -180<=lon<=180 and 0<alt<=10000):
            raise ValueError('Koordinatlar geçerli, irtifalar 0–10000 m arasında olmalı (0 hariç).')
        result.append((round(lat*1e7),round(lon*1e7),float(alt)))
    return result


def validate_servo_actions(actions, waypoint_count):
    checked=[]
    for waypoint,channel,pwm in actions:
        if not isinstance(waypoint,int) or not 1<=waypoint<=waypoint_count:
            raise ValueError('Servo komutu geçerli bir rota noktasına bağlı olmalı.')
        if not isinstance(channel,int) or not 1<=channel<=16:
            raise ValueError('Servo kanalı 1–16 arasında olmalı.')
        if not isinstance(pwm,(int,float)) or not math.isfinite(pwm) or not 1000<=pwm<=2000:
            raise ValueError('Servo PWM değeri 1000–2000 arasında olmalı.')
        checked.append((waypoint,channel,int(pwm)))
    return checked


class Transfer:
    def __init__(self,link,system,stop,report):
        self.link,self.system,self.stop,self.report=link,system,stop,report
        self.component=1
        self.last_hb=0
        self.last_sent=0

    def receive(self,kinds,timeout=3):
        deadline=time.monotonic()+timeout
        while time.monotonic()<deadline:
            if self.stop.is_set():raise RuntimeError('İşlem iptal edildi; karttaki görevin durumu doğrulanmadı.')
            now=time.monotonic()
            if self.last_hb and now-self.last_hb>5:raise RuntimeError('Araç yaşam sinyali kesildi; görev doğrulanmadı.')
            if now-self.last_sent>=1:
                self.link.mav.heartbeat_send(6,8,0,0,0)
                self.last_sent=now
            msg=self.link.recv_match(blocking=True,timeout=.2)
            if msg is None:continue
            if (msg.get_srcSystem(),msg.get_srcComponent())!=(self.system,self.component):continue
            kind=msg.get_type()
            if kind=='HEARTBEAT':
                if msg.autopilot!=3:raise RuntimeError('Hedef ArduPilot değil.')
                if msg.base_mode & 128:raise RuntimeError('Kart ARMED; görev aktarımı durduruldu.')
                self.last_hb=now
            if self.last_hb and now-self.last_hb>5:raise RuntimeError('Araç yaşam sinyali kesildi.')
            if kind in kinds:
                if getattr(msg,'mission_type',0)!=0:continue
                if getattr(msg,'target_system',255) not in (0,255):continue
                if getattr(msg,'target_component',190) not in (0,190):continue
                return msg
        return None

    def request(self,send,kinds):
        for _ in range(3):
            send()
            msg=self.receive(kinds)
            if msg is not None:return msg
        raise TimeoutError('Kart yanıt vermedi; görev doğrulanmadı. Bağlantıyı kontrol edin.')

    def run(self,points,servo_actions=()):
        points=validate_points(points)
        servo_actions=validate_servo_actions(servo_actions,len(points))
        hb=self.receive({'HEARTBEAT'},12)
        if hb is None:raise TimeoutError('Seçilen araçtan DISARMED ArduPilot yaşam sinyali alınamadı.')
        s,c=self.system,self.component
        self.report(f'ArduPilot araç {s}/{c} bağlı, DISARMED. HOME konumu okunuyor…')
        home=self.request(lambda:self.link.mav.command_long_send(s,c,512,0,242,0,0,0,0,0,0),{'HOME_POSITION'})
        # ArduPilot sequence zero is the home entry, not the first flown waypoint.
        # (command, frame, x, y, z, param1, param2, param3, param4)
        items=[(16,0,home.latitude,home.longitude,home.altitude/1000,0,0,0,0)]
        for index,(lat,lon,alt) in enumerate(points,1):
            items.append((16,3,lat,lon,alt,0,0,0,0))
            # DO commands execute immediately after their preceding waypoint.
            for waypoint,channel,pwm in servo_actions:
                if waypoint==index:items.append((183,2,0,0,0,channel,pwm,0,0))
        items += [(20,3,0,0,0,0,0,0,0)] # explicit RTL end command
        if len(items)>MAX_MAVLINK_MISSION_ITEMS:
            raise ValueError('Nokta ve servo komutları MAVLink görev kapasitesini aşıyor.')
        self.report(f'Görev yükleniyor: {len(points)} nokta, {len(servo_actions)} servo komutu + eve dönüş. Uçuş başlatılmayacak.')
        send=lambda:self.link.mav.mission_count_send(s,c,len(items))
        send()
        sent=set()
        retries=0
        deadline=time.monotonic()+90
        while time.monotonic()<deadline:
            msg=self.receive({'MISSION_REQUEST_INT','MISSION_REQUEST','MISSION_ACK'})
            if msg is None:
                retries+=1
                if retries>3:raise TimeoutError('Yükleme yanıtı alınamadı; görev durumu bilinmiyor.')
                send();continue
            if msg.get_type()=='MISSION_ACK':
                if msg.type!=0:raise RuntimeError(f'Kart görevi reddetti (MAVLink sonuç {msg.type}).')
                if len(sent)!=len(items):raise RuntimeError('Eksik görev onayı; doğrulanmadı.')
                break
            seq=msg.seq
            if not 0<=seq<len(items):raise RuntimeError('Kart geçersiz görev sırası istedi.')
            command,frame,lat,lon,alt,p1,p2,p3,p4=items[seq]
            send=lambda seq=seq,command=command,frame=frame,lat=lat,lon=lon,alt=alt,p1=p1,p2=p2,p3=p3,p4=p4:self.link.mav.mission_item_int_send(s,c,seq,frame,command,0,1,p1,p2,p3,p4,lat,lon,alt)
            send();sent.add(seq);retries=0
        else:raise TimeoutError('Görev yükleme zaman aşımı; sonuç doğrulanmadı.')
        self.report('Kart kabul etti. Görev geri okunup karşılaştırılıyor…')
        count=self.request(lambda:self.link.mav.mission_request_list_send(s,c),{'MISSION_COUNT'})
        if count.count!=len(items):raise RuntimeError('Karttaki görev sayısı farklı.')
        for seq,expected in enumerate(items):
            msg=self.request(lambda seq=seq:self.link.mav.mission_request_int_send(s,c,seq),{'MISSION_ITEM_INT'})
            command,frame,lat,lon,alt,p1,p2,p3,p4=expected
            if msg.seq!=seq or msg.command!=command:raise RuntimeError('Görev sırası/komutu doğrulanamadı.')
            if seq and command==16:
                if msg.frame not in (3,6) or abs(msg.x-lat)>1 or abs(msg.y-lon)>1 or abs(msg.z-alt)>.05 or msg.autocontinue!=1:
                    raise RuntimeError(f'{seq}. noktanın koordinatı/irtifası farklı.')
                if any(abs(getattr(msg,f'param{i}'))>.001 for i in (1,2,3,4)):
                    raise RuntimeError(f'{seq}. noktanın parametreleri farklı.')
            elif command==183:
                if msg.frame!=2 or any(abs(getattr(msg,f'param{i}')-v)>.001 for i,v in enumerate((p1,p2,p3,p4),1)):
                    raise RuntimeError(f'{seq}. servo komutu farklı.')
        self.link.mav.mission_ack_send(s,c,0)
        self.report('DOĞRULANDI: Görev karta yüklendi ve geri okundu. Uçuş başlatılmadı.')
