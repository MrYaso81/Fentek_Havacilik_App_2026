"""Lightweight RAG knowledge and deterministic UAV performance estimates.

This adapts the chunk/retrieve idea from the user supplied
``iha_rag_asistan.py`` without downloading a large embedding model.  Numeric
results are calculated here rather than guessed by a language model.
"""
from __future__ import annotations

from dataclasses import dataclass, fields
import math
import re
from pathlib import Path
from turkish_language import semantic_normalize


DOCUMENTS = (
    ("Ağırlık ve itki oranı",
     "Çok rotorlu bir İHA için azami toplam statik itki, motor sayısı ile aynı motor-pervane-batarya kombinasyonunun motor başına ölçülmüş itkisi çarpılarak bulunur. İtki/ağırlık oranı toplam itki bölü kalkış ağırlığıdır. Oran 1 veya altındaysa teorik olarak askıda kalma payı yoktur. Güvenli tasarım hedefi; araç türü, irtifa, sıcaklık, görev ve kontrol ihtiyacına göre doğrulanmalıdır. Katalog verisi yerine aynı gerilim ve pervanedeki test verisi kullanılmalıdır."),
    ("Uçuş süresi",
     "Yaklaşık uçuş süresi dakika olarak batarya kapasitesi Ah çarpı kullanılabilir oran çarpı 60 bölü ortalama toplam akımdır. Örnek hesaplarda kullanılabilir oran 0,80 alınabilir; bu garanti değildir. Kalkış, rüzgâr, manevra, batarya yaşı, sıcaklık ve voltaj çökmesi süreyi değiştirir. Ortalama akım bilinmeden yalnız mAh ile süre hesaplanamaz."),
    ("Batarya enerjisi ve ağırlığı",
     "Bataryanın yaklaşık nominal enerjisi Wh = nominal voltaj V × kapasite Ah formülüyle bulunur. Daha büyük batarya enerji taşır ama ağırlığı artırır; gereken askıda kalma itkisi ve akımı da yükseltebilir. Bu nedenle kapasite artışı uçuş süresini aynı oranda artırmayabilir. Gerçek karşılaştırma iki batarya ile ölçülen toplam kalkış ağırlığı ve ortalama akımla yapılır."),
    ("Motor KV ve pervane",
     "KV değeri yüksüz devir/volt ilişkisini belirtir; tek başına itki, güç veya taşıma kapasitesi değildir. Motor, ESC, pervane çapı/adımı ve hücre sayısı birlikte değerlendirilir. Üreticinin test tablosundan aynı pervane ve gerilimde itki, akım ve güç okunmalı; ESC ve motor sürekli akım sınırları aşılmamalıdır."),
    ("ESC payı",
     "ESC sürekli akım değeri, seçilen motor-pervane-batarya kombinasyonunun ölçülmüş azami akımından uygun payla yüksek olmalıdır. 35 A etiketi her koşulda 35 A sürekli taşıma garantisi değildir; soğutma, kart üretici sınırları ve anlık akım ayrıca kontrol edilir. Toplam batarya akımı yaklaşık olarak motor akımları ile yardımcı sistemlerin toplamıdır."),
    ("Sabit kanat yüklemesi",
     "Sabit kanatta kanat yüklemesi toplam kütlenin kanat alanına oranıdır ve g/dm² olarak ifade edilebilir. Ağırlık artınca stall hızı yaklaşık olarak ağırlık oranının kareköküyle artar; kesin sonuç için kanat alanı, kaldırma katsayısı ve hava yoğunluğu gerekir. Çok rotorlu itki/ağırlık hesabı sabit kanadın uçuş performansını tek başına açıklamaz."),
    ("Ağırlık bütçesi",
     "Kalkış ağırlığı; gövde, motorlar, ESC, pervaneler, uçuş kontrolcüsü, GPS, telemetri, alıcı, kablolar, iniş takımı, batarya ve faydalı yükün uçuşa hazır toplamıdır. En doğru değer tamamlanmış aracı hassas terazide ölçmektir. Hedef gram değeri görev, süre, taşıma kapasitesi ve seçilen tahrik sistemi bilinmeden belirlenemez."),
    ("Ölçüm ve belirsizlik",
     "Tahmini hesaplar uçuş testi değildir. İtki standı, wattmetre, terazi ve güvenli yer testiyle akım, itki ve sıcaklık doğrulanır. Üretici verisinin koşulları kaydedilir. Pervaneler takılı motor testi insanlardan uzakta ve uygun test düzeneğinde yapılır; yazılım tahmini fiziksel güvenlik kontrolünün yerine geçmez."),
    ("Çok rotorlu temel sistem",
     "Çok rotorlu bir araçta uçuşa hazır temel zincir gövde, uygun sayıda motor, ESC veya 4-in-1 ESC, doğru yön ve ölçüde pervaneler, uçuş kontrolcüsü, RC alıcı-kumanda, uçuş bataryası, güç dağıtımı, kablo-konektörler ve sağlam montaj elemanlarından oluşur. GPS/pusula konum tutma ve otonom modlar için; telemetri yer istasyonu bağlantısı için eklenir."),
    ("Sabit kanat temel sistem",
     "Sabit kanatta gövde ve kanatlara ek olarak motor-ESC-pervane, aileron/elevator/rudder için gereken servolar, kontrol kolları, pushrod ve menteşeler, uçuş kontrolcüsü, RC sistemi, batarya ve güç dağıtımı gerekir. Airspeed sensörü her araçta zorunlu değildir fakat bazı görev ve kontrol ayarlarında yararlıdır. Ağırlık merkezi ve kontrol yüzeyi yönleri yerde doğrulanır."),
    ("FPV görüntü zinciri",
     "FPV görüntüsü için kamera, video verici, uygun anten, yer tarafında uyumlu alıcı/gözlük veya ekran ve temiz bir güç kaynağı gerekir. Video frekansı, kanal, konektör ve anten tipi eşleşmelidir. Video bağlantısı RC kontrol ve MAVLink telemetrisinden ayrı bir sistem olabilir; görüntü gelmesi uçuş kontrol bağlantısının çalıştığını kanıtlamaz."),
    ("Cube Orange ve Here3 çevre birimleri",
     "Cube Orange taşıyıcı kart, uygun güç modülü, RC alıcı, motor/servo çıkış bağlantıları ve araç tipine göre ESC/servolarla çalışır. Here3 genellikle CAN üzerinden GPS ve pusula sağlar. Uzaktan yer istasyonu için Cube TELEM portuna hava telemetri modülü, bilgisayara eşlenmiş yer modülü bağlanır. USB ilk kurulum ve kalibrasyonda kullanılabilir."),
    ("Elektriksel uyumluluk",
     "Donanım uyumluluğu için batarya hücre sayısı ve tam dolu voltajı; motor ve ESC gerilim sınırları; motor-pervane testindeki azami akım; ESC sürekli/anlık akımı; batarya C değeri; konektör ve kablo akımı; BEC çıkış voltajı/akımı; sinyal mantık seviyesi ve port protokolü birlikte kontrol edilir. Yalnız konektörün fiziksel olarak uyması elektriksel uyumluluk anlamına gelmez."),
    ("Uçuş öncesi sistem tamamlama",
     "Parçalar tamamlandıktan sonra mekanik sıkılık, pervane yönü, motor sırası ve dönüş yönü, uçuş kontrolcüsü yönü, ivmeölçer ve pusula kalibrasyonu, RC kanal/yön/failsafe, batarya monitörü, GPS 3D fix, EKF, HOME, uçuş modları, sanal çit ve dönüş davranışı kontrol edilir. İlk motor denemeleri pervanesiz yapılır. Yazılım listesi fiziksel muayenenin ve kontrollü test planının yerine geçmez."),
    ("Faydalı yük ve ek donanım",
     "Kamera, gimbal, sensör, bırakma mekanizması veya başka faydalı yük toplam ağırlığı, ağırlık merkezini, güç tüketimini, titreşimi ve uçuş süresini etkiler. Yükün yalnız gramı değil konumu ve besleme ihtiyacı da değerlendirilir. Servo veya bırakma mekanizmasında çıkış akımı ve ayrı BEC gereksinimi kontrol edilir."),
)


