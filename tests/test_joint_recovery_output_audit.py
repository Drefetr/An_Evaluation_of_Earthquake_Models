"""Invented saved-output controls; no scientific evaluator or optimizer import."""
from pathlib import Path
import copy
import json
import math
import sys
import tempfile
import unittest
from unittest.mock import patch

from experiments.s04b_joint_recovery_audit import check as c


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value)+'\n', encoding='utf-8')


def fixture(root):
    arm='LIplus_immigrant'
    li_support,li_original=support_record()
    null_original={'passed':True,'value':1.}
    original=dict(passed=False,wall_seconds=12.,fits={'null':{'old':1},'LI':{'old':2}},
                  training_checks={'null':null_original,'LI':li_original})
    trace=[]; ends={}
    for name in ('null','LI',arm):
        for i in range(8 if name!=arm else 6):
            record=dict(start_index=i,method='L-BFGS-B',initial_parameters=[float(i)],
                        status='returned',success=True,nfev=2,nit=1)
            if name==arm:
                record.update(parameters=[0.]*8,fresh_score={'nll':3.},gradient=[0.]*8,projected_gradient=[0.]*8)
            if name==arm and i==5:
                record.update(status='exception',success=False,error_type='ArithmeticError',error='Finite objective has unrepresentable gradient')
            ends[name,i,'L-BFGS-B']=record
            trace.extend([dict(event='attempt_start',model=name,**record),dict(event='attempt_end',model=name,**record)])
    timeout=dict(start_index=5,method='Powell',initial_parameters=[5.],status='exception',success=False,
                 error_type='TimeoutError',last_evaluation=dict(evaluation_count=2040,parameters=[2.],score={'nll':3.},gradient=[4.]*8),
                 failed_evaluation_parameters=[6.])
    ends[arm,5,'Powell']=timeout
    trace.extend([dict(event='attempt_start',model=arm,**timeout),dict(event='attempt_end',model=arm,**timeout)])
    recordlist=[copy.deepcopy(ends[arm,i,'L-BFGS-B']) for i in range(6)]
    recordlist += [dict(start_index=5,method='Powell',initial_parameters=[5.],status='returned',success=True,nfev=2041)]
    recordlist += [dict(start_index=i,method='L-BFGS-B',initial_parameters=[float(i)],status='returned',success=True,nfev=2) for i in (6,7)]
    total=[dict(start_index=i,method='L-BFGS-B',initial_parameters=[float(i)],status='returned',success=True,nfev=2) for i in range(8)]
    report=copy.deepcopy(original)
    report.update(prior_training_attempt_seconds=12.,current_attempt_wall_seconds=4.,wall_seconds=16.)
    report['fits'].update({arm:dict(records=recordlist),'LIplus_inclusive':dict(records=total)})
    candidate_list=[dict(state_index=i+1,kind='optimizer',start_index=i,parameters=r['parameters'],score=r['fresh_score'],gradient=r['gradient']) for i,r in enumerate(recordlist[:5])]
    report['fits'][arm].update(candidates=copy.deepcopy(candidate_list),selected=copy.deepcopy(candidate_list[0]))
    report['recovery_provenance']=dict(exact_internal_optimizer_resume=False,original_partial_sha256='partial',original_trace_sha256='trace')
    policy=dict(predecessor=dict(case_sha256='partial',trace_sha256='trace'),
                recovery=dict(original_powell_options=dict(maxiter=400,maxfev=5000,ftol=1e-10,xtol=1e-6)))
    logical=[(name,r['start_index'],r['method']) for name in (arm,'LIplus_inclusive') for r in report['fits'][name]['records']]
    expected=[key for key in logical if not(key[0]==arm and(key[1]<5 or key[1:]==(5,'L-BFGS-B')))]
    counts={'train|LIplus_immigrant|8|restarted_interrupted_invocation|False':dict(attempted=2041,returned=2041),
            'train|LIplus_immigrant|8|new_optimizer_invocation|True':dict(attempted=4,returned=4),
            'train|LIplus_inclusive|8|new_optimizer_invocation|True':dict(attempted=16,returned=16)}
    ledger=[dict(event='lineage',original_failed_physical_attempts=23,interrupted=timeout)]
    ledger += [dict(event='reused_complete_arm',model=n,optimizer_calls=0) for n in ('null','LI')]
    null_support=dict(actual=null_original,expected=null_original,exact_match=True,differences=[],
                      operational_equivalence=dict(passed=True,policy='exact_saved_training_check'),accepted_check_source='original_saved_check')
    training_support={'null':null_support,'LI':li_support}
    ledger += [dict(event='repeated_training_check',model=n,**copy.deepcopy(v)) for n,v in training_support.items()]
    replayed_support={};replayed_candidates={}
    for i in range(5):
        r=ends[arm,i,'L-BFGS-B'];candidate=candidate_list[i]
        support=dict(actual=r,expected=r,exact_match=True,differences=[],accepted_record_source='original_saved_record',
                     operational_equivalence=dict(passed=True,policy='replayed_completed_start_support_gradient_only_v1',non_gradient_fields_exact=True,
                        raw_gradient_comparison=gradient_record(r['gradient'],r['gradient']),projected_gradient_comparison=gradient_record(r['projected_gradient'],r['projected_gradient']),
                        actual_projection_exact=True,expected_projection_exact=True))
        cp=dict(actual=candidate,expected=candidate,exact_match=True,differences=[],accepted_candidate_gradient_source='original_saved_record.gradient',
                operational_equivalence=dict(passed=True,non_gradient_fields_exact=True,gradient_comparison=gradient_record(candidate['gradient'],candidate['gradient'])))
        replayed_support[str(i)]=copy.deepcopy(support);replayed_candidates[str(i)]=copy.deepcopy(cp)
        ledger.append(dict(event='replayed_completed_start_support',model=arm,start_index=i,**copy.deepcopy(support)))
        ledger.append(dict(event='replayed_candidate_preserved',model=arm,start_index=i,**copy.deepcopy(cp)))
    ledger += [dict(event='replayed_optimizer_return',model=arm,start_index=i,method='L-BFGS-B',actual_objective_calls=0,historical_nfev=2,historical_nit=1) for i in range(5)]
    ledger += [dict(event='replayed_primary_error',actual_objective_calls=0,original_record=ends[arm,5,'L-BFGS-B'])]
    for name,i,method in expected:
        restart=(name,i,method)==(arm,5,'Powell')
        kind='restarted_interrupted_invocation' if restart else 'new_optimizer_invocation'
        ledger.append(dict(event='physical_optimizer_start',model=name,start_index=i,method=method,kind=kind,
                           initial_parameters=[float(i)],options=policy['recovery']['original_powell_options'] if restart else {}))
        if restart:
            anchor={k:v for k,v in timeout['last_evaluation'].items() if k!='evaluation_count'}
            eq=dict(passed=True,policy='unused_Powell_anchor_gradient_only_v1',objective_parameters_and_scores_exact=True,
                    gradient_comparison=gradient_record(anchor['gradient'],anchor['gradient']))
            ledger.append(dict(event='restart_return_anchor_comparison',evaluation_count=2040,
                               actual=copy.deepcopy(anchor),expected=copy.deepcopy(anchor),exact_match=True,differences=[],operational_equivalence=copy.deepcopy(eq)))
            ledger.append(dict(event='restart_return_anchor_verified',evaluation_count=2040,
                               actual_evaluation=copy.deepcopy(anchor),expected_evaluation=copy.deepcopy(anchor),exact_match=True,operational_equivalence=copy.deepcopy(eq)))
            ledger.append(dict(event='restart_next_input_anchor_verified',evaluation_number=2041,parameters=[6.]))
        ledger.append(dict(event='physical_optimizer_end',model=name,start_index=i,method=method,kind=kind,
                           returned=True,completed_objective_returns=2041 if restart else 2,actual_evaluations=counts))
    execution=dict(schema='joint_partial_optimizer_recovery_calls_v1',exact_internal_optimizer_resume=False,
                   original_physical_attempts_retained=23,arm_calls=['null','LI',arm,'LIplus_inclusive'],
                   reused_complete_arms=['null','LI'],replayed_successful_starts=list(range(5)),
                   original_interrupted_powell=timeout,original_primary_error=ends[arm,5,'L-BFGS-B'],
                   anchor_return_verified=True,anchor_next_input_verified=True,logical_optimizer_calls=logical,
                   actual_evaluations=counts)
    execution.update(repeated_training_checks=copy.deepcopy(training_support),replayed_start_support=replayed_support,replayed_candidates=replayed_candidates)
    write(root/'recovery_lineage/failed_case.json',original)
    (root/'recovery_lineage/failed_trace.jsonl').write_text(''.join(json.dumps(v)+'\n' for v in trace))
    write(root/'recovery_execution.json',execution)
    (root/'recovery_calls.jsonl').write_text(''.join(json.dumps(v)+'\n' for v in ledger))
    return copy.deepcopy(report),copy.deepcopy(policy),json.loads(json.dumps(ledger)),copy.deepcopy(execution)


