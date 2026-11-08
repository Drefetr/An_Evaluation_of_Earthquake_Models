"""Invented saved evidence only; no likelihood/native/optimizer evaluation.

Trust-root constants are explicitly replaced with invented fixture authorities.
Actual checker functions are never mocked. Integration uses the real operational
host assembly with invented child artifacts and the real independent audit.
"""
import copy
from contextlib import ExitStack
import datetime as dt
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch
import zipfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    value = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(value)
    return value


A = module('wall_independent_audit_tested', ROOT/'experiments/s04b_wall_failure_continuation_audit/check.py')
F = module('wall_invented_saved_fixture', ROOT/'tests/test_joint_exposure_refinement_audit.py')


def dump(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, allow_nan=False)+'\n', encoding='utf-8', newline='\n')


def encoded(value):
    return (json.dumps(value, indent=2, allow_nan=False)+'\n').encode()


def wall_fixture():
    science, template = F.science_fixture()
    report = copy.deepcopy(template)
    report.update(case_id=A.FAILURE, seed=410615, regime=6, passed=False, status='unknown', outcomes=[],
                  error_type='TimeoutError', error='Joint experiment deadline')
    report.pop('new_null_test', None); report.pop('test_checks', None)
    report.pop('training_selections_frozen', None); report.pop('bic_threshold', None)
    total = copy.deepcopy(report['fits'].pop('LIplus_inclusive'))
    report['training_checks'].pop('LIplus_inclusive')
    report['floor_checks'] = [x for x in report['floor_checks'] if x['phase'] == 'train']
    immigrant = report['fits']['LIplus_immigrant']['records']
    error = dict(start_index=5, method='L-BFGS-B', initial_parameters=immigrant[5]['initial_parameters'],
                 status='exception', success=False, error_type='ArithmeticError',
                 error='Finite objective has unrepresentable gradient')
    immigrant[5]['method'] = 'Powell'
    immigrant.insert(5, error)
    ends = [dict(event='attempt_end', model=model, **row) for model, fit in report['fits'].items() for row in fit['records']]
    ends += [dict(event='attempt_end', model='LIplus_inclusive', **row) for row in total['records'][:3]]
    interrupted = dict(event='attempt_end', model='LIplus_inclusive', start_index=3, method='L-BFGS-B',
        initial_parameters=total['records'][3]['initial_parameters'], status='exception', success=False,
        error_type='TimeoutError', error='Joint experiment deadline')
    ends.append(interrupted)
    trace = []
    for row in ends:
        trace += [dict(event='attempt_start', model=row['model'], start_index=row['start_index'], method=row['method'],
                       initial_parameters=row['initial_parameters'], status='running', success=False), row]
    policy = dict(original_native=dict(runtime_essential={'fixture':'never executed'}, library_sha256='a'*64, build_receipt_sha256='b'*64))
    result = dict(case_id=A.FAILURE, passed=False, scientific_passed=False, handled=False, disposition_valid=False,
        scientific_completion=False, disposition='technical_failure', status='failed', error_type='ValueError',
        error='Case optimizer records differ from trace', scientific_clock_cap_exceeded=True,
        phase_constructions=[dict(start=30,end=395,returned=True)], actual_optimizer_attempts=29, reused_optimizer_attempts=0,
        source_sha256={'invented':'c'*64}, runtime={'essential':policy['original_native']['runtime_essential']},
        library_sha256='a'*64, build_receipt_sha256='b'*64, wall_seconds=2490.02)
    supervision = dict(status='failed',returncode=1,launched=True,stop_reason=None,survivors_after_cleanup=[],cleanup_errors=[],
                       execution_wall_seconds=2490.5,wall_seconds_including_cleanup=2490.6)
    review = dict(source_sha256=result['source_sha256'],failure=dict(case_id=A.FAILURE,interrupted_record=interrupted,
        held_out_calls=0,new_outcomes_available=0,unavailable_comparisons=5,reuse_count=0),
        resource=dict(failed_scientific_seconds_not_indexed='2490.02',failed_child_outer_seconds_not_indexed='2490.6'))
    return report,result,trace,supervision,review,policy


class FailureClassification(unittest.TestCase):
    def test_raw_unknown_status_remains_technical_wall_failure(self):
        args = wall_fixture()
        A.failure_semantics(*args)
        self.assertEqual(args[0]['status'], 'unknown')
        self.assertFalse(args[1]['disposition_valid'])

    def test_repinned_semantic_relabelings_are_not_accepted(self):
        mutations = [lambda x:x[1].update(disposition='scientific_unknown'),
            lambda x:x[1].update(passed=True), lambda x:x[1].update(handled=True),
            lambda x:x[0].update(outcomes=[{'new_gain':0.}]),
            lambda x:x[1]['phase_constructions'].append(dict(start=395,end=760,returned=True)),
            lambda x:x[1].update(wall_seconds=2490),
            lambda x:x[3].update(stop_reason='wall_time'),
            lambda x:x[2][-1].update(error_type='ArithmeticError'),
            lambda x:x[1].update(actual_optimizer_attempts=27),
            lambda x:x[4]['failure'].update(unavailable_comparisons=0)]
        for mutate in mutations:
            args = wall_fixture(); mutate(args)
            with self.subTest(mutate=mutate), self.assertRaises((ValueError, KeyError)):
                A.failure_semantics(*args)


