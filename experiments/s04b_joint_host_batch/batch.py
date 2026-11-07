"""Sequential, supervised one-case children; frozen scientific driver is unchanged."""
import argparse
import datetime as dt
import hashlib
import json
import math
import os
from pathlib import Path
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
    return {p.relative_to(REPO).as_posix():sha(p) for p in sorted(HERE.iterdir())
            if p.is_file() and p.suffix in ('.py','.json')}


def verify_policy():
    policy = read(HERE/'batch_policy.json')
    allocation_path = REPO/'experiments/s04b_joint_budgeted/allocation_protocol.json'
    allocation = read(allocation_path)
    require(sha(allocation_path) == policy['allocation_protocol_sha256'], 'Frozen allocation changed')
    require(policy['shared_run'] == allocation['shared_run'], 'Shared expiry/config changed')
    require(policy['resources'] == dict(host_wall_seconds=14400, maximum_case_slots_seconds=12600,
        host_overhead_seconds=1800, upload_reserve_seconds=600, checker_wall_seconds=120,
        finalization_reserve_seconds=30), 'Host resource policy changed')
    slots = allocation['fixed_slots'][1:]
    groups, group, seconds = [], [], 0
    for slot in slots:
        if seconds+slot['wall_seconds'] > 12600:
            groups.append(dict(batch_id=len(groups)+1,case_ids=group,slot_seconds=seconds))
            group, seconds = [], 0
        group.append(slot['case_id']); seconds += slot['wall_seconds']
    groups.append(dict(batch_id=len(groups)+1,case_ids=group,slot_seconds=seconds))
    require(policy['batches'] == groups and len(groups) == 9, 'Fixed host partition/order differs')
    require(policy['initial_accepted_case_count'] == 6, 'Initial accepted prefix differs')
    return policy, allocation


def next_cases(policy, allocation, admission, index):
    require(index.get('partial_case') is None and index.get('last_attempt_passed') is True,
            'Failed/partial predecessor blocks continuation')
    ids = [r['case_id'] for r in index['cases']]
    require(ids == allocation['sequence'][:len(ids)] and 6 <= len(ids) < 80, 'Invalid accepted prefix')
    batch_id = admission['batch_id']
    require(type(batch_id) is int and 1 <= batch_id <= 9, 'Unknown fixed host batch')
    group = policy['batches'][batch_id-1]['case_ids']
    start = allocation['sequence'].index(group[0])
    require(start <= len(ids) < start+len(group), 'Predecessor is outside this fixed batch')
    remaining = group[len(ids)-start:]
    require(admission['case_ids'] == remaining, 'Host admission must retain the exact unexecuted suffix')
    attempts = admission['child_attempt_ids']
    require(set(attempts) == set(remaining), 'Child attempt roster differs')
    require(len(set(attempts.values())) == len(remaining), 'Duplicate child attempt identity')
    old = {r['attempt_id'] for r in index['attempts']}
    for name in remaining:
        expected = admission['numerical_attempt_id']+'-case-%03d' % (allocation['sequence'].index(name)+1)
        require(attempts[name] == expected and expected not in old, 'Child attempt is not unique under shared batch lease')
    return remaining


