# Fentek Havacılık

## Güncel operasyon bölümleri

Sol menüye Uçuş modu özellikleri, Görev planlama, Parametreler, Güvenlik, Yardımcı donanım ve Bilgi ve Kılavuz eklendi. Sol menü ve sayfalar fare tekerleğiyle kayar. Telemetri sayfasındaki ölçümler gerçek karttan gelir; eksik veriler boş, üç saniyeden eski veriler ESKİ olarak gösterilir.

- Uçuş modları kartın araç türüne göre seçilir; mod isteği yaşam sinyalinden doğrulanır. Listede olmak firmware'in mod değişikliğini mutlaka kabul edeceği anlamına gelmez.
- Donanım bağlı değilken uçuş modu listesi boş kalmaz: Döner kanat, Sabit kanat veya FPV seçimine göre temel demo seçenekleri gösterilir. Cube bağlandığında bu liste kartın araç türü için bildirdiği gerçek ArduPilot mod tablosuyla değiştirilir.
- Görev planında uygulamaya ait 10 nokta sınırı yoktur; noktalar düzenlenebilir, sıralanabilir, silinebilir ve HOME_RELATIVE JSON dosyasına kaydedilip açılabilir. Karta aktarılabilecek gerçek sayı Cube belleği, ArduPilot sürümü ve MAVLink görev kapasitesine bağlıdır. Aktarım ekranı waypoint + servo + RTL yükler ve geri okur; kart kapasiteyi reddederse görev başarılı sayılmaz.
- Parametre listesi karttan istenir; eksik indeksler tekrar istenir, 45 saniyede tamamlanmayan liste eksik gösterilir. Dosya karşılaştırması yalnız taslak oluşturur. Tek tek yazma, mevcut oturumda karttan okunmuş parametrelerle ve DISARMED ArduPilot ile sınırlıdır. Tür/sayısal temsil kontrol edilir; PARAM_VALUE cevabı eşleşmeden başarı gösterilmez. Doğrulanan değişiklikler oturum geçmişine kaydedilir ve karttaki güncel değerle çakışma yoksa geri alınabilir. Batarya, sanal çit, RC ve servo gibi bilinen alanlarda korumalı yerel aralık denetimi uygulanır; sürümü bilinmeyen parametreye aralık uydurulmaz.
- Güvenlik kontrolünde güncel heartbeat, ArduPilot kimliği, kart çalışma durumu, GPS, batarya, SYS_STATUS sensör sağlığı, kritik STATUSTEXT uyarıları, EKF ve sanal çit durumu değerlendirilir. Navigasyon modları güncel konum ve eksiksiz EKF navigasyon çözümü ister; AUTO/görev/RTL ayrıca ARM ve HOME konumu ister. Aynı kontroller komut gönderim katmanında da uygulanır. `ARMING_CHECK=0` ve etkin `ARMING_SKIPCHK` yazımları uygulama tarafından reddedilir. Bu kontroller uçuş sertifikası değildir; kartın kendi pre-arm kontrolü son kararı verir.
- Güvenlik ve yardımcı donanım sayfaları mevcut kart parametrelerini FS, BATT, RTL, FENCE, ARMING, GPS, CAN, SERIAL, SERVO, RC ve ARSPD gruplarına filtreler. CAN düğüm taraması/firmware yükleyicisi veya fiziksel motor testi içermez.
- Canlı bağlantıda ana Sistem Durumu paneli kartın bildirdiği batarya yüzdesini ve voltajını, ayrıca mevcutsa akımı ve tüketilen mAh değerini gösterir. Değerler güç modülü/batarya monitörü ölçümünden gelir; uygulama eksik ölçümü tahmin etmez.
- Bilgi ve Kılavuz sayfasında hızlı başlangıç, ana düğmeler, uçuş modları, güvenlik göstergeleri, haritalar ve telemetri açıklanır. Aranabilir parametre sözlüğü kritik parametreleri açıklar; bilinmeyen firmware parametreleri için tahminde bulunmaz. Parametreler sayfasındaki seçili kayıttan doğrudan sözlüğe geçilir.
- Tek İHA için Doğrudan kontrol sayfası MAVLink MANUAL_CONTROL yön komutları gönderir. Gaz ekseni gönderilmez; canlı ARMED ArduPilot, MAV_OPTIONS bit 0, GCS kimliği 255 ve basılı tutma kilidi gerekir. Düğme bırakılınca eksenler serbest bırakılır.
- Ölçüm araçları iki nokta mesafesi, rota ayakları, toplam rota, kapalı alan ve seçilen yatay hıza göre yaklaşık süre hesaplar.
- Rally / Güvenli iniş sayfası rally noktalarını düzenler, JSON olarak saklar ve MAVLink 2 üzerinden DISARMED karta yükleyip geri okur. Rally davranışı kartın RALLY parametrelerine bağlıdır.
- Görev planlamada duraklat, devam et ve belirli görev adımına geç kontrolleri bulunur. Adım değişikliği MISSION_CURRENT geri bildirimiyle doğrulanır.
- Kablosuz Telemetri sayfası SiK radyonun RADIO_STATUS verisinden yerel/uzak RSSI, gürültü, aktarım tamponu, hata/düzeltme sayaçları ve MAVLink sıra boşluklarından yaklaşık paket kaybını gösterir.
- Güvenlik sayfasındaki yerde senaryo testi gerçek bağlantıyı kesmeden ilgili failsafe parametresinin karttan okunup okunmadığını gösterir; gerçek failsafe tetiklemez.
- Güvenlik sayfasındaki Gerçek Donanım Kabul Testi, USB yer testi ve Kablosuz telemetri/uçuş öncesi aşamalarında canlı Cube verisini salt okunur olarak denetler. Kritik alanlar beş saniye kesintisiz uygun kalmadan UYGUN sonucu vermez; sentetik veri kabul edilmez ve sonuç metin raporu olarak kaydedilebilir.
- Google Uydu görünümü Maps Static API kullanır. Anahtar yalnız oturum belleğinde veya GOOGLE_MAPS_API_KEY ortam değişkeninden alınır; dosyaya yazılmaz. Google API etkinliği, kota ve faturalandırma kullanıcı hesabına bağlıdır.
- Uyarılar sayfası canlı telemetri kaybı, GPS 3D fix kaybı, düşük/kritik batarya, zayıf SiK bağlantısı, yüksek MAVLink paket kaybı, gerçek FENCE_STATUS ihlali ve kritik Cube mesajlarını renkli olarak gösterir. Yeni uyarıda kısa bir “dit-dit-dit” alarmı çalar; kritik alarmın tonu daha yüksek ve son sesi daha uzundur. Ses ayrı bir iş parçacığında çaldığı için arayüzü bekletmez. Susturma yalnız sesi kapatır ve geçmiş kaydını durdurmaz.
- Kamera görüntüsü sayfası USB Kamera 0/1 ile RTSP, HTTP ve HTTPS ağ kamerası yayınlarını gösterir. Kamera uygulama açılırken kendiliğinden başlamaz; yayın adresi dosyaya kaydedilmez. Görüntü alma ayrı iş parçacığında çalışır. PNG fotoğraf yanında zaman, taze konum ve görev adımı bilgisi JSON etiketiyle; video MP4 olarak kaydedilebilir. Canlı Cube bağlantısında kullanıcı onayıyla gimbal hedefi ve tek fotoğraf tetikleme komutu gönderilebilir. Test görüntüsü gerçek kamerayı açmadan arayüzü doğrular; fiziksel kamera ve gimbal desteği kendi donanımıyla ayrıca sınanmalıdır.
- Cube bağlantısı penceresi açıkken otomatik USB seçeneği COM portlarını ve yaygın telemetri hızlarını tarar. ArduPilot heartbeat ve araç kimliği doğrulanmadan bağlantıyı başarılı göstermez. Kopunca önce aynı portta yeniden bağlanır; 25 saniyeyi geçen kesintide Windows yeni COM numarası verdiyse USB keşfine döner.
- Pilot Arı varsayılan olarak yerel çalışır. Yerel mod son sekiz soru/yanıtı hatırlar; “bunu kısaca özetle”, “adım adım anlat” ve “örnek ver” gibi devam isteklerini önceki konuya göre yanıtlar. Türkçe karakter eksikleri, harf atlama/değiştirme, çift harf, komşu harflerin yer değiştirmesi, yanlış ek, kelimeye yapışan noktalama ve bitişik yazılmış alan ifadeleri iç niyet metninde düzeltilir; kullanıcının ekranda görünen asıl mesajı değiştirilmez. Düzeltici Damerau-Levenshtein yakınlığını, sık hata eşlemelerini, Türkçe ek ayırmayı ve alan sözlüğünü birlikte kullanır. Sözlük günlük konuşma; Cube/Here3; GPS/EKF/IMU; MAVLink/SiK/COM; uçuş modları; görev/waypoint; harita/konum; motor/ESC/pervane/batarya; ağırlık/itki/süre; kamera/sensör ve failsafe/güvenlik terimlerini kapsar. `telemteri baglanmyo`, `batrya gostrgesi gorunmyo`, `Orance Cub ve Her3`, `gpss sinyli gelymi`, `ucusmodnu loytera alabilrmym`, `ardupolt mavlnk firmwere` ve `uyduharitasi cok yvas yuklenmyo` gibi hatalı yazımlar doğru teknik akışlara yönlendirilir. Aynı uzun mesajdaki telemetri, GPS ve batarya sorunlarını ayrı başlıklarla ele alır; belirsiz sorularda önceki mesajı kaybetmeden konu sorar ve daha geniş günlük sohbet kalıplarını tanır. “AI ayarları” ekranında kullanıcının kendi OpenAI API anahtarı ve açık veri onayıyla GPT-5.4 mini veya GPT-5.4 nano etkinleştirilebilir. Bulut modunda son 12 kısa sohbet ve kesin konum içermeyen sınırlı Cube durum özeti kullanılır; `store=false` gönderilir. API anahtarı dosyaya yazılmaz, tam koordinat/COM portu/tam olay günlüğü paylaşılmaz ve pencere kapanırken anahtar bellekten temizlenir. Bulut servisi kullanılamazsa gelişmiş yerel Pilot Arı otomatik yanıt verir. Güncel hava isteği ayrı Open-Meteo akışıyla çalışır. Hem yerel hem bulut modu salt okunurdur; karta ARM, uçuş modu, motor, görev veya parametre komutu göndermez. OpenAI API hesabı, kullanım ücreti ve limiti kullanıcıya aittir.
- Gönderilen `iha_rag_asistan.py` örneğinin 600 karakter ve 80 karakter örtüşmeli belge parçalama yaklaşımı Pilot Arı içine hafif yerel RAG olarak uyarlandı. `belgeler/*.txt` dosyaları açılışta küçük bir sözcük dizinine alınır; ChromaDB, sentence-transformers veya ikinci bir bulut hesabı kurulmaz. Donanım hesabı toplam kalkış ağırlığı, motor sayısı, motor başına ölçülmüş statik itki, batarya mAh, ortalama toplam akım, voltaj ve sabit kanatta kanat alanını konuşma içinde toplar. İtki/ağırlık oranı, motor başına askıda kalma yükü, yaklaşık yüzde yük, %80 kullanılabilir kapasiteyle tahmini süre, Wh ve kanat yüklemesi formülle hesaplanır; eksik değer tahmin edilmez.

