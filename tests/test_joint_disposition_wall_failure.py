"""Invented mixed custody including one technical wall failure; no numerical calls."""
from copy import deepcopy
import json
from pathlib import Path
import tempfile
import unittest
import zipfile
from scripts import build_joint_disposition_report as B,render_joint_disposition_results as R
from tests.test_joint_disposition_reporting import data,write
from tests.test_joint_disposition_refined_cpu import ReaderEvidence
from tests import test_joint_disposition_findings as website_fixture
from website import build_findings as W


class WallEvidence(ReaderEvidence):
    case_id_overrides={(6,14):B.WALL_CASE}
    def __init__(self,root,mutation=None):
        super().__init__(root);self.wall(mutation)
    def wall(self,mutation):
        key=B.WALL_CASE;assert self.sequence[55]==key
        entry=next(e for e in self.registry['executions'] if e['execution_id']=='amended')
        with zipfile.ZipFile(self.repo/entry['archive']['path']) as z:files={n:z.read(n) for n in z.namelist()}
        wall_files={}
        for name in self.sequence[51:56]:
            source=self.index['records'][self.sequence.index(name)]['source'];source['execution_id']='wall-host04'
            prefix='host/'+str(Path(source['result_path']).parent).replace('\\','/')+'/'
            wall_files.update({n:raw for n,raw in files.items() if n.startswith(prefix)})
        source=deepcopy(self.index['records'][55]['source'])
        report=B.document(wall_files['host/'+source['case_path']]);result=B.document(wall_files['host/'+source['result_path']])
        report.update(passed=False,status='unknown',outcomes=[],error_type='TimeoutError',error='Joint experiment deadline',
            input_sha256={},stratum='invented',fixed_spatial_mark_law={})
        report['fits'].pop('LIplus_inclusive');report['training_checks'].pop('LIplus_inclusive')
        report['floor_checks']=[v for v in report['floor_checks'] if v['phase']=='train']
        result.update(passed=False,scientific_passed=False,handled=False,disposition_valid=False,disposition='technical_failure',
            error_type='ValueError',error='Case optimizer records differ from trace',scientific_clock_cap_exceeded=True,
            wall_seconds=2490.0270934919995,allocation={'scientific_seconds':2490,'wall_seconds':2520},
            phase_constructions=[dict(start=30,end=395,returned=True)])
        if mutation:mutation(report,result)
        supervisor=dict(status='failed',returncode=1,launched=True,stop_reason=None,cleanup_errors=[],survivors_after_cleanup=[],
            wall_seconds_including_cleanup=2490.5780963780003)
        wall_files['host/'+source['case_path']]=data(report);source['case_sha256']=B.digest(data(report));result['report_sha256']=source['case_sha256']
        wall_files['host/'+source['result_path']]=data(result);source['result_sha256']=B.digest(data(result))
        wall_files['host/'+source['supervision_path']]=data(supervisor);source['supervision_sha256']=B.digest(data(supervisor))
        census=dict(case_id=key,held_out_calls=0,new_outcomes_available=0,physical_optimizer_attempts=29,successful_optimizer_returns=27,
            optimizer_exception_attempts=2,completed_arms=list(B.ARMS[:3]),unfinished_arm='LIplus_inclusive',
            successful_trace_only_starts=[0,1,2],interrupted_start=3,not_run_starts=[4,5,6,7])
        raw=deepcopy(self.index);raw['records']=deepcopy(self.index['records'][:55]);raw['counts']=dict(processed_histories=55,complete_histories=54,unknown_histories=1,unattempted_histories=25,computed_outcomes=270)
        wall_files['host/index.json']=data(raw);self.raw_archive=self.zip('wall_host04.zip',wall_files)
        audit=dict(passed=False,audit_passed=True,scientific_completion=False,live_agent_review=True,live_agent_review_performed=True,
            final_batch_agent_review_required=False,review_kind='live_agent_saved_output_review',execution_id='wall-host04',
            checked_case_ids=self.sequence[51:56],artifact_sha256=self.raw_archive['sha256'],index_sha256=B.digest(data(raw)),source_sha256=self.new_sources,
            accepted_completed_prefix=dict(audit_passed=True,processed_histories=55,complete_histories=54,new_complete_cases=self.sequence[51:55]),failure=census)
        review_path=self.base+'wall_review.json';write(self.repo/review_path,audit);review_ref=dict(path=review_path,sha256=B.sha(self.repo/review_path))
        self.registry['executions'].append(dict(execution_id='wall-host04',archive=self.raw_archive,review=review_ref,member_prefix='host/'))
        directory=str(Path(B.OPERATIONAL).parent).replace('\\','/')
        sources=sorted([directory+'/'+n for n in ('__init__.py','host.py','transition.py','protocol.json')]+[
            'scripts/run_joint_wall_failure_continuation.py','.github/workflows/joint-wall-failure-continuation.yml',
            'tests/test_joint_wall_failure_continuation.py','tests/test_joint_wall_failure_launcher.py'])
        checker=['experiments/s04b_wall_failure_continuation_audit/__init__.py','experiments/s04b_wall_failure_continuation_audit/check.py',
            'experiments/s04b_exposure_refinement_audit/__init__.py','experiments/s04b_exposure_refinement_audit/check.py',
            'experiments/s04b_joint_remaining_audit/check.py','experiments/s04b_joint_audit/check.py',B.CORE]
        test='tests/test_joint_wall_failure_continuation_audit.py'
        for path in sources+checker+[test,'requirements.txt','requirements-cpu.txt']:
            target=self.repo/path
            if path!=B.OPERATIONAL and not target.exists():target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(b'# invented source never imported\n')
        f=dict(case_id=key,execution_id='wall-host04',failure_census=census)
        for kind in ('case','trace','result','supervision'):f.update({kind+'_member':'host/'+source[kind+'_path'],kind+'_sha256':source[kind+'_sha256']})
        self.op=dict(schema='joint_wall_failure_continuation_protocol_v1',version='wall_failure_continuation_v1',
            numerical_protocol=self.registry['numerical_amendment']['protocol'],scientific_protocol={'path':B.SCIENCE,'sha256':B.sha(self.repo/B.SCIENCE)},
            core_source_sha256=self.new_sources,full_sequence=self.sequence,case_ids=self.sequence[56:],original_native=self.native,
            base=dict(archive=self.raw_archive,review=review_ref,index_member='host/index.json',index_sha256=B.digest(data(raw))),failure=f,
            accounting={'failure_scientific_seconds':'2490.0270934919995','failure_outer_seconds':'2490.5780963780003'},
            producer_source_paths=sources,checker={'sources':checker,'test':test})
        write(self.repo/B.OPERATIONAL,self.op)
        host_sources=dict(self.new_sources,**{path:B.sha(self.repo/path) for path in sources})
        review_sources=dict(host_sources,**{path:B.sha(self.repo/path) for path in checker+[test,'requirements.txt','requirements-cpu.txt']})
        sr=self.base+'operational_source_review.json';write(self.repo/sr,dict(passed=True,live_agent_review=True,reviewed_files_sha256=review_sources))
        op_ref=dict(path=B.OPERATIONAL,sha256=B.sha(self.repo/B.OPERATIONAL))
        future_review=B.read(self.repo/entry['review']['path'])
        future_review.update(host_source_sha256=host_sources,operational_continuation=op_ref)
        write(self.repo/entry['review']['path'],future_review);entry['review']['sha256']=B.sha(self.repo/entry['review']['path'])
        row={k:deepcopy(report[k]) for k in ('case_id','regime','seed','input_sha256','n_train','n_test','stratum','thinning','fixed_spatial_mark_law','historical_comparisons')}
        row.update(disposition='wall_time_failure',scientific_passed=False,outcomes=[],source=source,reason_code='scientific_wall_limit',failure_review=review_ref,
            failure_census=census,primary_error={'type':report['error_type'],'message':report['error']},secondary_error={'type':result['error_type'],'message':result['error']},
            allocation=result['allocation'],numerical_amendment=result['numerical_amendment'])
        self.index['records'][55]=row
        self.index.update(schema='joint_exposure_refinement_operational_index_v1',operational_continuation=op_ref,host_source_sha256=host_sources,
            budget={'scope':'invented unchanged conservative index budget'},audited_host_overheads=[],
            counts=dict(processed_histories=80,complete_histories=78,unknown_histories=1,wall_time_failure_histories=1,unattempted_histories=0,computed_outcomes=390))
        self.index_review.update(execution_id='amended',resource={'whole_workflow_overhead_beyond_all_child_outer_seconds':'12.5','scope':'invented final known resource receipt'})
        self.sealed=deepcopy(self.index);self.sealed['records']=deepcopy(self.index['records'][:56])
        self.seal_path=self.base+'sealed_index.json';write(self.repo/self.seal_path,self.sealed)
        self.seal_review_path=self.base+'seal_review.json'
        self.seal_review=dict(passed=True,audit_passed=True,review_kind='live_operational_failure_transition_review',live_agent_review=True,live_agent_review_performed=True,
            final_batch_agent_review_required=False,failure_accounting_valid=True,scientific_execution_passed=False,scientific_completion=False,
            index_sha256=B.sha(self.repo/self.seal_path),operational_continuation=op_ref,raw_archive=self.raw_archive,raw_review=review_ref,raw_index_sha256=B.digest(data(raw)))
        write(self.repo/self.seal_review_path,self.seal_review)
        self.registry['operational_continuation']=dict(protocol=op_ref,source_review={'path':sr,'sha256':B.sha(self.repo/sr)},
            sealed_index={'path':self.seal_path,'sha256':B.sha(self.repo/self.seal_path)},sealing_review={'path':self.seal_review_path,'sha256':B.sha(self.repo/self.seal_review_path)})
        self.finish()
    def finish(self):
        write(self.repo/self.paths['index'],self.index);write(self.repo/self.paths['registry'],self.registry)
        self.index_review.update(index_sha256=B.sha(self.repo/self.paths['index']),counts=self.index['counts']);write(self.repo/self.paths['index_review'],self.index_review)


