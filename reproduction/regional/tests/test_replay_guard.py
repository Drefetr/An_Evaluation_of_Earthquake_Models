"""Fake reports and sleeping subprocesses only; no scientific imports or calls."""
import copy,importlib.util,os,sys,tempfile
from pathlib import Path
import unittest
from unittest.mock import patch
spec=importlib.util.spec_from_file_location('replay_guard',Path(__file__).resolve().parents[1]/'run_replay.py');guard=importlib.util.module_from_spec(spec);spec.loader.exec_module(guard)
PRIVATE=Path(__file__).resolve().parents[4]

class ReportTests(unittest.TestCase):
 def fixture(self):
  binding=dict(scope='point',manifest_sha256='manifest',dll_sha256='dll',sources={k:k for k in ('replay.py','original_full84.py','native_wrapper.py','independent.cpp','temporal_extension.cpp')})
  rows=[dict(model=m,origin=o,index=i,scope='point',passed=True,seconds=.1,receipt_sha256='r'+m+o,metrics=dict(recomputed_fields=list(guard.FIELDS_POINT),max_error=0.,point_and_joint_recomputed=True)) for m,o,i in sorted(guard.roster('pilot'))]
  receipts={guard.identity(r):r['receipt_sha256'] for r in rows}
  report=dict(passed=True,failed=0,complete=6,rows=rows,binding=dict(manifest_sha256='manifest',dll_sha256='dll',adapter_sha256='replay.py',source_pins=guard.archived_pins(binding),scope='point',pilot=True,planned=6))
  return report,binding,receipts
 def test_exact_pilot_is_valid_but_false_report_even_after_exit_zero_is_not(self):
  r,b,p=self.fixture();guard.validate_report(r,'pilot','point',b,p);r['passed']=False
  with self.assertRaises(ValueError):guard.validate_report(r,'pilot','point',b,p)
 def test_duplicate_missing_failed_and_out_of_roster_rows_rejected(self):
  for mutation in ('duplicate','missing','failed','outside'):
   r,b,p=self.fixture()
   if mutation=='duplicate':r['rows'][1]=copy.deepcopy(r['rows'][0])
   if mutation=='missing':r['rows'].pop()
   if mutation=='failed':r['rows'][0]['passed']=False
   if mutation=='outside':r['rows'][0]['index']=1
   with self.subTest(mutation=mutation),self.assertRaises(ValueError):guard.validate_report(r,'pilot','point',b,p)
 def test_nonfinite_error_and_wrong_scope_or_receipt_rejected(self):
  for mutation in ('nan','infinite_time','wrong_scope','receipt','threshold'):
   r,b,p=self.fixture();row=r['rows'][0]
   if mutation=='nan':row['metrics']['max_error']=float('nan')
   if mutation=='infinite_time':row['seconds']=float('inf')
   if mutation=='wrong_scope':row['scope']='temporal'
   if mutation=='receipt':row['receipt_sha256']='wrong'
   if mutation=='threshold':row['metrics']['max_error']=1.0001e-4
   with self.subTest(mutation=mutation),self.assertRaises(ValueError):guard.validate_report(r,'pilot','point',b,p)
 def test_scope_and_source_binding_drift_rejected(self):
  r,b,p=self.fixture();r['binding']['dll_sha256']='different'
  with self.assertRaises(ValueError):guard.validate_report(r,'pilot','point',b,p)
 def test_rosters_fixed_and_full_includes_pilot_and_probe_rows(self):
  self.assertEqual(len(guard.roster('full')),5994);self.assertEqual(len(guard.roster('pilot')),6)
  self.assertEqual(guard.roster('probe_oc'),{('OC','california_fold_0',74)})
  self.assertEqual(guard.roster('probe_ep'),{('EP','california_fold_2',573)})
  self.assertTrue(guard.roster('pilot')|guard.roster('probe_oc')|guard.roster('probe_ep')<=guard.roster('full'))
 def test_reused_pid_is_not_owned(self):
  with patch.object(guard.psutil,'Process') as factory:
   factory.return_value.create_time.return_value=200.
   self.assertIsNone(guard.live_identity(12345,100.));factory.return_value.kill.assert_not_called()