def _normalize(text):
    text=str(text).lower().translate(str.maketrans('çğıöşü','cgiosu'))
    text=re.sub(r'[^a-z0-9.,/²]+',' ',text).strip()
    aliases={'toplm':'toplam','agrlik':'agirlik','agirli':'agirlik','motorlar':'motor',
             'motro':'motor','itkii':'itki','batrya':'batarya','baterya':'batarya',
             'ortalma':'ortalama','akm':'akim','performasn':'performans','ucsu':'ucus'}
    for wrong,right in aliases.items():text=re.sub(rf'\b{re.escape(wrong)}\b',right,text)
    return semantic_normalize(text)


def chunk_text(text,chunk_size=600,overlap=80):
    """Chunk text with the same 600/80 strategy as iha_rag_asistan.py."""
    chunks=[];start=0;step=max(1,chunk_size-overlap)
    while start<len(text):
        value=text[start:start+chunk_size].strip()
        if value:chunks.append(value)
        start+=step
    return chunks


class LightweightRAG:
    """Small lexical retriever; no model download, database, or background RAM."""
    def __init__(self,documents=DOCUMENTS,document_folder=None):
        loaded=list(documents)
        folder=Path(document_folder) if document_folder else Path(__file__).resolve().parent.parent/'belgeler'
        if folder.is_dir():
            for path in sorted(folder.glob('*.txt')):
                try:text=path.read_text(encoding='utf-8')
                except (OSError,UnicodeError):continue
                for index,part in enumerate(chunk_text(text)):
                    loaded.append((f'{path.name} • parça {index+1}',part))
        self.documents=tuple(loaded)
        self.index=[]
        for title,body in self.documents:
            tokens=set(_normalize(title+' '+body).split())
            self.index.append(tokens)

    def retrieve(self,question,k=3):
        query=set(_normalize(question).split())
        if not query:return ''
        scored=[]
        for (title,body),tokens in zip(self.documents,self.index):
            shared=query & tokens
            score=sum(2.2 if len(word)>=6 else 1.0 for word in shared)
            if _normalize(title) in _normalize(question):score+=6
            if score>=2.2:scored.append((score,title,body))
        scored.sort(reverse=True)
        return '\n\n'.join(f'[Yerel kaynak: {title}]\n{body}' for _,title,body in scored[:k])


