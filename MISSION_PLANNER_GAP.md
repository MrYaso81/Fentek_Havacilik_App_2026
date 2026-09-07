# Mission Planner karşılaştırması

Bu proje şu anda güvenli bir telemetri ve görev planlama prototipidir. Mission Planner'ın resmi özellik listesiyle karşılaştırma:

## Hazır olanlar

- ArduPilot MAVLink bağlantısı (USB/seri, UDP, TCP)
- GPS, küresel WGS84 ve yerel NED konum gösterimi
- Dünya/uydu haritası ve rota işaretleri
- Waypoint + RTL görev yükleme ve geri okuma doğrulaması
- DO_SET_SERVO görev komutu
- ARM/DISARM düğmesi (canlı bağlantı ve onay kilidi)
- Temel telemetri, bağlantı eskimesi ve yeniden bağlanma

## Eksik veya doğrulanması gerekenler

- Failsafe parametrelerinin kullanıcı arayüzü (çekirdek hazır)
- Uçuş modu seçme ve karttan mod doğrulama
- AUTO görevi başlatma, durdurma ve mevcut waypoint'i değiştirme
- Tam parametre listesi, parametre dosyası karşılaştırma ve geri alma
- RC/joystick girişi ve manuel kumanda
- Servo/relay canlı test ekranı
- DataFlash/tlog indirme, oynatma ve grafik analizi
- GeoFence ve rally/safe point planları
- Takeoff, land, guided/fly-to-here ve kamera komutları
- Firmware yükleme/güncelleme ve donanım kurulum sihirbazı
- EKF, pre-arm, sensör, titreşim ve güç durumu teşhis ekranları
- Video/MJPEG, kamera ve gimbal yönetimi
- PX4 görev/failsafe uyumluluğu
- Gerçek Cube Orange, GPS ve servo donanımı üzerinde saha doğrulaması

Mission Planner'ın resmi Flight Data sayfası; mod değiştirme, ARM/DISARM, joystick, görev kontrolü, servo/relay, log ve harita komutlarının ayrı işlevler olduğunu belirtir. Bu listedeki maddeler tamamlanmadan uygulama tam Mission Planner karşılığı sayılmamalıdır.
