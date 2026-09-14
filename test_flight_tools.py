import unittest
from flight_tools import haversine_m, route_metrics, polygon_area_m2, radio_assessment, failsafe_preview,google_static_url


class FlightToolTests(unittest.TestCase):
    def test_route_distance_and_time(self):
        result = route_metrics([(41, 29), (41.001, 29)], 10)
        self.assertGreater(result['total_m'], 110)
        self.assertLess(result['total_m'], 112)
        self.assertAlmostEqual(result['seconds'], result['total_m'] / 10)

    def test_area(self):
        self.assertGreater(polygon_area_m2([(41, 29), (41, 29.001), (41.001, 29.001), (41.001, 29)]), 9000)

    def test_radio(self):
        self.assertEqual(radio_assessment(180, 120, 170, 120, 1)[0], 'İYİ')
        self.assertEqual(radio_assessment(age=9)[0], 'BEKLE')

    def test_failsafe_preview_does_not_guess(self):
        self.assertEqual(failsafe_preview({}, 'Yer istasyonu bağlantısı kesilirse')[0], 'BEKLE')
        self.assertEqual(failsafe_preview({'FS_GCS_ENABLE': (1, 6)}, 'Yer istasyonu bağlantısı kesilirse')[0], 'YAPILANDIRILMIŞ')

    def test_google_satellite_request(self):
        url=google_static_url(41,29,15,'test-key')
        self.assertIn('maptype=satellite',url);self.assertIn('size=640x640',url);self.assertIn('key=test-key',url)


if __name__ == '__main__':
    unittest.main()
