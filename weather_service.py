"""Small Open-Meteo client used by Pilot Arı.

The module deliberately contains no flight-authorisation logic.  It retrieves
modelled weather data and formats the measurements so the UI can present their
source and age honestly.
"""
from __future__ import annotations

import json
import math
import time
from dataclasses import dataclass
from urllib.parse import urlencode
from urllib.request import Request, urlopen


FORECAST_URL = "https://api.open-meteo.com/v1/forecast"
GEOCODING_URL = "https://geocoding-api.open-meteo.com/v1/search"
CURRENT_FIELDS = (
    "temperature_2m", "relative_humidity_2m", "precipitation", "rain",
    "weather_code", "cloud_cover", "surface_pressure", "visibility",
    "wind_speed_10m", "wind_direction_10m", "wind_gusts_10m",
)


class WeatherError(RuntimeError):
    pass


@dataclass(frozen=True)
class Location:
    latitude: float
    longitude: float
    label: str


def _coordinate(value, low, high, name):
    try:
        value = float(value)
    except (TypeError, ValueError) as exc:
        raise WeatherError(f"Geçersiz {name}.") from exc
    if not math.isfinite(value) or not low <= value <= high:
        raise WeatherError(f"Geçersiz {name}.")
    return value


def weather_url(latitude, longitude):
    latitude = _coordinate(latitude, -90, 90, "enlem")
    longitude = _coordinate(longitude, -180, 180, "boylam")
    query = urlencode({
        "latitude": f"{latitude:.6f}",
        "longitude": f"{longitude:.6f}",
        "current": ",".join(CURRENT_FIELDS),
        "wind_speed_unit": "ms",
        "timezone": "auto",
        "forecast_days": 1,
    })
    return f"{FORECAST_URL}?{query}"


def _read_json(url, timeout=12):
    request = Request(url, headers={"User-Agent": "Fentek-Havacilik/1.0 weather assistant"})
    try:
        with urlopen(request, timeout=timeout) as response:
            raw = response.read(1_000_001)
            if len(raw) > 1_000_000:
                raise WeatherError("Hava servisi yanıtı beklenenden büyük.")
        return json.loads(raw.decode("utf-8"))
    except WeatherError:
        raise
    except Exception as exc:
        raise WeatherError("İnternet veya hava servisi bağlantısı kurulamadı.") from exc


def geocode(place, fetch=_read_json):
    place = " ".join(str(place).strip().split())
    if len(place) < 2:
        raise WeatherError("Şehir veya ilçe adı çok kısa.")
    url = f"{GEOCODING_URL}?" + urlencode({"name": place, "count": 5, "language": "tr", "format": "json"})
    data = fetch(url)
    results = data.get("results") or []
    if not results:
        raise WeatherError(f'“{place}” için konum bulunamadı.')
    # Prefer Turkey when names collide, while still supporting worldwide use.
    item = next((row for row in results if row.get("country_code") == "TR"), results[0])
    parts = [item.get("name"), item.get("admin1"), item.get("country")]
    label = ", ".join(dict.fromkeys(part for part in parts if part))
    return Location(float(item["latitude"]), float(item["longitude"]), label or place)


def parse_location(text):
    """Return coordinates from 'lat, lon' input, otherwise None."""
    match = __import__("re").search(r"(-?\d{1,2}(?:[.,]\d+)?)\s*[,;/ ]\s*(-?\d{1,3}(?:[.,]\d+)?)", str(text))
    if not match:
        return None
    try:
        lat = float(match.group(1).replace(",", "."))
        lon = float(match.group(2).replace(",", "."))
        return Location(_coordinate(lat, -90, 90, "enlem"), _coordinate(lon, -180, 180, "boylam"), f"{lat:.5f}, {lon:.5f}")
    except WeatherError:
        return None


