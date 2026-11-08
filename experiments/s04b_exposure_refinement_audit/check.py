"""Independent custody/arithmetic audit of saved numerical-amendment outputs.

No producer module, likelihood, optimizer, native library or generator is loaded.
The original independent auditor is used only for its saved arithmetic checks;
this checker never rewrites an amended source identity into the old schema.
"""
from pathlib import Path, PurePosixPath
import argparse
import datetime as dt
from decimal import Decimal
import hashlib
import importlib.util
import json
import math
import sys
import zipfile

HERE = Path(__file__).resolve()
REPO = HERE.parents[2]
CHECKER_PATH = 'experiments/s04b_exposure_refinement_audit/check.py'
PROTOCOL_PATH = 'experiments/s04b_exposure_refinement/protocol.json'
DESIGN = 'validation/reproductions/continuation_20261107/exposure_refinement_design/'
DEPENDENCIES = {
    'experiments/s04b_joint_audit/check.py': '839c67fd3dca65294b457cb6511a66c1800fa422712fc13e302e4f4495ddaa13',
    'experiments/s04b_joint_nuisance_audit/audit.py': '47e38c68ff613f5dae1ac80da3713f03a673dc1a31553bf2a8ca3a27773231c3',
    'experiments/s04b_joint_remaining_audit/check.py': '6600b55612d665a1255fcfc5261275452d15abd8b63828f1feda0c38386f51d2',
}
DESIGN_PINS = {
    'protocol_proposal.json': '5ff434b999e2dd729552e18012fe97319578eb101738597fe7f8d18d9032ea23',
    'independent_design_review.json': 'da10a9b046925426f9b7fb4370be0961697dd6c81ca58539201ba361dd7e2758',
    'prior_failure_census.json': '3f1e5912a1c9ebd9efc69fec20cc3708e49e852da95512c5927e1d400bd159ac',
    'independent_reuse_census.json': 'beeb04498e6f57fa4d6027883ee5eb69a1f7a5cbb8ef412423f95991c750d4a0',
    'resources.json': 'e20f857ca92147c2a4710e915ac13fbd9c997a6de1ffdca52fc338c61365bd14',
}
MODEL_PATH = 'experiments/s04b_joint_nuisance/model.py'
MODEL_SHA = 'cc891181e51251247b9668fb6213642f0884deb288050efb2586cf179c6e8898'
SCIENCE_PATH = 'experiments/s04b_joint_nuisance/protocol.json'
SCIENCE_SHA = '8f31b9f28d830eeffa30bdbf3e0fcf1295087411869fa301b91333c95fa445e9'
PARTIAL = 'S6_narrow_short_total_seed410603'
UNKNOWN = 'S5_broad_long_imm_seed410518'
VERSION = 'joint_exposure_refinement_v1'
TARGET_ERROR = 'Nonfinite or negative full exposure'


def hash_bytes(value):
    return hashlib.sha256(value).hexdigest()


