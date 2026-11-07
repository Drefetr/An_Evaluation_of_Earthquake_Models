"""Independent saved-output check for the explicit interrupted-optimizer recovery.

Only JSON, file bytes and scalar arithmetic are read. No experiment implementation,
likelihood, optimizer, generator, native library or producer summary is imported.
The unchanged independent case auditor checks the logical scientific result. The
additional checks below retain the failed physical attempt and account for the
replayed returns and restarted invocation separately.
"""
from pathlib import Path
import argparse
import datetime as dt
import json
import math
import sys
import hashlib
import zipfile

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))
from experiments.s04b_joint_audit import check as custody
from experiments.s04b_joint_nuisance_audit import audit as core

CHECKER_PATH = 'experiments/s04b_joint_recovery_audit/check.py'
CUSTODY_PATH = 'experiments/s04b_joint_audit/check.py'
CORE_PATH = 'experiments/s04b_joint_nuisance_audit/audit.py'
CUSTODY_SHA256 = '839c67fd3dca65294b457cb6511a66c1800fa422712fc13e302e4f4495ddaa13'
CORE_SHA256 = '47e38c68ff613f5dae1ac80da3713f03a673dc1a31553bf2a8ca3a27773231c3'
RECOVERY_PATH = 'experiments/s04b_joint_recovery/recovery_protocol.json'
STARTUP_FILES = {'archive': 'startup_failure.zip', 'review': 'startup_failure_review.json',
                 'resource_review': 'startup_failure_resource.json', 'workflow_log': 'startup_failure_workflow.log'}
SUPPORT_FILES = {'archive': 'pilot02_support_failure.zip', 'review': 'pilot02_support_failure_review.json',
                 'resource_review': 'pilot02_support_failure_resource.json', 'workflow_log': 'pilot02_support_failure_workflow.log'}
DIAGNOSTIC_FILES = {'archive': 'support_diagnostic01.zip', 'review': 'support_diagnostic01_review.json',
                    'resource_review': 'support_diagnostic01_resource.json', 'workflow_log': 'support_diagnostic01_workflow.log'}
read, sha, safe, require, AuditError = custody.read, custody.sha, custody.safe, custody.require, custody.AuditError


def exact(a, b, message):
    require(json.dumps(a, sort_keys=True, separators=(',', ':'), allow_nan=False) ==
            json.dumps(b, sort_keys=True, separators=(',', ':'), allow_nan=False), message)


def integer(value):
    require(type(value) is int and value >= 0, 'Nonnegative integer required')
    return value


def numeric(value):
    require(type(value) in (int, float) and math.isfinite(value), 'Finite numeric comparison required')
    return value


def leaf_differences(actual, expected, path=''):
    """Independent scalar census, preserving exact serialized equality."""
    if json.dumps(actual, sort_keys=True, allow_nan=False) == json.dumps(expected, sort_keys=True, allow_nan=False):
        return []
    if isinstance(actual, dict) and isinstance(expected, dict):
        require(set(actual) == set(expected), 'Comparison object fields differ')
        return [row for key in sorted(actual) for row in
                leaf_differences(actual[key], expected[key], path+'/'+key.replace('~','~0').replace('/','~1'))]
    if isinstance(actual, list) and isinstance(expected, list):
        require(len(actual) == len(expected), 'Comparison array lengths differ')
        return [row for i,(a,b) in enumerate(zip(actual,expected)) for row in leaf_differences(a,b,path+'/'+str(i))]
    row=dict(path=path,kind='value',actual=actual,expected=expected)
    if type(actual) in (int,float) and type(expected) in (int,float):
        a,b=numeric(actual),numeric(expected)
        delta=a-b
        row.update(delta=delta if math.isfinite(delta) else None,
                   absolute_delta=abs(delta) if math.isfinite(delta) else None)
    return [row]


SCORE_KEYS = ('P','E','C','M','joint','nll')
SCORE_TOLERANCE = 1e-9


def score_tuple(value):
    require(isinstance(value,dict) and set(value)==set(SCORE_KEYS),'Score tuple fields differ')
    for key in SCORE_KEYS:numeric(value[key])
    require(value['E']>=-1e-9,'Original model exposure criterion failed')
    exact(value['C'],-value['E'],'Signed score exposure identity differs')
    exact(value['joint'],value['P']-value['E']+value['M'],'Score joint identity differs')
    exact(value['nll'],-value['joint'],'Score NLL identity differs')
    return value


def inspect_score_replay(actual,expected):
    score_tuple(actual);score_tuple(expected)
    differences={key:actual[key]-expected[key] for key in SCORE_KEYS}
    require(all(abs(v)<=SCORE_TOLERANCE for v in differences.values()),'Completed support score exceeds original1e-9 tolerance')
    return differences


def inspect_score_comparison(record,actual,expected):
    differences=inspect_score_replay(actual,expected)
    require(record['passed'] is True and record['tolerance']==SCORE_TOLERANCE,'Score comparison scope differs')
    wanted=[dict(field=k,actual=actual[k],expected=expected[k],delta=differences[k],
                 absolute_delta=abs(differences[k]),passed=True) for k in SCORE_KEYS]
    exact(record['components'],wanted,'Score difference census changed')
    exact(record['identities'],{label:dict(signed_exposure=True,joint=True,negative_joint=True,model_exposure=True)
          for label in ('actual','expected')},'Score identity census changed')


def vector(value,length):
    require(isinstance(value,list) and len(value)==length,'Gradient/state shape differs')
    for item in value:numeric(item)
    return value


def projected(theta,gradient,box):
    vector(theta,len(box));vector(gradient,len(box))
    return [0. if (x<=lo+1e-8 and g>0) or (x>=hi-1e-8 and g<0) else g
            for x,g,(lo,hi) in zip(theta,gradient,box)]


def selected_criteria(check,model,protocol,raw=None):
    dims=5 if model=='null' else 8
    score_tuple(check['coarse']);score_tuple(check['fine'])
    theta=vector(check['parameters'],8)
    coarse=vector(check['projected_gradient_coarse'],dims);fine=vector(check['projected_gradient_fine'],dims)
    delta=abs(check['coarse']['joint']-check['fine']['joint'])
    scaled=max(abs(x-y)/max(1.,abs(x),abs(y)) for x,y in zip(coarse,fine))
    kkt=max(map(abs,fine))
    exact(check['absolute_joint_delta'],delta,'Selected joint discrepancy was not independently derived')
    exact(check['projected_gradient_scaled_delta'],scaled,'Selected gradient discrepancy was not independently derived')
    exact(check['projected_kkt_infinity_norm'],kkt,'Selected KKT diagnostic was not independently derived')
    require(check['passed'] is True and check['fine']['E']>=0 and delta<=protocol['quadrature']['joint_absolute_tolerance'] and
            scaled<=protocol['quadrature']['selected_training_gradient_scaled_tolerance'],
            'Original selected-state scientific criterion failed')
    if model=='null':require(delta<=1e-9,'Original null functional criterion failed')
    if raw is not None:
        require(isinstance(raw,list) and len(raw)==2,'Exactly two existing raw selected-check evaluations required')
        box=protocol['shared_bounds']+([] if model=='null' else protocol['inhibition_bounds'])
        for row,order,key,pg in zip(raw,(8,16),('coarse','fine'),(coarse,fine)):
            require(row['model']==model and row['order']==order,'Selected raw evaluation identity differs')
            exact(row['parameters'],theta,'Selected raw parameters differ')
            exact(row['score'],check[key],'Selected raw score differs')
            gradient=vector(row['gradient'],8)
            exact(projected(theta[:dims],gradient[:dims],box),pg,'Fresh selected projection differs')
    result=dict(absolute_joint_delta=delta,projected_gradient_scaled_delta=scaled,
                projected_kkt_infinity_norm=kkt,passed=True,raw_gradient_available=raw is not None,
                derived_fields_exact=True,original_scientific_pass=True,null_functional_pass=True)
    if raw is not None:result['fresh_projections_exact']=True
    return result


