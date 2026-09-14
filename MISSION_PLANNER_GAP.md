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
- Görev duraklatma/devam ve belirli görev adımına geçme
- Rally noktası planlama, MAVLink 2 aktarım ve geri okuma
- SiK RADIO_STATUS bağlantı kalitesi ve yaklaşık paket kaybı
- Rota mesafesi, alan ve yaklaşık süre ölçümleri
- Google Maps Static API uydu görünümü (kullanıcı anahtarıyla)
- Parametre değişiklik geçmişi, doğrulamalı geri alma ve temel aralık denetimi
- USB yer kurulumunda pusula/IMU/RC/ESC/hava hızı kalibrasyon komutları
- Korumalı motor ve servo çıkış testi, eşleme kaydı ve acil durdurma
- PNG fotoğraf, MP4 video, MAVLink fotoğraf tetikleme ve temel gimbal hedefi
- Yerel ArduPilot SITL tanıma ve uygulama güvenlik hata matrisi

## Eksik veya doğrulanması gerekenler

- Failsafe sayısal seçeneklerinin firmware metadata ile adlandırılması
- Firmware sürümünden alınan eksiksiz parametre metadata'sı, yeniden başlatma işaretleri ve toplu geri alma
- Tam gaz eksenli joystick/gamepad girişi; mevcut doğrudan kontrol yalnız basılı yön MANUAL_CONTROL komutları gönderir
- Relay çıkış testi ve donanıma göre gelişmiş servo işlev keşfi
- DataFlash/tlog indirme, oynatma ve grafik analizi
- GeoFence çokgen aktarımı; rally planlama tamamlandı
- Takeoff, land, guided/fly-to-here ve görev içi gelişmiş kamera komutları
- Firmware yükleme/güncelleme ve donanım kurulum sihirbazı
- EKF, pre-arm, sensör, titreşim ve güç durumu teşhis ekranları
- Gimbal yetenek keşfi, gerçek açı geri bildirimi ve gelişmiş kamera ayarı
- PX4 görev/failsafe uyumluluğu
- Gerçek Cube Orange, GPS ve servo donanımı üzerinde saha doğrulaması
- Gerçek ArduPilot SITL sürecinde otomatik uçtan uca arıza enjeksiyonu

Mission Planner'ın resmi Flight Data sayfası; mod değiştirme, ARM/DISARM, joystick, görev kontrolü, servo/relay, log ve harita komutlarının ayrı işlevler olduğunu belirtir. Bu listedeki maddeler tamamlanmadan uygulama tam Mission Planner karşılığı sayılmamalıdır.
