"""Input custody checks only: no fitting, generation or scoring."""
import copy,importlib.util,math,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
spec=importlib.util.spec_from_file_location('s02_inputs',Path(__file__).with_name('inputs.py'));mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod)
class InputTests(unittest.TestCase):
 def fixture(self):
  row=dict(id='s000_h0p0',forest=0,h=0.,history_sha256='hash')
  phase=dict(pars=[-4.,0.,.5,0.],nll=2.)
  fit=dict(row,status='complete',methods=[dict(procedure=p,status='complete',null=copy.deepcopy(phase),alternative=copy.deepcopy(phase),attempts=[{}]*16) for p in ['M1','M2']])
  return row,fit
 def test_safe_paths(self):
  self.assertEqual(str(mod.safe_name('fits/case.json')),'fits/case.json')
  for p in ['../x','a/../x','/x','C:/x','a\\x','a/./x','']:
   with self.assertRaises(ValueError):mod.safe_name(p)
 def test_complete_pair(self):
  self.assertEqual(mod.validate_fit(*self.fixture()),32)
 def test_identity_mismatch(self):
  row,fit=self.fixture();fit['history_sha256']='changed'
  with self.assertRaisesRegex(ValueError,'identity'):mod.validate_fit(row,fit)
 def test_duplicate_or_incomplete_method(self):
  row,fit=self.fixture();fit['methods'][1]['procedure']='M1'
  with self.assertRaisesRegex(ValueError,'roster'):mod.validate_fit(row,fit)
  row,fit=self.fixture();fit['methods'][1]['status']='failed'
  with self.assertRaisesRegex(ValueError,'Incomplete'):mod.validate_fit(row,fit)
 def test_nonfinite_selected_state(self):
  for field,value in [('pars',[0.,0.,.5,float('nan')]),('nll',float('inf'))]:
   row,fit=self.fixture();fit['methods'][0]['alternative'][field]=value
   with self.assertRaisesRegex(ValueError,'Invalid'):mod.validate_fit(row,fit)
 def test_existing_output_is_not_overwritten(self):
  with tempfile.TemporaryDirectory() as td,patch.object(mod,'verify',return_value={'passed':True}):
   p=Path(td);sentinel=p/'keep.txt';sentinel.write_text('retained')
   with self.assertRaisesRegex(ValueError,'new directory'):mod.extract(p)
   self.assertEqual(sentinel.read_text(),'retained')
if __name__=='__main__':unittest.main()
