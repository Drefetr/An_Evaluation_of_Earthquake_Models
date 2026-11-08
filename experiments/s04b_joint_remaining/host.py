"""Supervise untouched histories once, retaining terminal scientific unknowns."""
import argparse
import copy
import datetime as dt
import hashlib
import json
import math
import os
from pathlib import Path, PurePosixPath
import shutil
import subprocess
import sys
import time
import zipfile

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
ARMS = ('null', 'LI', 'LIplus_immigrant', 'LIplus_inclusive')


def require(value, message):
    if not value:
        raise ValueError(message)


def read(path):
    return json.loads(Path(path).read_bytes())


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write(path, value):
    path = Path(path)
    temporary = path.with_suffix(path.suffix+'.tmp')
    temporary.write_bytes((json.dumps(value, indent=2, allow_nan=False)+'\n').encode('utf-8'))
    os.replace(temporary, path)


def safe(root, relative):
    require(isinstance(relative, str) and relative and '\\' not in relative and ':' not in relative,
            'Nonportable evidence path')
    p = PurePosixPath(relative)
    require(not p.is_absolute() and '..' not in p.parts, 'Escaping evidence path')
    path = (Path(root)/relative).resolve()
    require(path.is_relative_to(Path(root).resolve()), 'Escaping evidence path')
    return path


def source_identity():
    paths = [HERE/'host.py', HERE/'__init__.py', HERE/'protocol.json', REPO/'scripts/supervise_research.py']
    return {p.relative_to(REPO).as_posix():sha(p) for p in sorted(paths)}


def verify_protocol():
    p = read(HERE/'protocol.json')
    require(p['schema'] == 'joint_remaining_protocol_v1', 'Unknown protocol')
    sequence = p['full_sequence']
    require(len(sequence) == len(set(sequence)) == 80 and p['case_ids'] == sequence[41:], 'Changed untouched roster')
    slots = p['case_slots']
    require([s['case_id'] for s in slots] == p['case_ids'], 'Changed slot roster')
    for s in slots:
        cap = 2520 if s['case_id'].startswith('S6_') else 1200
        require(s['wall_seconds'] == cap and s['scientific_seconds'] == cap-30, 'Changed original case cap')
    r = p['resources']
    require(r['threads'] == 2 and r['workers'] == 1 and r['sampled_process_tree_rss_cap_bytes'] == 6442450944
            and r['minimum_host_free_bytes'] == 2147483648 and r['campaign_aggregate_seconds'] == 115200
            and r['host_overhead_seconds'] == 1800 and r['upload_reserve_seconds'] == 600
            and r['checker_wall_seconds'] == 120 and r['host_finalization_reserve_seconds'] == 30
            and r['global_finalization_reserve_seconds'] == 1800, 'Changed shared resource envelope')
    groups = p['actual_hosts']
    require([len(g['case_ids']) for g in groups] == [1,4,5,5,5,8,8,3]
            and [name for g in groups for name in g['case_ids']] == p['case_ids'], 'Changed fixed host partition')
    for i, g in enumerate(groups, 1):
        seconds = sum(s['wall_seconds'] for s in slots if s['case_id'] in g['case_ids'])
        require(g['host'] == i and g['case_slot_seconds'] == seconds <= 12600
                and g['outer_maximum_seconds'] == seconds+1800 <= 14400
                and g['host_overhead_reserve_seconds'] == 1800 and g['upload_reserve_seconds'] == 600
                and g['checker_reservations_seconds'] == 120*len(g['case_ids'])
                and g['host_finalization_reserve_seconds'] == 30
                and g['remaining_preparation_margin_seconds'] == 1170-120*len(g['case_ids']) >= 0,
                'Host does not reserve its fixed slots/checks/setup/upload')
    require(sum(s['wall_seconds'] for s in slots) == r['future_case_slots_seconds'] == 70560
            and r['future_host_count'] == 8 and r['future_host_overhead_reserve_seconds'] == 14400,
            'Future reservation changed')
    ref = p['immutable_failure_reference']
    require(ref['complete_case_ids'] == sequence[:40] and ref['case_id'] == sequence[40], 'Original disposition prefix changed')
    require(math.isclose(ref['included_current_scientific_seconds']+ref['additional_workflow_overhead_seconds'],
                         ref['whole_workflow_bound_seconds'], rel_tol=0, abs_tol=1e-9), 'Pilot wall charged twice or omitted')
    require(math.isclose(ref['accounted_base_seconds'], math.fsum(ref[k] for k in (
        'scientific_indexed_seconds','known_prior_outer_overhead_seconds','operational_failure_charge_seconds',
        'operational_diagnostic_charge_seconds','additional_workflow_overhead_seconds')), rel_tol=0, abs_tol=1e-9),
        'Original failed scientific attempt or overhead charged incorrectly')
    require(ref['accounted_base_seconds']+70560+14400+1800 <= 115200, 'Remaining envelope exceeds original allocation')
    for relative, pin in p['design_reviews'].items():
        require(sha(safe(REPO, relative)) == pin, 'Independent design evidence changed')
    for key in ('archive','review'):
        require(sha(safe(REPO, ref[key])) == ref[key+'_sha256'], 'Immutable failure evidence changed')
    return p