class InventedOperationalCampaign(F.InventedSavedCampaign):
    """Real custody and source gates, with openly invented prior authorities."""
    def __init__(self, directory):
        super().__init__(directory)
        from experiments import s04b_wall_failure_continuation as metadata
        from experiments.s04b_wall_failure_continuation import host, transition
        self.M, self.H, self.T = metadata, host, transition
        self.op = A.read(ROOT/A.PROTOCOL)
        real_policy = A.read(ROOT/A.frozen.PROTOCOL_PATH)
        # The old fixture supplies mathematical input artifacts. Broaden only its
        # declared invented trust roots, not a validation function.
        self.resources.update(copy.deepcopy(real_policy['resources']))
        self.resources['accounted_seconds'] = '25139.78809128000155'
        self.resources['costs_seconds'] = {'invented_retained_cost':'25139.78809128000155'}
        self.policy.update(partial_case_id=A.frozen.PARTIAL, resources=self.resources)
        self.policy['refinement'].update(joint_absolute_tolerance=self.science['quadrature']['joint_absolute_tolerance'],
            projected_gradient_scaled_tolerance=self.science['quadrature']['selected_training_gradient_scaled_tolerance'])
        copied = set(real_policy['source_sha256']) | A.REQUIRED_PRODUCER | set(self.op['producer_source_paths']) | {self.op['checker']['test']}
        copied.update('experiments/s04b_exposure_refinement/'+name for name in
                      ('__init__.py','adapter.py','partial_fit.py','case_driver.py','host.py'))
        for rel in copied:
            if rel in (A.frozen.SCIENCE_PATH, A.PROTOCOL):continue
            target=self.repo/rel;target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes((ROOT/rel).read_bytes())
        self.policy['source_sha256'] = {name:A.sha(self.repo/name) for name in real_policy['source_sha256']}
        design=A.read(self.design_dir/'protocol_proposal.json')
        design['refinement']=self.policy['refinement'];design['unchanged']['scientific_dependency_sha256']=self.policy['source_sha256']
        dump(self.design_dir/'protocol_proposal.json',design);dump(self.design_dir/'resources.json',self.resources)
        self.design_pins={name:A.sha(self.design_dir/name) for name in A.frozen.DESIGN_PINS}
        self.policy['design_evidence_sha256']={A.frozen.DESIGN+name:pin for name,pin in self.design_pins.items()}
        dump(self.repo/A.frozen.PROTOCOL_PATH,self.policy);self.protocol_sha=A.sha(self.repo/A.frozen.PROTOCOL_PATH)
        self.source_map=A.scientific_sources(self.repo,self.policy)
        self.reports={}
        for name in self.op['case_ids']:
            report=self.make_report(name);self.add_historical_inputs(report);self.reports[name]=report
        dump(self.repo/'reproduction/synthetic/input_manifest.json',{'s04b':{'cases':self.manifest}})
        raw=copy.deepcopy(self.base)
        raw.update(schema='joint_exposure_refinement_index_v1',protocol_sha256=self.protocol_sha,
            numerical_amendment_version=A.frozen.VERSION,original_scientific_protocol_sha256=self.science_sha,
            host_source_sha256=self.source_map,scientific_source_sha256=self.source_map,original_native=self.native_meta,
            immutable_failure_reference=self.unknown_ref,original_exposure_failure_reference=self.policy['failed_case'],
            compatible_saved_prefix=self.policy['base'],predecessor={'invented':'accepted previous host'},budget={'invented':'old immutable accounting'})
        raw['attempts']=[]
        for i,name in enumerate(self.sequence[44:55],44):
            report=self.make_report(name)
            row=A.old.projection(report,'complete',{'kind':'host_execution','execution_id':'invented-prior-'+str(i)})
            if 46<=i<=50:row['execution_producer']={'schema':'invented_public_producer','retained_case':name}
            raw['records'].append(row)
            raw['attempts'].append(dict(case_id=name,numerical_attempt_id='old-child-'+str(i),host_execution_id='old-host-'+str(i),
                seconds=2.,outer_seconds=3.3,result_sha256='1'*64,supervision_sha256='2'*64,actual_optimizer_attempts=32,reused_optimizer_attempts=28 if i==44 else 0))
        raw['counts']=A.old.expected_counts(raw['records']);self.raw=raw
        report,result,trace,supervisor,review,_=wall_fixture()
        self.add_historical_inputs(report)
        report['fixed_spatial_mark_law']={'fixture':'unchanged law metadata'}
        dump(self.repo/'reproduction/synthetic/input_manifest.json',{'s04b':{'cases':self.manifest}})
        result.update(source_sha256=self.source_map,protocol_sha256=self.protocol_sha,
            runtime={'essential':self.native_meta['runtime_essential']},library_sha256=self.native_meta['library_sha256'],
            build_receipt_sha256=self.native_meta['build_receipt_sha256'],schema='joint_exposure_refinement_case_v1',
            allocation=next(x for x in self.policy['case_slots'] if x['case_id']==A.FAILURE),numerical_attempt_id='invented-failed-child',
            report_file='cases/'+A.FAILURE+'.json',trace_file='cases/'+A.FAILURE+'.attempts.jsonl',
            numerical_amendment={'version':A.frozen.VERSION,'fixture':'uncompleted saved artifact'})
        trace_raw=''.join(json.dumps(x)+'\n' for x in trace).encode();report['attempts_sha256']=A.frozen.hash_bytes(trace_raw)
        prefix='host/children/05_'+A.FAILURE
        admission=dict(case_id=A.FAILURE,case_ids=[A.FAILURE],source_sha256=self.source_map,wall_seconds=2520,scientific_seconds=2490)
        admission_raw=encoded(admission);result['admission_sha256']=A.frozen.hash_bytes(admission_raw)
        spec=dict(command=['python','-B','-m','experiments.s04b_exposure_refinement.case_driver','--mode','untouched','--case-id',A.FAILURE],
                  wall_cap_seconds=2520,rss_cap_bytes=6442450944,host_headroom_bytes=2147483648)
        spec_raw=encoded(spec);supervisor.update(spec_sha256=A.frozen.hash_bytes(spec_raw),execution_log_sha256=A.frozen.hash_bytes(b''),
            sampled_peak_tree_rss_bytes=1024,minimum_sampled_host_available_bytes=9999999999)
        result['report_sha256']=A.frozen.hash_bytes(encoded(report));result['trace_sha256']=A.frozen.hash_bytes(trace_raw)
        members={'host/index.json':encoded(raw),prefix+'/admission.json':admission_raw,prefix+'/supervisor_spec.json':spec_raw,
            prefix+'/supervision/execution.log':b'',prefix+'/science/'+result['report_file']:encoded(report),
            prefix+'/science/'+result['trace_file']:trace_raw,prefix+'/science/result.json':encoded(result),
            prefix+'/supervision/result.json':encoded(supervisor),'build/attenuation.so':self.native,'build/build_receipt.json':self.build_raw}
        archive_rel='validation/invented_wall_host.zip';archive=self.repo/archive_rel
        with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED) as saved:
            for name,value in members.items():saved.writestr(name,value)
        failure=review['failure'];failure.update(report_sha256=result['report_sha256'],trace_sha256=result['trace_sha256'],
            result_sha256=A.frozen.hash_bytes(encoded(result)))
        review.update(schema='invented_failed_host_live_review',passed=False,audit_passed=True,disposition_valid=False,scientific_passed=False,
            scientific_completion=False,review_kind='live_agent_saved_output_review',live_agent_review=True,live_agent_review_performed=True,
            final_batch_agent_review_required=False,execution_id='invented-host04',source_sha256=self.source_map,
            artifact_sha256=A.sha(archive),index_path='host/index.json',index_sha256=A.frozen.hash_bytes(encoded(raw)),counts=raw['counts'],
            archive_members_sha256={name:A.frozen.hash_bytes(value) for name,value in members.items()},
            accepted_completed_prefix=dict(audit_passed=True,processed_histories=55,complete_histories=54,permanent_unknown_histories=1,
                computed_outcomes=270,new_complete_cases=self.sequence[51:55],prior51_records_exact=True,prior5_public_producer_objects_exact=True))
        review['resource'].update(known_accounted_after_whole_host04_seconds='30000',prior_workflow_overheads_outside_index_seconds='20',
            whole_workflow_overhead_beyond_all_child_outer_seconds='10',workflow_logged_seconds='2513.8',
            completed_new_indexed_outer_seconds='13.2',charge_missing_from_completed_prefix_index_seconds='2500.6')
        failure_review_rel='validation/invented_wall_host_review.json';dump(self.repo/failure_review_rel,review)
        self.failure_review_sha=A.sha(self.repo/failure_review_rel)
        self.op.update(numerical_protocol=dict(path=A.frozen.PROTOCOL_PATH,sha256=self.protocol_sha),
            scientific_protocol=dict(path=A.frozen.SCIENCE_PATH,sha256=self.science_sha),core_source_sha256=self.source_map,
            original_native=self.native_meta,shared_run=self.shared)
        self.op['base']=dict(archive=dict(path=archive_rel,sha256=A.sha(archive)),review=dict(path=failure_review_rel,sha256=self.failure_review_sha),
            index_member='host/index.json',index_sha256=review['index_sha256'],records=55)
        self.op['failure']=dict(case_id=A.FAILURE,child_prefix=prefix,execution_id='invented-host04',failure_census=failure)
        for name,member in [('case',prefix+'/science/'+result['report_file']),('trace',prefix+'/science/'+result['trace_file']),
                            ('result',prefix+'/science/result.json'),('supervision',prefix+'/supervision/result.json')]:
            self.op['failure'].update({name+'_member':member,name+'_sha256':A.frozen.hash_bytes(members[member])})
        self.op['accounting'].update(sealed_known_seconds='30000',unconsumed_host_overhead_reserve_seconds='14370',
            failure_scientific_seconds='2490.02',failure_outer_seconds='2490.6',host04_overhead_seconds='10')
        dump(self.repo/A.DESIGN_REVIEW,dict(passed=True,fixture='Explicit invented design authority'))
        self.operational_design_sha=A.sha(self.repo/A.DESIGN_REVIEW)
        self.op['design_evidence']={A.DESIGN_REVIEW:self.operational_design_sha}
        dump(self.repo/A.PROTOCOL,self.op)
        self.host_map={**self.source_map,**{name:A.sha(self.repo/name) for name in self.op['producer_source_paths']}}
        self.checker_pins={name:A.sha(self.repo/name) for name in A.CHECKER_FILES}
        self.graph={**self.host_map,**self.checker_pins,**{name:A.sha(self.repo/name) for name in A.REQUIRED_PRODUCER|{self.op['checker']['test']}}}
        for command in (['git','-c','core.autocrlf=false','add','.'],['git','-c','user.name=Invented fixture','-c','user.email=fixture@example.invalid','-c','commit.gpgsign=false','commit','-m','Invented wall-failure evidence and source graph']):
            subprocess.run(command,cwd=self.repo,check=True,capture_output=True)
        self.commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=self.repo,text=True).strip()
        dump(self.repo/self.review_rel,dict(passed=True,live_agent_review=True,live_agent_review_performed=True,
            final_batch_agent_review_required=False,scientific_completion=False,reviewed_files_sha256=self.graph))
        self.review_sha=A.sha(self.repo/self.review_rel)
        with self.patches():
            self.sealed=self.T.build_sealed(self.op,*self.T.base_evidence(self.op))
        self.sealed_rel='validation/invented_transition/index.json';dump(self.repo/self.sealed_rel,self.sealed)
        self.seal_review_rel='validation/invented_transition/independent_review.json'
        seal_review=dict(passed=True,audit_passed=True,review_kind='live_operational_failure_transition_review',live_agent_review=True,
            live_agent_review_performed=True,final_batch_agent_review_required=False,scientific_completion=False,
            failure_accounting_valid=True,scientific_execution_passed=False,index_sha256=A.sha(self.repo/self.sealed_rel),
            operational_continuation=dict(path=A.PROTOCOL,sha256=A.sha(self.repo/A.PROTOCOL)),raw_archive=self.op['base']['archive'],
            raw_review=self.op['base']['review'],raw_index_sha256=self.op['base']['index_sha256'])
        dump(self.repo/self.seal_review_rel,seal_review)
        self.prior=self.repo/self.sealed_rel;self.prior_review=self.repo/self.seal_review_rel

    def patches(self):
        stack=super().patches()
        for target,key,value in [(A.frozen,'DESIGN_PINS',self.design_pins),(A.frozen,'SCIENCE_SHA',self.science_sha),
            (A,'FAILURE_REVIEW_SHA',self.failure_review_sha),(A,'DESIGN_REVIEW_SHA',self.operational_design_sha),
            (self.M,'REPO',self.repo),(self.H,'REPO',self.repo),
            (self.H.frozen.driver,'REPO',self.repo),(self.H.frozen.driver,'HERE',self.repo/'experiments/s04b_exposure_refinement'),
            (self.H.frozen,'REPO',self.repo),(self.H.frozen,'HERE',self.repo/'experiments/s04b_exposure_refinement')]:
            stack.enter_context(patch.object(target,key,value))
        return stack

    def saved_counters(self, report):
        counters={};calls=[];keys=[]
        def add(phase,model,order,context,n,gradient=True):
            if n:
                key=f'{phase}|{model}|{order}|{context}|{gradient}'
                value=counters.setdefault(key,dict(attempted=0,returned=0,errors=0))
                value['attempted']+=n;value['returned']+=n
        for model,fit in report['fits'].items():
            for row in fit['records']:
                method=row['method'];n=row['nfev'];keys.append([model,row['start_index'],method])
                add('train',model,8,'optimizer',n,method=='L-BFGS-B')
                options={key:self.science['solver'][key] for key in ('maxiter','maxls','ftol','gtol')} if method=='L-BFGS-B' else self.science['solver']['powell']
                calls += [dict(event='optimizer_start',model=model,start_index=row['start_index'],method=method,
                    initial_parameters=row['initial_parameters'],bounds=self.science['shared_bounds']+([] if model=='null' else self.science['inhibition_bounds']),
                    options=options,jac=method=='L-BFGS-B'),dict(event='optimizer_end',model=model,start_index=row['start_index'],method=method,
                    returned=True,callback_attempts=n,callback_returns=n,evaluation_census=copy.deepcopy(counters))]
        add('train','null',8,'original_support',1)
        for model,fit in report['fits'].items():
            add('train',model,8,'original_support',1+sum(r.get('finite_feasible') is True for r in fit['records'])+(1 if model in report['training_checks'] else 0))
            if model in report['training_checks']:add('train',model,16,'original_support',1)
        if report['passed']:
            for model in A.frozen.ARMS:add('test',model,8,'original_support',1);add('test',model,16,'original_support',1)
        phases=[dict(start=30,end=395,returned=True)]+([dict(start=395,end=760,returned=True)] if report['passed'] else [])
        return calls,dict(arm_calls=list(report['fits']),selected_check_calls=list(report['training_checks']),physical_optimizer_calls=keys,
            evaluation_census=counters,refinement_started=0,refinement_accepted=0,refinement_rejected=0,reuse_entries=[],
            phase_constructions=phases,callback_active=False,refinement_active=False)

    def child_artifacts(self, command, output, cap, admission, environment, spec_path, unknown=False):
        science=Path(command[command.index('--output')+1]);current=science.parent;name=command[command.index('--case-id')+1]
        report=copy.deepcopy(self.reports[name])
        if unknown:
            report=F.U.unknown_fixture()[1]
            report.update({key:self.reports[name][key] for key in ('case_id','regime','seed','input_sha256','stratum')})
        report.update(current_attempt_wall_seconds=2.,wall_seconds=2.,prior_training_attempt_seconds=0.)
        calls,receipt=self.saved_counters(report);science.mkdir();(science/'cases').mkdir()
        (science/'refinement_events.jsonl').write_bytes(b'')
        (science/'execution_calls.jsonl').write_bytes(''.join(json.dumps(row)+'\n' for row in calls).encode())
        reuse=dict(schema='joint_exposure_refinement_reuse_v1',mode='untouched',entries=[],original_failure_reference=None,
                   reused_optimizer_attempts=0,prior_failed_total_start4_attempts_retained=0)
        dump(science/'reuse_map.json',reuse)
        amendment=dict(version=A.frozen.VERSION,protocol_sha256=self.protocol_sha,original_scientific_protocol_sha256=self.science_sha,
            computation_kind='amended_untouched',reuse_map_sha256=A.sha(science/'reuse_map.json'),
            refinement_event_log_sha256=A.sha(science/'refinement_events.jsonl'),execution_calls_sha256=A.sha(science/'execution_calls.jsonl'),
            original_failure_reference=None)
        report['numerical_amendment']=amendment
        trace=F.trace_bytes(report);trace_path=science/'cases'/(name+'.attempts.jsonl');trace_path.write_bytes(trace)
        report_path=science/'cases'/(name+'.json');dump(report_path,report)
        grant=A.read(current/'admission.json');slot=next(s for s in self.policy['case_slots'] if s['case_id']==name)
        census=dict(attempted_models=list(report['fits']),completed_models=[m for m in report['fits'] if report['fits'][m]['passed']],
            not_run_models=list(A.frozen.ARMS[len(report['fits']):]),logical_optimizer_attempts=sum(len(x['records']) for x in report['fits'].values()),held_out_phase_constructed=not unknown)
        actual=dict(schema='joint_exposure_refinement_case_v1',case_id=name,handled=True,disposition_valid=True,status='terminal_disposition',
            scientific_completion=False,passed=not unknown,scientific_passed=not unknown,disposition='scientific_unknown' if unknown else 'complete',
            unknown_outcome_count=5 if unknown else 0,source_sha256=self.source_map,protocol_sha256=self.protocol_sha,
            runtime={'essential':self.native_meta['runtime_essential']},library_sha256=self.native_meta['library_sha256'],
            build_receipt_sha256=self.native_meta['build_receipt_sha256'],admission_sha256=A.sha(current/'admission.json'),allocation=slot,
            numerical_attempt_id=grant['numerical_attempt_id'],wall_seconds=3.,report_file='cases/'+report_path.name,report_sha256=A.sha(report_path),
            trace_file='cases/'+trace_path.name,trace_sha256=A.sha(trace_path),numerical_amendment=amendment,
            input_case=next(c for c in self.manifest if c['case_id']==name),phase_constructions=receipt['phase_constructions'],adapter=receipt,
            evaluation_census=receipt['evaluation_census'],refinement_census=dict(started=0,accepted=0,rejected=0),
            actual_optimizer_attempts=len(receipt['physical_optimizer_calls']),reused_optimizer_attempts=0,model_census=census)
        if unknown:
            model=list(report['fits'])[-1];arm=report['fits'][model]
            census.update(unresolved_model=model,unresolved_start=3,resolved_starts=arm['resolved_starts'],not_run_starts=arm['not_run_starts'])
            actual.update(terminal_solver_return=arm['records'][-1],unknown_reason=dict(error_type=report['error_type'],error=report['error'],arm_status=arm['status']))
        dump(science/'result.json',actual)
        # The numerical boundary emulates a retained Linux mount; argument
        # structure and the real producer's selected module/options stay intact.
        remote_command=[]
        for value in command:
            try:
                relative=Path(value).resolve().relative_to(self.artifact.resolve())
            except (ValueError,OSError):remote_command.append(value)
            else:remote_command.append('/invented/artifact/'+relative.as_posix())
        dump(spec_path,dict(command=remote_command,cwd='/invented/checkout',wall_cap_seconds=cap,rss_cap_bytes=6442450944,
             host_headroom_bytes=2147483648,env=environment))
        output.mkdir();(output/'execution.log').write_bytes(b'')
        dump(output/'result.json',dict(status='passed',returncode=0,launched=True,stop_reason=None,cleanup_errors=[],survivors_after_cleanup=[],
            spec_sha256=A.sha(spec_path),execution_log_sha256=A.sha(output/'execution.log'),supervisor_sha256=A.sha(self.repo/'scripts/supervise_research.py'),
            started_utc='2029-01-01T00:00:00+00:00',finished_utc='2029-01-01T00:00:04+00:00',execution_wall_seconds=3.2,
            wall_seconds_including_cleanup=3.3,sampled_peak_tree_rss_bytes=1024,minimum_sampled_host_available_bytes=9999999999))

    def run_host(self, unknown_position=1, technical_position=None, corrupt_index=None, batch=5, prior_overhead=None):
        self.artifact=self.root/('execution'+str(batch));self.artifact.mkdir();(self.artifact/'build').mkdir()
        library=self.artifact/'build/attenuation.so';library.write_bytes(self.native)
        build=self.artifact/'build/build_receipt.json';build.write_bytes(self.build_raw)
        group=self.op['hosts'][batch-5];names=group['case_ids'];token='invented-operational-lease'
        refs=dict(index=dict(path=self.sealed_rel,sha256=A.sha(self.prior)),review=dict(path=self.seal_review_rel,sha256=A.sha(self.prior_review)),
            raw_archive=self.op['base']['archive'],raw_review=self.op['base']['review'],raw_index_member='host/index.json',raw_index_sha256=self.op['base']['index_sha256'])
        conductor=dict(source_review=self.review_rel,source_review_sha256=self.review_sha,reviewed_files_sha256=self.graph)
        grant=dict(mode='exposure_refinement_host_batch',operational_mode='wall_failure_continuation',
            operational_continuation=dict(path=A.PROTOCOL,sha256=A.sha(self.repo/A.PROTOCOL)),batch_id=batch,case_ids=names,
            child_attempt_ids={name:'future-child-'+name for name in names},numerical_attempt_id='invented-host'+str(batch),
            source_sha256=self.host_map,scientific_source_sha256=self.source_map,protocol_sha256=self.protocol_sha,amendment_protocol_sha256=self.protocol_sha,
            host_batch_source_review_passed=True,checker_source_review_passed=True,shared_run=self.shared,expires_utc=self.shared['expires_utc'],
            rss_cap_bytes=6442450944,host_headroom_bytes=2147483648,lease_token_sha256=A.frozen.hash_bytes(token.encode()),
            library_sha256=self.native_meta['library_sha256'],build_receipt_sha256=self.native_meta['build_receipt_sha256'],
            prior_index_sha256=A.sha(self.prior),prior_review_sha256=A.sha(self.prior_review),
            prior_archive_sha256=self.op['base']['archive']['sha256'] if batch==5 else prior_overhead['archive']['sha256'],
            source_review_sha256=self.review_sha,checker_source_review_sha256=self.review_sha,reviewed_files_sha256=self.graph,
            conductor_review=conductor,source_commit=self.commit,host_started_utc=dt.datetime.now(dt.timezone.utc).isoformat(),
            execution_window_seconds=group['whole_host_upper_seconds']-600,
            sealed_predecessor=refs if batch==5 else None,prior_host_overhead=prior_overhead)
        dump(self.artifact/'admission.json',grant);self.grant=grant
        args=SimpleNamespace(output=self.artifact/'host',admission=self.artifact/'admission.json',prior_index=self.prior,prior_review=self.prior_review,
            config=self.config,source_review=self.repo/self.review_rel,checker_review=self.repo/self.review_rel,library=library,build_receipt=build,failed_prior=None)
        self.commands=[];self.audit_outputs=[]
        def boundary(command,output,cap,admission,environment,spec_path):
            self.commands.append(command)
            if command[3]=='experiments.s04b_exposure_refinement.case_driver':
                name=command[command.index('--case-id')+1];position=names.index(name)
                self.child_artifacts(command,output,cap,admission,environment,spec_path,unknown=position==unknown_position)
                if position==technical_position:
                    result_path=Path(command[command.index('--output')+1])/'result.json';actual=A.read(result_path)
                    actual.update(disposition='technical_failure',status='failed',passed=False,scientific_passed=False,handled=False,disposition_valid=False)
                    dump(result_path,actual)
                    raise ValueError('Invented future technical failure; no automatic continuation')
            else:
                if command[3]!=self.op['checker']['module']:raise AssertionError(command)
                current=Path(command[command.index('--current')+1])
                if corrupt_index is not None:corrupt_index(current)
                code=A.main(command[4:]);receipt=A.read(Path(command[command.index('--output')+1]));self.audit_outputs.append(receipt)
                if code:raise ValueError('Actual independent checker rejected: '+receipt.get('error',''))
        with self.patches(),patch.dict(os.environ,JOINT_NUMERICAL_LEASE_TOKEN=token),patch.object(self.H.generic,'supervised',side_effect=boundary):
            code=self.H.run(args)
        return code,A.read(args.output/'result.json'),args

    def publish_invented_host(self, args, overhead='17.25'):
        """Invented live authority for a real fixture host's retained index."""
        index=A.read(args.output/'index.json');execution=self.grant['numerical_attempt_id']
        archive_rel='validation/'+execution+'.zip';archive=self.repo/archive_rel
        with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED) as saved:
            saved.writestr('host/index.json',(args.output/'index.json').read_bytes())
        review_rel='validation/'+execution+'_review.json';review_path=self.repo/review_rel
        review=dict(passed=True,audit_passed=True,disposition_valid=True,scientific_completion=False,
            live_agent_review=True,live_agent_review_performed=True,final_batch_agent_review_required=False,
            review_kind='live_agent_saved_output_review',execution_id=execution,artifact_sha256=A.sha(archive),
            index_path='host/index.json',index_sha256=A.sha(args.output/'index.json'),counts=index['counts'],
            source_sha256=self.source_map,host_source_sha256=self.host_map,operational_continuation=A.operational_ref(self.repo),
            resource=dict(whole_workflow_overhead_beyond_all_child_outer_seconds=overhead))
        dump(review_path,review)
        self.prior=args.output/'index.json';self.prior_review=review_path
        return dict(execution_id=execution,seconds=overhead,review=dict(path=review_rel,sha256=A.sha(review_path)),
                    archive=dict(path=archive_rel,sha256=A.sha(archive)))

    def last_audit_args(self):
        command=self.commands[-1]
        assert command[3]==self.op['checker']['module']
        return SimpleNamespace(**{command[i][2:].replace('-','_'):command[i+1] for i in range(4,len(command),2)})


