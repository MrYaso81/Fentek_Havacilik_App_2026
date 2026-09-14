# Fentek Havacılık — Önemli Eksikler

Bu liste 13 Eylül 2026 tarihinde mevcut kod, 133 otomatik test, operasyon ekranı denetimi ve sentetik Cube kabul testi incelenerek güncellendi. Testlerin geçmesi yazılım senaryolarını doğrular; gerçek uçağın uçuşa hazır olduğunu kanıtlamaz.

## 1. Gerçek uçuştan önce tamamlanması gerekenler

1. **Fiziksel Cube Orange + Here3 + SiK kabul testi**  
   USB ve telemetri bağlantısı, gerçek GPS fix, batarya monitörü, mod değiştirme, ARM engelleri, görev aktarımı, bağlantı kaybı ve yeniden bağlanma gerçek donanımla henüz uçtan uca doğrulanmadı.

2. **Kalibrasyonların fiziksel kabulü**  
   Jiroskop, düz seviye, altı yön ivmeölçer, pusula, RC, ESC ve hava hızı kalibrasyon komutları ana arayüzde birleştirildi. ACK ve durum izleme hazırdır; her akış gerçek Cube ve ilgili sensörle tamamlanıp sonuçları fiziksel olarak doğrulanmalıdır.

3. **Motor, servo ve çıkış eşlemesinin fiziksel kabulü**  
   USB yer kurulumu, DISARMED, pervane onayı, düşük güç/süre sınırları, otomatik servo nötrü, acil durdurma ve JSON eşleme raporu eklendi. Komutların gerçek çıkış sırası, dönüş yönü ve durdurma davranışı pervaneler sökülü güvenli stantta doğrulanmalıdır.

4. **Derin uçuş öncesi teşhis ve log inceleme**  
   Canlı güvenlik kapısı temel EKF, GPS, sensör, batarya, HOME ve sanal çit durumunu denetliyor. Ancak titreşim, IMU tutarsızlığı, pusula sapması, güç hattı dalgalanması ve ayrıntılı pre-arm teşhisi yok. DataFlash ve tlog indirme, grafik, tekrar oynatma ve olay zaman çizelgesi de eksik.

5. **Sanal çit planını Cube'a aktarma**  
   İhlal durumu okunuyor ve çokgen doğrulama kodu var; fakat kullanıcının çizdiği geofence'i karta yükleme, geri okuma ve birebir doğrulama tamamlanmadı.

6. **Firmware'e göre tam parametre metadata'sı**  
   Karttan liste alma, yedekleme, karşılaştırma, temel güvenli aralıklar, doğrulanmış değişiklik geçmişi ve çakışma kontrollü geri alma var. Eksik olanlar: firmware sürümüne özel tüm seçenekler/birimler, yeniden başlatma gereksinimi ve toplu geri alma.

7. **Gerçek SITL sürecinde arıza enjeksiyonu**  
   Yalnız yerel adrese bağlanan, ArduPilot kimliğini ve SIM_SPEEDUP parametresini doğrulayan SITL sayfası ile GPS, batarya, sensör, EKF, HOME ve fence güvenlik matrisi eklendi. ArduPilot SITL ayrıca kurulup başlatılmalı; firmware içinde gerçek arızayı üretip RTL/LAND sonucunu doğrulayan otomasyon hâlâ eksiktir.

## 2. Operasyon yeteneğindeki önemli eksikler

8. **Doğrudan kontrolün tamamlanması**  
   Mevcut sayfa yalnız basılı tutulan yön komutlarını MAVLink `MANUAL_CONTROL` ile gönderir. Gaz ekseni, joystick/gamepad eşleme, dead-zone, failsafe, bağlantı koptuğunda girdi bırakma testi ve araç türüne göre eksen profili eksiktir.

