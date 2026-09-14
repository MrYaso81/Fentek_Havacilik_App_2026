# Fentek Havacılık Simülasyon Kabul Raporu

Tarih: 13 Eylül 2026

Sonuç: **BAŞARILI — tanımlanan simülasyon kontrollerinin %100'ü geçti.**

## Kapsam

- ArduCopter: kartın araç türü tablosundaki 27 uçuş modunun gönderimi ve HEARTBEAT ile doğrulanması
- ArduPlane: kartın araç türü tablosundaki 26 uçuş modunun gönderimi ve HEARTBEAT ile doğrulanması
- Tanımsız uçuş modunun reddedilmesi
- ARM, AUTO görev başlatma, LOITER/görev durdurma ve DISARM sırası
- Parametre listesinin karttan alınması, indekslerinin tamamlanması, tür korunarak yazılması ve PARAM_VALUE ile geri doğrulanması
- GPS, WGS84/NED konum, irtifa, yönelim, güç, GPS doğruluğu, EKF, titreşim, RC, servo çıkışı, görev adımı ve sanal çit telemetrisi
- GPS 2D, düşük batarya, sensör arızası, başlatılmamış/eksik EKF, DISARMED AUTO, eski veri, kritik kart durumu, kritik PreArm mesajı, sanal çit ihlali ve HOME eksikliği güvenlik engelleri
- `ARMING_CHECK=0` ile tüm pre-arm kontrollerini kapatma girişiminin hem arayüzde hem komut katmanında reddedilmesi
- Dünya Haritası, Uydu Görüntüsü ve 3D Simülasyon görünümü
- Sol menü, telemetri kaydırma, rota düzenleme ve eksik parametre listesi göstergesi
- 133 otomatik birim/entegrasyon testi; canlı batarya, rally aktarımı, rota ölçümleri, Kablosuz Telemetri/RADIO_STATUS, Google Static uydu isteği, görev duraklatma/devam, görev adımı seçimi, kılavuz araması, parametre geçmişi/aralık denetimi, korumalı yer komutları ve SITL güvenlik matrisi dahil

Simülatör toplam 261 MAVLink olayını işledi ve 12 ayrı arıza/engel senaryosunu doğruladı. Tüm test süreçleri fiziksel COM portu açmadan çalıştırıldı.

## Sonucun sınırı

Bu rapordaki %100, yalnız yukarıdaki tanımlı yazılım senaryolarının tamamının geçtiği anlamına gelir. Cube Orange donanımı, Here3 anteni, gerçek ArduPilot firmware sürümü, CAN hattı, telemetri radyosu, güç sistemi, servo/motor bağlantıları, RF kopması ve açık alan GNSS davranışı simülasyonla kanıtlanamaz.

Fiziksel uçuş güvenilirliği için pervaneler sökülüyken USB testi, ardından güvenli stant testi ve kontrollü açık alan testi ayrıca yapılmalıdır. Kartın kendi pre-arm denetimi her zaman son kararı verir.

ArduPilot SITL bağlantı istemcisi ve güvenlik hata matrisi ayrıca hazırdır. Bu rapordaki sentetik Cube testi gerçek ArduPilot SITL değildir; gerçek firmware testi için yerel SITL süreci ayrıca başlatılmalıdır.

## Yeniden çalıştırma

`SIMULASYON_TESTI.bat` dosyasına çift tıklayın. Başarılı çalışmada `PASS`, `OK` ve arayüz kontrolü sonucu görünür.