def fetch_current(location, fetch=_read_json):
    data = fetch(weather_url(location.latitude, location.longitude))
    current = data.get("current")
    if not isinstance(current, dict):
        raise WeatherError("Hava servisi güncel ölçüm döndürmedi.")
    required = ("time", "temperature_2m", "wind_speed_10m", "wind_gusts_10m")
    if any(current.get(key) is None for key in required):
        raise WeatherError("Hava servisinin kritik alanları eksik.")
    return {
        "location": location,
        "current": current,
        "units": data.get("current_units") or {},
        "timezone": data.get("timezone") or "",
        "elevation": data.get("elevation"),
        "fetched_at": time.time(),
        "source": "Open-Meteo",
    }


WEATHER_CODES = {
    0: "açık", 1: "çoğunlukla açık", 2: "parçalı bulutlu", 3: "kapalı",
    45: "sisli", 48: "kırağı sisli", 51: "hafif çisenti", 53: "çisenti",
    55: "yoğun çisenti", 61: "hafif yağmur", 63: "yağmur", 65: "şiddetli yağmur",
    71: "hafif kar", 73: "kar", 75: "yoğun kar", 80: "hafif sağanak",
    81: "sağanak", 82: "şiddetli sağanak", 95: "gök gürültülü fırtına",
    96: "dolulu fırtına", 99: "şiddetli dolulu fırtına",
}


def format_current(report):
    current = report["current"]
    location = report["location"]
    code = int(current.get("weather_code", -1))
    visibility = current.get("visibility")
    visibility_text = "—" if visibility is None else f"{float(visibility) / 1000:.1f} km"
    rain = float(current.get("precipitation") or 0)
    wind = float(current.get("wind_speed_10m") or 0)
    gust = float(current.get("wind_gusts_10m") or 0)
    lines = [
        f"{location.label} için güncel hava modeli:",
        f"• Durum: {WEATHER_CODES.get(code, f'kod {code}')}",
        f"• Sıcaklık: {float(current['temperature_2m']):.1f} °C  • Nem: %{float(current.get('relative_humidity_2m') or 0):.0f}",
        f"• Rüzgâr: {wind:.1f} m/s, hamle {gust:.1f} m/s, yön {float(current.get('wind_direction_10m') or 0):.0f}°",
        f"• Yağış: {rain:.1f} mm  • Görüş: {visibility_text}  • Bulut: %{float(current.get('cloud_cover') or 0):.0f}",
        f"• Veri zamanı: {current['time']} {report.get('timezone', '')}".rstrip(),
    ]
    risks = []
    if code in (95, 96, 99):
        risks.append("Gök gürültülü hava bildirildi: uçuşu erteleyin.")
    if rain > 0 or code in set(range(51, 83)):
        risks.append("Yağış bildirildi: donanım açıkça bu koşula uygun değilse uçuşu erteleyin.")
    if visibility is not None and float(visibility) < 5000:
        risks.append("Görüş 5 km altında: saha ve mevzuat koşullarını ayrıca doğrulayın.")
    if code in (45, 48):
        risks.append("Sis bildirildi: görsel temas ve yön farkındalığı riski var.")
    if gust >= 10:
        risks.append("Rüzgâr hamlesi yüksek görünüyor; aracın doğrulanmış sınırı bilinmeden uçuş uygun denemez.")
    if gust >= max(6, wind * 1.6):
        risks.append("Rüzgâr ile hamle arasında belirgin fark var; ani yük değişimleri beklenebilir.")
    if risks:
        lines.append("\nDikkat:\n" + "\n".join("• " + item for item in risks))
    else:
        lines.append("\nBelirgin yağış/fırtına işareti görünmüyor. Yine de araç sınırı, saha rüzgâr ölçümü ve yerel koşullar doğrulanmadan uçuş kararı verilmez.")
    lines.append("\nKaynak: Open-Meteo. Bunlar 15 dakikalık hava modeli verileridir; kalkış alanındaki yerel sensör ölçümü değildir.")
    return "\n".join(lines)
