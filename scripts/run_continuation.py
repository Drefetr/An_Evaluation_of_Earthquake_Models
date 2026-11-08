"""Execute a conductor-reviewed continuation stage on a fresh Linux runner.

An admission is a source/scope attestation, not an authentication mechanism.
No results are promoted to manuscript claims by this controller.
"""
import argparse
import datetime as dt
import hashlib
import json
import math
import os
from pathlib import Path
import secrets
import shutil
import subprocess
import sys
import urllib.request
import zipfile

ROOT = Path(__file__).resolve().parents[1]
JOINT_CONTINUATION_STAGES = ('joint-continuation-pilot', 'joint-continuation-campaign')
BUDGETED_STAGE = 'joint-budgeted-case'
HOST_BATCH_STAGE = 'joint-budgeted-host'
RECOVERY_HOST_STAGE = 'joint-recovery-host'
REMAINING_HOST_STAGE = 'joint-remaining-host'
LI_REPAIR_STAGE = 'li-constructor-repair'
LI_ORIGINAL_PILOT = ['original_li/LI_CA_M4_F2/LI/train',
                     'original_li/S0_uniform_null_seed410002/LI/test',
                     'original_li/S0_uniform_null_seed410002/OC/test']
READER_STAGES = {'reader-pilot': ('productivity_profiles', 'pilot'),
                 'reader-completion': ('s03', 'completion')}


