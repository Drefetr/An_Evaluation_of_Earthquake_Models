"""Input-contract controls only; no likelihood, fit or simulation."""
import importlib.util
from pathlib import Path
import unittest
import numpy as np
spec=importlib.util.spec_from_file_location('regional_inputs',Path(__file__).resolve().parents[1]/'inputs.py')
mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod)

class InputContractTests(unittest.TestCase):
 def state(self):return dict(params=np.array([-2,0,.5,.1,1.3,5,5,2,10,1,2]),rectangles=np.ones((9,4)),pi=np.ones(9)/9,training_xy=np.zeros((2,2)),prehistory=np.array([[0.,.2,0.,0.]]),subblocks=np.linspace(1,2,6))
 def row(self):return dict(model='OC',origin='california_fold_0',index=0,receipt=dict(status='complete',case_id='california_fold_0',index=0,mode='simulate',phase='production',seed_records=mod.seed_records('OC','california_fold_0',0)),scalars=dict(stats=dict(count=1,other=list(range(83)))))
 def test_archive_path_traversal_rejected(self):
  for path in ('../x','/x','C:/x','a\\x','a/../../x','a/./x'):
   with self.assertRaises(ValueError):mod.safe_name(path)
  self.assertEqual(str(mod.safe_name('S05/states/a.npz')),'S05/states/a.npz')
 def test_seed_scope_and_streams_are_distinct(self):
  seeds=mod.seed_records('OC','california_fold_0',0)
  self.assertEqual(len({s['sha256'] for s in seeds}),4)
  self.assertNotEqual(seeds,mod.seed_records('EP','california_fold_0',0))
  self.assertNotEqual(seeds,mod.seed_records('OC','california_fold_0',1))
 def test_seed_mutation_rejected(self):
  r=self.row();r['receipt']['seed_records'][0]['seed_words_uint32_be'][0]^=1
  with self.assertRaisesRegex(ValueError,'Seed'):mod.validate_future(r,self.state(),np.array([[1.5,.2,0,0]]))
 def test_count_and_forecast_bounds_rejected(self):
  r=self.row();s=self.state();mod.validate_future(r,s,np.array([[1.5,.2,0,0]]))
  with self.assertRaisesRegex(ValueError,'interval'):mod.validate_future(r,s,np.array([[2.,.2,0,0]]))
  r['scalars']['stats']['count']=2
  with self.assertRaisesRegex(ValueError,'count'):mod.validate_future(r,s,np.array([[1.5,.2,0,0]]))
 def test_observed_future_cannot_leak_into_simulation_state(self):
  s=self.state();mod.validate_state(s,'OC');s['observed']=np.ones((1,4))
  with self.assertRaisesRegex(ValueError,'leakage'):mod.validate_state(s,'OC')
 def test_numeric_pointer_fingerprint_distinguishes_value_and_location(self):
  self.assertEqual(mod.numeric({'path':'archive:/x','x':1.25}),[('/x',1.25)])
  self.assertNotEqual(mod.numeric({'x':1.25}),mod.numeric({'y':1.25}))
  self.assertNotEqual(mod.numeric({'x':1.25}),mod.numeric({'x':1.25001}))
 def test_materialization_refreshes_current_receipt_pins_and_retains_old(self):
  old=dict(input_state_sha256='old_state',scalars_sha256='old_scalars',path_sha256='old_path',detail_sha256='omitted_detail',job_sha256='old_job',seed_records=[1,2])
  new=mod.materialized_receipt(old,'new_state','same_path','new_scalars')
  self.assertEqual(new['input_state_sha256'],'new_state');self.assertEqual(new['scalars_sha256'],'new_scalars')
  self.assertNotIn('detail_sha256',new);self.assertNotIn('job_sha256',new)
  self.assertEqual(new['materialization_provenance']['historical_hash_fields']['detail_sha256'],'omitted_detail')
  self.assertEqual(new['seed_records'],old['seed_records']);self.assertEqual(old['scalars_sha256'],'old_scalars')
if __name__=='__main__':unittest.main()