def projection(report, disposition, source):
    fits = report['fits']
    return dict(case_id=report['case_id'], regime=report['regime'], seed=report['seed'],
        disposition=disposition, scientific_passed=disposition == 'complete', source=source,
        outcomes=copy.deepcopy(report['outcomes']) if disposition == 'complete' else [],
        n_train=report['n_train'], n_test=report['n_test'], thinning=report['thinning'],
        optimizer_failed_attempts_by_arm={name:sum(row['success'] is False for row in fits[name]['records'])
                                        for name in ARMS if name in fits},
        null_search_gap_by_arm={name:bool(fits[name]['null_search_gaps']) for name in ARMS
                               if name in fits and fits[name]['passed'] is True})


def initial_records(policy, prior_path, prior_review_path):
    """Read exact old evidence once; never copy its case trees into new outputs."""
    ref = policy['immutable_failure_reference']
    require(sha(prior_path) == ref['index_sha256'] and sha(prior_review_path) == ref['review_sha256'],
            'Wrong immutable predecessor')
    index, audit = read(prior_path), read(prior_review_path)
    require(index['last_attempt_passed'] is False and audit['audit_passed'] is True and audit['passed'] is False,
            'The capped predecessor cannot become successful')
    rows = []
    prefix = str(PurePosixPath(ref['index_member']).parent)
    with zipfile.ZipFile(safe(REPO, ref['archive'])) as saved:
        require(len(saved.namelist()) == len(set(saved.namelist())), 'Duplicate archive member')
        def data(member, pin):
            raw = saved.read(member)
            require(hashlib.sha256(raw).hexdigest() == pin, 'Original member identity differs: '+member)
            return json.loads(raw)
        require(saved.read(ref['index_member']) == Path(prior_path).read_bytes(), 'Original index member differs')
        for entry in index['cases']:
            member, trace = prefix+'/'+entry['file'], prefix+'/'+entry['trace']
            report = data(member, entry['sha256'])
            require(hashlib.sha256(saved.read(trace)).hexdigest() == entry['trace_sha256'], 'Original trace differs')
            require(report['passed'] is True and len(report['outcomes']) == 5, 'Incomplete original successful case')
            source = dict(kind='immutable_archive', archive_sha256=ref['archive_sha256'], case_member=member,
                          case_sha256=entry['sha256'], trace_member=trace, trace_sha256=entry['trace_sha256'])
            rows.append(projection(report, 'complete', source))
        failed = data(ref['case_member'], ref['case_sha256'])
        trace = saved.read(ref['trace_member'])
        require(hashlib.sha256(trace).hexdigest() == ref['trace_sha256'], 'Original failure trace differs')
        last = json.loads(trace.splitlines()[-1])
        require(last.pop('event') == 'attempt_end' and last.pop('model') == 'LIplus_immigrant'
                and last == audit['failure']['capped_optimizer_record'], 'Original capped return differs')
        require(last['success'] is False and last['solver_status'] == 1 and last['nfev'] == 5000 and last['nit'] == 22
                and failed['passed'] is False and failed['outcomes'] == [], 'Original unknown was relabelled')
        source = dict(kind='immutable_archive', archive_sha256=ref['archive_sha256'], case_member=ref['case_member'],
                      case_sha256=ref['case_sha256'], trace_member=ref['trace_member'], trace_sha256=ref['trace_sha256'])
        row = projection(failed, 'scientific_unknown', source)
        row.update(unknown_origin='audited_retained_failure',
            unknown_reason=dict(primary_status='unknown_starts', unresolved_model='LIplus_immigrant',
                unresolved_start=5, not_run_starts=[6,7], not_run_models=['LIplus_inclusive'],
                masking_error_type=failed['error_type'], masking_error=failed['error'], terminal_solver_return=last),
            model_census=audit['execution_census'])
        rows.append(row)
    require([r['case_id'] for r in rows] == policy['full_sequence'][:41], 'Original prefix differs')
    return rows