def sha(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def write(path, value):
    with Path(path).open('x', encoding='utf-8') as stream:
        json.dump(value, stream, indent=2, allow_nan=False)
        stream.write('\n')


def inside(base, relative):
    path = (base / relative).resolve()
    if Path(relative).is_absolute() or not path.is_relative_to(base.resolve()):
        raise ValueError('Path outside declared directory')
    return path


def replay_paths(review):
    package = ROOT / 'reproduction/score_replay'
    registry = inside(ROOT, review.get('registry', 'reproduction/score_replay/cached_registry.json'))
    proposal = inside(ROOT, review.get('proposal', 'reproduction/score_replay/cached_pilot_proposal.json'))
    if not registry.is_relative_to(package) or proposal.parent != registry.parent:
        raise ValueError('Replay registry/proposal must share a declared package directory')
    return package, registry, proposal


def replay_roster(review, proposal, registry):
    phase = review['stage'].split('-')[1]
    selected = review['row_ids']
    by_id = {row['id']: row for row in registry['rows']}
    if len(by_id) != len(registry['rows']):
        raise ValueError('Duplicate registry identity')
    if not selected or len(selected) != len(set(selected)) or set(selected)-by_id.keys():
        raise ValueError('Invalid reviewed replay roster')
    pilot = proposal['row_ids']
    if not pilot or len(pilot) != len(set(pilot)) or set(pilot)-by_id.keys():
        raise ValueError('Invalid proposed pilot roster')
    if review['stage'] == LI_REPAIR_STAGE:
        repair = proposal.get('constructor_repair', {})
        if (review.get('constructor_repair') is not True or
                proposal.get('schema') != 'original_li_replay_pilot_v1' or
                pilot != LI_ORIGINAL_PILOT or selected != pilot[:1] or
                repair.get('retry_row_ids') != pilot[:1] or
                repair.get('original_pilot_roster_unchanged') is not True or
                [r['id'] for r in repair.get('retained_passed_rows', [])] != pilot[1:]):
            raise ValueError('Constructor repair admits only the one original failed LI row')
        return selected, by_id
    if 'constructor_repair' in review:
        raise ValueError('Constructor repair marker requires its dedicated stage')
    if phase == 'pilot' and selected != pilot:
        raise ValueError('Pilot differs from the predeclared source-review roster')
    if phase == 'completion':
        if review.get('pilot_output_review_passed') is not True:
            raise ValueError('Replay completion requires an independently accepted pilot')
        if selected != [r for r in by_id if r not in pilot]:
            raise ValueError('Completion must cover exactly the non-pilot rows')
    if phase not in ('pilot', 'completion'):
        raise ValueError('Unknown replay phase')
    return selected, by_id


def li_constructor_repair_evidence(review, proposal, registry):
    """Validate the unchanged two-row evidence; never score or treat the pilot as passed."""
    selected, by_id = replay_roster(review, proposal, registry)
    if review['stage'] != LI_REPAIR_STAGE:
        raise ValueError('Not a constructor repair admission')
    repair = proposal['constructor_repair']
    _, registry_path, proposal_path = replay_paths(review)
    archive = inside(ROOT, review['partial_archive'])
    audit_path = inside(ROOT, review['partial_output_review'])
    source_path = inside(ROOT, review['source_review_record'])
    audit, source = read(audit_path), read(source_path)
    if sha(archive) != review['partial_archive_sha256'] or sha(archive) != repair['failed_pilot_archive_sha256']:
        raise ValueError('Original partial LI archive changed')
    if (audit.get('schema') != 'independent_original_li_partial_pilot_audit_v1' or
            audit.get('passed') is not True or audit.get('original_pilot_passed') is not False or
            audit.get('requested_rows') != 3 or audit.get('accepted_rows') != 2 or audit.get('failed_rows') != 1 or
            audit.get('complete_pilot_union_accepted') is not False or
            audit.get('retained_passed_rows') != repair['retained_passed_rows'] or
            audit.get('retry_row_ids') != selected):
        raise ValueError('Independent partial review does not certify precisely the original two rows')
    for audit_key, repair_key in [('artifact_sha256','failed_pilot_archive_sha256'),
                                  ('result_sha256','failed_pilot_result_sha256'),
                                  ('launch_sha256','failed_pilot_launch_sha256')]:
        if audit.get(audit_key) != repair[repair_key]:
            raise ValueError('Partial review evidence identity differs')
    required_source = {'reproduction/score_replay/li_replay.py',
                       proposal_path.relative_to(ROOT).as_posix(), 'tests/test_li_replay_options.py'}
    if (source.get('schema') != 'independent_original_li_constructor_source_review_v1' or
            source.get('passed') is not True or source.get('partial_output_review_sha256') != sha(audit_path) or
            not required_source.issubset(source.get('source_sha256', {})) or
            any(sha(inside(ROOT, path)) != value for path, value in source['source_sha256'].items())):
        raise ValueError('Constructor source review does not bind the current source and partial review')
    with zipfile.ZipFile(archive) as saved:
        if len(saved.namelist()) != len(set(saved.namelist())):
            raise ValueError('Duplicate original partial archive member')
        def member(name, expected):
            raw = saved.read(name)
            if hashlib.sha256(raw).hexdigest() != expected:
                raise ValueError('Original partial member changed: '+name)
            return json.loads(raw)
        result = member('science/result.json', repair['failed_pilot_result_sha256'])
        launch = member('science/launch.json', repair['failed_pilot_launch_sha256'])
        old_sources = dict(proposal['source_sha256'], **{'li_replay.py':repair['original_replay_source_sha256']})
        if (launch.get('source_sha256') != old_sources or launch.get('registry_sha256') != sha(registry_path) or
                launch.get('registry_sha256') != proposal['registry_sha256'] or
                launch.get('mode') != 'pilot' or launch.get('row_ids') != LI_ORIGINAL_PILOT):
            raise ValueError('Original launch source/input/roster differs')
        if (result.get('passed') is not False or result.get('requested_rows') != 3 or
                result.get('completed_rows') != 3 or result.get('passed_rows') != 2 or
                [r['id'] for r in result.get('rows', [])] != LI_ORIGINAL_PILOT or
                result.get('full_registry') is not False or result.get('entire_task_complete') is not False):
            raise ValueError('Original partial result is not the declared failed pilot')
        for index, row in enumerate(result['rows']):
            name = 'science/rows/%05d/result.json' % index
            if row['result'] != name.removeprefix('science/'):
                raise ValueError('Original partial row member differs')
            report = member(name, row['sha256'])
            if report.get('id') != row['id']:
                raise ValueError('Original partial row identity differs')
            if index == 0:
                if (row.get('passed') is not False or report.get('passed') is not False or
                        report.get('status') != 'failed' or report.get('error') != 'Unexpected original objective option' or
                        'actual' in report):
                    raise ValueError('Retry row is not the original pre-objective constructor failure')
                continue
            retained = repair['retained_passed_rows'][index-1]
            actual = report.get('actual', {})
            array = actual.get('native_arrays', {})
            array_name = (Path(name).parent/'native_components.npz').as_posix()
            original = by_id[row['id']]
            if (row.get('passed') is not True or report.get('passed') is not True or
                    report.get('status') != 'replayed' or report.get('comparison', {}).get('passed') is not True or
                    retained['result_member'] != name or retained['result_sha256'] != row['sha256'] or
                    retained['native_arrays_member'] != array_name or array.get('path') != 'native_components.npz' or
                    array.get('sha256') != retained['native_arrays_sha256'] or
                    actual.get('raw_sha256') != original['raw']['sha256'] or
                    actual.get('state_sha256') != original['state']['sha256'] or
                    hashlib.sha256(saved.read(array_name)).hexdigest() != retained['native_arrays_sha256']):
                raise ValueError('Accepted original LI row or array evidence changed')
    return dict(schema='original_li_constructor_retry_evidence_v1',
                original_pilot_passed=False, complete_pilot_union_accepted=False,
                partial_archive_sha256=sha(archive), partial_output_review_sha256=sha(audit_path),
                source_review_sha256=sha(source_path), retained_passed_rows=repair['retained_passed_rows'],
                retry_row_ids=selected, original_pilot_row_ids=LI_ORIGINAL_PILOT)


def mandatory_sources(stage, review=None):
    paths = {'scripts/run_continuation.py','scripts/supervise_research.py',
             'scripts/tests/test_supervise_research_linux.py',
             'tests/test_continuation_controller.py',
             'engine/cpu_build.py','engine/stage2_followup/native_build.py',
             '.github/workflows/research-continuation.yml','requirements.txt','requirements-cpu.txt'}
    if stage in READER_STAGES:
        route, phase = READER_STAGES[stage]
        if review is None or review.get('reader_route') != route:
            raise ValueError('Public reader dispatch route is not declared')
        inherited = dict(review, stage=('cached-' if route == 'productivity_profiles' else 'regional-')+phase)
        paths.update(mandatory_sources(inherited['stage'], inherited))
        paths.update(('scripts/reproduce_cpu.py',
                      'validation/reproductions/score_replay_20261107/accepted_execution_index.json'))
        paths.update(review.get('reader_execution_evidence_sha256', {}))
    elif stage == REMAINING_HOST_STAGE:
        paths.update(mandatory_sources('joint-pilot', review))
        paths.update(('experiments/s04b_joint_execution/parallel_chunks.py',
                      'experiments/s04b_joint_remaining/case_driver.py',
                      'experiments/s04b_joint_remaining/host.py',
                      'experiments/s04b_joint_remaining/protocol.json',
                      'experiments/s04b_joint_remaining_audit/check.py',
                      'tests/test_joint_parallel_chunks.py',
                      'experiments/s04b_joint_audit/check.py',
                      'experiments/s04b_joint_nuisance_audit/audit.py',
                      'tests/test_joint_output_audit.py',
                      'tests/test_joint_recovery.py',
                      'tests/test_joint_execution_driver.py',
                      'tests/test_joint_saved_output_audit.py',
                      'tests/test_joint_remaining_controller.py',
                      review['source_review_record'], review['checker_source_review'],
                      review['operational_run_config_path'], review['prior_index_review']))
        for name in ('s04b_joint_remaining', 's04b_joint_remaining_audit'):
            paths.update(p.relative_to(ROOT).as_posix() for p in (ROOT/'experiments'/name).rglob('*')
                         if p.is_file() and p.suffix in ('.py', '.json', '.md'))
        for name in ('s04b_joint_execution', 's04b_joint_budgeted', 's04b_joint_recovery'):
            paths.update(p.relative_to(ROOT).as_posix() for p in (ROOT/'experiments'/name).glob('*.py'))
        paths.update(('experiments/s04b_joint_execution/operational_protocol.json',
                      'experiments/s04b_joint_execution/proposal.json'))
        paths.update(p.relative_to(ROOT).as_posix() for p in (ROOT/'tests').glob('test_joint_remaining*.py'))
        paths.update(review['remaining_evidence_sha256'])
    elif stage == RECOVERY_HOST_STAGE:
        # Recovery is an explicit operational amendment, never an approval of
        # the failed fixed-slot campaign. Retain its complete source lineage.
        inherited = dict(review, stage=HOST_BATCH_STAGE)
        paths.update(mandatory_sources(HOST_BATCH_STAGE, inherited))
        for name in ('s04b_joint_recovery', 's04b_joint_recovery_host'):
            package = ROOT/'experiments'/name
            paths.update(p.relative_to(ROOT).as_posix() for p in package.rglob('*')
                         if p.is_file() and p.suffix in ('.py','.json','.md'))
        paths.update(('tests/test_joint_recovery_controller.py',
                      'tests/test_joint_recovery_host.py'))
        paths.update(review['recovery_evidence_sha256'])
        paths.update(review['recovery_test_paths'])
        paths.update(review['recovery_checker_source_paths'])
    elif stage in ('joint-pilot','joint-full',BUDGETED_STAGE,HOST_BATCH_STAGE) + JOINT_CONTINUATION_STAGES:
        paths.add('tests/test_s04b_joint_nuisance.py')
        package = ROOT/'experiments/s04b_joint_nuisance'
        paths.update(p.relative_to(ROOT).as_posix() for p in package.iterdir()
                     if p.is_file() and p.suffix in ('.py','.cpp','.json'))
        if stage in JOINT_CONTINUATION_STAGES or stage in (BUDGETED_STAGE,HOST_BATCH_STAGE):
            execution = ROOT/'experiments/s04b_joint_execution'
            paths.update(p.relative_to(ROOT).as_posix() for p in execution.iterdir()
                         if p.is_file() and p.suffix in ('.py','.json'))
            paths.update(('tests/test_joint_execution_driver.py','tests/test_joint_parallel_chunks.py',
                          'experiments/s04b_joint_nuisance/pre_repair_source.zip'))
            paths.add(review['failed_archive'])
            paths.add(review['prior_index_review'] if 'prior_artifact_id' in review else review['training_review'])
            if stage in (BUDGETED_STAGE,HOST_BATCH_STAGE):
                budgeted = ROOT/'experiments/s04b_joint_budgeted'
                paths.update(p.relative_to(ROOT).as_posix() for p in budgeted.rglob('*')
                             if p.is_file() and p.suffix in ('.py','.json','.md'))
                paths.update(('tests/test_joint_budgeted_driver.py',review['source_review_record']))
            if stage == HOST_BATCH_STAGE:
                host = ROOT/'experiments/s04b_joint_host_batch'
                paths.update(p.relative_to(ROOT).as_posix() for p in host.iterdir()
                             if p.is_file() and p.suffix in ('.py','.json'))
                paths.update(('tests/test_joint_budgeted_batch.py','experiments/s04b_joint_audit/check.py',
                              'experiments/s04b_joint_nuisance_audit/audit.py','tests/test_joint_saved_output_audit.py',
                              review['checker_source_review'],review['operational_run_config_path']))
    elif stage in ('s02-pilot','s02-completion','initialmark-pilot','initialmark-completion'):
        paths.update(('reproduction/score_replay/s02_replay.py','tests/test_s02_score_replay.py'))
        package = ROOT/'reproduction/score_replay/s02'
        paths.update(p.relative_to(ROOT).as_posix() for p in package.rglob('*')
                     if p.is_file() and p.suffix in ('.py','.cpp','.json'))
        if stage.startswith('initialmark-'):
            paths.update(('reproduction/score_replay/initial_mark_replay.py','tests/test_initial_mark_replay.py'))
            package = ROOT/'reproduction/score_replay/initial_mark'
            paths.update(p.relative_to(ROOT).as_posix() for p in package.rglob('*')
                         if p.is_file() and p.suffix in ('.py','.json'))
    elif stage in ('cached-pilot','cached-completion','regional-pilot','regional-completion',
                   'inhibition-pilot','inhibition-completion','li-pilot','li-completion',LI_REPAIR_STAGE,
                   'blocks-pilot','blocks-completion','observed-pilot','observed-completion'):
        prefix = 'reproduction/score_replay/'
        package, registry, proposal = replay_paths(review or {})
        if stage.startswith('observed-'):
            names = ('__init__.py','core.py','inhibition_replay.py','observed_replay.py')
            paths.update((review or {}).get('fresh_artifacts_sha256',{}))
        elif stage.startswith('blocks-'):
            names = ('__init__.py','core.py','california_blocks_replay.py')
            paths.add('tests/test_partition_portable_source.py')
            paths.update((review or {}).get('fresh_artifacts_sha256',{}))
        elif stage.startswith('li-'):
            names = ('__init__.py','core.py','li_replay.py')
            if stage == LI_REPAIR_STAGE:
                paths.update(('tests/test_li_replay_options.py', review['partial_archive'],
                              review['partial_output_review'], review['source_review_record']))
        elif stage.startswith('regional-'):
            names = ('__init__.py','core.py','regional_build.py','regional_replay.py')
        elif stage.startswith('inhibition-'):
            names = ('__init__.py','core.py','inhibition_build.py','inhibition_replay.py')
        else:
            names = ('__init__.py','build.py','cached_native.py','core.py','inventory.py','replay.py')
        paths.update(prefix+name for name in names)
        paths.update(p.relative_to(ROOT).as_posix() for p in (registry, proposal, registry.parent/'input_manifest.json'))
        paths.update(prefix+name for name in ('protocol.json','cached_field_crosswalk.json'))
    else:
        raise ValueError('Unknown bounded continuation stage')
    return paths


def materialize_fresh_scores(review, output, required, require_arrays=True):
    """Copy only passed event-array evidence from already accepted local ZIPs."""
    records = {}
    for index, (relative, expected) in enumerate(review['fresh_artifacts_sha256'].items()):
        archive = inside(ROOT, relative)
        if sha(archive) != expected:
            raise ValueError('Fresh-score artifact changed')
        destination = output/'fresh'/str(index)
        with zipfile.ZipFile(archive) as source:
            names = source.namelist()
            if len(names) != len(set(names)):
                raise ValueError('Duplicate fresh-score artifact member')
            for name in names:
                if not name.startswith('science/rows/') or not name.endswith('/result.json'):
                    continue
                raw = source.read(name)
                report = json.loads(raw)
                identity = report.get('id')
                if identity not in required:
                    continue
                if identity in records or report.get('passed') is not True or report.get('status') != 'replayed':
                    raise ValueError('Fresh-score row duplicate or not passed')
                target = inside(destination, name)
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(raw)
                if require_arrays:
                    array = report['actual']['native_array_components']
                    array_name = (Path(name).parent/array['path']).as_posix()
                    array_target = inside(target.parent, array['path'])
                    if array_name not in names:
                        raise ValueError('Missing fresh event arrays')
                    data = source.read(array_name)
                    if hashlib.sha256(data).hexdigest() != array['sha256']:
                        raise ValueError('Fresh event array identity differs')
                    array_target.write_bytes(data)
                records[identity] = dict(result_path=str(target),sha256=sha(target))
    if set(records) != set(required):
        raise ValueError('Fresh-score evidence does not cover every required state')
    path = output/'fresh_scores.json'
    write(path,dict(rows=records))
    return path


def observed_continuation(review, output):
    """Prepare the reviewed CPU BLAS replay; no builder or score is invoked."""
    package, registry_path, proposal_path = replay_paths(review)
    proposal, registry = read(proposal_path), read(registry_path)
    selected, rows = replay_roster(review, proposal, registry)
    phase = review['stage'].split('-')[1]
    if review['stage'] not in ('observed-pilot','observed-completion'):
        raise ValueError('Unexpected observed phase')
    if proposal['registry_sha256'] != sha(registry_path) or proposal['input_manifest_sha256'] != sha(registry_path.parent/'input_manifest.json'):
        raise ValueError('Observed proposal input identity differs')
    budget = proposal.get('chunk_bytes')
    if type(budget) is not int or not 64*2**20 <= budget <= 512*2**20 or proposal.get('numeric_threads') != 2:
        raise ValueError('Observed proposal scratch/thread limits differ')
    wall = review['wall_cap_seconds']
    if isinstance(wall,bool) or not isinstance(wall,(int,float)) or not math.isfinite(wall) or wall<=0:
        raise ValueError('Observed wall allowance must be finite and positive')
    if phase == 'pilot' and wall > proposal['caps']['wall_seconds']:
        raise ValueError('Observed pilot exceeds frozen wall cap')
    if review['rss_cap_bytes'] > proposal['caps']['process_tree_rss_bytes'] or review['host_headroom_bytes'] < proposal['caps']['minimum_host_available_bytes']:
        raise ValueError('Observed memory/headroom envelope differs')
    fresh = materialize_fresh_scores(review,output,{rows[r]['fresh_score_row_id'] for r in selected},require_arrays=False)
    write(output/'rows.json',selected)
    admission = dict(proposal,passed=True,status='reviewed_workflow_admission',mode=phase,row_ids=selected,
                     numerical_lease=review['numerical_attempt_id'],expires_utc=review['expires_utc'],
                     fresh_scores_sha256=sha(fresh),numeric_threads=2)
    command = [sys.executable,'-B',str(package/'observed_replay.py'),'--registry',str(registry_path),
               '--fresh-scores',str(fresh),'--admission',str(output/'admission.json'),
               '--mode',phase,'--rows',str(output/'rows.json'),'--output',str(output/'science')]
    return admission,command


def observed_batch_passed(output, review):
    result = read(output/'science/result.json')
    selected = review['row_ids']
    if result.get('passed') is not True or result.get('mode') != review['stage'].split('-')[1]:
        raise ValueError('Observed child did not pass its requested phase')
    if [r.get('id') for r in result.get('rows',[])] != selected or any(r.get('passed') is not True or r.get('status')!='replayed' for r in result['rows']):
        raise ValueError('Observed child did not finish exact passed roster')
    if any(result.get(key)!=len(selected) for key in ('requested_rows','completed_rows','passed_rows')) or result.get('failed_rows')!=0:
        raise ValueError('Observed child terminal counts differ')
    _, registry, _ = replay_paths(review)
    if result.get('registry_sha256')!=sha(registry):
        raise ValueError('Observed child terminal registry differs')


def prior_artifact(review, output):
    artifact_id = int(review['pilot_artifact_id'])
    repository = 'Drefetr/An_Evaluation_of_Earthquake_Models'
    url = f'https://api.github.com/repos/{repository}/actions/artifacts/{artifact_id}/zip'
    request = urllib.request.Request(url, headers={
        'Authorization': 'Bearer ' + os.environ['GITHUB_TOKEN'],
        'Accept': 'application/vnd.github+json'})
    archive = output / 'prior_artifact.zip'
    class SafeRedirect(urllib.request.HTTPRedirectHandler):
        def redirect_request(self, req, fp, code, msg, headers, newurl):
            redirected = super().redirect_request(req, fp, code, msg, headers, newurl)
            if redirected is not None:
                redirected.remove_header('Authorization')
            return redirected
    opener = urllib.request.build_opener(SafeRedirect())
    with opener.open(request, timeout=120) as response, archive.open('xb') as stream:
        while chunk := response.read(1024 * 1024):
            stream.write(chunk)
    if sha(archive) != review['pilot_archive_sha256']:
        raise ValueError('Prior artifact identity differs from reviewed artifact')
    destination = output / 'prior'
    destination.mkdir()
    with zipfile.ZipFile(archive) as source:
        names = [i.filename for i in source.infolist()]
        if len(names) != len(set(names)) or sum(i.file_size for i in source.infolist()) > 2**30:
            raise ValueError('Invalid prior-artifact member roster or size')
        for info in source.infolist():
            inside(destination, info.filename)
            if (info.external_attr >> 16) & 0o170000 == 0o120000:
                raise ValueError('Artifact symlinks are not accepted')
        source.extractall(destination)
    return destination


def joint_continuation(review, output, token, prior):
    """Prepare the unchanged driver; this function never builds or evaluates."""
    from experiments.s04b_joint_execution import driver
    package = ROOT/'experiments/s04b_joint_execution'
    science = ROOT/'experiments/s04b_joint_nuisance'
    op, _ = driver.verify_protocol()
    resources = op['resources']
    if review.get('driver_source_review_passed') is not True or review.get('scheduler_source_review_passed') is not True:
        raise ValueError('Joint continuation requires independent driver and scheduler review')
    run_id = review.get('operational_run_id')
    config_hash = review.get('operational_run_config_sha256')
    if not isinstance(run_id,str) or not run_id.strip() or not isinstance(config_hash,str) or len(config_hash)!=64 or any(c not in '0123456789abcdef' for c in config_hash):
        raise ValueError('Separate operational run identity/config attestation is required')
    wall = review['wall_cap_seconds']
    if isinstance(wall,bool) or not isinstance(wall,(int,float)) or not math.isfinite(wall) or not 0 < wall <= resources['batch_wall_seconds']:
        raise ValueError('Joint batch wall allowance differs from frozen operational envelope')
    if review['rss_cap_bytes'] != resources['sampled_process_tree_rss_cap_bytes'] or review['host_headroom_bytes'] < resources['minimum_host_free_bytes']:
        raise ValueError('Joint continuation memory/headroom envelope differs')
    if bool(prior) != ('prior_artifact_id' in review) or 'pilot_artifact_id' in review:
        raise ValueError('Joint continuation requires its own exact prior-artifact route')
    phase = review['stage'].removeprefix('joint-continuation-')
    current = driver.source_identity()
    admission = dict(phase=phase,independent_review_passed=True,scheduler_review_passed=True,
                     external_supervision=True,source_sha256=current,
                     operational_protocol_sha256=sha(package/'operational_protocol.json'),
                     operational_run_id=run_id,operational_run_config_sha256=config_hash,
                     expires_utc=review['expires_utc'],numerical_attempt_id=review['numerical_attempt_id'],
                     lease_token_sha256=hashlib.sha256(token.encode()).hexdigest(),
                     threads=2,workers=1,sampled_process_tree_rss_cap_bytes=review['rss_cap_bytes'],
                     wall_seconds=wall,case_ids=review['case_ids'],
                     case_reservations_seconds=review['case_reservations_seconds'])
    command = [sys.executable,'-B',str(package/'driver.py'),'--output',str(output/'science'),
               '--admission',str(output/'admission.json')]
    if prior:
        index_path = inside(prior,review['prior_index_path'])
        index_review = inside(ROOT,review['prior_index_review'])
        accepted = read(index_review)
        if accepted.get('passed') is not True or sha(index_path) != review['prior_index_sha256'] or accepted.get('index_sha256') != sha(index_path):
            raise ValueError('Prior index lacks exact independent acceptance')
        index = read(index_path)
        if index['partial_case'] is not None:
            raise ValueError('A failed partial case requires separate reviewed disposition')
        if index['source_sha256'] != current or index['operational_protocol_sha256'] != admission['operational_protocol_sha256']:
            raise ValueError('Prior index source/envelope changed')
        driver.charged(index,op)
        if [r['case_id'] for r in index['cases']] != op['sequence'][:len(index['cases'])]:
            raise ValueError('Prior index is not the fixed completed prefix')
        admission.update(prior_index_sha256=sha(index_path),prior_review_sha256=sha(index_review))
        command += ['--prior-index',str(index_path),'--prior-review',str(index_review)]
    else:
        index = {'cases':[]}
    if driver.next_batch(index,op,review['case_ids']) != phase:
        raise ValueError('Joint batch phase differs from the exact next prefix')
    reservations = review['case_reservations_seconds']
    if set(reservations) != set(review['case_ids']) or any(isinstance(v,bool) or not isinstance(v,(int,float)) or not math.isfinite(v) or v<=0 for v in reservations.values()) or math.fsum(reservations.values()) > wall:
        raise ValueError('Invalid joint case reservations')
    if phase == 'campaign':
        if review.get('pilot_projection_review_passed') is not True:
            raise ValueError('Joint campaign requires an independently reviewed measured-pilot projection')
        admission.update(pilot_projection_review_passed=True,projection_sha256=review['projection_sha256'])
    archive = inside(ROOT,review['failed_archive'])
    policy = read(science/'checkpoint_repair.json')
    if sha(archive) != policy['failed_archive_sha256'] or sha(archive) != op['original_failure']['failed_archive_sha256']:
        raise ValueError('Original failed artifact changed')
    copied_archive = output/'original_failure.zip'
    shutil.copy2(archive,copied_archive)
    original = output/'original_failure'
    original.mkdir()
    with zipfile.ZipFile(copied_archive) as source:
        infos = source.infolist()
        if len({i.filename for i in infos}) != len(infos) or sum(i.file_size for i in infos)>2**30:
            raise ValueError('Invalid original-artifact member roster or size')
        for info in infos:
            inside(original,info.filename)
            if (info.external_attr>>16)&0o170000 == 0o120000:
                raise ValueError('Original-artifact symlinks are not accepted')
        source.extractall(original)
    build = output/'build'
    shutil.copytree(original/'build',build)
    library, receipt = build/'attenuation.so',build/'build_receipt.json'
    failed = read(original/'science/result.json')
    if sha(library) != failed['library_sha256'] or sha(receipt) != failed['build_receipt_sha256']:
        raise ValueError('Original native binary/build identity differs')
    admission.update(library_sha256=sha(library),build_receipt_sha256=sha(receipt))
    command += ['--library',str(library),'--build-receipt',str(receipt)]
    if not prior:
        audit = inside(ROOT,review['training_review'])
        evidence = {'failed_result_sha256':original/'science/result.json',
                    'checkpoint_sha256':original/'science'/(policy['case_id']+'.json'),
                    'attempts_sha256':original/'science'/(policy['case_id']+'.attempts.jsonl'),
                    'failed_archive_sha256':copied_archive,'audit_sha256':audit}
        if any(sha(path) != policy[key] for key,path in evidence.items()):
            raise ValueError('Original frozen training or review identity differs')
        checked = read(audit)
        if checked.get('passed') is not True or checked.get('scientific_pilot_passed') is not False:
            raise ValueError('Original review must accept partial training, not a completed pilot')
        admission['training_resume'] = dict(independent_review_passed=True,**{key:policy[key] for key in evidence})
        command += ['--resume-training',str(original/'science'),'--resume-review',str(audit),
                    '--resume-archive',str(copied_archive)]
    return admission,command


def joint_budgeted(review, output, token, prior, driver=None):
    """Explicit allocation transition; the failed forecast is never approved."""
    if driver is None:
        from experiments.s04b_joint_budgeted import driver
    if prior is None or review.get('stage') != BUDGETED_STAGE:
        raise ValueError('Budgeted continuation requires its exact predecessor artifact')
    if any(review.get(k) is not True for k in ('driver_source_review_passed',
                                               'scheduler_source_review_passed',
                                               'allocation_protocol_review_passed')):
        raise ValueError('Budgeted source, scheduler and allocation reviews are required')
    if 'pilot_projection_review_passed' in review:
        raise ValueError('A failed runtime forecast cannot authorize this separate mode')
    policy = driver.verify_protocol()
    resources = policy['resources']
    case = review['case_id']
    if review.get('case_ids') != [case]:
        raise ValueError('Exactly one budgeted case is required')
    slots = {s['case_id']: s for s in policy['fixed_slots']}
    wall = review['wall_cap_seconds']
    if (case not in slots or isinstance(wall,bool) or not isinstance(wall,(int,float))
            or not math.isfinite(wall) or wall != slots[case]['wall_seconds']):
        raise ValueError('Budgeted case wall cap differs from its frozen allocation')
    if (review['rss_cap_bytes'] != resources['sampled_process_tree_rss_cap_bytes']
            or review['host_headroom_bytes'] < resources['minimum_host_free_bytes']):
        raise ValueError('Budgeted resource envelope differs')
    index_path = inside(prior,review['prior_index_path'])
    checked_path = inside(ROOT,review['prior_index_review'])
    checked = read(checked_path); index = read(index_path)
    if (checked.get('passed') is not True or sha(index_path) != review['prior_index_sha256']
            or checked.get('index_sha256') != sha(index_path) or index['partial_case'] is not None):
        raise ValueError('Budgeted predecessor lacks complete exact independent acceptance')
    count = len(index['cases'])
    if (not 5 <= count < 80 or [r['case_id'] for r in index['cases']] != policy['sequence'][:count]
            or case != policy['sequence'][count]):
        raise ValueError('Budgeted case must be the next unchanged roster entry')
    build = output/'build'
    shutil.copytree(prior/'build',build)
    library, receipt = build/'attenuation.so', build/'build_receipt.json'
    original = policy['predecessor']
    if sha(library) != original['library_sha256'] or sha(receipt) != original['build_receipt_sha256']:
        raise ValueError('Budgeted continuation requires the original native/build bytes')
    original_op = read(ROOT/'experiments/s04b_joint_execution/operational_protocol.json')
    failed = inside(ROOT,review['failed_archive'])
    if sha(failed) != original_op['original_failure']['failed_archive_sha256']:
        raise ValueError('Original failed training artifact changed')
    shutil.copy2(failed,output/'original_failure.zip')
    package = ROOT/'experiments/s04b_joint_budgeted'
    admission = dict(mode='budgeted_campaign',independent_review_passed=True,
        scheduler_review_passed=True,external_supervision=True,source_sha256=driver.source_identity(),
        allocation_protocol_sha256=sha(package/'allocation_protocol.json'),
        transition_review_sha256=policy['transition_review_sha256'],
        prior_index_sha256=sha(index_path),prior_review_sha256=sha(checked_path),
        library_sha256=sha(library),build_receipt_sha256=sha(receipt),
        numerical_attempt_id=review['numerical_attempt_id'],expires_utc=review['expires_utc'],
        operational_run_id=review['operational_run_id'],
        operational_run_config_sha256=review['operational_run_config_sha256'],
        lease_token_sha256=hashlib.sha256(token.encode()).hexdigest(),threads=2,workers=1,
        sampled_process_tree_rss_cap_bytes=review['rss_cap_bytes'],case_id=case,
        case_ids=[case],wall_seconds=wall)
    command = [sys.executable,'-B',str(package/'driver.py'),'--output',str(output/'science'),
        '--admission',str(output/'admission.json'),'--library',str(library),
        '--build-receipt',str(receipt),'--prior-index',str(index_path),'--prior-review',str(checked_path)]
    return admission, command


def joint_batch_passed(output, review):
    result = read(output/'science/result.json')
    if result.get('passed') is not True or result.get('status') != 'batch_complete' or [r['case_id'] for r in result.get('cases',[])] != review['case_ids']:
        raise ValueError('Zero child exit did not certify the exact requested joint batch')
    if result.get('index_sha256') != sha(output/'science/index.json'):
        raise ValueError('Completed joint index identity differs')


def joint_host_batch(review, output, token, prior):
    """Prepare local-prefix orchestration; no fitting or automated acceptance here."""
    from experiments.s04b_joint_host_batch import batch
    from experiments.s04b_joint_budgeted import driver
    if prior is None or review['stage'] != HOST_BATCH_STAGE:
        raise ValueError('Host batch requires its exact accepted predecessor artifact')
    if any(review.get(key) is not True for key in ('driver_source_review_passed','scheduler_source_review_passed',
            'allocation_protocol_review_passed','host_batch_source_review_passed','checker_source_review_passed')):
        raise ValueError('Host/science/checker source reviews are required')
    if os.environ.get('CONTINUATION_HOST_TIMEOUT_MINUTES') != '240':
        raise ValueError('Host batch requires the explicit <=240-minute workflow route')
    policy, allocation = batch.verify_policy()
    if review['wall_cap_seconds'] != 13800 or review['rss_cap_bytes'] != 6442450944 or review['host_headroom_bytes'] < 2147483648:
        raise ValueError('Host resource envelope differs')
    started = os.environ['CONTINUATION_HOST_STARTED_UTC']
    batch.timing(policy,started,0,0)
    index_path = inside(prior,review['prior_index_path'])
    artifact = index_path.parent.parent
    if index_path != artifact/'science/index.json':
        raise ValueError('Host predecessor must retain its original artifact layout')
    index_review = inside(ROOT,review['prior_index_review'])
    checked = read(index_review)
    if checked.get('passed') is not True or checked.get('index_sha256') != sha(index_path) or sha(index_path) != review['prior_index_sha256']:
        raise ValueError('Host predecessor lacks exact acceptance')
    batch.next_cases(policy,allocation,review,read(index_path))
    config = inside(ROOT,review['operational_run_config_path'])
    if sha(config) != policy['shared_run']['config_sha256'] or review['operational_run_config_sha256'] != sha(config) or review['operational_run_id'] != policy['shared_run']['run_id']:
        raise ValueError('Host config/run identity differs')
    checker_review = inside(ROOT,review['checker_source_review'])
    if sha(checker_review) != review['checker_source_review_sha256']:
        raise ValueError('Checker source-review identity differs')
    shutil.copyfile(config,output/'run_config.json')
    admission = dict(mode='fixed_host_batch',source_sha256=batch.source_identity(),
        scientific_source_sha256=driver.source_identity(),batch_policy_sha256=sha(ROOT/'experiments/s04b_joint_host_batch/batch_policy.json'),
        shared_run=policy['shared_run'],batch_id=review['batch_id'],case_ids=review['case_ids'],child_attempt_ids=review['child_attempt_ids'],
        numerical_attempt_id=review['numerical_attempt_id'],lease_token_sha256=hashlib.sha256(token.encode()).hexdigest(),
        prior_index_sha256=sha(index_path),prior_review_sha256=sha(index_review),expires_utc=review['expires_utc'],
        host_started_utc=started,rss_cap_bytes=review['rss_cap_bytes'],host_headroom_bytes=review['host_headroom_bytes'],
        checker_source_review_sha256=sha(checker_review),host_batch_source_review_passed=True,checker_source_review_passed=True,
        source_commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),
        reviewed_files_sha256=review['reviewed_files_sha256'],conductor_review=review)
    command = [sys.executable,'-B',str(ROOT/'experiments/s04b_joint_host_batch/batch.py'),
        '--admission',str(output/'admission.json'),'--prior',str(artifact),'--prior-review',str(index_review),
        '--config',str(output/'run_config.json'),'--checker-review',str(checker_review),
        '--failed-archive',str(inside(ROOT,review['failed_archive'])),'--output',str(output/'host')]
    return admission,command


