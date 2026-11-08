"""Invented saved artifacts only; no numerical model/native/optimizer calls."""
import copy
from contextlib import ExitStack
import importlib.util
import json
import math
from pathlib import Path
import subprocess
import tempfile
import types
import unittest
from unittest import mock
import zipfile

ROOT = Path(__file__).resolve().parents[1]
def module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    value = importlib.util.module_from_spec(spec);spec.loader.exec_module(value);return value
A = module('refinement_independent_audit_tested', ROOT/'experiments/s04b_exposure_refinement_audit/check.py')
F = module('refinement_invented_math_fixture', ROOT/'tests/test_joint_output_audit.py')
U = module('refinement_invented_unknown_fixture', ROOT/'tests/test_joint_remaining_output_audit.py')


def dump(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, allow_nan=False)+'\n', encoding='utf-8')


def trace_bytes(report):
    rows = []
    for model in A.ARMS:
        for row in report['fits'].get(model, {}).get('records', []):
            rows += [dict(event='attempt_start', model=model, start_index=row['start_index'], method=row['method'],
                initial_parameters=row['initial_parameters'], status='running', success=False), dict(event='attempt_end', model=model, **row)]
    raw = ''.join(json.dumps(x)+'\n' for x in rows).encode()
    report['attempts_sha256'] = A.hash_bytes(raw)
    return raw


def science_fixture():
    p, report = F.fixture()
    p['solver'].update(maxls=200, ftol=1e-10, gtol=2e-6)
    p['solver']['powell'].update(ftol=1e-10, xtol=1e-6)
    return p, report


def event_fixture():
    p, r = science_fixture();theta=r['fits']['LIplus_inclusive']['candidates'][5]['parameters']
    def score(E):
        P=-10.;M=-1.;joint=P-E+M
        return dict(P=P,E=E,C=-E,M=M,joint=joint,nll=-joint)
    c, fine = score(-1e-8), score(1e-9)
    context=dict(phase='train',model='LIplus_inclusive',start_index=4,method='L-BFGS-B',callback_index=1,theta=theta)
    packet=dict(score=c,gradient=[0.]*8,theta=theta,model='LIplus_inclusive',order=8,
        error_type='ArithmeticError',error=A.TARGET_ERROR,origin=A.MODEL_PATH+':Phase.evaluate',origin_sha256=A.MODEL_SHA)
    comparison=dict(passed=True,finite=True,projected_coarse=[0.]*8,projected_fine=[0.]*8,
        absolute_joint_delta=abs(fine['joint']-c['joint']),projected_gradient_scaled_delta=0.,
        score_identities=True,same_P_M=True,fine_exposure_nonnegative=True,joint_tolerance=1e-4,gradient_tolerance=1e-4)
    return p,[dict(event='refinement_start',event_id=1,context=context,theta=theta,coarse=packet,coarse_seconds=.1),
              dict(event='refinement_end',event_id=1,context=context,theta=theta,fine=dict(score=fine,gradient=[0.]*8),
                   comparison=comparison,accepted=True,effective_order=16,coarse_seconds=.1,fine_seconds=.2)]


def partial_fixture(report):
    old = copy.deepcopy(report)
    old.update(case_id=A.PARTIAL,regime=6,seed=410603,passed=False,status='unknown',outcomes=[],
        error_type='ValueError',error='Unresolved alternative starts')
    for k in ('training_selections_frozen','new_null_test','test_checks','bic_threshold'):
        old.pop(k,None)
    old['training_checks'].pop('LIplus_inclusive')
    old['floor_checks']=[r for r in old['floor_checks'] if r['phase']=='train']
    total=old['fits']['LIplus_inclusive'];start=copy.deepcopy(total['records'][4])
    failures=[]
    for method in ('L-BFGS-B','Powell'):
        failures.append(dict(start_index=4,method=method,initial_parameters=start['initial_parameters'],status='exception',success=False,
            error_type='ArithmeticError',error=A.TARGET_ERROR,last_evaluation={},failed_evaluation_parameters=start['initial_parameters']))
    total.update(status='unknown_starts',passed=False,records=total['records'][:4]+failures,candidates=total['candidates'][:5],
                 resolved_starts=[True]*4+[False],not_run_starts=[5,6,7])
    for k in ('selected','selected_state_index','null_search_gaps'):total.pop(k)
    trace_bytes(old)
    return old


