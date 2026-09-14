"""Small Turkish semantic layer for the offline Pilot Arı assistant."""
from __future__ import annotations

import re


# Input to these rules is already lowercase and ASCII-folded.  The rules map
# everyday wording to the canonical terms used by the deterministic flight
# advisor.  Longer/specific phrases come first.
PHRASE_RULES=(
    (r'\b(?:yer istasyonu|ground station|data link|veri linki|radyo linki)\b','telemetri'),
    (r'\b(?:uydu alicisi|uydu modulu|gnss modulu|koordinat modulu)\b','gps'),
    (r'\b(?:sarj seviyesi|pil seviyesi|kalan enerji|kalan sarj)\b','batarya seviyesi'),
    (r'\b(?:pil|lipo|li ion|li-ion)\b','batarya'),
    (r'\b(?:veri gelmiyor|yanit vermiyor|haberlesemiyorum|iletisim kuramiyorum|goremiyorum|okuyamiyorum)\b','calismiyor'),
    (r'\b(?:ayni noktada dursun|yerinde dursun|konumunu korusun|havada sabit kalsin|hover yapsin)\b','loiter'),
    (r'\b(?:yuksekligi korusun|irtifayi korusun|sadece irtifa tutsun)\b','alt_hold'),
    (r'\b(?:eve geri donsun|kalktigi yere (?:kendi )?(?:geri )?donsun|geri gelsin|home noktasina donsun)\b','rtl'),
    (r'\b(?:rotayi (?:kendi )?izlesin|noktalari takip etsin|gorevi kendi yapsin|otonom rotayi ucsun)\b','auto'),
    (r'\b(?:hedef konuma gitsin|belirli konuma gitsin|yer istasyonunun hedefine gitsin)\b','guided'),
    (r'\b(?:kendi inis yapsin|otomatik insin|bulundugu yere insin)\b','land'),
    (r'\b(?:dengede kalsin|devrilmesin|elle dengeli ucurayim|temel denge)\b','stabilize'),
    (r'\b(?:ucus beyni|otopilot karti|kontrol karti)\b','ucus kontrolcu'),
    (r'\b(?:motor surucusu|motor kontrolcusu)\b','esc'),
    (r'\b(?:hava hizi sensoru|hiz tupu)\b','airspeed pitot'),
    (r'\b(?:eve donus|geri donus modu)\b','rtl'),
    (r'\b(?:konum tutma modu|pozisyon tutma)\b','loiter'),
    (r'\b(?:irtifa tutma modu|yukseklik tutma)\b','alt_hold'),
    (r'\b(?:rota modu|gorev modu)\b','auto'),
    (r'\b(?:parca listesi|malzeme listesi|alisveris listesi)\b','donanim listesi'),
    (r'\b(?:ne almaliyim|neler almaliyim|ne lazim|neler lazim)\b','ne gerekli'),
    (r'\b(?:yeter mi|tam mi|hepsi var mi)\b','yeterli mi'),
    (r'\b(?:uyar mi|birbirine uyar mi|beraber calisir mi)\b','uyumlu mu'),
)

WORD_SYNONYMS={
    'enerji':'batarya','sarj':'batarya','pil':'batarya','yukseklik':'irtifa',
    'pozisyon':'konum','mevki':'konum','lokasyon':'konum','uydular':'gps',
    'navigasyon':'gps','otopilot':'ardupilot','haritalar':'harita','kameralar':'kamera',
    'arizali':'calismiyor','bozuk':'calismiyor','kopuk':'baglanmiyor','kesiliyor':'kopuyor',
    'donuyor':'yavas','kasiyor':'yavas','malzeme':'donanim','parcalar':'donanim',
    'agirligi':'agirlik','kutlesi':'agirlik','performansi':'performans','menzil':'ucus_suresi',
    'havada':'ucus','ucabilirmi':'ucabilir','ucarmi':'ucabilir','guvenlimi':'guvenli',
}

CANONICAL_ROOTS=('motor','batarya','telemetri','harita','kamera','pervane','servo','sensor','parametre',
                 'uyari','gorev','kanat','donanim','agirlik','konum','irtifa','guvenlik','kumanda','alici')
ROOT_SUFFIXES=('lar','ler','lari','leri','nin','dan','den','da','de','yi','yı','yu','yü','si','sı','su','sü',
               'im','ım','um','üm','in','ın','un','ün','e','a','i','ı','u','ü')

INTENT_KEYWORDS={
    'connection':('telemetri','com','baud','mavlink','radyo','baglanti'),
    'gps':('gps','here3','uydu','gnss','pusula','konum'),
    'battery':('batarya','voltaj','akim','mah','sarj'),
    'mode':('stabilize','alt_hold','loiter','auto','guided','rtl','land','mod'),
    'mission':('gorev','rota','waypoint','otonom'),
    'hardware':('donanim','motor','esc','pervane','servo','govde','kanat','alici'),
    'performance':('agirlik','itki','ucus_suresi','performans','kanat yuklemesi'),
    'safety':('guvenlik','failsafe','sanal cit','geofence','uyari','arm'),
    'map':('harita','uydu goruntusu','google','openstreetmap','koordinat'),
    'camera':('kamera','video','vtx','rtsp','fpv goruntu'),
    'setup':('kalibrasyon','firmware','parametre','kurulum','test'),
    'weather':('hava','ruzgar','yagmur','sis','gorus','sicaklik'),
}


def semantic_normalize(text):
    value=' '.join(str(text).split())
    for pattern,replacement in PHRASE_RULES:value=re.sub(pattern,replacement,value)
    words=[]
    for word in value.split():
        mapped=WORD_SYNONYMS.get(word)
        if mapped is None:
            mapped=word
            for root in CANONICAL_ROOTS:
                if word.startswith(root) and word[len(root):] in ROOT_SUFFIXES:
                    mapped=root;break
        words.append(mapped)
    return ' '.join(words)


def detect_intents(text):
    value=semantic_normalize(text);scores=[]
    for intent,keywords in INTENT_KEYWORDS.items():
        score=sum(2 if ' ' in key and key in value else 1 for key in keywords if key in value)
        if score:scores.append((score,intent))
    scores.sort(key=lambda item:(-item[0],item[1]))
    return tuple(intent for _,intent in scores)