def budget(policy, attempts):
    ref, r = policy['immutable_failure_reference'], policy['resources']
    ids = [a['case_id'] for a in attempts]
    require(ids == policy['case_ids'][:len(ids)] and len(set(ids)) == len(ids), 'Repeated or reordered attempt')
    require(len({a['numerical_attempt_id'] for a in attempts}) == len(attempts), 'Repeated numerical attempt')
    slots = {s['case_id']:s['wall_seconds'] for s in policy['case_slots']}
    for a in attempts:
        require(type(a['seconds']) in (int,float) and math.isfinite(a['seconds']) and 0 <= a['seconds'] <= slots[a['case_id']],
                'Invalid actual child time')
    new = math.fsum(a['seconds'] for a in attempts)
    b = dict(base_scientific_indexed_seconds=ref['scientific_indexed_seconds'], new_case_seconds=new,
        scientific_indexed_seconds=ref['scientific_indexed_seconds']+new,
        known_prior_outer_overhead_seconds=ref['known_prior_outer_overhead_seconds'],
        operational_failure_charge_seconds=ref['operational_failure_charge_seconds'],
        operational_diagnostic_charge_seconds=ref['operational_diagnostic_charge_seconds'],
        pilot04_incremental_workflow_overhead_seconds=ref['additional_workflow_overhead_seconds'],
        accounted_seconds=ref['accounted_base_seconds']+new,
        remaining_case_slots_seconds=sum(slots[name] for name in policy['case_ids'][len(ids):]),
        reserved_host_overhead_seconds=r['future_host_overhead_reserve_seconds'],
        global_finalization_reserve_seconds=r['global_finalization_reserve_seconds'])
    b['upper_bound_seconds'] = math.fsum(b[k] for k in ('accounted_seconds','remaining_case_slots_seconds',
        'reserved_host_overhead_seconds','global_finalization_reserve_seconds'))
    require(b['upper_bound_seconds'] <= r['campaign_aggregate_seconds'], 'Original aggregate allowance exhausted')
    return b


def counts(records):
    require(all(r['disposition'] in ('complete','scientific_unknown') for r in records), 'Invalid terminal disposition')
    for row in records:
        require(row['scientific_passed'] is (row['disposition'] == 'complete') and
                len(row['outcomes']) == (5 if row['scientific_passed'] else 0), 'Unknown cannot contribute scores')
    return dict(processed_histories=len(records), complete_histories=sum(r['scientific_passed'] for r in records),
        unknown_histories=sum(not r['scientific_passed'] for r in records), unattempted_histories=80-len(records),
        computed_outcomes=sum(len(r['outcomes']) for r in records))


