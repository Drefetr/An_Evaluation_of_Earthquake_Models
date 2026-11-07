"""Fixed, supervised recovery hosts; no automatic retry or scientific changes."""
import argparse
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

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
sys.path.insert(0, str(REPO))


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
    temporary.write_text(json.dumps(value, indent=2, allow_nan=False)+'\n', encoding='utf-8')
    os.replace(temporary, path)


def source_identity():
    return {p.relative_to(REPO).as_posix():sha(p) for p in sorted(HERE.rglob('*'))
            if p.is_file() and p.suffix in ('.py','.json')}


def repo_path(relative):
    pure = PurePosixPath(relative)
    require(not pure.is_absolute() and '..' not in pure.parts and
            '\\' not in relative and ':' not in relative, 'Nonportable source path')
    value = (REPO/relative).resolve()
    require(value.is_relative_to(REPO.resolve()), 'Escaping source path')
    return value


def pre_execution_charge(policy, recovery):
    """One retained workflow bound; nested child durations are not extra charges."""
    failure = recovery['pre_execution_failure']
    require(failure['charge_seconds'] == policy['pre_execution_failure_charge_seconds'] == 90 and
            failure['status'] == 'failed_before_scientific_evaluation' and
            failure['scientific_predecessor_unchanged'] is True,
            'Explicit pre-science startup charge changed')
    require(failure['resource_review_sha256'] == policy['pre_execution_failure_resource_review_sha256'],
            'Startup accounting review differs')
    for key in ('archive', 'review', 'resource_review', 'workflow_log'):
        require(sha(repo_path(failure[key])) == failure[key+'_sha256'],
                'Retained startup-failure evidence changed: '+key)
    audit = read(repo_path(failure['review']))
    resource = read(repo_path(failure['resource_review']))
    require(audit.get('audit_passed') is True and audit.get('passed') is False and
            audit.get('overall_scientific_passed') is False and
            audit['archive_sha256'] == failure['archive_sha256'],
            'Startup failure cannot be relabelled successful')
    require(resource.get('passed') is True and
            resource['amendment']['explicit_new_charge_bound_seconds'] == failure['charge_seconds'],
            'Startup resource amendment is not accepted')
    # The ninety-second workflow bound already contains both nested durations.
    require(0 <= failure['nested_scientific_seconds'] <= failure['nested_supervised_seconds'] <= 90,
            'Nested startup timing is outside its one workflow bound')
    return failure['charge_seconds']


def operational_failure_charge(policy, recovery):
    """Prepared ordered accounting; the historical singleton is an uncharged alias."""
    failures = recovery['operational_failures']
    require(isinstance(failures,list) and len(failures) == 2 and
            failures[0] == recovery['pre_execution_failure'],
            'Operational failures must preserve the exact first historical alias')
    require(len({row['archive_sha256'] for row in failures}) == len(failures),
            'Duplicate failed operational launch')
    require([row['charge_seconds'] for row in failures] == [90,120],
            'Reviewed ordered operational charges differ')
    # This validates the original90s evidence once; it does not add the alias separately.
    first = pre_execution_charge(policy,recovery)
    second = failures[1]
    require(second['status'] == 'failed_during_training_support' and
            second['scientific_predecessor_unchanged'] is True and
            second['support_evaluation_count'] == 5 and second['optimizer_call_count'] == 0,
            'Second failure execution scope differs')
    for key in ('archive','review','resource_review','workflow_log'):
        require(sha(repo_path(second[key])) == second[key+'_sha256'],
                'Second failed-launch evidence changed: '+key)
    audit = read(repo_path(second['review']))
    resource = read(repo_path(second['resource_review']))
    require(audit.get('audit_passed') is True and audit.get('passed') is False and
            audit.get('overall_scientific_passed') is False and
            audit['archive_sha256'] == second['archive_sha256'],
            'Second failed launch cannot be relabelled successful')
    require(resource.get('passed') is True and
            resource['timing']['conservative_whole_launch_charge_seconds'] == 120 and
            resource['failure']['support_evaluation_count'] == 5 and
            resource['failure']['optimizer_call_count'] == 0,
            'Second failure resource/scope evidence differs')
    require(0 <= second['nested_scientific_seconds'] <= second['nested_supervised_seconds'] <= 120,
            'Nested second-launch time exceeds its one workflow bound')
    return first+second['charge_seconds']


