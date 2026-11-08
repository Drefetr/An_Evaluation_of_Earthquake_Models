"""Invented metadata and full-case controls; no historical fits/native calls."""
import argparse
from contextlib import ExitStack, nullcontext
import copy
import datetime as dt
import hashlib
import json
from pathlib import Path
import tempfile
import time
from types import SimpleNamespace
import unittest
from unittest.mock import patch
import zipfile

import numpy as np
from experiments import s04b_refined_cpu_reader as M
from experiments.s04b_refined_cpu_reader import reader as R
from experiments.s04b_exposure_refinement import adapter as A, case_driver as D
from experiments.s04b_joint_execution import driver as legacy
from experiments.s04b_joint_nuisance import fit
from tests import test_joint_exposure_refinement as fixtures


def digest(data):
    return hashlib.sha256(data).hexdigest()


class InventedMetadata:
    def __init__(self, root):
        self.root = root
        def put(name, value):
            path = root/name; path.parent.mkdir(parents=True, exist_ok=True)
            if isinstance(value, bytes): path.write_bytes(value)
            else: R.write(path, value)
            return path
        self.put = put
        self.case = 'S6_narrow_short_total_seed410606'
        self.library = b'\x7fELF\x02\x01'+b'\x00'*12+(62).to_bytes(2, 'little')+b'invented-not-executable'
        build = dict(passed=True, library_sha256=digest(self.library), source_sha256=digest(b'invented source'))
        self.build = (json.dumps(build)+'\n').encode()
        archive = root/'input.zip'
        with zipfile.ZipFile(archive, 'w') as z:
            z.writestr('build/attenuation.so', self.library); z.writestr('build/build_receipt.json', self.build)
            z.writestr('unneeded/history', b'must not extract')
        put('experiments/s04b_joint_nuisance/attenuation.cpp', b'invented source')
        put('experiments/s04b_joint_nuisance/protocol.json', {'invented': True})
        review=put('native_review.json',{'audit_passed':True,'passed':False,'scope':'Invented native custody'})
        old = dict(archive='input.zip', archive_sha256=M.sha(archive), library_member='build/attenuation.so', build_receipt_member='build/build_receipt.json',review='native_review.json',review_sha256=M.sha(review))
        self.amendment = dict(source_sha256={'experiments/s04b_joint_nuisance/attenuation.cpp': digest(b'invented source')},
            full_sequence=[self.case]+['invented-%02d'%i for i in range(79)], permanent_unknown=old,
            original_native={'library_sha256': digest(self.library), 'build_receipt_sha256': digest(self.build)},
            original_scientific_protocol_sha256=M.sha(root/'experiments/s04b_joint_nuisance/protocol.json'),
            shared_run={'expires_utc': '2000-01-01T00:00:00+00:00'},
            case_slots=[dict(case_id=self.case,mode='untouched',wall_seconds=2520,scientific_seconds=2490)])
        ap = put('experiments/s04b_exposure_refinement/protocol.json', self.amendment)
        code = put('experiments/s04b_exposure_refinement/adapter.py', b'# invented core\n')
        core = dict(self.amendment['source_sha256'])
        core.update({q.relative_to(root).as_posix(): M.sha(q) for q in (ap,code)})
        put(M.ENTRYPOINT, b'# invented reader\n')
        self.profile = dict(schema='joint_refined_cpu_reader_profile_v1',version='fixture',entrypoint=M.ENTRYPOINT,operation='fit',
            numerical_version='joint_exposure_refinement_v1',amendment_protocol={'path':ap.relative_to(root).as_posix(),'sha256':M.sha(ap)},
            scientific_protocol={'path':'experiments/s04b_joint_nuisance/protocol.json','sha256':M.sha(root/'experiments/s04b_joint_nuisance/protocol.json')},
            core_source_sha256=core,producer_source_paths=sorted([M.PROFILE,M.ENTRYPOINT]),case_ids=self.amendment['full_sequence'],
            bundled_native=dict(archive_reference={'path':old['archive'],'sha256':old['archive_sha256']},
                review_reference={'path':old['review'],'sha256':old['review_sha256']},
                library_member=old['library_member'],build_receipt_member=old['build_receipt_member'],**self.amendment['original_native']),
            supported_runtime=dict(system='Linux',architecture='x86_64',byteorder='little',python_implementation='CPython',python_major_minor=[3,13],numpy='2.2.6',scipy='1.15.3'))
        put(M.PROFILE, self.profile)
    def args(self, output):
        return argparse.Namespace(case_id=self.case,output=output,wall_seconds=2520.,rss_mib=6144.,headroom_mib=2048.,execution_record=None)


