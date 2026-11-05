"""Exact-input custody and tiny independent likelihood fixtures; no campaigns."""
import importlib.util
import json
import math
from pathlib import Path
import sys
import tempfile
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from types import SimpleNamespace
import unittest

ROOT=Path(__file__).resolve().parents[1]
REPRO=ROOT/'reproduction/synthetic'
sys.path.insert(0,str(REPRO))
spec=importlib.util.spec_from_file_location('synthetic_replay_tests_subject',REPRO/'replay.py')
replay=importlib.util.module_from_spec(spec);spec.loader.exec_module(replay)
import numpy as np
oracle_spec=importlib.util.spec_from_file_location('synthetic_independent_oracle',REPRO/'source/direct_oracle.py')
oracle=importlib.util.module_from_spec(oracle_spec);oracle_spec.loader.exec_module(oracle)


class SyntheticInputTests(unittest.TestCase):
    def test_complete_exact_banks(self):
        manifest=replay.read(REPRO/'input_manifest.json')
        result=replay.verify_inputs(REPRO,manifest)
        self.assertEqual(result['s04b_histories'],80)
        self.assertEqual(result['s01_histories'],2149)
        bank=replay.read(REPRO/manifest['s01']['bank'])
        self.assertEqual(sum('stage2_recovery_fit' in r for r in bank['cases']),397)
        self.assertEqual(sum(r['clock_mode']=='paired_clock' for r in bank['cases']),1)
        self.assertTrue(all(r['original_restricted_state_bundled'] is False for r in bank['cases']))

    def test_no_path_escape_or_hash_acceptance(self):
        with self.assertRaises(ValueError):replay.resolve_input(REPRO,'../../README.md')
        with tempfile.TemporaryDirectory() as temp:
            p=Path(temp)/'x';p.write_bytes(b'changed')
            with self.assertRaises(ValueError):
                replay.verify_inputs(temp,{'files':[dict(path='x',bytes=7,sha256='0'*64)]})

    def test_all_training_selections_and_tamper_rejection(self):
        manifest=replay.read(REPRO/'input_manifest.json')
        for case in manifest['s04b']['cases']:
            for path in case['fits'].values():replay.saved_selection(replay.read(REPRO/path))
        fit=replay.read(REPRO/manifest['s04b']['cases'][0]['fits']['LI'])
        fit['selected']['nll']+=1.
        with self.assertRaises(ValueError):replay.saved_selection(fit)


class TinyNativeLikelihoodTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp=tempfile.TemporaryDirectory()
        cls.libs=replay.build(Path(cls.temp.name)/'native')
        cls.native=replay.Native(cls.libs['cpu'])

    @classmethod
    def tearDownClass(cls):
        # Windows cannot unlink a loaded DLL. Drop handles before cleanup.
        if sys.platform=='win32':
            import ctypes
            ctypes.windll.kernel32.FreeLibrary.argtypes=[ctypes.c_void_p]
            ctypes.windll.kernel32.FreeLibrary(cls.native.lib._handle)
        cls.temp.cleanup()

    def fixture(self):
        return dict(parents=np.array([[0.,0.,0.,.3,.2,1.],[1.,1.,0.,.4,.1,1.]]),
                    events=np.array([[1.,.2,.3,.4,.2,.25],[2.,1.,1.,.3,.1,.25]]),
                    space=np.array([[0.,0.,.5,.3,.25],[1.,1.,.5,.3,.25]]),
                    times=np.array([.5,1.,1.5,2.]),weights=np.array([.2,.3,.3,.2]),
                    meta=np.array([-2.,.2,.35,.05,1.3,3.,1.2,-.1,10.]))

    def native_value(self,data,parameters,plus,inclusive):
        handle=self.native.create(data)
        try:return self.native.evaluate(handle,parameters,plus,inclusive)
        finally:self.native.free(handle)

    def test_scalar_oracle_ties_floor_and_mark_stress(self):
        data=self.fixture()
        for plus,inclusive in [(0,0),(1,0),(1,1)]:
            for eta in [0.,.3,4.]:
                parameters=[eta,math.log(5.),math.log(7.)]
                expected=oracle.evaluate(*(data[k] for k in replay.KEYS),parameters,plus,inclusive)
                actual=self.native_value(data,parameters,plus,inclusive)
                np.testing.assert_allclose(actual,expected,rtol=0,atol=2e-12)
        empty=self.fixture();empty['parents']=np.empty((0,6))
        parameters=[2.,math.log(30.),math.log(7.)]
        np.testing.assert_allclose(self.native_value(empty,parameters,1,1),oracle.evaluate(*(empty[k] for k in replay.KEYS),parameters,True,True),rtol=0,atol=2e-12)

    def test_chunk_additivity_counts_events_and_marks_once(self):
        data=self.fixture();parameters=[.5,math.log(15.),math.log(.25)]
        np_,ne,ns,nt=(len(data[k]) for k in replay.KEYS[:4])
        shared=8*(9*np_+10*ne+5*nt+nt*np_)+4*(nt+1)
        budget=shared+8*(9+2*np_+2*nt)
        pieces=list(replay.chunks(data,budget))
        self.assertEqual(len(pieces),2)
        self.assertEqual(sum(len(p['events']) for p in pieces),len(data['events']))
        for plus,inclusive in [(0,0),(1,0),(1,1)]:
            total=sum((self.native_value(p,parameters,plus,inclusive) for p in pieces),np.zeros(6))
            np.testing.assert_allclose(total,self.native_value(data,parameters,plus,inclusive),rtol=0,atol=2e-12)

    def test_native_rejects_nonfinite_stress_parameters(self):
        data=self.fixture();handle=self.native.create(data)
        try:
            with self.assertRaises(ArithmeticError):self.native.evaluate(handle,[float('nan'),math.log(5.),math.log(7.)],1,1)
        finally:self.native.free(handle)


