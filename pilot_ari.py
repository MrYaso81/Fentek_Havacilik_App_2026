"""Pilot Arı: local, read-only flight decision support chat."""
import re
import os
import time
import queue
import threading
from difflib import SequenceMatcher
import tkinter as tk
from tkinter import ttk, messagebox

from branded import BLACK, SURFACE, YELLOW, WHITE, GRAY
from guide_catalog import TOPICS, parameter_help
from weather_service import Location, WeatherError, fetch_current, format_current, geocode, parse_location
from cloud_pilot import CloudPilotError, MODELS, OpenAIPilotClient
from iha_knowledge import (HardwareProfile, LightweightRAG, inventory_report, is_build_question,
                           is_performance_question, parse_inventory, parse_specs, performance_report)
from turkish_language import detect_intents, semantic_normalize


TECH_KNOWLEDGE=(
    (('cube','orange','ucus kontrol'),
     'Cube Orange uçuş kontrolcüsüdür. IMU, barometre ve bağlı sensörlerden gelen verileri ArduPilot ile birleştirir; motor/servo çıkışlarını yönetir. Uygulama Cube’a MAVLink üzerinden bağlanır. Kartın kurulumu, yönü ve araç çerçevesi doğru yapılandırılmadan yalnız bağlantı kurulmuş olması uçuşa hazır olduğu anlamına gelmez.'),
    (('here3','dronecan','gps pusula'),
     'Here3, Cube’a genellikle DroneCAN üzerinden konum ve pusula verisi sağlar. CAN kablolaması, sonlandırma, GPS türü ve CAN sürücüsü doğru olmalıdır. Açık gökyüzünde 3D fix, uydu sayısı, HDOP ve pusula yönü yerde doğrulanmalıdır. Harita interneti Here3’ün GPS konumu üretmesi için gerekli değildir.'),
    (('ekf','konum birlestirme'),
     'EKF; ivmeölçer, jiroskop, GPS, barometre ve pusula ölçümlerini birleştirerek yönelim ve konum kestirir. LOITER, GUIDED, AUTO ve RTL gibi navigasyon modları sağlıklı EKF çözümüne bağlıdır. Uygulamadaki EKF uyarısı giderilmeden navigasyon moduna geçilmemelidir.'),
    (('batarya','guc modulu','akim voltaj'),
     'Canlı batarya bilgisi Cube’a bağlı güç modülü veya desteklenen batarya monitöründen gelir. Voltaj, akım ve kapasite ölçeği doğru kalibre edilmelidir. Yüzde değeri tek başına yeterli değildir; hücre voltajı, yük altındaki düşüm, tüketilen mAh ve düşük/kritik batarya failsafe ayarları birlikte değerlendirilir.'),
    (('telemetri','sik','radyo','mavlink'),
     'Hava ve yer telemetri radyoları MAVLink verisini taşır. İki radyo eşleşmeli; Cube SERIAL protokolü ve hızı yer modülüyle uyumlu olmalıdır. RSSI tek başına yeterli değildir; uzak/yakın gürültü, sinyal-gürültü farkı, gönderim tamponu ve paket kaybı birlikte izlenir.'),
    (('rc','kumanda','alici'),
     'RC kumanda pilotun ana kontrol yoludur; telemetri yer istasyonu verisi ve komutları içindir. RC failsafe alıcıyla birlikte yerde doğrulanmalı, mod anahtarları doğru kanallara atanmalı ve uçuş sırasında güvenli manuel moda dönüş yolu korunmalıdır.'),
    (('failsafe','baglanti kaybi','guvenlik'),
     'Failsafe davranışı olay gerçekleştiğinde Cube’un ne yapacağını belirler. RC kaybı, GCS/telemetri kaybı, düşük-kritik batarya ve EKF arızası ayrı ayrı yapılandırılır. Uygulamadaki senaryo ekranı yalnız kart parametresini açıklar; gerçek davranış pervanesiz yerde ve kontrollü uçuş planıyla doğrulanmalıdır.'),
    (('sanal cit','geofence','fence'),
     'Sanal çit azami irtifa, HOME çevresi veya çokgen sınırlar tanımlayabilir. İhlal eylemi firmware ayarına bağlıdır. Haritadaki çizim ile Cube’a yüklenen çitin aynı olduğu geri okunmalı; GPS hatası ve RTL rotası için güvenli pay bırakılmalıdır.'),
    (('rally','guvenli inis'),
     'Rally noktaları ana görevden ayrıdır ve RTL için alternatif hedefler sağlar. Noktaların irtifası, erişilebilirliği ve çevresindeki engeller kontrol edilmelidir. Bir Rally noktası eklemek, alanın otomatik olarak güvenli iniş alanı olduğu anlamına gelmez.'),
    (('gorev','waypoint','rota','mission'),
     'Görev planında her waypoint’in WGS84 konumu, HOME üstü irtifası, sırası ve komutu kontrol edilir. Yükleme sonrasında görev Cube’dan geri okunup karşılaştırılmalıdır. AUTO başlamadan HOME, GPS, EKF, batarya, sanal çit ve görev başlangıç adımı doğrulanır.'),
    (('kalibrasyon','ivmeolcer','pusula','gyro'),
     'Kalibrasyon araç sabitken, doğru kart yönüyle ve pervaneler sökülüyken yapılmalıdır. Pusula kalibrasyonu metal, mıknatıs ve yüksek akım kablolarından uzakta gerçekleştirilir. Bu uygulamadaki motor testi sentetiktir; gerçek motor yönü ve çıkış eşlemesi ayrıca doğrulanmalıdır.'),
    (('motor','esc','pervane'),
     'Motor numarası, dönüş yönü, ESC protokolü ve pervane yönü araç çerçevesiyle eşleşmelidir. Masa testinde pervaneler çıkarılır. Uygulamanın mevcut motor testi yalnız görsel demodur ve gerçek motor çıkışı üretmez.'),
    (('harita','uydu','google','esri','openstreetmap'),
     'OpenStreetMap sokak haritası, Esri ve Google ise hazırlanmış uydu görüntüsü katmanlarıdır; hiçbiri canlı uydu kamerası değildir. İHA konumu Here3/Cube telemetrisinden gelir ve haritanın üzerine çizilir. Google katmanı anahtar ve faturalandırma gerektirir; Esri görünümü anahtarsızdır.'),
    (('koordinat','wgs84','ned','home'),
     'Enlem-boylam WGS84 dünya koordinatıdır. Görev irtifası çoğunlukla HOME üzerindeki metre olarak ele alınır. NED ekseninde X kuzey, Y doğu ve Z aşağı yönlüdür; bu nedenle yükselirken NED Z değeri negatif olabilir.'),
    (('kamera','video','vtx','rtsp'),
     'Kamera sistemi uçuş kontrolünden ayrı bir görüntü zinciridir. USB kamera doğrudan bilgisayara; RTSP/HTTP kamera ise ağ adresi üzerinden bağlanır. FPV sisteminde kamera, VTX, uygun anten ve yer alıcısı aynı standart/frekansla çalışmalıdır. Görüntü gelmemesi Cube telemetrisinin de kesildiği anlamına gelmez.'),
    (('servo','pwm','cikis','bec'),
     'Servo sistemi doğru çıkış kanalı, PWM aralığı, yön, mekanik bağlantı ve yeterli besleme ister. Cube sinyal üretse de servoların güç ihtiyacı taşıyıcı kartın izin verdiği şekilde ayrı BEC gerektirebilir. Yön ve hareket sınırları yerde, motor devre dışıyken doğrulanmalıdır.'),
)