def inspect_training_equivalence(record,original,model,raw,protocol):
    actual,expected=record['actual'],record['expected']
    exact(expected,original,'Original selected-check evidence changed')
    exact(record['differences'],leaf_differences(actual,expected),'Selected-check difference census changed')
    require(record['exact_match'] is (not record['differences']) and
            record['accepted_check_source']=='original_saved_check','Selected-check reuse attribution differs')
    mutable={'coarse','fine','absolute_joint_delta','projected_gradient_coarse','projected_gradient_fine',
             'projected_gradient_scaled_delta','projected_kkt_infinity_norm'}
    exact({k:v for k,v in actual.items() if k not in mutable},
          {k:v for k,v in expected.items() if k not in mutable},'Selected-check identity or status changed')
    for key in ('coarse','fine'):inspect_score_comparison(record['score_comparisons'][key],actual[key],expected[key])
    actual_criteria=selected_criteria(actual,model,protocol,raw)
    expected_criteria=selected_criteria(expected,model,protocol)
    exact(record['actual_criteria'],actual_criteria,'Fresh scientific criteria census differs')
    exact(record['expected_criteria'],expected_criteria,'Original scientific criteria census differs')
    require(record['passed'] is True,'Repeated selected check failed')
    return dict(actual=actual_criteria,expected=expected_criteria,
                original_raw_fine_gradient_available=False)


def inspect_replayed_support(record,original,box,start):
    token=record['token'];actual,expected=record['actual_evaluation'],record['expected_evaluation']
    require(isinstance(token['id'],str) and bool(token['id']) and token['model']=='LIplus_immigrant' and
            token['start_index']==start and token['order']==8 and token['require_gradient'] is True,
            'Completed-return token identity differs')
    exact(token['parameters'],original['parameters'],'Replay token state changed')
    wanted=dict(parameters=original['parameters'],score=original['fresh_score'],gradient=original['gradient'],
                projected_gradient=original['projected_gradient'])
    exact(expected,wanted,'Original completed-return support changed')
    exact(actual['parameters'],expected['parameters'],'Actual replay support parameters changed')
    inspect_score_comparison(record['score_comparison'],actual['score'],expected['score'])
    for payload in (actual,expected):
        vector(payload['gradient'],8)
        exact(projected(payload['parameters'],payload['gradient'],box),payload['projected_gradient'],'Completed-return projection differs')
    delta=abs(actual['score']['nll']-original['returned_nll'])
    require(delta<=1e-9,'Actual support fails original solver-return freshness criterion')
    exact(record['actual_returned_nll_delta'],delta,'Actual returned-NLL delta differs')
    require(record['passed'] is True and record['finite_gradients'] is True and record['saved_projection_exact'] is True and
            record['consumed_once'] is True and record['physical_optimizer_active'] is False and
            record['accepted_source']=='original_completed_return','Support substitution outside declared replay boundary')
    descriptive=record['gradient_differences']
    exact(descriptive['actual'],actual['gradient'],'Fresh gradient diagnostic differs')
    exact(descriptive['expected'],expected['gradient'],'Original gradient diagnostic differs')
    differences=leaf_differences(actual['gradient'],expected['gradient'])
    exact(descriptive['differences'],differences,'Gradient difference census differs')
    require(descriptive['exact_match'] is (not differences),'Gradient exact-match label differs')
    exact(record['canonical_return'],dict(score=expected['score'],gradient=expected['gradient']),
          'Candidate construction did not receive immutable completed values')
    return token['id']


def inspect_replayed_candidate(record,original,start,token_id):
    expected=dict(state_index=start+1,kind='optimizer',start_index=start,parameters=original['parameters'],
                  score=original['fresh_score'],gradient=original['gradient'])
    exact(record['expected'],expected,'Original completed candidate differs')
    exact(record['actual'],expected,'Original candidate was not preserved before selection')
    require(record['passed'] is True and record['exact_match'] is True and record['differences']==[] and
            record['accepted_candidate_source']=='original_completed_return_before_selection' and
            record['source_support_token_id']==token_id,
            'Candidate lost one-shot support lineage')
    return expected


def inspect_floor_replay(record,original,report):
    """A fresh floor is tested at its original tolerance, never overwritten."""
    expected=[r for r in original['floor_checks'] if r['phase']=='train']
    actual=[r for r in report['floor_checks'] if r['phase']=='train']
    require(len(actual)==len(expected)==3 and record['passed'] is True,'Historical training floor roster differs')
    exact(record['actual'],actual,'Fresh floor was not retained in the case')
    exact(record['expected'],expected,'Original floor reference changed')
    comparisons=[]
    for a,b in zip(actual,expected):
        exact({k:v for k,v in a.items() if k not in ('actual_nll','absolute_delta')},
              {k:v for k,v in b.items() if k not in ('actual_nll','absolute_delta')},'Historical floor identity changed')
        require(a['tolerance']==1e-9,'Historical floor tolerance changed')
        for row in (a,b):
            delta=abs(numeric(row['actual_nll'])-numeric(row['expected_nll']))
            exact(row['absolute_delta'],delta,'Historical floor discrepancy differs')
            require(delta<=1e-9,'Historical floor fails original tolerance')
        difference=a['actual_nll']-b['actual_nll']
        require(abs(difference)<=1e-9,'Repeated floor exceeds original replay tolerance')
        comparisons.append(dict(passed=True,actual_nll_difference=difference))
    exact(record['rows'],comparisons,'Floor replay census differs')