Open-Meteo isteğinde seçilen koordinat hizmete gönderilir. Açık erişim hizmeti ticari olmayan kullanım ve CC BY 4.0 koşullarına tabidir; ticari dağıtım için Open-Meteo abonelik şartları değerlendirilmelidir. Servis verileri meteorolojik model çıktısıdır ve saha anemometresi/yerel sensör ölçümü yerine geçmez.

Doğrulama: `py -3.12 -m unittest discover -s cube_station -p "test_*.py"` (133 test), `py -3.12 cube_station/check_operations.py` ve `py -3.12 cube_station/simulation_acceptance.py`. Open-Meteo geocoding ve güncel hava isteği Düzce için gerçek internet bağlantısıyla sınandı. Kamera sayfası test görüntüsü ve kaynak doğrulamasıyla sınandı; fiziksel kamera kullanıcı seçimi olmadan açılmadı. Motor/servo korumaları ve MAVLink komut biçimleri sahte bağlantıyla doğrulandı; fiziksel Cube, motor, servo ve kalibrasyon sonucu henüz donanım üzerinde sınanmadı. ArduPilot SITL kabul ekranı hazırdır; gerçek SITL raporu için bu bilgisayarda ayrı bir SITL süreci başlatılmalıdır. Fiziksel Cube/Here3/Kablosuz Telemetri otomatik port taraması ve gerçek Google API çağrısı henüz yapılmadı. Aşağıdaki eski sürüm notları tarihsel özellikleri de içerir; güncel davranış için bu bölüm esas alınmalıdır.

