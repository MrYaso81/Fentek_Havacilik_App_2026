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

## Hazırlanacak yazılımsal modüller

- [ ] Failsafe ayar ekranı
- [ ] AUTO görev başlatma/durdurma
- [ ] Tam parametre ekranı ve geri alma
- [ ] DataFlash/tlog indirme ve temel inceleme
- [ ] Geofence/rally planlama
- [ ] Joystick/RC ve kamera/gimbal komutları
- [ ] PX4 protokol profili
- [ ] SITL senaryoları ve hata enjeksiyon testleri

## Son fiziksel test sırası

1. Pervaneler sökülü: USB bağlantısı, heartbeat, GPS, parametre okuma.
2. Pervaneler sökülü: ARM/DISARM, mod ve görev aktarımı.
3. Servo mekanizmaları enerjisiz/ayrı güvenli stantta test.
4. Düşük irtifada, açık alanda failsafe ve RTL testi.
5. Log indirme ve görev/konum geri doğrulaması.

Uygulama gerçek donanım görülmeden ARM veya uçuş başlatmaz.
