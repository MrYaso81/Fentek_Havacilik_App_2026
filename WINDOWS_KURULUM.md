# Fentek Havacılık — Windows taşınabilir sürüm

## Kullanıcı kurulumu

1. `Fentek_Havacilik_Windows_x64.zip` dosyasını bilgisayara kopyalayın.
2. ZIP dosyasını tamamen bir klasöre çıkarın.
3. `Fentek Havacılık.exe` dosyasını açın.
4. İsterseniz EXE dosyasına sağ tıklayıp **Gönder → Masaüstü (kısayol oluştur)** seçin.

Python kurulması gerekmez. `Fentek Havacılık.exe` tek başına başka klasöre taşınmamalıdır; yanındaki `_internal` klasörü uygulamanın parçalarını içerir.

## Donanım bağlantısı

- Cube Orange USB kurulumu için kartı veri aktarabilen USB kablosuyla bağlayın.
- Kablosuz telemetri için yer modülünü bilgisayara takın.
- Windows gerekli USB/seri sürücüsünü tanımıyorsa donanım üreticisinin sürücüsü ayrıca kurulmalıdır.
- Kamera ve çevrimiçi harita özellikleri ilgili donanım ile internet bağlantısına bağlıdır.

## Geliştirici derlemesi

Kaynak klasöründe `EXE_OLUSTUR.bat` çalıştırılır. Derleme sonucu `dist\Fentek Havacılık` klasörüne yazılır. Derleme bilgisayarında Python 3.12 ve internet bağlantısı gerekir; son kullanıcı bilgisayarında Python gerekmez.

Windows, imzalanmamış yeni EXE dosyalarında SmartScreen uyarısı gösterebilir. Dağıtım büyüdüğünde güvenilir bir kod imzalama sertifikasıyla EXE imzalanmalıdır.