def host_batch_passed(output, review):
    result = read(output/'host/result.json')
    if (result.get('passed') is not True or result.get('status') != 'host_batch_complete' or
            [row['case_id'] for row in result.get('children',[])] != review['case_ids'] or
            result.get('live_agent_review') is not False or result.get('final_batch_agent_review_required') is not True):
        raise ValueError('Host batch did not complete its exact reviewed suffix')
    last = result['children'][-1]
    if sha(inside(output/'host',result['latest_index'])) != last['index_sha256']:
        raise ValueError('Host final accepted index changed')


def joint_remaining_host(review, output, token, prior, host=None, driver=None):
    """Prepare untouched cases; the capped predecessor is never retried."""
    if host is None:
        from experiments.s04b_joint_remaining import host
    if driver is None:
        from experiments.s04b_joint_remaining import case_driver as driver
    if review.get('stage') != REMAINING_HOST_STAGE or any(review.get(k) is not True for k in (
            'remaining_protocol_review_passed', 'host_batch_source_review_passed', 'checker_source_review_passed')):
        raise ValueError('Untouched-case protocol, host and checker reviews are required')
    if os.environ.get('CONTINUATION_HOST_TIMEOUT_MINUTES') != '240':
        raise ValueError('Untouched cases require the bounded host workflow')
    policy_path = ROOT/'experiments/s04b_joint_remaining/protocol.json'
    policy = read(policy_path)
    group = next((g for g in policy['actual_hosts'] if g['host'] == review['batch_id']), None)
    if group is None or review['case_ids'] != group['case_ids']:
        raise ValueError('Untouched host roster differs')
    window = group['outer_maximum_seconds']-group['upload_reserve_seconds']
    resource, shared = policy['resources'], policy['shared_run']
    if (not 0 < window <= 13800 or review['wall_cap_seconds'] != window or
            review['rss_cap_bytes'] != resource['sampled_process_tree_rss_cap_bytes'] or
            review['host_headroom_bytes'] < resource['minimum_host_free_bytes']):
        raise ValueError('Untouched host resource envelope differs')
    config = inside(ROOT, review['operational_run_config_path'])
    if (sha(config) != shared['config_sha256'] or review['operational_run_config_sha256'] != sha(config) or
            review['operational_run_id'] != shared['run_id'] or review['expires_utc'] != shared['expires_utc']):
        raise ValueError('Untouched continuation cannot extend shared limits')
    source_review = inside(ROOT, review['source_review_record'])
    checker_review = inside(ROOT, review['checker_source_review'])
    if sha(source_review) != review['source_review_sha256'] or sha(checker_review) != review['checker_source_review_sha256']:
        raise ValueError('Untouched source-review identity changed')
    for relative, expected in review['remaining_evidence_sha256'].items():
        if sha(inside(ROOT, relative)) != expected:
            raise ValueError('Untouched-case evidence changed: '+relative)
    failed = policy['immutable_failure_reference']
    archive = inside(ROOT, failed['archive'])
    if sha(archive) != failed['archive_sha256']:
        raise ValueError('Original terminal failure archive changed')
    build = output/'build'
    build.mkdir(exist_ok=False)
    with zipfile.ZipFile(archive) as saved:
        for key, filename, pin in (
                ('library_member', 'attenuation.so', policy['original_native']['library_sha256']),
                ('build_receipt_member', 'build_receipt.json', policy['original_native']['build_receipt_sha256'])):
            if saved.namelist().count(failed[key]) != 1:
                raise ValueError('Missing or duplicated original native member')
            data = saved.read(failed[key])
            if hashlib.sha256(data).hexdigest() != pin:
                raise ValueError('Original native member identity changed')
            (build/filename).write_bytes(data)
        if review['batch_id'] == 1:
            if prior is not None or saved.namelist().count(failed['index_member']) != 1:
                raise ValueError('Initial untouched pilot must use the exact terminal failed index')
            data = saved.read(failed['index_member'])
            if hashlib.sha256(data).hexdigest() != failed['index_sha256']:
                raise ValueError('Original failed index identity changed')
            index_path = output/'initial_failed_index.json'
            index_path.write_bytes(data)
        else:
            if prior is None or review.get('prior_index_path') != 'host/index.json':
                raise ValueError('Later untouched host requires the prior compact index')
            index_path = inside(prior, review['prior_index_path'])
    index_review = inside(ROOT, review['prior_index_review'])
    if sha(index_path) != review['prior_index_sha256'] or sha(index_review) != review['prior_review_sha256']:
        raise ValueError('Untouched predecessor or its review changed')
    if review['batch_id'] == 1 and (review['prior_index_review'] != failed['review'] or
                                   sha(index_review) != failed['review_sha256']):
        raise ValueError('Initial failed index lacks its independent disposition review')
    admission = dict(mode='remaining_host_batch', source_sha256=host.source_identity(),
        scientific_source_sha256=driver.source_identity(), protocol_sha256=sha(policy_path),
        scientific_protocol_sha256=policy['scientific_protocol_sha256'], shared_run=shared,
        batch_id=review['batch_id'], case_ids=review['case_ids'], child_attempt_ids=review['child_attempt_ids'],
        numerical_attempt_id=review['numerical_attempt_id'], lease_token_sha256=hashlib.sha256(token.encode()).hexdigest(),
        prior_index_sha256=sha(index_path), prior_review_sha256=sha(index_review), expires_utc=review['expires_utc'],
        prior_archive_sha256=review.get('prior_archive_sha256',failed['archive_sha256']),
        prior_artifact_id=review.get('prior_artifact_id'),
        host_started_utc=os.environ['CONTINUATION_HOST_STARTED_UTC'], execution_window_seconds=window,
        rss_cap_bytes=review['rss_cap_bytes'], host_headroom_bytes=review['host_headroom_bytes'],
        library_sha256=sha(build/'attenuation.so'), build_receipt_sha256=sha(build/'build_receipt.json'),
        source_review_sha256=sha(source_review), checker_source_review_sha256=sha(checker_review),
        host_batch_source_review_passed=True, checker_source_review_passed=True,
        source_commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),
        reviewed_files_sha256=review['reviewed_files_sha256'], conductor_review=review)
    command = [sys.executable,'-B','-m','experiments.s04b_joint_remaining.host',
        '--admission',str(output/'admission.json'),'--output',str(output/'host'),
        '--prior-index',str(index_path),'--prior-review',str(index_review),
        '--config',str(config),'--source-review',str(source_review),'--checker-review',str(checker_review),
        '--library',str(build/'attenuation.so'),'--build-receipt',str(build/'build_receipt.json')]
    return admission, command


