import unittest

from iha_knowledge import (HardwareProfile,LightweightRAG,inventory_report,is_build_question,
                           is_performance_question,parse_inventory,parse_specs,performance_report)


class IhaKnowledgeTests(unittest.TestCase):
    def test_parses_and_calculates_multirotor(self):
        profile=HardwareProfile();profile.update(parse_specs('Toplam ağırlık 1450 g, 4 motor, motor başına itki 900 g, batarya 5200 mAh, ortalama akım 22 A, voltaj 14.8 V'))
        self.assertEqual(profile.motor_count,4);self.assertEqual(profile.weight_g,1450)
        text=performance_report(profile)
        self.assertIn('2.48',text);self.assertIn('11.3 dakika',text);self.assertIn('77.0 Wh',text)

    def test_fixed_wing_loading(self):
        profile=HardwareProfile(weight_g=1200,wing_area_dm2=30)
        self.assertIn('40.0 g/dm²',performance_report(profile,'Sabit kanat'))

    def test_missing_data_is_requested_without_guess(self):
        text=performance_report(HardwareProfile(battery_mah=5200))
        self.assertIn('Eksik veri',text);self.assertNotIn('dakika =',text)

    def test_lightweight_rag_retrieves_relevant_source(self):
        text=LightweightRAG().retrieve('Motor KV değeri tek başına itkiyi gösterir mi?')
        self.assertIn('Motor KV ve pervane',text)
        self.assertTrue(is_performance_question('İHA kaç gram olmalı?'))

    def test_inventory_detects_components_and_lists_missing(self):
        inventory=parse_inventory('Elimde Cube Orange, Here3 GPS, dört motor, ESC ve batarya var')
        self.assertTrue({'flight_controller','gps','motors','esc','battery'}<=inventory)
        text=inventory_report(inventory,'Döner kanat')
        self.assertIn('Pervaneler',text);self.assertIn('RC alıcı',text);self.assertIn('Uyumluluk kontrolü',text)
        self.assertTrue(is_build_question('Bunların dışında başka ne lazım?'))


if __name__=='__main__':unittest.main()
