"""Invented fixtures only: candidate scheduling equivalence, not a benchmark."""
import math,tempfile,threading,time,unittest
from pathlib import Path
from unittest.mock import patch
import numpy as np
from threadpoolctl import threadpool_limits
from engine.cpu_build import build_shared
from experiments.s04b_joint_nuisance import model
from experiments.s04b_joint_execution.parallel_chunks import OrderedChunkScheduler,ParallelPhase
from test_s04b_joint_nuisance import fixture


class NativeEquivalence(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.limits=threadpool_limits(limits=2);cls.limits.__enter__()
        cls.temp=tempfile.TemporaryDirectory(prefix='joint_scheduler_controls_')
        cls.receipt=build_shared(model.HERE/'attenuation.cpp',Path(cls.temp.name)/'native',dependency_root=model.HERE)
        cls.native=model.Native(cls.receipt['library'])
    @classmethod
    def tearDownClass(cls):
        try:cls.temp.cleanup()
        except PermissionError:pass
        cls.limits.__exit__(None,None,None)
    def compare_case(self,rows,eta,name,order):
        original=fixture(self.native)
        if rows is not None:
            for grid in original._grids.values():
                for key in('r2','coeff','b','area'):grid[key]=grid[key][:rows]
                grid['space_nodes']=len(grid['b'])
        theta=np.array([-1.2,.15,.3,math.log(.07),1.4,eta,math.log(3.),math.log(.25)])
        with OrderedChunkScheduler()as scheduler:
            candidate=ParallelPhase(original.a,original.m,{},self.native,scheduler=scheduler)
            candidate._grids=original._grids;candidate.plan=lambda o:candidate._grids[o]
            expected,gradient=original.evaluate(theta,name,order)
            actual,parallel_gradient=candidate.evaluate(theta,name,order)
            for key in expected:
                self.assertEqual(np.asarray(expected[key],dtype='float64').tobytes(),np.asarray(actual[key],dtype='float64').tobytes(),key)
            self.assertEqual(gradient.tobytes(),parallel_gradient.tobytes())
            self.assertEqual(original.deficit(theta,name,order).tobytes(),candidate.deficit(theta,name,order).tobytes())
    def test_even_multichunk_zero_and_positive_eta_all_arms(self):
        for name in('LI','LIplus_immigrant','LIplus_inclusive'):
            for eta in(0.,.4):
                with self.subTest(name=name,eta=eta):self.compare_case(1024,eta,name,8)
    def test_odd_and_partial_final_chunks_all_arms(self):
        for name in('LI','LIplus_immigrant','LIplus_inclusive'):
            with self.subTest(name=name):self.compare_case(513,.4,name,16)
    def test_fine_multichunk_total_and_cache_parameter_changes(self):
        original=fixture(self.native);theta=np.array([-1.2,.15,.3,math.log(.07),1.4,.4,math.log(3.),math.log(.25)])
        with OrderedChunkScheduler()as scheduler:
            candidate=ParallelPhase(original.a,original.m,{},self.native,scheduler=scheduler)
            candidate._grids=original._grids;candidate.plan=lambda o:candidate._grids[o]
            for step in(0.,.01,-.02,0.):
                theta[3]+=step
                for order in(8,16):
                    a,ag=original.evaluate(theta,'LIplus_inclusive',order);b,bg=candidate.evaluate(theta,'LIplus_inclusive',order)
                    self.assertEqual(np.asarray(list(a.values())).tobytes(),np.asarray(list(b.values())).tobytes());self.assertEqual(ag.tobytes(),bg.tobytes())
    def test_native_error_is_read_in_worker_thread(self):
        phase=fixture(self.native);theta=np.array([-1.2,.15,.3,math.log(.07),1.4,-1.,math.log(3.),math.log(.25)])
        with OrderedChunkScheduler()as scheduler:
            with self.assertRaisesRegex(ArithmeticError,'invalid attenuation parameter'):scheduler.deficit(phase,theta,'LI',8)


class SchedulingControls(unittest.TestCase):
    def fixture(self,failing=False):
        state={'active':0,'max_active':0,'prepares':0,'calls':[],'first_batch':threading.Barrier(2),'finished_second':threading.Event()};lock=threading.Lock()
        class Slice:
            def __matmul__(self,other):
                with lock:
                    if state['active']:raise AssertionError('BLAS overlaps native work')
                    state['prepares']+=1
                return np.zeros((self.count,len(other[0])))
        class Coeff:
            def __getitem__(self,sl):
                value=Slice();value.count=min(sl.stop,513)-sl.start;return value
        class Native:
            def integrate(self,pt,marks,r2,area,b,t,w,h,theta,T0):
                index=int(r2[0,0])//256
                with lock:
                    state['active']+=1;state['max_active']=max(state['max_active'],state['active']);state['calls'].append(index)
                    if state['active']>2:raise AssertionError('More than two native calls')
                    if index<2 and state['prepares']!=2:raise AssertionError('Native started before paired BLAS preparation')
                try:
                    if index<2:state['first_batch'].wait(timeout=2)
                    if index==0:state['finished_second'].wait(timeout=2)
                    if index==1:state['finished_second'].set()
                    if failing and index==0:raise ArithmeticError('invented native failure')
                    return np.full(9,[1e16,-1e16,1.][index])
                finally:
                    with lock:state['active']-=1
        class Phase:
            native=Native();a={'parent_time':np.array([0.]),'parent_excess':np.array([0.])};m={'T0':1.};_temporal={}
            def plan(self,order):return grid
            def check(self):pass
        grid={'b':np.ones(513),'area':np.ones(513),'r2':np.arange(513.).reshape(-1,1),'coeff':Coeff(),'t':np.array([.2,.8]),'w':np.array([.5,.5])}
        return Phase(),state
    def test_two_calls_no_blas_overlap_and_original_ordered_sum(self):
        phase,state=self.fixture();theta=np.array([-1.,0.,.3,-2.,1.4,.2,0.,0.])
        with OrderedChunkScheduler()as scheduler:result=scheduler.deficit(phase,theta,'LIplus_inclusive',8)
        np.testing.assert_array_equal(result,np.ones(9));self.assertEqual(state['max_active'],2);self.assertEqual(state['active'],0);self.assertEqual(state['prepares'],3)
    def test_native_failure_drains_batch_and_does_not_start_another(self):
        phase,state=self.fixture(True);theta=np.array([-1.,0.,.3,-2.,1.4,.2,0.,0.])
        with OrderedChunkScheduler()as scheduler:
            with self.assertRaisesRegex(ArithmeticError,'invented native failure'):scheduler.deficit(phase,theta,'LIplus_inclusive',8)
            self.assertEqual(state['active'],0);self.assertEqual(sorted(state['calls']),[0,1]);self.assertEqual(state['prepares'],2)
    def test_closed_or_reentrant_scheduler_is_rejected(self):
        phase,_=self.fixture();scheduler=OrderedChunkScheduler();theta=np.zeros(8)
        scheduler._lock.acquire()
        try:
            with self.assertRaisesRegex(RuntimeError,'already belongs'):scheduler.deficit(phase,theta,'LI',8)
        finally:scheduler._lock.release()
        scheduler.close()
        with self.assertRaisesRegex(RuntimeError,'closed'):scheduler.deficit(phase,theta,'LI',8)
    def test_submission_failure_waits_for_already_submitted_work(self):
        scheduler=OrderedChunkScheduler();phase,state=self.fixture();theta=np.zeros(8)
        started=threading.Event();release=threading.Event();finished=threading.Event()
        class OneCall:
            def integrate(self,*args):
                state['active']+=1;state['calls'].append(0);started.set()
                try:
                    if not release.wait(timeout=2):raise RuntimeError('fixture release timed out')
                    return np.ones(9)
                finally:state['active']-=1;finished.set()
        phase.native=OneCall();submit=scheduler._pool.submit;count=0
        def fail_second(*args):
            nonlocal count
            count+=1
            if count==1:return submit(*args)
            self.assertTrue(started.wait(timeout=2));release.set();raise RuntimeError('invented submission failure')
        with patch.object(scheduler._pool,'submit',side_effect=fail_second):
            with self.assertRaisesRegex(RuntimeError,'submission'):scheduler.deficit(phase,theta,'LIplus_inclusive',8)
        self.assertTrue(finished.is_set());self.assertEqual(state['active'],0);self.assertEqual(state['calls'],[0]);self.assertEqual(count,2);scheduler.close()
    def test_process_wide_lock_prevents_two_scheduler_instances(self):
        phase,_=self.fixture();first=OrderedChunkScheduler();second=OrderedChunkScheduler()
        first._lock.acquire()
        try:
            with self.assertRaisesRegex(RuntimeError,'already belongs'):second.deficit(phase,np.zeros(8),'LI',8)
        finally:first._lock.release();first.close();second.close()


if __name__=='__main__':unittest.main()