def inspect_return_context(ledger,execution,ends,box,report):
    arm='LIplus_immigrant';wanted=set(map(str,range(5)))
    require(set(execution['replayed_start_support'])==set(execution['replayed_candidates'])==wanted,
            'Replayed support/candidate census differs')
    pending=None;physical=False;created=[];supported=[];consumed=[];canonical=[]
    for event in ledger:
        kind=event['event']
        if kind=='physical_optimizer_start':
            require(not physical and pending is None,'Replay token overlaps physical optimization')
            physical=True
        elif kind=='physical_optimizer_end':
            require(physical and pending is None,'Unbalanced physical optimizer context')
            physical=False
        elif kind=='token_created':
            require(pending is None and not physical,'Overlapping replay token')
            token=event['token'];start=token['start_index']
            require(start==len(created) and start in range(5),'Duplicate or new-start replay token')
            pending=token;created.append(token['id'])
            exact(token,execution['replayed_start_support'][str(start)]['token'],'Created token differs from support')
        elif kind=='completed_return_support':
            require(pending is not None and not physical and pending['id'] not in supported,'Repeated or misplaced support return')
            start=pending['start_index'];payload={k:v for k,v in event.items() if k!='event'}
            exact(payload,execution['replayed_start_support'][str(start)],'Completed support ledger differs')
            exact(payload['token'],pending,'Completed support token changed')
            token_id=inspect_replayed_support(payload,ends[(arm,start,'L-BFGS-B')],box,start)
            supported.append(token_id)
        elif kind=='token_consumed':
            require(pending is not None and not physical and supported and supported[-1]==pending['id'],
                    'Token consumed before actual support or inside optimizer')
            exact(event['token'],pending,'Consumed token changed')
            exact(event['canonical_return'],execution['replayed_start_support'][str(pending['start_index'])]['canonical_return'],
                  'Candidate received changed canonical values')
            require(event['before_candidate_construction'] is True,'Canonical values supplied after candidate construction')
            consumed.append(pending['id']);pending=None
        elif kind=='canonical_completed_record':
            start=event['start_index'];require(not physical and pending is None and start==len(canonical) and len(consumed)==start+1,
                'Completed record lacks one-shot preselection support')
            require(event['model']==arm and event['exact_match'] is True and event['differences']==[],
                    'Canonical completed record changed')
            exact(event['actual'],ends[(arm,start,'L-BFGS-B')],'Canonical record actual differs')
            exact(event['expected'],ends[(arm,start,'L-BFGS-B')],'Canonical record expected differs')
            canonical.append(start)
    require(not physical and pending is None and execution['pending_return'] is None and
            created==supported==consumed and len(set(created))==len(created)==5 and canonical==list(range(5)),
            'Replay token consumption/canonicalization census differs')
    candidates=[v for v in ledger if v['event']=='replayed_candidate_preserved']
    require([v['start_index'] for v in candidates]==list(range(5)),'Preserved candidate census differs')
    for start,row in enumerate(candidates):
        require(row['model']==arm,'Replayed candidate model changed')
        payload={k:v for k,v in row.items() if k not in ('event','model','start_index')}
        exact(payload,execution['replayed_candidates'][str(start)],'Replayed candidate ledger differs')
        expected=inspect_replayed_candidate(payload,ends[(arm,start,'L-BFGS-B')],start,consumed[start])
        selected=[v for v in report['fits'][arm]['candidates'] if v['kind']=='optimizer' and v['start_index']==start]
        require(len(selected)==1,'Replayed candidate state missing/duplicated')
        exact(selected[0],expected,'Immutable completed candidate changed')
    selected=report['fits'][arm]['selected']
    all_candidates=report['fits'][arm]['candidates']
    require(selected in all_candidates,'Selected state missing from final candidates')
    exact(selected,min(all_candidates,key=lambda x:(x['score']['nll'],x['kind']=='optimizer',x['start_index'])),
          'Selection was changed after immutable candidate reuse')


def inspect_reference_snapshots(snapshots,ledger,interrupted,returned_count):
    require(set(snapshots)=={'return','next_input'},'Powell observation roster differs')
    for key,event_name,threshold,expected in (
        ('return','restart_return_reference',2040,{k:v for k,v in interrupted['last_evaluation'].items() if k!='evaluation_count'}),
        ('next_input','restart_next_input_reference',2041,interrupted['failed_evaluation_parameters'])):
        snapshot=snapshots[key];events=[v for v in ledger if v['event']==event_name]
        observed=returned_count>=threshold
        require(snapshot.get('observed') is observed and len(events)==int(observed),'Powell observation count differs')
        if not observed:
            exact(snapshot,{'observed':False},'Unreached Powell observation was fabricated')
            continue
        exact(snapshot,{k:v for k,v in events[0].items() if k!='event'},'Powell observation ledger differs')
        require(snapshot['scope']=='observational_only' and snapshot['reference_count']==threshold,
                'Powell comparison became an eligibility gate')
        exact(snapshot['expected'],expected,'Original Powell reference changed')
        actual=snapshot['actual']
        if key=='return':
            vector(actual['parameters'],8);score_tuple(actual['score'])
            if actual['gradient'] is not None:vector(actual['gradient'],8)
        else:vector(actual,8)
        differences=leaf_differences(actual,expected)
        exact(snapshot['differences'],differences,'Powell descriptive difference census differs')
        require(snapshot['exact_match'] is (not differences),'Powell exact-match label differs')


def inspect_support_policy(policy):
    p=policy['recovery']['support_equivalence']
    require(p['schema']=='joint_original_contract_recovery_v2' and p['score_absolute_tolerance']==1e-9,
            'Unreviewed recovery replay tolerance')
    exact(p['score_fields'],list(SCORE_KEYS),'Replay score fields differ')
    exact(p['score_identities'],['C=-E','joint=P-E+M','nll=-joint'],'Replay identities differ')
    exact(p['completed_return_support'],dict(model='LIplus_immigrant',starts=list(range(5)),one_shot_token=True,
        exact_model_start_parameters=True,order=8,require_gradient=True,actual_support_recorded_before_reuse=True,
        original_returned_nll_freshness_required=True,canonical_saved_score_and_gradient_before_candidate_construction=True,
        forbidden_in_actual_optimizer_or_new_start=True),'Replay boundary policy differs')
    exact(p['reused_selected_checks'],dict(models=['null','LI'],capture_existing_raw_coarse_fine_evaluations=True,
        independently_rederive_original_scientific_criteria=True,actual_and_original_must_pass=True,
        return_original_saved_check_after_validation=True,original_fine_raw_gradient_not_archived=True),
        'Selected-state replay policy differs')
    exact(p['historical_floor'],dict(retain_fresh_actual_nll_and_discrepancy=True,
        original_absolute_tolerance=1e-9,identifiers_expected_values_exact=True),'Historical floor replay policy differs')
    exact(p['powell_reference_snapshots'],dict(observational_only=True,record_if_naturally_reached=True,
        not_reached_allowed=True,no_forced_evaluations=True,initial_bounds_options_caps_unchanged=True),
        'Powell restart observation policy differs')


def source_review(repo, path, pin):
    require(sha(path) == pin, 'Checker review bytes changed')
    review = read(path)
    require(review.get('passed') is True, 'Checker source review failed')
    pins = {CHECKER_PATH: sha(__file__), CUSTODY_PATH: CUSTODY_SHA256, CORE_PATH: CORE_SHA256}
    for relative, expected in pins.items():
        require(sha(safe(repo, relative)) == expected == review['reviewed_files_sha256'].get(relative),
                'Unreviewed checker dependency: ' + relative)
    return review, pins


def validate_review(review, index_pin, checker_pins, source_review_pin, *, pilot=False):
    require(review.get('passed') is True and review.get('index_sha256') == index_pin,
            'Prior review does not accept exact index')
    if review.get('review_kind') == 'automated_saved_output_check':
        require(not pilot, 'Standalone recovery pilot needs live independent review')
        require(review.get('live_agent_review') is False and review.get('live_agent_review_performed') is False
                and review.get('final_batch_agent_review_required') is True, 'Automated review attribution')
        require(review.get('checker_sources_sha256') == checker_pins and
                review.get('checker_source_review_sha256') == source_review_pin, 'Prior checker identity')
    else:
        require(review.get('reviewer') == '/root/continuation_cpu' and
                review.get('review_kind') == 'live_agent_saved_output_review' and
                review.get('live_agent_review') is True and
                not review.get('final_batch_agent_review_required', False), 'Genuine independent live review required')


def preserved_prefix(index, old, current, prior):
    require(index['cases'][:-1] == old['cases'] and index['attempts'][:-1] == old['attempts'],
            'Case or charged-attempt prefix changed')
    require(index['reviews'][:-1] == old['reviews'], 'Review prefix changed')
    for entry in old['cases']:
        for key in ('file', 'trace'):
            require(safe(current, entry[key]).read_bytes() == safe(prior, entry[key]).read_bytes(),
                    'Prior case/trace bytes changed')
    for entries in (old['attempts'], old['reviews']):
        for entry in entries:
            require(safe(current, entry['file']).read_bytes() == safe(prior, entry['file']).read_bytes(),
                    'Prior attempt/review bytes changed')
    for name in ('transition', 'training_resume', 'recovery_lineage'):
        directory = prior / name
        if directory.is_dir():
            for path in directory.rglob('*'):
                if path.is_file():
                    require(safe(current, path.relative_to(prior)).read_bytes() == path.read_bytes(),
                            'Carried lineage bytes changed')
    for relative, pin in old.get('recovery_execution_files', {}).items():
        require(sha(safe(current, relative)) == sha(safe(prior, relative)) == pin,
                'Prior physical recovery evidence changed')