def next_cases(policy, admission, index, prior_review):
    number = admission['batch_id']
    require(type(number) is int and 1 <= number <= 8, 'Unknown fixed host')
    group = policy['actual_hosts'][number-1]
    expected_count = 41+sum(len(g['case_ids']) for g in policy['actual_hosts'][:number-1])
    require(admission['case_ids'] == group['case_ids'], 'Host roster differs')
    if number == 1:
        ref = policy['immutable_failure_reference']
        require(admission['prior_index_sha256'] == ref['index_sha256'] and
                admission['prior_review_sha256'] == ref['review_sha256'] and
                index['last_attempt_passed'] is False and prior_review['audit_passed'] is True and prior_review['passed'] is False,
                'Initial host requires the exact audited terminal failure')
        require([r['case_id'] for r in index['cases']] == policy['full_sequence'][:40], 'Original complete prefix differs')
    else:
        require(index['schema'] == 'joint_remaining_index_v1' and index['protocol_sha256'] == admission['protocol_sha256']
                and index['host_source_sha256'] == admission['source_sha256']
                and index['scientific_source_sha256'] == admission['scientific_source_sha256']
                and index['original_native'] == policy['original_native']
                and index['immutable_failure_reference'] == policy['immutable_failure_reference']
                and index['passed'] is False and index['scientific_completion'] is False, 'Invalid compact predecessor')
        require([r['case_id'] for r in index['records']] == policy['full_sequence'][:expected_count]
                and len(index['records']) == expected_count, 'No suffix retry or skipped history is allowed')
        require(index['budget'] == budget(policy,index['attempts']) and index['counts'] == counts(index['records']),
                'Predecessor count/accounting changed')
        require(prior_review.get('audit_passed') is True and prior_review.get('disposition_valid') is True and
                prior_review['index_sha256'] == admission['prior_index_sha256'], 'Prior compact index is not audited')
        require(prior_review.get('review_kind') == 'live_agent_saved_output_review' and
                prior_review.get('live_agent_review') is True and
                prior_review.get('final_batch_agent_review_required') is False,
                'Each new host requires live independent review of its predecessor')
    attempts = admission['child_attempt_ids']
    require(set(attempts) == set(group['case_ids']) and len(set(attempts.values())) == len(attempts), 'Incomplete child attempt roster')
    for name in group['case_ids']:
        require(attempts[name] == admission['numerical_attempt_id']+'-case-%03d'%(policy['full_sequence'].index(name)+1),
                'Child attempt identity differs')
    return group


def timing(policy, group, started, child_seconds, next_slot, now=None, final=False):
    now = dt.datetime.now(dt.timezone.utc) if now is None else now
    elapsed = (now-dt.datetime.fromisoformat(started)).total_seconds()
    r = policy['resources']; check = 0 if final else r['checker_wall_seconds']
    require(math.isfinite(elapsed) and elapsed >= 0 and math.isfinite(child_seconds) and 0 <= child_seconds <= elapsed+1,
            'Invalid whole-host timing')
    require(elapsed+next_slot+check+30 <= group['outer_maximum_seconds']-600,
            'Complete next slot does not fit actual host deadline')
    require(elapsed-child_seconds+check+30 <= r['host_overhead_seconds']-600, 'Host overhead reserve exhausted')
    return elapsed


def check_source_reviews(admission, policy, scientific, source_path, checker_path):
    require(sha(source_path) == admission['source_review_sha256'] and
            sha(checker_path) == admission['checker_source_review_sha256'], 'Source-review evidence changed')
    source, checker = read(source_path), read(checker_path)
    require(source.get('passed') is True and checker.get('passed') is True, 'Independent source reviews required')
    checker_pins = {p:sha(safe(REPO,p)) for p in policy['checker_sources']}
    for path, pin in {**source_identity(),**scientific}.items():
        require(source['reviewed_files_sha256'].get(path) == pin, 'Unreviewed host/scientific dependency: '+path)
    for path, pin in checker_pins.items():
        require(checker['reviewed_files_sha256'].get(path) == pin, 'Unreviewed checker dependency: '+path)
    for path, pin in {**source_identity(),**scientific,**checker_pins}.items():
        require(admission['reviewed_files_sha256'].get(path) == pin, 'Conductor omitted source: '+path)
    for path, pin in admission['reviewed_files_sha256'].items():
        require(sha(safe(REPO,path)) == pin, 'Admitted source changed: '+path)
    return checker_pins


def supervised(command, output, cap, admission, environment, spec_path):
    spec = dict(command=command,cwd=str(REPO),output=str(output),env=environment,
        wall_cap_seconds=cap,rss_cap_bytes=admission['rss_cap_bytes'],host_headroom_bytes=admission['host_headroom_bytes'],sample_seconds=.5)
    write(spec_path,spec)
    process = subprocess.run([sys.executable,'-B',str(REPO/'scripts/supervise_research.py'),str(spec_path)],cwd=REPO)
    require(process.returncode == 0, 'Supervised process failed')
    actual = read(Path(output)/'result.json')
    require(actual.get('status') == 'passed' and actual.get('returncode') == 0 and
            actual.get('cleanup_errors') == [] and actual.get('survivors_after_cleanup') == [], 'Supervisor did not certify quiescent success')
    return actual