class MetadataControls(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name); self.repo = self.root/'repo'; self.repo.mkdir()
        self.f = InventedMetadata(self.repo)
        self.stack = ExitStack(); self.addCleanup(self.stack.close)
        self.stack.enter_context(patch.object(M,'REPO',self.repo)); self.stack.enter_context(patch.object(R,'REPO',self.repo))
    def test_complete_source_map_and_profile_custody(self):
        p = M.verify_profile(); produced = M.producer()
        self.assertEqual(produced['core_source_sha256'],p['core_source_sha256'])
        self.assertEqual(produced['execution_source_sha256'],M.source_identity())
        self.assertIsNone(produced['source_review'])
        (self.repo/'experiments/s04b_exposure_refinement/adapter.py').write_bytes(b'# changed')
        with self.assertRaisesRegex(ValueError,'Frozen core'):M.source_identity()
    def test_changed_producer_must_be_in_genuine_source_review(self):
        full = M.source_identity()
        path = self.f.put('review.json',dict(passed=True,live_agent_review=True,reviewed_files_sha256=full))
        reference = dict(path='review.json',sha256=M.sha(path))
        self.assertEqual(M.producer(reference)['source_review'],reference)
        (self.repo/M.ENTRYPOINT).write_bytes(b'# another reader')
        with self.assertRaisesRegex(ValueError,'misses actual producer'):M.producer(reference)
    def test_contradictory_review_flag_rejects(self):
        path = self.f.put('review.json',dict(passed=True,live_agent_review=True,live_agent_review_performed=False,reviewed_files_sha256=M.source_identity()))
        with self.assertRaisesRegex(ValueError,'not accepted'):M.producer(dict(path='review.json',sha256=M.sha(path)))
    def test_post_expiry_local_plan_and_expired_author_no_fallback(self):
        args = self.f.args(self.root/'out')
        with patch.object(R,'platform_check'):
            request = R.plan(args,time.monotonic(),['invented'])
            self.assertEqual(request['mode'],'fresh_local');self.assertNotIn('expires_utc',request)
            record=dict(mode='exposure_refinement_case',case_id=self.f.case,case_ids=[self.f.case],source_sha256=M.source_identity(),
                wall_seconds=2520,scientific_seconds=2490,sampled_process_tree_rss_cap_bytes=6442450944,minimum_host_free_bytes=2147483648,
                expires_utc='2000-01-01T00:00:00+00:00',reader_source_review=None)
            path=self.f.put('expired.json',record);args.execution_record=path
            with self.assertRaisesRegex(ValueError,'expired'):R.plan(args,time.monotonic(),['invented'])
    def test_invalid_limits_and_case_rejected(self):
        with patch.object(R,'platform_check'):
            for bad in (0,-1,float('nan'),float('inf'),True,30):
                args=self.f.args(self.root/'out');args.wall_seconds=bad
                with self.assertRaises(ValueError):R.plan(args,time.monotonic(),['invented'])
            args=self.f.args(self.root/'out');args.case_id='not-a-supplied-history'
            with self.assertRaisesRegex(ValueError,'roster'):R.plan(args,time.monotonic(),['invented'])
    def test_only_two_exact_native_members_are_extracted(self):
        out=self.root/'out';out.mkdir();receipt,library,build=R.extract_native(self.f.profile,out)
        self.assertEqual(library.read_bytes(),self.f.library);self.assertEqual(build.read_bytes(),self.f.build)
        self.assertEqual(sorted(x.relative_to(out).as_posix() for x in out.rglob('*') if x.is_file()),['bundled_native.json','native/attenuation.so','native/build_receipt.json'])
        self.assertEqual(receipt['archive_reference'],self.f.profile['bundled_native']['archive_reference'])
    def test_archive_member_hash_and_duplicate_reject(self):
        for mode in ('archive','member','duplicate'):
            with self.subTest(mode=mode):
                p=copy.deepcopy(self.f.profile);out=self.root/mode;out.mkdir()
                archive=self.repo/'input.zip'
                if mode=='archive':p['bundled_native']['archive_reference']['sha256']='0'*64
                elif mode=='member':p['bundled_native']['library_sha256']='0'*64
                else:
                    with zipfile.ZipFile(archive,'a') as z:z.writestr('build/attenuation.so',self.f.library)
                    p['bundled_native']['archive_reference']['sha256']=M.sha(archive)
                with self.assertRaises(ValueError):R.extract_native(p,out)
    def test_platform_and_package_mismatch_reject(self):
        with patch.object(R.platform,'system',return_value='Darwin'):
            with self.assertRaisesRegex(ValueError,'Linux'):R.platform_check(self.f.profile)
        with self.assertRaisesRegex(ValueError,'requirements'):
            R.package_check(self.f.profile,{'essential':{'numpy':'wrong','scipy':'1.15.3'}})
    def test_invalid_author_record_does_not_launch_fresh_worker(self):
        args=['fit','--case-id',self.f.case,'--output',str(self.root/'failed'),'--wall-seconds','2520','--rss-mib','6144','--headroom-mib','2048','--execution-record',str(self.f.put('bad.json',{}))]
        with patch.object(R,'platform_check'),patch.object(R,'worker') as worker,patch.object(R.subprocess,'run') as launched:
            self.assertEqual(R.main(args),1);worker.assert_not_called();launched.assert_not_called()
        self.assertFalse(M.read(self.root/'failed/reader_result.json')['execution_passed'])
    def worker_fixture(self, *, late=False, mismatched_producer=False):
        output=self.root/'worker';output.mkdir()
        with patch.object(R,'platform_check'):
            request=R.plan(self.f.args(output),100.,['invented-real-entrypoint'])
        request['mode']='author_envelope'
        record=self.f.put('author.json',{'fixture':'only the deadline branch is under test'})
        request.update(execution_record=str(record),execution_record_sha256=M.sha(record))
        R.write(output/'reader_request.json',request)
        clock=[100.]
        grant=dict(reader_source_review=None,execution_producer=copy.deepcopy(request['execution_producer']),numerical_attempt_id='invented-attempt')
        if mismatched_producer:grant['execution_producer']['kind']='forged'
        slot=dict(wall_seconds=2520,scientific_seconds=2490,mode='untouched')
        runtime={'essential':{'numpy':'2.2.6','scipy':'1.15.3'}}
        def execute(*args):
            clock[0]=102. if late else 100.
            return dict(passed=True,scientific_passed=True,handled=True,disposition_valid=True,disposition='complete',status='terminal_disposition')
        with patch.object(R,'platform_check'),patch.object(R.time,'monotonic',side_effect=lambda:clock[0]), \
             patch.object(D,'verify_protocol'),patch.object(legacy,'verify_protocol'), \
             patch.object(legacy.frozen,'runtime_identity',return_value=runtime), \
             patch.object(D,'admission',return_value=(grant,slot,dt.datetime.now(dt.timezone.utc)+dt.timedelta(seconds=1))), \
             patch.object(R,'execute_case',side_effect=execute) as called:
            code=R.worker(request,output)
        return code,M.read(output/'result.json'),called.call_count
    def test_shortened_author_expiry_revokes_finalized_success(self):
        code,result,calls=self.worker_fixture(late=True)
        self.assertEqual(calls,1);self.assertEqual(code,1)
        self.assertTrue(result['finalization_deadline_exceeded']);self.assertFalse(result['scientific_passed'])
        self.assertNotIn('scientific_clock_cap_exceeded',result)
    def test_full_author_producer_object_checked_before_same_helper(self):
        code,result,calls=self.worker_fixture(mismatched_producer=True)
        self.assertEqual(code,1);self.assertEqual(calls,0)
        self.assertIn('producer differs',result['error'])
    def test_worker_keeps_exact_native_receipts_source_and_command(self):
        code,result,calls=self.worker_fixture()
        self.assertEqual(code,0);self.assertEqual(calls,1)
        self.assertEqual(result['actual_command'],['invented-real-entrypoint'])
        self.assertEqual(result['execution_mode'],'author_envelope')
        self.assertEqual(result['source_sha256'],result['execution_producer']['execution_source_sha256'])
        self.assertEqual(result['bundled_native']['library_sha256'],digest(self.f.library))