def verify_policy():
    policy = read(HERE/'batch_policy.json')
    path = REPO/'experiments/s04b_joint_recovery/recovery_protocol.json'
    recovery = read(path)
    require(sha(path) == policy['recovery_protocol_sha256'], 'Recovery protocol changed')
    require(policy['shared_run'] == recovery['shared_run'], 'Shared expiry/config changed')
    require(policy['resources'] == dict(host_wall_seconds=14400, maximum_case_slots_seconds=12600,
        maximum_cases_per_host=8, host_overhead_seconds=1800, upload_reserve_seconds=600,
        checker_wall_seconds=120, finalization_reserve_seconds=30,
        campaign_aggregate_seconds=115200, additional_global_finalization_reserve_seconds=1800),
        'Host resource policy changed')
    evidence_path = HERE/'evidence/resource_review.json'
    require(sha(evidence_path) == policy['resource_review_sha256'], 'Resource review changed')
    evidence = read(evidence_path)
    require(evidence.get('passed') is True and policy['actual_hosts'] ==
            recovery['actual_hosts'] == evidence['proposal']['actual_execution_hosts'],
            'Reviewed actual host partition changed')
    require(policy['initial_accepted_case_count'] == 40 and
            policy['starting_accepted_counts'] == [40,41,46,51,56,61,69,77],
            'Fixed host prefixes changed')
    sequence = recovery['sequence']
    require(len(sequence) == len(set(sequence)) == 80, 'Nonunique scientific roster')
    slots = recovery['fixed_slots']
    require([r['case_id'] for r in slots] == sequence[40:], 'Remaining fixed slots differ')
    require([n for g in policy['actual_hosts'] for n in g['case_ids']] == sequence[40:],
            'Host cases omit, reorder or repeat a remaining case')
    for number, group in enumerate(policy['actual_hosts'], 1):
        require(group['host'] == number and 1 <= len(group['case_ids']) <= 8,
                'Invalid actual host count/order')
        selected = [r for r in slots if r['case_id'] in group['case_ids']]
        seconds = sum(r['wall_seconds'] for r in selected)
        for row in selected:
            expected = 2520 if row['regime'] in (4,6) else 1200
            require(row['wall_seconds'] == expected and
                    row['scientific_reservation_seconds'] == expected-30, 'Case cap changed')
        require(seconds == group['case_slot_seconds'] <= 12600 and
                group['outer_maximum_seconds'] == seconds+1800 <= 14400 and
                group['host_overhead_reserve_seconds'] == 1800 and
                group['checker_reservations_seconds'] == 120*len(selected) and
                group['upload_reserve_seconds'] == 600 and
                group['host_finalization_reserve_seconds'] == 30 and
                group['remaining_preparation_margin_seconds'] == 1800-600-30-120*len(selected) >= 0,
                'Host reserves no longer cover the full fixed group')
    require(sum(r['wall_seconds'] for r in slots) == 71760, 'Future case allocation differs')
    startup_charge = pre_execution_charge(policy, recovery)
    require(recovery['predecessor']['known_outer_charged_seconds']+startup_charge+71760+8*1800+1800 <= 115200,
            'Known outer time and conservative reserves exceed unchanged allowance')
    for relative, pin in policy['historical_sources'].items():
        require(sha(repo_path(relative)) == pin, 'Historical helper source changed')
    return policy, recovery


def reviewed_index(review):
    if review.get('review_kind') == 'live_agent_failure_and_partial_output_review':
        return review.get('failed_index',{}).get('sha256')
    return review.get('index_sha256')