class RecoveryOutputAudit(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name)
        self.report,self.policy,self.ledger,self.execution=fixture(self.root)

    def audit(self):return c.inspect_recovery_execution(self.root,self.report,self.policy,
                {'shared_bounds':[[-1.,1.]]*5,'inhibition_bounds':[[-1.,1.]]*3})

    def ledger_change(self,mutate):
        mutate(self.ledger)
        (self.root/'recovery_calls.jsonl').write_text(''.join(json.dumps(v)+'\n' for v in self.ledger))

    def test_logical_success_keeps_physical_timeout(self):
        r=self.audit()
        self.assertEqual(r['original_physical_attempts'],23)
        self.assertEqual(r['new_physical_optimizer_invocations'],11)
        self.assertTrue(r['original_timeout_retained'])
        self.assertFalse(r['exact_internal_optimizer_resume'])

    def test_all_three_nonbitwise_support_scopes_keep_original_fit_records(self):
        before=copy.deepcopy(self.report)
        start=self.execution['replayed_start_support']['0']
        start['actual']=copy.deepcopy(start['actual'])
        start['actual']['gradient'][2]=start['actual']['projected_gradient'][2]=32*sys.float_info.epsilon
        start['exact_match']=False;start['differences']=c.leaf_differences(start['actual'],start['expected'])
        eq=start['operational_equivalence']
        eq['raw_gradient_comparison']=gradient_record(start['actual']['gradient'],start['expected']['gradient'])
        eq['projected_gradient_comparison']=gradient_record(start['actual']['projected_gradient'],start['expected']['projected_gradient'])
        candidate=self.execution['replayed_candidates']['0']
        candidate['actual']=copy.deepcopy(candidate['actual'])
        candidate['actual']['gradient']=copy.deepcopy(start['actual']['gradient'])
        candidate['exact_match']=False;candidate['differences']=c.leaf_differences(candidate['actual'],candidate['expected'])
        candidate['operational_equivalence']['gradient_comparison']=gradient_record(candidate['actual']['gradient'],candidate['expected']['gradient'])
        for event,payload in [('replayed_completed_start_support',start),('replayed_candidate_preserved',candidate)]:
            next(v for v in self.ledger if v['event']==event and v['start_index']==0).update(copy.deepcopy(payload))
        anchor=next(v for v in self.ledger if v['event']=='restart_return_anchor_comparison')
        anchor['actual']['gradient'][2]+=32*sys.float_info.epsilon
        anchor['exact_match']=False;anchor['differences']=c.leaf_differences(anchor['actual'],anchor['expected'])
        anchor['operational_equivalence']['gradient_comparison']=gradient_record(anchor['actual']['gradient'],anchor['expected']['gradient'])
        verified=next(v for v in self.ledger if v['event']=='restart_return_anchor_verified')
        verified.update(actual_evaluation=copy.deepcopy(anchor['actual']),exact_match=False,operational_equivalence=copy.deepcopy(anchor['operational_equivalence']))
        write(self.root/'recovery_execution.json',self.execution)
        self.ledger_change(lambda rows:None)
        result=self.audit()
        self.assertEqual(result['new_physical_optimizer_invocations'],11)
        self.assertEqual(self.report,before)

    def test_changed_reused_training_check_rejected(self):
        self.report['training_checks']['LI']['value']=2.000001
        with self.assertRaisesRegex(c.AuditError,'training check'):self.audit()

    def test_changed_replayed_return_rejected(self):
        self.report['fits']['LIplus_immigrant']['records'][0]['nfev']=3
        with self.assertRaisesRegex(c.AuditError,'Replayed return'):self.audit()

    def test_extra_physical_optimizer_rejected(self):
        self.ledger_change(lambda rows:rows.extend(copy.deepcopy(rows[-2:])))
        with self.assertRaisesRegex(c.AuditError,'invocation roster'):self.audit()

    def test_last_iterate_restart_rejected(self):
        self.ledger_change(lambda rows:next(v for v in rows if v['event']=='physical_optimizer_start').update(initial_parameters=[2.]))
        with self.assertRaisesRegex(c.AuditError,'initial point'):self.audit()

    def test_anchor_payload_not_boolean_only(self):
        self.ledger_change(lambda rows:next(v for v in rows if v['event']=='restart_return_anchor_verified')['actual_evaluation']['score'].update(nll=4.))
        with self.assertRaisesRegex(c.AuditError,'completed-return anchor'):self.audit()

    def test_next_input_payload_checked(self):
        self.ledger_change(lambda rows:next(v for v in rows if v['event']=='restart_next_input_anchor_verified').update(parameters=[7.]))
        with self.assertRaisesRegex(c.AuditError,'next-input anchor'):self.audit()

    def test_optimizer_budget_not_extended(self):
        self.ledger_change(lambda rows:next(v for v in rows if v['event']=='physical_optimizer_start')['options'].update(maxfev=7040))
        with self.assertRaisesRegex(c.AuditError,'restart budget'):self.audit()

    def test_eval_counters_balance(self):
        with self.assertRaisesRegex(c.AuditError,'balance'):
            c.counters({'train|LI|8|support|True':dict(attempted=3,returned=1,errors=1)})

    def test_automated_pilot_review_is_not_live(self):
        v=dict(passed=True,index_sha256='index',review_kind='automated_saved_output_check',
               live_agent_review=False,live_agent_review_performed=False,final_batch_agent_review_required=True,
               checker_sources_sha256={},checker_source_review_sha256='review')
        with self.assertRaisesRegex(c.AuditError,'pilot'):
            c.validate_review(v,'index',{},'review',pilot=True)
        c.validate_review(v,'index',{},'review',pilot=False)

    def test_missing_live_attribution_rejected(self):
        with self.assertRaisesRegex(c.AuditError,'live review'):
            c.validate_review(dict(passed=True,index_sha256='index',reviewer='/root/continuation_cpu'),
                              'index',{},'review',pilot=True)

    def test_prefix_attempt_cannot_disappear(self):
        prior=self.root/'prior';current=self.root/'current';prior.mkdir();current.mkdir()
        old=dict(cases=[],attempts=[dict(attempt_id='failed')],reviews=[])
        index=dict(cases=[{}],attempts=[dict(attempt_id='new')],reviews=[{}])
        with self.assertRaisesRegex(c.AuditError,'charged-attempt prefix'):
            c.preserved_prefix(index,old,current,prior)

    def test_failed_checker_receipt_is_unambiguously_automated(self):
        output=self.root/'failure.json'
        argv=[]
        for key in ('repo','current','prior','prior-review','config','commit','checker-source-review','checker-source-review-sha256'):
            argv.extend(['--'+key,'invented'])
        argv.extend(['--output',str(output)])
        with patch.object(c,'audit_saved',side_effect=c.AuditError('injected')):
            self.assertEqual(c.main(argv),1)
        result=json.loads(output.read_text())
        self.assertFalse(result['passed']);self.assertFalse(result['live_agent_review'])
        self.assertTrue(result['final_batch_agent_review_required'])
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
                         operational_failures=[startup,{'charge_seconds':120}],operational_diagnostics=[{'charge_seconds':80}])
        self.index=dict(pre_execution_failure=copy.deepcopy(startup),recovery_transition=dict(pre_execution_failure=copy.deepcopy(startup)),
                        attempts=[dict(attempt_id='original-interruption')],
                        operational_accounting=dict(scientific_indexed_seconds=100.,known_prior_outer_overhead_seconds=3.,
                                                    operational_failure_charge_seconds=210,operational_diagnostic_charge_seconds=80,accounted_seconds=393.))

    def audit(self):
        c.inspect_startup_failure(self.index,self.root,self.policy)
        return c.inspect_operational_accounting(self.index,self.policy,100.)

    def test_separate_charge_preserves_scientific_sum(self):
        result=self.audit()
        self.assertEqual(result['scientific_indexed_seconds'],100.)
        self.assertEqual(result['accounted_seconds'],393.)

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