class RefinementSemantics(unittest.TestCase):
    def test_finite_pair_accepted(self):
        p,e=event_fixture();rows=A.inspect_refinements(e,p)
        self.assertEqual((len(rows),rows[0]['accepted'],rows[0]['fine_returned']),(1,True,True))

    def test_counterexamples_reject_independently_of_hashes(self):
        mutations=[lambda e:e[0]['context'].update(phase='test'),
            lambda e:e[0]['coarse'].update(origin_sha256='0'*64),
            lambda e:e[0]['coarse'].update(error='Finite objective has unrepresentable gradient'),
            lambda e:e[0]['coarse']['gradient'].__setitem__(0,True),
            lambda e:e[1].update(accepted=False),lambda e:e[1]['fine']['gradient'].__setitem__(0,1.),
            lambda e:e[1]['fine']['score'].update(P=-9.),lambda e:e[1].update(effective_order=8),
            lambda e:e[1]['context'].update(callback_index=0),lambda e:e.pop()]
        for mutate in mutations:
            p,e=event_fixture();mutate(e)
            with self.subTest(mutate=mutate),self.assertRaises((ValueError,KeyError)):A.inspect_refinements(e,p)

    def test_nonfinite_fine_is_explicit_rejection(self):
        p,e=event_fixture();e[1]['fine']['gradient'][0]={'nonfinite':'+inf'}
        e[1].update(accepted=False,comparison=dict(passed=False,finite=False))
        self.assertFalse(A.inspect_refinements(e,p)[0]['accepted'])
        e[1]['accepted']=True
        with self.assertRaises(ValueError):A.inspect_refinements(e,p)

    def test_original_guard_threshold_is_strict(self):
        p,e=event_fixture();c=e[0]['coarse']['score'];c['E']=-1e-9;c['C']=-c['E'];c['joint']=c['P']-c['E']+c['M'];c['nll']=-c['joint']
        with self.assertRaises(ValueError):A.inspect_refinements(e,p)

    def test_duplicate_callback_and_missing_pair_rejected(self):
        p,e=event_fixture();again=copy.deepcopy(e)
        for x in again:x['event_id']=2
        with self.assertRaises(ValueError):A.inspect_refinements(e+again,p)


class ReusedValues(unittest.TestCase):
    def test_partial_exact_prefix_and_new_four_starts(self):
        p,r=science_fixture();r.update(case_id=A.PARTIAL,regime=6,seed=410603)
        old=partial_fixture(r)
        physical=A.inspect_reused_values(r,old,'partial')
        self.assertEqual([x[1]['start_index'] for x in physical],[4,5,6,7])
        for mutation in (lambda x:x['fits']['null']['selected']['score'].update(joint=0),
                         lambda x:x['training_checks']['LI'].update(passed=False),
                         lambda x:x['fits']['LIplus_inclusive']['candidates'][2]['gradient'].__setitem__(0,1),
                         lambda x:x['fits']['LIplus_inclusive']['records'][4].update(start_index=3)):
            bad=copy.deepcopy(r);mutation(bad)
            with self.assertRaises(ValueError):A.inspect_reused_values(bad,old,'partial')

    def test_original_fresh_failure_is_counted_as_error_not_new_gate(self):
        p,r=science_fixture();records=[(m,x) for m in A.ARMS for x in r['fits'][m]['records']]
        counts={}
        def add(phase,model,order,n,errors=0):counts[f'{phase}|{model}|{order}|original_support|True']=dict(attempted=n,returned=n-errors,errors=errors)
        for model in A.ARMS:
            add('train',model,8,11 if model=='null' else 10);add('train',model,16,1)
            add('test',model,8,1);add('test',model,16,1)
        failed=copy.deepcopy(r['fits']['LI']['records'][0]);failed.update(status='exception',success=False,error_type='ArithmeticError',error=A.TARGET_ERROR)
        failed.pop('fresh_score')
        records.insert(8,('LI',failed))
        counts['train|LI|8|original_support|True'].update(attempted=11,errors=1)
        receipt=dict(evaluation_census=counts,arm_calls=list(A.ARMS),selected_check_calls=list(A.ARMS))
        A.inspect_support_counts(r,receipt,'untouched',records)
        receipt['evaluation_census']['train|LI|8|original_support|True'].update(returned=11,errors=0)
        with self.assertRaises(ValueError):A.inspect_support_counts(r,receipt,'untouched',records)