# Common mobile-keyboard and fast-typing mistakes seen in Turkish chat.  This
# operates only on the internal intent text; the user's original message is
# never rewritten on screen.
TYPO_ALIASES={
    'sau':'suan','suanlik':'suan','dea':'daha','gelistr':'gelistir','gelistirir':'gelistir',
    'nasl':'nasil','nsl':'nasil','naslsin':'nasilsin','gostrgesi':'gostergesi',
    'gorunmyo':'gorunmuyor','gozukmuyo':'gorunmuyor','calisyo':'calisiyor','calsmiyor':'calismiyor',
    'baglanmyo':'baglanmiyor','baglanmıyo':'baglanmiyor','baglycam':'baglayacagim',
    'bagliycam':'baglayacagim','baglanabilityo':'baglanabiliyor','telemteri':'telemetri',
    'telemetir':'telemetri','telmetri':'telemetri','batrya':'batarya','baterya':'batarya',
    'orance':'orange','orangce':'orange','vube':'cube','cub':'cube','her3':'here3',
    'uyfu':'uydu','hatita':'harita','similasyon':'simulasyon','klaibre':'kalibre',
    'gucenlik':'guvenlik','gucenligi':'guvenlik','parameteler':'parametreler',
    'donanmi':'donanim','performasn':'performans','agrlik':'agirlik','agirli':'agirlik',
    'ucabn':'ucan','ihaa':'iha','ihanin':'iha','ihayi':'iha',
    # Daily conversation and frequent phonetic/mobile forms.
    'slm':'selam','mrb':'merhaba','nbr':'naber','bugn':'bugun','bugun':'bugun',
    'naptin':'ne yaptin','napion':'ne yapiyorsun','napiyon':'ne yapiyorsun',
    'tesekur':'tesekkur','tesekurler':'tesekkurler','tsk':'tesekkurler',
    'sagolun':'sagol','gorusurz':'gorusuruz','anlmadim':'anlamadim','anlamadm':'anlamadim',
    # Connection, telemetry and Cube/Here3.
    'bilgisyara':'bilgisayar','bilgisayra':'bilgisayar','laptoba':'laptop','laptopa':'laptop',
    'baglayamiyrm':'baglayamiyorum','baglayabilirmym':'baglayabilir miyim',
    'baglanabilirmi':'baglanabilir mi','baglantiymi':'baglantiyi','baglanty':'baglanti',
    'sinyli':'sinyal','sinyali':'sinyal','gelymi':'gelmiyor','gelmyor':'gelmiyor',
    'comu':'com','comport':'com port','boud':'baud','baoud':'baud','anteni':'anten',
    'ardupolt':'ardupilot','ardupolot':'ardupilot','mavlnk':'mavlink','mavlik':'mavlink',
    'firmwere':'firmware','firmvare':'firmware','dronecan':'dronecan','droncan':'dronecan',
    # Flight, modes, map and mission.
    'ucusmodnu':'ucus modu','ucusmodu':'ucus modu','denge modu':'denge modu',
    'stablize':'stabilize','stabilze':'stabilize','loyter':'loiter','loytera':'loiter',
    'altold':'alt_hold','althold':'alt_hold','guded':'guided','rtll':'rtl',
    'otonomucus':'otonom ucus','gorevplanlama':'gorev planlama','waypoynt':'waypoint',
    'veypoint':'waypoint','rotayi':'rota','rotayı':'rota','irtfa':'irtifa','irtifaı':'irtifa',
    'canlikonum':'canli konum','uyduharitasi':'uydu harita','dunyaharitasi':'dunya harita',
    'gogle':'google','googole':'google','opnstreetmap':'openstreetmap','similasyon':'simulasyon',
    'yaklastr':'yaklastir','uzaklastr':'uzaklastir','noktayi':'nokta','koordinati':'koordinat',
    # Hardware and performance.
    'agırlık':'agirlik','kutle':'agirlik','kacgr':'kac gram','gramm':'gram',
    'motro':'motor','motroo':'motor','escc':'esc','pervene':'pervane','pervana':'pervane',
    'itkii':'itki','itkisi':'itki','kaldirma':'itki','kaldırma':'itki',
    'mahkac':'mah','kapsite':'kapasite','kapasitse':'kapasite','voltaji':'voltaj',
    'akm':'akim','amperr':'amper','ucussuresi':'ucus suresi','havadakalma':'havada kalma',
    'tasirmi':'tasir mi','kaldirirmi':'kaldirir mi','kanatalani':'kanat alani',
    'kanatyuklemesi':'kanat yuklemesi','faydaliyuk':'faydali yuk','gövde':'govde',
    'agirlikmerkezi':'agirlik merkezi','cgsi':'cg','sensr':'sensor','servp':'servo',
    'alci':'alici','kumnda':'kumanda','pusla':'pusula','barometre':'barometre',
    'pitott':'pitot','airspped':'airspeed','lidarr':'lidar','gimball':'gimbal',
    # Safety, setup and UI actions.
    'guvenlk':'guvenlik','failssef':'failsafe','failsef':'failsafe','feylsafe':'failsafe',
    'sanlcit':'sanal cit','geofnce':'geofence','kalibrsyn':'kalibrasyon','kalibreasyon':'kalibrasyon',
    'ayrlari':'ayarlari','ayarlr':'ayarlar','paramtre':'parametre','paramter':'parametre',
    'gostergeyi':'gosterge','gostermiyo':'gostermiyor','acilmiyo':'acilmiyor',
    'acılmıyor':'acilmiyor','kapanmiyo':'kapanmiyor','bozldu':'bozuldu','yvas':'yavas',
    'yuklenmyo':'yuklenmiyor','ekliyemiyrm':'ekleyemiyorum','silemiyrm':'silemiyorum',
}
TYPO_VOCAB=(
    'telemetri','batarya','gostergesi','gorunmuyor','baglanmiyor','baglanabiliyor',
    'baglayacagim','baglayabilirim','baglanti','calismiyor','calisiyor','nasil','neden',
    'orange','cube','here3','ucus','uygulama','guvenlik','agirlik','performans','motor',
    'pervane','harita','uydu','konum','kalibrasyon','denge','gorev','parametre','sinyal',
    'kamera','failsafe','stabilize','loiter','guided','otomatik','kanat','donanim','guncel',
    'goster','ekle','sil','gelistir','kapat','acik','iletisim','pusula','irtifa','akim',
    'selam','merhaba','naber','bugun','nasilsin','tesekkurler','sagol','gorusuruz',
    'anlamadim','bilgisayar','laptop','baglayamiyorum','baglanabilir','gelmiyor','port',
    'baud','anten','ardupilot','mavlink','firmware','dronecan','rssi','radyo','alici','kumanda',
    'servo','guc','modulu','voltaj','kapasite','amper','pervane','itki','gram','sure','tasir',
    'kaldirir','govde','merkezi','sensor','barometre','pitot','airspeed','lidar','gimbal',
    'planlama','waypoint','rota','simulasyon','openstreetmap','dunya','canli','nokta',
    'koordinat','yaklastir','uzaklastir','sanal','cit','geofence','ayarlar','acilmiyor',
    'kapanmiyor','bozuldu','yavas','yuklenmiyor','ekleyemiyorum','silemiyorum','gostermiyor',
    'alt_hold','rtl','land','auto','manual','fpv','sabit','doner','faydali','yuk','alan',
    'gps','ekf','imu','esc','bec','pdb','can','com','kv',
)

TYPO_SUFFIXES=('lar','ler','lari','leri','nin','nın','nun','nün','dan','den','dir','dır','dur','dür',
               'da','de','ta','te','yi','yı','yu','yü','si','sı','su','sü','im','ım','um','üm','in','ın','un','ün','e','a','i','ı','u','ü')


def _distance(left,right):
    """Damerau-Levenshtein distance, including neighbouring transpositions."""
    if left==right:return 0
    previous=list(range(len(right)+1));before_previous=None
    for i,a in enumerate(left,1):
        current=[i]+[0]*len(right)
        for j,b in enumerate(right,1):
            current[j]=min(current[j-1]+1,previous[j]+1,previous[j-1]+(a!=b))
            if before_previous is not None and i>1 and j>1 and a==right[j-2] and left[i-2]==b:
                current[j]=min(current[j],before_previous[j-2]+1)
        before_previous,previous=previous,current
    return previous[-1]


def _fuzzy_candidate(word,strict=False):
    if word in TYPO_VOCAB:return word
    candidates=[]
    for candidate in TYPO_VOCAB:
        if abs(len(word)-len(candidate))>3:continue
        if word[:1]!=candidate[:1]:continue
        distance=_distance(word,candidate)
        allowance=1 if max(len(word),len(candidate))<=6 else 2 if max(len(word),len(candidate))<=10 else 3
        if strict:allowance=min(allowance,1)
        if distance<=allowance:candidates.append((distance,-len(candidate),candidate))
    return min(candidates)[2] if candidates else None


def _correct_word(word):
    direct=TYPO_ALIASES.get(word)
    if direct:return direct
    if len(word)<4 or any(char.isdigit() for char in word) or '_' in word:return word
    # Preserve correctly suffixed domain words before fuzzy matching the whole
    # token.  Otherwise valid forms such as "noktada" were shortened to
    # "nokta" and natural phrase matching stopped working.
    for suffix in TYPO_SUFFIXES:
        if len(word)-len(suffix)<4 or not word.endswith(suffix):continue
        root=word[:-len(suffix)]
        if root in TYPO_VOCAB:return word
        candidate=TYPO_ALIASES.get(root) or _fuzzy_candidate(root)
        if candidate:return candidate
    candidate=_fuzzy_candidate(word)
    if candidate:return candidate
    return word


def _correct_parts(word):
    corrected=_correct_word(word)
    if corrected!=word:return corrected.split()
    # Recover a small set of accidentally joined domain phrases, such as
    # "uyduharitasi" or "nasilbaglanirim".
    if len(word)>=9 and not any(char.isdigit() for char in word):
        for cut in range(3,len(word)-2):
            left=TYPO_ALIASES.get(word[:cut]) or _fuzzy_candidate(word[:cut],True)
            right=TYPO_ALIASES.get(word[cut:]) or _fuzzy_candidate(word[cut:],True)
            if left and right:return (left+' '+right).split()
    return [word]


def normalize(text):
    text=str(text).lower().replace('i\u0307','i').translate(str.maketrans('çğıöşü','cgiosu'))
    clean=re.sub(r'\s+',' ',re.sub(r'[^a-z0-9_/%., ]+',' ',text)).strip()
    # Retain decimal numbers such as 14.8 while removing punctuation attached
    # to ordinary words before fuzzy correction.
    words=re.findall(r'\d+(?:[.,]\d+)?|[a-z][a-z0-9_/%]*',clean)
    corrected=[]
    for word in words:corrected.extend(_correct_parts(word))
    return semantic_normalize(' '.join(corrected))


def has_like(text,target,ratio=.72):
    """Recognise short everyday phrases despite common missing letters."""
    words=normalize(text).split();target=normalize(target)
    return target in words or any(SequenceMatcher(None,word,target).ratio()>=ratio for word in words)