def inspect_lineage(index, science, policy):
    p, transition = policy['predecessor'], index['recovery_transition']
    expected = {'recovery_lineage/failed_index.json': p['index_sha256'],
                'recovery_lineage/failed_case.json': p['case_sha256'],
                'recovery_lineage/failed_trace.jsonl': p['trace_sha256'],
                'recovery_lineage/failed_review.json': p['review_sha256'],
                'recovery_lineage/failed_result.json': p['result_sha256'],
                'recovery_lineage/failed_supervision.json': p['supervision_sha256'],
                'recovery_lineage/failed_admission.json': p['admission_sha256'],
                'recovery_lineage/failed_host.zip': p['archive_sha256']}
    for row,names in operational_rows(policy):
        expected.update({'recovery_lineage/'+filename:row[key+'_sha256'] for key,filename in names.items()})
    require(transition['schema'] == 'joint_interrupted_optimizer_transition_v1' and
            transition['original_status'] == 'failed' and transition['files'] == expected,
            'Failed transition identity or evidence roster changed')
    require(transition['original_index_sha256'] == p['index_sha256'] and
            transition['protocol_sha256'] == index['recovery_protocol_sha256'] and
            transition['known_outer_overhead_seconds'] == p['known_outer_overhead_seconds'],
            'Recovery transition pins changed')
    for relative, pin in expected.items():
        require(sha(safe(science, relative)) == pin, 'Failed evidence bytes changed: ' + relative)
    inspect_startup_failure(index, science, policy)
    inspect_operational_lists(index,science,policy)
    failed = read(science / 'recovery_lineage/failed_index.json')
    disposition = read(science / 'recovery_lineage/failed_review.json')
    result = read(science / 'recovery_lineage/failed_result.json')
    require(disposition.get('passed') is False and disposition.get('audit_passed') is True and
            disposition.get('live_agent_review') is True and disposition['failed_index']['sha256'] == p['index_sha256'],
            'Failed attempt was relabelled as accepted')
    require(failed['last_attempt_passed'] is False and result['passed'] is False and
            len(failed['cases']) == 40 and len(failed['attempts']) == 41,
            'Original failed-prefix scope differs')
    require(index['cases'][:40] == failed['cases'] and index['attempts'][:41] == failed['attempts'] and
            index['reviews'][:len(failed['reviews'])] == failed['reviews'], 'Frozen failed prefix changed')
    require(failed['source_sha256'] == policy['predecessor_source_sha256'] and
            failed['budget']['total_seconds'] == p['original_index_charged_seconds'],
            'Original source/time charge differs')
    # The earlier training-only recovery remains a different, intact failure.
    original = index['original_failure']
    require(original == failed['original_failure'], 'Original training failure changed')
    require(index['transition'] == failed['transition'], 'Earlier allocation transition changed')
    for relative, pin in index['transition']['files'].items():
        require(sha(safe(science, relative)) == pin, 'Earlier allocation evidence changed')
    return failed


def inspect_startup_failure(index, science, policy):
    """Retain the failed startup separately; its nested time is not a fit attempt."""
    startup = policy['pre_execution_failure']
    require(startup['status'] == 'failed_before_scientific_evaluation' and
            startup['scientific_predecessor_unchanged'] is True and
            type(startup['charge_seconds']) is int and startup['charge_seconds'] == 90,
            'Startup failure status or single charge changed')
    exact(index['pre_execution_failure'], startup, 'Index startup failure changed')
    exact(index['recovery_transition']['pre_execution_failure'], startup, 'Transition startup failure changed')
    for key, filename in STARTUP_FILES.items():
        require(sha(science / 'recovery_lineage' / filename) == startup[key + '_sha256'],
                'Startup failure evidence bytes changed: ' + key)
    review = read(science / 'recovery_lineage/startup_failure_review.json')
    resource = read(science / 'recovery_lineage/startup_failure_resource.json')
    require(review.get('passed') is False and review.get('audit_passed') is True and
            review.get('live_agent_review') is True and review.get('reviewer') == '/root/continuation_cpu' and
            review.get('overall_scientific_passed') is False and
            review['archive_sha256'] == startup['archive_sha256'], 'Startup failure relabelled or unreviewed')
    census = review['execution_census']
    require(all(census[key] == 0 for key in ('new_completed_cases', 'new_full_likelihood_evaluations',
                                           'new_optimizer_invocations', 'new_optimizer_trace_records')),
            'Startup failure zero-call scope changed')
    require(resource.get('passed') is True and resource['failure']['passed'] is False and
            resource['failure']['archive_sha256'] == startup['archive_sha256'] and
            resource['amendment']['explicit_new_charge_bound_seconds'] == 90 and
            resource['amendment']['shared_allowance_seconds'] == 115200 and
            resource['amendment']['automatic_retry'] is False,
            'Startup resource disposition changed')
    require(resource['independent_failure_audit']['sha256'] == startup['review_sha256'] and
            resource['inputs_sha256']['joint_recovery_host_01_workflow.log'] == startup['workflow_log_sha256'],
            'Startup review/log linkage changed')
    require(resource['observed_timing']['child_scientific_seconds'] == startup['nested_scientific_seconds'] and
            resource['observed_timing']['outer_supervised_seconds'] == startup['nested_supervised_seconds'] and
            resource['observed_timing']['timings_nested'] is True, 'Startup nested timing changed')
    require(resource['failure']['failed_attempt_id'] not in {v['attempt_id'] for v in index['attempts']},
            'Startup child duration charged again as scientific attempt')


def operational_rows(policy):
    failures,diagnostics=policy['operational_failures'],policy['operational_diagnostics']
    require(isinstance(failures,list) and failures and isinstance(diagnostics,list),'Operational launch lists missing')
    exact(failures[0],policy['pre_execution_failure'],'Historical failed-launch alias changed')
    rows=failures+diagnostics;identities=[row['archive_sha256'] for row in rows]
    require(len(set(identities))==len(identities),'Duplicate operational launch archive')
    mapping=policy['operational_lineage_files']
    require(set(mapping)==set(identities),'Operational lineage mapping omitted or added launch')
    filenames=[];result=[]
    for row in rows:
        names=mapping[row['archive_sha256']]
        require(set(names)=={'archive','review','resource_review','workflow_log'},'Operational evidence roster differs')
        for name in names.values():
            require(isinstance(name,str) and name not in ('','.','..') and '/' not in name and chr(92) not in name,
                    'Unsafe operational evidence basename')
            filenames.append(name)
        require(type(row['charge_seconds']) is int and row['charge_seconds']>0 and
                row['scientific_predecessor_unchanged'] is True,'Invalid operational launch charge/scope')
        require(0<=numeric(row['nested_scientific_seconds'])<=numeric(row['nested_supervised_seconds'])<=row['charge_seconds'],
                'Nested operational durations exceed single launch charge')
        result.append((row,names))
    require(len(set(filenames))==len(filenames),'Duplicate operational evidence destination')
    exact(mapping[failures[0]['archive_sha256']],STARTUP_FILES,'Original startup evidence names changed')
    return result