def gradient_record(a,b):
    rows=[]
    for i,(x,y) in enumerate(zip(a,b)):
        limit=64*sys.float_info.epsilon*max(1.,abs(x),abs(y))
        rows.append(dict(index=i,actual=x,expected=y,delta=x-y,absolute_delta=abs(x-y),bound=limit,passed=True))
    return dict(passed=True,epsilon=sys.float_info.epsilon,multiplier=64,
                formula='64 * float64_epsilon * max(1, abs(actual), abs(expected))',components=rows)


def support_record():
    expected=dict(passed=True,parameters=[0.]*8,coarse={'nll':7.},fine={'nll':7.},
                  projected_gradient_coarse=[0.]*8,projected_gradient_fine=[0.]*8,
                  projected_gradient_scaled_delta=0.,projected_kkt_infinity_norm=0.)
    actual=copy.deepcopy(expected);actual['projected_gradient_coarse'][3]=32*sys.float_info.epsilon
    actual['projected_gradient_scaled_delta']=32*sys.float_info.epsilon
    eq=dict(passed=True,policy='reused_LI_training_support_gradient_only_v1',
            scientific_criteria_unchanged=True,hardware_cause_established=False,
            gradient_checks={key:gradient_record(actual[key],expected[key]) for key in ('projected_gradient_coarse','projected_gradient_fine')},
            recomputed_gradient_delta=dict(actual=actual['projected_gradient_scaled_delta'],expected=0.),
            derived_delta_comparison=gradient_record([actual['projected_gradient_scaled_delta']],[0.]))
    record=dict(actual=actual,expected=expected,exact_match=False,differences=c.leaf_differences(actual,expected),
                accepted_check_source='original_saved_check',operational_equivalence=eq)
    return record,copy.deepcopy(expected)