def sha(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


# Validate independently authored dependencies before their imports.
for _relative, _pin in DEPENDENCIES.items():
    if sha(REPO / _relative) != _pin:
        raise ValueError('Changed independent audit dependency: '+_relative)
_spec = importlib.util.spec_from_file_location('exposure_amendment_saved_math', REPO/'experiments/s04b_joint_remaining_audit/check.py')
old = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(old)
core, custody = old.core, old.custody
require, read, safe = custody.require, custody.read, custody.safe
ARMS = old.ARMS


def document(value):
    return json.loads(value, object_pairs_hook=custody.object_pairs,
        parse_constant=lambda v: (_ for _ in ()).throw(custody.AuditError('Nonfinite JSON: '+v)))


def records(value):
    return [document(line) for line in value.splitlines() if line.strip()]


def canonical_sha(value):
    return hash_bytes(json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode())


def finite_vector(value, size=8):
    require(isinstance(value, list) and len(value) == size, 'Full finite vector required')
    for item in value:
        core.number(item)
    return value


def exact_number(actual, expected, name):
    require(core.number(actual) == expected, 'Changed '+name)


def live_review(value):
    require(value.get('live_agent_review') is True and value.get('live_agent_review_performed') is True,
            'Genuine live independent review required')
    require(value.get('final_batch_agent_review_required') is not True, 'Pending live review')
    require(value.get('live_independent_review', True) is True, 'Contradictory live review')


def trace_matches(value, report):
    require(hash_bytes(value) == report['attempts_sha256'], 'Trace hash differs')
    expected = []
    for model in ARMS:
        for row in report['fits'].get(model, {}).get('records', []):
            expected += [dict(event='attempt_start', model=model, start_index=row['start_index'],
                method=row['method'], initial_parameters=row['initial_parameters'], status='running', success=False),
                dict(event='attempt_end', model=model, **row)]
    actual = records(value)
    require(actual == expected, 'Logical trace differs from exact fit records')
    return actual


class Archives:
    """Open only pinned public ZIP bytes; no extraction or producer resolver."""
    def __init__(self, repo):
        self.repo, self.handles = Path(repo), {}

    def close(self):
        for saved in self.handles.values():
            saved.close()

    def member(self, archive, archive_sha256, member, member_sha256):
        path = safe(self.repo, archive)
        key = (str(path), archive_sha256)
        if key not in self.handles:
            require(sha(path) == archive_sha256, 'Public evidence archive changed')
            saved = zipfile.ZipFile(path)
            require(len(saved.namelist()) == len(set(saved.namelist())), 'Duplicate ZIP member')
            for info in saved.infolist():
                require(((info.external_attr >> 16) & 0o170000) != 0o120000, 'ZIP symlink')
                pure = PurePosixPath(info.filename)
                require(not pure.is_absolute() and '..' not in pure.parts and '\\' not in info.filename,
                        'Unsafe ZIP member')
            self.handles[key] = saved
        raw = self.handles[key].read(member)
        require(hash_bytes(raw) == member_sha256, 'Archive member changed: '+member)
        return raw


def load_contract(repo):
    repo = Path(repo)
    for name, pin in DESIGN_PINS.items():
        require(sha(safe(repo, DESIGN+name)) == pin, 'Accepted design evidence changed: '+name)
    design = read(repo/DESIGN/'protocol_proposal.json')
    review = read(repo/DESIGN/'independent_design_review.json')
    require(review['passed'] is True and review['implementation_admitted'] is True, 'Unaccepted amendment design')
    live_review(review)
    policy = read(repo/PROTOCOL_PATH)
    require(policy['schema'] == 'joint_exposure_refinement_protocol_v1' and policy['version'] == VERSION and
            policy['scientific_completion'] is False, 'Unknown numerical amendment')
    require(policy['refinement'] == design['refinement'], 'Numerical refinement rules changed')
    require(policy['resources'] == read(repo/DESIGN/'resources.json'), 'Resource amendment changed')
    require(policy['case_ids'] == [PARTIAL]+design['future']['case_ids'] and len(policy['case_ids']) == 36,
            'Amended case roster changed')
    require(policy['full_sequence'] == read(repo/'experiments/s04b_joint_remaining/protocol.json')['full_sequence'],
            'Original eighty-history sequence changed')
    require(policy['permanent_unknown'] == design['reuse']['permanent_unknown'], 'Permanent unknown changed')
    require(policy['failed_case'] == design['resume_current']['original_failure'], 'Partial failure custody changed')
    require(policy['original_scientific_protocol_sha256'] == SCIENCE_SHA == sha(repo/SCIENCE_PATH),
            'Original scientific protocol changed')
    require(policy['original_native'] == design['unchanged']['native'] and
            policy['shared_run'] == design['resources']['shared_run'], 'Native/runtime/shared boundary changed')
    for relative, pin in policy['source_sha256'].items():
        require(sha(safe(repo, relative)) == pin, 'Frozen dependency changed: '+relative)
    for relative, pin in design['unchanged']['scientific_dependency_sha256'].items():
        require(policy['source_sha256'].get(relative) == pin, 'Missing original source identity: '+relative)
    for relative, pin in policy['design_evidence_sha256'].items():
        require(sha(safe(repo, relative)) == pin, 'Retained design artifact changed')
    for name, pin in DESIGN_PINS.items():
        require(policy['design_evidence_sha256'].get(DESIGN+name) == pin, 'Missing accepted design identity')
    expected_slots = [dict(case_id=PARTIAL, wall_seconds=1806, scientific_seconds=1776, mode='partial')]
    expected_slots += [dict(row, mode='untouched') for row in design['future']['case_slots']]
    require(policy['case_slots'] == expected_slots, 'Case caps changed')
    return policy, read(repo/SCIENCE_PATH), design


def initial_evidence(repo, policy, science, design):
    """Recheck the immutable 44-record base and exact 43-history projection."""
    saved = Archives(repo)
    try:
        base = policy['base']
        index = document(saved.member(base['archive'], base['archive_sha256'], base['index_member'], base['index_sha256']))
        require(sha(safe(repo, base['review'])) == base['review_sha256'], 'Initial live failure review changed')
        review = read(safe(repo, base['review']))
        require(review['audit_passed'] is True and review['passed'] is False and review['scientific_completion'] is False,
                'Original technical failure was relabelled')
        live_review(review)
        rows = index['records']
        require(len(rows) == 44 and [r['case_id'] for r in rows] == policy['full_sequence'][:44] and
                index['counts'] == old.expected_counts(rows), 'Original base projection/counts changed')
        require(index['scientific_completion'] is False and index['passed'] is False, 'Original base claims success')
        by_id = {row['case_id']: row for row in rows}
        for ref in design['reuse']['complete_histories']:
            report = document(saved.member(ref['archive'], ref['archive_sha256'], ref['case_member'], ref['case_sha256']))
            trace = saved.member(ref['archive'], ref['archive_sha256'], ref['trace_member'], ref['trace_sha256'])
            core.inspect_case(report, science)
            events = trace_matches(trace, report)
            require(not any(e.get('error_type') == 'ArithmeticError' and e.get('error') == TARGET_ERROR for e in events),
                    'Reused complete history had a refinement trigger')
            row = by_id[ref['case_id']]
            require(row == old.projection(report, 'complete', row['source']), 'Saved complete projection differs')
            require(row['source']['case_sha256'] == ref['case_sha256'] and row['source']['trace_sha256'] == ref['trace_sha256'],
                    'Original source locator changed')
        unknown = by_id[UNKNOWN]
        require(unknown['disposition'] == 'scientific_unknown' and unknown['outcomes'] == [] and unknown['scientific_passed'] is False,
                'Permanent cap unknown became complete')
        ref = policy['permanent_unknown']
        require(unknown['source']['case_sha256'] == ref['case_sha256'] and unknown['source']['trace_sha256'] == ref['trace_sha256'],
                'Permanent unknown custody changed')
        raw = saved.member(ref['archive'], ref['archive_sha256'], ref['trace_member'], ref['trace_sha256'])
        terminal = records(raw)[-1]
        require(terminal['method'] == 'Powell' and terminal['nfev'] == 5000 and terminal['solver_status'] == 1 and
                terminal['success'] is False and terminal['start_index'] == 5, 'Permanent cap evidence changed')
        failure = policy['failed_case']
        partial = document(saved.member(failure['archive']['path'], failure['archive']['sha256'],
            failure['case_member'], failure['case_sha256']))
        trace = saved.member(failure['archive']['path'], failure['archive']['sha256'], failure['trace_member'], failure['trace_sha256'])
        trace_matches(trace, partial)
        require(partial['case_id'] == PARTIAL and partial['passed'] is False and partial['outcomes'] == [], 'Partial failure changed')
        return index, partial
    finally:
        saved.close()


def finite_value(value):
    return not isinstance(value, bool) and isinstance(value, (int, float)) and math.isfinite(value)


def score_identities(value):
    return all(finite_value(value.get(k)) for k in ('P', 'E', 'C', 'M', 'joint', 'nll')) and (
        value['C'] == -value['E'] and value['joint'] == value['P']-value['E']+value['M'] and
        value['nll'] == -value['joint'])


def inspect_refinements(events, science):
    """Rederive every trigger and paired numerical decision from saved operands."""
    require(len(events) % 2 == 0, 'Incomplete refinement event pair')
    pairs, seen_callbacks = [], set()
    for number, offset in enumerate(range(0, len(events), 2), 1):
        start, end = events[offset:offset+2]
        require(start['event'] == 'refinement_start' and end['event'] == 'refinement_end' and
                start['event_id'] == end['event_id'] == number, 'Refinement sequence changed')
        context = start['context']
        require(end['context'] == context and context['phase'] == 'train' and context['model'] in ARMS and
                context['method'] in ('L-BFGS-B', 'Powell') and type(context['start_index']) is int and
                0 <= context['start_index'] < 8 and type(context['callback_index']) is int and context['callback_index'] > 0,
                'Refinement outside an identified training optimizer callback')
        key = (context['model'], context['start_index'], context['method'], context['callback_index'])
        require(key not in seen_callbacks, 'Repeated refinement within a callback')
        seen_callbacks.add(key)
        theta = finite_vector(start['theta'])
        require(end['theta'] == theta == context['theta'], 'Refinement point changed')
        coarse = start['coarse']
        require(coarse['theta'] == theta and coarse['model'] == context['model'] and coarse['order'] == 8 and
                coarse['error_type'] == 'ArithmeticError' and coarse['error'] == TARGET_ERROR and
                coarse['origin'] == MODEL_PATH+':Phase.evaluate' and coarse['origin_sha256'] == MODEL_SHA,
                'Different coarse exception origin/point/order')
        c = coarse['score']
        require(score_identities(c) and c['E'] < -1e-9, 'Not the finite negative original guard')
        gc = finite_vector(coarse['gradient'])
        # The original successful trial domain remains the original optimizer box.
        boxes = science['shared_bounds'] + ([] if context['model'] == 'null' else science['inhibition_bounds'])
        core.sides(theta[:len(boxes)], boxes)
        for field in ('coarse_seconds',):
            require(0 <= core.number(start[field]), 'Invalid coarse evaluation time')
        require(0 <= core.number(end['fine_seconds']), 'Invalid fine evaluation time')
        require(type(end['accepted']) is bool, 'Refinement decision must be boolean')
        if 'fine' not in end:
            require(end['accepted'] is False and isinstance(end.get('error'), str) and
                    isinstance(end.get('error_type'), str) and 'comparison' not in end,
                    'Missing fine return was treated as accepted')
            fine_returned = False
        else:
            require(end['effective_order'] == 16, 'Fine order changed')
            fine, gf = end['fine']['score'], end['fine']['gradient']
            finite = (all(finite_value(fine.get(k)) for k in ('P', 'E', 'C', 'M', 'joint', 'nll')) and
                      isinstance(gf, list) and len(gf) == 8 and all(finite_value(v) for v in gf))
            expected = dict(passed=False, finite=finite)
            if finite:
                pc = core.projected(theta[:len(boxes)], gc[:len(boxes)], boxes)
                pf = core.projected(theta[:len(boxes)], gf[:len(boxes)], boxes)
                delta = abs(fine['joint']-c['joint'])
                scaled = max((abs(x-y)/max(1., abs(x), abs(y)) for x, y in zip(pc, pf)), default=0.)
                identities = score_identities(fine)
                same_point = fine['P'] == c['P'] and fine['M'] == c['M']
                jt = science['quadrature']['joint_absolute_tolerance']
                gt = science['quadrature']['selected_training_gradient_scaled_tolerance']
                require(jt == gt == 1e-4, 'Original numerical tolerance changed')
                expected.update(projected_coarse=pc, projected_fine=pf, absolute_joint_delta=delta,
                    projected_gradient_scaled_delta=scaled, score_identities=identities, same_P_M=same_point,
                    fine_exposure_nonnegative=fine['E'] >= 0, joint_tolerance=jt, gradient_tolerance=gt)
                expected['passed'] = identities and same_point and fine['E'] >= 0 and delta <= jt and scaled <= gt
            require(end['comparison'] == expected and end['accepted'] is expected['passed'],
                    'Refinement acceptance/comparison is not independently reproducible')
            fine_returned = True
        pairs.append(dict(key=key, accepted=end['accepted'], fine_returned=fine_returned,
                          coarse_seconds=start['coarse_seconds'], fine_seconds=end['fine_seconds']))
    return pairs


def inspect_reused_values(report, partial, mode):
    """Exact saved values, with no replayed optimizer or replacement selection."""
    require(mode in ('partial', 'untouched'), 'Unknown computation mode')
    if mode == 'untouched':
        require(report['case_id'] != PARTIAL and report.get('prior_training_attempt_seconds', 0) == 0,
                'Untouched history contains partial reuse')
        return [(name, row) for name in ARMS for row in report['fits'].get(name, {}).get('records', [])]
    require(report['case_id'] == partial['case_id'] == PARTIAL and partial['passed'] is False and partial['outcomes'] == [],
            'Wrong partial predecessor')
    for name in ARMS[:3]:
        require(report['fits'][name] == partial['fits'][name] and
                report['training_checks'][name] == partial['training_checks'][name],
                'Reused completed arm/check values changed: '+name)
    new, old_fit = report['fits']['LIplus_inclusive'], partial['fits']['LIplus_inclusive']
    require(new['candidates'][:5] == old_fit['candidates'] and new['records'][:4] == old_fit['records'][:4],
            'Partial floor/candidate/record prefix changed')
    require(old_fit['resolved_starts'] == [True]*4+[False] and old_fit['not_run_starts'] == [5, 6, 7] and
            len(old_fit['records']) == 6 and len(old_fit['candidates']) == 5, 'Unexpected partial prefix')
    for row, method in zip(old_fit['records'][4:], ('L-BFGS-B', 'Powell')):
        require(row['start_index'] == 4 and row['method'] == method and row['status'] == 'exception' and
                row['error_type'] == 'ArithmeticError' and row['error'] == TARGET_ERROR and row['success'] is False,
                'Original failed start4 lineage changed')
    require(all(row['start_index'] in (4, 5, 6, 7) for row in new['records'][4:]), 'Completed start physically repeated')
    require([r for r in report['floor_checks'] if r['phase'] == 'train'] == partial['floor_checks'] and
            report['historical_comparisons'] == partial['historical_comparisons'], 'Saved historical/check values changed')
    return [('LIplus_inclusive', row) for row in new['records'][4:]]


def counter_rows(census):
    require(isinstance(census, dict), 'Evaluation census must be a mapping')
    result = {}
    for key, value in census.items():
        parts = key.split('|')
        require(len(parts) == 5, 'Unknown evaluation counter key')
        phase, model, order, context, gradient = parts
        require(phase in ('train', 'test') and model in ARMS and order in ('8', '16') and
                context in ('optimizer', 'original_support', 'refinement_fine') and gradient in ('True', 'False'),
                'Unrecognized evaluation context')
        counts = {k: value.get(k, 0) for k in ('attempted', 'returned', 'errors')}
        require(set(value) <= set(counts) and all(type(v) is int and v >= 0 for v in counts.values()) and
                counts['attempted'] == counts['returned']+counts['errors'], 'Evaluation counter does not reconcile')
        if context == 'optimizer':
            require(phase == 'train' and order == '8', 'Optimizer changed phase/order')
        if context == 'refinement_fine':
            require(phase == 'train' and order == '16' and gradient == 'True', 'Refinement changed phase/order/gradient')
        result[tuple(parts)] = counts
    return result


def inspect_physical_calls(entries, physical_records, pairs, science, receipt):
    """Cross-check real optimizer calls independently from reused logical records."""
    calls, pending = [], None
    reuse = []
    for entry in entries:
        kind = entry['event']
        if kind.startswith('reuse_'):
            require(pending is None, 'Reuse operation inside physical optimizer call')
            require(kind in ('reuse_arm', 'reuse_total_prefix', 'reuse_selected_training_check', 'reuse_historical_training_floor'),
                    'Unknown reuse operation')
            require(entry.get('physical_optimizer_calls', 0) == 0 and entry.get('physical_evaluations', 0) == 0,
                    'Reused evidence reported as physical work')
            reuse.append(entry)
            continue
        if kind == 'optimizer_start':
            require(pending is None, 'Nested physical optimizer')
            pending = entry
        else:
            require(kind == 'optimizer_end' and pending is not None, 'Missing optimizer start/end')
            start = pending; pending = None
            key = tuple(start[k] for k in ('model', 'start_index', 'method'))
            require(key == tuple(entry[k] for k in ('model', 'start_index', 'method')), 'Physical optimizer identity changed')
            calls.append((key, start, entry))
    require(pending is None and len(calls) == len(physical_records), 'Physical attempt census differs')
    require(len({key for key, _, _ in calls}) == len(calls), 'Duplicate physical optimizer attempt')
    by_key = {}
    for (key, start, end), (model, record) in zip(calls, physical_records):
        require(key == (model, record['start_index'], record['method']) and
                start['initial_parameters'] == record['initial_parameters'], 'Physical call differs from retained attempt')
        boxes = science['shared_bounds']+([] if model == 'null' else science['inhibition_bounds'])
        options = {k: science['solver'][k] for k in ('maxiter', 'maxls', 'ftol', 'gtol')} if key[2] == 'L-BFGS-B' else science['solver']['powell']
        require(start['bounds'] == boxes and start['options'] == options and start['jac'] is (key[2] == 'L-BFGS-B'),
                'Original solver recipe changed')
        attempted, returned = end['callback_attempts'], end['callback_returns']
        require(type(attempted) is int and type(returned) is int and 0 <= returned <= attempted and
                attempted-returned in (0, 1) and type(end['returned']) is bool, 'Invalid objective callback census')
        if end['returned']:
            require(attempted == returned and record.get('nfev') == attempted, 'Solver nfev differs from callback calls')
        else:
            require(record['status'] == 'exception' and attempted-returned == 1, 'Missing original objective failure')
        counter_rows(end['evaluation_census'])
        by_key[key] = end
    for pair in pairs:
        key, callback = pair['key'][:3], pair['key'][3]
        require(key in by_key and callback <= by_key[key]['callback_attempts'], 'Refinement has no physical callback')
    counters = counter_rows(receipt['evaluation_census'])
    for model in ARMS:
        for method, gradient in (('L-BFGS-B', 'True'), ('Powell', 'False')):
            selected = [end for (name, _, method_), _, end in calls if name == model and method_ == method]
            target = counters.get(('train', model, '8', 'optimizer', gradient), dict(attempted=0, returned=0, errors=0))
            refinements = [p for p in pairs if p['key'][0] == model and p['key'][2] == method]
            attempted = sum(r['callback_attempts'] for r in selected)
            callback_errors = sum(r['callback_attempts']-r['callback_returns'] for r in selected)
            # Every refinement begins with a coarse error; rejected refinements also
            # account for the outer callback error, so do not count those twice.
            accepted = sum(p['accepted'] for p in refinements)
            require(target['attempted'] == attempted and target['errors'] == callback_errors+accepted,
                    'Coarse optimizer evaluation census differs')
        fine = counters.get(('train', model, '16', 'refinement_fine', 'True'), dict(attempted=0, returned=0, errors=0))
        refs = [p for p in pairs if p['key'][0] == model]
        require(fine == dict(attempted=len(refs), returned=sum(p['fine_returned'] for p in refs),
                             errors=sum(not p['fine_returned'] for p in refs)), 'Added fine work was lost or duplicated')
    require(receipt['physical_optimizer_calls'] == [list(k) for k, _, _ in calls] and
            receipt['refinement_started'] == len(pairs) and receipt['refinement_accepted'] == sum(p['accepted'] for p in pairs) and
            receipt['refinement_rejected'] == sum(not p['accepted'] for p in pairs), 'Adapter counts disagree with saved events')
    require(receipt['callback_active'] is False and receipt['refinement_active'] is False, 'Unclosed objective/refinement context')
    return dict(actual_optimizer_attempts=len(calls), refinement_started=len(pairs),
                refinement_accepted=sum(p['accepted'] for p in pairs), refinement_rejected=sum(not p['accepted'] for p in pairs),
                actual_evaluations=sum(v['attempted'] for v in counters.values())), reuse


def inspect_support_counts(report, receipt, mode, physical_records):
    """Original frozen call roster outside optimizer callbacks, from saved state."""
    expected = {}
    def add(phase, model, order, returned=True):
        key = (phase, model, str(order), 'original_support', 'True')
        counts = expected.setdefault(key, dict(attempted=0, returned=0, errors=0))
        counts['attempted'] += 1
        counts['returned' if returned else 'errors'] += 1
    if mode == 'untouched':
        add('train', 'null', 8)  # Original historical training floor.
    for model in ARMS:
        if model not in report['fits']:
            continue
        reused = mode == 'partial' and model != 'LIplus_inclusive'
        if reused:
            continue
        if mode == 'untouched':
            add('train', model, 8)  # Original eligible floor before optimization.
        for name, record in physical_records:
            if name == model and record.get('finite_feasible') is True:
                add('train', model, 8, returned='fresh_score' in record)  # Original fresh check may fail before Powell rescue.
        if model in report.get('training_checks', {}):
            add('train', model, 8)
            add('train', model, 16)
    if report['passed']:
        add('test', 'null', 8)
        add('test', 'null', 16)
        for model in ARMS[1:]:
            add('test', model, 8)
            add('test', model, 16)
    actual = {key: value for key, value in counter_rows(receipt['evaluation_census']).items()
              if key[3] == 'original_support'}
    require(actual == expected, 'Original floor/fresh/selected/test evaluation roster changed')
    require(receipt['arm_calls'] == [m for m in ARMS if m in report['fits']] and
            receipt['selected_check_calls'] == [m for m in ARMS if m in report.get('training_checks', {})],
            'Original arm/selected-check order changed')


def inspect_reuse_map(reuse, report, partial, mode, policy, receipt, reuse_calls):
    require(reuse['schema'] == 'joint_exposure_refinement_reuse_v1' and reuse['mode'] == mode,
            'Missing explicit saved-computation reuse schema')
    physical = inspect_reused_values(report, partial, mode)
    expected_entries, expected_calls = [], []
    if mode == 'partial':
        expected_entries.append(dict(kind='historical_training_floor', pointer='/fits/null/candidates/0/score'))
        expected_calls.append(dict(event='reuse_historical_training_floor', physical_evaluations=0))
        for name in ARMS[:3]:
            expected_entries += [dict(kind='complete_arm', model=name, pointer='/fits/'+name),
                dict(kind='selected_training_check', model=name, pointer='/training_checks/'+name)]
            expected_calls += [dict(event='reuse_arm', model=name, physical_optimizer_calls=0),
                dict(event='reuse_selected_training_check', model=name, physical_evaluations=0)]
        expected_entries.append(dict(kind='total_prefix', model='LIplus_inclusive', candidate_indices=list(range(5)),
            record_indices=list(range(4)), prior_failed_record_indices=[4, 5]))
        expected_calls.append(dict(event='reuse_total_prefix', model='LIplus_inclusive', physical_optimizer_calls=0,
            candidate_indices=list(range(5)), record_indices=list(range(4))))
    require(reuse['entries'] == receipt['reuse_entries'] == expected_entries and reuse_calls == expected_calls,
            'Reused object/call roster changed')
    require(reuse['original_failure_reference'] == (policy['failed_case'] if mode == 'partial' else None) and
            reuse['reused_optimizer_attempts'] == (28 if mode == 'partial' else 0) and
            reuse['prior_failed_total_start4_attempts_retained'] == (2 if mode == 'partial' else 0),
            'Partial failed lineage or old/new attempt count changed')
    return physical


def inspect_amendment(current, report, result, policy, science, partial):
    amendment = report['numerical_amendment']
    require(result['numerical_amendment'] == amendment and amendment['version'] == VERSION and
            amendment['protocol_sha256'] == result['protocol_sha256'] and
            amendment['original_scientific_protocol_sha256'] == SCIENCE_SHA,
            'Amendment identity hidden or changed')
    mode = 'partial' if result['case_id'] == PARTIAL else 'untouched'
    require(amendment['computation_kind'] == 'amended_'+('partial_resume' if mode == 'partial' else 'untouched'),
            'Compatible/amended computation kind changed')
    root = Path(current)/'science'
    files = {'reuse_map_sha256': 'reuse_map.json', 'refinement_event_log_sha256': 'refinement_events.jsonl',
             'execution_calls_sha256': 'execution_calls.jsonl'}
    for key, filename in files.items():
        require(sha(root/filename) == amendment[key], 'Amendment log identity changed: '+filename)
    reuse = read(root/'reuse_map.json')
    require(amendment['original_failure_reference'] == reuse['original_failure_reference'], 'Failure lineage differs')
    pairs = inspect_refinements(records((root/'refinement_events.jsonl').read_bytes()), science)
    physical = inspect_reused_values(report, partial, mode)
    counts, reuse_calls = inspect_physical_calls(records((root/'execution_calls.jsonl').read_bytes()),
        physical, pairs, science, result['adapter'])
    inspect_reuse_map(reuse, report, partial, mode, policy, result['adapter'], reuse_calls)
    inspect_support_counts(report, result['adapter'], mode, physical)
    require(result['evaluation_census'] == result['adapter']['evaluation_census'] and
            result['refinement_census'] == dict(started=counts['refinement_started'], accepted=counts['refinement_accepted'],
                                                rejected=counts['refinement_rejected']) and
            result['actual_optimizer_attempts'] == counts['actual_optimizer_attempts'] and
            result['reused_optimizer_attempts'] == (28 if mode == 'partial' else 0), 'Old/new work counters changed')
    require(result['adapter']['phase_constructions'] == result['phase_constructions'], 'Phase construction receipt differs')
    require(sum(p['coarse_seconds']+p['fine_seconds'] for p in pairs) <= result['wall_seconds'],
            'Refinement times exceed actual case execution')
    counts['reused_optimizer_attempts'] = result['reused_optimizer_attempts']
    counts['prior_failed_attempts_retained'] = 2 if mode == 'partial' else 0
    return counts


def checker_review(repo, path, pin, policy):
    require(sha(path) == pin, 'Independent checker review changed')
    review = read(path)
    require(review['passed'] is True, 'Independent checker source review failed')
    live_review(review)
    names = [CHECKER_PATH, 'experiments/s04b_exposure_refinement_audit/__init__.py',
             'experiments/s04b_joint_remaining_audit/check.py', 'experiments/s04b_joint_audit/check.py',
             'experiments/s04b_joint_nuisance_audit/audit.py']
    require(policy['checker']['module'] == 'experiments.s04b_exposure_refinement_audit.check' and
            policy['checker']['sources'] == names, 'Independent checker graph changed')
    pins = {name: sha(safe(repo, name)) for name in names}
    require(pins[CHECKER_PATH] == sha(HERE), 'Different checker was executed')
    for name, pin in pins.items():
        require(review['reviewed_files_sha256'].get(name) == pin, 'Unreviewed checker dependency: '+name)
    return pins


def inspect_current(current, repo, policy, science, config, commit, checker_pins, partial):
    """Explicit amended admission, without asserting original source equivalence."""
    current, repo = Path(current), Path(repo)
    result, admission = read(current/'science/result.json'), read(current/'admission.json')
    conductor = read(current/'conductor_review.json')
    require(result['schema'] == 'joint_exposure_refinement_case_v1' and result['handled'] is True and
            result['disposition_valid'] is True and result['status'] == 'terminal_disposition' and
            result['scientific_completion'] is False, 'Technical/incomplete case cannot advance')
    name = result['case_id']
    require(name in policy['case_ids'] and name != UNKNOWN, 'Ineligible amended case')
    slot = next(s for s in policy['case_slots'] if s['case_id'] == name)
    require(admission['mode'] == 'exposure_refinement_case' and admission['case_id'] == name and
            admission['case_ids'] == [name] and result['admission_sha256'] == sha(current/'admission.json'),
            'Changed case admission')
    require(result['source_sha256'] == admission['source_sha256'], 'Executed/admitted source map differs')
    source_path = safe(repo, conductor['source_review'])
    require(sha(source_path) == conductor['source_review_sha256'] == conductor['host_source_review_sha256'],
            'Producer source review changed')
    source_review = read(source_path)
    require(source_review['passed'] is True, 'Producer source review failed')
    live_review(source_review)
    for relative, pin in result['source_sha256'].items():
        require(sha(safe(repo, relative)) == pin and conductor['reviewed_files_sha256'].get(relative) == pin and
                source_review['reviewed_files_sha256'].get(relative) == pin, 'Unreviewed executed dependency: '+relative)
    require(all(result['source_sha256'].get(k) == v for k, v in policy['source_sha256'].items()), 'Original dependency identities omitted')
    for required in ('adapter.py', 'partial_fit.py', 'case_driver.py', 'protocol.json', '__init__.py'):
        require('experiments/s04b_exposure_refinement/'+required in result['source_sha256'], 'Missing new amendment source identity')
    custody.verify_reviewed_sources(repo, commit, conductor, source_review)
    for relative, pin in checker_pins.items():
        require(conductor['reviewed_files_sha256'].get(relative) == pin, 'Checker absent from conductor graph')
    require(result['protocol_sha256'] == admission['protocol_sha256'] == admission['amendment_protocol_sha256'] == sha(repo/PROTOCOL_PATH),
            'Amendment protocol identity differs')
    require(result['runtime']['essential'] == policy['original_native']['runtime_essential'], 'Original numerical runtime changed')
    for key in ('library_sha256', 'build_receipt_sha256'):
        require(result[key] == admission[key] == policy['original_native'][key], 'Original native/build changed')
    require(result['allocation'] == slot and result['numerical_attempt_id'] == admission['numerical_attempt_id'], 'Attempt/allocation changed')
    require(admission['independent_review_passed'] is True and admission['external_supervision'] is True and
            admission['wall_seconds'] == slot['wall_seconds'] and admission['scientific_seconds'] == slot['scientific_seconds'],
            'Case numerical admission/caps changed')
    require(admission['threads'] == 2 and admission['workers'] == 1 and
            admission['sampled_process_tree_rss_cap_bytes'] == 6442450944 and admission['minimum_host_free_bytes'] == 2147483648,
            'Numerical resource admission changed')
    require(admission['operational_run_id'] == config['run_id'] == policy['shared_run']['run_id'] and
            admission['operational_run_config_sha256'] == policy['shared_run']['config_sha256'], 'Shared-run identity changed')
    expiry = dt.datetime.fromisoformat(admission['expires_utc'])
    require(expiry <= dt.datetime.fromisoformat(config['deadline_utc']) and
            expiry <= dt.datetime.fromisoformat(policy['shared_run']['expires_utc']), 'Shared deadline extended')
    spec, supervisor = read(current/'supervisor_spec.json'), read(current/'supervision/result.json')
    require(spec['wall_cap_seconds'] == slot['wall_seconds'] and spec['rss_cap_bytes'] == 6442450944 and
            spec['host_headroom_bytes'] == 2147483648, 'Supervision cap changed')
    for key in ('OMP_NUM_THREADS', 'OPENBLAS_NUM_THREADS', 'MKL_NUM_THREADS', 'NUMEXPR_NUM_THREADS', 'BLIS_NUM_THREADS'):
        require(spec['env'].get(key) == '2', 'Numeric thread limit changed')
    argv = spec['command']
    require(argv[1:4] == ['-B', '-m', 'experiments.s04b_exposure_refinement.case_driver'], 'Wrong supervised entrypoint')
    def arg(key):
        require(argv.count(key) == 1 and argv.index(key)+1 < len(argv), 'Missing/duplicate child argument: '+key)
        return argv[argv.index(key)+1]
    remote = arg('--output')
    require(arg('--mode') == slot['mode'] and arg('--case-id') == name and
            old.recorded_path(remote, remote, current) == (current/'science').resolve() and
            old.recorded_path(arg('--admission'), remote, current) == (current/'admission.json').resolve(), 'Supervised case/output differs')
    if slot['mode'] == 'partial':
        arg('--failed-prior')
    else:
        require('--failed-prior' not in argv, 'Untouched case received partial checkpoint')
    library = old.recorded_path(arg('--library'), remote, current)
    build_path = old.recorded_path(arg('--build-receipt'), remote, current)
    require(sha(library) == result['library_sha256'] and sha(build_path) == result['build_receipt_sha256'], 'Executed native bytes changed')
    build = read(build_path)
    require(build['passed'] is True and build['library_sha256'] == result['library_sha256'] and
            build['source_sha256'] == policy['source_sha256']['experiments/s04b_joint_nuisance/attenuation.cpp'], 'Build provenance changed')
    require(supervisor['status'] == 'passed' and supervisor['returncode'] == 0 and supervisor['launched'] is True and
            supervisor['stop_reason'] is None and not supervisor['cleanup_errors'] and not supervisor['survivors_after_cleanup'],
            'Child supervision did not complete cleanly')
    require(supervisor['spec_sha256'] == sha(current/'supervisor_spec.json') and
            supervisor['execution_log_sha256'] == sha(current/'supervision/execution.log') and
            supervisor['supervisor_sha256'] == sha(repo/'scripts/supervise_research.py'), 'Supervision custody changed')
    require(dt.datetime.fromisoformat(supervisor['started_utc']) <= dt.datetime.fromisoformat(supervisor['finished_utc']) <= expiry,
            'Execution exceeded shared expiry')
    seconds = core.number(result['wall_seconds'])
    outer = core.number(supervisor['wall_seconds_including_cleanup'])
    require(0 <= seconds <= slot['scientific_seconds'] and seconds <= supervisor['execution_wall_seconds'] <= outer <= slot['wall_seconds'] and
            supervisor['sampled_peak_tree_rss_bytes'] <= 6442450944 and supervisor['minimum_sampled_host_available_bytes'] >= 2147483648,
            'Case scientific/cleanup-inclusive resource cap exceeded')
    if name == PARTIAL:
        resource = policy['resources']
        require(Decimal(resource['partial_case_original_scientific_seconds'])+Decimal(str(seconds)) <= Decimal(2490) and
                Decimal(resource['partial_case_original_outer_seconds'])+Decimal(str(outer)) <= Decimal(2520),
                'Partial continuation granted a second original case cap')
    report_path, trace_path = safe(current/'science', result['report_file']), safe(current/'science', result['trace_file'])
    require(sha(report_path) == result['report_sha256'] and sha(trace_path) == result['trace_sha256'], 'Saved report/trace changed')
    report = read(report_path)
    source_case = next(c for c in read(repo/'reproduction/synthetic/input_manifest.json')['s04b']['cases'] if c['case_id'] == name)
    require(all(result['input_case'].get(k) == v for k, v in source_case.items()) and
            all(report.get(k) == source_case[k] for k in ('case_id', 'regime', 'seed', 'n_train', 'n_test')), 'Input/denominator changed')
    require(report['current_attempt_wall_seconds'] == report['wall_seconds'] <= seconds and
            report['prior_training_attempt_seconds'] == 0, 'Current physical case time was replaced by reused work')
    core.inspect_historical(report, source_case, repo)
    if result['disposition'] == 'complete':
        require(result['passed'] is True and result['scientific_passed'] is True and result['unknown_outcome_count'] == 0 and
                result['phase_constructions'] == [dict(start=30, end=395, returned=True), dict(start=395, end=760, returned=True)],
                'Complete case phase/acceptance flags changed')
        core.inspect_case(report, science)
        trace_matches(trace_path.read_bytes(), report)
        unknown = None
    else:
        require(result['disposition'] == 'scientific_unknown' and result['passed'] is False and
                result['scientific_passed'] is False and result['unknown_outcome_count'] == 5, 'Unknown flags changed')
        require(name != PARTIAL, 'Mandatory resumed pilot did not complete')
        unknown = old.inspect_unknown(report, science, result['phase_constructions'], trace_path)
        arm = report['fits'][unknown['failed_model']]
        require(result['terminal_solver_return'] == arm['records'][-1] and result['unknown_reason'] ==
            dict(error_type=report['error_type'], error=report['error'], arm_status=arm['status']), 'Unknown terminal evidence changed')
    names = [m for m in ARMS if m in report['fits']]
    census = dict(attempted_models=names, completed_models=[m for m in names if report['fits'][m]['passed']],
        not_run_models=list(ARMS[len(names):]), logical_optimizer_attempts=sum(len(report['fits'][m]['records']) for m in names),
        held_out_phase_constructed=len(result['phase_constructions']) == 2)
    if unknown:
        arm = report['fits'][unknown['failed_model']]
        census.update(unresolved_model=unknown['failed_model'], unresolved_start=unknown['unresolved_start'],
                      resolved_starts=arm['resolved_starts'], not_run_starts=arm['not_run_starts'])
    require(result['model_census'] == census, 'Logical model/start census changed')
    work = inspect_amendment(current, report, result, policy, science, partial)
    return result, report, unknown, work


def inspect_budget(index, policy):
    attempts = index['attempts']
    require([r['case_id'] for r in attempts] == policy['case_ids'][:len(attempts)] and
            len({r['numerical_attempt_id'] for r in attempts}) == len(attempts), 'Amended attempts skipped/repeated')
    for row, slot in zip(attempts, policy['case_slots']):
        require(0 <= core.number(row['seconds']) <= slot['scientific_seconds'] and
                row['seconds'] <= core.number(row['outer_seconds']) <= slot['wall_seconds'], 'Case cap expanded')
        require(type(row['actual_optimizer_attempts']) is int and row['actual_optimizer_attempts'] >= 1 and
                row['reused_optimizer_attempts'] == (28 if row['case_id'] == PARTIAL else 0), 'Attempt reuse accounting changed')
    resource = policy['resources']
    scientific = sum((Decimal(str(r['seconds'])) for r in attempts), Decimal(0))
    outer = sum((Decimal(str(r['outer_seconds'])) for r in attempts), Decimal(0))
    base = Decimal(resource['accounted_seconds'])
    require(base == sum((Decimal(v) for v in resource['costs_seconds'].values()), Decimal(0)), 'Original charges do not reconcile')
    remaining = Decimal(sum(s['wall_seconds'] for s in policy['case_slots'][len(attempts):]))
    overhead = Decimal(resource['future_host_overhead_seconds'])
    finalization = Decimal(resource['global_finalization_reserve_seconds'])
    accounted = base+outer
    upper = accounted+remaining+overhead+finalization
    require(upper <= Decimal(115200), 'Shared aggregate cap exceeded')
    expected = dict(base_accounted_seconds=base, amended_scientific_seconds=scientific, amended_outer_seconds=outer,
        remaining_case_slots_seconds=remaining, all_eight_host_overhead_reserved_seconds=overhead,
        global_finalization_reserve_seconds=finalization, accounted_seconds=accounted,
        upper_bound_seconds=upper, remaining_headroom_seconds=Decimal(115200)-upper)
    require(set(index['budget']) == set(expected), 'Budget schema changed')
    for key, value in expected.items():
        # Storage is binary64; this tolerance only reconciles display arithmetic.
        # All safety decisions above use exact Decimal values without tolerance.
        require(abs(Decimal(str(core.number(index['budget'][key])))-value) <= Decimal('0.00000001'),
                'Budget reconciliation differs: '+key)
    if attempts:
        first = attempts[0]
        require(Decimal(resource['partial_case_original_scientific_seconds'])+Decimal(str(first['seconds'])) <= Decimal(2490) and
                Decimal(resource['partial_case_original_outer_seconds'])+Decimal(str(first['outer_seconds'])) <= Decimal(2520),
                'Partial cumulative original allowance exceeded')
    return {key: str(value) for key, value in expected.items()}


def inspect_transition(index, prior, prior_review, base, result, report, current, policy, checker_pins, review_pin):
    require(index['schema'] == 'joint_exposure_refinement_index_v1' and index['passed'] is False and
            index['scientific_completion'] is False and index['numerical_amendment_version'] == VERSION and
            index['original_scientific_protocol_sha256'] == SCIENCE_SHA, 'Amended index claims original full success')
    require(index['original_native'] == policy['original_native'] and index['immutable_failure_reference'] == policy['permanent_unknown'] and
            index['original_exposure_failure_reference'] == policy['failed_case'] and index['compatible_saved_prefix'] == policy['base'],
            'Original evidence identities were substituted')
    if prior['schema'] == 'joint_remaining_index_v1':
        require(prior == base and result['case_id'] == PARTIAL, 'Wrong initial amended predecessor')
        old_attempts = []
    else:
        require(prior['schema'] == 'joint_exposure_refinement_index_v1' and prior['scientific_completion'] is False and
                prior['protocol_sha256'] == index['protocol_sha256'] and
                prior['host_source_sha256'] == index['host_source_sha256'] and
                prior['scientific_source_sha256'] == index['scientific_source_sha256'], 'Amended predecessor changed')
        old_attempts = prior['attempts']
    require(index['records'][:-1] == prior['records'] and index['records'][:44] == base['records'] and
            index['attempts'][:-1] == old_attempts, 'Accepted prefix or old accounting changed')
    require([r['case_id'] for r in index['records']] == policy['full_sequence'][:len(index['records'])] and
            len(index['records']) == 44+len(index['attempts']), 'Disposition roster changed')
    require(index['protocol_sha256'] == result['protocol_sha256'] and
            index['scientific_source_sha256'] == result['source_sha256'], 'Index/result amendment sources differ')
    source = index['records'][-1]['source'];host = Path(current).parent.parent
    require(source['kind'] == 'host_execution', 'New computation lacks execution custody')
    paths = dict(case_path=Path(current)/'science'/result['report_file'], trace_path=Path(current)/'science'/result['trace_file'],
        result_path=Path(current)/'science/result.json', supervision_path=Path(current)/'supervision/result.json')
    for key, path in paths.items():
        require(source[key] == path.relative_to(host).as_posix() and source[key.replace('_path', '_sha256')] == sha(path),
                'New source locator changed: '+key)
    expected = old.projection(report, result['disposition'], source)
    expected.update(numerical_amendment=result['numerical_amendment'], refinement_census=result['refinement_census'])
    if result['disposition'] == 'scientific_unknown':
        expected.update(unknown_origin='new_frozen_solver_cap', unknown_reason=result['unknown_reason'],
            model_census=result['model_census'], terminal_solver_return=result['terminal_solver_return'])
    require(index['records'][-1] == expected, 'New compact record differs from saved output')
    supervisor = read(Path(current)/'supervision/result.json')
    attempt = dict(case_id=result['case_id'], numerical_attempt_id=result['numerical_attempt_id'], host_execution_id=source['execution_id'],
        seconds=result['wall_seconds'], outer_seconds=supervisor['wall_seconds_including_cleanup'],
        result_sha256=source['result_sha256'], supervision_sha256=source['supervision_sha256'],
        actual_optimizer_attempts=result['actual_optimizer_attempts'], reused_optimizer_attempts=result['reused_optimizer_attempts'])
    require(index['attempts'][-1] == attempt and index['counts'] == old.expected_counts(index['records']), 'New attempt/counts differ')
    grant = read(host.parent/'admission.json')
    group = next(h for h in policy['resources']['future_hosts'] if h['host'] == grant['batch_id'])
    require(grant['mode'] == 'exposure_refinement_host_batch' and grant['case_ids'] == group['case_ids'] and
            result['case_id'] in group['case_ids'], 'Different host/case admitted')
    require(source['execution_id'] == grant['numerical_attempt_id'] and
            grant['child_attempt_ids'][result['case_id']] == result['numerical_attempt_id'], 'Unadmitted numerical attempt')
    require(index['host_source_sha256'] == grant['source_sha256'] and index['scientific_source_sha256'] == grant['scientific_source_sha256'] and
            index['protocol_sha256'] == grant['protocol_sha256'], 'Parent admitted different sources')
    position = group['case_ids'].index(result['case_id'])
    if position == 0:
        require(index['predecessor']['index_sha256'] == grant['prior_index_sha256'] and
                index['predecessor']['review_sha256'] == grant['prior_review_sha256'] and
                index['predecessor']['archive_sha256'] == grant['prior_archive_sha256'], 'Parent predecessor custody differs')
        if grant['batch_id'] == 1:
            require(grant['prior_index_sha256'] == policy['base']['index_sha256'] and
                    grant['prior_review_sha256'] == policy['base']['review_sha256'] and
                    grant['prior_archive_sha256'] == policy['base']['archive_sha256'], 'Different initial failed-host archive')
        else:
            live_review(prior_review)
            require(prior_review['review_kind'] == 'live_agent_saved_output_review' and prior_review['passed'] is True and
                    prior_review['audit_passed'] is True and prior_review['artifact_sha256'] == grant['prior_archive_sha256'],
                    'New host lacks accepted actual prior-host review')
    else:
        require(index['predecessor']['archive_sha256'] is None and prior['records'][-1]['case_id'] == group['case_ids'][position-1] and
                prior['records'][-1]['source']['execution_id'] == grant['numerical_attempt_id'], 'Within-host predecessor changed')
        require(prior_review['review_kind'] == 'automated_saved_output_check' and prior_review['passed'] is True and
                prior_review['audit_passed'] is True and prior_review['live_agent_review'] is False and
                prior_review['live_agent_review_performed'] is False and prior_review['final_batch_agent_review_required'] is True and
                prior_review['checker_sources_sha256'] == checker_pins and prior_review['checker_source_review_sha256'] == review_pin,
                'Within-host automated review changed or misattributed')
    require(grant['shared_run'] == policy['shared_run'] and grant['expires_utc'] == policy['shared_run']['expires_utc'], 'Parent extended shared limits')
    return inspect_budget(index, policy)


def audit_saved(args):
    require(not sys.flags.optimize, 'Optimized Python is not admitted')
    repo, current = Path(args.repo).resolve(), Path(args.current).resolve()
    policy, science, design = load_contract(repo)
    config = read(args.config)
    require(sha(args.config) == policy['shared_run']['config_sha256'], 'Shared configuration changed')
    checker_pins = checker_review(repo, Path(args.checker_source_review), args.checker_source_review_sha256, policy)
    base, partial = initial_evidence(repo, policy, science, design)
    result, report, unknown, work = inspect_current(current, repo, policy, science, config, args.commit, checker_pins, partial)
    prior_path, review_path = Path(args.prior).resolve(), Path(args.prior_review).resolve()
    prior, review = read(prior_path), read(review_path)
    index = read(current/'index.json')
    require(index['predecessor']['index_sha256'] == sha(prior_path) and
            index['predecessor']['review_sha256'] == sha(review_path), 'Actual predecessor bytes differ')
    if prior['schema'] == 'joint_remaining_index_v1':
        require(sha(prior_path) == policy['base']['index_sha256'] and sha(review_path) == policy['base']['review_sha256'],
                'Initial predecessor identity differs')
    else:
        require(review['index_sha256'] == sha(prior_path) and review['scientific_completion'] is False, 'Prior review/index mismatch')
    conductor = read(current/'conductor_review.json')
    for relative, pin in index['host_source_sha256'].items():
        require(sha(safe(repo, relative)) == pin and conductor['reviewed_files_sha256'].get(relative) == pin, 'Unreviewed host dependency')
    require('experiments/s04b_exposure_refinement/host.py' in index['host_source_sha256'], 'Amended host source missing')
    budget = inspect_transition(index, prior, review, base, result, report, current, policy, checker_pins, args.checker_source_review_sha256)
    complete = {r['case_id']: r for r in index['records'] if r['disposition'] == 'complete'}
    summary = old.disposition_summary(index['records'], complete, policy['full_sequence'])
    return dict(schema='joint_exposure_refinement_independent_saved_output_check_v1', passed=True, audit_passed=True,
        disposition_valid=True, disposition=result['disposition'], scientific_passed=result['scientific_passed'],
        scientific_completion=False, original_full_success_gate_passed=False, original_publication_gate_satisfied=False,
        review_kind='automated_saved_output_check', live_agent_review=False, live_agent_review_performed=False,
        final_batch_agent_review_required=True, index_sha256=sha(current/'index.json'),
        source_sha256=index['scientific_source_sha256'], host_source_sha256=index['host_source_sha256'],
        checker_sources_sha256=checker_pins, checker_source_review_sha256=args.checker_source_review_sha256,
        prior_index_sha256=sha(prior_path), prior_review_sha256=sha(review_path), report_sha256=result['report_sha256'],
        trace_sha256=result['trace_sha256'], case_id=result['case_id'], counts=index['counts'], budget=budget,
        unknown_census=unknown, refinement_and_reuse_census=work, independent_summary=summary,
        compatible_saved_histories=43, numerical_amendment_version=VERSION, all_histories_attempted=len(index['records']) == 80,
        numerical_calls=0, optimizer_calls=0,
        scope='Independent saved custody/arithmetic only; amended computations are explicit, permanent unknown remains unavailable.')


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('repo', 'current', 'prior', 'prior-review', 'config', 'commit', 'output', 'checker-source-review', 'checker-source-review-sha256'):
        parser.add_argument('--'+name, required=True)
    args = parser.parse_args(argv)
    output = Path(args.output).resolve()
    require(not output.exists(), 'Checker output must be fresh')
    try:
        result = audit_saved(args)
    except Exception as exc:
        result = dict(passed=False, audit_passed=False, disposition_valid=False, scientific_passed=False,
            scientific_completion=False, original_full_success_gate_passed=False, review_kind='automated_saved_output_check',
            live_agent_review=False, live_agent_review_performed=False, final_batch_agent_review_required=True,
            error_type=type(exc).__name__, error=str(exc), numerical_calls=0, optimizer_calls=0)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2, allow_nan=False)+'\n', encoding='utf-8')
    return 0 if result['audit_passed'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