def child_admission(admission, policy, scientific, name, slot):
    return dict(mode='untouched_remaining_case',case_id=name,case_ids=[name],source_sha256=scientific,
        protocol_sha256=admission['protocol_sha256'],independent_review_passed=True,external_supervision=True,
        operational_run_id=policy['shared_run']['run_id'],operational_run_config_sha256=policy['shared_run']['config_sha256'],
        expires_utc=admission['expires_utc'],wall_seconds=slot['wall_seconds'],threads=2,workers=1,
        sampled_process_tree_rss_cap_bytes=admission['rss_cap_bytes'],minimum_host_free_bytes=admission['host_headroom_bytes'],
        lease_token_sha256=admission['lease_token_sha256'],library_sha256=admission['library_sha256'],
        build_receipt_sha256=admission['build_receipt_sha256'],numerical_attempt_id=admission['child_attempt_ids'][name])


def append_candidate(policy, admission, previous, current, output, prior_index, prior_review):
    actual = read(current/'science/result.json');name = actual['case_id']
    require(actual.get('schema') == 'joint_remaining_case_result_v1' and actual.get('handled') is True
            and actual.get('disposition_valid') is True and actual.get('status') == 'terminal_disposition'
            and actual['disposition'] in ('complete','scientific_unknown'), 'Zero exit is not a valid scientific disposition')
    require(actual['passed'] is actual['scientific_passed'] and actual['passed'] is (actual['disposition'] == 'complete'),
            'Scientific unknown cannot be relabelled successful')
    require(actual['source_sha256'] == admission['scientific_source_sha256'] and
            actual['protocol_sha256'] == admission['protocol_sha256'] and
            actual['numerical_attempt_id'] == admission['child_attempt_ids'][name], 'Executed child identity differs')
    case_path = safe(current/'science',actual['report_file']); trace_path = safe(current/'science',actual['trace_file'])
    require(sha(case_path) == actual['report_sha256'] and sha(trace_path) == actual['trace_sha256'], 'Current case/trace bytes differ')
    report = read(case_path)
    require(report['case_id'] == name and name == policy['full_sequence'][len(previous['records'])], 'Child is not the exact next untouched case')
    source = dict(kind='host_execution',execution_id=admission['numerical_attempt_id'],
        case_path=case_path.relative_to(output).as_posix(),case_sha256=sha(case_path),
        trace_path=trace_path.relative_to(output).as_posix(),trace_sha256=sha(trace_path),
        result_path=(current/'science/result.json').relative_to(output).as_posix(),result_sha256=sha(current/'science/result.json'),
        supervision_path=(current/'supervision/result.json').relative_to(output).as_posix(),supervision_sha256=sha(current/'supervision/result.json'))
    row = projection(report, actual['disposition'], source)
    if not actual['scientific_passed']:
        require(report['outcomes'] == [], 'Unknown contains held-out scores')
        row.update(unknown_origin='new_frozen_solver_cap',unknown_reason=actual['unknown_reason'],
                   model_census=actual['model_census'],terminal_solver_return=actual['terminal_solver_return'])
    attempt = dict(case_id=name,numerical_attempt_id=actual['numerical_attempt_id'],host_execution_id=admission['numerical_attempt_id'],
                   seconds=actual['wall_seconds'],result_sha256=source['result_sha256'])
    rows, attempts = previous['records']+[row], previous['attempts']+[attempt]
    local_prior = Path(prior_index).resolve().is_relative_to(Path(output).resolve())
    return dict(schema='joint_remaining_index_v1',protocol_sha256=admission['protocol_sha256'],
        host_source_sha256=admission['source_sha256'],scientific_source_sha256=admission['scientific_source_sha256'],
        original_native=policy['original_native'],immutable_failure_reference=policy['immutable_failure_reference'],
        records=rows,attempts=attempts,predecessor=dict(index_sha256=sha(prior_index),review_sha256=sha(prior_review),
            archive_sha256=None if local_prior else admission.get('prior_archive_sha256'),
            artifact_id=None if local_prior else admission.get('prior_artifact_id')),
        budget=budget(policy,attempts),counts=counts(rows),passed=False,scientific_completion=False)