def remaining_host_passed(output, review):
    result = read(output/'host/result.json')
    if (result.get('host_execution_passed') is not True or result.get('status') != 'host_batch_complete' or
            result.get('scientific_completion') is not False or
            [v['case_id'] for v in result.get('children', [])] != review['case_ids'] or
            result.get('live_agent_review') is not False or result.get('final_batch_agent_review_required') is not True or
            result.get('latest_index') != 'index.json' or sha(output/'host/index.json') != result.get('index_sha256')):
        raise ValueError('Untouched host did not certify its exact execution scope and retained unknown')


def joint_recovery_host(review, output, token, prior, batch=None, driver=None):
    """Prepare the separately reviewed partial-fit recovery; no science here."""
    if batch is None:
        from experiments.s04b_joint_recovery_host import batch
    if driver is None:
        from experiments.s04b_joint_recovery import driver
    if prior is None or review.get('stage') != RECOVERY_HOST_STAGE:
        raise ValueError('Recovery requires its explicit predecessor artifact route')
    if any(review.get(key) is not True for key in (
            'driver_source_review_passed','scheduler_source_review_passed',
            'recovery_protocol_review_passed','host_batch_source_review_passed',
            'checker_source_review_passed')):
        raise ValueError('Recovery protocol, source and checker reviews are required')
    if 'pilot_projection_review_passed' in review:
        raise ValueError('Recovery cannot approve the superseded runtime projection')
    if os.environ.get('CONTINUATION_HOST_TIMEOUT_MINUTES') != '240':
        raise ValueError('Recovery requires the explicit <=240-minute workflow route')
    policy, recovery = batch.verify_policy()
    groups = {row['host']: row for row in recovery['actual_hosts']}
    group = groups.get(review['batch_id'])
    if group is None:
        raise ValueError('Recovery host is not in the fixed remaining schedule')
    window = group['outer_maximum_seconds']-group['upload_reserve_seconds']
    resources = recovery['resources']
    if (review['wall_cap_seconds'] != window or not 0 < window <= 13800 or
            review['rss_cap_bytes'] != resources['sampled_process_tree_rss_cap_bytes'] or
            review['host_headroom_bytes'] < resources['minimum_host_free_bytes']):
        raise ValueError('Recovery resource envelope differs from its fixed allocation')
    index_path = inside(prior,review['prior_index_path'])
    artifact = index_path.parent.parent
    if index_path != artifact/'science/index.json':
        raise ValueError('Recovery predecessor must retain its original artifact layout')
    index_review = inside(ROOT,review['prior_index_review'])
    if sha(index_path) != review['prior_index_sha256']:
        raise ValueError('Recovery predecessor index changed')
    # This verifies the exact failed first index or a later passed v2 index,
    # including the mandatory independent pilot gate and fixed prefix.
    batch.next_cases(policy,recovery,review,read(index_path),read(index_review))
    config = inside(ROOT,review['operational_run_config_path'])
    shared = recovery['shared_run']
    if (sha(config) != shared['config_sha256'] or
            review['operational_run_config_sha256'] != sha(config) or
            review['operational_run_id'] != shared['run_id'] or
            review['expires_utc'] != shared['expires_utc']):
        raise ValueError('Recovery cannot extend the shared run or its deadline')
    checker_review = inside(ROOT,review['checker_source_review'])
    source_review = inside(ROOT,review['source_review_record'])
    if (sha(checker_review) != review['checker_source_review_sha256'] or
            sha(source_review) != review['source_review_sha256']):
        raise ValueError('Recovery source-review identity differs')
    for relative, expected in review['recovery_evidence_sha256'].items():
        if sha(inside(ROOT,relative)) != expected:
            raise ValueError('Recovery evidence changed: '+relative)
    started = os.environ['CONTINUATION_HOST_STARTED_UTC']
    shutil.copyfile(config,output/'run_config.json')
    admission = dict(mode='recovery_host_batch',source_sha256=batch.source_identity(),
        scientific_source_sha256=driver.source_identity(),
        batch_policy_sha256=sha(ROOT/'experiments/s04b_joint_recovery_host/batch_policy.json'),
        recovery_protocol_sha256=sha(ROOT/'experiments/s04b_joint_recovery/recovery_protocol.json'),
        shared_run=shared,batch_id=review['batch_id'],case_ids=review['case_ids'],
        child_attempt_ids=review['child_attempt_ids'],numerical_attempt_id=review['numerical_attempt_id'],
        lease_token_sha256=hashlib.sha256(token.encode()).hexdigest(),
        prior_index_sha256=sha(index_path),prior_review_sha256=sha(index_review),
        expires_utc=review['expires_utc'],host_started_utc=started,execution_window_seconds=window,
        rss_cap_bytes=review['rss_cap_bytes'],host_headroom_bytes=review['host_headroom_bytes'],
        checker_source_review_sha256=sha(checker_review),host_batch_source_review_passed=True,
        checker_source_review_passed=True,source_review_sha256=sha(source_review),
        source_commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),
        reviewed_files_sha256=review['reviewed_files_sha256'],conductor_review=review)
    command = [sys.executable,'-B','-m','experiments.s04b_joint_recovery_host.batch',
        '--admission',str(output/'admission.json'),'--prior',str(artifact),
        '--prior-review',str(index_review),'--config',str(output/'run_config.json'),
        '--checker-review',str(checker_review),'--failed-archive',str(inside(ROOT,review['failed_archive'])),
        '--output',str(output/'host')]
    return admission,command