class InventedSavedCampaign:
    """An explicitly invented trust root; real audit functions are never mocked.

    Only fixed design/science *pin constants* are scoped to these invented bytes.
    Git, archive custody, arithmetic, CLI and every validation function run normally.
    """
    def __init__(self, directory):
        self.root=Path(directory);self.repo=self.root/'repo';self.repo.mkdir()
        self.science,self.template=science_fixture()
        self.sequence=json.loads((ROOT/'experiments/s04b_joint_remaining/protocol.json').read_text())['full_sequence']
        self.science['roster']=self.sequence
        self.design_dir=self.repo/A.DESIGN;self.design_dir.mkdir(parents=True)
        for rel in [*A.DEPENDENCIES,A.CHECKER_PATH,'experiments/s04b_exposure_refinement_audit/__init__.py',
                    A.MODEL_PATH,'experiments/s04b_joint_nuisance/attenuation.cpp','scripts/supervise_research.py']:
            target=self.repo/rel;target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes((ROOT/rel).read_bytes())
        dump(self.repo/A.SCIENCE_PATH,self.science);self.science_sha=A.sha(self.repo/A.SCIENCE_PATH)
        dump(self.repo/'experiments/s04b_joint_remaining/protocol.json',{'full_sequence':self.sequence})
        for rel in ('adapter.py','partial_fit.py','case_driver.py','host.py','__init__.py'):
            path=self.repo/'experiments/s04b_exposure_refinement'/rel;path.parent.mkdir(exist_ok=True)
            path.write_text('# Invented unexecuted producer identity for custody controls.\n')
        self.native=b'Invented native bytes; never loaded.'
        self.build=dict(passed=True,source_sha256=A.sha(self.repo/'experiments/s04b_joint_nuisance/attenuation.cpp'),library_sha256=A.hash_bytes(self.native))
        self.build_raw=(json.dumps(self.build,indent=2)+'\n').encode()
        self.native_meta=dict(library_sha256=A.hash_bytes(self.native),build_receipt_sha256=A.hash_bytes(self.build_raw),runtime_essential={'fixture':'not executed'})
        self.shared=dict(run_id='invented-shared-run',config_sha256='',expires_utc='2030-01-01T00:00:00+00:00')
        self.config=self.root/'config.json';dump(self.config,dict(run_id=self.shared['run_id'],deadline_utc=self.shared['expires_utc']))
        self.shared['config_sha256']=A.sha(self.config)
        self.members={};base_rows=[];refs=[]
        self.partial=partial_fixture(self.make_report(A.PARTIAL))
        for name in self.sequence[:44]:
            if name==A.UNKNOWN:
                _,r=U.unknown_fixture('LIplus_immigrant',5);r.update(case_id=name,regime=5,seed=410518)
                disposition='scientific_unknown'
            else:r=self.make_report(name);disposition='complete'
            case_member=f'saved/{name}.json';trace_member=f'saved/{name}.jsonl'
            tr=trace_bytes(r);raw=(json.dumps(r,indent=2)+'\n').encode();self.members[case_member]=raw;self.members[trace_member]=tr
            source=dict(kind='host_execution',execution_id='invented-original',case_path=case_member,case_sha256=A.hash_bytes(raw),trace_path=trace_member,trace_sha256=A.hash_bytes(tr))
            row=A.old.projection(r,disposition,source);base_rows.append(row)
            ref=dict(case_id=name,case_member=case_member,case_sha256=A.hash_bytes(raw),trace_member=trace_member,trace_sha256=A.hash_bytes(tr),paired_attempts=sum(len(a['records']) for a in r['fits'].values()),target_exception_count=0)
            if name==A.UNKNOWN:self.unknown_ref=ref
            else:refs.append(ref)
        self.partial_trace=trace_bytes(self.partial)
        self.members['partial/case.json']=(json.dumps(self.partial,indent=2)+'\n').encode();self.members['partial/trace.jsonl']=self.partial_trace
        self.members['partial/result.json']=b'{"wall_seconds":713.4644529529999}\n'
        self.members['partial/supervision.json']=b'{"wall_seconds_including_cleanup":713.9540351120002}\n'
        self.base=dict(schema='joint_remaining_index_v1',records=base_rows,attempts=[],counts=A.old.expected_counts(base_rows),scientific_completion=False,passed=False)
        self.base_raw=(json.dumps(self.base,indent=2)+'\n').encode();self.members['host/index.json']=self.base_raw
        archive_rel='validation/invented_original.zip';archive=self.repo/archive_rel;archive.parent.mkdir(exist_ok=True)
        with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED) as z:
            for name,value in self.members.items():z.writestr(name,value)
        archive_sha=A.sha(archive)
        review_rel='validation/invented_original_review.json';base_review=dict(passed=False,audit_passed=True,scientific_completion=False,
            live_agent_review=True,live_agent_review_performed=True,final_batch_agent_review_required=False,accepted_completed_prefix=True,artifact_sha256=archive_sha)
        dump(self.repo/review_rel,base_review)
        for ref in refs:ref.update(archive=archive_rel,archive_sha256=archive_sha)
        self.unknown_ref.update(archive=archive_rel,archive_sha256=archive_sha)
        failure=dict(archive=dict(path=archive_rel,sha256=archive_sha),review=dict(path=review_rel,sha256=A.sha(self.repo/review_rel)),
            case_member='partial/case.json',case_sha256=A.hash_bytes(self.members['partial/case.json']),trace_member='partial/trace.jsonl',trace_sha256=A.hash_bytes(self.partial_trace),
            driver_result_member='partial/result.json',driver_result_sha256=A.hash_bytes(self.members['partial/result.json']),
            supervision_member='partial/supervision.json',supervision_sha256=A.hash_bytes(self.members['partial/supervision.json']))
        slots=[dict(case_id=n,wall_seconds=1806 if n==A.PARTIAL else (1200 if n.startswith('S7') else 2520),scientific_seconds=1776 if n==A.PARTIAL else (1170 if n.startswith('S7') else 2490),mode='partial' if n==A.PARTIAL else 'untouched') for n in self.sequence[44:]]
        self.resources=dict(accounted_seconds='25139.78809128000155',costs_seconds={'invented_retained_cost':'25139.78809128000155'},
            future_host_overhead_seconds='14400',global_finalization_reserve_seconds='1800',partial_case_original_scientific_seconds='713.4644529529999',partial_case_original_outer_seconds='713.9540351120002',
            future_hosts=[dict(host=1,case_ids=[A.PARTIAL]),dict(host=2,case_ids=[self.sequence[45]])])
        # The rest of the future roster is reserved, but not executed in these controls.
        source_keys=[A.MODEL_PATH,A.SCIENCE_PATH,'experiments/s04b_joint_nuisance/attenuation.cpp']
        original_sources={k:A.sha(self.repo/k) for k in source_keys}
        refinement=dict(coarse_order=8,fine_order=16,coarse_exposure_guard_strictly_below=-1e-9)
        design=dict(refinement=refinement,reuse=dict(permanent_unknown=self.unknown_ref,complete_histories=refs),
            resume_current=dict(original_failure=failure),future=dict(case_ids=self.sequence[45:],case_slots=[{k:v for k,v in x.items() if k!='mode'} for x in slots[1:]]),
            unchanged=dict(native=self.native_meta,scientific_dependency_sha256=original_sources),resources=dict(shared_run=self.shared))
        dump(self.design_dir/'protocol_proposal.json',design)
        dump(self.design_dir/'independent_design_review.json',dict(passed=True,implementation_admitted=True,live_agent_review=True,live_agent_review_performed=True))
        dump(self.design_dir/'prior_failure_census.json',{'invented':True});dump(self.design_dir/'independent_reuse_census.json',{'invented':True})
        dump(self.design_dir/'resources.json',self.resources)
        self.design_pins={n:A.sha(self.design_dir/n) for n in A.DESIGN_PINS}
        checker_names=[A.CHECKER_PATH,'experiments/s04b_exposure_refinement_audit/__init__.py','experiments/s04b_joint_remaining_audit/check.py','experiments/s04b_joint_audit/check.py','experiments/s04b_joint_nuisance_audit/audit.py']
        self.policy=dict(schema='joint_exposure_refinement_protocol_v1',version=A.VERSION,scientific_completion=False,
            source_sha256=original_sources,original_scientific_protocol_sha256=self.science_sha,refinement=refinement,resources=self.resources,
            case_ids=self.sequence[44:],case_slots=slots,full_sequence=self.sequence,permanent_unknown=self.unknown_ref,failed_case=failure,
            original_native=self.native_meta,shared_run=self.shared,design_evidence_sha256={A.DESIGN+n:v for n,v in self.design_pins.items()},
            base=dict(archive=archive_rel,archive_sha256=archive_sha,review=review_rel,review_sha256=A.sha(self.repo/review_rel),index_member='host/index.json',index_sha256=A.hash_bytes(self.base_raw)),
            checker=dict(module='experiments.s04b_exposure_refinement_audit.check',sources=checker_names))
        dump(self.repo/A.PROTOCOL_PATH,self.policy)
        self.protocol_sha=A.sha(self.repo/A.PROTOCOL_PATH)
        self.source_map=dict(original_sources)
        for rel in ('adapter.py','partial_fit.py','case_driver.py','protocol.json','__init__.py'):
            key='experiments/s04b_exposure_refinement/'+rel;self.source_map[key]=A.sha(self.repo/key)
        self.host_map=dict(self.source_map,**{'experiments/s04b_exposure_refinement/host.py':A.sha(self.repo/'experiments/s04b_exposure_refinement/host.py')})
        self.checker_pins={k:A.sha(self.repo/k) for k in checker_names}
        self.graph={**self.host_map,**self.checker_pins,'scripts/supervise_research.py':A.sha(self.repo/'scripts/supervise_research.py')}
        self.manifest=[]
        self.report=self.make_report(A.PARTIAL);self.add_historical_inputs(self.report)
        self.unknown_report=U.unknown_fixture()[1];self.unknown_report.update(case_id=self.sequence[45],regime=6,seed=int(self.sequence[45].split('seed')[1]))
        self.add_historical_inputs(self.unknown_report)
        dump(self.repo/'reproduction/synthetic/input_manifest.json',{'s04b':{'cases':self.manifest}})
        for command in (['git','init'],['git','-c','core.autocrlf=false','add','.'],['git','-c','user.name=Invented fixture','-c','user.email=fixture@example.invalid','-c','commit.gpgsign=false','commit','-m','Invented checker custody fixture']):
            subprocess.run(command,cwd=self.repo,check=True,capture_output=True)
        self.commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=self.repo,text=True).strip()
        self.review_rel='validation/source_review.json'
        dump(self.repo/self.review_rel,dict(passed=True,live_agent_review=True,live_agent_review_performed=True,reviewed_files_sha256=self.graph))
        self.review_sha=A.sha(self.repo/self.review_rel)
        self.prior=self.root/'prior_index.json';self.prior.write_bytes(self.base_raw)
        self.prior_review=self.repo/review_rel

    def patches(self):
        stack=ExitStack();stack.enter_context(mock.patch.object(A,'DESIGN_PINS',self.design_pins));stack.enter_context(mock.patch.object(A,'SCIENCE_SHA',self.science_sha));return stack

    def make_report(self,name):
        r=copy.deepcopy(self.template);r.update(case_id=name,regime=int(name[1]),seed=int(name.split('seed')[1]))
        return r

    def add_historical_inputs(self,r):
        name=r['case_id'];root=self.repo/'reproduction/synthetic';prefix='invented/'+name
        case={k:r[k] for k in ('case_id','regime','seed','n_train','n_test')}
        case.update(history=prefix+'/history.npz',generator_receipt=prefix+'/generation.json',expected=prefix+'/expected.json',states=prefix+'/states.json',fits={m:prefix+'/'+m+'.json' for m in A.ARMS[1:]})
        history=root/case['history'];history.parent.mkdir(parents=True,exist_ok=True);history.write_bytes(b'Invented history identity; never opened by a model.')
        dump(root/case['generator_receipt'],{'counters':r['thinning']})
        states={m:[{'pars':{'floor':True}},{'pars':{'floor':False}}] for m in A.ARMS[1:]};dump(root/case['states'],states)
        for m,path in case['fits'].items():dump(root/path,{'floor':{'floor':True}})
        phases={'order16_train':{},'order32_test':{}}
        for m in A.ARMS[1:]:
            phases['order16_train'][m]=[[10.,0,0,0,0,F.score(-10.)['P']],[11.,0,0,0,0,0]]
            phases['order32_test'][m]=[[13.,0,0,0,0,F.score(-13.)['P']],[12.,0,0,0,0,0]]
        dump(root/case['expected'],dict(phase_values=phases,results=[dict(model=m,gate=g,selected_state_index=1,gain=1.) for m,g in A.core.OUTCOMES]))
        oldrel='validation/live_results/methodological_20261106/refitted_floor/'+name+'.json'
        old=dict(fixed_backbone=dict(a_historical=math.log(.2),d=.2,n=.35,c=.05,p=1.3),phases=dict(train=dict(historical=F.score(-10.)),test=dict(historical=F.score(-13.),refitted=F.score(-14.))),
            outcomes=[dict(model=m,gate=g,selected_state_index=1,original_gain=1.,new_gain=2.,saved_procedure_test_joint=-12.,original_floor_test_joint=-13.,original_off_floor=True) for m,g in A.core.OUTCOMES])
        dump(self.repo/oldrel,old)
        r['input_sha256']={**{case[k]:A.sha(root/case[k]) for k in ('history','generator_receipt','expected')},oldrel:A.sha(self.repo/oldrel)}
        r['stratum']='count-suppressed/weak-geometry' if r['regime'] in (5,7) else 'narrow-short'
        self.manifest.append(case)

    def build_child(self,unknown=False,prior=None,prior_review=None):
        report=copy.deepcopy(self.unknown_report if unknown else self.report);name=report['case_id'];mode='untouched' if unknown else 'partial';batch=2 if unknown else 1
        artifact=self.root/('new_host'+str(batch));current=artifact/'host/children/01_case';science=current/'science';science.mkdir(parents=True)
        (artifact/'build').mkdir();(artifact/'build/attenuation.so').write_bytes(self.native);(artifact/'build/build_receipt.json').write_bytes(self.build_raw)
        if not unknown:
            # The imported partial has the same exact fixture values; top-level inputs
            # are new receipt metadata, while all saved fits/checks remain unchanged.
            physical=A.inspect_reused_values(report,self.partial,mode)
        else:physical=A.inspect_reused_values(report,self.partial,mode)
        evals={};calls=[];reuse_entries=[];reuse_calls=[]
        def add(phase,model,order,context,n,gradient=True,errors=0):
            if not n:return
            key=f'{phase}|{model}|{order}|{context}|{gradient}';old=evals.setdefault(key,dict(attempted=0,returned=0,errors=0))
            old['attempted']+=n;old['returned']+=n-errors;old['errors']+=errors
        if not unknown:
            reuse_entries.append(dict(kind='historical_training_floor',pointer='/fits/null/candidates/0/score'));reuse_calls.append(dict(event='reuse_historical_training_floor',physical_evaluations=0))
            for m in A.ARMS[:3]:
                reuse_entries.extend([dict(kind='complete_arm',model=m,pointer='/fits/'+m),dict(kind='selected_training_check',model=m,pointer='/training_checks/'+m)])
                reuse_calls.extend([dict(event='reuse_arm',model=m,physical_optimizer_calls=0),dict(event='reuse_selected_training_check',model=m,physical_evaluations=0)])
            reuse_entries.append(dict(kind='total_prefix',model='LIplus_inclusive',candidate_indices=list(range(5)),record_indices=list(range(4)),prior_failed_record_indices=[4,5]))
            reuse_calls.append(dict(event='reuse_total_prefix',model='LIplus_inclusive',physical_optimizer_calls=0,candidate_indices=list(range(5)),record_indices=list(range(4))))
        calls.extend(reuse_calls)
        keys=[]
        for model,row in physical:
            method=row['method'];keys.append([model,row['start_index'],method]);n=row.get('nfev',1)
            add('train',model,8,'optimizer',n,method=='L-BFGS-B')
            options={k:self.science['solver'][k] for k in ('maxiter','maxls','ftol','gtol')} if method=='L-BFGS-B' else self.science['solver']['powell']
            calls += [dict(event='optimizer_start',model=model,start_index=row['start_index'],method=method,initial_parameters=row['initial_parameters'],bounds=self.science['shared_bounds']+([] if model=='null' else self.science['inhibition_bounds']),options=options,jac=method=='L-BFGS-B'),
                      dict(event='optimizer_end',model=model,start_index=row['start_index'],method=method,returned=True,callback_attempts=n,callback_returns=n,evaluation_census=copy.deepcopy(evals))]
        if unknown:add('train','null',8,'original_support',1)
        for model in report['fits']:
            if not unknown and model!='LIplus_inclusive':continue
            n=sum(row.get('finite_feasible') is True for m,row in physical if m==model)
            add('train',model,8,'original_support',n+(1 if unknown else 0)+(1 if model in report.get('training_checks',{}) else 0))
            if model in report.get('training_checks',{}):add('train',model,16,'original_support',1)
        if not unknown:
            for model in A.ARMS:add('test',model,8,'original_support',1);add('test',model,16,'original_support',1)
        phases=[dict(start=30,end=395,returned=True)]+([] if unknown else [dict(start=395,end=760,returned=True)])
        receipt=dict(arm_calls=list(report['fits']),selected_check_calls=list(report['training_checks']),physical_optimizer_calls=keys,evaluation_census=evals,
            refinement_started=0,refinement_accepted=0,refinement_rejected=0,reuse_entries=reuse_entries,phase_constructions=phases,callback_active=False,refinement_active=False)
        reuse=dict(schema='joint_exposure_refinement_reuse_v1',mode=mode,entries=reuse_entries,original_failure_reference=None if unknown else self.policy['failed_case'],reused_optimizer_attempts=0 if unknown else 28,prior_failed_total_start4_attempts_retained=0 if unknown else 2)
        dump(science/'reuse_map.json',reuse);(science/'refinement_events.jsonl').write_bytes(b'');(science/'execution_calls.jsonl').write_text(''.join(json.dumps(x)+'\n' for x in calls))
        amendment=dict(version=A.VERSION,protocol_sha256=self.protocol_sha,original_scientific_protocol_sha256=self.science_sha,computation_kind='amended_untouched' if unknown else 'amended_partial_resume',reuse_map_sha256=A.sha(science/'reuse_map.json'),refinement_event_log_sha256=A.sha(science/'refinement_events.jsonl'),execution_calls_sha256=A.sha(science/'execution_calls.jsonl'),original_failure_reference=reuse['original_failure_reference'])
        report.update(numerical_amendment=amendment,current_attempt_wall_seconds=2.,wall_seconds=2.,prior_training_attempt_seconds=0.)
        trace=trace_bytes(report);tracepath=science/'cases'/f'{name}.jsonl';tracepath.parent.mkdir();tracepath.write_bytes(trace);reportpath=science/'cases'/f'{name}.json';dump(reportpath,report)
        slot=self.policy['case_slots'][1 if unknown else 0];attempt='invented-case-'+str(batch);hostid='invented-host-'+str(batch)
        admission=dict(mode='exposure_refinement_case',case_id=name,case_ids=[name],source_sha256=self.source_map,protocol_sha256=self.protocol_sha,amendment_protocol_sha256=self.protocol_sha,independent_review_passed=True,external_supervision=True,wall_seconds=slot['wall_seconds'],scientific_seconds=slot['scientific_seconds'],threads=2,workers=1,sampled_process_tree_rss_cap_bytes=6442450944,minimum_host_free_bytes=2147483648,operational_run_id=self.shared['run_id'],operational_run_config_sha256=self.shared['config_sha256'],expires_utc=self.shared['expires_utc'],numerical_attempt_id=attempt,library_sha256=self.native_meta['library_sha256'],build_receipt_sha256=self.native_meta['build_receipt_sha256'])
        dump(current/'admission.json',admission)
        command=['python','-B','-m','experiments.s04b_exposure_refinement.case_driver','--mode',mode,'--case-id',name,'--output','/invented/host/children/01_case/science','--admission','/invented/host/children/01_case/admission.json','--library','/invented/build/attenuation.so','--build-receipt','/invented/build/build_receipt.json']
        if not unknown:command+=['--failed-prior','/invented/prior']
        spec=dict(command=command,wall_cap_seconds=slot['wall_seconds'],rss_cap_bytes=6442450944,host_headroom_bytes=2147483648,env={k:'2' for k in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','NUMEXPR_NUM_THREADS','BLIS_NUM_THREADS')});dump(current/'supervisor_spec.json',spec)
        (current/'supervision').mkdir();(current/'supervision/execution.log').write_bytes(b'')
        supervisor=dict(status='passed',returncode=0,launched=True,stop_reason=None,cleanup_errors=[],survivors_after_cleanup=[],spec_sha256=A.sha(current/'supervisor_spec.json'),execution_log_sha256=A.sha(current/'supervision/execution.log'),supervisor_sha256=A.sha(self.repo/'scripts/supervise_research.py'),started_utc='2029-01-01T00:00:00+00:00',finished_utc='2029-01-01T00:00:04+00:00',execution_wall_seconds=3.2,wall_seconds_including_cleanup=3.3,sampled_peak_tree_rss_bytes=1024,minimum_sampled_host_available_bytes=9999999999)
        dump(current/'supervision/result.json',supervisor)
        census=dict(attempted_models=list(report['fits']),completed_models=[m for m in report['fits'] if report['fits'][m]['passed']],not_run_models=list(A.ARMS[len(report['fits']):]),logical_optimizer_attempts=sum(len(x['records']) for x in report['fits'].values()),held_out_phase_constructed=not unknown)
        result=dict(schema='joint_exposure_refinement_case_v1',case_id=name,handled=True,disposition_valid=True,status='terminal_disposition',scientific_completion=False,passed=not unknown,scientific_passed=not unknown,disposition='scientific_unknown' if unknown else 'complete',unknown_outcome_count=5 if unknown else 0,
            source_sha256=self.source_map,protocol_sha256=self.protocol_sha,runtime={'essential':self.native_meta['runtime_essential']},library_sha256=self.native_meta['library_sha256'],build_receipt_sha256=self.native_meta['build_receipt_sha256'],admission_sha256=A.sha(current/'admission.json'),allocation=slot,numerical_attempt_id=attempt,wall_seconds=3.,report_file='cases/'+reportpath.name,report_sha256=A.sha(reportpath),trace_file='cases/'+tracepath.name,trace_sha256=A.sha(tracepath),numerical_amendment=amendment,input_case=next(c for c in self.manifest if c['case_id']==name),phase_constructions=phases,adapter=receipt,evaluation_census=evals,refinement_census=dict(started=0,accepted=0,rejected=0),actual_optimizer_attempts=len(physical),reused_optimizer_attempts=0 if unknown else 28,model_census=census)
        if unknown:
            model=list(report['fits'])[-1];arm=report['fits'][model];census.update(unresolved_model=model,unresolved_start=3,resolved_starts=arm['resolved_starts'],not_run_starts=arm['not_run_starts'])
            result.update(terminal_solver_return=arm['records'][-1],unknown_reason=dict(error_type=report['error_type'],error=report['error'],arm_status=arm['status']))
        dump(science/'result.json',result)
        prior_path=prior or self.prior;prior_review_path=prior_review or self.prior_review;previous=A.read(prior_path)
        grant=dict(mode='exposure_refinement_host_batch',batch_id=batch,case_ids=[name],numerical_attempt_id=hostid,child_attempt_ids={name:attempt},source_sha256=self.host_map,scientific_source_sha256=self.source_map,protocol_sha256=self.protocol_sha,prior_index_sha256=A.sha(prior_path),prior_review_sha256=A.sha(prior_review_path),prior_archive_sha256=self.policy['base']['archive_sha256'] if not unknown else '1'*64,shared_run=self.shared,expires_utc=self.shared['expires_utc'])
        dump(artifact/'admission.json',grant)
        dump(current/'conductor_review.json',dict(source_review=self.review_rel,source_review_sha256=self.review_sha,host_source_review_sha256=self.review_sha,reviewed_files_sha256=self.graph))
        source=dict(kind='host_execution',execution_id=hostid)
        for key,path in dict(case_path=reportpath,trace_path=tracepath,result_path=science/'result.json',supervision_path=current/'supervision/result.json').items():source[key]=path.relative_to(artifact/'host').as_posix();source[key.replace('_path','_sha256')]=A.sha(path)
        row=A.old.projection(report,result['disposition'],source);row.update(numerical_amendment=amendment,refinement_census=result['refinement_census'])
        if unknown:row.update(unknown_origin='new_frozen_solver_cap',unknown_reason=result['unknown_reason'],model_census=census,terminal_solver_return=result['terminal_solver_return'])
        attempts=[] if not unknown else previous['attempts'].copy();attempts.append(dict(case_id=name,numerical_attempt_id=attempt,host_execution_id=hostid,seconds=3.,outer_seconds=3.3,result_sha256=source['result_sha256'],supervision_sha256=source['supervision_sha256'],actual_optimizer_attempts=len(physical),reused_optimizer_attempts=0 if unknown else 28))
        index=dict(schema='joint_exposure_refinement_index_v1',protocol_sha256=self.protocol_sha,numerical_amendment_version=A.VERSION,original_scientific_protocol_sha256=self.science_sha,host_source_sha256=self.host_map,scientific_source_sha256=self.source_map,original_native=self.native_meta,immutable_failure_reference=self.unknown_ref,original_exposure_failure_reference=self.policy['failed_case'],compatible_saved_prefix=self.policy['base'],records=previous['records']+[row],attempts=attempts,predecessor=dict(index_sha256=A.sha(prior_path),review_sha256=A.sha(prior_review_path),archive_sha256=grant['prior_archive_sha256']),passed=False,scientific_completion=False)
        base=float(self.resources['accounted_seconds']);outer=math.fsum(a['outer_seconds'] for a in attempts);remaining=sum(s['wall_seconds'] for s in self.policy['case_slots'][len(attempts):]);upper=base+outer+remaining+14400+1800
        index['budget']=dict(base_accounted_seconds=base,amended_scientific_seconds=3.*len(attempts),amended_outer_seconds=outer,remaining_case_slots_seconds=remaining,all_eight_host_overhead_reserved_seconds=14400.,global_finalization_reserve_seconds=1800.,accounted_seconds=base+outer,upper_bound_seconds=upper,remaining_headroom_seconds=115200-upper)
        index['counts']=A.old.expected_counts(index['records']);dump(current/'index.json',index)
        return current,prior_path,prior_review_path

    def check(self,paths,output):
        current,prior,review=paths
        args=['--repo',str(self.repo),'--current',str(current),'--prior',str(prior),'--prior-review',str(review),'--config',str(self.config),'--commit',self.commit,'--output',str(output),'--checker-source-review',str(self.repo/self.review_rel),'--checker-source-review-sha256',self.review_sha]
        with self.patches():return A.main(args)

    def repin(self,current):
        """Keep artifact custody coherent so negative controls reach semantics."""
        science=current/'science';result=A.read(science/'result.json');reportpath=science/result['report_file'];report=A.read(reportpath)
        for key,name in {'reuse_map_sha256':'reuse_map.json','refinement_event_log_sha256':'refinement_events.jsonl','execution_calls_sha256':'execution_calls.jsonl'}.items():
            report['numerical_amendment'][key]=A.sha(science/name)
        dump(reportpath,report);result['report_sha256']=A.sha(reportpath);result['numerical_amendment']=report['numerical_amendment'];dump(science/'result.json',result)
        index=A.read(current/'index.json');row=index['records'][-1]
        row.update(numerical_amendment=result['numerical_amendment'],refinement_census=result['refinement_census'])
        for key,path in {'case_sha256':reportpath,'result_sha256':science/'result.json','supervision_sha256':current/'supervision/result.json'}.items():row['source'][key]=A.sha(path)
        index['attempts'][-1].update(result_sha256=row['source']['result_sha256'],supervision_sha256=row['source']['supervision_sha256'])
        dump(current/'index.json',index)

    def add_refinement(self,current):
        science=current/'science';_,events=event_fixture()
        (science/'refinement_events.jsonl').write_bytes(''.join(json.dumps(x)+'\n' for x in events).encode())
        result=A.read(science/'result.json');key='train|LIplus_inclusive|8|optimizer|True';fine='train|LIplus_inclusive|16|refinement_fine|True'
        def added(census):
            census[key]['errors']+=1;census[key]['returned']-=1
            census[fine]=dict(attempted=1,returned=1,errors=0)
        for census in (result['evaluation_census'],result['adapter']['evaluation_census']):added(census)
        result['adapter'].update(refinement_started=1,refinement_accepted=1)
        result['refinement_census'].update(started=1,accepted=1)
        dump(science/'result.json',result)
        calls=A.records((science/'execution_calls.jsonl').read_bytes())
        for call in calls:
            if call['event']=='optimizer_end':added(call['evaluation_census'])
        (science/'execution_calls.jsonl').write_bytes(''.join(json.dumps(x)+'\n' for x in calls).encode())
        self.repin(current)


class WholeSavedChecker(unittest.TestCase):
    def test_paired_refinement_then_repinned_out_of_context_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            fixture=InventedSavedCampaign(temp);paths=fixture.build_child();current=paths[0];fixture.add_refinement(current)
            review=Path(temp)/'accepted_refinement.json'
            self.assertEqual(fixture.check(paths,review),0,A.read(review))
            self.assertEqual(A.read(review)['refinement_and_reuse_census']['refinement_accepted'],1)
            eventpath=current/'science/refinement_events.jsonl';events=A.records(eventpath.read_bytes())
            for event in events:event['context']['phase']='test'
            eventpath.write_bytes(''.join(json.dumps(x)+'\n' for x in events).encode());fixture.repin(current)
            rejected=Path(temp)/'rejected_context.json';self.assertEqual(fixture.check(paths,rejected),1)
            self.assertIn('training optimizer callback',A.read(rejected)['error'])

    def test_preserved_prefix_cannot_be_relabelled(self):
        with tempfile.TemporaryDirectory() as temp:
            fixture=InventedSavedCampaign(temp);paths=fixture.build_child();current=paths[0]
            index=A.read(current/'index.json');index['records'][0]['scientific_passed']=False;dump(current/'index.json',index)
            rejected=Path(temp)/'rejected_prefix.json';self.assertEqual(fixture.check(paths,rejected),1)
            self.assertIn('Accepted prefix',A.read(rejected)['error'])

    def test_repinned_cleanup_time_exceeds_exact_partial_cap(self):
        with tempfile.TemporaryDirectory() as temp:
            fixture=InventedSavedCampaign(temp);paths=fixture.build_child();current=paths[0]
            path=current/'supervision/result.json';supervisor=A.read(path);supervisor['wall_seconds_including_cleanup']=1806.0001;dump(path,supervisor);fixture.repin(current)
            rejected=Path(temp)/'rejected_cap.json';self.assertEqual(fixture.check(paths,rejected),1)
            self.assertIn('resource cap',A.read(rejected)['error'])

    def test_complete_then_unknown_through_real_cli(self):
        with tempfile.TemporaryDirectory() as temp:
            fixture=InventedSavedCampaign(temp);first=fixture.build_child();review=Path(temp)/'first_review.json'
            self.assertEqual(fixture.check(first,review),0,A.read(review))
            saved=A.read(review);self.assertFalse(saved['live_agent_review']);self.assertFalse(saved['scientific_completion']);self.assertEqual(saved['refinement_and_reuse_census']['reused_optimizer_attempts'],28)
            saved.update(review_kind='live_agent_saved_output_review',live_agent_review=True,live_agent_review_performed=True,final_batch_agent_review_required=False,artifact_sha256='1'*64)
            live=Path(temp)/'invented_live_review.json';dump(live,saved)
            second=fixture.build_child(True,first[0]/'index.json',live);review2=Path(temp)/'second_review.json'
            self.assertEqual(fixture.check(second,review2),0,A.read(review2))
            final=A.read(review2);self.assertEqual(final['disposition'],'scientific_unknown');self.assertEqual(final['counts']['unknown_histories'],2)
            self.assertTrue(all(r['mean_gain'] is None for r in final['independent_summary'] if r['regime']==6))


if __name__=='__main__':unittest.main()
