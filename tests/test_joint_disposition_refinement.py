"""Invented old/amended custody chain; no real report, likelihood or fit."""
from copy import deepcopy
import json
from pathlib import Path
import tempfile
import unittest
import zipfile
from scripts import build_joint_disposition_report as B, render_joint_disposition_results as R
from tests.test_joint_disposition_reporting import InventedDispositionEvidence, data, write


class AmendedEvidence(InventedDispositionEvidence):
    def __init__(self,root,extra_unknown=False,mutation=None,refinement=False,refinement_mutation=None):
        super().__init__(root,extra_unknown)
        self.new_sources={'amended_fixture.py':'4'*64}
        self.mutation=mutation
        self.refinement=refinement;self.refinement_mutation=refinement_mutation
        self.amend()
    def host_case(self,key,execution,report,amendment=None,extra=None):
        old=self.index['records'][self.sequence.index(key)]
        source=deepcopy(old['source']);prefix='children/'+key+'/science/'
        source.update(execution_id=execution,case_path=prefix+'case.json',trace_path=prefix+'trace.jsonl',result_path=prefix+'result.json',supervision_path=prefix+'supervision.json')
        raw=data(report);trace=b''.join(json.dumps(v).encode()+b'\n' for v in self.traces[key])
        source.update(case_sha256=B.digest(raw),trace_sha256=B.digest(trace))
        result=dict(schema='joint_remaining_case_result_v1',handled=True,disposition_valid=True,status='terminal_disposition',
            case_id=key,disposition=old['disposition'],scientific_passed=report['passed'],passed=report['passed'],
            report_sha256=source['case_sha256'],trace_sha256=source['trace_sha256'],protocol_sha256=B.sha(self.repo/B.POLICY),
            immutable_failure_reference=self.policy['immutable_failure_reference'],runtime={'essential':self.native['runtime_essential']},
            library_sha256=self.native['library_sha256'],build_receipt_sha256=self.native['build_receipt_sha256'],source_sha256=self.sources)
        if not report['passed']:
            result.update(unknown_outcome_count=5,terminal_solver_return=self.terminal,
                phase_constructions=[dict(start=30,end=395,returned=True)],model_census=old['model_census'],unknown_reason=old['unknown_reason'])
        if amendment:result.update(amendment)
        supervision=dict(status='passed',returncode=0,launched=True,stop_reason=None,cleanup_errors=[],survivors_after_cleanup=[])
        source.update(result_sha256=B.digest(data(result)),supervision_sha256=B.digest(data(supervision)))
        record=dict(B.projection(report),disposition=old['disposition'],scientific_passed=report['passed'],outcomes=deepcopy(report['outcomes']),source=source)
        if not report['passed']:
            record.update({k:deepcopy(old[k]) for k in ('unknown_origin','model_census','terminal_solver_return','unknown_reason')})
        if amendment:record.update(numerical_amendment=amendment['numerical_amendment'],refinement_census=amendment['refinement_census'])
        contents={'host/'+source['case_path']:raw,'host/'+source['trace_path']:trace,'host/'+source['result_path']:data(result),'host/'+source['supervision_path']:data(supervision)}
        for name,value in (extra or {}).items():contents['host/'+prefix+name]=value
        return record,contents
    def review_host(self,execution,archive,ids,failed=False):
        review=dict(passed=not failed,audit_passed=True,scientific_completion=False,live_agent_review=True,live_agent_review_performed=True,
            final_batch_agent_review_required=False,review_kind='live_agent_saved_output_review',artifact_sha256=archive['sha256'],execution_id=execution,
            checked_case_ids=ids,source_sha256=self.sources if execution in ('old-pilot','old-failed') else self.new_sources)
        if failed:
            review.update(accepted_completed_prefix=True,accepted_completed_case_ids=self.sequence[42:44],index_sha256=self.base_index_sha)
        relative=self.base+execution+'_review.json';write(self.repo/relative,review)
        return dict(execution_id=execution,archive=archive,member_prefix='host/',review=dict(path=relative,sha256=B.sha(self.repo/relative)))
    def amend(self):
        executions=[];records=deepcopy(self.index['records'][:41])
        record,files=self.host_case(self.sequence[41],'old-pilot',self.reports[self.sequence[41]])
        records.append(record);executions.append(self.review_host('old-pilot',self.zip('old_pilot.zip',files),self.sequence[41:42]))
        failed_files={}
        for key in self.sequence[42:44]:
            record,files=self.host_case(key,'old-failed',self.reports[key]);records.append(record);failed_files.update(files)
        partial_id=self.sequence[44]
        # Eight declared logical starts per complete fit; no optimizer is executed.
        for key in self.sequence[44:]:
            report=self.reports[key]
            if report['passed']:
                for arm in B.ARMS:
                    report['fits'][arm].update(records=[dict(success=True,start_index=i,method='L-BFGS-B') for i in range(8)],
                        candidates=[dict(state_index=i,fixture=arm) for i in range(9)])
                report['training_checks']={arm:dict(passed=True,fixture=arm) for arm in B.ARMS}
            else:
                for arm,fit in report['fits'].items():
                    if fit['passed']:fit['records']=[dict(success=True,start_index=i,method='L-BFGS-B') for i in range(8)]
        partial=deepcopy(self.reports[partial_id]);partial.update(passed=False,status='unknown_starts',outcomes=[])
        partial['floor_checks']=[r for r in partial['floor_checks'] if r['phase']=='train']
        partial['training_checks'].pop('LIplus_inclusive')
        total=partial['fits']['LIplus_inclusive'];total.update(passed=False,status='unknown_starts',records=total['records'][:4]+[
            dict(success=False,start_index=4,method=m,error_type='ArithmeticError',error='Nonfinite or negative full exposure') for m in ('L-BFGS-B','Powell')],candidates=total['candidates'][:5])
        partial_member='host/children/failed/science/case.json';failed_files[partial_member]=data(partial)
        base_index=dict(self.index,records=deepcopy(records),counts=dict(processed_histories=44,complete_histories=43,unknown_histories=1,unattempted_histories=36,computed_outcomes=215))
        failed_files['host/index.json']=data(base_index);self.base_index_sha=B.digest(data(base_index))
        failed_archive=self.zip('old_failed.zip',failed_files)
        failed_entry=self.review_host('old-failed',failed_archive,self.sequence[42:45],True);executions.append(failed_entry)
        base=dict(archive=failed_archive['path'],archive_sha256=failed_archive['sha256'],review=failed_entry['review']['path'],review_sha256=failed_entry['review']['sha256'],
            index_member='host/index.json',index_sha256=self.base_index_sha,records=44,complete_histories=43,unknown_histories=1)
        checker=['experiments/s04b_exposure_refinement_audit/check.py','experiments/s04b_exposure_refinement_audit/__init__.py',
                 'experiments/s04b_joint_remaining_audit/check.py','experiments/s04b_joint_audit/check.py',B.CORE]
        protocol=dict(schema='joint_exposure_refinement_protocol_v1',version='joint_exposure_refinement_v1',source_sha256={},checker={'sources':checker},
            original_scientific_protocol_sha256=B.sha(self.repo/B.SCIENCE),full_sequence=self.sequence,case_ids=self.sequence[44:],partial_case_id=partial_id,
            original_native=self.native,permanent_unknown=self.policy['immutable_failure_reference'],base=base,
            failed_case=dict(archive=failed_archive,review=failed_entry['review'],case_member=partial_member,case_sha256=B.digest(data(partial))))
        write(self.repo/B.AMENDMENT,protocol)
        sources={}
        for name in ['__init__.py','adapter.py','partial_fit.py','case_driver.py','host.py']:
            path=str(Path(B.AMENDMENT).parent/name).replace('\\','/');target=self.repo/path;target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(b'# invented source, never imported\n');sources[path]=B.sha(target)
        sources[B.AMENDMENT]=B.sha(self.repo/B.AMENDMENT)
        self.new_sources=deepcopy(sources)
        for path in checker:
            target=self.repo/path;target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(b'# invented reviewed checker, never imported\n');sources[path]=B.sha(target)
        review_path=self.base+'amendment_source_review.json';write(self.repo/review_path,dict(passed=True,live_agent_review=True,reviewed_files_sha256=sources))
        new_files={}
        for key in self.sequence[44:]:
            report=self.reports[key];is_partial=key==partial_id
            entries=[]
            if is_partial:
                entries=[dict(kind='historical_training_floor',pointer='/fits/null/candidates/0/score')]
                for arm in B.ARMS[:3]:entries.extend([dict(kind='complete_arm',model=arm,pointer='/fits/'+arm),dict(kind='selected_training_check',model=arm,pointer='/training_checks/'+arm)])
                entries.append(dict(kind='total_prefix',model='LIplus_inclusive',candidate_indices=list(range(5)),record_indices=list(range(4)),prior_failed_record_indices=[4,5]))
            reuse=dict(schema='joint_exposure_refinement_reuse_v1',mode='partial' if is_partial else 'untouched',entries=entries,
                original_failure_reference=protocol['failed_case'] if is_partial else None,reused_optimizer_attempts=28 if is_partial else 0,prior_failed_total_start4_attempts_retained=2 if is_partial else 0)
            calls=[]
            for entry in entries:
                event={'historical_training_floor':'reuse_historical_training_floor','complete_arm':'reuse_arm','selected_training_check':'reuse_selected_training_check','total_prefix':'reuse_total_prefix'}[entry['kind']]
                row=dict(event=event,**({'model':entry['model']} if 'model' in entry else {}))
                row['physical_optimizer_calls' if entry['kind'] in ('complete_arm','total_prefix') else 'physical_evaluations']=0;calls.append(row)
            physical=[]
            for arm in B.ARMS:
                for row in report['fits'].get(arm,{}).get('records',[]):
                    if is_partial and (arm!='LIplus_inclusive' or row['start_index']<4):continue
                    physical.append([arm,row['start_index'],row['method']]);context=dict(model=arm,start_index=row['start_index'],method=row['method'])
                    calls.extend([dict(event='optimizer_start',**context),dict(event='optimizer_end',**context)])
            if self.mutation:self.mutation(key,report,reuse,calls)
            refinements=[];evaluations={};census=dict(started=0,accepted=0,rejected=0)
            if is_partial and self.refinement:
                context=dict(phase='train',model='LIplus_inclusive',start_index=4,method='L-BFGS-B',callback_index=1,theta=[0.]*8)
                coarse=dict(P=0.,E=-1e-8,C=1e-8,M=0.,joint=1e-8,nll=-1e-8)
                fine=dict(P=0.,E=1e-8,C=-1e-8,M=0.,joint=-1e-8,nll=1e-8)
                refinements=[dict(event='refinement_start',event_id=1,context=context,theta=[0.]*8,coarse_seconds=.1,coarse=dict(score=coarse,gradient=[0.]*8)),
                    dict(event='refinement_end',event_id=1,context=context,theta=[0.]*8,coarse_seconds=.1,fine_seconds=.2,accepted=True,effective_order=16,
                         fine=dict(score=fine,gradient=[0.]*8),comparison=dict(passed=True,finite=True))]
                evaluations={'train|LIplus_inclusive|8|optimizer|True':dict(attempted=1,errors=1),
                             'train|LIplus_inclusive|16|refinement_fine|True':dict(attempted=1,returned=1)}
                census=dict(started=1,accepted=1,rejected=0)
                if self.refinement_mutation:self.refinement_mutation(refinements)
            raw_calls=b''.join(data(v).replace(b'\n',b' ')+b'\n' for v in calls)
            raw_refinements=b''.join(data(v).replace(b'\n',b' ')+b'\n' for v in refinements)
            extra={'reuse_map.json':data(reuse),'execution_calls.jsonl':raw_calls,'refinement_events.jsonl':raw_refinements}
            meta=dict(version=protocol['version'],protocol_sha256=B.sha(self.repo/B.AMENDMENT),original_scientific_protocol_sha256=B.sha(self.repo/B.SCIENCE),
                computation_kind='amended_partial_resume' if is_partial else 'amended_untouched',original_failure_reference=reuse['original_failure_reference'],
                reuse_map_sha256=B.digest(extra['reuse_map.json']),execution_calls_sha256=B.digest(raw_calls),refinement_event_log_sha256=B.digest(raw_refinements))
            report['numerical_amendment']=meta
            result=dict(schema='joint_exposure_refinement_case_v1',source_sha256=self.new_sources,protocol_sha256=B.sha(self.repo/B.AMENDMENT),numerical_amendment=meta,
                actual_optimizer_attempts=len(physical),reused_optimizer_attempts=reuse['reused_optimizer_attempts'],evaluation_census=evaluations,refinement_census=census,
                adapter=dict(reuse_entries=entries,physical_optimizer_calls=physical,evaluation_census=evaluations,refinement_started=census['started'],refinement_accepted=census['accepted'],refinement_rejected=census['rejected'],callback_active=False,refinement_active=False))
            record,files=self.host_case(key,'amended',report,result,extra);records.append(record);new_files.update(files)
        new_archive=self.zip('amended.zip',new_files);executions.append(self.review_host('amended',new_archive,self.sequence[44:]))
        self.registry.update(executions=executions,numerical_amendment=dict(protocol=dict(path=B.AMENDMENT,sha256=B.sha(self.repo/B.AMENDMENT)),source_review=dict(path=review_path,sha256=B.sha(self.repo/review_path))))
        self.index.update(schema='joint_exposure_refinement_index_v1',protocol_sha256=B.sha(self.repo/B.AMENDMENT),scientific_source_sha256=self.new_sources,host_source_sha256=self.new_sources,
            numerical_amendment_version=protocol['version'],original_scientific_protocol_sha256=B.sha(self.repo/B.SCIENCE),compatible_saved_prefix=base,
            original_exposure_failure_reference=protocol['failed_case'],records=records)
        write(self.repo/self.paths['index'],self.index);write(self.repo/self.paths['registry'],self.registry)
        self.index_review['index_sha256']=B.sha(self.repo/self.paths['index']);write(self.repo/self.paths['index_review'],self.index_review)