Tam simülasyon kabul testi `SIMULASYON_TESTI.bat` ile yeniden çalıştırılabilir. Test, ArduCopter ve ArduPlane mod tablolarının tamamını, kritik telemetri alanlarını, arıza engellerini ve parametre geri doğrulamasını sahte Cube üzerinden sınar. Ayrıntılı son çalıştırma sonucu `SIMULATION_TEST_REPORT.md` dosyasındadır.

## Buton animasyonları ve uçuş modları

Tüm normal ve temalı butonlarda fare üzerine geldiğinde yaklaşık 130 ms süren renk, altın çerçeve ve yükselme animasyonu; basıldığında kısa basma tepkisi vardır. Animasyon ana ekranı bekletmeden çalışır.

Canlı Cube Orange penceresindeki uçuş modu listesi, bağlantı kurulduktan sonra kartın bildirdiği araç türüne göre yenilenir. Döner kanat ve sabit kanat aynı mod numaralarını kullanmadığı için MAVLink mod numarası araç türüne özel tablodan seçilir. İstek gönderildikten sonra yeni mod kartın sonraki yaşam sinyalinde görülürse doğrulandı olarak bildirilir; sekiz saniye içinde görülmezse doğrulanamadı uyarısı verilir. STABILIZE, ALT_HOLD, LOITER, GUIDED, AUTO, RTL, LAND ve MANUAL seçeneklerinin hepsi her araçta bulunmaz; bağlantıdan sonra yalnız o firmware/araç türü için tanımlı modlar listelenir.

