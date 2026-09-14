"""Pure calculations used by map measurements and ground-only safety previews."""
import math
from urllib.parse import urlencode

EARTH_RADIUS_M = 6_371_008.8


def google_static_url(lat,lon,zoom,key):
    lat,lon,zoom=float(lat),float(lon),int(zoom);key=str(key).strip()
    if not key:raise ValueError('Google Maps API anahtarı boş.')
    if not -90<=lat<=90 or not -180<=lon<=180 or not 0<=zoom<=21:raise ValueError('Google harita merkezi veya yakınlaştırma değeri geçersiz.')
    query=urlencode({'center':f'{lat:.7f},{lon:.7f}','zoom':str(zoom),'size':'640x640','scale':'1','maptype':'satellite','format':'png','key':key})
    return 'https://maps.googleapis.com/maps/api/staticmap?'+query


def haversine_m(a, b):
    lat1, lon1 = map(math.radians, (float(a[0]), float(a[1])))
    lat2, lon2 = map(math.radians, (float(b[0]), float(b[1])))
    dlat, dlon = lat2 - lat1, lon2 - lon1
    value = math.sin(dlat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
    return 2 * EARTH_RADIUS_M * math.asin(min(1.0, math.sqrt(value)))


def route_metrics(points, speed_mps=10.0):
    points = [tuple(map(float, p[:2])) for p in points]
    speed = float(speed_mps)
    if not math.isfinite(speed) or speed <= 0:
        raise ValueError('Tahmini hız sıfırdan büyük olmalı.')
    legs = [haversine_m(a, b) for a, b in zip(points, points[1:])]
    total = sum(legs)
    return {'legs': legs, 'total_m': total, 'seconds': total / speed}


def polygon_area_m2(points):
    points = [tuple(map(float, p[:2])) for p in points]
    if len(points) < 3:
        return 0.0
    lat0 = math.radians(sum(p[0] for p in points) / len(points))
    xy = [(EARTH_RADIUS_M * math.radians(lon) * math.cos(lat0), EARTH_RADIUS_M * math.radians(lat))
          for lat, lon in points]
    return abs(sum(x1 * y2 - x2 * y1 for (x1, y1), (x2, y2) in zip(xy, xy[1:] + xy[:1]))) / 2


def radio_assessment(rssi=None, noise=None, remote_rssi=None, remote_noise=None, age=None):
    if age is None or age > 3:
        return 'BEKLE', 'RADIO_STATUS verisi yok veya eski.'
    margins = []
    if rssi not in (None, 255) and noise not in (None, 255):
        margins.append(int(rssi) - int(noise))
    if remote_rssi not in (None, 255) and remote_noise not in (None, 255):
        margins.append(int(remote_rssi) - int(remote_noise))
    if not margins:
        return 'BİLGİ YOK', 'Radyo sinyal ve gürültü değerlerini bildirmedi.'
    margin = min(margins)
    if margin >= 35:
        return 'İYİ', f'En düşük sinyal/gürültü farkı {margin} ham birim.'
    if margin >= 20:
        return 'ORTA', f'En düşük sinyal/gürültü farkı {margin}; menzil testini izleyin.'
    return 'ZAYIF', f'En düşük sinyal/gürültü farkı {margin}; uçuş öncesi bağlantıyı düzeltin.'


def failsafe_preview(values, scenario):
    """Explain likely configuration path without pretending to execute a real failsafe."""
    scenario = str(scenario)
    mapping = {
        'Yer istasyonu bağlantısı kesilirse': ('FS_GCS_ENABLE', 'Yer istasyonu/telemetri kaybı davranışı'),
        'RC kumanda sinyali kesilirse': ('FS_THR_ENABLE', 'RC kumanda kaybı davranışı'),
        'Batarya düşük seviyeye inerse': ('BATT_FS_LOW_ACT', 'Düşük batarya davranışı'),
        'Batarya kritik seviyeye inerse': ('BATT_FS_CRT_ACT', 'Kritik batarya davranışı'),
        'EKF veya konum çözümü bozulursa': ('FS_EKF_ACTION', 'EKF hata davranışı'),
    }
    if scenario not in mapping:
        raise ValueError('Bilinmeyen güvenlik senaryosu.')
    name, label = mapping[scenario]
    if name not in values:
        return 'BEKLE', f'{label}: {name} karttan okunmadı. Sonuç tahmin edilmedi.'
    value = values[name][0] if isinstance(values[name], tuple) else values[name]
    return 'YAPILANDIRILMIŞ', f'{label}: {name} = {float(value):g}. Sayısal seçeneğin anlamını bağlı firmware belgesinden doğrulayın.'
