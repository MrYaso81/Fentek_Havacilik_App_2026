import unittest
from parameter_metadata import metadata_for,validate_metadata

class MetadataTests(unittest.TestCase):
    def test_servo_and_battery_ranges(self):
        self.assertEqual(metadata_for('SERVO3_TRIM')[2],'µs')
        self.assertEqual(validate_metadata('BATT_CAPACITY',5200),5200)
        with self.assertRaises(ValueError):validate_metadata('SERVO3_MAX',3000)
    def test_unknown_is_not_guessed(self):self.assertIsNone(metadata_for('FIRMWARE_SPECIAL_X'))
    def test_rtl_alt_is_vehicle_specific(self):
        self.assertIsNotNone(metadata_for('RTL_ALT',2));self.assertIsNone(metadata_for('RTL_ALT',1))

if __name__=='__main__':unittest.main()
