# Fentek Havacılık — Cube Orange Yazılım Test Raporu

**Tarih:** 15 Eylül 2026  
**Sonuç:** Yazılım ve sentetik MAVLink testleri başarılı; fiziksel Cube Orange kabul testi bekliyor.

## Başarılı kontroller

- 133/133 otomatik birim ve entegrasyon testi geçti.
- Cube/ArduPilot odaklı 15/15 ayrıntılı MAVLink testi geçti.
- ArduCopter araç tablosundaki 27 uçuş modu işlendi.
- ArduPlane araç tablosundaki 26 uçuş modu işlendi.
- 17 kritik telemetri alanı ve 261 sentetik MAVLink olayı işlendi.
- 12 güvenlik/arıza senaryosu beklenen şekilde engellendi.
- GPS dönüşümü, bağlantı adresleri, yeniden bağlanma ve bağlantı kapanınca komut temizleme geçti.
- Kalibrasyon komutları ile ARMED ve telemetri bağlantısında kalibrasyon engeli geçti.
- USB yer kurulumu dışında motor/servo çıkışlarının engellenmesi geçti.
- Korumalı motor/servo komutları, görev duraklatma ve görev adımı seçimi geçti.
- Kamera tetikleme ve gimbal açı sınırı testleri geçti.
- Operasyon sayfaları, kaydırma, rota düzenleme, kısmi parametre listesi ve yer testi düğmelerinin kilitli başlangıcı geçti.
- Ayrı Kalibrasyon merkezi sayfası, USB/telemetri bağlantı seçimleri ve uçuş ekranındaki hızlı erişim düğmesi geçti.

## Bu çalıştırmada bulunmayanlar

- USB taramasında yalnız Bluetooth COM3 ve COM4 görüldü.
- Cube Orange veya bilgisayara takılı yer telemetrisi algılanmadı.
- `127.0.0.1:5760` üzerinde ArduPilot SITL çalışmıyordu; yerel SITL bağlantısı bu nedenle reddedildi.

## Fiziksel kabul için gereken sonraki test

Cube Orange USB veri kablosuyla takıldıktan sonra uygulamadaki **Güvenlik → Gerçek Donanım Kabul Testi → USB yer testi** çalıştırılmalıdır. Ardından yer telemetrisi takılıp **Kablosuz telemetri / uçuş öncesi** aşaması yapılmalıdır. Bu testler salt okunur yürütülmeli; pervaneler sökülmeden motor, servo, ARM veya kalibrasyon denemesi yapılmamalıdır.

Bu rapor yazılım senaryolarını doğrular. Gerçek sensör, güç modülü, Here3, motor/servo çıkışları ve radyo bağlantısı fiziksel donanım bağlı olmadan doğrulanmış sayılmaz.