class NarrowGradientEquivalence(unittest.TestCase):
    def replay(self):
        old=dict(parameters=[0.]*8,gradient=[0.]*8,projected_gradient=[0.]*8,fresh_score={'nll':3.},success=True)
        actual=copy.deepcopy(old);actual['gradient'][2]=actual['projected_gradient'][2]=32*sys.float_info.epsilon
        eq=dict(passed=True,policy='replayed_completed_start_support_gradient_only_v1',non_gradient_fields_exact=True,
                raw_gradient_comparison=gradient_record(actual['gradient'],old['gradient']),
                projected_gradient_comparison=gradient_record(actual['projected_gradient'],old['projected_gradient']),
                actual_projection_exact=True,expected_projection_exact=True)
        record=dict(actual=actual,expected=old,exact_match=False,differences=c.leaf_differences(actual,old),
                    operational_equivalence=eq,accepted_record_source='original_saved_record')
        return record,old,[[-1.,1.]]*8

    def test_replayed_start_gradient_has_independent_projection(self):
        record,old,box=self.replay();c.inspect_replayed_support(record,old,box)
        record['actual']['projected_gradient'][2]=0.
        record['differences']=c.leaf_differences(record['actual'],old)
        record['operational_equivalence']['projected_gradient_comparison']=gradient_record(record['actual']['projected_gradient'],old['projected_gradient'])
        with self.assertRaisesRegex(c.AuditError,'projected gradient differs'):c.inspect_replayed_support(record,old,box)

    def test_replayed_scalar_and_success_remain_exact(self):
        record,old,box=self.replay()
        for key in ('fresh_score','success'):
            v=copy.deepcopy(record)
            if key=='fresh_score':v['actual'][key]['nll']+=4*sys.float_info.epsilon
            else:v['actual'][key]=False
            # An altered nonnumeric field is itself an immediate rejection.
            if key=='fresh_score':v['differences']=c.leaf_differences(v['actual'],old)
            with self.subTest(key=key),self.assertRaises(c.AuditError):c.inspect_replayed_support(v,old,box)

    def test_replayed_candidate_keeps_score_and_state_exact(self):
        record,old,box=self.replay()
        expected=dict(state_index=1,kind='optimizer',start_index=0,parameters=old['parameters'],score=old['fresh_score'],gradient=old['gradient'])
        actual=copy.deepcopy(expected);actual['gradient']=record['actual']['gradient']
        candidate=dict(actual=actual,expected=expected,exact_match=False,differences=c.leaf_differences(actual,expected),
                       accepted_candidate_gradient_source='original_saved_record.gradient',operational_equivalence=dict(passed=True,non_gradient_fields_exact=True,
                           gradient_comparison=gradient_record(actual['gradient'],expected['gradient'])))
        self.assertEqual(c.inspect_replayed_candidate(candidate,old,0),expected)
        candidate['actual']['state_index']=2;candidate['differences']=c.leaf_differences(candidate['actual'],expected)
        with self.assertRaisesRegex(c.AuditError,'score or identity'):c.inspect_replayed_candidate(candidate,old,0)

    def test_bound_is_exact_and_not_a_general_score_tolerance(self):
        a=[64*sys.float_info.epsilon]*8;b=[0.]*8
        c.inspect_gradient_comparison(a,b,gradient_record(a,b))
        a[0]=math.nextafter(a[0],math.inf)
        with self.assertRaisesRegex(c.AuditError,'exceeds declared bound'):
            c.inspect_gradient_comparison(a,b,gradient_record(a,b))

    def test_nonfinite_gradient_cannot_pass_with_claimed_success(self):
        for value in (math.nan,math.inf,-math.inf,True):
            with self.subTest(value=value),self.assertRaises(c.AuditError):
                c.inspect_gradient_comparison([value]+[0.]*7,[0.]*8,gradient_record([0.]*8,[0.]*8))

    def test_claimed_bound_cannot_be_enlarged(self):
        a=[0.]*8;record=gradient_record(a,a);record['components'][0]['bound']=1e-9
        with self.assertRaisesRegex(c.AuditError,'component arithmetic'):
            c.inspect_gradient_comparison(a,a,record)

    def test_support_gradient_difference_is_reported_not_called_exact(self):
        record,original=support_record();c.inspect_training_equivalence(record,original,'LI')
        record['exact_match']=True
        with self.assertRaisesRegex(c.AuditError,'attribution'):
            c.inspect_training_equivalence(record,original,'LI')

    def test_support_scalar_score_cannot_use_gradient_bound(self):
        record,original=support_record();record['actual']['fine']['nll']+=sys.float_info.epsilon*8
        record['differences']=c.leaf_differences(record['actual'],record['expected'])
        with self.assertRaisesRegex(c.AuditError,'Non-gradient'):
            c.inspect_training_equivalence(record,original,'LI')

    def test_support_derived_delta_is_recomputed(self):
        record,original=support_record();record['actual']['projected_gradient_scaled_delta']=0.
        record['differences']=c.leaf_differences(record['actual'],record['expected'])
        with self.assertRaisesRegex(c.AuditError,'Derived support'):
            c.inspect_training_equivalence(record,original,'LI')

    def test_support_cannot_be_relabelled_as_fresh(self):
        record,original=support_record();record['accepted_check_source']='fresh_check'
        with self.assertRaisesRegex(c.AuditError,'reuse/equality'):
            c.inspect_training_equivalence(record,original,'LI')

    def test_powell_unused_gradient_only_parameters_and_scores_exact(self):
        expected=dict(parameters=[1.]*8,score={'nll':3.},gradient=[0.]*8)
        actual=copy.deepcopy(expected);actual['gradient'][2]=32*sys.float_info.epsilon
        record=dict(actual=actual,expected=expected,exact_match=False,differences=c.leaf_differences(actual,expected),
                    operational_equivalence=dict(passed=True,policy='unused_Powell_anchor_gradient_only_v1',
                      objective_parameters_and_scores_exact=True,gradient_comparison=gradient_record(actual['gradient'],expected['gradient'])))
        c.inspect_anchor_equivalence(record,expected)
        for field in ('parameters','score'):
            changed=copy.deepcopy(record)
            if field=='parameters':changed['actual']['parameters'][0]+=sys.float_info.epsilon
            else:changed['actual']['score']['nll']+=4*sys.float_info.epsilon
            changed['differences']=c.leaf_differences(changed['actual'],changed['expected'])
            with self.subTest(field=field),self.assertRaisesRegex(c.AuditError,'score or parameter'):
                c.inspect_anchor_equivalence(changed,expected)


