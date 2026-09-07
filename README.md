# Fentek Havacılık

## Konum, yerel koordinatlar ve ARM durumu

Sağ alt panel bilgisayar konumundan çözümlenen şehir ve ülkeyi gösterir. X doğu, Y kuzey ve Z irtifa eksenidir; metre cinsinden uçuş başlangıç noktasına göre hesaplanır. Bilgisayar konumu alınırsa sentetik uçuş başlangıcı bu konuma taşınır. Yer adı OpenStreetMap Nominatim servisinden bir kez alınır; konum izni veya internet yoksa ilgili alanlarda hata durumu gösterilir.

90 saniyelik sentetik uçuş döngüsü yerde bekleme, kalkış, seyir, iniş ve tekrar yerde bekleme aşamalarını içerir. Araç yükseldiğinde sağ panel `ARM • UÇUŞTA`, indiğinde `DISARM • YERDE` gösterir. Her geçiş olay günlüğüne zaman damgasıyla eklenir. Bu değerler demo davranışıdır; henüz Cube Orange ARM durumunu okumaz veya karta ARM komutu göndermez.

## Üç ayrı harita sistemi

**Dünya Haritası**, kök dizindeki `app.py` ile aynı OpenStreetMap döşeme kaynağını kullanır. **Uydu Görüntüsü**, masaüstündeki `index.html` ile aynı Esri World Imagery kaynağını kullanır. **Simülasyon Haritası (3D)** internet olmadan sentetik uçuş alanını çizer. Harita kaynakları birbirinden ayrı seçilir; gerçek haritalardaki İHA hareketi şimdilik sentetik veridir.

Duraklat, Baştan başlat, Bağlantı kaybını dene ve İHA'yı merkezle düğmeleri uçuş ekranının üstündeki sabit kontrol çubuğuna taşındı. Böylece Demo kontrolleri sekmesi görünmese bile temel demo kontrollerine ulaşılır.

## Harita kontrolleri

OpenStreetMap ve uydu görünümünde fareyle kaydırma ve imlecin bulunduğu noktaya tekerlekle yaklaşma çalışır. Görüntüler yedi gün yerel önbellekte tutulur. Uydu katmanı canlı kamera yayını değildir; harita sağlayıcısının güncellediği görüntü döşemeleridir.

Harita parçaları merkeze en yakın görüntüden başlayarak eşzamanlı yüklenir; Esri uydu görünümünde dört, OpenStreetMap görünümünde iki indirme işçisi kullanılır. Önceden alınan parçalar ağ isteği olmadan önbellekten açılır. Nokta kontrolleri ayrı bir satırdadır: son nokta silinebilir, bütün noktalar temizlenebilir veya bir nokta haritada sağ tıklanarak kaldırılabilir.

Alt harita çubuğu küçük, tek satırlı düğmeler kullanır. Haritanın sağ üstündeki Yerel Koordinat panelinde X, Y ve Z metre değerleri düzenlenebilir. `İHA’dan al` mevcut sentetik konumu alanlara getirir, `Nokta koy` X/Y değerlerini uçuş başlangıcına göre harita konumuna çevirir ve Z değerini noktanın irtifası olarak saklar. `Kopyala` üç değeri birlikte Windows panosuna gönderir.

Harita sağlayıcısının görünür atfı büyük bir şerit yerine sol alttaki küçük kaynak etiketinde gösterilir. Etikete tıklanınca OpenStreetMap, ODbL, OSM döşeme kuralları, Esri World Imagery sağlayıcıları, Nominatim ve uygulama kullanım notlarını içeren `Harita Kaynakları ve Lisanslar` penceresi açılır. Aktif haritaya göre görünür kısa atıf otomatik değişir.

Simülasyon görünümünde fareyle kamera döndürme, akıcı tekerlek yakınlaştırması ve İHA türü simgeleri çalışır.

## 3D görünüm, bilgisayar konumu ve İHA profilleri

Güncel **flight_pro.py** sürümü varsayılan olarak OpenStreetMap görünümüyle açılır. Üstteki harita seçicisinden uydu görüntüsüne veya 3D simülasyona geçilir. 3D görünüm gerçek Google 3D uydu/fotogrametri verisi değildir.

İHA türü Sabit kanat, Döner kanat veya FPV olarak seçilebilir; harita simgesi buna göre değişir. Bu seçim şimdilik sentetik profil ve görünüm içindir, gerçek Cube Orange çerçeve ayarını değiştirmez.

Bilgisayar konumumu bul düğmesi yalnız kullanıcı bastığında Windows konum servisini bir kez çağırır. Windows konum izni kapalıysa veya cihaz konum üretemezse demo konumu korunur. Windows konumu GPS, Wi-Fi, hücresel ağ, IP adresi veya sistemdeki varsayılan konumdan gelebilir; gösterilen doğruluk yaklaşık değerdir. Konum dosyaya kaydedilmez.

## Canlı uçuş merkezi