Yazılım testleri animasyonları, üç harita görünümünü ve uçuş modu komut yolunu doğrular. Gerçek Cube Orange kartının modu kabul etmesi henüz fiziksel kart bağlıyken denenmemiştir.

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

Lisans penceresindeki kaynak bağlantıları ve Kapat düğmesi sabit alt çubukta tutulur. Metin alanı kaydırılabilir; ekran ölçeklendirmesi veya küçük pencere boyutu düğmeleri gizlemez.

Simülasyon görünümünde fareyle kamera döndürme, akıcı tekerlek yakınlaştırması ve İHA türü simgeleri çalışır.

## 3D görünüm, bilgisayar konumu ve İHA profilleri

Güncel **flight_pro.py** sürümü varsayılan olarak OpenStreetMap görünümüyle açılır. Üstteki harita seçicisinden uydu görüntüsüne veya 3D simülasyona geçilir. 3D görünüm gerçek Google 3D uydu/fotogrametri verisi değildir.

İHA türü Sabit kanat, Döner kanat veya FPV olarak seçilebilir; harita simgesi buna göre değişir. Bu seçim şimdilik sentetik profil ve görünüm içindir, gerçek Cube Orange çerçeve ayarını değiştirmez.

Bilgisayar konumumu bul düğmesi yalnız kullanıcı bastığında Windows konum servisini bir kez çağırır. Windows konum izni kapalıysa veya cihaz konum üretemezse demo konumu korunur. Windows konumu GPS, Wi-Fi, hücresel ağ, IP adresi veya sistemdeki varsayılan konumdan gelebilir; gösterilen doğruluk yaklaşık değerdir. Konum dosyaya kaydedilmez.