class OrderedOperationalEvidence(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name);lineage=self.root/'recovery_lineage';lineage.mkdir()
        first=dict(archive_sha256='earlier',charge_seconds=90)
        objects=[]
        for names,charge,diagnostic in ((c.SUPPORT_FILES,120,False),(c.DIAGNOSTIC_FILES,80,True)):
            (lineage/names['archive']).write_bytes(str(charge).encode())
            (lineage/names['workflow_log']).write_text('invented workflow '+str(charge))
            row=dict(charge_seconds=charge,scientific_predecessor_unchanged=True,nested_scientific_seconds=1.,nested_supervised_seconds=2.,
                     archive_sha256=c.sha(lineage/names['archive']),workflow_log_sha256=c.sha(lineage/names['workflow_log']),
                     support_evaluation_count=5,optimizer_call_count=0)
            review=dict(archive_sha256=row['archive_sha256'],audit_passed=True,live_agent_review=True,reviewer='/root/continuation_cpu')
            resource=dict(passed=True,timing=dict(conservative_whole_launch_charge_seconds=charge,child_scientific_seconds=1.,
                          outer_including_cleanup_seconds=2.,nested_intervals_not_additive=True),input_sha256={'log':row['workflow_log_sha256']})
            if diagnostic:
                row.update(status='diagnostic_complete',passed=True,equality_passed=False,scientific_completion=False,held_out_call_count=0)
                review.update(passed=True,diagnostic_complete=True,equality_passed=False,accepted_recovery_case=False,scientific_completion=False)
            else:
                row.update(status='failed_during_training_support')
                review.update(passed=False,overall_scientific_passed=False,accepted_completed_prefix={'count':40},
                              execution_census=dict(new_training_support_evaluations=5,new_optimizer_invocations=0))
            write(lineage/names['review'],review);row['review_sha256']=c.sha(lineage/names['review'])
            if diagnostic:resource['diagnostic']=dict(archive_sha256=row['archive_sha256'],independent_review_sha256=row['review_sha256'])
            else:resource.update(failure=dict(passed=False,archive_sha256=row['archive_sha256'],failed_attempt_id='support-failed'),
                                 independent_failure_audit=dict(sha256=row['review_sha256']))
            write(lineage/names['resource_review'],resource);row['resource_review_sha256']=c.sha(lineage/names['resource_review'])
            objects.append(row)
        self.policy=dict(pre_execution_failure=first,operational_failures=[first,objects[0]],operational_diagnostics=[objects[1]])
        self.index=dict(operational_failures=copy.deepcopy(self.policy['operational_failures']),operational_diagnostics=copy.deepcopy(self.policy['operational_diagnostics']),
                        recovery_transition=copy.deepcopy(self.policy),attempts=[dict(attempt_id='original-science')])

    def test_exact_two_failures_one_diagnostic_have_separate_scope(self):
        c.inspect_operational_lists(self.index,self.root,self.policy)

    def test_diagnostic_cannot_be_relabelled_as_scientific_success(self):
        self.policy['operational_diagnostics'][0]['scientific_completion']=True
        self.index['operational_diagnostics']=copy.deepcopy(self.policy['operational_diagnostics'])
        self.index['recovery_transition']['operational_diagnostics']=copy.deepcopy(self.policy['operational_diagnostics'])
        with self.assertRaisesRegex(c.AuditError,'Diagnostic accounting'):c.inspect_operational_lists(self.index,self.root,self.policy)

    def test_operational_archive_cannot_be_duplicated(self):
        self.policy['operational_diagnostics'][0]['archive_sha256']=self.policy['operational_failures'][1]['archive_sha256']
        with self.assertRaisesRegex(c.AuditError,'Duplicate operational'):c.inspect_operational_lists(self.index,self.root,self.policy)

    def test_support_child_is_not_another_scientific_charge(self):
        self.index['attempts'].append(dict(attempt_id='support-failed'))
        with self.assertRaisesRegex(c.AuditError,'charged again'):c.inspect_operational_lists(self.index,self.root,self.policy)

    def test_retained_diagnostic_archive_is_hashed(self):
        (self.root/'recovery_lineage'/c.DIAGNOSTIC_FILES['archive']).write_bytes(b'changed')
        with self.assertRaisesRegex(c.AuditError,'evidence bytes'):c.inspect_operational_lists(self.index,self.root,self.policy)


if __name__=='__main__':unittest.main()
