import unittest
from sitl_acceptance import validate_endpoint,fault_matrix

class SitlTests(unittest.TestCase):
    def test_only_loopback_endpoints_are_allowed(self):
        self.assertEqual(validate_endpoint('tcp:127.0.0.1:5760'),'tcp:127.0.0.1:5760')
        for value in ('COM5','tcp:192.168.1.3:5760','udp:127.0.0.1:14550'):
            with self.assertRaises(ValueError):validate_endpoint(value)
    def test_fault_matrix_is_fail_closed(self):
        rows=fault_matrix();self.assertEqual(len(rows),6);self.assertTrue(all(blocked for _,blocked in rows))

if __name__=='__main__':unittest.main()
