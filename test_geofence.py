import unittest
from geofence import validate_polygon,fence_items
class GeofenceTests(unittest.TestCase):
 def test_polygon(self): self.assertEqual(len(fence_items([(1,1),(1,2),(2,2)])),3)
 def test_reject(self):
  with self.assertRaises(ValueError):validate_polygon([(1,1),(1,1),(1,1)])