class FakeProcessTests(unittest.TestCase):
 def test_normal_fake_process_exit_records_actual_resource_identity(self):
  with tempfile.TemporaryDirectory(dir=PRIVATE) as folder:
   r=guard.supervise([sys.executable,'-B','-c','import time; time.sleep(.2)'],Path(folder)/'process',3,1024**3,dict(os.environ),minimum_available=0)
   self.assertTrue(r['passed']);self.assertEqual(r['exit_code'],0);self.assertTrue(r['tracked']);self.assertGreater(r['peak_process_tree_rss_bytes'],0)
 def test_wall_limit_kills_recorded_process_tree(self):
  code='import subprocess,sys,time; subprocess.Popen([sys.executable,"-B","-c","import time; time.sleep(60)"]); time.sleep(60)'
  with tempfile.TemporaryDirectory(dir=PRIVATE) as folder:
   r=guard.supervise([sys.executable,'-B','-c',code],Path(folder)/'process',.7,1024**3,dict(os.environ),minimum_available=0)
   self.assertFalse(r['passed']);self.assertEqual(r['termination'],'wall_limit');self.assertGreaterEqual(len(r['tracked']),2);self.assertTrue(r['termination_actions']);self.assertEqual(r['survivors'],[])
 def test_memory_breach_fails_and_retains_kill_actions(self):
  with tempfile.TemporaryDirectory(dir=PRIVATE) as folder:
   r=guard.supervise([sys.executable,'-B','-c','import time; time.sleep(60)'],Path(folder)/'process',3,1,dict(os.environ),minimum_available=0)
   self.assertFalse(r['passed']);self.assertEqual(r['termination'],'memory_limit');self.assertEqual(r['survivors'],[]);self.assertTrue(r['termination_actions'])
 def test_lease_loss_stops_owned_child(self):
  def lost():raise ValueError('owner changed')
  with tempfile.TemporaryDirectory(dir=PRIVATE) as folder:
   r=guard.supervise([sys.executable,'-B','-c','import time; time.sleep(60)'],Path(folder)/'process',3,1024**3,dict(os.environ),lost,minimum_available=0)
   self.assertFalse(r['passed']);self.assertIn('lease_lost',r['termination']);self.assertEqual(r['survivors'],[])
class SamplingFailureTests(unittest.TestCase):
 def assert_failed_clean(self,r,folder):
  self.assertFalse(r['passed']);self.assertEqual(r['termination'],'supervision_exception');self.assertIsNotNone(r['primary_error']);self.assertEqual(r['survivors'],[]);self.assertTrue((folder/'supervision.json').is_file())
  for row in r['tracked']:self.assertIsNone(guard.live_identity(row['pid'],row['create_time']))
 def test_access_denied_children_is_retained_and_owned_root_is_killed(self):
  with tempfile.TemporaryDirectory(dir=PRIVATE) as tmp:
   folder=Path(tmp)/'process'
   with patch.object(guard.psutil.Process,'children',side_effect=guard.psutil.AccessDenied(pid=123)):
    r=guard.supervise([sys.executable,'-B','-c','import time; time.sleep(60)'],folder,3,1024**3,dict(os.environ),minimum_available=0)
   self.assert_failed_clean(r,folder);self.assertEqual(r['primary_error']['error_type'],'AccessDenied');self.assertTrue(r['descendant_discovery_uncertain']);self.assertTrue(r['cleanup_errors'])
 def test_memory_and_cpu_sampling_exceptions_cleanup(self):
  for method,error in [('memory_info',guard.psutil.AccessDenied(pid=123)),('cpu_times',RuntimeError('injected CPU sampler error'))]:
   with self.subTest(method=method),tempfile.TemporaryDirectory(dir=PRIVATE) as tmp:
    folder=Path(tmp)/'process'
    with patch.object(guard.psutil.Process,method,side_effect=error):
     r=guard.supervise([sys.executable,'-B','-c','import time; time.sleep(60)'],folder,3,1024**3,dict(os.environ),minimum_available=0)
    self.assert_failed_clean(r,folder);self.assertEqual(r['primary_error']['phase'],method)
 def test_virtual_memory_failure_after_launch_cleanup(self):
  actual=guard.psutil.virtual_memory();calls=0
  def sampler():
   nonlocal calls
   calls+=1
   if calls>1:raise RuntimeError('injected available-memory error')
   return actual
  with tempfile.TemporaryDirectory(dir=PRIVATE) as tmp:
   folder=Path(tmp)/'process'
   with patch.object(guard.psutil,'virtual_memory',side_effect=sampler):
    r=guard.supervise([sys.executable,'-B','-c','import time; time.sleep(60)'],folder,3,1024**3,dict(os.environ),minimum_available=0)
   self.assert_failed_clean(r,folder);self.assertEqual(r['primary_error']['phase'],'available_memory')
 def test_initial_identity_denial_uses_owned_handle_and_retains_uncertainty(self):
  with tempfile.TemporaryDirectory(dir=PRIVATE) as tmp:
   folder=Path(tmp)/'process'
   with patch.object(guard.psutil.Process,'create_time',side_effect=guard.psutil.AccessDenied(pid=123)):
    r=guard.supervise([sys.executable,'-B','-c','import time; time.sleep(60)'],folder,3,1024**3,dict(os.environ),minimum_available=0)
   self.assert_failed_clean(r,folder);self.assertTrue(r['descendant_discovery_uncertain']);self.assertTrue(any(a['operation']=='kill_owned_popen_handle' and a['requested'] for a in r['termination_actions']))
 def test_unverified_identity_is_not_reported_as_gone(self):
  with patch.object(guard.psutil,'Process',side_effect=guard.psutil.AccessDenied(pid=123)):
   with self.assertRaises(guard.psutil.AccessDenied):guard.live_identity(123,100.)
