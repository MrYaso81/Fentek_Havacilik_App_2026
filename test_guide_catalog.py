import unittest
from guide_catalog import TOPICS,parameter_help

class GuideCatalogTests(unittest.TestCase):
    def test_topics_are_unique_and_complete(self):
        titles=[title for category,title,body in TOPICS]
        self.assertEqual(len(titles),len(set(titles)))
        self.assertTrue(all(category and title and len(body)>30 for category,title,body in TOPICS))
    def test_critical_parameters_have_specific_help(self):
        for name in ('ARMING_CHECK','FS_GCS_ENABLE','BATT_CAPACITY','RTL_ALT','FENCE_ENABLE'):
            category,text=parameter_help(name);self.assertNotEqual(category,'Firmware özel');self.assertGreater(len(text),30)
    def test_unknown_parameter_is_not_guessed(self):
        category,text=parameter_help('VENDOR_MAGIC_42')
        self.assertEqual(category,'Firmware özel');self.assertIn('doğrulanmadan değiştirilmemelidir',text)
    def test_prefix_fallback(self):
        category,text=parameter_help('SERVO9_FUNCTION');self.assertEqual(category,'Çıkışlar')

if __name__=='__main__':unittest.main()