def knowledge_answer(question):
    q=normalize(question);tokens=set(q.split())
    # ArduPilot parameter names are answered from the same verified in-app dictionary.
    candidates=re.findall(r'\b[A-Z][A-Z0-9_]{2,}\b',str(question).upper())
    for name in candidates:
        if '_' in name:
            category,description=parameter_help(name)
            if category!='Firmware özel':return f'{name} • {category}\n{description}'
    if 'cube' in q and 'here3' in q:
        return TECH_KNOWLEDGE[0][1]+'\n\n'+TECH_KNOWLEDGE[1][1]
    scored=[]
    for aliases,answer in TECH_KNOWLEDGE:
        score=0
        for alias in aliases:
            words=normalize(alias).split()
            if normalize(alias) in q:score+=4+len(words)
            else:score+=sum(1 for word in words if word in tokens or any(SequenceMatcher(None,t,word).ratio()>=.82 for t in tokens))
        scored.append((score,answer))
    score,answer=max(scored,key=lambda item:item[0])
    if score>=2:return answer
    # Fall back to the detailed guide topics when their title is a good match.
    guide=[]
    for category,title,body in TOPICS:
        title_words=set(normalize(title).split())
        overlap=len(tokens & title_words)
        fuzzy=sum(1 for word in title_words if any(SequenceMatcher(None,t,word).ratio()>=.86 for t in tokens))
        guide.append((overlap*3+fuzzy,category,title,body))
    score,category,title,body=max(guide,key=lambda item:item[0])
    return f'{title} • {category}\n{body}' if score>=4 else None


def mode_answer(question, aircraft='Döner kanat'):
    q=normalize(question)
    pairs=(('stabilize','STABILIZE pilotun gaz ve yatay hareketi yönetmesine yardım eder; araç kendi kendine konum veya irtifa tutmaz.'),
           ('alt_hold','ALT_HOLD barometreyle irtifayı korumaya çalışır; yatay konumu GPS ile sabitlemez.'),
           ('loiter','LOITER sağlıklı GPS ve EKF ile konum ve irtifayı tutmaya çalışır.'),
           ('auto','AUTO, Cube üzerindeki yüklenmiş görevi yürütür; görev, HOME, GPS ve EKF doğrulanmalıdır.'),
           ('guided','GUIDED, yer istasyonundan gönderilen konum hedeflerini izler ve sürekli güvenilir telemetri tasarımı ister.'),
           ('rtl','RTL, kayıtlı HOME noktasına dönüş davranışıdır; doğru HOME, GPS, irtifa ve RTL parametrelerine bağlıdır.'),
           ('land','LAND bulunduğu yerde kontrollü alçalma ister; uygun ve boş iniş alanı yine pilot tarafından doğrulanmalıdır.'),
           ('fbwa','FBWA sabit kanatta pilot komutlarını yatış/yunuslama sınırlarıyla destekleyen temel yardımcı modlardan biridir.'))
    mentioned=[(key,text) for key,text in pairs if key in q]
    if len(mentioned)>=2:return '\n\n'.join(text for _,text in mentioned)+'\n\nSeçim, araç türüne ve yapmak istediğiniz manevraya bağlıdır.'
    if mentioned:return mentioned[0][1]
    if any(word in q for word in ('hangi mod','hangi modu','mod oner','modda ucur')):
        if aircraft=='Sabit kanat':return 'Sabit kanatta kontrollü ilk denemeler için kart destekliyorsa FBWA temel yardımcı seçenektir. Otomatik rota için AUTO, dönüş için RTL kullanılır; gerçek mod listesi bağlı firmware’den doğrulanmalıdır.'
        return 'Elle kontrollü denge için STABILIZE, yalnız irtifa desteği için ALT_HOLD, GPS ile konum tutmak için LOITER, yüklenmiş görev için AUTO kullanılır. İlk deneme yerde ve ardından kontrollü alanda STABILIZE ile yapılmalıdır.'
    return None


def weather_answer(question):
    q=normalize(question)
    weather_words=('hava','ruzgar','yagmur','sis','kar','firtina','gorusu','sicaklik','ucus yapilir')
    measurement=re.search(r'(\d+(?:[.,]\d+)?)\s*(m/s|km/?h|knot|kt)',q)
    if not any(word in q for word in weather_words) and not measurement:return None
    hazards=[]
    if any(word in q for word in ('yildirim','firtina','siddetli yagmur','dolu')):hazards.append('Yıldırım, fırtına, dolu veya şiddetli yağış varsa uçuşu erteleyin.')
    elif any(word in q for word in ('yagmur','kar')) and not any(clear in q for clear in ('yagmur yok','yagis yok','kar yok')):
        hazards.append('Araç ve bütün donanım açıkça bu koşul için derecelendirilmediyse yağışta uçuşu erteleyin.')
    if 'sis' in q:hazards.append('Sis görüşü ve yön farkındalığını azaltır; yasal görüş şartları doğrulanmadan uçmayın.')
    match=measurement
    if match:
        value=float(match.group(1).replace(',','.'));unit=match.group(2)
        ms=value if unit=='m/s' else value/3.6 if unit.startswith('km') else value*.514444
        hazards.append(f'Yazdığınız rüzgâr yaklaşık {ms:.1f} m/s. Bunu aracın üretici sınırı ve yerde doğrulanmış güvenli sınırıyla karşılaştırın; evrensel bir güvenli rüzgâr değeri yoktur.')
    if hazards:return '\n'.join('• '+item for item in hazards)+'\n\nPilot Arı meteoroloji ölçümü yapmaz; kalkış alanındaki gerçek rüzgâr, hamle, görüş ve yağışı ayrıca doğrulayın.'
    return 'Hava uygunluğunu değerlendirebilmem için rüzgâr hızını ve birimini, yağış durumunu, görüşü ve mümkünse rüzgâr hamlesini yazın. Örnek: “Rüzgâr 5 m/s, hamle 8 m/s, yağış yok, görüş açık.”'