9. **Görev komutlarının genişletilmesi**  
   Waypoint, servo adımı ve RTL aktarımı; duraklatma, devam ve adıma geçme var. TAKEOFF, LAND, loiter süresi/turu, hız değiştirme, ROI, kamera tetikleme ve güvenli `Fly to here / GUIDED` akışı eksik.

10. **SiK radyo kurulum ve eşleme ekranı**  
    RSSI, gürültü, tampon, hata sayaçları ve yaklaşık paket kaybı gösteriliyor. Yer/hava radyosu ayarlarını okuma, iki modülün uyumunu karşılaştırma, kanal/ağ kimliği/seri hız denetimi ve eşleme yardımcısı yok.

11. **Arazi, engel ve hava sahası denetimi**  
    Harita rota uzunluğunu ve süreyi hesaplar; fakat rota boyunca arazi yüksekliği, engel açıklığı, irtifa referansı tutarlılığı, hava sahası ve NOTAM kontrolü yapmaz.

12. **Gelişmiş kamera operasyonu**  
    USB/RTSP/HTTP görüntü, PNG fotoğraf + JSON zaman/konum/görev etiketi, MP4 video, MAVLink fotoğraf tetikleme ve temel gimbal hedefi var. Eksik olanlar: gimbal yetenek keşfi, gerçek açı geri bildirimi, kamera ayar profilleri ve görev içi gelişmiş tetikleme.

13. **Firmware kurulum ve araç yapılandırma sihirbazı**  
    ArduPilot firmware yükleme/güncelleme, kart/araç türü kurulumu, frame ve çıkış düzeni seçimi ile sürüm uyumluluğu denetimi yok.

## 3. Faydalı fakat uçuşu engellemeyen eksikler

14. **Harita ve hava verisi**  
    Google Static uydu görüntüsü anahtar/kota/faturalandırmaya bağlı ve gerçek anahtarla uçtan uca denenmedi. Google Earth 3D fotogrametri yok. Çevrimdışı saha paketi, harita indirme yöneticisi ve rota koridoru önbelleği de bulunmuyor. Open-Meteo hava modeli var; METAR/TAF ve yerel anemometre verisiyle çapraz kontrol yok.

15. **Pilot Arı'nın sınırları**  
    Yerel dil/RAG sistemi teknik soruları, yazım hatalarını ve donanım hesaplarını ele alıyor. Genel ve uzun sohbet için bulut AI kullanıcının API anahtarına ve internetine bağlıdır. Pilot Arı salt okunurdur ve uçuş komutu göndermez.

16. **Dağıtım ve bakım**  
    Tek dosyalı kurucu, otomatik sürüm güncelleme, bozuk kurulum onarımı, ayar profilleri ve sürüm geçiş testi henüz yok.

## Önerilen uygulama sırası

1. Gerçek donanım kabul testi ve ayrıntılı teşhis/log ekranı.
2. Kalibrasyon merkezi ile motor/servo eşlemesini fiziksel donanımda kabul etme.
3. Tam firmware metadata'sı ve geofence aktarımı.
4. ArduPilot SITL içinde gerçek arıza enjeksiyonu.
5. Görev komutları, joystick ve SiK kurulum yardımcısı.
6. Kamera, harita/hava ve dağıtım iyileştirmeleri.

## Bu denetimde doğrulanan mevcut temel işlevler

- 133 otomatik test geçti.
- Operasyon sayfaları, kaydırma, rota düzenleme ve kısmi parametre listesi denetimi geçti.
- Sentetik kabul testi: ArduCopter 27 mod, ArduPlane 26 mod, 17 kritik telemetri alanı, 12 arıza senaryosu ve 261 MAVLink olayı geçti.
- Canlı GPS/batarya okuma, mod/ARM komut kapıları, görev ve rally aktarımını geri doğrulama, uyarılar, otomatik yeniden bağlanma, SiK kalite göstergeleri, kamera izleme ve Pilot Arı yazılımda bulunuyor.