Güncel **cockpit.py** ekranında harita ortada, uçuş/konum tablosu solda ve sistem/telemetri tablosu sağdadır. Harita işareti dört motorlu İHA şeklindedir. Sağ paneldeki denge modu düğmesi sentetik uçuşu STABILIZE ve MANUAL arasında değiştirir; yapay ufukta yatış ve yunuslama etkisi görülür. Bu düğme henüz Cube Orange'a MAVLink uçuş modu komutu göndermez ve gerçek uçuşta kullanılmamalıdır.

## Harita fare kontrolleri

Harita üzerinde sol tuşu basılı tutup sürükleyerek görünümü kaydırabilirsiniz. Fare tekerleği imlecin bulunduğu noktaya yakınlaştırır veya uzaklaştırır. Haritaya çift tıklamak görünümü sentetik İHA'nın son konumuna getirir. İşaret ekleme açıkken sol tıklama haritayı sürüklemek yerine numaralı not noktası ekler.

## Kurulum ve test laboratuvarı

Güncel başlatıcı **workbench.py** dosyasını açar. Kurulum ve test sekmesinde altı yön ivmeölçer ve jiroskop demo adımları, temsili çift motor düzeninde sol/sağ motor testi, %0–100 gaz yüzdesi ve 1–10 saniye süre seçimi vardır. Süre dolunca veya demo bağlantısı kesilince görsel motor testi durur. Bunlar yalnız simülasyondur; hiçbir motor/kalibrasyon MAVLink komutu gönderilmez. Gaz yüzdesi ölçülmüş elektriksel güç değildir. Gerçek motor numaraları ve donanım çıkışları eşlenmiş değildir.

Parametre ekranı yalnız DEMO_ isimli uygulama değerlerini doğrular, oturuma uygular ve istenirse JSON olarak kaydeder. ArduPilot parametre listesi veya karta yazma özelliği değildir. Düşük batarya eşiği uygulanırken mevcut sentetik değerle karşılaştırılır. Gerçek donanım desteği ayrıca kart tipi, firmware ve çıkış düzeni üzerinden doğrulanmalıdır.

Referans alınan akışlar: https://github.com/ArduPilot/MissionPlanner/blob/master/GCSViews/ConfigurationView/ConfigMotorTest.cs ve https://ardupilot.org/dev/docs/mavlink-calibration.html . Arayüz özgün siyah-sarı tasarımı kullanır.

## Güncel siyah-sarı okul arayüzü

BASLAT.bat, okul logosunu kullanan **enhanced.py** masaüstü demosunu açar. Altı sekme: uçuş ekranı, telemetri, harita ayarları, demo kontrolleri, uçuş analizi ve olay günlüğü. Analiz son 120 örneği gösterir. Haritaya en fazla 10 numaralı not noktası eklenebilir; bunlar uçuş rotası veya araca gönderilen komut değildir. İz görünürlüğü değiştirilebilir. Günlük en son 300 olayı bellekte tutar; yalnız Kaydet ile dosyaya yazılır. Ana ekran sentetik verilerle çalışır. Google görüntüsü için API anahtarı gereksinimi sürer.

## Donanım olmadan çalışan yeni demo

**BASLAT.bat** artık **demo.py** dosyasını açar. Bu masaüstü demo Python 3.12'nin standart kütüphanesiyle çalışır; MAVLink paketleri, cihaz veya internet gerekmez. Hareketli sentetik İHA, rota izi, irtifa, hız, batarya, uydu sayısı ve yönelim gösterir. Duraklatma, sıfırlama, bağlantı kaybı denemesi ve CSV kayıt düğmeleri vardır. CSV kayıtları SYNTHETIC_DEMO olarak etiketlenir; en son 3600 örnek tutulur. Google görüntüsü yüklenmezse çizilen zemin şematik demo haritadır.

Google uydu görüntüsü düğmesi Maps Static API anahtarıyla görüntüyü uygulamanın içine yükler. Google projesinde API ve faturalandırma etkin olmalıdır; kullanım ücret doğurabilir. Anahtar kaydedilmez; otomatik/tekrarlayan Google isteği gönderilmez. Bu canlı uydu yayını veya gerçek İHA tespiti değildir; uydu fotoğrafı üzerinde sentetik uçuş gösterilir. Görüntüye çift tıklamak Google Haritalar bağlantısını açar; normal demo çalışmasında tarayıcı açılmaz. API anahtarı olmadığı için Google servisinden görüntü alma uçtan uca test edilmedi.

Anahtarı Windows ortam değişkeni olarak `GOOGLE_MAPS_API_KEY` adıyla tanımlarsanız pencere anahtarı otomatik doldurur; anahtar dosyaya yazılmaz. Harita görüntüsünün üzerine sentetik İHA işareti ve rota izi çizilir. ZIP içindeki Google uydu katmanı yaklaşımı bu akışa uyarlanmıştır.

Gerçek bağlantılı önceki sürümü açmak için **GERCEK_BAGLANTI.bat** kullanılır. Aşağıdaki bağlantı ve kalibrasyon yönergeleri bu gerçek bağlantı sürümü içindir.

Cube Orange + Here3 için masaüstü MAVLink yer istasyonu **station.py** üzerinden çalışır. Eski app.py, ekran bileşenleri için kullanılan önceki USB sürümüdür.

