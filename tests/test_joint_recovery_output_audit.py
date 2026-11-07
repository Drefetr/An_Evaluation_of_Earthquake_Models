"""Invented retained-output controls only: no evaluator, producer or optimizer import."""
from pathlib import Path
import copy
import json
import math
import tempfile
import unittest
from unittest.mock import patch
from experiments.s04b_joint_recovery_audit import check as c


def write(path,value):
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(value)+'\n',encoding='utf-8')


def score(nll=3.,exposure=2.):
    joint=-nll;point=joint+exposure
    return dict(P=point,E=exposure,C=-exposure,M=0.,joint=point-exposure,nll=-(point-exposure))


def compare(a,b):
    return dict(actual=copy.deepcopy(a),expected=copy.deepcopy(b),exact_match=a==b,differences=c.leaf_differences(a,b))


def score_record(a,b):
    return dict(passed=True,tolerance=1e-9,identities={k:dict(signed_exposure=True,joint=True,negative_joint=True,model_exposure=True) for k in ('actual','expected')},
                components=[dict(field=k,actual=a[k],expected=b[k],delta=a[k]-b[k],absolute_delta=abs(a[k]-b[k]),passed=True) for k in c.SCORE_KEYS])


def protocol():
    return dict(shared_bounds=[[-1.,1.]]*5,inhibition_bounds=[[-1.,1.]]*3,
                quadrature=dict(joint_absolute_tolerance=1e-4,selected_training_gradient_scaled_tolerance=1e-4))


def selected_record(model='LI',g=0.):
    dims=5 if model=='null' else 8
    value=dict(passed=True,parameters=[0.]*8,selection='original coarse selection',coarse=score(),fine=score(),
        projected_gradient_coarse=[g]*dims,projected_gradient_fine=[g]*dims,
        absolute_joint_delta=0.,projected_gradient_scaled_delta=0.,projected_kkt_infinity_norm=abs(g))
    raw=[dict(model=model,order=order,parameters=[0.]*8,score=score(),gradient=[g]*8) for order in (8,16)]
    return value,raw


def training_payload(actual,old,raw,model):
    result=compare(actual,old)
    result.update(passed=True,accepted_check_source='original_saved_check',score_comparisons={k:score_record(actual[k],old[k]) for k in ('coarse','fine')},
        actual_criteria=c.selected_criteria(actual,model,protocol(),raw),expected_criteria=c.selected_criteria(old,model,protocol()))
    return result


def original_return(start=0):
    return dict(start_index=start,method='L-BFGS-B',parameters=[0.]*8,returned_nll=3.,
                fresh_score=score(),gradient=[0.]*8,projected_gradient=[0.]*8)


def return_payload(old,start=0):
    expected=dict(parameters=old['parameters'],score=old['fresh_score'],gradient=old['gradient'],projected_gradient=old['projected_gradient'])
    return dict(token=dict(id='token-'+str(start),model='LIplus_immigrant',start_index=start,parameters=[0.]*8,order=8,require_gradient=True),
        actual_evaluation=copy.deepcopy(expected),expected_evaluation=copy.deepcopy(expected),score_comparison=score_record(expected['score'],expected['score']),
        gradient_differences=compare(expected['gradient'],expected['gradient']),actual_returned_nll_delta=0.,finite_gradients=True,saved_projection_exact=True,
        consumed_once=True,physical_optimizer_active=False,passed=True,canonical_return=dict(score=old['fresh_score'],gradient=old['gradient']),accepted_source='original_completed_return')


