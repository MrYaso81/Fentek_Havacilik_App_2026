# Uçuşa hazırlık planı

## Yazılımsal hazırlık

- [x] MAVLink ArduPilot bağlantısı
- [x] GPS WGS84 ve yerel NED koordinatları
- [x] Canlı harita ve son konum göstergesi
- [x] Waypoint + RTL görev aktarımı ve geri doğrulama
- [x] DO_SET_SERVO görev komutu
- [x] ARM/DISARM güvenlik onayı
- [x] Uçuş modu seçimi ve kritik mod onayı
- [x] Failsafe parametreleri için güvenli istemci çekirdeği
- [x] Bağlantı kaybı ve eski veri göstergesi
- [x] Cihazsız otomatik testler
- [x] Görev duraklatma/devam ve görev adımı seçimi
- [x] Rally noktası planlama, MAVLink 2 aktarım ve geri doğrulama
- [x] SiK RADIO_STATUS bağlantı kalitesi göstergeleri
- [x] Harita mesafe, alan, rota ve süre ölçümleri
- [x] Yerde failsafe yapılandırma senaryosu
- [x] Salt okunur USB/SiK gerçek donanım kabul testi ve raporu
- [x] Parametre yazma geçmişi, doğrulamalı geri alma ve temel güvenli aralıklar
- [x] USB yer kurulumunda gerçek kalibrasyon komut merkezi
- [x] Korumalı motor/servo çıkış testi, nötre dönüş ve acil durdurma
- [x] Kamera fotoğraf/video kaydı, gimbal hedefi ve MAVLink tetikleme
- [x] Yerel ArduPilot SITL tanıma ve güvenlik hata matrisi

## Hazırlanacak yazılımsal modüller

- [x] Failsafe ayar ve yerde senaryo ekranı
- [x] AUTO görev başlatma/duraklatma/devam/durdurma
- [ ] Firmware sürümünden indirilen tam parametre metadata'sı ve toplu geri alma
- [ ] DataFlash/tlog indirme ve temel inceleme
- [ ] Geofence çokgen aktarımı (rally planlama tamamlandı)
- [ ] Tam gaz eksenli joystick/gamepad ve RC eşleme
- [ ] PX4 protokol profili
- [ ] Gerçek ArduPilot SITL sürecinde uçtan uca hata enjeksiyonu ve rapor

## Son fiziksel test sırası

1. Pervaneler sökülü: USB bağlantısı, heartbeat, GPS, parametre okuma.
2. Pervaneler sökülü: ARM/DISARM, mod ve görev aktarımı.
3. Servo mekanizmaları enerjisiz/ayrı güvenli stantta test.
4. Düşük irtifada, açık alanda failsafe ve RTL testi.
5. Log indirme ve görev/konum geri doğrulaması.

Uygulama gerçek donanım görülmeden ARM veya uçuş başlatmaz.