## Başlatma

Python 3.12 ile uyumludur. BASLAT.bat dosyasına çift tıklayın. Bağımlılıklar bulunamazsa KUR.bat çalıştırın. Bu bilgisayarda gerekli paketler vendor klasörüne de indirilmiştir; bunlar Windows Python 3.12 içindir. Farklı Python sürümlerinde kendi ortamınıza requirements.txt paketlerini kurun ve vendor klasörünü kullanmayın.

## USB ile yerde kurulum

1. Cube Orange'ı USB veri kablosuyla bağlayın. Here3 üretici kılavuzuna uygun CAN bağlantısıyla takılmış ve beslenmiş olmalı; ArduPilot GPS ayarları yapılmış olmalı.
2. Mission Planner gibi aynı COM portunu kullanan uygulamaların bağlantısını kapatın.
3. Seri / USB, kartın COM portu ve 115200 seçin. USB ile yerde kurulum kutusunu işaretleyip Bağlan'a basın.
4. Kalibrasyon penceresinde jiroskop, düz seviye veya altı yön ivmeölçer kalibrasyonunu seçin. Araç DISARMED olmalı. Masa testinde pervaneleri sökün. Kartın istediği yönü yerleştirip sabitken Devam'a basın. Kart yanıtları ve sonucu ekranda gösterilir.

Pusula, radyo, ESC ve hava hızı kalibrasyonları bu sürüme dahil değildir. Komut kabulü, altı yön kalibrasyonunun tamamlandığı anlamına gelmez; kartın başarı sonucunu bekleyin. Yanıt kesilirse başarı varsayılmaz. Kalibrasyon komutları yeniden bağlanınca otomatik tekrarlanmaz. Yarım kalan kalibrasyonda kart durumunu kontrol edip gerekirse yerde yeniden başlatın. Uygulama motor çalıştırma veya uçuş komutu göndermez.

## Telemetriye geçiş

Uçaktaki MAVLink uyumlu radyo modülü Cube Orange'ın uygun TELEM bağlantısına; yerdeki modül bilgisayara bağlanır. Radyoların eşleşmesi, gerilimleri ve kartın seri protokol/hız ayarları modele göre yapılmalıdır. Uygulama tüm cihazları otomatik yapılandırmaz.

Alıcının COM portunu ve üreticinin seri hızını seçin (örneğin 57600, fakat bu evrensel değildir). USB ile yerde kurulum işaretini kaldırın. **Seçili bağlantıya geç** düğmesi eski bağlantıyı kapatıp seçili bağlantıyı açar. Bu geçiş sıfır kesinti garantisi vermez. Ayar seçenekleri yeni bağlantı açılırken uygulanır.

## Ağ bağlantıları

- UDP dinle: yerel IP:port; örnek `0.0.0.0:14550`. Verici bilgisayarın erişilebilir IP adresine ve bu porta MAVLink göndermelidir.
- UDP gönder: karşı cihaz IP:port; örnek `192.168.1.20:14550`.
- TCP: karşı cihaz IP:port; örnek `192.168.1.20:5760`. Karşıda TCP sunucusu çalışmalıdır.

UDP/TCP seçenekleri MAVLink verisi taşıyan Wi-Fi/Ethernet/hücresel köprüler içindir. Modemlerin ağa bağlanması ve güvenlik duvarı yapılandırması ayrıca yapılır. IPv6 adres biçimi bu sürümde desteklenmez.

## Kopma ve konum

Kartın yaşam sinyali 6 saniye kesilirse bağlantı kayıp gösterilir. Yeniden bağlan seçeneği aynı adreste 2–10 saniye aralıkla dener; farklı COM portlarını rastgele seçmez. Aynı oturumda ilk bağlanılan MAVLink sistem/bileşen kimliği korunur. Manuel bağlantı geçişi yeni oturum açar.

5 saniyedir yenilenmeyen alanlar güncel değil olarak işaretlenir. Son geçerli konum ve kaç saniye önce alındığı korunur; ayrı düğmeyle açılır. Geçersiz GPS sabitlenmesinde eski konum güncel gösterilmez. Bu zaman, bilgisayara ulaşma zamanıdır; GNSS ölçüm zamanının bağımsız doğrulaması değildir. GPS irtifası deniz seviyesine göredir.

Google Haritalar düğmeye basıldığı andaki koordinatı tarayıcıda açar. Uygulamanın içinde canlı Google haritası bu sürümde yoktur. Google haritasını yüklemek için internet gerekir; Here3'ün konum ölçümü internet gerektirmez.

## Doğrulama

`python -m unittest discover -s cube_station -p test_station.py` ile bağlantı biçimleri, GPS dönüşümleri, kalibrasyon komutları, armed engeli, yeniden bağlanma ve komut kuyruğu temizliği test edilir (üst klasörden). Gerçek Cube Orange/Here3 ve radyo modülüyle donanım doğrulaması henüz yapılmadı.

Kaynaklar: https://mavlink.io/en/messages/common • https://mavlink.io/en/mavgen_python/ • https://ardupilot.org/dev/docs/mavlink-calibration.html
