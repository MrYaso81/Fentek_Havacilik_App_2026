import unittest
from parameter_tree import ParameterTree
class ParameterTreeTests(unittest.TestCase):
 def test_search_and_set(self):
  t=ParameterTree();t.upsert('BATT_CAPACITY',5200,description='batarya kapasitesi');t.upsert('ATC_RAT_RLL_P',.1,description='PID roll')
  self.assertEqual(t.search('pid')[0].name,'ATC_RAT_RLL_P');self.assertEqual(t.set_value('BATT_CAPACITY',6000),6000)
 def test_invalid(self):
  with self.assertRaises(ValueError):ParameterTree().set_value('X',float('nan'))