@dataclass
class HardwareProfile:
    weight_g: float | None = None
    motor_count: int | None = None
    thrust_per_motor_g: float | None = None
    battery_mah: float | None = None
    average_current_a: float | None = None
    voltage_v: float | None = None
    wing_area_dm2: float | None = None

    def update(self,values):
        for item in fields(self):
            value=values.get(item.name)
            if value is not None:setattr(self,item.name,value)


def _number(value):
    return float(value.replace(',','.'))


def parse_specs(text):
    q=_normalize(text);result={}
    def match(pattern):
        found=re.search(pattern,q)
        return found.groups() if found else None
    value=match(r'(?:toplam agirlik|kalkis agirligi|iha agirligi|agirlik)\s*(?:[:=]|yaklasik)?\s*(\d+(?:[.,]\d+)?)\s*(kg|g)\b')
    if value:result['weight_g']=_number(value[0])*(1000 if value[1]=='kg' else 1)
    value=match(r'\b(\d{1,2})\s*(?:adet\s*)?motor\b')
    if value:result['motor_count']=int(value[0])
    value=match(r'(?:motor basina\s*)?(?:azami\s*)?(?:itki|motor itkisi)\s*(?:[:=]|yaklasik)?\s*(\d+(?:[.,]\d+)?)\s*(kgf|kg|g)\b')
    if value:result['thrust_per_motor_g']=_number(value[0])*(1000 if value[1] in ('kg','kgf') else 1)
    value=match(r'(?:batarya|kapasite)\s*(?:[:=])?\s*(\d+(?:[.,]\d+)?)\s*mah\b')
    if value:result['battery_mah']=_number(value[0])
    value=match(r'(?:ortalama|hover|seyir)\s*(?:toplam\s*)?akim\s*(?:[:=])?\s*(\d+(?:[.,]\d+)?)\s*a\b')
    if value:result['average_current_a']=_number(value[0])
    value=match(r'(?:nominal\s*)?(?:voltaj|gerilim)\s*(?:[:=])?\s*(\d+(?:[.,]\d+)?)\s*v\b')
    if value:result['voltage_v']=_number(value[0])
    value=match(r'kanat alani\s*(?:[:=])?\s*(\d+(?:[.,]\d+)?)\s*(dm2|dm²|m2|m²)\b')
    if value:result['wing_area_dm2']=_number(value[0])*(100 if value[1].startswith('m') else 1)
    return result


def is_performance_question(text):
    q=_normalize(text)
    keys=('kac gram','agirlik','itki','performans','ucus suresi','havada kal','motor kv','motor sec','pervane sec','kanat yuk','mah','kalkis kutlesi','tasir mi')
    return any(key in q for key in keys)


