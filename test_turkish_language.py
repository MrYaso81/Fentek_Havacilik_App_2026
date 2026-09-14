import unittest

from turkish_language import detect_intents,semantic_normalize


class TurkishLanguageTests(unittest.TestCase):
    def test_everyday_phrases_map_to_flight_terms(self):
        cases={
            'yer istasyonu aracı görmüyor':'telemetri',
            'aynı noktada dursun':'loiter',
            'yüksekliği korusun':'alt_hold',
            'kalktığı yere dönsün':'rtl',
            'yüklediğim rotayı izlesin':'auto',
            'hedef konuma gitsin':'guided',
            'otomatik insin':'land',
            'devrilmesin':'stabilize',
        }
        table=str.maketrans('çğıöşü','cgiosu')
        for raw,expected in cases.items():
            value=semantic_normalize(raw.lower().translate(table))
            self.assertIn(expected,value,(raw,value))

    def test_detects_multiple_intents(self):
        intents=detect_intents('telemetri ve gps çalışmıyor batarya voltajı da yok')
        self.assertIn('connection',intents);self.assertIn('gps',intents);self.assertIn('battery',intents)


if __name__=='__main__':unittest.main()