class ParallelOrchestrationTests(unittest.TestCase):
    """Deterministic scheduler controls; no scientific histories evaluated."""
    def executor(self,**kwargs):
        self.assertEqual(kwargs['mp_context'].get_start_method(),'spawn')
        self.assertIs(kwargs['initializer'],replay._score_worker_init)
        pool=ThreadPoolExecutor(max_workers=kwargs['max_workers'])
        release=getattr(self,'release_after_second',None)
        if release:
            original_submit=pool.submit
            def controlled_submit(function,case):
                future=original_submit(function,case)
                if case['case_id']=='b':future.add_done_callback(lambda completed:release.set())
                return future
            pool.submit=controlled_submit
        return pool

    def test_total_thread_budget_and_nonfinite_deadline(self):
        replay.validate_resources(1,4,256,60.)
        replay.validate_resources(4,1,256,60.)
        for args in [(4,2,256,60.),(5,1,256,60.),(0,1,256,60.),(1,1,256,float('inf'))]:
            with self.assertRaises(ValueError):replay.validate_resources(*args)

    def test_out_of_order_completion_preserves_original_roster(self):
        completed_second=threading.Event();self.release_after_second=completed_second;calls=[]
        def worker(case):
            cid=case['case_id'];calls.append(cid)
            if cid=='a':self.assertTrue(completed_second.wait(5))
            return dict(case_id=cid,passed=True,report=cid+'.json')
        with tempfile.TemporaryDirectory() as temp:
            result=dict(passed=False,cases=[])
            passed=replay.parallel_score_cases([dict(case_id=c) for c in 'abc'],{'cpu':'unused','radial':'unused'},Path(temp),SimpleNamespace(workers=2,threads=1,chunk_mib=256),time.monotonic()+10,result,self.executor,worker)
            self.assertTrue(passed)
            self.assertEqual([c['case_id'] for c in result['cases']],list('abc'))
            self.assertEqual(sorted(calls),list('abc'))
            self.assertEqual(result['unstarted_cases'],[])
            self.assertEqual(result['active_cases'],[])

    def test_failure_stops_dispatch_and_retains_running_case(self):
        failure_ready=threading.Event();self.release_after_second=failure_ready;calls=[]
        def worker(case):
            cid=case['case_id'];calls.append(cid)
            if cid=='a':self.assertTrue(failure_ready.wait(5));return dict(case_id=cid,passed=True,report=cid+'.json')
            if cid=='b':raise RuntimeError('deliberate worker failure')
            self.fail('Scheduler launched a new case after failure')
        with tempfile.TemporaryDirectory() as temp:
            result=dict(passed=False,cases=[])
            passed=replay.parallel_score_cases([dict(case_id=c) for c in 'abcd'],{'cpu':'unused','radial':'unused'},Path(temp),SimpleNamespace(workers=2,threads=1,chunk_mib=256),time.monotonic()+10,result,self.executor,worker)
            self.assertFalse(passed)
            self.assertEqual(sorted(calls),list('ab'))
            self.assertEqual([c['case_id'] for c in result['cases']],list('ab'))
            self.assertEqual(result['unstarted_cases'],list('cd'))
            failure=replay.read(Path(temp)/'b.json')
            self.assertFalse(failure['passed']);self.assertEqual(failure['error_type'],'RuntimeError')


if __name__=='__main__':unittest.main()