class WholeCaseControls(unittest.TestCase):
    def setUp(self):
        self.fixture=fixtures.fixtures.RecoveryControls();self.fixture.setUp();self.addCleanup(self.fixture.tearDown)
        self.root=self.fixture.root
    def execute(self, mode='fresh_local', technical=False, capped=False):
        current=fixtures.fixtures.RecoveryControls();current.setUp();self.addCleanup(current.tearDown)
        delegate,case,modules,_,_=current.startup_fixture()
        class Phase(fixtures.TinyPhase):
            _grids={k:dict(space_nodes=1,time_nodes=1,parents=1,estimate=1) for k in (8,16)}
            def evaluate(self,theta,model='null',order=8,require_gradient=True):
                if technical:raise ArithmeticError('invented unrelated error')
                score,g=super().evaluate(theta,'null',order,require_gradient)
                score['joint']=np.float64(score['joint']);score['nll']=np.float64(score['nll'])
                return score,g
        def factory(rows,gm,start,end,*args):
            phase=Phase();phase.a={'event_time':np.array([start+1])};return phase
        delegate.model.phase_from_rows=factory
        original_adapter=A.Adapter
        def adapter(*args,**kwargs):
            self.assertIsNone(kwargs['partial']);self.assertIsNone(kwargs['trace'])
            def optimizer(fn,x,**opts):
                value=fn(x);answer=fixtures.returned(x,value[0] if opts['jac'] else value)
                if capped:
                    answer.success=False;answer.status=1;answer.message='Invented original cap'
                    answer.nfev=current.science['solver']['powell']['maxfev'] if opts['method']=='Powell' else 1
                    answer.nit=1
                return answer
            return original_adapter(*args,**kwargs,optimizer=optimizer)
        output=self.root/mode;output.mkdir()
        request=dict(case_id=case['case_id'],mode=mode,execution_producer={'kind':'invented-reader'})
        profile=dict(numerical_version='fixture',amendment_protocol={'sha256':'amendment'},scientific_protocol={'sha256':'science'})
        with ExitStack() as stack:
            stack.enter_context(patch.object(A,'Adapter',side_effect=adapter))
            stack.enter_context(patch.object(legacy.frozen,'verify_inputs',return_value=[case]))
            stack.enter_context(patch.object(legacy.model,'archived',return_value=modules))
            stack.enter_context(patch.object(legacy.model,'Native',return_value=None))
            stack.enter_context(patch.object(legacy,'OrderedChunkScheduler',return_value=nullcontext()))
            stack.enter_context(patch.object(legacy,'runner_with_scheduler',return_value=delegate))
            stack.enter_context(patch.object(legacy,'verify_case'))
            result=R.execute_case(request,profile,output,Path('invented'),Path('invented'),{},time.monotonic(),time.monotonic()+60)
        return result,output
    def test_fresh_and_author_share_full_original_case_assembly(self):
        first,out1=self.execute();second,out2=self.execute('author_envelope')
        self.assertTrue(first['scientific_passed'],first);self.assertTrue(second['scientific_passed'],second)
        report1=M.read(out1/first['report_file']);report2=M.read(out2/second['report_file'])
        # Runtime timestamps differ, mathematical case/fit outputs do not.
        for name in ('fits','outcomes','new_null_test','training_checks','test_checks','floor_checks'):
            self.assertEqual(report1[name],report2[name])
        self.assertEqual(first['actual_optimizer_attempts'],32);self.assertEqual(first['reused_optimizer_attempts'],0)
        self.assertEqual(report1['execution_producer'],{'kind':'invented-reader'})
        self.assertEqual(M.read(out1/'reuse_map.json')['entries'],[])
        self.assertTrue(all(type(v['gate_active']) is bool for v in report1['outcomes']))
    def test_unrelated_error_retained_not_unknown_or_refinement(self):
        result,out=self.execute(technical=True)
        self.assertFalse(result['handled']);self.assertEqual(result['disposition'],'technical_failure')
        self.assertEqual(result['refinement_census'],dict(started=0,accepted=0,rejected=0))
        self.assertTrue((out/'execution_calls.jsonl').is_file())
    def test_finite_original_cap_remains_unknown_without_test_outputs(self):
        result,out=self.execute(capped=True)
        self.assertTrue(result['handled'],result);self.assertTrue(result['disposition_valid'])
        self.assertFalse(result['passed']);self.assertFalse(result['scientific_passed'])
        self.assertEqual(result['disposition'],'scientific_unknown')
        report=M.read(out/result['report_file']);self.assertEqual(report['outcomes'],[])
        self.assertNotIn('new_null_test',report)
        self.assertFalse(result['model_census']['held_out_phase_constructed'])
        self.assertEqual(result['actual_optimizer_attempts'],2)


if __name__=='__main__':unittest.main()