def next_cases(policy, recovery, admission, index, prior_review):
    batch_id = admission['batch_id']
    require(type(batch_id) is int and 1 <= batch_id <= 8, 'Unknown fixed recovery host')
    group = policy['actual_hosts'][batch_id-1]
    count = policy['starting_accepted_counts'][batch_id-1]
    ids = [r['case_id'] for r in index['cases']]
    require(ids == recovery['sequence'][:count] and len(ids) == count,
            'Wrong fixed host prefix; no automatic suffix retry')
    require(admission['case_ids'] == group['case_ids'], 'Host roster must be the exact fixed group')
    require(reviewed_index(prior_review) == admission['prior_index_sha256'],
            'Prior review does not bind this exact index')
    if batch_id == 1:
        p = recovery['predecessor']
        require(admission['prior_index_sha256'] == p['index_sha256'] and
                index.get('schema') == 'joint_budgeted_case_index_v2' and
                index.get('last_attempt_passed') is False and
                index.get('partial_case',{}).get('case_id') == p['case_id'] and
                index['budget']['total_seconds'] == p['original_index_charged_seconds'],
                'Only the exact failed predecessor can enter standalone recovery')
        require(prior_review.get('audit_passed') is True and prior_review.get('passed') is False and
                prior_review.get('overall_scientific_passed') is False and
                prior_review.get('live_agent_review') is True and
                prior_review.get('review_kind') == 'live_agent_failure_and_partial_output_review',
                'Failed predecessor needs its explicit independent failure audit')
        require(group['case_ids'] == [p['case_id']], 'Recovery pilot must run alone')
    else:
        require(index.get('schema') == 'joint_recovery_case_index_v2' and
                index.get('partial_case') is None and index.get('last_attempt_passed') is True and
                prior_review.get('passed') is True, 'Failed/partial successor blocks progression')
        if batch_id == 2:
            require(prior_review.get('live_agent_review') is True and
                    prior_review.get('review_kind') == 'live_agent_saved_output_review' and
                    not prior_review.get('final_batch_agent_review_required',False),
                    'Standalone recovery pilot requires live independent acceptance')
    attempts = admission['child_attempt_ids']
    require(set(attempts) == set(group['case_ids']) and len(set(attempts.values())) == len(attempts),
            'Child attempt roster is incomplete or duplicated')
    old = {r['attempt_id'] for r in index['attempts']}
    for name in group['case_ids']:
        expected = admission['numerical_attempt_id']+'-case-%03d' % (recovery['sequence'].index(name)+1)
        require(attempts[name] == expected and expected not in old, 'Child attempt is not unique')
    return group['case_ids']


def timing(policy, group, host_started, child_seconds, slot_seconds, now=None, final=False):
    now = dt.datetime.now(dt.timezone.utc) if now is None else now
    elapsed = (now-dt.datetime.fromisoformat(host_started)).total_seconds()
    r = policy['resources']
    require(math.isfinite(elapsed) and elapsed >= 0 and math.isfinite(child_seconds) and child_seconds >= 0,
            'Invalid host clock/accounting')
    overhead = elapsed-child_seconds
    require(overhead >= -1, 'Inconsistent host/child timing')
    check = 0 if final else r['checker_wall_seconds']
    require(elapsed+slot_seconds+check+r['finalization_reserve_seconds']
            <= group['outer_maximum_seconds']-r['upload_reserve_seconds'],
            'Whole next slot does not fit this actual host deadline')
    require(overhead+check+r['finalization_reserve_seconds']
            <= r['host_overhead_seconds']-r['upload_reserve_seconds'], 'Host overhead allowance exhausted')
    return elapsed, max(0, overhead)


def checked_supervision(output):
    record = read(Path(output)/'result.json')
    require(record.get('status') == 'passed' and record.get('returncode') == 0 and
            record.get('cleanup_errors') == [] and record.get('survivors_after_cleanup') == [],
            'Child supervisor did not certify clean success')
    return record


def supervised(command, output, cap, admission, environment, spec_path):
    spec = dict(command=command,cwd=str(REPO),output=str(output),env=environment,
                wall_cap_seconds=cap,rss_cap_bytes=admission['rss_cap_bytes'],
                host_headroom_bytes=admission['host_headroom_bytes'],sample_seconds=.5)
    write(spec_path,spec)
    process = subprocess.run([sys.executable,'-B',str(REPO/'scripts/supervise_research.py'),str(spec_path)],cwd=REPO)
    require(process.returncode == 0, 'Supervised child failed')
    return checked_supervision(output)


def check_receipt(path, current, checker_path, checker_review_sha, checker_pins):
    receipt = read(path)
    require(receipt.get('passed') is True and receipt.get('index_sha256') == sha(current/'science/index.json'),
            'Automated checker did not accept the exact index')
    require(receipt.get('review_kind') == 'automated_saved_output_check' and
            receipt.get('live_agent_review') is False and receipt.get('live_agent_review_performed') is False and
            receipt.get('final_batch_agent_review_required') is True,
            'Automated review attribution differs')
    require(receipt.get('checker_source_review_sha256') == checker_review_sha and
            receipt.get('checker_sources_sha256') == checker_pins and
            checker_pins.get(checker_path.relative_to(REPO).as_posix()) == sha(checker_path),
            'Automated checker identity differs')
    return receipt