def timing(policy, host_started, child_seconds, slot_seconds, now=None):
    now = dt.datetime.now(dt.timezone.utc) if now is None else now
    elapsed = (now-dt.datetime.fromisoformat(host_started)).total_seconds()
    r = policy['resources']
    require(math.isfinite(elapsed) and elapsed >= 0, 'Invalid host clock')
    overhead = elapsed-child_seconds
    require(overhead >= -1, 'Inconsistent host/child timing')
    require(elapsed+slot_seconds+r['checker_wall_seconds']+r['finalization_reserve_seconds']
            <= r['host_wall_seconds']-r['upload_reserve_seconds'], 'Whole next slot does not fit host deadline')
    require(overhead+r['checker_wall_seconds']+r['finalization_reserve_seconds']
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


def check_receipt(path, current, checker_path, checker_review_sha):
    receipt = read(path)
    require(receipt.get('passed') is True and receipt.get('index_sha256') == sha(current/'science/index.json'),
            'Automated checker did not accept the exact index')
    require(receipt.get('review_kind') == 'automated_saved_output_check' and
            receipt.get('live_agent_review') is False and receipt.get('final_batch_agent_review_required') is True,
            'Automated review attribution differs')
    require(receipt.get('live_agent_review_performed') is False and
            receipt.get('checker_source_review_sha256') == checker_review_sha and
            receipt.get('checker_sources_sha256',{}).get('experiments/s04b_joint_audit/check.py') == sha(checker_path),
            'Automated checker identity differs')
    return receipt


def run(args):
    output = Path(args.output).resolve()
    require(not output.is_relative_to(REPO), 'Output must be outside checkout')
    output.mkdir(parents=True,exist_ok=False)
    result = dict(schema='joint_fixed_host_batch_v1',passed=False,status='preflight',children=[],
                  live_agent_review=False,final_batch_agent_review_required=True,scientific_completion=False)
    write(output/'result.json',result)
    current = None; child_seconds = 0.
    try:
        policy, allocation = verify_policy(); admission = read(args.admission)
        require(admission['mode'] == 'fixed_host_batch' and admission['source_sha256'] == source_identity() and
                admission['batch_policy_sha256'] == sha(HERE/'batch_policy.json'), 'Host source/policy admission differs')
        require(admission['host_batch_source_review_passed'] is True and admission['checker_source_review_passed'] is True,
                'Independent host/checker source review required')
        require(admission['shared_run'] == policy['shared_run'], 'Host shared run differs')
        require(sha(args.config) == policy['shared_run']['config_sha256'], 'Config identity differs')
        require(dt.datetime.fromisoformat(admission['expires_utc']) <= dt.datetime.fromisoformat(policy['shared_run']['expires_utc']),
                'Host expiry exceeds unchanged shared run')
        require(dt.datetime.now(dt.timezone.utc) < dt.datetime.fromisoformat(admission['expires_utc']), 'Expired host')
        require(admission['rss_cap_bytes'] == 6442450944 and admission['host_headroom_bytes'] >= 2147483648,
                'Host memory policy differs')
        token = os.environ.get('JOINT_NUMERICAL_LEASE_TOKEN','')
        require(token and hashlib.sha256(token.encode()).hexdigest() == admission['lease_token_sha256'], 'Shared batch lease differs')
        from experiments.s04b_joint_budgeted import driver
        require(driver.source_identity() == admission['scientific_source_sha256'], 'Frozen one-case source identity differs')
        original = read(REPO/'experiments/s04b_joint_execution/operational_protocol.json')
        require(sha(args.failed_archive) == original['original_failure']['failed_archive_sha256'], 'Original failed artifact changed')
        prior = Path(args.prior).resolve(); prior_review = Path(args.prior_review).resolve()
        index = read(prior/'science/index.json'); reviewed = read(prior_review)
        require(reviewed.get('passed') is True and reviewed.get('index_sha256') == sha(prior/'science/index.json') == admission['prior_index_sha256'] and
                sha(prior_review) == admission['prior_review_sha256'], 'Initial exact accepted predecessor differs')
        if len(index['cases']) == 6:
            require(sha(prior/'science/index.json') == policy['initial_index_sha256'] and
                    sha(prior_review) == policy['initial_review_sha256'], 'Initial joint06 acceptance differs')
        names = next_cases(policy,allocation,admission,index)
        checker = REPO/'experiments/s04b_joint_audit/check.py'
        require(sha(args.checker_review) == admission['checker_source_review_sha256'] == policy['checker']['source_review_sha256'],
                'Checker source-review bytes changed')
        source_review = read(args.checker_review)
        require(source_review.get('passed') is True, 'Checker source review is not passed')
        for path,pin in policy['checker']['source_sha256'].items():
            require(sha(REPO/path) == admission['reviewed_files_sha256'].get(path) == source_review['reviewed_files_sha256'].get(path) == pin,
                    'Checker/core source changed: '+path)
        for path,pin in admission['reviewed_files_sha256'].items():
            require(sha(REPO/path) == pin, 'Reviewed host source changed: '+path)
        environment = {k:'2' for k in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','NUMEXPR_NUM_THREADS','BLIS_NUM_THREADS')}
        environment.update(PYTHONDONTWRITEBYTECODE='1',JOINT_NUMERICAL_LEASE_TOKEN=token,NUMERICAL_LEASE_TOKEN=token)
        slots = {s['case_id']:s for s in allocation['fixed_slots']}
        result.update(status='running',batch_id=admission['batch_id'],requested_cases=names,
                      source_sha256=source_identity(),admission_sha256=sha(args.admission),prior_index_sha256=admission['prior_index_sha256'])
        for number,name in enumerate(names):
            slot = slots[name]
            timing(policy,admission['host_started_utc'],child_seconds,slot['wall_seconds'])
            require((dt.datetime.fromisoformat(admission['expires_utc'])-dt.datetime.now(dt.timezone.utc)).total_seconds()
                    >= slot['wall_seconds']+policy['resources']['checker_wall_seconds']+30, 'Whole next child does not fit shared expiry')
            current = output/'children'/('%02d_%s'%(number+1,name));current.mkdir(parents=True)
            result['active_child'] = current.relative_to(output).as_posix();write(output/'result.json',result)
            shutil.copytree(prior/'build',current/'build')
            shutil.copyfile(args.failed_archive,current/'original_failure.zip')
            native, build = current/'build/attenuation.so', current/'build/build_receipt.json'
            require(sha(native) == allocation['predecessor']['library_sha256'] and
                    sha(build) == allocation['predecessor']['build_receipt_sha256'], 'Original native/build changed')
            review = dict(admission['conductor_review'],stage='joint-budgeted-case',case_id=name,case_ids=[name],
                          numerical_attempt_id=admission['child_attempt_ids'][name],wall_cap_seconds=slot['wall_seconds'],
                          prior_index_sha256=sha(prior/'science/index.json'),prior_index_review=str(prior_review),
                          automated_progression=True,live_agent_review_of_prior_child=False)
            review['host_initial_artifact'] = {key:review.pop(key) for key in
                ('prior_artifact_id','prior_archive_sha256') if key in review}
            review.update(prior_index_path=str(prior/'science/index.json'),prior_artifact_directory=str(prior),
                          live_agent_review_of_this_child=False)
            write(current/'conductor_review.json',review)
            child = dict(mode='budgeted_campaign',independent_review_passed=True,scheduler_review_passed=True,
                external_supervision=True,source_sha256=driver.source_identity(),allocation_protocol_sha256=policy['allocation_protocol_sha256'],
                transition_review_sha256=allocation['transition_review_sha256'],prior_index_sha256=sha(prior/'science/index.json'),
                prior_review_sha256=sha(prior_review),library_sha256=sha(native),build_receipt_sha256=sha(build),
                numerical_attempt_id=review['numerical_attempt_id'],expires_utc=admission['expires_utc'],
                operational_run_id=policy['shared_run']['run_id'],operational_run_config_sha256=policy['shared_run']['config_sha256'],
                lease_token_sha256=admission['lease_token_sha256'],threads=2,workers=1,sampled_process_tree_rss_cap_bytes=admission['rss_cap_bytes'],
                case_id=name,case_ids=[name],wall_seconds=slot['wall_seconds'],shared_host_numerical_attempt_id=admission['numerical_attempt_id'])
            write(current/'admission.json',child)
            command = [sys.executable,'-B',str(REPO/'experiments/s04b_joint_budgeted/driver.py'),'--output',str(current/'science'),
                '--admission',str(current/'admission.json'),'--library',str(native),'--build-receipt',str(build),
                '--prior-index',str(prior/'science/index.json'),'--prior-review',str(prior_review)]
            # Preparation is charged host overhead; re-admit the full fixed slot immediately before launch.
            timing(policy,admission['host_started_utc'],child_seconds,slot['wall_seconds'])
            require((dt.datetime.fromisoformat(admission['expires_utc'])-dt.datetime.now(dt.timezone.utc)).total_seconds()
                    >= slot['wall_seconds']+policy['resources']['checker_wall_seconds']+30, 'Preparation consumed shared-expiry margin')
            started = time.monotonic()
            try:
                supervised(command,current/'supervision',slot['wall_seconds'],admission,environment,current/'supervisor_spec.json')
            finally:
                child_seconds += time.monotonic()-started
            actual = read(current/'science/result.json')
            require(actual.get('passed') is True and actual.get('status') == 'batch_complete' and
                    [c['case_id'] for c in actual.get('cases',[])] == [name] and actual.get('index_sha256') == sha(current/'science/index.json'),
                    'Zero exit is not an exact completed case')
            check = current/'automated_review.json'
            command = [sys.executable,'-B',str(checker),'--repo',str(REPO),'--current',str(current),'--prior',str(prior),
                '--prior-review',str(prior_review),'--config',str(args.config),'--commit',admission['source_commit'],'--output',str(check),
                '--checker-source-review',str(args.checker_review),'--checker-source-review-sha256',admission['checker_source_review_sha256']]
            supervised(command,current/'checker_supervision',policy['resources']['checker_wall_seconds'],admission,environment,current/'checker_supervisor_spec.json')
            check_receipt(check,current,checker,admission['checker_source_review_sha256'])
            result['children'].append(dict(case_id=name,artifact=current.relative_to(output).as_posix(),
                index_sha256=sha(current/'science/index.json'),automated_review_sha256=sha(check),
                scientific_result_sha256=sha(current/'science/result.json'),supervision_sha256=sha(current/'supervision/result.json')))
            result.pop('active_child',None);result.update(latest_index=(current/'science/index.json').relative_to(output).as_posix(),
                latest_automated_review=check.relative_to(output).as_posix())
            write(output/'result.json',result);prior,prior_review = current,check;current=None
        timing(policy,admission['host_started_utc'],child_seconds,0)
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
                timing(policy,admission['host_started_utc'],child_seconds,0)
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