def inspect_operational_accounting(index,policy,total):
    rows=operational_rows(policy)
    failure_charge=math.fsum(row['charge_seconds'] for row in policy['operational_failures'])
    diagnostic_charge=math.fsum(row['charge_seconds'] for row in policy['operational_diagnostics'])
    overhead=policy['predecessor']['known_outer_overhead_seconds']
    expected=dict(scientific_indexed_seconds=total,known_prior_outer_overhead_seconds=overhead,
                  operational_failure_charge_seconds=failure_charge,operational_diagnostic_charge_seconds=diagnostic_charge,
                  accounted_seconds=math.fsum([total,overhead,failure_charge,diagnostic_charge]))
    require(set(index['operational_accounting'])==set(expected),'Operational accounting fields differ')
    for key,value in expected.items():core.close(index['operational_accounting'][key],value,'Operational accounting '+key,1e-8)
    require(expected['accounted_seconds']<=115200,'Global operational envelope exceeded')
    return expected


def inspect_operational_lists(index,science,policy):
    rows=operational_rows(policy)
    for key in ('operational_failures','operational_diagnostics'):
        exact(index[key],policy[key],'Index operational launch list changed')
        exact(index['recovery_transition'][key],policy[key],'Transition operational launch list changed')
    for row,names in rows[1:]:
        for key,filename in names.items():
            require(sha(science/'recovery_lineage'/filename)==row[key+'_sha256'],'Operational evidence bytes changed')
        review=read(science/'recovery_lineage'/names['review'])
        resource=read(science/'recovery_lineage'/names['resource_review'])
        require(review['archive_sha256']==row['archive_sha256'] and review['audit_passed'] is True and
                review['live_agent_review'] is True and review['reviewer']=='/root/continuation_cpu' and resource['passed'] is True,
                'Operational launch review linkage differs')
        timing=resource['timing']
        require(timing['conservative_whole_launch_charge_seconds']==row['charge_seconds'],
                'Operational charge differs from reviewed whole launch')
        if row in policy['operational_failures']:
            failure=resource['failure']
            review_pin=(resource['independent_failure_audit']['sha256'] if 'independent_failure_audit' in resource
                        else failure['independent_review_sha256'])
            require(row['status']==resource['failure']['status'] and review['passed'] is False and
                    review['overall_scientific_passed'] is False and review['accepted_completed_prefix']['count']==40 and
                    resource['failure']['passed'] is False and resource['failure']['archive_sha256']==row['archive_sha256'] and
                    review_pin==row['review_sha256'],'Failed launch relabelled')
            census=review['execution_census']
            for key,review_key in [('support_evaluation_count','new_training_support_evaluations'),
                ('optimizer_call_count','new_optimizer_invocations'),('physical_optimizer_call_count','new_optimizer_invocations'),
                ('replayed_optimizer_return_count','replayed_immigrant_optimizer_returns'),('held_out_call_count','new_test_evaluations')]:
                if key in row:
                    integer(row[key]);require(row[key]==failure[key]==census[review_key],'Failed launch evaluation census differs')
            if 'failed_attempt_id' in failure:
                failed_attempt=failure['failed_attempt_id']
            else:
                descriptor=review['failed_index']
                with zipfile.ZipFile(science/'recovery_lineage'/names['archive']) as archive:
                    require(archive.namelist().count(descriptor['path'])==1,'Failed index archive member missing/duplicated')
                    raw=archive.read(descriptor['path'])
                require(hashlib.sha256(raw).hexdigest()==descriptor['sha256']==failure['failed_index_sha256'],
                        'Failed launch index custody differs')
                failed_index=json.loads(raw)
                require(failed_index['last_attempt_passed'] is False and len(failed_index['cases'])==40,
                        'Operational failure archive claims new accepted case')
                failed_attempt=failed_index['attempts'][-1]['attempt_id']
            require(failed_attempt not in {v['attempt_id'] for v in index['attempts']},
                    'Nested failed launch charged again as scientific attempt')
        else:
            require(row['status']=='diagnostic_complete' and row['passed'] is True and row['equality_passed'] is False and
                    row['scientific_completion'] is False,'Diagnostic accounting scope differs')
            require(review['passed'] is True and review['diagnostic_complete'] is True and review['equality_passed'] is False and
                    review['accepted_recovery_case'] is False and review['scientific_completion'] is False,
                    'Diagnostic relabelled as recovered case')
            census=review['execution']
            require(row['support_evaluation_count']==census['actual_training_evaluations'] and
                    row['optimizer_call_count']==census['optimizer_calls']==0 and
                    row['held_out_call_count']==census['held_out_calls']==0 and census['new_complete_cases']==0,
                    'Diagnostic evaluation scope differs')
            require(resource['diagnostic']['archive_sha256']==row['archive_sha256'] and
                    resource['diagnostic']['independent_review_sha256']==row['review_sha256'],'Diagnostic resource linkage differs')
        require(timing['child_scientific_seconds']==row['nested_scientific_seconds'] and
                timing['outer_including_cleanup_seconds']==row['nested_supervised_seconds'] and
                timing['nested_intervals_not_additive'] is True,'Nested operational timing linkage differs')
        require(row['workflow_log_sha256'] in resource['input_sha256'].values(),'Operational log lacks resource binding')


def inspect_charges(index, science, policy):
    p = policy['predecessor']
    entries = index['attempts']
    require(len(entries) == 41 + len(index['cases']) - 40, 'Recovery attempts/case count differs')
    require(len({v['attempt_id'] for v in entries}) == len(entries), 'Duplicate attempt charge')
    for position, entry in enumerate(entries):
        require(sha(safe(science, entry['file'])) == entry['sha256'], 'Attempt receipt changed')
        receipt = read(safe(science, entry['file']))
        require(receipt['attempt_id'] == entry['attempt_id'] and receipt['phase'] == entry['phase'] and
                receipt['wall_seconds'] == entry['seconds'] and math.isfinite(entry['seconds']) and entry['seconds'] >= 0,
                'Invalid charged attempt')
        if position == 40:
            require(receipt['passed'] is False and receipt['partial_case'] is not None,
                    'Original interrupted attempt disappeared')
        else:
            require(receipt['passed'] is True and receipt['status'] == 'batch_complete' and
                    receipt['partial_case'] is None, 'Unaccepted additional failed attempt')
        if position >= 41:
            slot = policy['fixed_slots'][position - 41]
            require(receipt['case_ids'] == [slot['case_id']] and receipt['phase'] == 'campaign' and
                    receipt['wall_seconds'] <= slot['wall_seconds'], 'Recovery slot/case/cap differs')
            require(receipt['source_sha256'] == index['source_sha256'] and
                    receipt['recovery_protocol_sha256'] == index['recovery_protocol_sha256'],
                    'Recovery charged source differs')
    total = math.fsum([index['original_failure']['prior_scientific_seconds'], *[v['seconds'] for v in entries]])
    pilot = math.fsum([index['original_failure']['prior_scientific_seconds'],
                      *[v['seconds'] for v in entries if v['phase'] == 'pilot']])
    core.close(total, index['budget']['total_seconds'], 'Total charge', 1e-8)
    core.close(pilot, index['budget']['pilot_seconds'], 'Original pilot charge', 1e-8)
    operational = inspect_operational_accounting(index, policy, total)
    before = total - entries[-1]['seconds']
    remaining = sum(v['wall_seconds'] for v in policy['fixed_slots'][len(index['cases']) - 41:])
    bound = before + p['known_outer_overhead_seconds'] + operational['operational_failure_charge_seconds'] + operational['operational_diagnostic_charge_seconds'] + remaining + 8*1800 + 1800
    require(bound <= 115200 and total <= 115200, 'Global recovery envelope exceeded')
    return {'total_seconds': total, 'pilot_seconds': pilot,
            'original_failed_attempt_seconds': entries[40]['seconds'],
            'known_outer_overhead_seconds': p['known_outer_overhead_seconds'],
            'operational_accounting': operational,
            'conservative_remaining_admission_bound_seconds': bound,
            'past_unmeasured_workflow_overhead': 'unknown, not asserted zero'}