class NormalExitGraceTests(unittest.TestCase):
 def command(self,delay=60,exitcode=0):
  return [sys.executable,'-B','-c',f'import subprocess,sys,time; subprocess.Popen([sys.executable,"-B","-c","import time; time.sleep({delay})"]); time.sleep(.35); sys.exit({exitcode})']
 def run_case(self,command,seconds=5,lease=lambda:None):
  with tempfile.TemporaryDirectory(dir=PRIVATE) as tmp:
   r=guard.supervise(command,Path(tmp)/'process',seconds,1024**3,dict(os.environ),lease,minimum_available=0)
  self.assertEqual(r['survivors'],[])
  for row in r['tracked']:self.assertIsNone(guard.live_identity(row['pid'],row['create_time']))
  return r
 def test_delayed_normal_helper_exit_is_success_without_kill(self):
  r=self.run_case(self.command(.8));self.assertTrue(r['passed']);self.assertTrue(r['normal_exit_grace_started']);self.assertGreater(r['normal_exit_grace_elapsed_seconds'],.1);self.assertLess(r['normal_exit_grace_elapsed_seconds'],3);self.assertEqual(r['termination_actions'],[])
 def test_persistent_helper_fails_and_is_killed_after_grace(self):
  r=self.run_case(self.command());self.assertFalse(r['passed']);self.assertEqual(r['termination'],'lingering_owned_descendants');self.assertGreaterEqual(r['normal_exit_grace_elapsed_seconds'],3);self.assertTrue(r['termination_actions'])
 def test_original_wall_cap_limits_grace(self):
  r=self.run_case(self.command(),seconds=.65);self.assertFalse(r['passed']);self.assertEqual(r['termination'],'wall_limit');self.assertTrue(r['normal_exit_grace_started']);self.assertLess(r['normal_exit_grace_elapsed_seconds'],.6)
 def test_nonzero_root_exit_does_not_receive_grace(self):
  r=self.run_case(self.command(exitcode=2));self.assertFalse(r['passed']);self.assertFalse(r['normal_exit_grace_started']);self.assertEqual(r['exit_code'],2)
 def test_lease_loss_during_grace_fails_and_cleans(self):
  real=guard.subprocess.Popen;roots=[]
  def create(*a,**k):
   child=real(*a,**k);roots.append(child);return child
  def lease():
   if roots and roots[0].poll()==0:raise ValueError('lease revoked in grace')
  with patch.object(guard.subprocess,'Popen',side_effect=create):r=self.run_case(self.command(),lease=lease)
  self.assertFalse(r['passed']);self.assertTrue(r['normal_exit_grace_started']);self.assertIn('lease_lost',r['termination'])
 def test_memory_breach_during_grace_fails_and_cleans(self):
  from types import SimpleNamespace
  real=guard.subprocess.Popen;sample=guard.psutil.Process.memory_info;roots=[]
  def create(*a,**k):
   child=real(*a,**k);roots.append(child);return child
  def memory(p):return SimpleNamespace(rss=2*1024**3) if roots and roots[0].poll()==0 else sample(p)
  with patch.object(guard.subprocess,'Popen',side_effect=create),patch.object(guard.psutil.Process,'memory_info',new=memory):r=self.run_case(self.command())
  self.assertFalse(r['passed']);self.assertTrue(r['normal_exit_grace_started']);self.assertEqual(r['termination'],'memory_limit')
 def test_identity_error_during_grace_fails_and_cleans(self):
  real=guard.subprocess.Popen;identity=guard.live_identity;roots=[];raised=False
  def create(*a,**k):
   child=real(*a,**k);roots.append(child);return child
  def check(pid,created):
   nonlocal raised
   if roots and roots[0].poll()==0 and pid!=roots[0].pid and not raised:
    raised=True;raise guard.psutil.AccessDenied(pid=pid)
   return identity(pid,created)
  with patch.object(guard.subprocess,'Popen',side_effect=create),patch.object(guard,'live_identity',side_effect=check):r=self.run_case(self.command())
  self.assertFalse(r['passed']);self.assertTrue(r['normal_exit_grace_started']);self.assertEqual(r['termination'],'supervision_exception');self.assertEqual(r['primary_error']['phase'],'identity')
if __name__=='__main__':unittest.main()