class RefinedReportingControls(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.root=Path(self.temp.name)
    def fixture(self,**kwargs):return AmendedEvidence(self.root,**kwargs)
    def test_exact_old_sources_partial_reuse_and_unavailable_statistics(self):
        f=self.fixture();report,pins=B.build(f.repo,f.paths)
        self.assertEqual(report['counts']['accepted_terminal_dispositions'],80);self.assertEqual(report['counts']['computed_outcomes'],395)
        self.assertEqual(len(report['outcomes']),400);self.assertFalse(report['scientific_completion'])
        self.assertEqual([r['computation']['kind'] for r in report['case_dispositions'][:44]],['retained_original']*44)
        partial=report['case_dispositions'][44]['computation'];self.assertEqual(partial['reused_optimizer_attempts'],28);self.assertEqual(partial['actual_optimizer_attempts'],4)
        self.assertEqual(partial['prior_failed_total_start4_attempts_retained'],2)
        self.assertEqual(report['complete_regimes'],[4,6,7]);self.assertTrue(all(r['full_regime'] is None for r in report['regime_summary'] if r['regime']==5))
        self.assertIn(B.AMENDMENT,pins);self.assertIn('experiments/s04b_exposure_refinement_audit/check.py',pins)
        text,_=R.render(report,'validation/invented.json','0'*64);self.assertIn('reused evidence',text)
    def test_genuine_separate_validator_rebuilds_extended_report(self):
        f=self.fixture();report,_,_=f.accept();rebuilt,_=R.validate(f.repo,f.public)
        self.assertEqual(report,rebuilt);self.assertFalse(rebuilt['original_publication_gate_satisfied'])
    def test_mutated_original_prefix_rejected_even_with_new_final_review_hash(self):
        f=self.fixture();f.index['records'][42]['n_train']+=1;write(f.repo/f.paths['index'],f.index)
        f.index_review['index_sha256']=B.sha(f.repo/f.paths['index']);write(f.repo/f.paths['index_review'],f.index_review)
        with self.assertRaisesRegex(ValueError,'prefix changed'):B.build(f.repo,f.paths)
    def test_omitted_amendment_never_falls_back_to_original_gate(self):
        f=self.fixture();f.registry.pop('numerical_amendment');write(f.repo/f.paths['registry'],f.registry)
        with self.assertRaises(ValueError):B.build(f.repo,f.paths)
    def test_reuse_event_claiming_physical_work_is_not_silently_zero(self):
        def mutation(key,report,reuse,calls):
            if reuse['mode']=='partial':next(r for r in calls if r['event']=='reuse_arm')['physical_optimizer_calls']=1
        f=self.fixture(mutation=mutation)
        with self.assertRaisesRegex(ValueError,'claims physical'):B.build(f.repo,f.paths)
    def test_changed_reuse_pointer_rejected_after_repinning(self):
        def mutation(key,report,reuse,calls):
            if reuse['mode']=='partial':reuse['entries'][0]['pointer']='/fits/null/selected/score'
        f=self.fixture(mutation=mutation)
        with self.assertRaisesRegex(ValueError,'pointer roster'):B.build(f.repo,f.paths)
    def test_contradictory_source_review_live_flag_rejected(self):
        f=self.fixture();ref=f.registry['numerical_amendment']['source_review'];value=B.read(f.repo/ref['path']);value['live_agent_review_performed']=False
        write(f.repo/ref['path'],value);ref['sha256']=B.sha(f.repo/ref['path']);write(f.repo/f.paths['registry'],f.registry)
        with self.assertRaisesRegex(ValueError,'live amendment source'):B.build(f.repo,f.paths)
    def test_checker_source_change_rejected_before_saved_aggregation(self):
        f=self.fixture();(f.repo/'experiments/s04b_exposure_refinement_audit/check.py').write_bytes(b'changed')
        with self.assertRaisesRegex(ValueError,'dependency changed'):B.build(f.repo,f.paths)
    def test_additional_scientific_unknown_stays_unavailable(self):
        f=self.fixture(extra_unknown=True);report,_=B.build(f.repo,f.paths)
        self.assertEqual(report['counts']['unavailable_outcomes'],10);self.assertEqual(report['complete_regimes'],[4,6])
        self.assertEqual(report['case_dispositions'][-1]['computation']['reused_optimizer_attempts'],0)
    def test_old_execution_cannot_borrow_final_amended_source_map(self):
        f=self.fixture();entry=f.registry['executions'][0];review=B.read(f.repo/entry['review']['path']);review['source_sha256']=f.new_sources
        write(f.repo/entry['review']['path'],review);entry['review']['sha256']=B.sha(f.repo/entry['review']['path']);write(f.repo/f.paths['registry'],f.registry)
        with self.assertRaisesRegex(ValueError,'Per-execution reviewed source'):B.build(f.repo,f.paths)
    def test_failed_old_case_cannot_use_accepted_completed_prefix(self):
        f=self.fixture();record=f.index['records'][44];record['source']['execution_id']='old-failed';write(f.repo/f.paths['index'],f.index)
        f.index_review['index_sha256']=B.sha(f.repo/f.paths['index']);write(f.repo/f.paths['index_review'],f.index_review)
        with self.assertRaisesRegex(ValueError,'only its independently accepted complete'):B.build(f.repo,f.paths)
    def test_final_source_map_must_equal_reviewed_driver_graph(self):
        f=self.fixture();f.index['scientific_source_sha256']=f.index['host_source_sha256']={'unreviewed.py':'4'*64}
        write(f.repo/f.paths['index'],f.index);f.index_review['index_sha256']=B.sha(f.repo/f.paths['index']);write(f.repo/f.paths['index_review'],f.index_review)
        with self.assertRaisesRegex(ValueError,'explicit amendment'):B.build(f.repo,f.paths)
    def test_nonempty_paired_refinement_is_preserved(self):
        f=self.fixture(refinement=True);report,_=B.build(f.repo,f.paths)
        self.assertEqual(report['case_dispositions'][44]['computation']['refinement_census'],dict(started=1,accepted=1,rejected=0))
    def test_unpaired_refinement_cannot_disappear_into_summary(self):
        f=self.fixture(refinement=True,refinement_mutation=lambda rows:rows.pop())
        with self.assertRaisesRegex(ValueError,'Unpaired'):B.build(f.repo,f.paths)
    def test_rejected_refinement_cannot_be_labelled_accepted(self):
        f=self.fixture(refinement=True,refinement_mutation=lambda rows:rows[-1]['comparison'].update(passed=False))
        with self.assertRaisesRegex(ValueError,'Rejected/nonfinite'):B.build(f.repo,f.paths)


if __name__=='__main__':unittest.main()
