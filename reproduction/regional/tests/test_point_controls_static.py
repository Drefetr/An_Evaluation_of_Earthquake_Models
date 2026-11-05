"""Fake-output/source controls only: no native loading or reference quadrature."""
import importlib.util
import json
from pathlib import Path
import unittest
from unittest.mock import patch
import numpy as np
spec=importlib.util.spec_from_file_location('point_controls',Path(__file__).resolve().parents[1]/'point_controls.py')
controls=importlib.util.module_from_spec(spec);spec.loader.exec_module(controls)

class PointControlFailureTests(unittest.TestCase):
 def test_native_point_component_cannot_be_hidden_by_other_components(self):
  expected=np.array([2,.4,1.,.3,-1.,-2.,.2,-3.1]);actual=expected.copy();actual[5]+=2e-7
  result=controls.assess(actual,expected)
  self.assertFalse(result['passed']);self.assertFalse(result['components'][5]['passed']);self.assertTrue(result['components'][7]['passed'])
 def test_count_is_exact_and_mark_sum_has_own_tolerance(self):
  expected=np.zeros(8);actual=expected.copy();actual[0]=1e-15
  self.assertFalse(controls.assess(actual,expected)['passed'])
  actual=expected.copy();actual[1]=2e-12
  self.assertFalse(controls.assess(actual,expected)['passed'])
 def test_nonfinite_and_wrong_shape_fail_with_serializable_evidence(self):
  expected=np.zeros(8);actual=expected.copy();actual[5]=float('nan')
  result=controls.assess(actual,expected);self.assertFalse(result['passed']);json.dumps(result,allow_nan=False)
  self.assertFalse(controls.assess(np.zeros(7),expected)['passed'])
 def test_exceptions_are_retained_and_do_not_skip_later_case(self):
  def fail():raise RuntimeError('injected native failure')
  rows=[controls.retained_attempt('failed',fail),controls.retained_attempt('later',lambda:dict(passed=True))]
  self.assertFalse(rows[0]['passed']);self.assertEqual(rows[0]['error'],'injected native failure');self.assertTrue(rows[1]['passed'])
 def test_fixture_roster_covers_native_abi_and_empty_prehistory_compensator(self):
  fixtures=controls.fixtures();self.assertEqual(len(fixtures),25)
  self.assertEqual({(f['model'],f['q']) for f in fixtures},{('OC',2.),('EP',1.05),('EP',1.4),('EP',2.),('EP',3.)})
  for f in fixtures:
   self.assertEqual(len(f['state']['params']),11 if f['model']=='OC' else 12)
   if f['scenario']=='empty_with_prehistory':self.assertEqual(len(f['events']),0);self.assertGreater(len(f['state']['prehistory']),0)
   if f['scenario']=='strict_past':self.assertEqual(f['events'][1,0],f['events'][2,0])
   self.assertGreater(np.ptp(f['state']['pi']),0)
   rect=f['state']['rectangles'];self.assertGreater(np.ptp((rect[:,1]-rect[:,0])*(rect[:,3]-rect[:,2])),0)
 def test_boundary_assignment_uses_right_upper_cell_and_clips_outer_edge(self):
  rect=controls.fixtures()[0]['state']['rectangles']
  self.assertEqual(controls.CartesianReference.cell((1.,1.),rect),4)
  self.assertEqual(controls.CartesianReference.cell((3.,6.),rect),8)
  self.assertEqual(controls.CartesianReference.cell((0.,0.),rect),0)
 def test_import_and_fixture_access_do_not_load_dll_or_integrate(self):
  with patch.object(controls,'load_native',side_effect=AssertionError('forbidden native load')),patch.object(controls.CartesianReference,'integral',side_effect=AssertionError('forbidden integration')):
   self.assertEqual(len(controls.fixtures()),25)
   self.assertTrue(controls.assess(np.zeros(8),np.zeros(8))['passed'])
 def test_report_inside_source_is_rejected_before_any_directory_creation(self):
  output=Path(controls.__file__).resolve().parent/'should_not_create/report.json'
  with patch.object(Path,'mkdir',side_effect=AssertionError('unexpected write')):
   with self.assertRaisesRegex(ValueError,'external'):controls.run('unloaded.dll','unused_sources',output)
if __name__=='__main__':unittest.main()
