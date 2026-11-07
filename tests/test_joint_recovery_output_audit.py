"""Invented saved-output controls; no scientific evaluator or optimizer import."""
from pathlib import Path
import copy
import json
import tempfile
import unittest
from unittest.mock import patch

from experiments.s04b_joint_recovery_audit import check as c


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value)+'\n', encoding='utf-8')


def fixture(root):
    arm='LIplus_immigrant'
    original=dict(passed=False,wall_seconds=12.,fits={'null':{'old':1},'LI':{'old':2}},
                  training_checks={'null':{'value':1.},'LI':{'value':2.}})
    trace=[]; ends={}
    for name in ('null','LI',arm):
        for i in range(8 if name!=arm else 6):
            record=dict(start_index=i,method='L-BFGS-B',initial_parameters=[float(i)],
                        status='returned',success=True,nfev=2,nit=1)
            if name==arm and i==5:
                record.update(status='exception',success=False,error_type='ArithmeticError',error='Finite objective has unrepresentable gradient')
            ends[name,i,'L-BFGS-B']=record
            trace.extend([dict(event='attempt_start',model=name,**record),dict(event='attempt_end',model=name,**record)])
    timeout=dict(start_index=5,method='Powell',initial_parameters=[5.],status='exception',success=False,
                 error_type='TimeoutError',last_evaluation=dict(evaluation_count=2040,parameters=[2.],score={'nll':3.},gradient=[4.]),
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
    ledger += [dict(event='replayed_optimizer_return',model=arm,start_index=i,method='L-BFGS-B',actual_objective_calls=0,historical_nfev=2,historical_nit=1) for i in range(5)]
    ledger += [dict(event='replayed_primary_error',actual_objective_calls=0,original_record=ends[arm,5,'L-BFGS-B'])]
    for name,i,method in expected:
        restart=(name,i,method)==(arm,5,'Powell')
        kind='restarted_interrupted_invocation' if restart else 'new_optimizer_invocation'
        ledger.append(dict(event='physical_optimizer_start',model=name,start_index=i,method=method,kind=kind,
                           initial_parameters=[float(i)],options=policy['recovery']['original_powell_options'] if restart else {}))
        if restart:
            ledger.append(dict(event='restart_return_anchor_verified',evaluation_count=2040,
                               actual_evaluation={k:v for k,v in timeout['last_evaluation'].items() if k!='evaluation_count'}))
            ledger.append(dict(event='restart_next_input_anchor_verified',evaluation_number=2041,parameters=[6.]))
        ledger.append(dict(event='physical_optimizer_end',model=name,start_index=i,method=method,kind=kind,
                           returned=True,completed_objective_returns=2041 if restart else 2,actual_evaluations=counts))
    execution=dict(schema='joint_partial_optimizer_recovery_calls_v1',exact_internal_optimizer_resume=False,
                   original_physical_attempts_retained=23,arm_calls=['null','LI',arm,'LIplus_inclusive'],
                   reused_complete_arms=['null','LI'],replayed_successful_starts=list(range(5)),
                   original_interrupted_powell=timeout,original_primary_error=ends[arm,5,'L-BFGS-B'],
                   anchor_return_verified=True,anchor_next_input_verified=True,logical_optimizer_calls=logical,
                   actual_evaluations=counts)
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

    def audit(self):return c.inspect_recovery_execution(self.root,self.report,self.policy)

    def ledger_change(self,mutate):
        mutate(self.ledger)
        (self.root/'recovery_calls.jsonl').write_text(''.join(json.dumps(v)+'\n' for v in self.ledger))

    def test_logical_success_keeps_physical_timeout(self):
        r=self.audit()
        self.assertEqual(r['original_physical_attempts'],23)
        self.assertEqual(r['new_physical_optimizer_invocations'],11)
        self.assertTrue(r['original_timeout_retained'])
        self.assertFalse(r['exact_internal_optimizer_resume'])

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
        self.policy=dict(pre_execution_failure=startup,predecessor=dict(known_outer_overhead_seconds=3.))
        self.index=dict(pre_execution_failure=copy.deepcopy(startup),recovery_transition=dict(pre_execution_failure=copy.deepcopy(startup)),
                        attempts=[dict(attempt_id='original-interruption')],
                        operational_accounting=dict(scientific_indexed_seconds=100.,known_prior_outer_overhead_seconds=3.,
                                                    pre_execution_failure_charge_seconds=90,accounted_seconds=193.))

    def audit(self):
        c.inspect_startup_failure(self.index,self.root,self.policy)
        return c.inspect_operational_accounting(self.index,self.policy,100.)

    def test_separate_charge_preserves_scientific_sum(self):
        result=self.audit()
        self.assertEqual(result['scientific_indexed_seconds'],100.)
        self.assertEqual(result['accounted_seconds'],193.)

    def test_omitted_or_doubled_charge_rejected(self):
        for value in (0,180):
            with self.subTest(value=value):
                self.index['operational_accounting']['pre_execution_failure_charge_seconds']=value
                self.index['operational_accounting']['accounted_seconds']=103.+value
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


if __name__=='__main__':unittest.main()