def reader_dispatch_plan(review, output):
    """Validate a nonduplicate public-reader request; no build/evaluation here."""
    from scripts import reproduce_cpu as reader
    route, phase = READER_STAGES[review['stage']]
    if review.get('reader_route') != route or any(k in review for k in ('pilot_artifact_id','prior_artifact_id')):
        raise ValueError('Reader dispatch uses its declared route and local published evidence only')
    wall = review['wall_cap_seconds']
    if isinstance(wall, bool) or not isinstance(wall, (int, float)) or not math.isfinite(wall) or not 0 < wall <= 14400:
        raise ValueError('Reader wall cap must be finite, positive and within the workflow allowance')
    args = argparse.Namespace(route=route,phase=phase,rows=None,wall_seconds=wall,
        rss_mib=review['rss_cap_bytes']/2**20,headroom_mib=review['host_headroom_bytes']/2**20,
        pilot_output=None,pilot_review=None)
    plan = reader.make_plan(args)
    if (plan['row_ids'] != review['row_ids'] or plan['registry'] != review['registry']
            or plan['proposal'] != review['proposal']):
        raise ValueError('Reviewed public-reader request differs from exact frozen source/roster')
    for name, expected in plan['pins'].items():
        if review['reviewed_files_sha256'].get(name) != expected:
            raise ValueError('Reader plan is not covered by source admission: '+name)
    existing = set(); evidence = {}
    for archive in sorted((reader.PUBLISHED/route).glob('*.zip')):
        record = reader.published_review(route,archive.stem)
        evidence[record['archive']] = record['sha256']
        for item in record['reviews']:
            evidence[item['path']] = item['sha256']
        if record['acceptance_index']:
            item = record['acceptance_index']; evidence[item['path']] = item['sha256']
        result = record['result']
        if result.get('passed') is not True:
            raise ValueError('Published route execution has not passed')
        for row in result.get('rows', []):
            if row.get('passed') is not True:
                raise ValueError('Published route contains a failed row')
            if row['id'] in existing:
                raise ValueError('Duplicate published route row')
            existing.add(row['id'])
    if review.get('reader_execution_evidence_sha256') != evidence:
        raise ValueError('Published execution inventory differs from reviewed nonduplicate evidence')
    if set(plan['row_ids']) & existing:
        raise ValueError('Public reader would repeat an already passed published row')
    if phase == 'completion':
        proposal = read(ROOT/review['proposal'])
        if existing != set(proposal['row_ids']) or review.get('pilot_output_review_passed') is not True:
            raise ValueError('Reader completion requires exactly the accepted pilot and unexecuted remainder')
    elif existing:
        raise ValueError('Fresh reader pilot cannot have a prior passed route execution')
    command = [sys.executable,'-B',str(ROOT/'scripts/reproduce_cpu.py'),'run',
        '--route',route,'--phase',phase,'--output',str(output/'reader'),
        '--wall-seconds',str(wall),'--rss-mib',str(review['rss_cap_bytes']/2**20),
        '--headroom-mib',str(review['host_headroom_bytes']/2**20)]
    return plan,command