def performance_report(profile,aircraft='Döner kanat'):
    lines=[];calculated=False
    if profile.weight_g and profile.motor_count and profile.thrust_per_motor_g:
        total=profile.motor_count*profile.thrust_per_motor_g
        ratio=total/profile.weight_g
        hover_each=profile.weight_g/profile.motor_count
        load=100*hover_each/profile.thrust_per_motor_g
        if ratio<=1:assessment='Teorik askıda kalma payı yok; bu kombinasyon uçuşa uygun görünmüyor.'
        elif ratio<1.5:assessment='İtki payı sınırlı; manevra, rüzgâr ve kontrol payı özellikle doğrulanmalı.'
        elif ratio<2:assessment='Orta düzey itki payı var; hedefe uygunluğu gerçek test verisi belirler.'
        else:assessment='Yüksek bir statik itki payı görünüyor; akım, yapı ve kontrol sınırları yine doğrulanmalı.'
        lines.extend((f'İtki/ağırlık hesabı: ({profile.motor_count} × {profile.thrust_per_motor_g:.0f} g) ÷ {profile.weight_g:.0f} g = {ratio:.2f}',
                      f'Toplam azami statik itki: {total:.0f} g • Motor başına askıda kalma yükü: {hover_each:.0f} g • Azami itkinin yaklaşık %{load:.0f}’i',assessment));calculated=True
    if profile.battery_mah and profile.average_current_a:
        minutes=(profile.battery_mah/1000)*.80/profile.average_current_a*60
        lines.append(f'Tahmini süre: ({profile.battery_mah/1000:.2f} Ah × 0,80 × 60) ÷ {profile.average_current_a:.1f} A = {minutes:.1f} dakika')
        lines.append('Bu, yazdığınız ortalama toplam akıma dayalı yaklaşık değerdir; güvenli kullanılabilir uçuş süresi olarak kabul edilmemelidir.');calculated=True
    if profile.battery_mah and profile.voltage_v:
        wh=profile.battery_mah/1000*profile.voltage_v
        lines.append(f'Nominal batarya enerjisi: {profile.voltage_v:.2f} V × {profile.battery_mah/1000:.2f} Ah = {wh:.1f} Wh');calculated=True
    if aircraft=='Sabit kanat' and profile.weight_g and profile.wing_area_dm2:
        loading=profile.weight_g/profile.wing_area_dm2
        lines.append(f'Kanat yüklemesi: {profile.weight_g:.0f} g ÷ {profile.wing_area_dm2:.1f} dm² = {loading:.1f} g/dm²');calculated=True
    missing=[]
    if not (profile.weight_g and profile.motor_count and profile.thrust_per_motor_g):missing.append('itki oranı için toplam ağırlık + motor sayısı + motor başına ölçülmüş azami itki')
    if not (profile.battery_mah and profile.average_current_a):missing.append('süre için batarya mAh + ortalama toplam akım A')
    if aircraft=='Sabit kanat' and not profile.wing_area_dm2:missing.append('kanat yüklemesi için kanat alanı dm²')
    if missing:lines.append('Eksik veri: '+'; '.join(missing)+'.')
    if not calculated:
        lines.insert(0,'Hesap yapabilmem için sayısal donanım bilgisi gerekiyor.')
    lines.append('Örnek giriş: “Toplam ağırlık 1450 g, 4 motor, motor başına itki 900 g, batarya 5200 mAh, ortalama akım 22 A, voltaj 14.8 V.”')
    lines.append('Sonuç bir tasarım tahminidir; gerçek motor-pervane test tablosu, terazi, wattmetre ve güvenli yer testiyle doğrulanmalıdır.')
    return '\n\n'.join(lines)


COMPONENTS={
    'frame':('Gövde / şase',('govde','sase','frame','airframe','kanat govdesi')),
    'motors':('Motorlar',('motor','motorlar','brushless')),
    'esc':('ESC / motor sürücüsü',('esc','4in1','4 in 1','aio esc','motor surucu')),
    'propellers':('Pervaneler',('pervane','propeller','prop')),
    'flight_controller':('Uçuş kontrolcüsü',('cube orange','cube','pixhawk','ucus kontrolcu','flight controller','speedybee')),
    'gps':('GPS + pusula',('here3','gps','gnss','pusula','compass')),
    'receiver':('RC alıcı',('rc alici','alici','receiver','rx')),
    'transmitter':('RC kumanda',('rc kumanda','kumanda','transmitter','tx')),
    'battery':('Uçuş bataryası',('batarya','lipo','li ion','li-ion')),
    'power':('Güç modülü / dağıtımı',('guc modulu','power module','pdb','bec','guc dagitim')),
    'telemetry':('Hava + yer telemetri seti',('telemetri','sik radyo','radio telemetry','yer modulu','hava modulu')),
    'servos':('Servolar',('servo','servolar')),
    'linkages':('Kontrol kolları / bağlantıları',('horn','pushrod','kontrol kolu','menteşe','mentese')),
    'camera':('FPV kamera',('fpv kamera','kamera')),
    'vtx':('Video verici',('vtx','video verici')),
    'video_receiver':('Video alıcı / gözlük',('video alici','fpv gozluk','goggles','ekran')),
    'video_antenna':('Video antenleri',('video anten','vtx anten')),
    'charger':('Uygun balanslı şarj cihazı',('sarj cihaz','charger','balans sarj')),
    'buzzer':('Buzzer / araç bulucu',('buzzer','arac bulucu','bipleyici')),
    'mounting':('Titreşim sönümleme ve bağlantı elemanları',('standoff','vida','somun','titreşim','titresim','montaj')),
    'landing_gear':('İniş takımı',('inis takimi','landing gear')),
    'airspeed':('Airspeed / pitot sensörü',('airspeed','pitot')),
}