class OriginalContractSupport(unittest.TestCase):
    def test_original_tolerance_accepts_ulp_and_rejects_outside(self):
        old=score();actual=score(3.+5e-10)
        c.inspect_score_replay(actual,old)
        with self.assertRaisesRegex(c.AuditError,'original1e-9'):c.inspect_score_replay(score(3.+2e-9),old)

    def test_exact_tolerance_boundary(self):
        old=score(0.,0.);actual=score(1e-9,0.)
        c.inspect_score_replay(actual,old)
        with self.assertRaises(c.AuditError):c.inspect_score_replay(score(math.nextafter(1e-9,math.inf),0.),old)

    def test_inconsistent_tuple_not_rescued_by_small_error(self):
        old=score();actual=copy.deepcopy(old);actual['C']+=1e-15
        with self.assertRaisesRegex(c.AuditError,'identity'):c.inspect_score_replay(actual,old)

    def test_nonfinite_and_boolean_score_rejected(self):
        for value in (float('inf'),float('nan'),True):
            actual=score();actual['P']=value
            with self.subTest(value=value),self.assertRaises(c.AuditError):c.score_tuple(actual)

    def test_original_model_exposure_and_selected_fine_bound(self):
        value=score(3.,-5e-10);c.score_tuple(value)
        selected,raw=selected_record();selected['fine']=value;raw[1]['score']=value
        selected['absolute_joint_delta']=abs(selected['coarse']['joint']-value['joint'])
        with self.assertRaisesRegex(c.AuditError,'scientific'):c.selected_criteria(selected,'LI',protocol(),raw)

    def test_unused_gradient_difference_has_no_cross_run_bound(self):
        old,unused=selected_record();fresh,raw=selected_record(g=10.)
        record=training_payload(fresh,old,raw,'LI')
        c.inspect_training_equivalence(record,old,'LI',raw,protocol())

    def test_changed_selected_parameter_rejected(self):
        old,raw=selected_record();record=training_payload(old,old,raw,'LI')
        record['actual']['parameters'][0]=.1;record['differences']=c.leaf_differences(record['actual'],old);record['exact_match']=False
        with self.assertRaisesRegex(c.AuditError,'identity'):c.inspect_training_equivalence(record,old,'LI',raw,protocol())

    def test_derived_selected_diagnostic_is_not_trusted(self):
        old,raw=selected_record();fresh=copy.deepcopy(old);fresh['projected_kkt_infinity_norm']=1.
        with self.assertRaisesRegex(c.AuditError,'independently derived'):c.selected_criteria(fresh,'LI',protocol(),raw)

    def test_fresh_projection_required(self):
        value,raw=selected_record();raw[1]['gradient'][0]=.1
        with self.assertRaisesRegex(c.AuditError,'projection'):c.selected_criteria(value,'LI',protocol(),raw)

    def test_original_scientific_gradient_check_cannot_be_relaxed(self):
        value,raw=selected_record();value['projected_gradient_fine'][0]=.1;raw[1]['gradient'][0]=.1
        value['projected_gradient_scaled_delta']=value['projected_kkt_infinity_norm']=.1
        with self.assertRaisesRegex(c.AuditError,'scientific'):c.selected_criteria(value,'LI',protocol(),raw)

    def test_replayed_return_preserves_original_candidate_before_near_tie(self):
        old=original_return();record=return_payload(old);actual=score(3.+5e-10)
        record['actual_evaluation']['score']=actual;record['score_comparison']=score_record(actual,old['fresh_score']);record['actual_returned_nll_delta']=abs(actual['nll']-3.)
        token=c.inspect_replayed_support(record,old,[[-1.,1.]]*8,0)
        candidate=dict(state_index=1,kind='optimizer',start_index=0,parameters=old['parameters'],score=old['fresh_score'],gradient=old['gradient'])
        result=dict(passed=True,actual=candidate,expected=candidate,exact_match=True,differences=[],source_support_token_id=token,accepted_candidate_source='original_completed_return_before_selection')
        canonical=c.inspect_replayed_candidate(result,old,0,token)
        competitor=dict(score=score(3.+2.5e-10))
        self.assertIs(min([canonical,competitor],key=lambda x:x['score']['nll']),canonical)
        result['actual']=copy.deepcopy(candidate);result['actual']['score']=actual
        with self.assertRaisesRegex(c.AuditError,'before selection'):c.inspect_replayed_candidate(result,old,0,token)

    def test_token_context_and_state_not_relaxed(self):
        for field,value in [('physical_optimizer_active',True),('consumed_once',False)]:
            old=original_return();record=return_payload(old);record[field]=value
            with self.subTest(field=field),self.assertRaises(c.AuditError):c.inspect_replayed_support(record,old,[[-1.,1.]]*8,0)
        old=original_return();record=return_payload(old);record['token']['parameters'][0]=.1
        with self.assertRaisesRegex(c.AuditError,'state'):c.inspect_replayed_support(record,old,[[-1.,1.]]*8,0)

    def test_new_optimizer_cannot_claim_a_replay_token(self):
        old=original_return();record=return_payload(old);record['token']['start_index']=6
        with self.assertRaisesRegex(c.AuditError,'identity'):c.inspect_replayed_support(record,old,[[-1.,1.]]*8,0)

    def test_replayed_gradient_is_finite_and_projected(self):
        old=original_return();record=return_payload(old);record['actual_evaluation']['gradient'][1]=float('nan')
        with self.assertRaises(c.AuditError):c.inspect_replayed_support(record,old,[[-1.,1.]]*8,0)
        record=return_payload(old);record['actual_evaluation']['gradient'][1]=.1
        with self.assertRaisesRegex(c.AuditError,'projection'):c.inspect_replayed_support(record,old,[[-1.,1.]]*8,0)

    def test_gradient_diagnostic_difference_census_checked(self):
        old=original_return();record=return_payload(old)
        record['actual_evaluation']['gradient'][1]=record['actual_evaluation']['projected_gradient'][1]=1.
        with self.assertRaisesRegex(c.AuditError,'gradient diagnostic'):c.inspect_replayed_support(record,old,[[-1.,1.]]*8,0)