def check_receipt(path, candidate, checker_pins, review_pin):
    value = read(path)
    require(value.get('audit_passed') is True and value.get('disposition_valid') is True and
            value.get('index_sha256') == sha(candidate) and value.get('live_agent_review') is False and
            value.get('live_agent_review_performed') is False and value.get('scientific_completion') is False and
            value.get('final_batch_agent_review_required') is True, 'Automated checker did not accept the exact disposition/index')
    require(value.get('checker_sources_sha256') == checker_pins and value.get('checker_source_review_sha256') == review_pin,
            'Independent checker source identity differs')


def load_driver():
    from experiments.s04b_joint_remaining import case_driver
    return case_driver


def run(args):
    out = Path(args.output).resolve()
    require(not out.is_relative_to(REPO.resolve()), 'Output must be outside checkout')
    out.mkdir(parents=True,exist_ok=False)
    result = dict(schema='joint_remaining_host_v1',passed=False,host_execution_passed=False,status='preflight',children=[],
        scientific_completion=False,live_agent_review=False,final_batch_agent_review_required=True)
    write(out/'result.json',result);current=None;child_seconds=0.
    try:
        policy=verify_protocol();a=read(args.admission);driver=load_driver();scientific=driver.source_identity()
        require(a['mode']=='remaining_host_batch' and a['source_sha256']==source_identity() and
                a['scientific_source_sha256']==scientific and a['protocol_sha256']==sha(HERE/'protocol.json') and
                a['scientific_protocol_sha256']==policy['scientific_protocol_sha256'], 'Source/protocol admission differs')
        require(a['host_batch_source_review_passed'] is True and a['checker_source_review_passed'] is True,
                'Source approvals missing')
        require(a['shared_run']==policy['shared_run'] and sha(args.config)==policy['shared_run']['config_sha256'] and
                a['expires_utc']==policy['shared_run']['expires_utc'], 'Shared allocation/expiry changed')
        require(a['rss_cap_bytes']==6442450944 and a['host_headroom_bytes']==2147483648, 'Memory gates differ')
        require(dt.datetime.now(dt.timezone.utc)<dt.datetime.fromisoformat(a['expires_utc']), 'Expired host')
        token=os.environ.get('JOINT_NUMERICAL_LEASE_TOKEN','')
        require(token and hashlib.sha256(token.encode()).hexdigest()==a['lease_token_sha256'], 'Shared lease differs')
        for key,path in (('library_sha256',args.library),('build_receipt_sha256',args.build_receipt)):
            require(sha(path)==a[key]==policy['original_native'][key], 'Original native/build bytes differ')
        checker_pins=check_source_reviews(a,policy,scientific,args.source_review,args.checker_review)
        prior_index,prior_review=Path(args.prior_index),Path(args.prior_review)
        require(sha(prior_index)==a['prior_index_sha256'] and sha(prior_review)==a['prior_review_sha256'], 'Predecessor bytes differ')
        previous=read(prior_index);reviewed=read(prior_review);group=next_cases(policy,a,previous,reviewed)
        require(a['execution_window_seconds']==group['outer_maximum_seconds']-600, 'Actual host window differs')
        if a['batch_id']==1:
            previous=dict(records=initial_records(policy,prior_index,prior_review),attempts=[])
        environment={k:'2' for k in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','NUMEXPR_NUM_THREADS','BLIS_NUM_THREADS')}
        environment.update(PYTHONDONTWRITEBYTECODE='1',JOINT_NUMERICAL_LEASE_TOKEN=token,NUMERICAL_LEASE_TOKEN=token)
        slots={s['case_id']:s for s in policy['case_slots']}
        result.update(status='running',batch_id=a['batch_id'],requested_cases=group['case_ids'],source_sha256=source_identity(),
            admission_sha256=sha(args.admission),protocol_sha256=a['protocol_sha256'])
        for number,name in enumerate(group['case_ids'],1):
            slot=slots[name]
            timing(policy,group,a['host_started_utc'],child_seconds,slot['wall_seconds'])
            require((dt.datetime.fromisoformat(a['expires_utc'])-dt.datetime.now(dt.timezone.utc)).total_seconds()
                    >=slot['wall_seconds']+150, 'Whole child does not fit shared expiry')
            current=out/'children'/('%02d_%s'%(number,name));current.mkdir(parents=True)
            result['active_child']=current.relative_to(out).as_posix();write(out/'result.json',result)
            child=child_admission(a,policy,scientific,name,slot);write(current/'admission.json',child)
            conductor=dict(a['conductor_review'],stage='joint-remaining-case',case_id=name,case_ids=[name],
                numerical_attempt_id=child['numerical_attempt_id'],wall_cap_seconds=slot['wall_seconds'],
                prior_index_sha256=sha(prior_index),prior_review_sha256=sha(prior_review),
                live_agent_review_of_this_child=False,automated_progression=number>1,
                host_source_review_sha256=a['source_review_sha256'])
            write(current/'conductor_review.json',conductor)
            command=[sys.executable,'-B','-m','experiments.s04b_joint_remaining.case_driver',
                '--case-id',name,'--library',str(args.library),'--build-receipt',str(args.build_receipt),
                '--admission',str(current/'admission.json'),'--output',str(current/'science')]
            timing(policy,group,a['host_started_utc'],child_seconds,slot['wall_seconds'])
            require((dt.datetime.fromisoformat(a['expires_utc'])-dt.datetime.now(dt.timezone.utc)).total_seconds()
                    >=slot['wall_seconds']+150, 'Preparation consumed shared-expiry margin')
            started=time.monotonic()
            try:
                supervised(command,current/'supervision',slot['wall_seconds'],a,environment,current/'supervisor_spec.json')
            finally:
                child_seconds+=time.monotonic()-started
            candidate=append_candidate(policy,a,previous,current,out,prior_index,prior_review)
            write(current/'index.json',candidate)
            check=current/'automated_review.json'
            command=[sys.executable,'-B',str(safe(REPO,policy['checker_sources'][0])),
                '--repo',str(REPO),'--current',str(current),'--prior',str(prior_index),'--prior-review',str(prior_review),
                '--config',str(args.config),'--commit',a['source_commit'],'--output',str(check),
                '--checker-source-review',str(args.checker_review),'--checker-source-review-sha256',a['checker_source_review_sha256']]
            supervised(command,current/'checker_supervision',120,a,environment,current/'checker_supervisor_spec.json')
            check_receipt(check,current/'index.json',checker_pins,a['checker_source_review_sha256'])
            shutil.copyfile(current/'index.json',out/'index.json')
            result['children'].append(dict(case_id=name,artifact=current.relative_to(out).as_posix(),
                disposition=candidate['records'][-1]['disposition'],scientific_passed=candidate['records'][-1]['scientific_passed'],
                index_sha256=sha(out/'index.json'),automated_review_sha256=sha(check),
                scientific_result_sha256=sha(current/'science/result.json'),supervision_sha256=sha(current/'supervision/result.json')))
            result.pop('active_child',None);result.update(latest_index='index.json',index_sha256=sha(out/'index.json'),
                latest_automated_review=check.relative_to(out).as_posix(),counts=candidate['counts'],budget=candidate['budget'])
            write(out/'result.json',result)
            previous=candidate;prior_index=current/'index.json';prior_review=check;current=None
        timing(policy,group,a['host_started_utc'],child_seconds,0,final=True)
        result.update(passed=False,host_execution_passed=True,status='host_batch_complete',scientific_completion=False)
    except BaseException as exc:
        result.update(passed=False,host_execution_passed=False,status='stopped_requires_review',error_type=type(exc).__name__,error=str(exc))
        if current is not None:
            result['failed_child']=dict(artifact=current.relative_to(out).as_posix(),evidence={
                name:dict(path=(current/name).relative_to(out).as_posix(),sha256=sha(current/name)) if (current/name).is_file() else None
                for name in ('science/result.json','index.json','supervision/result.json','checker_supervision/result.json','automated_review.json')})
    finally:
        result['supervised_case_process_seconds']=child_seconds;write(out/'result.json',result)
        if result['host_execution_passed']:
            try:
                timing(policy,group,a['host_started_utc'],child_seconds,0,final=True)
                require(dt.datetime.now(dt.timezone.utc)<dt.datetime.fromisoformat(a['expires_utc']), 'Finalization exceeded shared expiry')
            except BaseException as exc:
                result.update(host_execution_passed=False,status='stopped_requires_review',error_type=type(exc).__name__,error=str(exc))
                write(out/'result.json',result)
    return 0 if result['host_execution_passed'] else 1


if __name__ == '__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ('admission','prior-index','prior-review','config','source-review','checker-review','library','build-receipt','output'):
        parser.add_argument('--'+name,required=True,type=Path)
    raise SystemExit(run(parser.parse_args()))
