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
class GraceProcessTree:
 """Deterministic OS double; production supervise() still owns all decisions.

 Time advances only through the supervisor's requested sleep. Root/helper
 lifetimes, identity checks and kill effects are explicit, so host scheduling
 cannot consume a wall budget before the branch under test is reached.
 Real-process discovery/cleanup coverage remains in the classes above.
 """
 def __init__(self,helper_exit=60,root_code=0,fault=None):
  self.clock=0.;self.observed_exit=None;self.fault=fault;self.injected=False
  self.root=self.Process(self,910001,100.,.35,root_code)
  self.helper=self.Process(self,910002,101.,helper_exit,0)
  self.members={p.pid:p for p in (self.root,self.helper)}
 class Process:
  def __init__(self,tree,pid,created,exits,code):
   self.tree,self.pid,self.created,self.exits,self.code=tree,pid,created,exits,code
   self.killed=False;self.returncode=None
  def create_time(self):return self.created
  def is_running(self):return not self.killed and self.tree.clock<self.exits
  def status(self):return 'running' if self.is_running() else guard.psutil.STATUS_ZOMBIE
  def children(self,recursive=True):
   return [self.tree.helper] if self is self.tree.root and self.is_running() and self.tree.helper.is_running() else []
  def memory_info(self):
   from types import SimpleNamespace
   # Preserve the prior fixture fix: observe the supervisor's last poll;
   # never perform a fresh poll from a fault injector.
   breach=self.tree.fault=='memory' and self.tree.observed_exit==0
   if breach:self.tree.injected=True
   return SimpleNamespace(rss=2*1024**3 if breach else 4096)
  def cpu_times(self):
   from types import SimpleNamespace
   return SimpleNamespace(user=self.tree.clock/100,system=0.)
  def poll(self):
   if not self.is_running():self.returncode=-9 if self.killed else self.code
   if self is self.tree.root:self.tree.observed_exit=self.returncode
   return self.returncode
  def kill(self):self.killed=True;self.poll()
  def wait(self,timeout=None):
   if self.is_running():raise guard.subprocess.TimeoutExpired('deterministic fixture',timeout)
   return self.poll()
 def process(self,pid):
  if pid not in self.members:raise guard.psutil.NoSuchProcess(pid)
  return self.members[pid]
 def popen(self,*args,**kwargs):return self.root
 def sleep(self,seconds):
  if seconds<0:raise AssertionError('Negative supervisor sleep')
  # Real monotonic time progresses even for sleep(0); avoid a float-equality
  # deadlock when the grace deadline differs by less than one clock tick.
  self.clock+=max(seconds,1e-9)
 def wait_procs(self,processes,timeout=None):
  return ([p for p in processes if not p.is_running()],[p for p in processes if p.is_running()])
 def lease(self):
  if self.fault=='lease' and self.observed_exit==0:
   self.injected=True;raise ValueError('lease revoked in grace')

class NormalExitGraceTests(unittest.TestCase):
 def run_case(self,helper_exit=60,root_code=0,seconds=5,fault=None):
  from types import SimpleNamespace
  tree=GraceProcessTree(helper_exit,root_code,fault);identity=guard.live_identity
  def check(pid,created):
   if fault=='identity' and tree.observed_exit==0 and pid==tree.helper.pid and not tree.injected:
    tree.injected=True;raise guard.psutil.AccessDenied(pid=pid)
   return identity(pid,created)
  with tempfile.TemporaryDirectory(dir=PRIVATE) as tmp, \
       patch.object(guard.subprocess,'Popen',new=tree.popen), \
       patch.object(guard.psutil,'Process',new=tree.process), \
       patch.object(guard.psutil,'virtual_memory',return_value=SimpleNamespace(available=4*1024**3)), \
       patch.object(guard.psutil,'wait_procs',new=tree.wait_procs), \
       patch.object(guard.time,'monotonic',new=lambda:tree.clock), \
       patch.object(guard.time,'sleep',new=tree.sleep), \
       patch.object(guard,'live_identity',new=check):
   folder=Path(tmp)/'process'
   r=guard.supervise(['deterministic process-tree fixture'],folder,seconds,1024**3,dict(os.environ),tree.lease,minimum_available=0)
   self.assertTrue((folder/'supervision.json').is_file());self.assertEqual(r['survivors'],[])
   self.assertEqual({row['pid'] for row in r['tracked']},set(tree.members))
   for row in r['tracked']:self.assertIsNone(guard.live_identity(row['pid'],row['create_time']))
   self.assertFalse(any(p.is_running() for p in tree.members.values()))
   if fault:self.assertTrue(tree.injected,'Fault must occur after supervisor-observed root exit')
  return r
 def test_delayed_normal_helper_exit_is_success_without_kill(self):
  r=self.run_case(helper_exit=.8);self.assertTrue(r['passed']);self.assertTrue(r['normal_exit_grace_started']);self.assertGreater(r['normal_exit_grace_elapsed_seconds'],.1);self.assertLess(r['normal_exit_grace_elapsed_seconds'],3);self.assertEqual(r['termination_actions'],[])
 def test_persistent_helper_fails_and_is_killed_after_grace(self):
  r=self.run_case();self.assertFalse(r['passed']);self.assertEqual(r['termination'],'lingering_owned_descendants');self.assertGreaterEqual(r['normal_exit_grace_elapsed_seconds'],3);self.assertTrue(r['termination_actions']);self.assertTrue(any(a['requested'] for a in r['termination_actions']))
 def test_original_wall_cap_limits_grace(self):
  r=self.run_case(seconds=.65);self.assertFalse(r['passed']);self.assertEqual(r['termination'],'wall_limit');self.assertTrue(r['normal_exit_grace_started']);self.assertLess(r['normal_exit_grace_elapsed_seconds'],.6);self.assertLessEqual(r['elapsed_seconds'],.65+1e-8)
 def test_nonzero_root_exit_does_not_receive_grace(self):
  r=self.run_case(root_code=2);self.assertFalse(r['passed']);self.assertFalse(r['normal_exit_grace_started']);self.assertEqual(r['exit_code'],2)
 def test_lease_loss_during_grace_fails_and_cleans(self):
  r=self.run_case(fault='lease');self.assertFalse(r['passed']);self.assertTrue(r['normal_exit_grace_started']);self.assertIn('lease_lost',r['termination'])
 def test_memory_breach_during_grace_fails_and_cleans(self):
  r=self.run_case(fault='memory');self.assertFalse(r['passed']);self.assertTrue(r['normal_exit_grace_started']);self.assertEqual(r['termination'],'memory_limit')
 def test_identity_error_during_grace_fails_and_cleans(self):
  r=self.run_case(fault='identity');self.assertFalse(r['passed']);self.assertTrue(r['normal_exit_grace_started']);self.assertEqual(r['termination'],'supervision_exception');self.assertEqual(r['primary_error']['phase'],'identity')
if __name__=='__main__':unittest.main()