class ScopeChecks(unittest.TestCase):
    def test_automated_pilot_review_is_not_live(self):
        v=dict(passed=True,index_sha256='index',review_kind='automated_saved_output_check',live_agent_review=False,
               live_agent_review_performed=False,final_batch_agent_review_required=True,checker_sources_sha256={},checker_source_review_sha256='review')
        with self.assertRaisesRegex(c.AuditError,'pilot'):c.validate_review(v,'index',{},'review',pilot=True)
        c.validate_review(v,'index',{},'review')

    def test_missing_live_attribution_rejected(self):
        with self.assertRaisesRegex(c.AuditError,'live review'):c.validate_review(dict(passed=True,index_sha256='index',reviewer='/root/continuation_cpu'),'index',{},'review',pilot=True)

    def test_prefix_attempt_cannot_disappear(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaisesRegex(c.AuditError,'charged-attempt prefix'):
                c.preserved_prefix(dict(cases=[{}],attempts=[dict(attempt_id='new')],reviews=[{}]),dict(cases=[],attempts=[dict(attempt_id='failed')],reviews=[]),Path(tmp),Path(tmp))

    def test_eval_counters_balance(self):
        with self.assertRaisesRegex(c.AuditError,'balance'):c.counters({'train|LI|8|support|True':dict(attempted=3,returned=1,errors=1)})

    def test_failed_checker_receipt_is_automated(self):
        with tempfile.TemporaryDirectory() as tmp:
            output=Path(tmp)/'failed.json';argv=[]
            for key in ('repo','current','prior','prior-review','config','commit','checker-source-review','checker-source-review-sha256'):argv.extend(['--'+key,'invented'])
            argv.extend(['--output',str(output)])
            with patch.object(c,'audit_saved',side_effect=c.AuditError('injected')):self.assertEqual(c.main(argv),1)
            result=c.read(output);self.assertFalse(result['passed']);self.assertFalse(result['live_agent_review']);self.assertTrue(result['final_batch_agent_review_required'])
            with self.assertRaises(FileExistsError):c.main(argv)


class StartupFailureAccounting(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name);lineage=self.root/'recovery_lineage';lineage.mkdir()
        (lineage/'startup_failure.zip').write_bytes(b'invented retained archive')
        (lineage/'startup_failure_workflow.log').write_text('invented log\n')
        startup=dict(status='failed_before_scientific_evaluation',charge_seconds=90,
                     scientific_predecessor_unchanged=True,nested_scientific_seconds=.5,nested_supervised_seconds=1.5,
                     archive_sha256=c.sha(lineage/'startup_failure.zip'),workflow_log_sha256=c.sha(lineage/'startup_failure_workflow.log'))
        review=dict(passed=False,audit_passed=True,live_agent_review=True,reviewer='/root/continuation_cpu',
                    overall_scientific_passed=False,archive_sha256=startup['archive_sha256'],
                    execution_census=dict(new_completed_cases=0,new_full_likelihood_evaluations=0,
                                          new_optimizer_invocations=0,new_optimizer_trace_records=0))
        write(lineage/'startup_failure_review.json',review)
        startup['review_sha256']=c.sha(lineage/'startup_failure_review.json')
        resource=dict(passed=True,failure=dict(passed=False,archive_sha256=startup['archive_sha256'],failed_attempt_id='startup-failed'),
                      amendment=dict(explicit_new_charge_bound_seconds=90,shared_allowance_seconds=115200,automatic_retry=False),
                      independent_failure_audit=dict(sha256=startup['review_sha256']),
                      inputs_sha256={'joint_recovery_host_01_workflow.log':startup['workflow_log_sha256']},
                      observed_timing=dict(child_scientific_seconds=.5,outer_supervised_seconds=1.5,timings_nested=True))
        write(lineage/'startup_failure_resource.json',resource)
        startup['resource_review_sha256']=c.sha(lineage/'startup_failure_resource.json')
        self.policy=dict(pre_execution_failure=startup,predecessor=dict(known_outer_overhead_seconds=3.),
                         operational_failures=[startup],operational_diagnostics=[],
                         operational_lineage_files={startup['archive_sha256']:c.STARTUP_FILES})
        self.index=dict(pre_execution_failure=copy.deepcopy(startup),recovery_transition=dict(pre_execution_failure=copy.deepcopy(startup)),
                        attempts=[dict(attempt_id='original-interruption')],
                        operational_accounting=dict(scientific_indexed_seconds=100.,known_prior_outer_overhead_seconds=3.,
                                                    operational_failure_charge_seconds=90,operational_diagnostic_charge_seconds=0,accounted_seconds=193.))

    def audit(self):
        c.inspect_startup_failure(self.index,self.root,self.policy)
        return c.inspect_operational_accounting(self.index,self.policy,100.)

    def test_separate_charge_preserves_scientific_sum(self):
        result=self.audit()
        self.assertEqual(result['scientific_indexed_seconds'],100.)
        self.assertEqual(result['accounted_seconds'],193.)

    def test_omitted_or_doubled_charge_rejected(self):
        for value in (0,420):
            with self.subTest(value=value):
                self.index['operational_accounting']['operational_failure_charge_seconds']=value
                self.index['operational_accounting']['accounted_seconds']=183.+value
                with self.assertRaisesRegex(c.core.AuditError,'Operational accounting'):self.audit()

    def test_nested_child_cannot_be_another_scientific_attempt(self):
        self.index['attempts'].append(dict(attempt_id='startup-failed'))
        with self.assertRaisesRegex(c.AuditError,'charged again'):self.audit()

    def test_nested_duration_cannot_be_added_to_scientific_sum(self):
        self.index['operational_accounting']['scientific_indexed_seconds']+=.5
        self.index['operational_accounting']['accounted_seconds']+=.5
        with self.assertRaisesRegex(c.core.AuditError,'scientific_indexed'):self.audit()

    def test_retained_failed_archive_cannot_change(self):
        (self.root/'recovery_lineage/startup_failure.zip').write_bytes(b'replaced')
        with self.assertRaisesRegex(c.AuditError,'evidence bytes'):self.audit()

    def test_failed_startup_cannot_be_relabelled(self):
        self.policy['pre_execution_failure']['status']='passed'
        with self.assertRaisesRegex(c.AuditError,'status'):self.audit()

    def test_transition_cannot_omit_charge_record(self):
        self.index['recovery_transition']['pre_execution_failure'].pop('charge_seconds')
        with self.assertRaisesRegex(c.AuditError,'Transition startup'):self.audit()

    def test_repinned_claim_of_calls_rejected(self):
        path=self.root/'recovery_lineage/startup_failure_review.json'
        review=c.read(path);review['execution_census']['new_optimizer_invocations']=1;write(path,review)
        for obj in (self.policy['pre_execution_failure'],self.index['pre_execution_failure'],self.index['recovery_transition']['pre_execution_failure']):
            obj['review_sha256']=c.sha(path)
        with self.assertRaisesRegex(c.AuditError,'zero-call'):self.audit()




class OrderedOperationalEvidence(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name);lineage=self.root/'recovery_lineage';lineage.mkdir()
        first=dict(archive_sha256='earlier',charge_seconds=90,scientific_predecessor_unchanged=True,nested_scientific_seconds=.5,nested_supervised_seconds=1.)
        mapping={'earlier':c.STARTUP_FILES};objects=[]
        names3={key:'third_'+name for key,name in c.SUPPORT_FILES.items()}
        for names,charge,diagnostic,support_count in ((c.SUPPORT_FILES,120,False,5),(names3,80,False,8),(c.DIAGNOSTIC_FILES,80,True,5)):
            (lineage/names['archive']).write_bytes((str(charge)+str(diagnostic)+str(support_count)).encode())
            (lineage/names['workflow_log']).write_text('invented workflow '+names['workflow_log'])
            row=dict(charge_seconds=charge,scientific_predecessor_unchanged=True,nested_scientific_seconds=1.,nested_supervised_seconds=2.,
                     archive_sha256=c.sha(lineage/names['archive']),workflow_log_sha256=c.sha(lineage/names['workflow_log']),support_evaluation_count=support_count,optimizer_call_count=0)
            review=dict(archive_sha256=row['archive_sha256'],audit_passed=True,live_agent_review=True,reviewer='/root/continuation_cpu')
            resource=dict(passed=True,timing=dict(conservative_whole_launch_charge_seconds=charge,child_scientific_seconds=1.,outer_including_cleanup_seconds=2.,nested_intervals_not_additive=True),input_sha256={'log':row['workflow_log_sha256']})
            if diagnostic:
                row.update(status='diagnostic_complete',passed=True,equality_passed=False,scientific_completion=False,held_out_call_count=0)
                review.update(passed=True,diagnostic_complete=True,equality_passed=False,accepted_recovery_case=False,scientific_completion=False,
                              execution=dict(actual_training_evaluations=5,optimizer_calls=0,held_out_calls=0,new_complete_cases=0))
            else:
                row.update(status='failed_during_training_support')
                review.update(passed=False,overall_scientific_passed=False,accepted_completed_prefix={'count':40},execution_census=dict(new_training_support_evaluations=support_count,new_optimizer_invocations=0))
                if support_count==8:
                    row.update(replayed_optimizer_return_count=2,physical_optimizer_call_count=0,held_out_call_count=0)
                    review['execution_census'].update(replayed_immigrant_optimizer_returns=2,new_test_evaluations=0)
            write(lineage/names['review'],review);row['review_sha256']=c.sha(lineage/names['review'])
            if diagnostic:resource['diagnostic']=dict(archive_sha256=row['archive_sha256'],independent_review_sha256=row['review_sha256'])
            else:resource.update(failure=dict(passed=False,status=row['status'],archive_sha256=row['archive_sha256'],failed_attempt_id='failed-'+str(support_count),
                         **{k:v for k,v in row.items() if k.endswith('_count')}),independent_failure_audit=dict(sha256=row['review_sha256']))
            write(lineage/names['resource_review'],resource);row['resource_review_sha256']=c.sha(lineage/names['resource_review'])
            objects.append(row);mapping[row['archive_sha256']]=names
        self.policy=dict(pre_execution_failure=first,operational_failures=[first,*objects[:2]],operational_diagnostics=[objects[2]],
                         operational_lineage_files=mapping,predecessor=dict(known_outer_overhead_seconds=3.))
        self.index=dict(operational_failures=copy.deepcopy(self.policy['operational_failures']),operational_diagnostics=copy.deepcopy(self.policy['operational_diagnostics']),
            recovery_transition=copy.deepcopy(self.policy),attempts=[dict(attempt_id='original-science')],
            operational_accounting=dict(scientific_indexed_seconds=100.,known_prior_outer_overhead_seconds=3.,operational_failure_charge_seconds=290.,operational_diagnostic_charge_seconds=80.,accounted_seconds=473.))

    def test_three_failures_plus_diagnostic_charged_once(self):
        c.inspect_operational_lists(self.index,self.root,self.policy)
        self.assertEqual(c.inspect_operational_accounting(self.index,self.policy,100.)['accounted_seconds'],473.)

    def test_diagnostic_cannot_be_relabelled_as_scientific_success(self):
        self.policy['operational_diagnostics'][0]['scientific_completion']=True
        self.index['operational_diagnostics']=copy.deepcopy(self.policy['operational_diagnostics']);self.index['recovery_transition']['operational_diagnostics']=copy.deepcopy(self.policy['operational_diagnostics'])
        with self.assertRaisesRegex(c.AuditError,'Diagnostic accounting'):c.inspect_operational_lists(self.index,self.root,self.policy)

    def test_missing_or_extra_destination_rejected(self):
        key=self.policy['operational_failures'][2]['archive_sha256'];self.policy['operational_lineage_files'].pop(key)
        with self.assertRaisesRegex(c.AuditError,'mapping'):c.operational_rows(self.policy)

    def test_duplicate_archives_rejected(self):
        self.policy['operational_failures'].append(copy.deepcopy(self.policy['operational_failures'][1]))
        with self.assertRaisesRegex(c.AuditError,'Duplicate'):c.operational_rows(self.policy)

    def test_unsafe_or_aliased_names_rejected(self):
        key=self.policy['operational_failures'][2]['archive_sha256']
        for name in ('../x','x/','./x','a\\b','startup_failure.zip'):
            self.policy['operational_lineage_files'][key]['archive']=name
            with self.subTest(name=name),self.assertRaises(c.AuditError):c.operational_rows(self.policy)

    def test_failed_child_nested_duration_not_recharged(self):
        self.index['attempts'].append(dict(attempt_id='failed-8'))
        with self.assertRaisesRegex(c.AuditError,'charged again'):c.inspect_operational_lists(self.index,self.root,self.policy)

    def test_retained_diagnostic_archive_hashed(self):
        (self.root/'recovery_lineage'/c.DIAGNOSTIC_FILES['archive']).write_bytes(b'changed')
        with self.assertRaisesRegex(c.AuditError,'evidence bytes'):c.inspect_operational_lists(self.index,self.root,self.policy)

    def test_omitted_third_launch_charge_rejected(self):
        self.index['operational_accounting']['operational_failure_charge_seconds']=210.
        self.index['operational_accounting']['accounted_seconds']=393.
        with self.assertRaisesRegex(c.core.AuditError,'Operational accounting'):c.inspect_operational_accounting(self.index,self.policy,100.)


class FloorAndReferenceChecks(unittest.TestCase):
    def floors(self):
        old=[dict(phase='train',model=model,expected_nll=3.,actual_nll=3.,absolute_delta=0.,tolerance=1e-9) for model in ('LI','LIplus_immigrant','LIplus_inclusive')]
        fresh=copy.deepcopy(old)
        for row in fresh:row.update(actual_nll=3.+5e-10,absolute_delta=abs(3.+5e-10-3.))
        record=dict(passed=True,actual=fresh,expected=old,rows=[dict(passed=True,actual_nll_difference=a['actual_nll']-b['actual_nll']) for a,b in zip(fresh,old)])
        return record,dict(floor_checks=old),dict(floor_checks=fresh)

    def test_floor_fresh_values_retained_at_original_tolerance(self):
        record,old,fresh=self.floors();c.inspect_floor_replay(record,old,fresh)
        self.assertNotEqual(fresh,old)

    def test_floor_no_posthoc_overwrite(self):
        record,old,fresh=self.floors()
        with self.assertRaisesRegex(c.AuditError,'retained'):c.inspect_floor_replay(record,old,old)

    def test_floor_expected_metadata_cannot_change(self):
        record,old,fresh=self.floors();record['actual'][0]['expected_nll']+=1e-10
        with self.assertRaisesRegex(c.AuditError,'identity'):c.inspect_floor_replay(record,old,fresh)

    def test_powell_success_before_reference_count_is_valid(self):
        c.inspect_reference_snapshots({'return':{'observed':False},'next_input':{'observed':False}},[],
            dict(last_evaluation=dict(evaluation_count=2040,parameters=[0.]*8,score=score(),gradient=[0.]*8),failed_evaluation_parameters=[0.]*8),17)

    def test_powell_different_trajectory_is_descriptive(self):
        old=dict(last_evaluation=dict(evaluation_count=2040,parameters=[0.]*8,score=score(),gradient=None),failed_evaluation_parameters=[0.]*8)
        a=dict(parameters=[.5]*8,score=score(9.),gradient=[2.]*8)
        expected={k:v for k,v in old['last_evaluation'].items() if k!='evaluation_count'}
        snapshots={'return':dict(observed=True,reference_count=2040,scope='observational_only',**compare(a,expected)),
                   'next_input':dict(observed=True,reference_count=2041,scope='observational_only',**compare([.8]*8,old['failed_evaluation_parameters']))}
        ledger=[dict(event='restart_return_reference',**snapshots['return']),dict(event='restart_next_input_reference',**snapshots['next_input'])]
        c.inspect_reference_snapshots(snapshots,ledger,old,2041)
        snapshots['return']['differences']=[]
        with self.assertRaisesRegex(c.AuditError,'ledger'):c.inspect_reference_snapshots(snapshots,ledger,old,2041)

    def test_reference_cannot_claim_absence_after_reached(self):
        old=dict(last_evaluation=dict(evaluation_count=2040,parameters=[0.]*8,score=score(),gradient=None),failed_evaluation_parameters=[0.]*8)
        with self.assertRaisesRegex(c.AuditError,'count'):c.inspect_reference_snapshots({'return':{'observed':False},'next_input':{'observed':False}},[],old,2041)



def execution_fixture(root,powell_count=17):
    arm='LIplus_immigrant';original=dict(passed=False,wall_seconds=12.,fits={'null':{'old':1},'LI':{'old':2}},training_checks={})
    rawchecks={};checks={}
    for name in ('null','LI'):
        old,raw=selected_record(name);original['training_checks'][name]=old
        rawchecks[name]=raw;checks[name]=training_payload(old,old,raw,name)
    original['floor_checks']=[dict(phase='train',model=m,expected_nll=3.,actual_nll=3.,absolute_delta=0.,tolerance=1e-9) for m in ('LI',arm,'LIplus_inclusive')]
    trace=[];ends={}
    for name in ('null','LI',arm):
        for i in range(6 if name==arm else 8):
            r=dict(start_index=i,method='L-BFGS-B',initial_parameters=[0.]*8,status='returned',success=True,nfev=2,nit=1)
            if name==arm:r.update(original_return(i))
            if name==arm and i==5:r.update(status='exception',success=False,error_type='ArithmeticError',error='original arithmetic failure')
            ends[name,i,'L-BFGS-B']=r
            trace.extend([dict(event='attempt_start',model=name,**r),dict(event='attempt_end',model=name,**r)])
    interrupted=dict(start_index=5,method='Powell',initial_parameters=[0.]*8,status='exception',success=False,error_type='TimeoutError',
        last_evaluation=dict(evaluation_count=2040,parameters=[.2]*8,score=score(4.),gradient=None),failed_evaluation_parameters=[.3]*8)
    trace.extend([dict(event='attempt_start',model=arm,**interrupted),dict(event='attempt_end',model=arm,**interrupted)])
    ends[arm,5,'Powell']=interrupted
    report=copy.deepcopy(original);report.update(prior_training_attempt_seconds=12.,current_attempt_wall_seconds=4.,wall_seconds=16.,
        recovery_provenance=dict(exact_internal_optimizer_resume=False,original_partial_sha256='partial',original_trace_sha256='trace'))
    oldrecords=[copy.deepcopy(ends[arm,i,'L-BFGS-B']) for i in range(6)]
    new=[dict(start_index=5,method='Powell',initial_parameters=[0.]*8,status='returned',success=True,nfev=powell_count)]
    new.extend(dict(start_index=i,method='L-BFGS-B',initial_parameters=[0.]*8,status='returned',success=True,nfev=2) for i in (6,7))
    total=[dict(start_index=i,method='L-BFGS-B',initial_parameters=[0.]*8,status='returned',success=True,nfev=2) for i in range(8)]
    candidates=[dict(state_index=i+1,kind='optimizer',start_index=i,parameters=r['parameters'],score=r['fresh_score'],gradient=r['gradient']) for i,r in enumerate(oldrecords[:5])]
    report['fits'].update({arm:dict(records=oldrecords+new,candidates=copy.deepcopy(candidates),selected=copy.deepcopy(candidates[0])),
                          'LIplus_inclusive':dict(records=total)})
    policy=dict(predecessor=dict(case_sha256='partial',trace_sha256='trace'),recovery=dict(original_powell_options=dict(maxiter=400,maxfev=5000,ftol=1e-10,xtol=1e-6)))
    logical=[(m,r['start_index'],r['method']) for m in (arm,'LIplus_inclusive') for r in report['fits'][m]['records']]
    actual=[key for key in logical if not(key[0]==arm and(key[1]<5 or key[1:]==(5,'L-BFGS-B')))]
    counts={'train|LIplus_immigrant|8|restarted_interrupted_invocation|False':dict(attempted=powell_count,returned=powell_count),
            'train|LIplus_immigrant|8|new_optimizer_invocation|True':dict(attempted=4,returned=4),
            'train|LIplus_inclusive|8|new_optimizer_invocation|True':dict(attempted=16,returned=16)}
    floor_record=dict(passed=True,actual=copy.deepcopy(original['floor_checks']),expected=copy.deepcopy(original['floor_checks']),
                      rows=[dict(passed=True,actual_nll_difference=0.) for i in range(3)])
    ledger=[dict(event='lineage',original_failed_physical_attempts=23,interrupted=interrupted),dict(event='historical_floor_replay',**floor_record)]
    for name in ('null','LI'):
        ledger.append(dict(event='reused_complete_arm',model=name,optimizer_calls=0))
        ledger.extend(dict(event='selected_support_evaluation',check_name=name,**r) for r in rawchecks[name])
        ledger.append(dict(event='repeated_training_check',model=name,**checks[name]))
    supports={};candidate_rows={}
    for i in range(5):
        support=return_payload(ends[arm,i,'L-BFGS-B'],i);supports[str(i)]=support;token=support['token']
        ledger.extend([dict(event='token_created',token=token),dict(event='replayed_optimizer_return',model=arm,start_index=i,method='L-BFGS-B',actual_objective_calls=0,historical_nfev=2,historical_nit=1),
            dict(event='completed_return_support',**support),dict(event='token_consumed',token=token,canonical_return=support['canonical_return'],before_candidate_construction=True),
            dict(event='canonical_completed_record',model=arm,start_index=i,**compare(ends[arm,i,'L-BFGS-B'],ends[arm,i,'L-BFGS-B']))])
        candidate_rows[str(i)]=dict(passed=True,actual=candidates[i],expected=candidates[i],exact_match=True,differences=[],source_support_token_id=token['id'],accepted_candidate_source='original_completed_return_before_selection')
    ledger.append(dict(event='replayed_primary_error',actual_objective_calls=0,original_record=ends[arm,5,'L-BFGS-B']))
    snapshots={'return':{'observed':False},'next_input':{'observed':False}}
    for name,i,method in actual:
        restart=(name,i,method)==(arm,5,'Powell');kind='restarted_interrupted_invocation' if restart else 'new_optimizer_invocation'
        ledger.append(dict(event='physical_optimizer_start',model=name,start_index=i,method=method,kind=kind,initial_parameters=[0.]*8,options=policy['recovery']['original_powell_options'] if restart else {}))
        if restart:
            for key,event,threshold,expected in [('return','restart_return_reference',2040,{k:v for k,v in interrupted['last_evaluation'].items() if k!='evaluation_count'}),('next_input','restart_next_input_reference',2041,interrupted['failed_evaluation_parameters'])]:
                if powell_count>=threshold:
                    snapshot=dict(observed=True,reference_count=threshold,scope='observational_only',**compare(expected,expected));snapshots[key]=snapshot;ledger.append(dict(event=event,**snapshot))
        ledger.append(dict(event='physical_optimizer_end',model=name,start_index=i,method=method,kind=kind,returned=True,completed_objective_returns=powell_count if restart else 2,actual_evaluations=counts))
    for i in range(5):ledger.append(dict(event='replayed_candidate_preserved',model=arm,start_index=i,**candidate_rows[str(i)]))
    execution=dict(schema='joint_partial_optimizer_recovery_calls_v2',exact_internal_optimizer_resume=False,original_physical_attempts_retained=23,
        arm_calls=['null','LI',arm,'LIplus_inclusive'],reused_complete_arms=['null','LI'],replayed_successful_starts=list(range(5)),
        original_interrupted_powell=interrupted,original_primary_error=ends[arm,5,'L-BFGS-B'],logical_optimizer_calls=logical,actual_evaluations=counts,
        repeated_training_checks=checks,selected_check_evaluations=rawchecks,historical_floor_replay=floor_record,replayed_start_support=supports,
        replayed_candidates=candidate_rows,reference_snapshots=snapshots,pending_return=None)
    write(root/'recovery_lineage/failed_case.json',original)
    (root/'recovery_lineage/failed_trace.jsonl').write_text(''.join(json.dumps(v)+'\n' for v in trace))
    write(root/'recovery_execution.json',execution)
    (root/'recovery_calls.jsonl').write_text(''.join(json.dumps(v)+'\n' for v in ledger))
    return report,policy,copy.deepcopy(ledger),copy.deepcopy(execution)


class WholeRecoveryLedger(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.root=Path(self.temp.name)
        self.report,self.policy,self.ledger,self.execution=execution_fixture(self.root)

    def save(self):
        write(self.root/'recovery_execution.json',self.execution)
        (self.root/'recovery_calls.jsonl').write_text(''.join(json.dumps(v)+'\n' for v in self.ledger))

    def audit(self):
        self.save();return c.inspect_recovery_execution(self.root,self.report,self.policy,protocol())

    def test_complete_logical_recovery_keeps_interrupted_physical_work(self):
        result=self.audit();self.assertEqual(result['new_physical_optimizer_invocations'],11)
        self.assertTrue(result['original_timeout_retained']);self.assertFalse(result['exact_internal_optimizer_resume'])

    def test_original_successful_start_cannot_change(self):
        self.report['fits']['LIplus_immigrant']['records'][0]['nfev']=3
        with self.assertRaisesRegex(c.AuditError,'Replayed return'):self.audit()

    def test_replayed_token_cannot_be_consumed_twice(self):
        row=next(x for x in self.ledger if x['event']=='token_consumed');i=self.ledger.index(row);self.ledger.insert(i+1,copy.deepcopy(row))
        with self.assertRaisesRegex(c.AuditError,'Token consumed'):self.audit()

    def test_support_cannot_occur_inside_real_optimizer(self):
        start=next(x for x in self.ledger if x['event']=='physical_optimizer_start')
        self.ledger.insert(1,copy.deepcopy(start))
        with self.assertRaisesRegex(c.AuditError,'Overlapping replay token'):self.audit()

    def test_canonicalization_must_precede_candidate(self):
        next(x for x in self.ledger if x['event']=='token_consumed')['before_candidate_construction']=False
        with self.assertRaisesRegex(c.AuditError,'after candidate'):self.audit()

    def test_no_hidden_completed_optimizer_reexecution(self):
        self.ledger.extend(copy.deepcopy(self.ledger[-7:-5]))
        with self.assertRaises(c.AuditError):self.audit()

    def test_restart_initial_not_last_iterate(self):
        next(x for x in self.ledger if x['event']=='physical_optimizer_start')['initial_parameters']=[.2]*8
        with self.assertRaisesRegex(c.AuditError,'initial point'):self.audit()

    def test_restart_original_budget_not_extended(self):
        next(x for x in self.ledger if x['event']=='physical_optimizer_start')['options']={'maxfev':7040}
        with self.assertRaisesRegex(c.AuditError,'budget'):self.audit()

    def test_reference_missing_if_reached_rejected(self):
        self.report,self.policy,self.ledger,self.execution=execution_fixture(self.root,2041)
        self.execution['reference_snapshots']['next_input']={'observed':False}
        with self.assertRaisesRegex(c.AuditError,'observation count'):self.audit()

    def test_reused_check_not_replaced_with_fresh_gradient(self):
        self.report['training_checks']['LI']['projected_gradient_fine'][0]=.1
        with self.assertRaisesRegex(c.AuditError,'training check'):self.audit()


if __name__=='__main__':unittest.main()