class PilotAdvisor:
    def __init__(self,app):
        self.app=app;self.last_topic=None;self.user_name=None;self.turns=0
        self.pending=None;self.pending_question='';self.current_question=''
        self.history=[];self.last_question='';self.last_answer=''
        self.hardware_profile=HardwareProfile();self.rag=LightweightRAG()
        self.hardware_inventory=set()

    def remember(self,topic,text):
        self.last_topic=topic;self.turns+=1
        question=self.current_question.strip()
        if question:
            self.history.append((question,text));self.history=self.history[-8:]
            self.last_question=question
        self.last_answer=text
        return text

    def followup(self,question):
        """Handle short references to the previous answer without losing context."""
        if not self.last_answer:return None
        q=normalize(question)
        if any(phrase in q for phrase in ('anlamadim','daha basit anlat','basit anlat','tekrar anlat','baska turlu anlat')):
            parts=[part.strip(' •0123456789.') for part in re.split(r'(?<=[.!?])\s+|\n+',self.last_answer) if len(part.strip())>5]
            core=' '.join(parts[:2]) if parts else self.last_answer
            return 'Daha basit anlatayım: '+core+'\n\nTakıldığın kelimeyi yazarsan onu da tek cümleyle açıklayabilirim.'
        if any(phrase in q for phrase in ('liste yap','madde madde','sirala','kontrol listesi yap')):
            parts=[part.strip(' •0123456789.') for part in re.split(r'(?<=[.!?])\s+|\n+',self.last_answer) if len(part.strip())>5]
            if parts:return '\n'.join('• '+part for part in parts[:8])
        if any(phrase in q for phrase in ('avantaji ne','dezavantaji ne','artisi eksisi','iyi yani ne','kotu yani ne')):
            comparisons={
                'mode':'Avantaj ve sınırlama seçilen moda göre değişir. Modun adını yazarsan pilot kontrolü, gereken sensörler ve bağlantı kaybındaki davranış açısından karşılaştırabilirim.',
                'hardware':'Donanımın artısı performans veya özellik kazandırmasıdır; karşılığında ağırlık, akım, maliyet ve arıza noktası ekleyebilir. Hangi parçayı kastettiğini yaz.',
                'components':'Ek parçanın faydasını; ağırlık, enerji tüketimi, bağlantı gereksinimi ve kazandırdığı özelliklerle birlikte değerlendirebilirim. Parçanın tam modelini yaz.',
                'connection':'Telemetrinin avantajı canlı veri ve görev iletişimidir; radyo menzili, parazit, güç ve doğru failsafe ayarı gerektirir.',
            }
            return comparisons.get(self.last_topic,'Hangi seçeneğin avantaj ve dezavantajını istediğini yazarsan iki tarafı birlikte karşılaştırabilirim.')
        if any(phrase in q for phrase in ('kisa ozet','kisaca','ozetle','kisa anlat')):
            parts=[part.strip() for part in re.split(r'(?<=[.!?])\s+|\n+',self.last_answer) if part.strip()]
            return 'Kısaca: '+' '.join(parts[:2])
        if any(phrase in q for phrase in ('adim adim','sirayla anlat','nasil yapacagim','nasil yapalim')):
            parts=[part.strip(' •0123456789.') for part in re.split(r'(?<=[.!?])\s+|\n+',self.last_answer) if len(part.strip())>8]
            if parts:return '\n'.join(f'{index}. {part}' for index,part in enumerate(parts[:6],1))
        if any(phrase in q for phrase in ('ornek ver','bir ornek','mesela nasil')):
            examples={
                'mode':'Örnek: Araç elle uçurulacaksa STABILIZE; havada GPS ile aynı noktada beklenecekse LOITER; önceden yüklenip geri doğrulanmış rota çalıştırılacaksa AUTO seçilir.',
                'connection':'Örnek bağlantı: hava radyosu Cube TELEM1’e, yer radyosu laptop USB’sine bağlanır; iki taraf aynı ağ ayarı ve seri hızında olur. Uygulama doğru COM portunda ArduPilot heartbeat görmelidir.',
                'weather':'Örnek bilgi: “Rüzgâr 4 m/s, hamle 7 m/s, yağış yok, görüş 10 km.” Pilot Arı bunu aracın doğrulanmış sınırıyla karşılaştırmak için model ve sınır bilgisini ayrıca sorabilir.',
                'battery':'Örnek: Güç modülü %35, 15.2 V ve 8 A bildiriyorsa bunlar canlı ölçümlerdir; kalan güvenli süreyi yalnız yüzdeye bakarak kesin söylemek doğru değildir.',
                'knowledge':'Somut bir örnek verebilmem için önceki konunun hangi bölümünü kastettiğini yaz: bağlantı, ayar, uçuş davranışı veya arıza durumu.',
            }
            return examples.get(self.last_topic,'Hangi konu için örnek istediğini bir iki kelimeyle yazarsan somut bir senaryo kurabilirim.')
        if q in ('neden','neden boyle','nasil yani','biraz daha anlat','daha ayrintili anlat','devam et','peki sonra'):
            prompts={
                'mode':'Modun sensör gereksinimini mi, pilot kontrolünü mü, yoksa hangi durumda seçileceğini mi ayrıntılandırayım?',
                'connection':'Bağlantının bilgisayar tarafını mı, iki radyonun eşleşmesini mi, yoksa Cube TELEM ayarlarını mı ayrıntılandıralım?',
                'weather':'Rüzgârı mı, yağışı/görüşü mü, yoksa aracın sınırlarıyla karşılaştırmayı mı ayrıntılandıralım?',
                'battery':'Güç modülü bağlantısını mı, kalibrasyonu mu, yoksa düşük batarya failsafe ayarını mı açıklayayım?',
                'gps':'Here3 bağlantısını mı, 3D fix sorununu mu, yoksa pusula/EKF ilişkisini mi açıklayayım?',
            }
            return prompts.get(self.last_topic,'Önceki cevabın bağlantı, ayar, güvenlik veya kullanım kısmından hangisini derinleştireyim?')
        return None

    def compound(self,question):
        """Answer several concrete flight issues from one longer message."""
        q=normalize(question);topics=[]
        trouble=any(word in q for word in ('calismiyor','baglanmiyor','baglayamiyorum','kopuyor','goremiyor','gorunmuyor','gelmiyor','acilmiyor','gostermiyor','yuklenmiyor','bozuldu','sorun','hata','yok'))
        if trouble and any(word in q for word in ('telemetri','com','sik')):topics.append(('TELEMETRİ',self.connection_help(question)))
        if trouble and ('gps' in q or 'here3' in q):topics.append(('GPS / HERE3',self.gps_help()))
        if trouble and 'batarya' in q:topics.append(('BATARYA',self.battery_help()))
        if any(name in q for name in ('stabilize','alt_hold','loiter','auto','guided','rtl','land','fbwa')):
            answer=mode_answer(question,getattr(self.app,'aircraft_type','Döner kanat'))
            if answer:topics.append(('UÇUŞ MODU',answer))
        if len(topics)<2:return None
        return '\n\n'.join(title+'\n'+text for title,text in topics[:3])+'\n\nÖnce ilk başlıktan başlayıp sonucu yazarsan sonraki adımı birlikte daraltabiliriz.'

    def hardware_reply(self,question):
        values=parse_specs(question)
        active=is_performance_question(question) or self.pending=='hardware_specs'
        if not active:return None
        self.hardware_profile.update(values)
        report=performance_report(self.hardware_profile,getattr(self.app,'aircraft_type','Döner kanat'))
        enough_thrust=all((self.hardware_profile.weight_g,self.hardware_profile.motor_count,self.hardware_profile.thrust_per_motor_g))
        enough_time=all((self.hardware_profile.battery_mah,self.hardware_profile.average_current_a))
        self.pending=None if enough_thrust or enough_time else 'hardware_specs'
        source=self.rag.retrieve(question,2)
        if source:
            short='\n\n'.join(block.split('\n',1)[0] for block in source.split('\n\n'))
            report+='\n\nKullanılan yerel bilgi: '+short.replace('[Yerel kaynak: ','').replace(']','')
        return self.remember('hardware',report)

    def build_reply(self,question):
        q=normalize(question);found=parse_inventory(q)
        active=is_build_question(q) or self.pending=='component_inventory'
        if not active:return None
        self.hardware_inventory.update(found)
        if not self.hardware_inventory:self.pending='component_inventory'
        elif any(phrase in q for phrase in ('tamam','baska ne','eksik','yeterli','hazir')):self.pending=None
        else:self.pending='component_inventory'
        return self.remember('components',inventory_report(self.hardware_inventory,getattr(self.app,'aircraft_type','Döner kanat')))

    def casual(self,question):
        q=normalize(question)
        words=q.split()
        name=re.search(r'benim adim ([a-z]{2,20})',q)
        if name:
            self.user_name=name.group(1).title()
            return f'Memnun oldum {self.user_name}! Ben Pilot Arı. Uçuş hazırlığında ve günlük sorularında buradayım.'
        if any(phrase in q for phrase in ('adin ne','ismin ne','sen kimsin','kimsin sen')):
            return 'Ben Pilot Arı 🐝 Fentek Havacılık uygulamasının yerel uçuş yardımcısıyım. Sohbet eder, Cube verilerini açıklar ve modları karşılaştırırım.'
        if any(phrase in q for phrase in ('ne yapabilirsin','neler yapabilirsin','bana nasil yardim')) or has_like(q,'yeteneklerin'):
            return ('Canlı batarya, GPS, ARM ve telemetri durumunu yorumlayabilirim; uçuş modlarını karşılaştırabilirim; '
                    'yazdığın rüzgâr, yağış ve görüş koşullarındaki riskleri açıklayabilirim. Ayrıca benimle normal şekilde sohbet edebilirsin.')
        greeting=any(word in words for word in ('sa','selam','merhaba','hey','slm')) or any(phrase in q for phrase in ('gunaydin','iyi aksamlar','iyi geceler'))
        # “Nasıl çalışır?” is a technical question, not “Nasılsın?”. Only use
        # fuzzy matching when a greeting or a direct “sen” address is present.
        how=(any(word in words for word in ('nasilsin','naslsin','nasilsiniz','nabersin','naber')) or
             'ne haber' in q or (greeting or 'sen' in words) and has_like(q,'nasilsin',.64))
        if greeting and how:
            return f'{"Aleyküm selam" if "sa" in q.split() else "Merhaba"}{" "+self.user_name if self.user_name else ""}! İyiyim, teşekkür ederim. Sen nasılsın? Bugün uçuş planı mı hazırlıyoruz?'
        if greeting:
            return f'{"Aleyküm selam" if "sa" in q.split() else "Merhaba"}{" "+self.user_name if self.user_name else ""}! Nasıl gidiyor? Uçuşla ilgili bir şey sorabilir veya biraz sohbet edebilirsin.'
        if how:return 'İyiyim, teşekkür ederim 🐝 Sistemleri kontrol etmeye hazırım. Sen nasılsın?'
        if any(phrase in q for phrase in ('ben iyiyim','iyiyim sagol','iyi gidiyor','gayet iyiyim')):
            return 'Buna sevindim! Bugün bir uçuş hazırlığı mı yapıyoruz, yoksa uygulamayı mı geliştiriyoruz?'
        if any(phrase in q for phrase in ('yoruldum','cok yorucu','dinlenmem lazim')):
            return 'Biraz ara vermek iyi olabilir. Özellikle uçuş hazırlığında yorgunken acele etmek kontrol atlamaya yol açabilir. İstersen kaldığımız işi kısa bir kontrol listesine dönüştürebilirim.'
        if any(phrase in q for phrase in ('canim sikiliyor','sikildim','ne yapalim')):
            return 'İstersen küçük bir İHA bilgi oyunu yapalım, bir uçuş senaryosu kuralım veya uygulamada geliştireceğimiz bir özelliği birlikte seçelim. Hangisi daha keyifli gelir?'
        if any(phrase in q for phrase in ('ne yapiyorsun','napiyorsun','napiyosun')):
            return 'Şu anda seni dinliyor ve sorunu anlamaya çalışıyorum 🐝 İstersen sohbet edebiliriz veya uçuş hazırlığına devam edebiliriz.'
        if any(phrase in q for phrase in ('gunun nasil','bugun nasilsin')):
            return 'İyi ve hazırım 🐝 Bugün sende işler nasıl gidiyor?'
        if any(phrase in q for phrase in ('kotuyum','moralim bozuk','iyi degilim')):
            return 'Üzüldüm. İstersen biraz konuşabiliriz; acelemiz yok. Uçuş yapmayı düşünüyorsan dikkatini toparlayana kadar ertelemek daha iyi olabilir.'
        if has_like(q,'tesekkurler',.68) or has_like(q,'sagol',.70) or 'eyvallah' in q:
            return 'Rica ederim! Ne zaman istersen buradayım 🐝'
        if any(phrase in q for phrase in ('gorusuruz','hosca kal','bay bay','kendine iyi bak')):
            return 'Görüşürüz! Güvenli ve güzel uçuşlar 🐝'
        if any(phrase in q for phrase in ('seni kim yapti','kim gelistirdi','seni kim gelistirdi')):
            return 'Beni Fentek Havacılık uygulamasının içinde çalışan yerel bir yardımcı olarak birlikte geliştirdiniz. İnternet hesabına bağlı olmadan bu bilgisayarda çalışıyorum.'
        if any(phrase in q for phrase in ('cok iyisin','harikasin','guzel olmus','aferin')):
            return 'Teşekkür ederim! İşine yaramasına sevindim 🐝 Bir sonraki sorunu yazabilirsin.'
        if q in ('tamam','okey','olur','peki','anladim'):
            if self.last_topic=='weather':return 'Tamamdır. Hava değişirse rüzgâr, hamle, yağış ve görüş değerlerini tekrar yazabilirsin.'
            if self.last_topic=='mode':return 'Tamamdır. Modu değiştirmeden önce canlı bağlantı ve güvenlik kontrollerini gözden geçirmeyi unutma.'
            return 'Tamamdır! Devam etmek istediğinde buradayım.'
        if any(phrase in q for phrase in ('saat kac','saat ne')):return 'Bilgisayar saatine göre '+time.strftime('%H:%M')+'.'
        return None

    def status(self):
        live=getattr(self.app,'live_map',None);now=time.monotonic()
        if not live or not live.enabled:return 'Canlı Cube bağlantısı yok. Batarya, GPS, EKF ve telemetriyi değerlendiremiyorum.'
        state=live.state;lines=[]
        age=now-state.heartbeat_time if state.heartbeat_time else None
        lines.append('Telemetri: '+('güncel' if age is not None and age<3 else 'güncel değil'))
        lines.append('Batarya: '+('veri yok' if state.battery is None else f'%{state.battery:.0f}'))
        lines.append('GPS: '+('veri yok' if state.fix is None else f'Fix {state.fix}, {state.satellites if state.satellites is not None else "—"} uydu'))
        lines.append('Mod: '+str(state.mode));lines.append('ARM: '+('ARMED' if state.armed else 'DISARMED' if state.armed is False else 'bilinmiyor'))
        errors=live.safety.checks(now,'mission' if state.armed else 'arm')
        if errors:lines.append('Bekleyen kontroller: '+'; '.join(errors[:6]))
        else:lines.append('Uygulamanın mevcut kontrollerinde engel görünmüyor; fiziksel kontrol ve hava bilgisi ayrıca gereklidir.')
        return '\n'.join(lines)

    def connection_help(self,question):
        q=normalize(question);live=getattr(self.app,'live_map',None);now=time.monotonic()
        ports=[]
        try:ports=[p.device for p in live.serial_ports()]
        except Exception:pass
        if live and live.enabled:
            age=now-live.state.heartbeat_time if live.state.heartbeat_time else None
            if age is not None and age<3:
                return ('Telemetri bağlantısı şu anda çalışıyor; Cube yaşam sinyali güncel. Sorun yalnız harita veya GPS ise telemetri bağlantısını yeniden kurmak yerine ilgili veriyi kontrol edelim.\n\n'+self.status())
            connection=getattr(live,'connection','Bağlantı bilgisi yok')
            return (f'Oturum açılmış ancak Cube yaşam sinyali güncel değil. Uygulama durumu: {connection}\n\n'
                    '1. Hava ve yer radyosunun antenleri takılıyken enerjilerini kontrol edin.\n'
                    '2. Aynı COM portunu kullanan Mission Planner veya başka programı kapatın.\n'
                    '3. Bağlantı penceresinde otomatik taramayı yeniden başlatın.\n'
                    '4. Cube’un ilgili TELEM portundaki MAVLink protokolü ve seri hızını radyo ayarıyla karşılaştırın.')
        port_text=', '.join(ports) if ports else 'Windows şu anda kullanılabilir USB seri port bildirmiyor'
        return (f'Tespit edilen seri portlar: {port_text}.\n\n'
                'Bağlantı sırası:\n'
                '1. Uçaktaki radyoyu Cube’un uygun TELEM portuna üretici kablosuyla bağlayın; TX/RX/GND ve besleme bağlantısını doğrulayın.\n'
                '2. Her iki anteni radyolara enerji vermeden önce takın ve hava tarafındaki Cube’u besleyin.\n'
                '3. Yer radyosunu bilgisayarın USB girişine takın; Mission Planner aynı COM portunda açıksa bağlantısını kapatın.\n'
                '4. Uçuş ekranında “CUBE’A BAĞLAN” penceresini açıp “USB telemetri takılınca otomatik bağlan” seçeneğini kullanın.\n'
                '5. Elle deneyecekseniz SiK radyolarda sık kullanılan başlangıç değeri 57600 baud’dur; kesin değer iki radyo ve Cube SERIAL ayarıyla aynı olmalıdır.\n\n'
                'COM hiç görünmüyorsa USB kablosu/sürücüsü; COM görünüyor fakat yaşam sinyali yoksa radyo eşleşmesi, Cube gücü, TELEM portu, MAVLink protokolü ve baud ayarı kontrol edilir.')

    def gps_help(self):
        live=getattr(self.app,'live_map',None);state=getattr(live,'state',None)
        current='Canlı bağlantı yok; GPS verisini okuyamıyorum.'
        if live and live.enabled and state:
            current=f'Kartın bildirdiği GPS: Fix {state.fix if state.fix is not None else "yok"}, uydu {state.satellites if state.satellites is not None else "yok"}.'
        return (current+'\n\nHere3 çalışmıyorsa CAN kablosu ve besleme, CAN sürücüsü/GPS türü, düğümün algılanması ve açık gökyüzü kontrol edilir. '
                'İlk fix kapalı alanda uzun sürebilir. GPS görünse bile 3D fix ve güncel konum gelmeden LOITER, AUTO, GUIDED veya RTL denenmemelidir.')

    def battery_help(self):
        live=getattr(self.app,'live_map',None);state=getattr(live,'state',None)
        current='Canlı bağlantı yok; batarya ölçümünü okuyamıyorum.'
        if live and live.enabled and state:
            current='Kart batarya yüzdesi bildirmiyor.' if state.battery is None else f'Kartın bildirdiği batarya %{state.battery:.0f}.'
        return (current+'\n\nBatarya görünmüyorsa güç modülünün Cube POWER girişini, BATT_MONITOR seçimini, voltaj/akım pin ve ölçek ayarlarını kontrol edin. '
                'Uygulama eksik ölçümü tahmin etmez. Değeri önce multimetre veya güç analizörüyle yerde doğrulayın.')

    def warning_help(self):
        manager=getattr(self.app,'alert_manager',None)
        active=getattr(manager,'active',{}) if manager else {}
        if active:
            rows='\n'.join(f'• {title}: {detail}' for level,title,detail in active.values())
            return 'Şu anda etkin uyarılar:\n'+rows+'\n\nUyarılar sekmesindeki geçmişten ilk oluşma saatini görebilirsin.'
        return ('Şu anda Pilot Arı’nın okuyabildiği etkin bir uyarı yok. Uyarının tam metnini yazarsan anlamını açıklayabilirim. '
                'Uyarılar sekmesi batarya, GPS, telemetri, SiK bağlantısı, paket kaybı, sanal çit ve Cube durum mesajlarını kaydeder.')

    def reply(self,question):
        q=normalize(question).strip()
        if not q:return 'Bir soru yazın.'
        self.current_question=str(question)
        build=self.build_reply(question)
        if build:return build
        hardware=self.hardware_reply(question)
        if hardware:return hardware
        if self.pending=='mode_goal':
            self.pending=None
            if any(word in q for word in ('manuel','elle','temel','ilk')):
                return self.remember('mode','Temel elle kontrol ve ilk kontrollü deneme için STABILIZE uygundur. Araç irtifayı veya konumu kendi başına tutmaz; pilot gazı yönetir. Pervanesiz yer kontrolleri ve gerçek RC kumandası doğrulanmadan uçuşa geçmeyin.')
            if any(word in q for word in ('konum','bekle','sabit','hover')):
                return self.remember('mode','Konumda bekleme amacı için LOITER kullanılır. Güncel 3D GPS fix, sağlıklı EKF, doğru pusula ve HOME gerekir; bunlardan biri eksikse Pilot Arı bu modu önermez.')
            if any(word in q for word in ('gorev','rota','waypoint','otonom')):
                return self.remember('mode','Yüklenip geri doğrulanmış rota için AUTO kullanılır. Görev sırası, irtifalar, HOME, GPS, EKF, batarya ve failsafe kontrolleri tamamlanmalıdır.')
            if any(word in q for word in ('don','eve','rtl')):
                return self.remember('mode','Eve dönüş için RTL kullanılır. HOME konumu ve RTL irtifası yerde doğrulanmadan bu moda güvenmeyin.')
            self.pending='mode_goal'
            return self.remember('mode','Amacı biraz daha netleştirir misin: temel elle kontrol, irtifa tutma, konumda bekleme, görev uçuşu veya eve dönüş mü?')
        if self.pending=='clarify_topic':
            self.pending=None
            combined=f'{self.pending_question} {question}'.strip();self.pending_question=''
            answer=knowledge_answer(combined) or mode_answer(combined,getattr(self.app,'aircraft_type','Döner kanat'))
            if answer:return self.remember('knowledge',answer)
        followup=self.followup(question)
        if followup:return self.remember(self.last_topic or 'chat',followup)
        casual=self.casual(question)
        if casual:return self.remember('chat',casual)
        compound=self.compound(question)
        if compound:return self.remember('troubleshooting',compound)
        trouble=any(word in q for word in ('calismiyor','baglanmiyor','baglayamiyorum','kopuyor','goremiyor','gorunmuyor','gelmiyor','acilmiyor','gostermiyor','yuklenmiyor','bozuldu','sorun','hata'))
        connect_request=any(part in q for part in ('nasil baglan','nasil baglay','baglanti kur','com port','baud','telemetriyi bagla'))
        if ('telemetri' in q or 'com' in q or 'sik' in q) and (trouble or connect_request):
            return self.remember('connection',self.connection_help(question))
        if 'gps' in q and trouble:return self.remember('gps',self.gps_help())
        if 'batarya' in q and trouble:return self.remember('battery',self.battery_help())
        if ('uyari' in q and any(word in q for word in ('neden','nedir','acikla','veriyor'))) or 'uyarilari acikla' in q:
            return self.remember('warning',self.warning_help())
        if self.last_topic=='mode' and any(phrase in q for phrase in ('hangisi daha iyi','hangisini seceyim','peki hangisi')):
            return self.remember('mode','Tek bir “en iyi” mod yok. Elle denge için STABILIZE, irtifa desteği için ALT_HOLD, GPS ile beklemek için LOITER, doğrulanmış görev için AUTO daha uygundur. Amacını ve araç türünü yazarsan seçenekleri daraltabilirim.')
        if self.last_topic=='weather' and any(word in q for word in ('peki','ya','hamle','goruş','gorus','yagis')):
            answer=weather_answer(question)
            if answer:return self.remember('weather',answer)
        if self.last_topic=='knowledge' and q in ('peki','biraz daha anlat','daha ayrintili anlat','devam et'):
            return self.remember('knowledge','Hangi kısmı ayrıntılandırayım? Örneğin bağlantı, sensör verisi, parametre, güvenlik kontrolü veya uçuş sırasında oluşacak davranışı sorabilirsin.')
        status_request=('durum' in q or 'canli veri' in q or any(phrase in q for phrase in ('batarya kac','gps kac','telemetri nasil','telemetri ne durumda')) or 'ucabilir' in q or 'ucus yapilir mi' in q)
        if status_request:
            status=self.status()
            weather=weather_answer(question)
            if 'ucus yapilir' in q or 'ucabilir' in q:
                return self.remember('weather',status+'\n\n'+(weather or 'Hava koşulları yazılmadı. Uçuş kararı için rüzgâr, yağış ve görüş bilgisi de gerekir.'))
            if not any(word in q for word in ('hangi mod','fark')):return self.remember('status',status)
        generic_mode=any(phrase in q for phrase in ('hangi modda','hangi modu','mod oner','hangi mod daha iyi'))
        named_mode=any(name in q for name in ('stabilize','alt_hold','loiter','auto','guided','rtl','land','fbwa','manual'))
        if generic_mode and not named_mode:
            self.pending='mode_goal'
            return self.remember('mode','Doğru modu seçebilmem için amacını sorayım: temel elle kontrol, irtifa tutma, konumda bekleme, görev uçuşu veya eve dönüş mü?')
        answer=mode_answer(question,getattr(self.app,'aircraft_type','Döner kanat'))
        if answer:return self.remember('mode',answer+'\n\nBu açıklama modu etkinleştirmez; komut yalnız ilgili kontrol ekranından ve kullanıcı onayıyla gönderilir.')
        answer=weather_answer(question)
        if answer:return self.remember('weather',answer)
        answer=knowledge_answer(question)
        if answer:return self.remember('knowledge',answer+'\n\nİstersen bunun belirli bir bölümünü daha ayrıntılı sorabilirsin.')
        rag=self.rag.retrieve(question,2)
        if rag:return self.remember('knowledge',rag+'\n\nBu bilgi yerel İHA kütüphanesinden getirildi. Sayısal hesap istersen ağırlık, motor, ölçülmüş itki ve batarya bilgilerini yaz.')
        if any(word in q for word in ('fark','mod')):
            return self.remember('mode','Karşılaştırmam için iki modu adıyla yazın. Örnek: “STABILIZE ile LOITER arasındaki fark nedir?”')
        intents=detect_intents(q)
        if intents:
            labels={'connection':'telemetri/bağlantı','gps':'GPS/konum','battery':'batarya/güç','mode':'uçuş modu',
                    'mission':'görev/rota','hardware':'donanım','performance':'performans hesabı','safety':'güvenlik',
                    'map':'harita','camera':'kamera/görüntü','setup':'kurulum/ayar','weather':'hava'}
            subjects=', '.join(labels[item] for item in intents[:3])
            self.pending='clarify_topic';self.pending_question=str(question)
            return self.remember('chat',f'Sorunun {subjects} ile ilgili olduğunu anladım. Ne olduğunu mu, nasıl kurulacağını mı, bir arızayı mı, yoksa iki seçeneğin karşılaştırmasını mı istiyorsun?')
        self.pending='clarify_topic';self.pending_question=str(question)
        stop={'bir','bu','su','ve','ile','icin','gibi','ama','mi','mu','mı','mü','ne','nasil','neden','ben','sen','o','da','de'}
        clues=[word for word in q.split() if len(word)>3 and word not in stop][:3]
        subject=' / '.join(clues)
        if subject:
            return self.remember('chat',f'“{subject}” konusunu anladım ama yerel bilgi tabanım doğru yanıt için yeterli ayrıntıyı bulamadı. Bunu İHA bağlantısı, donanım, uçuş, uygulama kullanımı veya günlük sohbet açısından mı soruyorsun?')
        return self.remember('chat','Seni yanlış yönlendirmemek için biraz daha ayrıntı verir misin? İstersen ne yapmak istediğini tek cümleyle anlat; ben uygun yerden devam edeyim.')