def load_driver():
    from experiments.s04b_joint_recovery import driver
    return driver


def check_source_reviews(admission, policy, scientific, checker_review_path):
    source_path = repo_path(admission['conductor_review']['source_review_record'])
    require(sha(source_path) == admission['source_review_sha256'], 'Host/driver source review changed')
    source = read(source_path)
    require(source.get('passed') is True, 'Host/driver source review is not passed')
    require(sha(checker_review_path) == admission['checker_source_review_sha256'] ==
            policy['checker']['source_review_sha256'], 'Checker source review changed')
    checker_review = read(checker_review_path)
    require(checker_review.get('passed') is True, 'Checker source review is not passed')
    checker_keys = (policy['checker']['path'], policy['checker']['core_path'],
                    *policy['checker']['helper_sources_sha256'])
    checker_pins = {key:sha(repo_path(key)) for key in checker_keys}
    require(checker_pins[policy['checker']['core_path']] == policy['checker']['core_sha256'],
            'Independent scientific arithmetic auditor changed')
    for relative, pin in policy['checker']['helper_sources_sha256'].items():
        require(checker_pins[relative] == pin, 'Independent checker helper changed: '+relative)
    for relative, pin in {**source_identity(), **scientific}.items():
        require(source['reviewed_files_sha256'].get(relative) == pin == sha(repo_path(relative)),
                'Unreviewed host/driver source: '+relative)
    for relative, pin in checker_pins.items():
        require(checker_review['reviewed_files_sha256'].get(relative) == pin,
                'Unreviewed checker source: '+relative)
    for relative, pin in {**source_identity(), **scientific, **checker_pins}.items():
        require(admission['reviewed_files_sha256'].get(relative) == pin,
                'Conductor omitted a required source pin: '+relative)
    for relative, pin in admission['reviewed_files_sha256'].items():
        require(sha(repo_path(relative)) == pin, 'Conductor source changed: '+relative)
    return checker_pins


def child_admission(admission, policy, recovery, driver_pins, name, slot, prior, prior_review, native, build):
    return dict(mode='recovery_campaign',independent_review_passed=True,scheduler_review_passed=True,
        external_supervision=True,source_sha256=driver_pins,
        recovery_protocol_sha256=policy['recovery_protocol_sha256'],
        prior_index_sha256=sha(prior/'science/index.json'),prior_review_sha256=sha(prior_review),
        library_sha256=sha(native),build_receipt_sha256=sha(build),
        numerical_attempt_id=admission['child_attempt_ids'][name],expires_utc=admission['expires_utc'],
        operational_run_id=policy['shared_run']['run_id'],operational_run_config_sha256=policy['shared_run']['config_sha256'],
        lease_token_sha256=admission['lease_token_sha256'],threads=2,workers=1,
        sampled_process_tree_rss_cap_bytes=admission['rss_cap_bytes'],minimum_host_free_bytes=admission['host_headroom_bytes'],
        case_id=name,case_ids=[name],wall_seconds=slot['wall_seconds'],
        shared_host_numerical_attempt_id=admission['numerical_attempt_id'],
        host_source_review_sha256=admission['source_review_sha256'])


