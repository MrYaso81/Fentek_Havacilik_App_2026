import unittest
from urllib.parse import parse_qs, urlparse

from weather_service import Location, WeatherError, fetch_current, format_current, geocode, parse_location, weather_url


class WeatherServiceTests(unittest.TestCase):
    def test_url_requests_aviation_relevant_current_fields(self):
        query=parse_qs(urlparse(weather_url(40.84,31.16)).query)
        self.assertEqual(query['wind_speed_unit'],['ms'])
        for field in ('visibility','wind_gusts_10m','precipitation','weather_code'):
            self.assertIn(field,query['current'][0])

    def test_invalid_coordinate_is_rejected(self):
        with self.assertRaises(WeatherError):weather_url(140,31)

    def test_coordinate_text_is_recognised(self):
        loc=parse_location('40.8432, 31.1565')
        self.assertAlmostEqual(loc.latitude,40.8432)
        self.assertAlmostEqual(loc.longitude,31.1565)

    def test_geocoding_prefers_turkey_and_keeps_label(self):
        data={'results':[{'name':'Duzce','country':'Other','country_code':'XX','latitude':1,'longitude':2},
                         {'name':'Düzce','admin1':'Düzce','country':'Türkiye','country_code':'TR','latitude':40.84,'longitude':31.16}]}
        loc=geocode('Düzce',lambda _url:data)
        self.assertEqual(loc.latitude,40.84);self.assertIn('Türkiye',loc.label)

    def test_missing_current_data_is_not_guessed(self):
        with self.assertRaises(WeatherError):fetch_current(Location(40,30,'Test'),lambda _url:{})

    def test_weather_report_has_time_source_and_risks(self):
        payload={'current':{'time':'2026-09-10T12:00','temperature_2m':18,'relative_humidity_2m':80,
                            'precipitation':1.2,'weather_code':95,'cloud_cover':90,'visibility':4000,
                            'wind_speed_10m':7,'wind_direction_10m':180,'wind_gusts_10m':12},
                 'current_units':{},'timezone':'Europe/Istanbul'}
        report=fetch_current(Location(40.84,31.16,'Düzce'),lambda _url:payload)
        text=format_current(report)
        self.assertIn('Veri zamanı',text);self.assertIn('Open-Meteo',text)
        self.assertIn('uçuşu erteleyin',text);self.assertIn('yerel sensör',text)


if __name__=='__main__':unittest.main()