class PilotAri:
    def __init__(self,app):
        self.app=app;self.advisor=PilotAdvisor(app)
        self.weather_queue=queue.Queue();self.weather_cache={};self.weather_loading=False
        self.weather_question='';self.weather_job=None
        self.ai_queue=queue.Queue();self.ai_loading=False;self.ai_job=None
        self.ai_enabled=False;self.ai_model='gpt-5.4-mini';self.ai_history=[]
        self.api_key=os.environ.get('OPENAI_API_KEY','').strip()
        self._build()
        self.weather_job=self.app.root.after(150,self.poll_weather)
        self.ai_job=self.app.root.after(150,self.poll_ai)

    def _build(self):
        name='Pilot Arı'
        page=tk.Frame(self.app.deck,bg=BLACK);self.app.pages[name]=page
        nav=next(iter(self.app.nav_buttons.values())).master
        button=tk.Button(nav,text='09   🐝 Pilot Arı',anchor='w',command=lambda:self.app.select(name),bg='#101113',fg=GRAY,
                         activebackground='#25231a',activeforeground=YELLOW,relief='flat',bd=0,padx=15,pady=10,
                         font=('Segoe UI',10,'bold'),cursor='hand2')
        button.pack(fill='x',pady=4);self.app.nav_buttons[name]=button
        # Operations rebuilds the navigation from app.pages. Keep Pilot Arı
        # directly below the main flight screen for quick access.
        ordered={}
        for key,value in self.app.pages.items():
            if key==name:continue
            ordered[key]=value
            if key=='Uçuş ekranı':ordered[name]=page
        if name not in ordered:ordered[name]=page
        self.app.pages.clear();self.app.pages.update(ordered)
        self.app.heading(page,'🐝  PİLOT ARI','Yerel + isteğe bağlı bulut yapay zekâ • Uçuş komutu göndermez')
        status=tk.Frame(page,bg='#302a12',padx=12,pady=7);status.pack(fill='x',pady=(0,9))
        self.service_status=tk.StringVar(value='● SOHBET HAZIR • HAVA İÇİN İNTERNET GEREKİR')
        tk.Label(status,textvariable=self.service_status,bg='#302a12',fg='#7cdbac',font=('Segoe UI',9,'bold')).pack(side='left')
        tk.Label(status,text='Open-Meteo • Bulut AI isteğe bağlı • Salt okunur',bg='#302a12',fg=YELLOW,font=('Segoe UI',9)).pack(side='right')
        quick=tk.Frame(page,bg=BLACK);quick.pack(fill='x',pady=(0,10))
        for text,question in (('Canlı durum','Batarya GPS ve telemetri durumunu yorumla'),
                              ('Hangi mod?','Hangi modda uçurmalıyım?'),
                              ('Donanım hesabı','İHA ağırlık ve uçuş performansı hesabı yapmak istiyorum'),
                              ('Parça kontrolü','Elimdeki parçalar dışında İHA için başka ne gerekli?'),
                              ('Bağlantı sorunu','Telemetri çalışmıyor, nasıl bağlayabilirim?'),
                              ('Cube + Here3','Cube Orange ve Here3 nasıl çalışır?'),
                              ('Failsafe','Failsafe nedir ve neyi kontrol etmeliyim?'),
                              ('Canlı hava','Bulunduğum yerde hava durumu nasıl?')):
            ttk.Button(quick,text=text,command=lambda q=question:self.ask(q),style='Dark.TButton').pack(side='left',padx=(0,7))
        tk.Button(quick,text='↺  Yeni sohbet',command=self.reset_chat,bg='#292b2f',fg=WHITE,
                  activebackground='#41454a',activeforeground=WHITE,relief='flat',bd=0,padx=12,pady=9,
                  font=('Segoe UI',9,'bold'),cursor='hand2').pack(side='right')
        self.ai_settings_button=tk.Button(quick,text='⚙  AI ayarları',command=self.show_ai_settings,bg='#292b2f',fg=WHITE,
                  activebackground='#41454a',activeforeground=WHITE,relief='flat',bd=0,padx=12,pady=9,
                  font=('Segoe UI',9,'bold'),cursor='hand2')
        self.ai_settings_button.pack(side='right',padx=(0,7))
        # Pack the composer before this expandable history pane. This guarantees
        # that Windows scaling cannot let the history consume the input's space.
        host=tk.Frame(page,bg=SURFACE,highlightthickness=1,highlightbackground='#303238')
        scroll=ttk.Scrollbar(host);scroll.pack(side='right',fill='y')
        self.chat=tk.Text(host,bg=SURFACE,fg=WHITE,relief='flat',wrap='word',state='disabled',font=('Segoe UI',10),
                          padx=16,pady=14,yscrollcommand=scroll.set)
        self.chat.pack(side='left',fill='both',expand=True);scroll.configure(command=self.chat.yview)
        self.chat.tag_configure('user_name',foreground='#8fd2ff',font=('Segoe UI',10,'bold'),spacing1=6)
        self.chat.tag_configure('bot_name',foreground=YELLOW,font=('Segoe UI',10,'bold'),spacing1=6)
        self.chat.tag_configure('body',foreground=WHITE,font=('Segoe UI',10),lmargin1=10,lmargin2=10,spacing3=8)
        # Use native Tk controls with explicit colours here. The application-wide
        # ttk animation/theme must not be able to hide the composer text.
        # Keep a generous, fixed composer height so the Entry cannot collapse
        # when the chat page is resized or the window is scaled by Windows.
        composer=tk.Frame(page,bg=BLACK,height=96);composer.pack(side='bottom',fill='x',pady=(9,0));composer.pack_propagate(False)
        input_box=tk.Frame(composer,bg='#30343a',highlightthickness=2,highlightbackground='#5a5e64',highlightcolor=YELLOW)
        input_box.pack(side='left',fill='both',expand=True,pady=5)
        tk.Label(input_box,text='MESAJINIZ  •  Aşağıdaki alana tıklayıp yazın',bg='#30343a',fg='#d0d2d5',font=('Segoe UI',8,'bold')).pack(anchor='w',padx=12,pady=(7,0))
        self.query=tk.StringVar()
        self.entry=tk.Entry(input_box,textvariable=self.query,bg='#202328',fg=WHITE,insertbackground=YELLOW,
                            selectbackground='#6b5b1d',selectforeground=WHITE,relief='flat',bd=0,font=('Segoe UI',11))
        self.entry.pack(fill='x',padx=12,pady=(4,10),ipady=8);self.entry.bind('<Return>',lambda _e:self.send())
        self.entry.bind('<FocusIn>',lambda _e:input_box.configure(highlightbackground=YELLOW))
        self.entry.bind('<FocusOut>',lambda _e:input_box.configure(highlightbackground='#4a4d53'))
        self.send_button=tk.Button(composer,text='GÖNDER  ➜',command=self.send,bg=YELLOW,fg='#0c0d0f',
                                   activebackground='#ffe36a',activeforeground='#0c0d0f',disabledforeground='#5f5a43',
                                   relief='flat',bd=0,width=16,padx=14,pady=8,font=('Segoe UI',10,'bold'),cursor='hand2')
        self.send_button.pack(side='right',fill='y',padx=(9,0),pady=5)
        # The history takes only the space left above the fixed composer.
        host.pack(fill='both',expand=True)
        self.write('🐝 Pilot Arı','Merhaba! Günlük sohbet edebilir; canlı uçuş durumunu, hava koşullarını, Cube/Here3 sistemini ve ArduPilot modlarını açıklayabilirim. Daha güçlü sohbet için “AI ayarları”ndan GPT-5.4 mini açılabilir. Bulut AI kapalıyken yerel yardım çalışmaya devam eder.')

    def write(self,who,text):
        self.chat.configure(state='normal')
        self.chat.insert('end',f'{who}  ·  {time.strftime("%H:%M")}\n','bot_name' if 'Pilot Arı' in who else 'user_name')
        self.chat.insert('end',text+'\n\n','body')
        self.chat.see('end');self.chat.configure(state='disabled')

    def reset_chat(self):
        self.advisor=PilotAdvisor(self.app)
        self.ai_history.clear()
        self.chat.configure(state='normal');self.chat.delete('1.0','end');self.chat.configure(state='disabled')
        self.write('🐝 Pilot Arı','Yeni sohbet başladı. Merhaba! Bugün ne hakkında konuşalım?')
        self.entry.focus_set()

    def show_ai_settings(self):
        if getattr(self,'ai_window',None) and self.ai_window.winfo_exists():
            self.ai_window.lift();return
        w=tk.Toplevel(self.app.root);self.ai_window=w
        w.title('Pilot Arı • Bulut AI ayarları');w.geometry('690x510');w.minsize(620,470);w.configure(bg='#17191c')
        box=tk.Frame(w,bg='#17191c',padx=26,pady=22);box.pack(fill='both',expand=True)
        tk.Label(box,text='PİLOT ARI • BULUT YAPAY ZEKÂ',bg='#17191c',fg=YELLOW,font=('Segoe UI',16,'bold')).pack(anchor='w')
        tk.Label(box,text='GPT-5.4 mini, Pilot Arı’nın sohbet ve teknik açıklama yeteneğini büyük ölçüde artırır.',
                 bg='#17191c',fg=WHITE,font=('Segoe UI',10),wraplength=620,justify='left').pack(anchor='w',pady=(5,18))
        tk.Label(box,text='MODEL',bg='#17191c',fg=GRAY,font=('Segoe UI',9,'bold')).pack(anchor='w')
        selected=next((label for label,value in MODELS.items() if value==self.ai_model),next(iter(MODELS)))
        model_var=tk.StringVar(value=selected)
        model=ttk.Combobox(box,textvariable=model_var,values=list(MODELS),state='readonly',width=34)
        model.pack(anchor='w',fill='x',pady=(5,14))
        tk.Label(box,text='OPENAI API ANAHTARI',bg='#17191c',fg=GRAY,font=('Segoe UI',9,'bold')).pack(anchor='w')
        key_var=tk.StringVar(value=self.api_key)
        key=tk.Entry(box,textvariable=key_var,show='●',bg='#24272b',fg=WHITE,insertbackground=YELLOW,
                     relief='flat',font=('Segoe UI',10));key.pack(anchor='w',fill='x',ipady=8,pady=(5,7))
        tk.Label(box,text='Anahtar yalnız açık uygulama oturumunda bellekte tutulur; dosyaya ve sohbet geçmişine yazılmaz.',
                 bg='#17191c',fg='#8fd2ff',font=('Segoe UI',9),wraplength=620,justify='left').pack(anchor='w')
        info=('Bulut AI açılırsa yazdığınız mesajlar, son kısa sohbet geçmişi ve sınırlı uçuş özeti OpenAI API’ye gönderilir. '
              'Kesin GPS koordinatı, COM portu, tam olay günlüğü ve API anahtarı gönderilmez. İstekler store=false ile yapılır.\n\n'
              'OpenAI API kullanıma göre ücretlidir ve API hesabında faturalandırma/limit gerekebilir. GPT-5.4 nano daha ekonomik; '
              'GPT-5.4 mini daha güçlü seçenektir. Pilot Arı her iki seçenekte de yalnız danışmandır ve karta komut göndermez.')
        tk.Label(box,text=info,bg='#101113',fg='#d6d8dc',font=('Segoe UI',9),wraplength=610,justify='left',
                 padx=14,pady=12).pack(fill='x',pady=16)
        buttons=tk.Frame(box,bg='#17191c');buttons.pack(fill='x',side='bottom')
        def enable():
            value=key_var.get().strip()
            if len(value)<20 or any(char.isspace() for char in value):
                messagebox.showerror('Bulut AI','Geçerli OpenAI API anahtarını girin.',parent=w);return
            approved=messagebox.askyesno('Bulut AI veri onayı',
                'Mesajların, kısa sohbet geçmişinin ve kesin konum içermeyen uçuş durumunun OpenAI API’ye gönderilmesini onaylıyor musunuz?\n\nAPI kullanımı ücret oluşturabilir.',parent=w)
            if not approved:return
            self.api_key=value;self.ai_model=MODELS[model_var.get()];self.ai_enabled=True
            self.ai_history.clear();key_var.set('')
            self.service_status.set('● BULUT AI HAZIR • '+self.ai_model.upper())
            self.write('🐝 Pilot Arı','Bulut AI açıldı. Artık daha doğal ve ayrıntılı yanıt verebilirim. Uçuş verilerini yalnız salt okunur özet olarak kullanırım; karta komut göndermem.')
            w.destroy();self.entry.focus_set()
        def disable():
            self.ai_enabled=False;self.api_key='';self.ai_history.clear();key_var.set('')
            self.service_status.set('● YEREL SOHBET HAZIR • BULUT AI KAPALI')
            self.write('🐝 Pilot Arı','Bulut AI kapatıldı ve anahtar oturum belleğinden silindi. Yerel Pilot Arı çalışmaya devam ediyor.')
            w.destroy();self.entry.focus_set()
        tk.Button(buttons,text='BULUT AI’Yİ ETKİNLEŞTİR',command=enable,bg=YELLOW,fg='#0c0d0f',relief='flat',
                  font=('Segoe UI',10,'bold'),padx=14,pady=10,cursor='hand2').pack(side='left')
        tk.Button(buttons,text='Bulut AI’yi kapat',command=disable,bg='#2a2c30',fg=WHITE,relief='flat',
                  font=('Segoe UI',9,'bold'),padx=12,pady=10,cursor='hand2').pack(side='left',padx=8)
        tk.Button(buttons,text='Kapat',command=w.destroy,bg='#2a2c30',fg=WHITE,relief='flat',
                  font=('Segoe UI',9),padx=12,pady=10,cursor='hand2').pack(side='right')
        key.focus_set()

    def _safe_context(self):
        live=getattr(self.app,'live_map',None);lines=[]
        lines.append('Kaynak: '+('CANLI CUBE' if live and live.enabled else 'SENTETİK DEMO / canlı kart yok'))
        lines.append('Araç türü: '+str(getattr(self.app,'aircraft_type','bilinmiyor')))
        if live and live.enabled and getattr(live,'state',None):
            state=live.state;now=time.monotonic()
            age=now-state.heartbeat_time if state.heartbeat_time else None
            lines.extend((
                'Telemetri: '+('güncel' if age is not None and age<3 else 'eski veya yok'),
                'ARM: '+('ARMED' if state.armed else 'DISARMED' if state.armed is False else 'bilinmiyor'),
                'Mod: '+str(state.mode),
                'Batarya: '+('veri yok' if state.battery is None else f'%{state.battery:.0f}'),
                'GPS: '+('veri yok' if state.fix is None else f'fix {state.fix}, uydu {state.satellites if state.satellites is not None else "bilinmiyor"}'),
            ))
        manager=getattr(self.app,'alert_manager',None)
        titles=[]
        if manager:
            for value in list(getattr(manager,'active',{}).values())[:6]:
                if isinstance(value,(tuple,list)) and len(value)>=2:titles.append(str(value[1]))
        lines.append('Etkin uyarılar: '+(', '.join(titles) if titles else 'yok veya okunamadı'))
        return '\n'.join(lines)

    def request_ai(self,question):
        if self.ai_loading:
            self.write('🐝 Pilot Arı','Önceki bulut yanıtı hazırlanıyor. Birkaç saniye bekleyin.');return
        self.ai_loading=True;self.service_status.set('● PİLOT ARI DÜŞÜNÜYOR…')
        self.send_button.configure(state='disabled')
        history=tuple(self.ai_history);context=self._safe_context();key=self.api_key;model=self.ai_model
        rag=self.advisor.rag.retrieve(question,3)
        if rag:context+='\n\nYEREL İHA BİLGİ KÜTÜPHANESİ:\n'+rag
        def worker():
            try:
                answer=OpenAIPilotClient(key,model).reply(question,history,context)
                self.ai_queue.put(('ok',(question,answer)))
            except CloudPilotError as exc:self.ai_queue.put(('error',(question,str(exc))))
            except Exception:self.ai_queue.put(('error',(question,'Beklenmeyen bir bulut bağlantısı sorunu oluştu.')))
        threading.Thread(target=worker,daemon=True).start()

    def poll_ai(self):
        try:
            kind,value=self.ai_queue.get_nowait();question,answer=value
            self.ai_loading=False
            if not self.weather_loading:self.send_button.configure(state='normal')
            if kind=='ok':
                self.ai_history.extend((('user',question),('assistant',answer)))
                self.ai_history=self.ai_history[-12:]
                self.service_status.set('● BULUT AI HAZIR • '+self.ai_model.upper())
                self.write('🐝 Pilot Arı • AI',answer)
            else:
                self.service_status.set('● BULUT AI ULAŞILAMADI • YEREL SOHBET AKTİF')
                local=self.advisor.reply(question)
                self.write('🐝 Pilot Arı',f'Bulut AI yanıt vermedi: {answer}\n\nYerel yanıt:\n{local}')
            self.entry.focus_set()
        except queue.Empty:pass
        try:self.ai_job=self.app.root.after(150,self.poll_ai)
        except tk.TclError:self.ai_job=None

    def ask(self,text):self.query.set(text);self.send()

    @staticmethod
    def _weather_intent(question):
        q=normalize(question)
        return (any(phrase in q for phrase in ('hava durumu','canli hava','bugun hava','hava nasil','internetten hava','bulundugum yerde hava'))
                or ('hava' in q and any(word in q for word in ('ucus','uculur','uygun'))))

    def _automatic_location(self):
        live=getattr(self.app,'live_map',None)
        if live and live.enabled and getattr(live,'state',None) and live.state.fresh():
            pos=live.state.position
            return Location(pos['lat'],pos['lon'],'İHA canlı konumu')
        pc=getattr(self.app,'pc_location',None)
        if pc:
            city=getattr(self.app,'place_city','')
            country=getattr(self.app,'place_country','')
            label=', '.join(part for part in (city,country) if part and part not in ('—','Aranıyor…','Bilinmiyor')) or 'Bilgisayar konumu'
            return Location(pc[0],pc[1],label)
        return None

    @staticmethod
    def _place_in_question(question):
        q=normalize(question)
        match=re.match(r'(.{2,40}?)\s+(?:icin\s+)?(?:bugun\s+)?hava(?:\s+durumu)?',q)
        if match:
            value=match.group(1).strip()
            if value not in ('burada','bulundugum yerde','konumumda'):return value
        return None

    def request_weather(self,location_or_text,original_question=''):
        if self.weather_loading:
            self.write('🐝 Pilot Arı','Bir hava sorgusu zaten sürüyor. Sonuç geldiğinde burada göstereceğim.')
            return
        self.weather_loading=True;self.weather_question=original_question
        self.service_status.set('● GÜNCEL HAVA ALINIYOR…')
        self.send_button.configure(state='disabled')
        self.write('🐝 Pilot Arı','Güncel hava modeli alınıyor…')
        def worker():
            try:
                location=location_or_text if isinstance(location_or_text,Location) else (parse_location(location_or_text) or geocode(location_or_text))
                key=(round(location.latitude,3),round(location.longitude,3))
                cached=self.weather_cache.get(key)
                if cached and time.time()-cached['fetched_at']<600:
                    report=cached
                else:
                    report=fetch_current(location);self.weather_cache[key]=report
                self.weather_queue.put(('ok',report))
            except WeatherError as exc:self.weather_queue.put(('error',str(exc)))
            except Exception:self.weather_queue.put(('error','Hava bilgisi alınırken beklenmeyen bir sorun oluştu.'))
        threading.Thread(target=worker,daemon=True).start()

    def poll_weather(self):
        try:
            kind,value=self.weather_queue.get_nowait()
            self.weather_loading=False;self.send_button.configure(state='normal')
            if kind=='ok':
                answer=format_current(value)
                if any(word in normalize(self.weather_question) for word in ('ucus','uculur','uygun')):
                    answer+='\n\nDaha özel değerlendirme için İHA modelinin doğrulanmış azami rüzgâr/hamle sınırını ve uçuş amacını yaz. Bu sınırı bilmiyorsan üretici belgesinden kontrol etmeliyiz.'
                self.service_status.set('● HAVA GÜNCEL • '+value['current']['time'])
                self.advisor.remember('weather',answer);self.write('🐝 Pilot Arı',answer)
            else:
                self.service_status.set('● HAVA ALINAMADI • SOHBET HAZIR')
                self.advisor.pending='weather_location'
                self.write('🐝 Pilot Arı',value+' Şehir/ilçe veya “40.98, 29.05” biçiminde koordinat yazabilirsin; rüzgâr, hamle, yağış ve görüşü biliyorsan elle de yazabilirsin.')
            self.entry.focus_set()
        except queue.Empty:pass
        try:self.weather_job=self.app.root.after(150,self.poll_weather)
        except tk.TclError:self.weather_job=None

    def send(self):
        question=self.query.get().strip()
        if not question:return
        self.query.set('');self.write('Siz',question)
        q=normalize(question)
        if self.ai_enabled and (is_build_question(q) or self.advisor.pending=='component_inventory'):
            answer=self.advisor.build_reply(question)
            if answer:self.write('🐝 Pilot Arı • Donanım',answer);self.entry.focus_set();return
        if self.ai_enabled and (is_performance_question(question) or self.advisor.pending=='hardware_specs'):
            answer=self.advisor.hardware_reply(question)
            if answer:self.write('🐝 Pilot Arı • Hesap',answer);self.entry.focus_set();return
        if self.advisor.pending=='weather_location':
            if q in ('iptal','vazgec','bosver'):
                self.advisor.pending=None;self.write('🐝 Pilot Arı','Hava sorgusunu iptal ettim.')
            else:
                use_current=any(phrase in q for phrase in ('konumumu kullan','mevcut konum','iha konumu','cube konumu','bilgisayar konumu'))
                location=self._automatic_location() if use_current else question
                if use_current and location is None:
                    self.advisor.pending='weather_location'
                    self.write('🐝 Pilot Arı','Güncel Cube konumu veya izin verilmiş Windows konumu bulunamadı. Önce Uçuş ekranındaki “Konumumu bul” düğmesini kullanabilir ya da şehir/ilçe veya koordinat yazabilirsin.')
                else:
                    self.advisor.pending=None;self.request_weather(location,'hava durumu')
            self.entry.focus_set();return
        if self._weather_intent(question):
            explicit=parse_location(question) or self._place_in_question(question)
            location=explicit or self._automatic_location()
            if location is None:
                self.advisor.pending='weather_location'
                self.write('🐝 Pilot Arı','Hangi şehir veya ilçe için bakayım? İstersen “Düzce” ya da “40.84, 31.16” biçiminde koordinat yaz. Canlı Cube konumu veya Windows konumu varsa onu da kullanabilirim.')
            else:self.request_weather(location,question)
            self.entry.focus_set();return
        if self.ai_enabled:
            self.request_ai(question);self.entry.focus_set();return
        self.write('🐝 Pilot Arı',self.advisor.reply(question));self.entry.focus_set()

    def close(self):
        self.api_key='';self.ai_history.clear()
        for job in (self.weather_job,self.ai_job):
            if job:
                try:self.app.root.after_cancel(job)
                except tk.TclError:pass