def parse_inventory(text):
    q=_normalize(text);found=set()
    for key,(_,aliases) in COMPONENTS.items():
        if any(re.search(rf'(?<![a-z0-9]){re.escape(_normalize(alias))}(?![a-z0-9])',q) for alias in aliases):found.add(key)
    return found


def is_build_question(text):
    q=_normalize(text)
    phrases=('ne gerekli','neler gerekli','ne lazim','baska ne','eksik ne','eksigi var','parcalar yeterli','yeterli mi',
             'iha yapmak','iha toplamak','iha kurmak','ucusa hazir','ucmaya hazir','uyumlu mu','birlikte calisir mi')
    return any(phrase in q for phrase in phrases)


def inventory_report(inventory,aircraft='Döner kanat'):
    if aircraft=='Sabit kanat':
        essential=('frame','motors','esc','propellers','servos','linkages','flight_controller','receiver','transmitter','battery','power')
        navigation=('gps','telemetry');recommended=('charger','buzzer','mounting','landing_gear','airspeed')
    elif aircraft=='FPV':
        essential=('frame','motors','esc','propellers','flight_controller','receiver','transmitter','battery','power')
        navigation=('gps','telemetry');recommended=('camera','vtx','video_receiver','video_antenna','charger','buzzer','mounting')
    else:
        essential=('frame','motors','esc','propellers','flight_controller','receiver','transmitter','battery','power')
        navigation=('gps','telemetry');recommended=('charger','buzzer','mounting','landing_gear')
    label=lambda key:COMPONENTS[key][0]
    lines=[f'ARAÇ TÜRÜ: {aircraft}']
    if inventory:lines.append('Yazdığınız mevcut parçalar: '+', '.join(label(key) for key in essential+navigation+recommended if key in inventory)+'.')
    missing=[key for key in essential if key not in inventory]
    if inventory:
        lines.append('Temel sistemde henüz belirtilmeyenler:\n'+'\n'.join('• '+label(key) for key in missing) if missing else 'Temel uçuş parçalarının tamamı mesajda belirtilmiş görünüyor.')
    else:
        lines.append('Temel uçuş sistemi:\n'+'\n'.join('• '+label(key) for key in essential))
    nav_missing=[key for key in navigation if key not in inventory]
    if nav_missing:lines.append('Konum/yer istasyonu özellikleri için:\n'+'\n'.join('• '+label(key) for key in nav_missing))
    rec_missing=[key for key in recommended if key not in inventory]
    if rec_missing:lines.append('Kurulum ve güvenlik için değerlendirin:\n'+'\n'.join('• '+label(key) for key in rec_missing))
    lines.append('Uyumluluk kontrolü:\n'
                 '1. Motor + pervane + batarya hücre sayısının üretici test tablosu\n'
                 '2. Ölçülmüş motor azami akımı ile ESC sürekli/anlık sınırı\n'
                 '3. Toplam akım ile batarya C değeri, konektör ve kablo kesiti\n'
                 '4. Uçuş kontrolcüsünün güç, sinyal seviyesi, port ve protokolü\n'
                 '5. Toplam kalkış ağırlığı, ölçülmüş itki ve ağırlık merkezi\n'
                 '6. Pervanesiz kurulum, yön, failsafe ve kumanda testleri')
    lines.append('Bir parçanın yalnız adına bakarak uyumlu veya uçuşa hazır kararı verilemez. Model, voltaj/hücre sayısı, akım, pervane, ağırlık ve bağlantı türlerini yazarsanız kontrolü daraltabilirim.')
    return '\n\n'.join(lines)