## Canlı uçuş merkezi

Güncel **cockpit.py** ekranında harita ortada, uçuş/konum tablosu solda ve sistem/telemetri tablosu sağdadır. Harita işareti dört motorlu İHA şeklindedir. Sağ paneldeki denge düğmesi bağlantı yokken sentetik animasyonu yönetir. Canlı Cube Orange bağlantısında ise STABILIZE isteğini gerçek karta gönderir; düğme yalnız güncel ArduPilot heartbeat ve STABILIZE desteği görüldüğünde etkinleşir ve karttan gelen mod bilgisiyle durumunu yeniler.

**Bilgi ve Kılavuz** sayfasındaki **Bilgi Kılavuzunu İndir (PDF)** düğmesi, uygulamayla birlikte gelen 24 sayfalık ayrıntılı kullanım kılavuzunu kullanıcının seçtiği klasöre kaydeder. Kılavuz; döner kanat, sabit kanat ve FPV uçuş modlarını, sensör gereksinimlerini, parametre gruplarını, failsafe davranışlarını, yardımcı donanımları, telemetriyi ve görev aktarımını açıklar.

## Harita fare kontrolleri

Harita üzerinde sol tuşu basılı tutup sürükleyerek görünümü kaydırabilirsiniz. Fare tekerleği imlecin bulunduğu noktaya yakınlaştırır veya uzaklaştırır. Haritaya çift tıklamak görünümü sentetik İHA'nın son konumuna getirir. İşaret ekleme açıkken sol tıklama haritayı sürüklemek yerine numaralı not noktası ekler.

## Kurulum ve test merkezi

Kurulum ve test sayfası gerçek Cube için korumalı bir yer çalışma alanıdır. Bağlantı penceresinde **USB yer kurulumu** seçilmeli, kart güncel ve DISARMED olmalıdır. Jiroskop, düz seviye, altı yön ivmeölçer, pusula, RC kumanda, ESC ve hava hızı kalibrasyon komutları buradan gönderilir; kartın ACK ve durum mesajları ekranda izlenir.

Motor/servo testi yalnız aynı USB yer kurulumu bağlantısında, DISARMED kartta, güvenlik onayı ve `PERVANELER SÖKÜLDÜ` ifadesiyle açılır. Motor testi en fazla %30 ve 5 saniye, servo testi en fazla 3 saniyedir; servo süre sonunda nötre döner. Acil durdurma aktif servoyu nötre ve motor testlerini %0'a çeker. Motor yönü ve servo çıkış eşlemesi JSON raporuna kaydedilebilir. Yazılım kilitleri fiziksel güvenli stant, enerji sınırı ve üretici talimatlarının yerini tutmaz.

Parametre ekranı karttan gerçek listeyi alır; doğrulanmış yazmaları geçmişe ekler ve çakışma yoksa eski değere dönebilir. Yerel sınırlar bilinmeyen firmware parametreleri kartın kendi sürüm belgesi doğrulanmadan değiştirilmemelidir.

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

Pusula, RC kumanda, ESC ve hava hızı kalibrasyonları da aynı merkezde bulunur. Komut kabulü, fiziksel kalibrasyonun doğru tamamlandığı anlamına gelmez; kartın sonuç mesajını bekleyin. Yanıt kesilirse başarı varsayılmaz. Kalibrasyon komutları yeniden bağlanınca otomatik tekrarlanmaz. Yarım kalan kalibrasyonda kart durumunu kontrol edip gerekirse yerde yeniden başlatın. Motor/servo testi yalnız yukarıdaki sıkı yer güvenliği koşullarında komut gönderebilir.

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