class WallReportingControls(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.root=Path(self.temp.name)
    def test_mixed_case_kinds_keep_all400_slots_and_failure_separate(self):
        f=WallEvidence(self.root);report,_=B.build(f.repo,f.paths)
        self.assertEqual(report['counts']['computed_outcomes'],390);self.assertEqual(report['counts']['unresolved_technical_failures'],1)
        self.assertEqual(len(report['unknown_census']),1);self.assertEqual(len(report['failure_census']),1);self.assertEqual(report['complete_regimes'],[4,7])
        rows=[r for r in report['outcomes'] if r['case_id']==B.WALL_CASE];self.assertEqual(len(rows),5)
        self.assertTrue(all(all(r[k] is None for k in B.NULL_FIELDS) for r in rows));self.assertTrue(all('historical_comparators' in r for r in rows))
        self.assertEqual(report['case_dispositions'][44]['computation']['reused_optimizer_attempts'],28)
        self.assertEqual(report['public_reader']['case_ids'],f.reader_ids);self.assertFalse(report['scientific_completion'])
        self.assertEqual(report['resource_evidence']['index_budget'],f.index['budget'])
        self.assertEqual(report['resource_evidence']['final_live_resource'],f.index_review['resource'])
        text,_=R.render(report,'validation/invented.json','0'*64);self.assertIn('technical wall failure',text);self.assertIn('Procedure & Unavailable',text)
    def test_final_resource_receipt_rejects_missing_or_double_counted_overhead(self):
        for key in ('missing','duplicate','nonfinite','boolean'):
            f=WallEvidence(self.root/key)
            if key=='missing':f.index_review.pop('resource')
            elif key=='duplicate':f.index['audited_host_overheads']=[{'execution_id':'amended','seconds':'12.5'}]
            else:f.index_review['resource']['whole_workflow_overhead_beyond_all_child_outer_seconds']='NaN' if key=='nonfinite' else True
            f.finish()
            with self.assertRaises(ValueError):B.build(f.repo,f.paths)

    def test_full_validator_requires_separate_reporting_task_acceptance(self):
        f=WallEvidence(self.root);report,_,_=f.accept();self.assertEqual(R.validate(f.repo,f.public)[0],report)
    def test_failure_never_becomes_unknown_zero_or_complete_even_with_new_final_pin(self):
        for disposition,passed,outcomes in [('scientific_unknown',False,[]),('complete',True,[]),('wall_time_failure',False,[{'new_gain':0}])]:
            f=WallEvidence(self.root/disposition);f.index['records'][55].update(disposition=disposition,scientific_passed=passed,outcomes=outcomes);f.finish()
            with self.assertRaises(ValueError):B.build(f.repo,f.paths)
    def test_repinned_raw_failure_flags_still_reject(self):
        for name,change in [('handled',lambda c,r:r.update(handled=True)),('finite_cap',lambda c,r:c.update(error_type='ArithmeticError')),
                            ('clock',lambda c,r:r.update(wall_seconds=2490.)),('heldout',lambda c,r:c.update(outcomes=[{'new_gain':0}]))]:
            f=WallEvidence(self.root/name,mutation=change)
            with self.assertRaises(ValueError):B.build(f.repo,f.paths)
    def test_operational_references_require_canonical_public_validation_paths(self):
        f=WallEvidence(self.root);original=deepcopy(f.registry['operational_continuation'])
        for key in ('source_review','sealed_index','sealing_review'):
            raw=(f.repo/original[key]['path']).read_bytes()
            for location in ('private/'+key+'.json','validation/authorities/'+key+'.json',
                             'validation/Authorities/'+key+'.json','validation/../private/'+key+'.json',
                             'validation//'+key+'.json','validation/./'+key+'.json'):
                with self.subTest(key=key,location=location):
                    target=f.repo/location;target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(raw)
                    f.registry['operational_continuation']=deepcopy(original)
                    f.registry['operational_continuation'][key]['path']=location;f.finish()
                    with self.assertRaises(ValueError):B.build(f.repo,f.paths)
        f.registry['operational_continuation']=original;f.finish()
        self.assertEqual(B.build(f.repo,f.paths)[0]['counts']['wall_time_failure_histories'],1)
        self.assertTrue(original['protocol']['path'].startswith('experiments/'))

    def test_transition_review_cannot_duplicate_failed_host_execution(self):
        f=WallEvidence(self.root);f.seal_review['execution_id']='wall-host04';write(f.repo/f.seal_review_path,f.seal_review)
        f.registry['operational_continuation']['sealing_review']['sha256']=B.sha(f.repo/f.seal_review_path);f.finish()
        with self.assertRaisesRegex(ValueError,'Separate live seal'):B.build(f.repo,f.paths)
    def test_missing_policy_or_wrong_actual_host_source_does_not_fall_back(self):
        f=WallEvidence(self.root/'missing');f.registry.pop('operational_continuation');f.finish()
        with self.assertRaises(ValueError):B.build(f.repo,f.paths)
        f=WallEvidence(self.root/'source');f.index['host_source_sha256']=f.new_sources;f.finish()
        with self.assertRaisesRegex(ValueError,'execution identity'):B.build(f.repo,f.paths)
    def test_future_host_cannot_disguise_its_operational_source_map(self):
        f=WallEvidence(self.root);entry=next(e for e in f.registry['executions'] if e['execution_id']=='amended')
        review=B.read(f.repo/entry['review']['path']);review['host_source_sha256']=f.new_sources
        write(f.repo/entry['review']['path'],review);entry['review']['sha256']=B.sha(f.repo/entry['review']['path']);f.finish()
        with self.assertRaisesRegex(ValueError,'actual operational source identity'):B.build(f.repo,f.paths)

    def test_final79_and_altered_original_prefix_are_rejected(self):
        f=WallEvidence(self.root/'79');f.index['records'].pop();f.finish()
        with self.assertRaisesRegex(ValueError,'Final compact'):B.build(f.repo,f.paths)
        f=WallEvidence(self.root/'prefix');f.index['records'][51]['n_train']+=1;f.finish()
        with self.assertRaisesRegex(ValueError,'accepted prefix'):B.build(f.repo,f.paths)
    def test_failure_from_unaccepted_host_cannot_use_normal_amended_path(self):
        f=WallEvidence(self.root);f.index['records'][55]['source']['execution_id']='amended';f.finish()
        with self.assertRaises(ValueError):B.build(f.repo,f.paths)
    def test_real_validator_to_browser_preserves_wall_failure_nulls_and_labels(self):
        f=WallEvidence(self.root/'real');f.public={k:W.DISPOSITION_DIRECTORY+'/'+v+'.json' for k,v in [('report','report'),('audit','independent_review'),('completion_review','completion_review')]}
        f.accept();study,_=W.load_joint_disposition_study(f.repo)
        helper=website_fixture.TestDispositionFindings();helper.setUp();self.addCleanup(helper.doCleanups)
        output,_=helper.render_fixture(study,'wall_view');result=json.loads(helper.node(output).stdout)
        self.assertEqual(result['disposition_selector_cases'],10);self.assertEqual(len(study['failure_census']),1)
        self.assertEqual(study['counts']['scientific_unknown_histories'],1);self.assertEqual(study['counts']['wall_time_failure_histories'],1)


if __name__=='__main__':unittest.main()