def run(args):
    output = Path(args.output).resolve()
    require(not output.is_relative_to(REPO), 'Output must be outside checkout')
    output.mkdir(parents=True,exist_ok=False)
    result = dict(schema='joint_recovery_host_batch_v1',passed=False,status='preflight',children=[],
                  live_agent_review=False,final_batch_agent_review_required=True,scientific_completion=False)
    write(output/'result.json',result)
    current = None; child_seconds = 0.
    try:
        policy, recovery = verify_policy(); admission = read(args.admission)
        require(admission['mode'] == 'recovery_host_batch' and admission['source_sha256'] == source_identity() and
                admission['batch_policy_sha256'] == sha(HERE/'batch_policy.json') and
                admission['recovery_protocol_sha256'] == policy['recovery_protocol_sha256'],
                'Host source/policy admission differs')
        require(admission['host_batch_source_review_passed'] is True and admission['checker_source_review_passed'] is True,
                'Independent host/checker source reviews required')
        require(admission['shared_run'] == policy['shared_run'], 'Host shared run differs')
        require(sha(args.config) == policy['shared_run']['config_sha256'], 'Config identity differs')
        require(admission['expires_utc'] == policy['shared_run']['expires_utc'], 'Shared expiry changed')
        require(dt.datetime.now(dt.timezone.utc) < dt.datetime.fromisoformat(admission['expires_utc']), 'Expired host')
        require(admission['rss_cap_bytes'] == 6442450944 and admission['host_headroom_bytes'] == 2147483648,
                'Host memory policy differs')
        token = os.environ.get('JOINT_NUMERICAL_LEASE_TOKEN','')
        require(token and hashlib.sha256(token.encode()).hexdigest() == admission['lease_token_sha256'], 'Shared batch lease differs')
        driver = load_driver(); driver_pins = driver.source_identity()
        require(driver_pins == admission['scientific_source_sha256'], 'Reviewed recovery source differs')
        checker_pins = check_source_reviews(admission,policy,driver_pins,args.checker_review)
        original = read(REPO/'experiments/s04b_joint_execution/operational_protocol.json')
        require(sha(args.failed_archive) == original['original_failure']['failed_archive_sha256'], 'Original failed artifact changed')
        prior = Path(args.prior).resolve(); prior_review = Path(args.prior_review).resolve()
        index = read(prior/'science/index.json'); reviewed = read(prior_review)
        require(sha(prior/'science/index.json') == admission['prior_index_sha256'] and
                sha(prior_review) == admission['prior_review_sha256'], 'Predecessor evidence changed')
        if admission['batch_id'] == 1:
            require(sha(prior_review) == recovery['predecessor']['review_sha256'], 'Original failure-review pin differs')
        names = next_cases(policy,recovery,admission,index,reviewed)
        group = policy['actual_hosts'][admission['batch_id']-1]
        require(admission['execution_window_seconds'] == group['outer_maximum_seconds']-600,
                'Actual host execution window differs')
        checker = repo_path(policy['checker']['path'])
        environment = {k:'2' for k in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','NUMEXPR_NUM_THREADS','BLIS_NUM_THREADS')}
        environment.update(PYTHONDONTWRITEBYTECODE='1',JOINT_NUMERICAL_LEASE_TOKEN=token,NUMERICAL_LEASE_TOKEN=token)
        slots = {s['case_id']:s for s in recovery['fixed_slots']}
        result.update(status='running',batch_id=admission['batch_id'],requested_cases=names,
                      source_sha256=source_identity(),admission_sha256=sha(args.admission),
                      prior_index_sha256=admission['prior_index_sha256'],execution_window_seconds=admission['execution_window_seconds'],
                      recovery_protocol_sha256=policy['recovery_protocol_sha256'],
                      mandatory_pilot_live_review_pending=admission['batch_id']==1)
        for number,name in enumerate(names):
            slot = slots[name]
            timing(policy,group,admission['host_started_utc'],child_seconds,slot['wall_seconds'])
            require((dt.datetime.fromisoformat(admission['expires_utc'])-dt.datetime.now(dt.timezone.utc)).total_seconds()
                    >= slot['wall_seconds']+policy['resources']['checker_wall_seconds']+30,
                    'Whole next child does not fit shared expiry')
            current = output/'children'/('%02d_%s'%(number+1,name));current.mkdir(parents=True)
            result['active_child'] = current.relative_to(output).as_posix();write(output/'result.json',result)
            shutil.copytree(prior/'build',current/'build')
            shutil.copyfile(args.failed_archive,current/'original_failure.zip')
            native, build = current/'build/attenuation.so', current/'build/build_receipt.json'
            require(sha(native) == recovery['predecessor']['library_sha256'] and
                    sha(build) == recovery['predecessor']['build_receipt_sha256'], 'Original native/build changed')
            review = dict(admission['conductor_review'],stage='joint-recovery-case',case_id=name,case_ids=[name],
                numerical_attempt_id=admission['child_attempt_ids'][name],wall_cap_seconds=slot['wall_seconds'],
                prior_index_sha256=sha(prior/'science/index.json'),prior_index_review=str(prior_review),
                prior_review_sha256=sha(prior_review),automated_progression=number>0,
                live_agent_review_of_prior_child=number==0 and read(prior_review).get('live_agent_review') is True,
                live_agent_review_of_this_child=False,host_source_review_sha256=admission['source_review_sha256'])
            review['host_initial_artifact'] = {key:review.pop(key) for key in
                ('prior_artifact_id','prior_archive_sha256') if key in review}
            review.update(prior_index_path=str(prior/'science/index.json'),prior_artifact_directory=str(prior))
            write(current/'conductor_review.json',review)
            child = child_admission(admission,policy,recovery,driver_pins,name,slot,prior,prior_review,native,build)
            write(current/'admission.json',child)
            command = [sys.executable,'-B','-m','experiments.s04b_joint_recovery.driver',
                '--output',str(current/'science'),'--admission',str(current/'admission.json'),
                '--library',str(native),'--build-receipt',str(build),
                '--prior-index',str(prior/'science/index.json'),'--prior-review',str(prior_review)]
            # Preparation is charged as host overhead; re-admit the complete slot after copying evidence.
            timing(policy,group,admission['host_started_utc'],child_seconds,slot['wall_seconds'])
            require((dt.datetime.fromisoformat(admission['expires_utc'])-dt.datetime.now(dt.timezone.utc)).total_seconds()
                    >= slot['wall_seconds']+policy['resources']['checker_wall_seconds']+30,
                    'Preparation consumed shared-expiry margin')
            started = time.monotonic()
            try:
                supervised(command,current/'supervision',slot['wall_seconds'],admission,environment,current/'supervisor_spec.json')
            finally:
                child_seconds += time.monotonic()-started
            actual = read(current/'science/result.json')
            require(actual.get('passed') is True and actual.get('status') == 'batch_complete' and
                    actual.get('schema') == 'joint_recovery_batch_v1' and
                    [c['case_id'] for c in actual.get('cases',[])] == [name] and
                    actual.get('index_sha256') == sha(current/'science/index.json'),
                    'Zero exit is not an exact completed recovery case')
            check = current/'automated_review.json'
            command = [sys.executable,'-B',str(checker),'--repo',str(REPO),'--current',str(current),'--prior',str(prior),
                '--prior-review',str(prior_review),'--config',str(args.config),'--commit',admission['source_commit'],
                '--output',str(check),'--checker-source-review',str(args.checker_review),
                '--checker-source-review-sha256',admission['checker_source_review_sha256']]
            supervised(command,current/'checker_supervision',policy['resources']['checker_wall_seconds'],admission,
                       environment,current/'checker_supervisor_spec.json')
            check_receipt(check,current,checker,admission['checker_source_review_sha256'],checker_pins)
            result['children'].append(dict(case_id=name,artifact=current.relative_to(output).as_posix(),
                index_sha256=sha(current/'science/index.json'),automated_review_sha256=sha(check),
                scientific_result_sha256=sha(current/'science/result.json'),supervision_sha256=sha(current/'supervision/result.json')))
            result.pop('active_child',None);result.update(latest_index=(current/'science/index.json').relative_to(output).as_posix(),
                latest_automated_review=check.relative_to(output).as_posix())
            write(output/'result.json',result);prior,prior_review = current,check;current=None
        timing(policy,group,admission['host_started_utc'],child_seconds,0,final=True)
        result.update(passed=True,status='host_batch_complete',scientific_completion=False,
                      shared_run_budget=read(prior/'science/index.json')['budget'])
    except BaseException as exc:
        result.update(passed=False,status='stopped_requires_review',error_type=type(exc).__name__,error=str(exc))
        if current is not None:
            result['failed_child'] = dict(artifact=current.relative_to(output).as_posix(), evidence={
                name:dict(path=(current/name).relative_to(output).as_posix(),sha256=sha(current/name)) if (current/name).is_file() else None
                for name in ('science/result.json','science/index.json','supervision/result.json',
                             'checker_supervision/result.json','automated_review.json')})
    finally:
        result['supervised_case_process_seconds'] = child_seconds
        write(output/'result.json',result)
        if result['passed']:
            try:
                timing(policy,group,admission['host_started_utc'],child_seconds,0,final=True)
                require(dt.datetime.now(dt.timezone.utc) < dt.datetime.fromisoformat(admission['expires_utc']),
                        'Shared expiry crossed during final serialization')
            except BaseException as exc:
                result.update(passed=False,status='stopped_requires_review',error_type=type(exc).__name__,error=str(exc))
                write(output/'result.json',result)
    return 0 if result['passed'] else 1


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('admission','prior','prior-review','config','checker-review','failed-archive','output'):
        parser.add_argument('--'+name,required=True,type=Path)
    raise SystemExit(run(parser.parse_args()))
