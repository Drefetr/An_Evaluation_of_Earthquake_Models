"""Portable independent arithmetic/custody check of saved joint-comparison outputs.

This command calls no likelihood, optimizer, feature constructor or generator.
It emits an automated check, not a claim that an agent reviewed a new batch.
The standalone case auditor is independently authored and explicitly hash-pinned.
"""
from pathlib import Path, PurePosixPath
import argparse
import datetime as dt
import hashlib
import importlib.util
import json
import math
import re
import subprocess
import sys
import zipfile

CHECKER_PATH = 'experiments/s04b_joint_audit/check.py'
CORE_PATH = 'experiments/s04b_joint_nuisance_audit/audit.py'
CORE_SHA256 = '47e38c68ff613f5dae1ac80da3713f03a673dc1a31553bf2a8ca3a27773231c3'

class AuditError(ValueError):
    pass

def require(condition, message):
    if not condition:
        raise AuditError(str(message))

def h(value):
    return hashlib.sha256(value).hexdigest()

def sha(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()

def object_pairs(pairs):
    value = {}
    for key, item in pairs:
        require(key not in value, 'Duplicate JSON key: '+key)
        value[key] = item
    return value

def read(path):
    return json.loads(Path(path).read_bytes(), object_pairs_hook=object_pairs,
        parse_constant=lambda value: (_ for _ in ()).throw(AuditError('Nonfinite JSON: '+value)))

def safe(root, relative):
    relative = relative.as_posix() if isinstance(relative, Path) else str(relative)
    require('\\' not in relative and ':' not in relative, 'Nonportable evidence path')
    pure = PurePosixPath(relative)
    require(not pure.is_absolute() and '..' not in pure.parts, 'Escaping evidence path')
    root = Path(root).resolve()
    path = root / relative
    require(not any(p.is_symlink() for p in [path, *path.parents] if p != root.parent), 'Symbolic evidence path')
    resolved = path.resolve()
    require(resolved.is_relative_to(root), 'Escaping evidence path')
    return resolved

def verify_archive(archive, pin, root):
    require(sha(archive) == pin, 'Archive hash mismatch')
    with zipfile.ZipFile(archive) as z:
        require(len(z.namelist()) == len(set(z.namelist())), 'Duplicate ZIP member')
        for entry in z.infolist():
            require(((entry.external_attr >> 16) & 0o170000) != 0o120000, 'ZIP symlink')
            path = safe(root, entry.filename)
            if not entry.is_dir():
                require(path.read_bytes() == z.read(entry.filename), 'Archive/extraction mismatch')

def verify_source_review(repo, path, pin):
    require(sha(path) == pin, 'Checker source-review hash mismatch')
    review = read(path)
    require(review.get('passed') is True, 'Checker source review failed')
    pins = {CHECKER_PATH: sha(Path(__file__)), CORE_PATH: CORE_SHA256}
    for relative, expected in pins.items():
        require(sha(safe(repo, relative)) == expected, 'Checker source differs: '+relative)
        require(review['reviewed_files_sha256'].get(relative) == expected, 'Unreviewed checker source: '+relative)
    return review, pins

def verify_reviewed_sources(repo, commit, review, source_review):
    require(re.fullmatch(r'[0-9a-f]{7,40}', commit) is not None, 'Commit must be a hexadecimal identity')
    pins = review['reviewed_files_sha256']
    for key in (CHECKER_PATH, CORE_PATH):
        require(pins.get(key) == source_review['reviewed_files_sha256'][key], 'Checker missing from conductor pins')
    for relative, expected in pins.items():
        path = safe(repo, relative)
        require(sha(path) == expected, 'Current source differs: '+relative)
        value = subprocess.check_output(['git', 'show', commit+':'+relative], cwd=repo)
        require(h(value) == expected, 'Reviewed commit differs: '+relative)

def verify_prior_kind(prior, checker_pins, source_review_pin):
    require(prior.get('passed') is True, 'Prior review failed')
    if prior.get('review_kind') == 'automated_saved_output_check':
        require(prior.get('live_agent_review') is False and prior.get('live_agent_review_performed') is False,
                'Automated review misattributed')
        require(prior.get('final_batch_agent_review_required') is True, 'Final review requirement removed')
        require(prior.get('checker_sources_sha256') == checker_pins, 'Prior checker changed')
        require(prior.get('checker_source_review_sha256') == source_review_pin, 'Prior source review changed')
    else:
        require(prior.get('reviewer') == '/root/continuation_cpu', 'Unrecognized initial independent review')

def verify_resource_spec(spec, review, admission, config):
    require(spec['wall_cap_seconds'] == review['wall_cap_seconds'] == admission['wall_seconds'], 'Wall cap changed')
    require(spec['rss_cap_bytes'] == review['rss_cap_bytes'] == config['resources']['numerical_process_tree_rss_cap_bytes'], 'RSS cap changed')
    require(spec['host_headroom_bytes'] == review['host_headroom_bytes'] == config['resources']['minimum_host_free_bytes'], 'Headroom changed')
    require(admission['independent_review_passed'] is True and admission['scheduler_review_passed'] is True, 'Missing source admission')
    for name in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','NUMEXPR_NUM_THREADS','BLIS_NUM_THREADS'):
        require(spec['env'].get(name) == '2', 'Numeric thread limit changed')

def audit_saved(a):
    require(not sys.flags.optimize, 'Optimized Python is not admitted')
    REPO = Path(a.repo).resolve()
    ART = Path(a.current).resolve()
    SCI = ART / 'science'
    SOURCE = REPO / 'experiments/s04b_joint_nuisance'
    EXEC = REPO / 'experiments/s04b_joint_execution'
    BUDGET = REPO / 'experiments/s04b_joint_budgeted'
    config_path = Path(a.config).resolve()
    require(bool(a.archive) == bool(a.archive_sha256), 'Archive and hash must be supplied together')
    archive_sha256 = None
    if a.archive:
        verify_archive(Path(a.archive), a.archive_sha256, ART)
        archive_sha256 = a.archive_sha256
    source_review_sha256 = a.checker_source_review_sha256
    source_review, checker_pins = verify_source_review(REPO, Path(a.checker_source_review), source_review_sha256)

    review = read(ART / 'conductor_review.json')
    admission = read(ART / 'admission.json')
    result = read(SCI / 'result.json')
    index = read(SCI / 'index.json')
    op = read(EXEC / 'operational_protocol.json')
    protocol = read(SOURCE / 'protocol.json')
    config = read(config_path)
    policy = read(BUDGET / 'allocation_protocol.json')
    require(index['schema'] == 'joint_budgeted_case_index_v2' and index['last_attempt_passed'] is True, "Saved-output invariant: index['schema'] == 'joint_budgeted_case_index_v2' and index['last_attempt_passed'] is True")
    require(admission['expires_utc'] == review['expires_utc'] == config['deadline_utc'], 'Expiry mismatch')
    require(review['operational_run_id'] == config['run_id'] == admission['operational_run_id'], "Saved-output invariant: review['operational_run_id'] == config['run_id'] == admission['operational_run_id']")
    require(review['operational_run_config_sha256'] == sha(config_path) == admission['operational_run_config_sha256'], "Saved-output invariant: review['operational_run_config_sha256'] == sha(config_path) == admission['operational_run_config_sha256']")
    verify_reviewed_sources(REPO, a.commit, review, source_review)
    require(index['source_sha256'] == result['source_sha256'] == admission['source_sha256'], "Saved-output invariant: index['source_sha256'] == result['source_sha256'] == admission['source_sha256']")
    for path, pin in index['source_sha256'].items():
        require(sha(safe(REPO, path)) == pin, 'Saved-output invariant: sha(safe(REPO, path)) == pin')
    require(sha(BUDGET / 'allocation_protocol.json') == index['allocation_protocol_sha256'] == result['allocation_protocol_sha256'] == admission['allocation_protocol_sha256'], "Saved-output invariant: sha(BUDGET / 'allocation_protocol.json') == index['allocation_protocol_sha256'] == result['allocation_protocol_sha256'] == admission['allocation_protocol_sha256']")
    require(policy['shared_run']['config_sha256'] == sha(config_path) and policy['shared_run']['expires_utc'] == config['deadline_utc'], "Saved-output invariant: policy['shared_run']['config_sha256'] == sha(config_path) and policy['shared_run']['expires_utc'] == config['deadline_utc']")
    require(sha(SOURCE / 'protocol.json') == index['science_protocol_sha256'] == op['science_protocol_sha256'], "Saved-output invariant: sha(SOURCE / 'protocol.json') == index['science_protocol_sha256'] == op['science_protocol_sha256']")
    require(sha(SOURCE / 'input_pins.json') == protocol['input_pins_sha256'] == op['science_input_pins_sha256'], "Saved-output invariant: sha(SOURCE / 'input_pins.json') == protocol['input_pins_sha256'] == op['science_input_pins_sha256']")
    for path, pin in op['frozen_sources_sha256'].items():
        require(sha(safe(REPO, path)) == pin, 'Saved-output invariant: sha(safe(REPO, path)) == pin')
    pins = read(SOURCE / 'input_pins.json')
    for path, pin in pins.items():
        require(sha(safe(REPO, path)) == pin, path)
    require(result['passed'] is True and result['status'] == 'batch_complete' and (index['partial_case'] is None), "Saved-output invariant: result['passed'] is True and result['status'] == 'batch_complete' and (index['partial_case'] is None)")
    require(result['index_sha256'] == sha(SCI / 'index.json') and result['admission_sha256'] == sha(ART / 'admission.json'), "Saved-output invariant: result['index_sha256'] == sha(SCI / 'index.json') and result['admission_sha256'] == sha(ART / 'admission.json')")
    require([r['case_id'] for r in result['cases']] == admission['case_ids'] == review['case_ids'] == [result['requested_case']], "Saved-output invariant: [r['case_id'] for r in result['cases']] == admission['case_ids'] == review['case_ids'] == [result['requested_case']]")
    require(len(result['cases']) == 1, "Saved-output invariant: len(result['cases']) == 1")
    require(admission['mode'] == 'budgeted_campaign' and result['old_projection_status'] == 'failed', "Saved-output invariant: admission['mode'] == 'budgeted_campaign' and result['old_projection_status'] == 'failed'")
    ids = [r['case_id'] for r in index['cases']]
    require(ids == op['sequence'][:len(ids)] and len(ids) == len(set(ids)), "Saved-output invariant: ids == op['sequence'][:len(ids)] and len(ids) == len(set(ids))")
    require(result['complete_cases'] == len(ids) and result['cases'] == index['cases'][-len(result['cases']):], "Saved-output invariant: result['complete_cases'] == len(ids) and result['cases'] == index['cases'][-len(result['cases']):]")
    require(index['runtime'] == result['runtime'], "Saved-output invariant: index['runtime'] == result['runtime']")
    for key, path in [('library_sha256', ART / 'build/attenuation.so'), ('build_receipt_sha256', ART / 'build/build_receipt.json')]:
        require(index[key] == result[key] == admission[key] == sha(path), 'Saved-output invariant: index[key] == result[key] == admission[key] == sha(path)')
    build = read(ART / 'build/build_receipt.json')
    require(build['passed'] is True and build['source_sha256'] == sha(SOURCE / 'attenuation.cpp') and (build['library_sha256'] == index['library_sha256']), "Saved-output invariant: build['passed'] is True and build['source_sha256'] == sha(SOURCE / 'attenuation.cpp') and (build['library_sha256'] == index['library_sha256'])")
    supervisor_spec = read(ART / 'supervisor_spec.json')
    verify_resource_spec(supervisor_spec, review, admission, config)
    supervision = read(ART / 'supervision/result.json')
    require(supervision['stop_reason'] is None and supervision['launched'] is True,
            'Supervisor did not complete a launched child cleanly')
    require(supervision['supervisor_sha256'] == sha(REPO / 'scripts/supervise_research.py'),
            'Supervisor source identity mismatch')
    require(dt.datetime.fromisoformat(supervision['started_utc']) <=
            dt.datetime.fromisoformat(supervision['finished_utc']) <=
            dt.datetime.fromisoformat(config['deadline_utc']), 'Child exceeded shared expiry')
    require(supervision['status'] == 'passed' and supervision['returncode'] == 0 and (not supervision['cleanup_errors']) and (not supervision['survivors_after_cleanup']), "Saved-output invariant: supervision['status'] == 'passed' and supervision['returncode'] == 0 and (not supervision['cleanup_errors']) and (not supervision['survivors_after_cleanup'])")
    require(supervision['spec_sha256'] == sha(ART / 'supervisor_spec.json') and supervision['execution_log_sha256'] == sha(ART / 'supervision/execution.log'), "Saved-output invariant: supervision['spec_sha256'] == sha(ART / 'supervisor_spec.json') and supervision['execution_log_sha256'] == sha(ART / 'supervision/execution.log')")
    require(supervision['execution_wall_seconds'] <= review['wall_cap_seconds'] and supervision['sampled_peak_tree_rss_bytes'] <= review['rss_cap_bytes'] and (supervision['minimum_sampled_host_available_bytes'] >= review['host_headroom_bytes']), "Saved-output invariant: supervision['execution_wall_seconds'] <= review['wall_cap_seconds'] and supervision['sampled_peak_tree_rss_bytes'] <= review['rss_cap_bytes'] and (supervision['minimum_sampled_host_available_bytes'] >= review['host_headroom_bytes'])")
    require(result['wall_seconds'] <= supervision['execution_wall_seconds'] and result['wall_seconds'] <= admission['wall_seconds'], "Saved-output invariant: result['wall_seconds'] <= supervision['execution_wall_seconds'] and result['wall_seconds'] <= admission['wall_seconds']")
    require(admission['threads'] == 2 and admission['workers'] == 1 and (admission['external_supervision'] is True), "Saved-output invariant: admission['threads'] == 2 and admission['workers'] == 1 and (admission['external_supervision'] is True)")
    require(admission['sampled_process_tree_rss_cap_bytes'] == config['resources']['numerical_process_tree_rss_cap_bytes'] == op['resources']['sampled_process_tree_rss_cap_bytes'], "Saved-output invariant: admission['sampled_process_tree_rss_cap_bytes'] == config['resources']['numerical_process_tree_rss_cap_bytes'] == op['resources']['sampled_process_tree_rss_cap_bytes']")
    prior_count = 0
    if a.prior:
        prior = Path(a.prior).resolve()
        oldindex = read(prior / 'science/index.json')
        priorreview = Path(a.prior_review)
        pr = read(priorreview)
        verify_prior_kind(pr, checker_pins, source_review_sha256)
        require(pr['passed'] is True and pr['index_sha256'] == sha(prior / 'science/index.json') == admission['prior_index_sha256'] and (sha(priorreview) == admission['prior_review_sha256']), "Saved-output invariant: pr['passed'] is True and pr['index_sha256'] == sha(prior / 'science/index.json') == admission['prior_index_sha256'] and (sha(priorreview) == admission['prior_review_sha256'])")
        prior_count = len(oldindex['cases'])
        require(index['cases'][:prior_count] == oldindex['cases'] and index['attempts'][:-1] == oldindex['attempts'], "Saved-output invariant: index['cases'][:prior_count] == oldindex['cases'] and index['attempts'][:-1] == oldindex['attempts']")
        require(index['runtime']['essential'] == oldindex['runtime']['essential'] and index['library_sha256'] == oldindex['library_sha256'] and (index['build_receipt_sha256'] == oldindex['build_receipt_sha256']), "Saved-output invariant: index['runtime']['essential'] == oldindex['runtime']['essential'] and index['library_sha256'] == oldindex['library_sha256'] and (index['build_receipt_sha256'] == oldindex['build_receipt_sha256'])")
        for entry in oldindex['cases']:
            for key in ('file', 'trace'):
                require(safe(SCI, entry[key]).read_bytes() == safe(prior / 'science', entry[key]).read_bytes(), "Saved-output invariant: safe(SCI, entry[key]).read_bytes() == safe(prior / 'science', entry[key]).read_bytes()")
        for entry in oldindex['attempts']:
            require(safe(SCI, entry['file']).read_bytes() == safe(prior / 'science', entry['file']).read_bytes(), "Saved-output invariant: safe(SCI, entry['file']).read_bytes() == safe(prior / 'science', entry['file']).read_bytes()")
    else:
        require(result['prior_case_count'] == 0 and (not index['reviews']), "Saved-output invariant: result['prior_case_count'] == 0 and (not index['reviews'])")
    require(result['prior_case_count'] == prior_count, "Saved-output invariant: result['prior_case_count'] == prior_count")
    require(len(ids) == prior_count + 1, 'Expected exactly one new case')
    require(len(index['reviews']) == len(oldindex['reviews']) + 1, 'Missing or extra prior-index review')
    carried_review = index['reviews'][-1]
    require(carried_review['sha256'] == sha(priorreview) and
            carried_review['accepted_index_sha256'] == sha(prior / 'science/index.json') and
            safe(SCI, carried_review['file']).read_bytes() == priorreview.read_bytes(),
            'Carried prior review differs from the admitted exact review')
    attempt_ids = []
    for entry in index['attempts']:
        path = safe(SCI, entry['file'])
        require(sha(path) == entry['sha256'], "Saved-output invariant: sha(path) == entry['sha256']")
        receipt = read(path)
        require(receipt['attempt_id'] == entry['attempt_id'] and receipt['phase'] == entry['phase'] and (receipt['wall_seconds'] == entry['seconds']) and math.isfinite(entry['seconds']) and (entry['seconds'] >= 0), "Saved-output invariant: receipt['attempt_id'] == entry['attempt_id'] and receipt['phase'] == entry['phase'] and (receipt['wall_seconds'] == entry['seconds']) and math.isfinite(entry['seconds']) and (entry['seconds'] >= 0)")
        require(receipt['passed'] is True and receipt['status'] == 'batch_complete' and (receipt['partial_case'] is None), "Saved-output invariant: receipt['passed'] is True and receipt['status'] == 'batch_complete' and (receipt['partial_case'] is None)")
        attempt_ids.append(entry['attempt_id'])
    require(len(attempt_ids) == len(set(attempt_ids)) and attempt_ids[-1] == review['numerical_attempt_id'] == admission['numerical_attempt_id'], "Saved-output invariant: len(attempt_ids) == len(set(attempt_ids)) and attempt_ids[-1] == review['numerical_attempt_id'] == admission['numerical_attempt_id']")
    require(index['attempts'][-1]['seconds'] == result['wall_seconds'], "Saved-output invariant: index['attempts'][-1]['seconds'] == result['wall_seconds']")
    for entry in index['reviews']:
        require(sha(safe(SCI, entry['file'])) == entry['sha256'] and read(safe(SCI, entry['file']))['passed'] is True, "Saved-output invariant: sha(safe(SCI, entry['file'])) == entry['sha256'] and read(safe(SCI, entry['file']))['passed'] is True")
    require(index['original_failure'] == op['original_failure'], "Saved-output invariant: index['original_failure'] == op['original_failure']")
    original = index['original_failure']['prior_scientific_seconds']
    total = math.fsum([original, *[v['seconds'] for v in index['attempts']]])
    pilot = math.fsum([original, *[v['seconds'] for v in index['attempts'] if v['phase'] == 'pilot']])
    require(index['budget'] == result['budget'] == dict(total_seconds=total, pilot_seconds=pilot), "Saved-output invariant: index['budget'] == result['budget'] == dict(total_seconds=total, pilot_seconds=pilot)")
    require(total <= config['resources']['joint_campaign_wall_seconds'] == op['resources']['campaign_aggregate_seconds'] and pilot <= config['resources']['joint_pilot_wall_seconds'] == op['resources']['pilot_aggregate_seconds'], "Saved-output invariant: total <= config['resources']['joint_campaign_wall_seconds'] == op['resources']['campaign_aggregate_seconds'] and pilot <= config['resources']['joint_pilot_wall_seconds'] == op['resources']['pilot_aggregate_seconds']")
    require(abs(result['allocation']['prior_charged_seconds'] - (total - result['wall_seconds'])) < 1e-09, "Saved-output invariant: abs(result['allocation']['prior_charged_seconds'] - (total - result['wall_seconds'])) < 1e-09")
    require(a.prior and prior_count >= 5, 'Saved-output invariant: a.prior and prior_count >= 5')
    require(policy['sequence'] == op['sequence'] and len(policy['fixed_slots']) == 75, "Saved-output invariant: policy['sequence'] == op['sequence'] and len(policy['fixed_slots']) == 75")
    slot = policy['fixed_slots'][prior_count - 5]
    require(slot['case_id'] == result['requested_case'] and slot['wall_seconds'] == admission['wall_seconds'] == review['wall_cap_seconds'], "Saved-output invariant: slot['case_id'] == result['requested_case'] and slot['wall_seconds'] == admission['wall_seconds'] == review['wall_cap_seconds']")
    require(slot['scientific_reservation_seconds'] == slot['wall_seconds'] - 30, "Saved-output invariant: slot['scientific_reservation_seconds'] == slot['wall_seconds'] - 30")
    remaining = math.fsum((v['wall_seconds'] for v in policy['fixed_slots'][prior_count - 5:]))
    require(result['allocation']['unspent_fixed_slot_seconds'] == remaining, "Saved-output invariant: result['allocation']['unspent_fixed_slot_seconds'] == remaining")
    require(result['allocation']['maximum_future_charge'] == result['allocation']['prior_charged_seconds'] + remaining <= 115200, "Saved-output invariant: result['allocation']['maximum_future_charge'] == result['allocation']['prior_charged_seconds'] + remaining <= 115200")
    require(result['allocation']['forecast_passed'] is False and result['new_fit_arms'] == 4 and (result['reused_fit_arms'] == 0), "Saved-output invariant: result['allocation']['forecast_passed'] is False and result['new_fit_arms'] == 4 and (result['reused_fit_arms'] == 0)")
    transition = index['transition']
    require(transition['schema'] == 'joint_budgeted_transition_v1' and transition['old_projection_status'] == 'failed', "Saved-output invariant: transition['schema'] == 'joint_budgeted_transition_v1' and transition['old_projection_status'] == 'failed'")
    pred = policy['predecessor']
    require(transition['predecessor_index_sha256'] == pred['accepted_index_sha256'], "Saved-output invariant: transition['predecessor_index_sha256'] == pred['accepted_index_sha256']")
    require(transition['predecessor_source_sha256'] == pred['source_sha256'], "Saved-output invariant: transition['predecessor_source_sha256'] == pred['source_sha256']")
    require(transition['predecessor_operational_protocol_sha256'] == pred['operational_protocol_sha256'], "Saved-output invariant: transition['predecessor_operational_protocol_sha256'] == pred['operational_protocol_sha256']")
    require(transition['allocation_protocol_sha256'] == sha(BUDGET / 'allocation_protocol.json'), "Saved-output invariant: transition['allocation_protocol_sha256'] == sha(BUDGET / 'allocation_protocol.json')")
    expected = {'transition/predecessor_index.json': pred['accepted_index_sha256'], 'transition/predecessor_review.json': pred['accepted_review_sha256']}
    expected.update({'transition/' + name: pin for name, pin in policy['evidence_sha256'].items()})
    require(transition['files'] == expected, "Saved-output invariant: transition['files'] == expected")
    for name, pin in expected.items():
        require(sha(safe(SCI, name)) == pin, 'Saved-output invariant: sha(safe(SCI, name)) == pin')
    original_index = read(SCI / 'transition/predecessor_index.json')
    require(index['cases'][:5] == original_index['cases'] and index['attempts'][:len(original_index['attempts'])] == original_index['attempts'] and (index['reviews'][:len(original_index['reviews'])] == original_index['reviews']), "Saved-output invariant: index['cases'][:5] == original_index['cases'] and index['attempts'][:len(original_index['attempts'])] == original_index['attempts'] and (index['reviews'][:len(original_index['reviews'])] == original_index['reviews'])")
    require(sha(SCI / 'training_resume/provenance.json') == pred['training_resume_provenance_sha256'], "Saved-output invariant: sha(SCI / 'training_resume/provenance.json') == pred['training_resume_provenance_sha256']")
    require(len(index['attempts']) - len(original_index['attempts']) == len(ids) - 5, "Saved-output invariant: len(index['attempts']) - len(original_index['attempts']) == len(ids) - 5")
    require(index['runtime']['essential'] == pred['runtime_essential'], "Saved-output invariant: index['runtime']['essential'] == pred['runtime_essential']")
    for key in ('library_sha256', 'build_receipt_sha256'):
        require(index[key] == pred[key], 'Saved-output invariant: index[key] == pred[key]')
    for number, entry in enumerate(index['attempts'][len(original_index['attempts']):]):
        receipt = read(safe(SCI, entry['file']))
        expected_slot = policy['fixed_slots'][number]
        require(receipt['phase'] == 'campaign' and receipt['case_ids'] == [expected_slot['case_id']] and (receipt['wall_seconds'] <= expected_slot['wall_seconds']), "Saved-output invariant: receipt['phase'] == 'campaign' and receipt['case_ids'] == [expected_slot['case_id']] and (receipt['wall_seconds'] <= expected_slot['wall_seconds'])")
        require(receipt['source_sha256'] == index['source_sha256'] and receipt['allocation_protocol_sha256'] == index['allocation_protocol_sha256'], "Saved-output invariant: receipt['source_sha256'] == index['source_sha256'] and receipt['allocation_protocol_sha256'] == index['allocation_protocol_sha256']")
    require(index['reviews'][:len(oldindex['reviews'])] == oldindex['reviews'], "Saved-output invariant: index['reviews'][:len(oldindex['reviews'])] == oldindex['reviews']")
    for entry in oldindex['reviews']:
        require(safe(SCI, entry['file']).read_bytes() == safe(prior / 'science', entry['file']).read_bytes(), "Saved-output invariant: safe(SCI, entry['file']).read_bytes() == safe(prior / 'science', entry['file']).read_bytes()")
    for path in (prior / 'science/training_resume').rglob('*'):
        if path.is_file():
            require(safe(SCI, path.relative_to(prior / 'science')).read_bytes() == path.read_bytes(), "Saved-output invariant: safe(SCI, path.relative_to(prior / 'science')).read_bytes() == path.read_bytes()")
    spec = importlib.util.spec_from_file_location('independent_joint_saved_audit', REPO / 'experiments/s04b_joint_nuisance_audit/audit.py')
    audit = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(audit)
    manifest = {c['case_id']: c for c in read(REPO / 'reproduction/synthetic/input_manifest.json')['s04b']['cases']}
    reports = []
    for entry in index['cases']:
        path = safe(SCI, entry['file'])
        require(sha(path) == entry['sha256'], "Saved-output invariant: sha(path) == entry['sha256']")
        report = read(path)
        case = manifest[entry['case_id']]
        require(entry['file'] == 'cases/' + case['case_id'] + '.json' and entry['trace'] == 'cases/' + case['case_id'] + '.attempts.jsonl', "Saved-output invariant: entry['file'] == 'cases/' + case['case_id'] + '.json' and entry['trace'] == 'cases/' + case['case_id'] + '.attempts.jsonl'")
        for key in ('case_id', 'regime', 'seed', 'n_train', 'n_test'):
            require(report[key] == case[key], 'Saved-output invariant: report[key] == case[key]')
        audit.inspect_case(report, protocol)
        audit.inspect_trace(safe(SCI, entry['trace']), report)
        audit.inspect_historical(report, case, REPO)
        require(sha(safe(SCI, entry['trace'])) == entry['trace_sha256'], "Saved-output invariant: sha(safe(SCI, entry['trace'])) == entry['trace_sha256']")
        require(entry['reused_fit_arms'] == (4 if case['case_id'] == op['original_failure']['case_id'] else 0) and entry['new_fit_arms'] == 4 - entry['reused_fit_arms'], "Saved-output invariant: entry['reused_fit_arms'] == (4 if case['case_id'] == op['original_failure']['case_id'] else 0) and entry['new_fit_arms'] == 4 - entry['reused_fit_arms']")
        reports.append(report)
    policy = read(SOURCE / 'checkpoint_repair.json')
    prov = read(SCI / 'training_resume/provenance.json')
    for key, path in prov['evidence_files'].items():
        require(sha(safe(SCI, path)) == prov[key] == policy[key], 'Saved-output invariant: sha(safe(SCI, path)) == prov[key] == policy[key]')
    frozen = read(SCI / 'training_resume/frozen_training.json')
    failed = read(SCI / 'training_resume/failed_result.json')
    partialreview = read(SCI / 'training_resume/independent_partial_review.json')
    require(failed['passed'] is False and frozen['passed'] is False and (frozen['training_selections_frozen'] is True) and (frozen['outcomes'] == []) and (failed['cases'] == []), "Saved-output invariant: failed['passed'] is False and frozen['passed'] is False and (frozen['training_selections_frozen'] is True) and (frozen['outcomes'] == []) and (failed['cases'] == [])")
    require(partialreview['passed'] is True and partialreview['scientific_pilot_passed'] is False, "Saved-output invariant: partialreview['passed'] is True and partialreview['scientific_pilot_passed'] is False")
    require(failed['runtime']['essential'] == index['runtime']['essential'] and failed['runtime'] == prov['predecessor_runtime'], "Saved-output invariant: failed['runtime']['essential'] == index['runtime']['essential'] and failed['runtime'] == prov['predecessor_runtime']")
    for key in ('library_sha256', 'build_receipt_sha256'):
        require(failed[key] == index[key], 'Saved-output invariant: failed[key] == index[key]')
    require(failed['source_sha256'] == prov['predecessor_source_sha256'] == policy['predecessor_source_sha256'], "Saved-output invariant: failed['source_sha256'] == prov['predecessor_source_sha256'] == policy['predecessor_source_sha256']")
    first = reports[0]
    require(first['case_id'] == prov['case_id'] == policy['case_id'] and first['resume_provenance'] == prov, "Saved-output invariant: first['case_id'] == prov['case_id'] == policy['case_id'] and first['resume_provenance'] == prov")
    protected = {key: first[key] for key in policy['training_payload_keys']}
    protected['floor_checks'] = [v for v in first['floor_checks'] if v['phase'] == 'train']
    protected['plan_dimensions'] = {'train': first['plan_dimensions']['train']}
    previous = {key: frozen[key] for key in policy['training_payload_keys']}
    require(protected == previous, 'Saved-output invariant: protected == previous')
    require(h(json.dumps(previous, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()) == policy['training_payload_canonical_sha256'] == prov['training_payload_canonical_sha256'], "Saved-output invariant: h(json.dumps(previous, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()) == policy['training_payload_canonical_sha256'] == prov['training_payload_canonical_sha256']")
    require(prov['reused_fit_arms'] == 4 and prov['repeated_training_evaluations'] == 0, "Saved-output invariant: prov['reused_fit_arms'] == 4 and prov['repeated_training_evaluations'] == 0")
    require(sha(SCI / 'cases' / (first['case_id'] + '.attempts.jsonl')) == policy['attempts_sha256'], "Saved-output invariant: sha(SCI / 'cases' / (first['case_id'] + '.attempts.jsonl')) == policy['attempts_sha256']")
    require(first['prior_training_attempt_seconds'] == original and abs(first['wall_seconds'] - original - first['current_attempt_wall_seconds']) < 1e-09, "Saved-output invariant: first['prior_training_attempt_seconds'] == original and abs(first['wall_seconds'] - original - first['current_attempt_wall_seconds']) < 1e-09")
    require(sha(ART / 'original_failure.zip') == policy['failed_archive_sha256'], "Saved-output invariant: sha(ART / 'original_failure.zip') == policy['failed_archive_sha256']")
    with zipfile.ZipFile(ART / 'original_failure.zip') as z:
        for member, path in [('science/result.json', 'failed_result.json'), ('science/' + first['case_id'] + '.json', 'frozen_training.json'), ('science/' + first['case_id'] + '.attempts.jsonl', 'frozen_training.attempts.jsonl')]:
            require(z.read(member) == (SCI / 'training_resume' / path).read_bytes(), "Saved-output invariant: z.read(member) == (SCI / 'training_resume' / path).read_bytes()")
        require(z.read('build/attenuation.so') == (ART / 'build/attenuation.so').read_bytes() and z.read('build/build_receipt.json') == (ART / 'build/build_receipt.json').read_bytes(), "Saved-output invariant: z.read('build/attenuation.so') == (ART / 'build/attenuation.so').read_bytes() and z.read('build/build_receipt.json') == (ART / 'build/build_receipt.json').read_bytes()")
    counts = dict(completed_case_fit_arms=4 * len(ids), completed_case_new_fit_arms=4 * (len(ids) - 1), completed_case_reused_fit_arms=4, completed_outcomes=5 * len(ids))
    for key, v in counts.items():
        require(result[key] == v, 'Saved-output invariant: result[key] == v')
    require(result['partial_fit_checkpoint'] is None, "Saved-output invariant: result['partial_fit_checkpoint'] is None")
    independent = audit.aggregate(reports, protocol)
    if len(ids) == 80:
        require(result['scientific_completion'] is True and sha(SCI / 'summary.json') == result['summary_sha256'], "Saved-output invariant: result['scientific_completion'] is True and sha(SCI / 'summary.json') == result['summary_sha256']")
        audit.compare_tree(read(SCI / 'summary.json'), independent)
    else:
        require(result['scientific_completion'] is False, "Saved-output invariant: result['scientific_completion'] is False")
    out = dict(passed=True, index_sha256=sha(SCI / 'index.json'), review_kind='automated_saved_output_check', checker_author='/root/continuation_cpu', live_agent_review=False, live_agent_review_performed=False, final_batch_agent_review_required=True, artifact_sha256=archive_sha256, source_commit=a.commit, source_sha256=index['source_sha256'], allocation_protocol_sha256=index['allocation_protocol_sha256'], operational_run_config_sha256=sha(config_path), complete_cases=len(ids), outcomes=5 * len(ids), historical_floor_checks=6 * len(ids), historical_comparison_rows=5 * len(ids), verified_input_pins=len(pins), counts=counts, training_resume=dict(exact_preserved_training_fits=4, old_attempt_starts=32, new_first_case_fit_calls=0, training_trace_unchanged=True), budget=index['budget'], attempt_census=audit.attempt_census(reports, protocol), independent_summary=independent, scientific_completion=len(ids) == 80, scientific_execution_in_audit=False, allocation=result['allocation'], old_projection_status='failed', transition_sha256=h(json.dumps(transition, sort_keys=True).encode()), scope='Independent output arithmetic/gates/wins/boundaries/failure census and full retained source/input/runtime/native/prefix/resource custody. No experiment author aggregation imported, no likelihood/refit/generator calls. Resource values independently verified against retained supervisor record, not newly measured.', supervision=dict(passed=True, sampled_peak_tree_rss_bytes=supervision['sampled_peak_tree_rss_bytes'], execution_wall_seconds=supervision['execution_wall_seconds']), audit_script_sha256=sha(Path(__file__)), independent_case_auditor_sha256=sha(Path(audit.__file__)))
    out.update(checker_source_review_sha256=source_review_sha256, checker_sources_sha256=checker_pins, prior_index_sha256=sha(prior / 'science/index.json'), prior_review_sha256=sha(priorreview), admission_sha256=sha(ART / 'admission.json'), conductor_review_sha256=sha(ART / 'conductor_review.json'), supervisor_result_sha256=sha(ART / 'supervision/result.json'), supervisor_spec_sha256=sha(ART / 'supervisor_spec.json'), directory_evidence_checked=True, archive_checked=bool(a.archive))
    return out


def parser():
    p = argparse.ArgumentParser(description=__doc__)
    for name in ('repo','current','prior','prior-review','config','commit','output','checker-source-review','checker-source-review-sha256'):
        p.add_argument('--'+name, required=True)
    p.add_argument('--archive')
    p.add_argument('--archive-sha256')
    return p

def main(argv=None):
    args = parser().parse_args(argv)
    output = Path(args.output)
    # Reserve an exclusive output before checking; a failed retry cannot leave an old pass.
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open('x', encoding='utf-8', newline='\n') as stream:
        try:
            result = audit_saved(args)
        except Exception as error:
            result = dict(passed=False, review_kind='automated_saved_output_check',
                live_agent_review=False, live_agent_review_performed=False,
                final_batch_agent_review_required=True, scientific_execution_in_audit=False,
                error_type=type(error).__name__, error=str(error), audit_script_sha256=sha(Path(__file__)))
        stream.write(json.dumps(result, indent=2, allow_nan=False)+'\n')
    print(json.dumps(dict(passed=result['passed'], receipt=str(output), receipt_sha256=sha(output))))
    return 0 if result['passed'] else 1

if __name__ == '__main__':
    raise SystemExit(main())