def counters(value):
    for key, row in value.items():
        require(len(key.split('|')) == 5, 'Unclassified physical evaluation')
        attempted = integer(row.get('attempted', 0))
        returned = integer(row.get('returned', 0))
        errors = integer(row.get('errors', 0))
        require(attempted == returned + errors, 'Physical evaluation balance')
    return value


def inspect_recovery_execution(science, report, policy, scientific_protocol=None):
    """Validate physical work separately; the original timeout is never removed."""
    original = read(science / 'recovery_lineage/failed_case.json')
    trace = [json.loads(line) for line in (science / 'recovery_lineage/failed_trace.jsonl').read_text().splitlines()]
    ends = {(v['model'], v['start_index'], v['method']): {k:x for k,x in v.items() if k not in ('event','model')}
            for v in trace if v['event'] == 'attempt_end'}
    require(len(trace) == 46 and len(ends) == 23, 'Original physical attempts differ')
    for arm in ('null', 'LI'):
        exact(report['fits'][arm], original['fits'][arm], 'Reused fit subtree changed')
        exact(report['training_checks'][arm], original['training_checks'][arm], 'Reused training check changed')
    arm = 'LIplus_immigrant'
    records = report['fits'][arm]['records']
    for start in range(5):
        actual = [r for r in records if r['start_index'] == start]
        require(len(actual) == 1, 'Completed optimizer repeated')
        exact(actual[0], ends[(arm, start, 'L-BFGS-B')], 'Replayed return changed')
    old_error = ends[(arm, 5, 'L-BFGS-B')]
    exact(next(r for r in records if (r['start_index'], r['method']) == (5, 'L-BFGS-B')),
          old_error, 'Original arithmetic failure payload changed')
    interrupted = ends[(arm, 5, 'Powell')]
    require(interrupted['error_type'] == 'TimeoutError' and interrupted['last_evaluation']['evaluation_count'] == 2040,
            'Original interrupted invocation changed')
    execution = read(science / 'recovery_execution.json')
    ledger = [json.loads(line) for line in (science / 'recovery_calls.jsonl').read_text().splitlines()]
    scientific_protocol=scientific_protocol or read(REPO_ROOT/'experiments/s04b_joint_nuisance/protocol.json')
    box=scientific_protocol['shared_bounds']+scientific_protocol['inhibition_bounds']
    require(execution['schema'] == 'joint_partial_optimizer_recovery_calls_v2' and
            execution['exact_internal_optimizer_resume'] is False and execution['original_physical_attempts_retained'] == 23,
            'Recovery execution scope changed')
    require(execution['arm_calls'] == ['null','LI',arm,'LIplus_inclusive'] and
            execution['reused_complete_arms'] == ['null','LI'] and execution['replayed_successful_starts'] == list(range(5)),
            'Recovery reuse roster changed')
    exact(execution['original_interrupted_powell'], interrupted, 'Interrupted evidence changed')
    exact(execution['original_primary_error'], old_error, 'Original failure changed')
    require(ledger and ledger[0]['event'] == 'lineage' and ledger[0]['original_failed_physical_attempts'] == 23,
            'Missing physical lineage ledger')
    exact(ledger[0]['interrupted'], interrupted, 'Ledger failed invocation differs')
    reused = [v for v in ledger if v['event'] == 'reused_complete_arm']
    require([v['model'] for v in reused] == ['null','LI'] and all(v['optimizer_calls'] == 0 for v in reused),
            'Reused complete arms physically rerun')
    support=[v for v in ledger if v['event']=='repeated_training_check']
    require([v['model'] for v in support]==['null','LI'] and set(execution['repeated_training_checks'])=={'null','LI'} and
            set(execution['selected_check_evaluations'])=={'null','LI'},'Repeated training support census differs')
    selected_events=[v for v in ledger if v['event']=='selected_support_evaluation']
    expected_events=[dict(event='selected_support_evaluation',check_name=name,**v)
                     for name in ('null','LI') for v in execution['selected_check_evaluations'][name]]
    exact(selected_events,expected_events,'Selected raw support ledger differs')
    for row in support:
        payload={k:v for k,v in row.items() if k not in ('event','model')}
        exact(payload,execution['repeated_training_checks'][row['model']],'Training support ledger differs')
        inspect_training_equivalence(payload,original['training_checks'][row['model']],row['model'],
                                     execution['selected_check_evaluations'][row['model']],scientific_protocol)
    floors=[v for v in ledger if v['event']=='historical_floor_replay']
    require(len(floors)==1,'Historical floor replay ledger missing/duplicated')
    exact({k:v for k,v in floors[0].items() if k!='event'},execution['historical_floor_replay'],'Floor replay ledger differs')
    inspect_floor_replay(execution['historical_floor_replay'],original,report)
    inspect_return_context(ledger,execution,ends,box,report)
    returns = [v for v in ledger if v['event'] == 'replayed_optimizer_return']
    require([v['start_index'] for v in returns] == list(range(5)), 'Replayed successful start roster')
    for v in returns:
        old = ends[(arm, v['start_index'], 'L-BFGS-B')]
        require(v['model'] == arm and v['method'] == 'L-BFGS-B' and v['actual_objective_calls'] == 0 and
                v['historical_nfev'] == old['nfev'] and v['historical_nit'] == old['nit'], 'False replay-call census')
    failures = [v for v in ledger if v['event'] == 'replayed_primary_error']
    require(len(failures) == 1 and failures[0]['actual_objective_calls'] == 0, 'Primary error replay count')
    exact(failures[0]['original_record'], old_error, 'Replayed error ledger differs')
    physical_starts = [v for v in ledger if v['event'] == 'physical_optimizer_start']
    physical_ends = [v for v in ledger if v['event'] == 'physical_optimizer_end']
    logical = [(m, r['start_index'], r['method']) for m in (arm,'LIplus_inclusive') for r in report['fits'][m]['records']]
    expected = [key for key in logical if not (key[0] == arm and (key[1] < 5 or key[1:] == (5,'L-BFGS-B')))]
    require([tuple(v) for v in execution['logical_optimizer_calls']] == logical, 'Logical invocation census differs')
    require([(v['model'],v['start_index'],v['method']) for v in physical_starts] == expected ==
            [(v['model'],v['start_index'],v['method']) for v in physical_ends], 'Physical invocation roster differs')
    for start, end in zip(physical_starts, physical_ends):
        key = (start['model'],start['start_index'],start['method'])
        saved = next(r for r in report['fits'][key[0]]['records'] if (r['start_index'],r['method']) == key[1:])
        exact(start['initial_parameters'], saved['initial_parameters'], 'New physical initial point changed')
        restart = key == (arm,5,'Powell')
        require(start['kind'] == end['kind'] == ('restarted_interrupted_invocation' if restart else 'new_optimizer_invocation'),
                'Physical restart misclassified')
        require(end['returned'] is (saved['status'] == 'returned'), 'Physical return disagrees with logical record')
        integer(end['completed_objective_returns'])
        if end['returned']:
            require(end['completed_objective_returns'] == saved['nfev'], 'Physical objective count differs from solver count')
        if restart:
            exact(start['options'], policy['recovery']['original_powell_options'], 'Powell restart budget changed')
            exact(start['initial_parameters'], interrupted['initial_parameters'], 'Powell restarted from last iterate')
            require(end['completed_objective_returns'] <= 5000, 'Powell original per-invocation cap exceeded')
        counters(end['actual_evaluations'])
    restart_ends=[v for v in physical_ends if v['kind']=='restarted_interrupted_invocation']
    require(len(restart_ends)==1,'Interrupted Powell restart count differs')
    inspect_reference_snapshots(execution['reference_snapshots'],ledger,interrupted,restart_ends[0]['completed_objective_returns'])
    counts = counters(execution['actual_evaluations'])
    physical_returns = {}
    for end in physical_ends:
        key=(end['model'],end['kind'])
        physical_returns[key]=physical_returns.get(key,0)+end['completed_objective_returns']
        for name,row in end['actual_evaluations'].items():
            require(name in counts and all(value <= counts[name].get(field,0) for field,value in row.items()),
                    'Cumulative physical counters regress')
    for (model,context),expected_returns in physical_returns.items():
        actual_returns=sum(row.get('returned',0) for key,row in counts.items()
                           if key.split('|')[1]==model and key.split('|')[3]==context)
        require(actual_returns==expected_returns, 'Final physical return counters disagree with optimizer ledger')
    require(report['recovery_provenance']['exact_internal_optimizer_resume'] is False and
            report['recovery_provenance']['original_partial_sha256'] == policy['predecessor']['case_sha256'] and
            report['recovery_provenance']['original_trace_sha256'] == policy['predecessor']['trace_sha256'],
            'Recovered report lost physical provenance')
    core.close(report['prior_training_attempt_seconds'],original['wall_seconds'],'Retained partial case time')
    core.close(report['wall_seconds'],report['current_attempt_wall_seconds']+original['wall_seconds'],
               'Recovered case cumulative wall time')
    return dict(original_physical_attempts=23, original_timeout_retained=True,
                reused_complete_fit_arms=2, replayed_completed_optimizer_returns=5, replayed_primary_errors=1,
                new_physical_optimizer_invocations=len(physical_starts), restarted_interrupted_invocations=1,
                actual_evaluations=counts, exact_internal_optimizer_resume=False,
                reference_snapshot_scope='Observational only; restart may finish before either reference count. Original initial state and per-invocation recipe remain exact.')