class OperationalCustody(unittest.TestCase):
    def test_real_seal_reconstructs_independently_without_changing_raw_zip(self):
        with tempfile.TemporaryDirectory() as temp:
            f=InventedOperationalCampaign(temp)
            with f.patches():
                op,p,science,host,sources,pins,review=A.load_contract(f.repo,f.repo/f.review_rel,f.review_sha)
                evidence=A.retained_failure(f.repo,op,p,sources)
                A.accounting_policy(op,evidence[-1],p)
                expected=A.sealed_expected(f.repo,op,*evidence,host)
                A.equal(f.sealed,expected,'Real seal must equal independent reconstruction')
            self.assertEqual(len(f.raw['records']),55)
            self.assertEqual(len(f.sealed['records']),56)
            self.assertEqual(f.sealed['records'][55]['disposition'],'wall_time_failure')
            self.assertEqual(f.sealed['records'][:55],f.raw['records'])

    def test_real_frozen_host_facade_to_independent_checker_complete_and_cap_unknown(self):
        with tempfile.TemporaryDirectory() as temp:
            f=InventedOperationalCampaign(temp)
            code,result,args=f.run_host()
            self.assertEqual(code,0,result)
            self.assertEqual(len(f.commands),10)
            self.assertEqual(len(f.audit_outputs),5)
            index=A.read(args.output/'index.json')
            self.assertEqual(index['records'][:56],f.sealed['records'])
            self.assertEqual(index['counts'],dict(processed_histories=61,complete_histories=58,unknown_histories=2,
                wall_time_failure_histories=1,unattempted_histories=19,computed_outcomes=290))
            self.assertFalse(f.audit_outputs[1]['scientific_passed'])
            self.assertEqual(len(f.audit_outputs[-1]['independent_disposition_census']),20)
            self.assertNotIn('independent_summary',f.audit_outputs[-1])
            self.assertTrue(all(not r['full_regime_eligible'] for r in f.audit_outputs[-1]['independent_disposition_census'] if r['regime']==6))

    def test_real_later_host_charges_one_genuine_prior_workflow_overhead(self):
        with tempfile.TemporaryDirectory() as temp:
            f=InventedOperationalCampaign(temp)
            code,result,args=f.run_host(unknown_position=None)
            self.assertEqual(code,0,result)
            overhead=f.publish_invented_host(args)
            prior=A.read(f.prior)
            code,result,args=f.run_host(batch=6,unknown_position=None,prior_overhead=overhead)
            self.assertEqual(code,0,result)
            index=A.read(args.output/'index.json')
            self.assertEqual(index['records'][:61],prior['records'])
            self.assertEqual(len(index['records']),69)
            self.assertEqual(index['audited_host_overheads'],[overhead])
            self.assertEqual(index['budget']['audited_future_host_overhead_seconds'],'17.25')
            self.assertEqual(index['budget']['unconsumed_host_overhead_reserve_seconds'],'14352.75')
            with f.patches():
                for change in (dict(seconds='0'),dict(execution_id='wrong-workflow')):
                    bad={**overhead,**change}
                    with self.subTest(change=change),self.assertRaises(ValueError):
                        A.inspect_overhead(f.repo,bad,f.op,f.host_map,f.op['hosts'][0])
                with self.assertRaisesRegex(ValueError,'another group'):
                    A.inspect_overhead(f.repo,overhead,f.op,f.host_map,f.op['hosts'][1])

    def test_repinned_transition_corruptions_rejected_by_actual_audit(self):
        with tempfile.TemporaryDirectory() as temp:
            f=InventedOperationalCampaign(temp)
            code,result,args=f.run_host()
            self.assertEqual(code,0,result)
            call=f.last_audit_args();current=Path(call.current)
            index_path=current/'index.json';grant_path=args.admission
            result_path=current/'science/result.json';conductor_path=current/'conductor_review.json'
            mutations=[
                ('wall relabel',index_path,lambda x:x['records'][55].update(disposition='scientific_unknown')),
                ('missing becomes zero',index_path,lambda x:x['records'][55].update(outcomes=[{'new_gain':0.}])),
                ('failure passed',index_path,lambda x:x['records'][55].update(scientific_passed=True)),
                ('old public producer',index_path,lambda x:x['records'][46]['execution_producer'].update(entrypoint='pretend-old-driver')),
                ('failed cost omitted',index_path,lambda x:x['attempts'][11].update(outer_seconds=0)),
                ('unknown outcome',index_path,lambda x:x['records'][57]['outcomes'].append({'new_gain':0.})),
                ('index success',index_path,lambda x:x.update(passed=True)),
                ('source map omission',index_path,lambda x:x['host_source_sha256'].pop(A.PROTOCOL)),
                ('duplicated charge',index_path,lambda x:x['audited_host_overheads'].append(dict(execution_id='invented-host04',seconds='10',review={},archive={}))),
                ('extra count',index_path,lambda x:x['counts'].update(complete_histories=59)),
                ('wrong fixed group',grant_path,lambda x:x.update(batch_id=6)),
                ('case roster reorder',grant_path,lambda x:x['case_ids'].reverse()),
                ('retry wall failure',result_path,lambda x:x.update(case_id=A.FAILURE)),
                ('retry permanent unknown',result_path,lambda x:x.update(case_id=A.frozen.UNKNOWN)),
                ('conductor omitted graph',conductor_path,lambda x:x['reviewed_files_sha256'].pop(A.PROTOCOL)),
            ]
            with f.patches():
                for label,path,mutate in mutations:
                    original=path.read_bytes();value=json.loads(original);mutate(value);dump(path,value)
                    try:
                        with self.subTest(label=label),self.assertRaises((ValueError,KeyError)):
                            if path==index_path and label!='unknown outcome':
                                # Exercise the actual prefix/accounting gate
                                # directly for these metadata-only mutations.
                                # The positive and rejection host controls
                                # already traverse the complete audit path.
                                A.inspect_index_prefix(A.read(path),f.sealed,f.op,f.host_map)
                            else:A.audit_saved(call)
                    finally:path.write_bytes(original)

    def test_seal_review_cannot_impersonate_raw_execution_even_if_repinned(self):
        with tempfile.TemporaryDirectory() as temp:
            f=InventedOperationalCampaign(temp)
            refs=dict(index=dict(path=f.sealed_rel,sha256=A.sha(f.prior)),
                review=dict(path=f.seal_review_rel,sha256=A.sha(f.prior_review)),raw_archive=f.op['base']['archive'],
                raw_review=f.op['base']['review'],raw_index_member='host/index.json',raw_index_sha256=f.op['base']['index_sha256'])
            original=f.prior_review.read_bytes()
            with f.patches():
                A.inspect_sealed_predecessor(f.repo,refs,f.sealed,json.loads(original),f.sealed,f.op)
                for mutate in (lambda x:x.update(execution_id='invented-host04'),
                               lambda x:x.update(scientific_execution_passed=True),
                               lambda x:x.update(review_kind='live_agent_saved_output_review'),
                               lambda x:x.update(live_agent_review=False),
                               lambda x:x.update(index_sha256=f.op['base']['index_sha256'])):
                    review=json.loads(original);mutate(review);dump(f.prior_review,review)
                    changed=copy.deepcopy(refs);changed['review']['sha256']=A.sha(f.prior_review)
                    with self.subTest(mutate=mutate),self.assertRaises(ValueError):
                        A.inspect_sealed_predecessor(f.repo,changed,f.sealed,review,f.sealed,f.op)
                f.prior_review.write_bytes(original)
                changed=copy.deepcopy(refs);changed['raw_archive']=changed['index']
                with self.assertRaisesRegex(ValueError,'Raw ZIP55'):
                    A.inspect_sealed_predecessor(f.repo,changed,f.sealed,json.loads(original),f.sealed,f.op)

    def test_shared_accounting_rejects_caps_duplicate_work_and_double_charges(self):
        with tempfile.TemporaryDirectory() as temp:
            f=InventedOperationalCampaign(temp)
            attempts=copy.deepcopy(f.sealed['attempts'])
            slot=f.op['case_slots'][0]
            attempts.append(dict(case_id=slot['case_id'],numerical_attempt_id='new',seconds=2490,outer_seconds=2520,
                                 actual_optimizer_attempts=32,reused_optimizer_attempts=0))
            actual=A.budget(f.op,attempts,[])
            self.assertEqual(actual['accounted_seconds'],'32520')
            for change in (dict(seconds=2490.001),dict(outer_seconds=2520.001),dict(reused_optimizer_attempts=1),
                           dict(numerical_attempt_id=attempts[0]['numerical_attempt_id'])):
                bad=copy.deepcopy(attempts);bad[-1].update(change)
                with self.subTest(change=change),self.assertRaises(ValueError):A.budget(f.op,bad,[])
            row=dict(execution_id='future-host',seconds='10',review={},archive={})
            for rows in ([row,row],[{**row,'execution_id':f.op['failure']['execution_id']}],[{**row,'seconds':'1800.001'}]):
                with self.subTest(rows=rows),self.assertRaises(ValueError):A.budget(f.op,attempts,rows)

    def test_repinned_source_review_must_include_actual_checker_host_and_supervisor(self):
        with tempfile.TemporaryDirectory() as temp:
            f=InventedOperationalCampaign(temp)
            path=f.repo/f.review_rel;original=path.read_bytes()
            with f.patches():
                for name in (A.CHECKER,A.PROTOCOL,'scripts/supervise_research.py',f.op['checker']['test']):
                    review=json.loads(original);review['reviewed_files_sha256'].pop(name);dump(path,review)
                    with self.subTest(name=name),self.assertRaisesRegex(ValueError,'source graph'):
                        A.load_contract(f.repo,path,A.sha(path))
                path.write_bytes(original)

    def test_future_technical_failure_stops_without_sealing_another_failure(self):
        with tempfile.TemporaryDirectory() as temp:
            f=InventedOperationalCampaign(temp)
            code,result,args=f.run_host(unknown_position=None,technical_position=1)
            self.assertEqual(code,1,result)
            self.assertEqual(len(f.commands),3)
            self.assertEqual(len(f.audit_outputs),1)
            index=A.read(args.output/'index.json')
            self.assertEqual(len(index['records']),57)
            self.assertEqual(index['counts']['wall_time_failure_histories'],1)
            self.assertFalse(result['passed'])

    def test_real_checker_rejection_stops_before_candidate_promotion(self):
        with tempfile.TemporaryDirectory() as temp:
            f=InventedOperationalCampaign(temp)
            def corrupt(current):
                path=current/'index.json';index=A.read(path)
                index['records'][46]['execution_producer']['retained_case']='substituted'
                dump(path,index)
            code,result,args=f.run_host(corrupt_index=corrupt)
            self.assertEqual(code,1,result)
            self.assertEqual(len(f.commands),2)
            self.assertFalse(f.audit_outputs[0]['audit_passed'])
            self.assertFalse((args.output/'index.json').exists())
            self.assertEqual(A.read(f.prior),f.sealed)
            self.assertIn('Old prefix',f.audit_outputs[0]['error'])


if __name__ == '__main__':
    unittest.main()