def reader_batch_passed(output, review):
    """A zero process exit alone cannot certify a reader execution."""
    base=output/'reader'; result=read(base/'reader_result.json'); science=read(base/'science/result.json')
    supervision=read(base/'supervision/result.json')
    route,phase=READER_STAGES[review['stage']]
    if (result.get('passed') is not True or result.get('route')!=route or result.get('phase')!=phase
            or result.get('requested_ids')!=review['row_ids'] or result.get('retained_result_ids')!=review['row_ids']
            or result.get('result_sha256')!=sha(base/'science/result.json')
            or result.get('supervision_sha256')!=sha(base/'supervision/result.json')
            or supervision.get('status')!='passed' or science.get('passed') is not True
            or science.get('mode')!=phase or [r['id'] for r in science.get('rows',[])]!=review['row_ids']):
        raise ValueError('Reader did not certify exact requested output and supervised terminal state')
    return dict(passed=True,scope='Workflow custody check; public reader output is not independently accepted here',
                reader_result_sha256=sha(base/'reader_result.json'),row_ids=review['row_ids'])


def execute_reader_dispatch(review, output, expires):
    plan,command=reader_dispatch_plan(review,output)
    remaining=(expires-dt.datetime.now(dt.timezone.utc)).total_seconds()
    if remaining < review['wall_cap_seconds']:
        raise ValueError('Lease expires before entire public-reader allowance')
    # The reader owns compilation and the only scientific supervisor.
    child_environment={k:v for k,v in os.environ.items() if k not in (
        'GITHUB_TOKEN','GH_TOKEN','ACTIONS_RUNTIME_TOKEN','ACTIONS_ID_TOKEN_REQUEST_TOKEN')}
    write(output/'reader_plan.json',plan)
    write(output/'reader_command.json',dict(command=command,source_plan_sha256=sha(output/'reader_plan.json'),
        conductor_admission_sha256=sha(output/'conductor_review.json'),numerical_attempt_id=review['numerical_attempt_id'],
        github_token_forwarded=any(k in child_environment for k in ('GITHUB_TOKEN','GH_TOKEN')),
        resource_owner='scripts/reproduce_cpu.py -> scripts/supervise_research.py',nested_scientific_supervisor=False))
    process=subprocess.run(command,cwd=ROOT,env=child_environment)
    result=dict(passed=False,returncode=process.returncode,
        scope='All partial public-reader outputs retained; no numerical acceptance')
    if process.returncode==0:
        try:
            result=reader_batch_passed(output,review)
        except (ValueError,KeyError,OSError) as exc:
            result.update(error_type=type(exc).__name__,error=str(exc))
    write(output/'reader_dispatch_result.json',result)
    return 0 if result['passed'] else process.returncode or 1


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--admission', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if not sys.platform.startswith('linux'):
        raise RuntimeError('This production controller requires the reviewed Linux supervisor')
    review = read(args.admission)
    if review['independent_source_review'] != 'passed':
        raise ValueError('Independent source review has not passed')
    stage = review['stage']
    if stage in READER_STAGES and any(k in review for k in ('pilot_artifact_id','prior_artifact_id')):
        raise ValueError('Public reader dispatch does not download remote artifacts')
    missing = mandatory_sources(stage, review)-review['reviewed_files_sha256'].keys()
    if missing:
        raise ValueError('Incomplete reviewed-source coverage: '+str(sorted(missing)))
    if int(os.environ.get('GITHUB_RUN_ATTEMPT','1')) != review['allowed_github_run_attempt']:
        raise ValueError('Workflow retry requires a fresh conductor numerical admission')
    for relative, expected in review['reviewed_files_sha256'].items():
        if sha(inside(ROOT, relative)) != expected:
            raise ValueError('Reviewed source changed: ' + relative)
    now = dt.datetime.now(dt.timezone.utc)
    expires = dt.datetime.fromisoformat(review['expires_utc'])
    if now >= expires:
        raise ValueError('Expired numerical admission')
    output = args.output.resolve()
    if output.is_relative_to(ROOT):
        raise ValueError('Production output must be outside checkout')
    output.mkdir(parents=True, exist_ok=False)
    write(output / 'conductor_review.json', review)
    token = secrets.token_hex(32)
    environment = {key: '2' for key in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS',
                   'MKL_NUM_THREADS','NUMEXPR_NUM_THREADS','BLIS_NUM_THREADS')}
    environment['PYTHONDONTWRITEBYTECODE'] = '1'
    environment['JOINT_NUMERICAL_LEASE_TOKEN'] = token
    environment['NUMERICAL_LEASE_TOKEN'] = token
    os.environ.update(environment)
    if stage in JOINT_CONTINUATION_STAGES or stage in (BUDGETED_STAGE,HOST_BATCH_STAGE,RECOVERY_HOST_STAGE,REMAINING_HOST_STAGE):
        prior = prior_artifact(dict(pilot_artifact_id=review['prior_artifact_id'],
                                   pilot_archive_sha256=review['prior_archive_sha256']), output) if 'prior_artifact_id' in review else None
    else:
        prior = prior_artifact(review, output) if 'pilot_artifact_id' in review else None
    # Download credentials are unnecessary in compilers or numerical children.
    os.environ.pop('GITHUB_TOKEN', None)
    if stage in READER_STAGES:
        return execute_reader_dispatch(review,output,expires)
    if stage == REMAINING_HOST_STAGE:
        admission,command = joint_remaining_host(review,output,token,prior)
    elif stage == RECOVERY_HOST_STAGE:
        admission,command = joint_recovery_host(review,output,token,prior)
    elif stage == HOST_BATCH_STAGE:
        admission,command = joint_host_batch(review,output,token,prior)
    elif stage == BUDGETED_STAGE:
        admission,command = joint_budgeted(review,output,token,prior)
    elif stage in JOINT_CONTINUATION_STAGES:
        admission,command = joint_continuation(review,output,token,prior)
    elif stage in ('joint-pilot', 'joint-full'):
        package = ROOT / 'experiments/s04b_joint_nuisance'
        sys.path.insert(0, str(package))
        import run as joint
        if prior:
            build = inside(prior, review['pilot_build_directory'])
        else:
            from engine.cpu_build import build_shared
            build = output / 'build'
            build_shared(package / 'attenuation.cpp', build, dependency_root=package)
        receipt = build / 'build_receipt.json'
        library = build / 'attenuation.so'
        phase = stage.split('-')[1]
        admission = dict(phase=phase, independent_review_passed=True,
                        expires_utc=review['expires_utc'], source_sha256=joint.source_identity(),
                        protocol_sha256=sha(package/'protocol.json'), input_pins_sha256=sha(package/'input_pins.json'),
                        lease_token_sha256=hashlib.sha256(token.encode()).hexdigest(),
                        library_sha256=sha(library), build_receipt_sha256=sha(receipt),
                        threads=2, sampled_process_tree_rss_cap_bytes=review['rss_cap_bytes'],
                        wall_seconds=review['wall_cap_seconds'], numerical_attempt_id=review['numerical_attempt_id'])
        command = [sys.executable,'-B',str(package/'run.py'),'--phase',phase,
                   '--output',str(output/'science'),'--library',str(library),
                   '--build-receipt',str(receipt),'--admission',str(output/'admission.json')]
        if prior:
            admission.update(pilot_result_sha256=review['pilot_result_sha256'],
                             pilot_output_review_passed=review['pilot_output_review_passed'])
            command += ['--pilot',str(inside(prior,review['pilot_science_directory']))]
    elif stage in ('s02-pilot','s02-completion','initialmark-pilot','initialmark-completion'):
        if stage.startswith('initialmark-'):
            from reproduction.score_replay import initial_mark_replay as replay_module
            package = ROOT/'reproduction/score_replay/initial_mark'
        else:
            from reproduction.score_replay import s02_replay as replay_module
            package = ROOT/'reproduction/score_replay/s02'
        runner_path = Path(replay_module.__file__)
        protocol = read(package/'protocol.json')
        phase = stage.split('-')[1]
        if (phase == 'completion') != bool(prior):
            raise ValueError('Case replay completion requires the exact accepted pilot artifact')
        build = inside(prior, review['pilot_build_directory']) if prior else output/'build'
        if not prior:
            subprocess.run([sys.executable,'-B',str(runner_path),
                            'build','--output',str(build)],cwd=ROOT,check=True)
        receipt = build/'build_receipt.json'
        library = build/'components.so'
        selected = protocol['pilot'] if phase == 'pilot' else [c for c in protocol['roster'] if c not in protocol['pilot']]
        if review['case_ids'] != selected:
            raise ValueError('Reviewed case roster differs from its frozen protocol')
        admission = dict(passed=True,independent_review_passed=True,mode=phase,
                         source_sha256=replay_module.source_identity(),protocol_sha256=sha(package/'protocol.json'),
                         numerical_attempt_id=review['numerical_attempt_id'],
                         lease_token_sha256=hashlib.sha256(token.encode()).hexdigest(),
                         expires_utc=review['expires_utc'],case_ids=selected,threads=2,
                         wall_seconds=review['wall_cap_seconds'],sampled_process_tree_rss_cap_bytes=review['rss_cap_bytes'],
                         library_sha256=sha(library),build_receipt_sha256=sha(receipt))
        command = [sys.executable,'-B',str(runner_path),'run','--mode',phase,
                   '--library',str(library),'--build-receipt',str(receipt),
                   '--admission',str(output/'admission.json'),'--output',str(output/'science')]
        if prior:
            admission.update(pilot_result_sha256=review['pilot_result_sha256'],
                             pilot_output_review_passed=review['pilot_output_review_passed'])
            command += ['--pilot',str(inside(prior,review['pilot_science_directory']))]
    elif stage in ('observed-pilot','observed-completion'):
        admission,command = observed_continuation(review,output)
    elif stage in ('cached-pilot', 'cached-completion', 'regional-pilot', 'regional-completion',
                   'inhibition-pilot', 'inhibition-completion','li-pilot','li-completion',LI_REPAIR_STAGE,
                   'blocks-pilot','blocks-completion'):
        package, registry_path, proposal_path = replay_paths(review)
        regional = stage.startswith('regional-')
        inhibition = stage.startswith('inhibition-')
        li = stage.startswith('li-')
        blocks = stage.startswith('blocks-')
        builder, runner = (('california_blocks_replay.py','california_blocks_replay.py') if blocks else
                           ('li_replay.py','li_replay.py') if li else
                           ('regional_build.py','regional_replay.py') if regional else
                           ('inhibition_build.py','inhibition_replay.py') if inhibition else ('build.py','replay.py'))
        proposal = read(proposal_path)
        registry = read(registry_path)
        selected, by_id = replay_roster(review, proposal, registry)
        if stage == LI_REPAIR_STAGE:
            evidence = li_constructor_repair_evidence(review, proposal, registry)
            write(output/'constructor_repair_evidence.json', evidence)
            shutil.copyfile(inside(ROOT,review['partial_archive']), output/'original_failure.zip')
        build = output / 'build'
        subprocess.run([sys.executable,'-B',str(package/builder)]+(['--build'] if li or blocks else [])+[
                        '--registry',str(registry_path),'--output',str(build)],cwd=ROOT,check=True)
        libraries = read(build/'libraries.json')
        phase = 'pilot' if stage == LI_REPAIR_STAGE else stage.split('-')[1]
        used = {'annual','sequence'} if blocks else {'core','competitive'} if regional else {'cpu','radial'} if inhibition else {by_id[row]['adapter'] for row in selected} if not li else set()
        receipts = {'li':sha(libraries['library']['build_receipt_path'])} if li else {k:sha(libraries['libraries'][k]['build_receipt_path']) for k in sorted(used)}
        write(output/'rows.json',selected)
        admission = dict(proposal, passed=True, status='reviewed_workflow_admission', mode=phase, row_ids=selected,
                         numerical_lease=review['numerical_attempt_id'],
                         libraries_sha256=sha(build/'libraries.json'), expires_utc=review['expires_utc'], numeric_threads=2,
                         build_receipts_sha256=receipts)
        if stage == LI_REPAIR_STAGE:
            admission['constructor_repair_evidence_sha256'] = sha(output/'constructor_repair_evidence.json')
            admission['original_partial_archive_sha256'] = sha(output/'original_failure.zip')
        command = [sys.executable,'-B',str(package/runner),'--mode',phase,
                   '--registry',str(registry_path),
                   '--libraries',str(build/'libraries.json'),'--admission',str(output/'admission.json'),
                   '--rows',str(output/'rows.json'),'--output',str(output/'science')]
        if blocks:
            fresh = materialize_fresh_scores(review,output,{by_id[row]['fresh_score_row_id'] for row in selected})
            admission['fresh_scores_sha256'] = sha(fresh)
            command += ['--fresh-scores',str(fresh)]
    else:
        raise ValueError('Unknown bounded continuation stage')
    write(output/'admission.json',admission)
    remaining = (expires-dt.datetime.now(dt.timezone.utc)).total_seconds()
    wall_cap = review['wall_cap_seconds']
    if stage in (HOST_BATCH_STAGE,RECOVERY_HOST_STAGE,REMAINING_HOST_STAGE):
        window = admission.get('execution_window_seconds',13800)
        host_end = dt.datetime.fromisoformat(admission['host_started_utc'])+dt.timedelta(seconds=window)
        wall_cap = min(wall_cap,(host_end-dt.datetime.now(dt.timezone.utc)).total_seconds(),remaining)
        if wall_cap <= 0:
            raise ValueError('Host setup exhausted its reserved execution window')
    elif remaining < wall_cap:
        raise ValueError('Lease expires before entire approved stage allowance')
    spec = dict(command=command,cwd=str(ROOT),output=str(output/'supervision'),env=environment,
                wall_cap_seconds=wall_cap,rss_cap_bytes=review['rss_cap_bytes'],
                host_headroom_bytes=review['host_headroom_bytes'],sample_seconds=.5)
    write(output/'supervisor_spec.json',spec)
    result = subprocess.run([sys.executable,'-B',str(ROOT/'scripts/supervise_research.py'),
                             str(output/'supervisor_spec.json')],cwd=ROOT)
    if (stage in JOINT_CONTINUATION_STAGES or stage == BUDGETED_STAGE) and result.returncode == 0:
        joint_batch_passed(output,review)
    if stage in ('observed-pilot','observed-completion') and result.returncode == 0:
        observed_batch_passed(output,review)
    if stage in (HOST_BATCH_STAGE,RECOVERY_HOST_STAGE) and result.returncode == 0:
        host_batch_passed(output,review)
    if stage == REMAINING_HOST_STAGE and result.returncode == 0:
        remaining_host_passed(output,review)
    return result.returncode


if __name__ == '__main__':
    sys.path.insert(0,str(ROOT))
    raise SystemExit(main())