def audit_saved(args):
    require(not sys.flags.optimize, 'Optimized Python is not admitted')
    repo, art, prior = map(lambda p: Path(p).resolve(), (args.repo,args.current,args.prior))
    science, prior_science = art/'science', prior/'science'
    require(bool(args.archive) == bool(args.archive_sha256), 'Archive/hash must be paired')
    if args.archive:
        custody.verify_archive(args.archive,args.archive_sha256,art)
    review, checker_pins = source_review(repo,args.checker_source_review,args.checker_source_review_sha256)
    conductor = read(art/'conductor_review.json')
    # Generic verifier checks each reviewed byte against both checkout and exact Git commit.
    require(conductor['reviewed_files_sha256'].get(CHECKER_PATH) == checker_pins[CHECKER_PATH], 'Recovery checker omitted from source map')
    custody.verify_reviewed_sources(repo,args.commit,conductor,review)
    config = read(args.config)
    policy = read(repo/RECOVERY_PATH)
    inspect_support_policy(policy)
    protocol = read(repo/'experiments/s04b_joint_nuisance/protocol.json')
    op = read(repo/'experiments/s04b_joint_execution/operational_protocol.json')
    index, result, admission = read(science/'index.json'), read(science/'result.json'), read(art/'admission.json')
    old = read(prior_science/'index.json')
    prior_review = read(args.prior_review)
    require(index['schema'] == 'joint_recovery_case_index_v2' and index['last_attempt_passed'] is True and
            index['partial_case'] is None and result['passed'] is True and result['status'] == 'batch_complete',
            'Failed or partial recovery cannot pass')
    require(sha(repo/RECOVERY_PATH) == index['recovery_protocol_sha256'] == result['recovery_protocol_sha256'] == admission['recovery_protocol_sha256'],
            'Recovery protocol identity differs')
    require(index['source_sha256'] == result['source_sha256'] == admission['source_sha256'], 'Recovery source identity differs')
    for path,pin in index['source_sha256'].items():
        require(sha(safe(repo,path)) == pin == conductor['reviewed_files_sha256'].get(path), 'Unreviewed recovery source: '+path)
    for path,pin in policy['predecessor_source_sha256'].items():
        require(sha(safe(repo,path)) == pin, 'Frozen scientific source changed')
    pins = read(repo/'experiments/s04b_joint_nuisance/input_pins.json')
    require(sha(repo/'experiments/s04b_joint_nuisance/input_pins.json') == protocol['input_pins_sha256'], 'Input manifest changed')
    for path,pin in pins.items():
        require(sha(safe(repo,path)) == pin, 'Scientific input changed: '+path)
    require(sha(repo/'experiments/s04b_joint_nuisance/protocol.json') == index['science_protocol_sha256'] == policy['scientific_protocol_sha256'], 'Science protocol changed')
    require(policy['shared_run']['config_sha256'] == sha(args.config) == admission['operational_run_config_sha256'] == conductor['operational_run_config_sha256'], 'Shared configuration changed')
    require(policy['shared_run']['run_id'] == config['run_id'] == admission['operational_run_id'] == conductor['operational_run_id'], 'Shared run differs')
    require(admission['mode'] == 'recovery_campaign' and admission['threads'] == 2 and admission['workers'] == 1, 'Recovery admission differs')
    require(admission['expires_utc'] == conductor['expires_utc'] and
            dt.datetime.fromisoformat(admission['expires_utc']) <= dt.datetime.fromisoformat(config['deadline_utc']), 'Expiry extended')
    require(policy['shared_run']['expires_utc'] == config['deadline_utc'], 'Protocol expiry changed')
    require(sha(prior_science/'index.json') == admission['prior_index_sha256'] and
            sha(args.prior_review) == admission['prior_review_sha256'], 'Prior admission identity differs')
    ids = [v['case_id'] for v in index['cases']]
    require(ids == policy['sequence'][:len(ids)] and 41 <= len(ids) <= 80 and len(ids) == len(set(ids)), 'Not exact original prefix')
    require(len(ids) == len(old['cases'])+1 and result['complete_cases'] == len(ids) and
            result['prior_case_count'] == len(old['cases']), 'Expected one new completed case')
    if len(old['cases']) == 40:
        require(sha(prior_science/'index.json') == policy['predecessor']['index_sha256'] and
                sha(args.prior_review) == policy['predecessor']['review_sha256'] and prior_review['passed'] is False and
                prior_review['audit_passed'] is True, 'Only exact reviewed failed predecessor is allowed')
    else:
        validate_review(prior_review,sha(prior_science/'index.json'),checker_pins,args.checker_source_review_sha256,pilot=len(old['cases'])==41)
    preserved_prefix(index,old,science,prior_science)
    carried = index['reviews'][-1]
    require(carried['sha256'] == sha(args.prior_review) and carried['accepted_index_sha256'] == sha(prior_science/'index.json') and
            safe(science,carried['file']).read_bytes() == Path(args.prior_review).read_bytes(), 'Carried exact disposition differs')
    failed = inspect_lineage(index,science,policy)
    charges = inspect_charges(index,science,policy)
    p = policy['predecessor']
    require(index['runtime'] == result['runtime'] and index['runtime']['essential'] == p['runtime_essential'] == old['runtime']['essential'], 'Original runtime changed')
    for key,path in (('library_sha256','build/attenuation.so'),('build_receipt_sha256','build/build_receipt.json')):
        require(index[key] == result[key] == admission[key] == p[key] == sha(art/path) == sha(prior/path), 'Original native/build changed')
    build = read(art/'build/build_receipt.json')
    require(build['passed'] is True and build['library_sha256'] == index['library_sha256'] and
            build['source_sha256'] == sha(repo/'experiments/s04b_joint_nuisance/attenuation.cpp'), 'Build receipt differs')
    slot = policy['fixed_slots'][len(ids)-41]
    require(result['requested_case'] == ids[-1] == slot['case_id'] and result['cases'] == [index['cases'][-1]] and
            admission['case_ids'] == conductor['case_ids'] == [ids[-1]] and admission['wall_seconds'] == slot['wall_seconds'], 'One-case fixed allocation changed')
    require(result['wall_seconds'] == index['attempts'][-1]['seconds'] and result['budget'] == index['budget'] and
            result['index_sha256'] == sha(science/'index.json') and result['admission_sha256'] == sha(art/'admission.json'), 'Result/index linkage differs')
    exact(result['pre_execution_failure'], policy['pre_execution_failure'], 'Result startup failure changed')
    exact(result['operational_failures'],policy['operational_failures'],'Result operational failures changed')
    exact(result['operational_diagnostics'],policy['operational_diagnostics'],'Result operational diagnostics changed')
    exact(result['operational_accounting'], index['operational_accounting'], 'Result operational accounting changed')
    require(index['attempts'][-1]['attempt_id'] == admission['numerical_attempt_id'] == conductor['numerical_attempt_id'], 'Current attempt attribution differs')
    spec, supervision = read(art/'supervisor_spec.json'),read(art/'supervision/result.json')
    custody.verify_resource_spec(spec,conductor,admission,config)
    require(supervision['supervisor_sha256'] == sha(repo/'scripts/supervise_research.py') and
            supervision['spec_sha256'] == sha(art/'supervisor_spec.json') and supervision['execution_log_sha256'] == sha(art/'supervision/execution.log'), 'Supervision source/evidence differs')
    require(supervision['launched'] is True and supervision['status'] == 'passed' and supervision['returncode'] == 0 and
            supervision['stop_reason'] is None and not supervision['cleanup_errors'] and not supervision['survivors_after_cleanup'], 'Unclean/failed execution')
    require(result['wall_seconds'] <= supervision['execution_wall_seconds'] <= slot['wall_seconds'] and
            supervision['sampled_peak_tree_rss_bytes'] <= spec['rss_cap_bytes'] and
            supervision['minimum_sampled_host_available_bytes'] >= spec['host_headroom_bytes'], 'Resource gate failed')
    require(dt.datetime.fromisoformat(supervision['started_utc']) <= dt.datetime.fromisoformat(supervision['finished_utc']) <=
            dt.datetime.fromisoformat(admission['expires_utc']), 'Execution exceeded expiry')
    manifest = {v['case_id']:v for v in read(repo/'reproduction/synthetic/input_manifest.json')['s04b']['cases']}
    reports = []
    for position,entry in enumerate(index['cases']):
        report = read(safe(science,entry['file']))
        require(sha(safe(science,entry['file'])) == entry['sha256'] and
                sha(safe(science,entry['trace'])) == entry['trace_sha256'] == report['attempts_sha256'], 'Case/trace hash differs')
        require(entry['file'] == 'cases/'+ids[position]+'.json' and entry['trace'] == 'cases/'+ids[position]+'.attempts.jsonl', 'Case resource path differs')
        meta = manifest[ids[position]]
        for key in ('case_id','regime','seed','n_train','n_test'):
            require(report[key] == meta[key], 'Case/input metadata differs')
        core.inspect_case(report,protocol)
        core.inspect_trace(safe(science,entry['trace']),report)
        core.inspect_historical(report,meta,repo)
        expected_reused = 4 if position == 0 else 2 if position == 40 else 0
        require(entry['reused_fit_arms'] == expected_reused and entry['new_fit_arms'] == 4-expected_reused, 'Completed arm reuse census differs')
        reports.append(report)
    require(set(index['recovery_execution_files']) == {'recovery_calls.jsonl','recovery_execution.json'}, 'Physical evidence roster differs')
    for name,pin in index['recovery_execution_files'].items():
        require(sha(safe(science,name)) == pin, 'Physical evidence hash differs')
    require(reports[40]['recovery_provenance']['execution_files'] == index['recovery_execution_files'], 'Recovered case physical linkage differs')
    physical = inspect_recovery_execution(science,reports[40],policy,protocol)
    independent = core.aggregate(reports,protocol)
    counts = dict(completed_case_fit_arms=4*len(ids),completed_case_new_fit_arms=4*len(ids)-6,
                  completed_case_reused_fit_arms=6,completed_outcomes=5*len(ids))
    for key,value in counts.items():
        require(result[key] == value, 'Completed-work census differs: '+key)
    require(result['partial_fit_checkpoint'] is None and result['original_fixed_slot_status'] == 'failed', 'Original failure or partial classification changed')
    if len(ids)==80:
        require(result['scientific_completion'] is True and sha(science/'summary.json') == result['summary_sha256'], 'Missing full summary')
        core.compare_tree(read(science/'summary.json'),independent)
    else:
        require(result['scientific_completion'] is False, 'Partial prefix called complete')
    return dict(passed=True,review_kind='automated_saved_output_check',checker_author='/root/continuation_cpu',
        live_agent_review=False,live_agent_review_performed=False,final_batch_agent_review_required=True,
        index_sha256=sha(science/'index.json'),source_sha256=index['source_sha256'],source_commit=args.commit,
        artifact_sha256=args.archive_sha256,checker_sources_sha256=checker_pins,checker_source_review_sha256=args.checker_source_review_sha256,
        recovery_protocol_sha256=index['recovery_protocol_sha256'],prior_index_sha256=sha(prior_science/'index.json'),
        prior_review_sha256=sha(args.prior_review),complete_cases=len(ids),outcomes=5*len(ids),historical_floor_checks=6*len(ids),
        historical_comparison_rows=5*len(ids),verified_input_pins=len(pins),counts=counts,budget=index['budget'],
        resource_accounting=charges,physical_recovery=physical,attempt_census=core.attempt_census(reports,protocol),
        independent_summary=independent,scientific_completion=len(ids)==80,scientific_execution_in_audit=False,
        original_failed_attempt_passed=False,original_failed_index_sha256=policy['predecessor']['index_sha256'],
        supervision=dict(execution_wall_seconds=supervision['execution_wall_seconds'],sampled_peak_tree_rss_bytes=supervision['sampled_peak_tree_rss_bytes']),
        scope='Saved arithmetic and custody only; physical timeout remains retained separately from logical fit records. No likelihood/refit/generation calls.')


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ('repo','current','prior','prior-review','config','commit','output','checker-source-review','checker-source-review-sha256'):
        parser.add_argument('--'+name,required=True)
    parser.add_argument('--archive');parser.add_argument('--archive-sha256')
    args=parser.parse_args(argv);output=Path(args.output);output.parent.mkdir(parents=True,exist_ok=True)
    with output.open('x',encoding='utf-8',newline='\n') as stream:
        try:result=audit_saved(args)
        except Exception as error:
            result=dict(passed=False,review_kind='automated_saved_output_check',live_agent_review=False,
                        live_agent_review_performed=False,final_batch_agent_review_required=True,
                        scientific_execution_in_audit=False,error_type=type(error).__name__,error=str(error))
        stream.write(json.dumps(result,indent=2,allow_nan=False)+'\n')
    print(json.dumps(dict(passed=result['passed'],receipt=str(output),receipt_sha256=sha(output))))
    return 0 if result['passed'] else 1


if __name__=='__main__':
    raise SystemExit(main())
