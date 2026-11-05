"""Custody and input-schema tests only; no scientific scoring or DLL calls."""
import copy,importlib.util,io,json,tempfile,unittest
from pathlib import Path
import numpy as np
ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('regional_full84_inputs',ROOT/'inputs.py')
inputs=importlib.util.module_from_spec(spec);spec.loader.exec_module(inputs)

class Full84Inputs(unittest.TestCase):
 @classmethod
 def setUpClass(cls):cls.restored=inputs.full84_inputs(ROOT)
 def fixture(self):
  identity=next(iter(self.restored));r=copy.deepcopy(self.restored[identity]);a=r['artifacts']
  row=dict(model=identity[0],origin=identity[1],index=identity[2],receipt=json.loads(a['receipt.json']),scalars=json.loads(a['scalars.json']))
  return row,r
 def test_exact_fifteen_original_details(self):
  self.assertEqual(set(self.restored),{('EP',o,i) for o in inputs.ORIGINS for i in (0,249,499,749,998)})
  for identity,r in self.restored.items():
   a=r['artifacts'];row=dict(receipt=json.loads(a['receipt.json']),scalars=json.loads(a['scalars.json']))
   self.assertEqual(inputs.checked_full84_detail(row,r['state'],a['private_path.npz'],r),a['private_detail.npz'])
 def test_changed_state_or_path_rejected(self):
  row,r=self.fixture()
  with self.assertRaisesRegex(ValueError,'state/path'):inputs.checked_full84_detail(row,b'changed',r['artifacts']['private_path.npz'],r)
  with self.assertRaisesRegex(ValueError,'state/path'):inputs.checked_full84_detail(row,r['state'],b'changed',r)
 def test_changed_original_receipt_rejected(self):
  row,r=self.fixture();row['receipt']['seed_records'][0]['seed_words_uint32_be'][0]+=1
  with self.assertRaisesRegex(ValueError,'receipt/scalars'):inputs.checked_full84_detail(row,r['state'],r['artifacts']['private_path.npz'],r)
 def test_changed_detail_bytes_rejected(self):
  row,r=self.fixture();r['artifacts']['private_detail.npz']+=b'tamper'
  with self.assertRaisesRegex(ValueError,'detail hash'):inputs.checked_full84_detail(row,r['state'],r['artifacts']['private_path.npz'],r)
 def test_consistently_rehashed_wrong_shape_rejected(self):
  row,r=self.fixture();a=r['artifacts'];buf=io.BytesIO();np.savez(buf,detail=np.zeros((int(row['scalars']['stats']['count']),10)));a['private_detail.npz']=buf.getvalue()
  row['receipt']['detail_sha256']=inputs.sha(a['private_detail.npz']);a['receipt.json']=inputs.encode(row['receipt']);r['source']['historical_receipt_sha256']=inputs.sha(a['receipt.json'])
  with self.assertRaisesRegex(ValueError,'eleven-column'):inputs.checked_full84_detail(row,r['state'],a['private_path.npz'],r)
 def test_archive_hash_mismatch_rejected(self):
  with tempfile.TemporaryDirectory() as td:
   p=Path(td);m=json.loads((ROOT/'original_completion_20261101.manifest.json').read_text());(p/'original_completion_20261101.manifest.json').write_text(json.dumps(m));(p/m['archive']['path']).write_bytes(b'changed')
   with self.assertRaisesRegex(ValueError,'archive hash'):inputs.full84_inputs(p)
 def test_current_detail_pin_preserves_original_receipt(self):
  row,r=self.fixture();before=copy.deepcopy(row['receipt']);result=inputs.materialized_receipt(row['receipt'],'state','path','scalars',detail_sha256='current-detail')
  self.assertEqual(row['receipt'],before);self.assertEqual(result['detail_sha256'],'current-detail');self.assertEqual(result['materialization_provenance']['historical_hash_fields']['detail_sha256'],before['detail_sha256'])

if __name__=='__main__':unittest.main()
