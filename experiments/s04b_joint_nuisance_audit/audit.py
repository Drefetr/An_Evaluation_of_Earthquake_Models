"""Independent consistency/custody audit of retained joint-comparison outputs.

No experiment module is imported and no likelihood, optimizer or generator is
called. Arithmetic agreement is distinct from scientific score recomputation.
"""
from pathlib import Path
import argparse
import hashlib
import json
import math
import statistics

MODELS = ('LI', 'LIplus_immigrant', 'LIplus_inclusive')
OUTCOMES = ((MODELS[0], 'raw'), (MODELS[1], 'raw'), (MODELS[1], 'BIC'),
            (MODELS[2], 'raw'), (MODELS[2], 'BIC'))
SCORE_KEYS = ('P', 'E', 'C', 'M', 'joint')
TOL = 1e-9


class AuditError(ValueError):
    pass


def require(condition, message):
    if not condition:
        raise AuditError(message)


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8'),
                      parse_constant=lambda value: (_ for _ in ()).throw(AuditError('Nonfinite JSON ' + value)))


def sha(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def safe(root, relative):
    path = (Path(root) / relative).resolve()
    require(not Path(relative).is_absolute() and path.is_relative_to(Path(root).resolve()), 'Escaping artifact path')
    return path


def number(value):
    require(not isinstance(value, bool) and isinstance(value, (int, float)) and math.isfinite(value), 'Finite number required')
    return value


def close(a, b, message='Numeric mismatch', tolerance=TOL):
    require(abs(number(a) - number(b)) <= tolerance, message)


def vector(a, b, message='Vector mismatch'):
    require(len(a) == len(b), message)
    for left, right in zip(a, b):
        close(left, right, message)


def score(value, selected=False):
    for key in SCORE_KEYS:
        number(value[key])
    close(value['C'], -value['E'], 'Compensator sign')
    close(value['joint'], math.fsum((value['P'], value['C'], value['M'])), 'P+C+M identity')
    if 'nll' in value:
        close(value['nll'], -value['joint'], 'NLL sign')
    require(value['E'] >= (0 if selected else -TOL), 'Negative exposure')


def same_score(left, right):
    for key in SCORE_KEYS:
        close(left[key], right[key], 'Score mismatch: ' + key)


def sides(theta, boxes):
    require(len(theta) == len(boxes), 'Coordinate dimension')
    result = []
    for value, (low, high) in zip(theta, boxes):
        number(value)
        require(low <= value <= high, 'Infeasible selected coordinate')
        result.append('lower' if abs(value-low) <= 1e-8 else 'upper' if abs(value-high) <= 1e-8 else None)
    return result


def projected(theta, gradient, boxes):
    require(len(theta) == len(gradient) == len(boxes), 'Projected-gradient dimension')
    result = []
    for point, derivative, (low, high) in zip(theta, gradient, boxes):
        number(derivative)
        blocked = (point <= low + 1e-8 and derivative > 0) or (point >= high - 1e-8 and derivative < 0)
        result.append(0. if blocked else derivative)
    return result


def expected_start(protocol, count, arm, index, null_parameters):
    offset, trend, branching, c, power = protocol['starts']['shared_templates'][index]
    intercept = min(-.1, max(-11.5, math.log(.6 * max(count, 1) / 365)))
    common = [min(0., max(-12., intercept + offset)), trend, branching, math.log(c), power]
    if arm == 'null':
        return common
    strength, radius, memory = protocol['starts']['inhibition_templates'][index]
    if index == 0:
        common = null_parameters[:5]
    return [*common, strength, math.log(radius), math.log(memory)]


def inspect_fit(fitted, arm, protocol, count, null_parameters):
    require(fitted['passed'] is True and fitted['status'] == 'complete', 'Unknown fit cannot pass')
    require(fitted['model'] == arm and fitted['required_starts'] == 8, 'Wrong fit roster')
    require(fitted['resolved_starts'] == [True] * 8, 'Unresolved prescribed starts')
    boxes = protocol['shared_bounds'] + ([] if arm == 'null' else protocol['inhibition_bounds'])
    width = len(boxes)
    candidates = fitted['candidates']
    require(len(candidates) == 9 and [c['state_index'] for c in candidates] == list(range(9)), 'Candidate state roster')
    floor = candidates[0]
    require(floor['kind'] == ('historical_floor' if arm == 'null' else 'new_null_floor') and floor['start_index'] == -1, 'Eligible floor missing')
    if arm != 'null':
        vector(floor['parameters'], null_parameters, 'Eligible alternative floor is not the new null')
    else:
        require(floor['parameters'][5] == 0., 'Historical null has inhibition')
    records = fitted['records']
    starts = []
    for index in range(8):
        attempts = [item for item in records if item['start_index'] == index]
        require(len(attempts) in (1, 2), 'Attempt count differs from bounded recovery policy')
        require([item['method'] for item in attempts] == ['L-BFGS-B', 'Powell'][:len(attempts)], 'Solver order')
        vector(attempts[0]['initial_parameters'], expected_start(protocol, count, arm, index, null_parameters), 'Prescribed initial point changed')
        require(attempts[-1]['success'] is True, 'Start did not resolve')
        if len(attempts) == 2:
            require(attempts[0]['success'] is False, 'Rescue after successful primary')
            primary = attempts[0]
            restart = primary.get('returned_parameters') if primary.get('finite_feasible') and primary.get('parameters') is not None else primary['initial_parameters']
            vector(attempts[1]['initial_parameters'], restart, 'Rescue restart changed')
        for attempt in attempts:
            require(type(attempt['success']) is bool, 'Attempt success must be boolean')
            if attempt['status'] == 'exception':
                require(attempt['error_type'] in ('ArithmeticError', 'FloatingPointError', 'OverflowError', 'ZeroDivisionError'), 'Resource/programming exception recovered')
            if attempt['success']:
                require(attempt['status'] == 'returned' and attempt['solver_success'] is True and attempt['finite_feasible'] is True, 'Invalid successful attempt')
                require(attempt['nit'] <= (protocol['solver']['maxiter'] if attempt['method'] == 'L-BFGS-B' else protocol['solver']['powell']['maxiter']), 'Iteration cap exceeded')
                if attempt['method'] == 'Powell':
                    require(attempt['nfev'] <= protocol['solver']['powell']['maxfev'], 'Powell function cap exceeded')
                score(attempt['fresh_score'])
                close(attempt['fresh_nll_delta'], abs(attempt['fresh_score']['nll'] - attempt['returned_nll']), 'Fresh NLL delta')
                require(attempt['fresh_nll_delta'] <= TOL, 'Fresh NLL gate')
                require(attempt['boundaries'] == sides(attempt['parameters'][:width], boxes), 'Attempt boundary census')
                vector(attempt['projected_gradient'], projected(attempt['parameters'][:width], attempt['gradient'][:width], boxes), 'Attempt projected gradient')
        chosen = candidates[index + 1]
        require(chosen['kind'] == 'optimizer' and chosen['start_index'] == index, 'Resolved start state missing')
        vector(chosen['parameters'], attempts[-1]['parameters'])
        same_score(chosen['score'], attempts[-1]['fresh_score'])
        vector(chosen['gradient'], attempts[-1]['gradient'])
        starts.extend(attempts)
    require(starts == records, 'Attempt order or unregistered extra attempt')
    for candidate in candidates:
        require(len(candidate['parameters']) == 8, 'Full coordinate dimension')
        score(candidate['score'])
        sides(candidate['parameters'][:width], boxes)
        if arm == 'null':
            vector(candidate['parameters'][5:], [0., math.log(30.), math.log(7.)], 'Null inactive coordinates')
        require(len(candidate['gradient']) == 8, 'Gradient dimension')
        for value in candidate['gradient']:
            number(value)
    lowest = min(c['score']['nll'] for c in candidates)
    tied = [c for c in candidates if c['score']['nll'] == lowest]
    winner = floor if floor in tied else sorted(tied, key=lambda c: c['start_index'])[0]
    require(fitted['selected'] == winner and fitted['selected_state_index'] == winner['state_index'], 'Selected state or exact-tie rule')
    require(winner['score']['nll'] <= floor['score']['nll'] + TOL, 'Eligible floor worsened')
    if arm != 'null':
        gaps = [(c['state_index'], floor['score']['nll'] - c['score']['nll']) for c in candidates
                if c['parameters'][5] == 0 and floor['score']['nll'] - c['score']['nll'] > TOL]
        require([g['state_index'] for g in fitted['null_search_gaps']] == [g[0] for g in gaps], 'Null-search gap census')
        for stored, (_, gain) in zip(fitted['null_search_gaps'], gaps):
            close(stored['train_nll_improvement'], gain)


def inspect_training(check, fitted, boxes, protocol):
    require(check['passed'] is True, 'Training numerical gate failed')
    vector(check['parameters'], fitted['selected']['parameters'])
    score(check['coarse'])
    score(check['fine'], selected=True)
    same_score(check['coarse'], fitted['selected']['score'])
    difference = abs(check['fine']['joint'] - check['coarse']['joint'])
    close(check['absolute_joint_delta'], difference)
    require(difference <= protocol['quadrature']['joint_absolute_tolerance'], 'Training quadrature tolerance')
    coarse = projected(check['parameters'][:len(boxes)], fitted['selected']['gradient'][:len(boxes)], boxes)
    vector(check['projected_gradient_coarse'], coarse)
    fine = check['projected_gradient_fine']
    require(len(fine) == len(coarse), 'Fine gradient dimensions')
    difference = max(abs(number(a)-number(b))/max(1., abs(a), abs(b)) for a, b in zip(coarse, fine))
    close(check['projected_gradient_scaled_delta'], difference)
    require(difference <= protocol['quadrature']['selected_training_gradient_scaled_tolerance'], 'Training gradient tolerance')
    close(check['projected_kkt_infinity_norm'], max(map(abs, fine)))


def inspect_case(report, protocol):
    require(report['passed'] is True and report['status'] == 'complete', 'Incomplete/unknown case')
    require(report['training_selections_frozen'] is True, 'Missing training freeze record')
    require(set(report['fits']) == {'null', *MODELS}, 'Fit family roster')
    fits = report['fits']
    parameters = fits['null']['selected']['parameters']
    for arm in ('null', *MODELS):
        inspect_fit(fits[arm], arm, protocol, report['n_train'], parameters)
        box = protocol['shared_bounds'] + ([] if arm == 'null' else protocol['inhibition_bounds'])
        inspect_training(report['training_checks'][arm], fits[arm], box, protocol)
    null_training = report['training_checks']['null']
    close(null_training['coarse']['joint'], null_training['fine']['joint'], 'Analytic null changed order')
    null = report['new_null_test']
    score(null, selected=True)
    threshold = 1.5 * math.log(max(report['n_train'], 1))
    close(report['bic_threshold'], threshold)
    outcomes = report['outcomes']
    require(len(outcomes) == 5 and [(x['model'], x['gate']) for x in outcomes] == list(OUTCOMES), 'Five-outcome roster/order')
    for row in outcomes:
        arm, gate = row['model'], row['gate']
        fitted = fits[arm]
        training = report['training_checks'][arm]
        gain = null_training['fine']['nll'] - training['fine']['nll']
        coarse_gain = null_training['coarse']['nll'] - training['coarse']['nll']
        require(training['fine']['nll'] <= null_training['fine']['nll'] + TOL, 'Fine alternative worsens eligible null')
        active = gain > threshold
        close(row['training_gain'], gain)
        close(row['coarse_training_gain'], coarse_gain)
        close(row['fine_threshold_distance'], gain-threshold)
        close(row['coarse_threshold_distance'], coarse_gain-threshold)
        require(row['gate_active'] is active and row['coarse_fine_gate_disagreement'] is ((coarse_gain > threshold) != active), 'Training-only gate mismatch')
        test = report['test_checks'][arm]
        score(test['fine'], selected=True)
        score(test['coarse'])
        error = abs(test['fine']['joint'] - test['coarse']['joint'])
        close(test['absolute_joint_delta'], error)
        require(error <= protocol['quadrature']['joint_absolute_tolerance'], 'Held-out quadrature gate')
        floor = fitted['selected']['state_index'] == 0 or (gate == 'BIC' and not active)
        expected_parameters = parameters if floor else fitted['selected']['parameters']
        expected_score = null if floor else test['fine']
        expected_gain = 0. if floor else expected_score['joint'] - null['joint']
        require(row['floor_return'] is floor, 'Floor-return flag')
        require(row['selected_state_index'] == (0 if floor else fitted['selected_state_index']), 'Prediction state index')
        vector(row['parameters'], expected_parameters)
        same_score(row['score'], expected_score)
        same_score(row['new_null_score'], null)
        close(row['new_gain'], expected_gain)
        if floor:
            require(row['new_gain'] == 0 and row['score'] == null, 'Floor return must use exact stored null score')
        else:
            require(row['new_gain'] == expected_gain, 'Gain must be exact stored score subtraction before strict-win counting')
        for key in SCORE_KEYS:
            expected = 0. if floor else expected_score[key] - null[key]
            close(row['delta'][key], expected, 'Outcome component ' + key)
        close(row['new_gain'], math.fsum(row['delta'][k] for k in ('P', 'C', 'M')))
        require(row['delta']['M'] == 0 and row['delta']['C'] == -row['delta']['E'], 'Shared mark/sign identity')
        for key, expected in {'new_win': expected_gain > 0, 'near_zero': abs(expected_gain) <= TOL,
                              'robust_positive': expected_gain > TOL, 'robust_negative': expected_gain < -TOL,
                              'off_floor': expected_parameters[5] > 0,
                              'null_search_gap_detected': bool(fitted['null_search_gaps'])}.items():
            require(row[key] is expected, 'Outcome flag: ' + key)
        require(row['boundaries'] == sides(expected_parameters, protocol['shared_bounds'] + protocol['inhibition_bounds']), 'Outcome boundary census')
    require(len(report['floor_checks']) == 6 and {(x['phase'], x['model']) for x in report['floor_checks']} ==
            {(phase, model) for phase in ('train', 'test') for model in MODELS}, 'Six historical floor-check roster')
    for check in report['floor_checks']:
        require(check['tolerance'] == TOL, 'Historical floor tolerance changed')
        close(check['absolute_delta'], abs(check['actual_nll']-check['expected_nll']))
        close(check['actual_nll'], check['expected_nll'], 'Historical floor failed')
    require(len(report['historical_comparisons']) == 5 and {(x['model'], x['gate']) for x in report['historical_comparisons']} == set(OUTCOMES), 'Historical comparison roster')
    for row in report['historical_comparisons']:
        require(row['passed'] is True, 'Historical identity failed')
        close(row['fixed_floor_gain'], row['saved_procedure_joint'] - row['fixed_floor_joint'])
        close(row['intercept_only_gain'], row['saved_procedure_joint'] - row['intercept_floor_joint'])
        outcome = next(x for x in outcomes if (x['model'], x['gate']) == (row['model'], row['gate']))
        require(outcome['historical'] == row, 'Historical comparator copy mismatch')
        close(outcome['saved_procedure_vs_new_null'], row['saved_procedure_joint'] - null['joint'])
    return report


def interval(wins, count):
    # Solve the quadratic score inequality, independently of the author's
    # centre/half-width implementation. This is pointwise Wilson coverage.
    z2 = statistics.NormalDist().inv_cdf(.975) ** 2
    aa, bb, cc = count + z2, -(2*wins + z2), wins*wins/count
    discriminant = math.sqrt(max(0., bb*bb - 4*aa*cc))
    return [max(0., (-bb-discriminant)/(2*aa)), min(1., (-bb+discriminant)/(2*aa))]


def aggregate(reports, protocol):
    rows = []
    boxes = protocol['shared_bounds'] + protocol['inhibition_bounds']
    for regime in (4, 5, 6, 7):
        group = [case for case in reports if case['regime'] == regime]
        if not group:
            continue
        for model, gate in OUTCOMES:
            outcomes = [next(row for row in case['outcomes'] if (row['model'], row['gate']) == (model, gate)) for case in group]
            gains = [row['score']['joint'] - row['new_null_score']['joint'] if not row['floor_return'] else 0. for row in outcomes]
            count, wins = len(gains), sum(value > 0 for value in gains)
            boundary_rows = [sides(row['parameters'], boxes) for row in outcomes]
            row = dict(regime=regime, model=model, gate=gate, N=count,
                       mean_gain=statistics.mean(gains), median_gain=statistics.median(gains), wins=wins,
                       wilson95=interval(wins, count), near_zero=sum(abs(g) <= TOL for g in gains),
                       positive_near_zero=sum(0 < g <= TOL for g in gains), robust_positive=sum(g > TOL for g in gains),
                       robust_negative=sum(g < -TOL for g in gains), off_floor=sum(r['parameters'][5] > 0 for r in outcomes),
                       floor_returns=sum(r['floor_return'] for r in outcomes), unknowns=0,
                       a_boundary=sum(b[0] is not None for b in boundary_rows), eta_lower=sum(b[5] == 'lower' for b in boundary_rows),
                       eta_upper=sum(b[5] == 'upper' for b in boundary_rows),
                       null_search_gap_cases=sum(bool(case['fits'][model]['null_search_gaps']) for case in group),
                       coarse_fine_gate_disagreements=sum(r['coarse_fine_gate_disagreement'] for r in outcomes),
                       optimizer_failed_attempts=sum(attempt['success'] is False for case in group for arm in ('null', model) for attempt in case['fits'][arm]['records']),
                       coordinate_boundaries={name: {side: sum(b[i] == side for b in boundary_rows) for side in ('lower', 'upper')}
                                              for i, name in enumerate(protocol['coordinates'])},
                       realized_thinning={key: sum(case['thinning'][key] for case in group) for key in
                                          ('accepted_immigrants', 'rejected_immigrants', 'accepted_offspring', 'rejected_offspring')},
                       mean_training_events=statistics.mean(case['n_train'] for case in group),
                       mean_test_events=statistics.mean(case['n_test'] for case in group),
                       primary=(regime, model, gate) in ((5, MODELS[1], 'raw'), (7, MODELS[2], 'raw')))
            rows.append(row)
    return rows


def compare_tree(actual, expected, label='summary'):
    """All independently derived fields must exist and agree; prose may extend them."""
    if isinstance(expected, dict):
        require(isinstance(actual, dict), label + ' is not an object')
        for key, value in expected.items():
            require(key in actual, label + ' missing ' + key)
            compare_tree(actual[key], value, label + '.' + key)
    elif isinstance(expected, list):
        require(isinstance(actual, list) and len(actual) == len(expected), label + ' length')
        for index, value in enumerate(expected):
            compare_tree(actual[index], value, label + '[' + str(index) + ']')
    elif isinstance(expected, bool) or expected is None or isinstance(expected, str):
        require(actual == expected and type(actual) is type(expected), label + ' value')
    elif isinstance(expected, int):
        require(type(actual) is int and actual == expected, label + ' count')
    else:
        close(actual, expected, label)


def inspect_roster(result, protocol):
    phase = result['phase']
    require(phase in ('pilot', 'full'), 'Unknown phase')
    require(len(protocol['roster']) == len(set(protocol['roster'])) == 80, 'Protocol requires unique80 roster')
    require(len(protocol['pilot']) == len(set(protocol['pilot'])) == 5 and set(protocol['pilot']) <= set(protocol['roster']), 'Protocol requires fixed five-case pilot')
    expected = protocol['pilot'] if phase == 'pilot' else protocol['pilot'] + [c for c in protocol['roster'] if c not in protocol['pilot']]
    require(result['passed'] is True and result['status'] == 'complete', 'Unknown/not-run campaign is not accepted')
    require([r['case_id'] for r in result['cases']] == expected, 'Missing, extra, duplicated, or reordered case')
    require(result['unknown_case_ids'] == [], 'Unknown cases remain')
    require(result['not_run_case_ids'] == [c for c in protocol['roster'] if c not in expected], 'Not-run census')
    count = len(expected)
    resumed = 'training_resume' in result
    for key, wanted in dict(new_fit_count=(16 if resumed else 20) if phase == 'pilot' else 300, cumulative_fit_count=4*count,
                            outcome_count=5*count, historical_floor_checks=6*count,
                            historical_comparison_rows=5*count).items():
        require(type(result[key]) is int and result[key] == wanted, 'Campaign count: ' + key)
    if resumed or 'reused_fit_count' in result:
        wanted = (4 if resumed else 0) if phase == 'pilot' else 20
        require(type(result['reused_fit_count']) is int and result['reused_fit_count'] == wanted, 'Reused fit census')
    return expected


def inspect_training_resume(result, results, source, admission, reports):
    """Validate an immutable failed-run training checkpoint without author imports."""
    import zipfile
    provenance = result['training_resume']
    policy = read(source / 'checkpoint_repair.json')
    expected_files = {
        'failed_result_sha256': 'training_resume/failed_result.json',
        'checkpoint_sha256': 'training_resume/frozen_training.json',
        'attempts_sha256': 'training_resume/frozen_training.attempts.jsonl',
        'audit_sha256': 'training_resume/independent_partial_review.json',
        'failed_archive_sha256': 'training_resume/failed_pilot_original.zip'}
    require(provenance['evidence_files'] == expected_files, 'Resume evidence roster')
    for key, relative in expected_files.items():
        require(sha(safe(results, relative)) == provenance[key] == policy[key], 'Resume evidence pin: ' + key)
    if result['phase'] == 'pilot':
        grant = admission['training_resume']
        require(grant['independent_review_passed'] is True and all(grant[k] == policy[k] for k in expected_files), 'Resume admission pin')
    require(read(results/'training_resume/provenance.json') == provenance, 'Retained resume provenance')
    old = read(results/'training_resume/failed_result.json')
    frozen = read(results/'training_resume/frozen_training.json')
    review = read(results/'training_resume/independent_partial_review.json')
    require(old['passed'] is False and old['phase'] == 'pilot' and old['cases'] == [], 'Original run was not the specified failed pilot')
    require(review['passed'] is True and review['scientific_pilot_passed'] is False, 'Partial review status')
    require(old['source_sha256'] == policy['predecessor_source_sha256'] == provenance['predecessor_source_sha256'], 'Predecessor source map')
    for name, digest in old['source_sha256'].items():
        if name != 'run.py':
            require(sha(safe(source, name)) == digest, 'Resume changed mathematical source, protocol, or inputs')
    source_archive = source/'pre_repair_source.zip'
    require(sha(source_archive) == policy['source_archive_sha256'], 'Predecessor source archive pin')
    with zipfile.ZipFile(source_archive) as archive:
        require(len(archive.namelist()) == len(old['source_sha256']) and set(archive.namelist()) == set(old['source_sha256']), 'Predecessor source archive roster')
        for name, digest in old['source_sha256'].items():
            require(hashlib.sha256(archive.read(name)).hexdigest() == digest, 'Predecessor source archive bytes')
    with zipfile.ZipFile(results/'training_resume/failed_pilot_original.zip') as archive:
        for name, relative in [('result.json', 'failed_result.json'),
                               (policy['case_id']+'.json', 'frozen_training.json'),
                               (policy['case_id']+'.attempts.jsonl', 'frozen_training.attempts.jsonl')]:
            candidates = [member for member in archive.namelist() if member == 'science/'+name or member.endswith('/science/'+name)]
            require(len(candidates) == 1 and archive.read(candidates[0]) == (results/'training_resume'/relative).read_bytes(), 'Original archive/checkpoint bytes')
    require(old['runtime'] == provenance['predecessor_runtime'] and old['runtime']['essential'] == result['runtime']['essential'], 'Resume runtime identity')
    for key in ('library_sha256', 'build_receipt_sha256'):
        require(old[key] == result[key], 'Resume native identity: ' + key)
    require(provenance['reused_fit_arms'] == 4 and provenance['repeated_training_evaluations'] == 0, 'Resume repeated training work')
    require(frozen['training_selections_frozen'] is True and frozen['passed'] is False and frozen['outcomes'] == [], 'Frozen checkpoint scope')
    key = policy['case_id']
    require(frozen['case_id'] == provenance['case_id'] == key, 'Resume case identity')
    current = next(row for row in reports if row['case_id'] == key)
    require(current['resume_provenance'] == provenance, 'Case resume provenance')
    protected = {name: current[name] for name in policy['training_payload_keys']}
    protected['floor_checks'] = [row for row in current['floor_checks'] if row['phase'] == 'train']
    protected['plan_dimensions'] = {'train': current['plan_dimensions']['train']}
    original = {name: frozen[name] for name in policy['training_payload_keys']}
    require(protected == original, 'Frozen training payload changed')
    canonical = json.dumps(original, sort_keys=True, separators=(',', ':'), allow_nan=False).encode('utf-8')
    require(hashlib.sha256(canonical).hexdigest() == policy['training_payload_canonical_sha256'] == provenance['training_payload_canonical_sha256'], 'Canonical frozen payload')
    require(sha(results/(key+'.attempts.jsonl')) == policy['attempts_sha256'] == current['attempts_sha256'], 'Training trace replay changed')
    prior = number(old['wall_seconds'])
    close(prior, policy['prior_scientific_seconds'], 'Original attempt wall charge')
    close(prior, provenance['prior_scientific_seconds'], 'Provenance prior wall charge')
    close(current['prior_training_attempt_seconds'], prior, 'Case prior wall charge')
    close(current['wall_seconds'], number(current['current_attempt_wall_seconds'])+prior, 'Case cumulative wall')
    close(result['cumulative_scientific_seconds'], number(result['wall_seconds'])+number(result['prior_scientific_seconds']), 'Campaign cumulative wall')
    if result['phase'] == 'pilot':
        close(result['prior_scientific_seconds'], prior, 'Pilot prior wall charge')
        require(result['cumulative_scientific_seconds'] <= 1800 and admission['wall_seconds'] <= 1800-prior, 'Cumulative pilot wall cap')
    else:
        require(result['cumulative_scientific_seconds'] <= 14400, 'Cumulative full wall cap')
    return dict(case_id=key, reused_training_fits=4, repeated_training_evaluations=0,
                prior_scientific_seconds=prior, frozen_checkpoint_sha256=policy['checkpoint_sha256'])


def inspect_trace(path, report):
    require(sha(path) == report['attempts_sha256'], 'Attempt log hash')
    lines = [json.loads(line) for line in Path(path).read_text(encoding='utf-8').splitlines()]
    expected = []
    for arm in ('null', *MODELS):
        for record in report['fits'][arm]['records']:
            expected.append(dict(event='attempt_start', model=arm, start_index=record['start_index'],
                                 method=record['method'], initial_parameters=record['initial_parameters'],
                                 status='running', success=False))
            expected.append(dict(event='attempt_end', model=arm, **record))
    require(lines == expected, 'Attempt trace differs from retained fit records')


def inspect_historical(report, case, repo):
    root = repo / 'reproduction/synthetic'
    expected = read(safe(root, case['expected']))
    states = read(safe(root, case['states']))
    old_relative = 'validation/live_results/methodological_20261106/refitted_floor/' + case['case_id'] + '.json'
    old = read(safe(repo, old_relative))
    require(report['input_sha256'] == {**{case[k]: sha(safe(root, case[k])) for k in
                                         ('history', 'generator_receipt', 'expected')},
                                       old_relative: sha(safe(repo, old_relative))}, 'Case input hashes')
    require(report['thinning'] == read(safe(root, case['generator_receipt']))['counters'], 'Thinning census differs from generation receipt')
    require(report['stratum'] == ('count-suppressed/weak-geometry' if case['regime'] in (5, 7) else 'narrow-short'), 'Regime stratum')
    original = old['fixed_backbone']
    null_floor = report['fits']['null']['candidates'][0]
    vector(null_floor['parameters'], [original['a_historical'], original['d'], original['n'], math.log(original['c']),
                                      original['p'], 0., math.log(30.), math.log(7.)], 'Historical null coordinates')
    same_score(null_floor['score'], old['phases']['train']['historical'])
    for check in report['floor_checks']:
        phase, model = check['phase'], check['model']
        fit = read(safe(root, case['fits'][model]))
        indices = [i for i, s in enumerate(states[model]) if s['pars'] == fit['floor']]
        require(bool(indices), 'Saved eligible floor missing')
        values = expected['phase_values']['order' + ('16_train' if phase == 'train' else '32_test')][model][indices[0]]
        close(check['expected_nll'], values[0], 'Historical expected state NLL')
        close(check['actual_nll'], -old['phases'][phase]['historical']['joint'], 'Historical floor phase NLL')
        close(values[5], old['phases'][phase]['historical']['P'], 'Historical point sum')
    for row in report['historical_comparisons']:
        key = row['model'], row['gate']
        prior = next(r for r in old['outcomes'] if (r['model'], r['gate']) == key)
        archived = next(r for r in expected['results'] if (r['model'], r['gate']) == key)
        index = archived['selected_state_index']
        require(row['selected_state_index'] == prior['selected_state_index'] == index, 'Historical selected state')
        close(row['saved_procedure_joint'], -expected['phase_values']['order32_test'][key[0]][index][0])
        for output, source in [('fixed_floor_gain', 'original_gain'), ('intercept_only_gain', 'new_gain'),
                               ('saved_procedure_joint', 'saved_procedure_test_joint'), ('fixed_floor_joint', 'original_floor_test_joint')]:
            close(row[output], prior[source], 'Historical copied ' + output)
        close(row['fixed_floor_gain'], archived['gain'], 'Archive gain')
        close(row['intercept_floor_joint'], old['phases']['test']['refitted']['joint'])
        require(row['historical_off_floor'] is prior['original_off_floor'], 'Historical off-floor indicator')


def inspect_pilot_reuse(result, pilot, results, protocol, admission):
    prior = read(pilot / 'result.json')
    inspect_roster(prior, protocol)
    require(prior['phase'] == 'pilot', 'Reuse source is not pilot')
    require(result['pilot_result_sha256'] == admission['pilot_result_sha256'] == sha(pilot / 'result.json'), 'Pilot result pin')
    require(admission['pilot_output_review_passed'] is True, 'Missing independent pilot review admission')
    for key in ('source_sha256', 'library_sha256'):
        require(result[key] == prior[key], 'Pilot/full identity: ' + key)
    require(result['runtime']['essential'] == prior['runtime']['essential'] and result['pilot_runtime'] == prior['runtime'], 'Pilot/full essential runtime changed')
    if 'training_resume' in prior:
        require(result['training_resume'] == prior['training_resume'], 'Pilot/full resumed-training provenance changed')
        close(result['prior_scientific_seconds'], prior['cumulative_scientific_seconds'], 'Full campaign prior wall charge')
        for relative in prior['training_resume']['evidence_files'].values():
            require(sha(safe(pilot, relative)) == sha(safe(results, relative)), 'Pilot/full resume evidence changed')
    for entry in prior['cases']:
        reused = next(r for r in result['cases'] if r['case_id'] == entry['case_id'])
        require(reused['source'] == 'exact pilot reuse' and reused['sha256'] == entry['sha256'], 'Pilot case not reused exactly')
        require(sha(safe(pilot, entry['file'])) == sha(safe(results, reused['file'])) == entry['sha256'], 'Reused case bytes')
        trace = entry['case_id'] + '.attempts.jsonl'
        require(sha(safe(pilot, trace)) == sha(safe(results, trace)), 'Reused attempt trace bytes')


def attempt_census(reports, protocol):
    """Count attempts once per arm, without repeating the null in contrasts."""
    result = []
    for regime in (4, 5, 6, 7):
        group = [case for case in reports if case['regime'] == regime]
        if not group:
            continue
        for arm in ('null', *MODELS):
            attempts = [item for case in group for item in case['fits'][arm]['records']]
            def capped(item):
                policy = protocol['solver'] if item['method'] == 'L-BFGS-B' else protocol['solver']['powell']
                return item.get('nit', -1) >= policy['maxiter'] or (item['method'] == 'Powell' and item.get('nfev', -1) >= policy['maxfev'])
            result.append(dict(regime=regime, model=arm, histories=len(group), starts=8*len(group),
                               attempts=len(attempts), failed_attempts=sum(not r['success'] for r in attempts),
                               exceptions=sum(r['status'] == 'exception' for r in attempts),
                               capped_attempts=sum(capped(r) for r in attempts),
                               rescue_attempts=sum(r['method'] == 'Powell' for r in attempts),
                               unresolved_starts=sum(not flag for case in group for flag in case['fits'][arm]['resolved_starts'])))
    return result


def audit_files(results, protocol_path, admission_path, build_path, library_path, pilot=None):
    results, protocol_path = Path(results).resolve(), Path(protocol_path).resolve()
    source, repo = protocol_path.parent, protocol_path.parent.parents[1]
    protocol, admission, build = read(protocol_path), read(admission_path), read(build_path)
    result = read(results / 'result.json')
    roster = inspect_roster(result, protocol)
    identities = {p.name: sha(p) for p in sorted(source.iterdir()) if p.is_file() and p.suffix in ('.py', '.cpp', '.json')}
    require(result['source_sha256'] == admission['source_sha256'] == identities, 'Executed source identity differs')
    require(result['admission_sha256'] == sha(admission_path), 'Admission pin')
    require(result['numerical_attempt_id'] == admission['numerical_attempt_id'] and admission['independent_review_passed'] is True, 'Numerical attempt/review admission')
    require(admission['phase'] == result['phase'], 'Phase admission')
    require(admission['protocol_sha256'] == sha(protocol_path), 'Protocol pin')
    require(admission['input_pins_sha256'] == protocol['input_pins_sha256'] == sha(source / 'input_pins.json'), 'Input-pin document identity')
    pins = read(source / 'input_pins.json')
    for relative, expected_hash in pins.items():
        require(sha(safe(repo, relative)) == expected_hash, 'Input changed: ' + relative)
    require(build['passed'] is True and build['source_sha256'] == sha(source / 'attenuation.cpp'), 'Native build/source receipt')
    require(result['library_sha256'] == admission['library_sha256'] == build['library_sha256'] == sha(library_path), 'Native binary identity')
    require(result['build_receipt_sha256'] == admission['build_receipt_sha256'] == sha(build_path), 'Build receipt pin')
    require(result['resources']['threads'] == admission['threads'] == 2 and result['resources']['workers'] == 1, 'Declared numerical concurrency')
    require(result['resources']['sampled_process_tree_rss_cap_bytes'] == admission['sampled_process_tree_rss_cap_bytes'] == 6442450944, 'Resource declaration')
    require(all(row['num_threads'] <= 2 for row in result['threadpools']), 'Reported threadpool exceeds budget')
    require(number(result['wall_seconds']) <= admission['wall_seconds'], 'Reported final wall exceeds admission')
    records = read(repo / 'reproduction/synthetic/input_manifest.json')['s04b']['cases']
    manifest = {row['case_id']: row for row in records}
    require(len(records) == len(manifest) == 80 and set(manifest) == set(protocol['roster']), 'Input manifest roster')
    reports, errors = [], []
    for entry in result['cases']:
        try:
            case = manifest[entry['case_id']]
            path = safe(results, entry['file'])
            require(sha(path) == entry['sha256'], 'Case hash')
            report = read(path)
            for key in ('case_id', 'regime', 'seed', 'n_train', 'n_test'):
                require(report[key] == case[key], 'Input/output case field: ' + key)
            expected_source = 'exact pilot reuse' if result['phase'] == 'full' and case['case_id'] in protocol['pilot'] else 'new joint fit'
            if result['phase'] == 'pilot' and result.get('training_resume', {}).get('case_id') == case['case_id']:
                expected_source = 'exact frozen training reuse; missing test scoring only'
            require(entry['source'] == expected_source, 'Fit/reuse provenance')
            inspect_case(report, protocol)
            inspect_trace(safe(results, case['case_id'] + '.attempts.jsonl'), report)
            inspect_historical(report, case, repo)
            reports.append(report)
        except (AuditError, OSError, KeyError, TypeError, ValueError, StopIteration) as exc:
            errors.append({'case_id': entry['case_id'], 'error_type': type(exc).__name__, 'error': str(exc)})
    require(not errors, 'Per-case errors: ' + json.dumps(errors))
    require(len(reports) == len(roster), 'Not all cases audited')
    resume = inspect_training_resume(result, results, source, admission, reports) if 'training_resume' in result else None
    summary = aggregate(reports, protocol)
    if result['phase'] == 'full':
        require(pilot is not None, 'Full audit requires retained pilot directory')
        inspect_pilot_reuse(result, Path(pilot).resolve(), results, protocol, admission)
        require(sha(results / 'summary.json') == result['summary_sha256'], 'Summary hash')
        actual = read(results / 'summary.json')
        require(len(actual) == 20 and len({(r['regime'], r['model'], r['gate']) for r in actual}) == 20, 'Twenty unique summary rows')
        for row in summary:
            matching = next(r for r in actual if (r['regime'], r['model'], r['gate']) == (row['regime'], row['model'], row['gate']))
            compare_tree(matching, row)
    return dict(passed=True, phase=result['phase'], full_complete=result['phase'] == 'full',
                cases=len(reports), outcomes=5*len(reports), historical_floor_checks=6*len(reports),
                historical_comparison_rows=5*len(reports), verified_input_files=len(pins),
                source_sha256=identities, execution_result_sha256=sha(results/'result.json'),
                independent_summary=summary, attempt_census=attempt_census(reports, protocol), errors=[],
                training_resume=resume,
                scope='Independent output arithmetic, selections, roster, source/input and replay custody audit. No likelihood or fit re-executed; runtime/resources are reported evidence, not independently measured here.',
                scientific_likelihood_calls=0, scientific_fit_calls=0)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('results', 'protocol', 'admission', 'build-receipt', 'library', 'output'):
        parser.add_argument('--' + name, required=True)
    parser.add_argument('--pilot')
    args = parser.parse_args(argv)
    output = Path(args.output).resolve()
    output.mkdir(parents=True, exist_ok=False)
    try:
        report = audit_files(args.results, args.protocol, args.admission, args.build_receipt, args.library, args.pilot)
        summary = report.pop('independent_summary')
        (output/'independent_summary.json').write_text(json.dumps(summary, indent=2, allow_nan=False)+'\n', encoding='utf-8')
        report['independent_summary_sha256'] = sha(output/'independent_summary.json')
    except (AuditError, OSError, KeyError, TypeError, ValueError, StopIteration) as exc:
        report = dict(passed=False, full_complete=False, error_type=type(exc).__name__, error=str(exc),
                      scientific_likelihood_calls=0, scientific_fit_calls=0)
    report['auditor_sha256'] = sha(__file__)
    (output/'result.json').write_text(json.dumps(report, indent=2, allow_nan=False)+'\n', encoding='utf-8')
    print(json.dumps(report, sort_keys=True))
    return 0 if report['passed'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
