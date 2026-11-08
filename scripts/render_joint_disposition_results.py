"""Validate and stage a separately accepted disposition report; never install it.

All eighty dispositions must be independently accepted. Task 2 and Task 3 retain
their existing acceptance requirements. Unknown outcomes and incomplete-regime
statistics stay null/text, and the original full-success publication gate remains
false. This module imports only saved-output parsing/arithmetic/formatting code.
"""
import argparse
from decimal import Decimal, ROUND_HALF_EVEN
import json
from pathlib import Path

try:
    from scripts import build_joint_disposition_report as builder
    from scripts.render_joint_nuisance_results import require, read, sha, safe, numeric, integer, pointer, LABELS
except ModuleNotFoundError:
    import build_joint_disposition_report as builder
    from render_joint_nuisance_results import require, read, sha, safe, numeric, integer, pointer, LABELS

SCHEMA = 'joint_nuisance_disposition_acceptance_v1'
REVIEW_KIND = 'live_independent_disposition_and_saved_output_review'
TEX_LOCATION = 'chapters/13_s04b_joint_dispositions.tex'


def flags(value):
    require(value.get('reporting_accepted') is True and value.get('disposition_accounting_complete') is True and
            value.get('scientific_completion') is False and value.get('original_publication_gate_satisfied') is False and
            value.get('live_independent_review') is True and value.get('review_kind') == REVIEW_KIND and
            isinstance(value.get('reviewer'), str) and value['reviewer'].strip(),
            'Genuine live independent disposition acceptance is required')
    require('passed' not in value, 'Disposition acceptance must not assert unqualified passed')


def validate(repository, paths):
    """Return (report, pins) after reconstructing custody and saved arithmetic."""
    repository = Path(repository).resolve()
    require(set(paths) == {'report', 'audit', 'completion_review'}, 'Report, audit and completion review required')
    documents, pins = {}, {}
    for key, relative in paths.items():
        require(relative.startswith('validation/') and relative.endswith('.json') and
                not relative.startswith('validation/authorities/'), 'Public live reporting JSON inputs required')
        path = safe(repository, relative)
        documents[key], pins[relative] = read(path), sha(path)
    report, audit, acceptance = (documents[key] for key in ('report', 'audit', 'completion_review'))
    require(report.get('schema') == builder.REPORT_SCHEMA, 'Separate disposition report required')
    require(acceptance.get('schema') == SCHEMA, 'Separate disposition acceptance required')
    flags(audit)
    flags(acceptance)
    for key in ('report', 'audit'):
        require(acceptance['artifact_sha256'].get(paths[key]) == pins[paths[key]], 'Acceptance does not bind '+key)
    require(audit['report_sha256'] == pins[paths['report']], 'Independent review does not bind report')
    rebuilt, source_pins = builder.build(repository, report['inputs'])
    # Exact saved operands and null placement are mandatory. Only independently
    # summarized arithmetic below permits the established 1e-9 tolerance.
    require(json.dumps(report, sort_keys=True, allow_nan=False) == json.dumps(rebuilt, sort_keys=True, allow_nan=False),
            'Report differs from accepted saved operands, missing-data rules or summaries')
    require(audit['source_pins'] == source_pins, 'Independent review source identities differ')
    for value in (audit, acceptance):
        for count in value['counts'].values():
            integer(count)
        require(value['campaign_identity'] == report['campaign_identity'] and value['counts'] == report['counts'],
                'Accepted campaign identity or derived counts differ')
    summary = audit['independent_summary']
    require(isinstance(summary, list) and len(summary) == 20, 'Independent twenty-row summary required')
    expected = {(row['regime'], row['model'], row['gate']): row for row in report['regime_summary']}
    actual = {(row['regime'], row['model'], row['gate']): row for row in summary}
    require(len(actual) == 20 and set(actual) == set(expected), 'Independent summary procedure roster differs')
    core = builder.arithmetic()
    for key, row in expected.items():
        require(set(actual[key]) == set(row), 'Independent summary fields differ')
        core.compare_tree(actual[key], row, 'Independent disposition summary')
        if row['full_regime'] is not None:
            require(set(actual[key]['full_regime']) == set(row['full_regime']), 'Independent full-regime fields differ')
    tasks = acceptance['tasks']
    require(set(tasks) == {'task1', 'task2', 'task3'}, 'All three publication tasks are required')
    for name, task in tasks.items():
        reference = task['acceptance']
        relative = reference['path']
        require(relative.startswith('validation/') and not relative.startswith('validation/authorities/'),
                'Public live task acceptance required')
        path = safe(repository, relative)
        require(sha(path) == reference['sha256'], 'Task acceptance hash differs: '+name)
        value = read(path)
        pins[relative] = reference['sha256']
        if name == 'task1':
            require('passed' not in task and task.get('disposition_reporting_accepted') is True and task.get('scientific_completion') is False and
                    reference == dict(path=paths['audit'], sha256=pins[paths['audit']]),
                    'Task 1 requires the bound disposition review, never scientific success')
            flags(value)
        else:
            require(task.get('passed') is True and value.get('passed') is True, 'Incomplete '+name)
    pins.update(source_pins)
    return report, pins


def render(report, report_path, report_sha, tex_location=TEX_LOCATION):
    claims = {}
    def cell(where, places=None):
        value = numeric(pointer(report, where))
        if places is None:
            display = str(integer(value))
        else:
            rounded = Decimal(str(value)).quantize(Decimal(1).scaleb(-places), rounding=ROUND_HALF_EVEN)
            if rounded == 0:
                rounded = abs(rounded)
            display = format(rounded, f'.{places}f')
        if where not in claims:
            claims[where] = dict(id='s04b-joint-disposition-'+report_sha[:12]+'-'+where.strip('/').replace('/', '-'),
                bundled_source=report_path, source_path=report_path, source_sha256=report_sha,
                json_pointer=where, resolved_source_value=value, display=display,
                transformation='decimal rounding to displayed precision', json_value_kind='numeric_scalar',
                ledger_role='manuscript_binding', final_display_locations=[tex_location],
                component='S04B audited terminal dispositions and complete-regime comparisons',
                qualification='Disposition accounting is complete; scientific completion remains false. Full-regime statistics use all original 20 histories only; Wilson intervals concern strict wins.',
                status='source_bound', binding_kind='exact_json_pointer', value=value,
                reconciliation_status='staged_pending_manuscript_installation')
        return display
    def label(row):
        return LABELS[row['model']]+' ('+row['gate']+')'+(r'$^{\dagger}$' if row['primary'] else '')
    lines = [r'% Separate disposition report, staged only. No manuscript or ledger installation.',
        'All '+cell('/counts/planned_histories')+' planned histories have accepted terminal dispositions: '+
        cell('/counts/complete_histories')+' complete and '+cell('/counts/scientific_unknown_histories')+
        ' scientific unknown. Of '+cell('/counts/planned_outcomes')+' planned outcomes, '+
        cell('/counts/computed_outcomes')+' are computed and '+cell('/counts/unavailable_outcomes')+
        ' are unavailable. Scientific completion is false; the original full-success publication gate remains unsatisfied.',
        '', r'\begin{table}[htbp]', r'\centering', r'\setlength{\tabcolsep}{3pt}',
        r'\caption{Saved joint-score procedure comparisons, in nats. Full-regime statistics require all original twenty histories. Incomplete regimes remain unavailable; no complete-case mean, median or Wilson interval is substituted. Wins are strictly positive gains; positive near-zero gains remain wins. Wilson intervals are pointwise win-rate intervals, not mean-gain uncertainty. Marked rows are the prespecified primary contrasts. Historical fixed-floor and intercept-only comparisons remain unchanged.}',
        r'\label{tab:s04b-joint-disposition-scores}', r'\begin{tabular}{@{}llrrrrr@{}}', r'\toprule',
        r'Regime & Procedure & Computed/planned & Mean & Median & Wins & Wilson interval \\', r'\midrule']
    for i, row in enumerate(report['regime_summary']):
        prefix = f'/regime_summary/{i}'
        values = ['S'+cell(prefix+'/regime'), label(row), cell(prefix+'/computed_histories')+'/'+cell(prefix+'/planned_histories')]
        if row['statistics_available']:
            full = prefix+'/full_regime'
            values += [cell(full+'/mean_gain', 4), cell(full+'/median_gain', 4),
                       cell(full+'/wins')+'/'+cell(full+'/N'),
                       '['+cell(full+'/wilson95/0', 4)+', '+cell(full+'/wilson95/1', 4)+']']
        else:
            values += ['Unavailable']*4
        lines.append(' & '.join(values)+r' \\')
    lines += [r'\bottomrule', r'\end{tabular}', r'\end{table}', '', r'\begin{table}[htbp]', r'\centering',
        r'\caption{Complete-regime search and numerical census. Full-regime diagnostic cells are unavailable for incomplete regimes. Failed attempts count unsuccessful logical attempts for the shared null and named alternative; raw/BIC rows reuse searches and must not be added. Resource interruptions and administrative restarts remain in execution records. Near-zero is numerical, not statistical significance. A null-search gap prevents attributing a procedure contrast to inhibition.}',
        r'\label{tab:s04b-joint-disposition-diagnostics}', r'\begin{tabular}{@{}llrrrrrr@{}}', r'\toprule',
        r'Regime & Procedure & Unknown & $a$ bounds & $\eta$ bounds & Failed attempts & Null gaps & Gate differences \\', r'\midrule']
    for i, row in enumerate(report['regime_summary']):
        prefix = f'/regime_summary/{i}'
        values = ['S'+cell(prefix+'/regime'), label(row), cell(prefix+'/unavailable_histories')]
        full = prefix+'/full_regime'
        values += ([cell(full+'/coordinate_boundaries/a/lower')+'/'+cell(full+'/coordinate_boundaries/a/upper'),
                    cell(full+'/eta_lower')+'/'+cell(full+'/eta_upper')]+
                   [cell(full+'/'+key) for key in ('optimizer_failed_attempts', 'null_search_gap_cases',
                    'coarse_fine_gate_disagreements')] if row['statistics_available'] else ['Unavailable']*5)
        lines.append(' & '.join(values)+r' \\')
    lines += [r'\bottomrule', r'\end{tabular}', r'\end{table}', '', r'\begin{table}[htbp]', r'\centering',
        r'\caption{Complete-regime floor and near-zero census. Positive near-zero gains remain strict wins. An alternative with zero inhibition and a better nuisance solution is a procedure and optimizer contrast, not evidence of inhibition. Incomplete regimes have no full-regime diagnostic census.}',
        r'\label{tab:s04b-joint-disposition-floor-census}', r'\begin{tabular}{@{}llrrrrrr@{}}', r'\toprule',
        r'Regime & Procedure & Off-floor & Floor returns & Near zero & Positive near zero & Robust positive & Robust negative \\', r'\midrule']
    for i, row in enumerate(report['regime_summary']):
        prefix = f'/regime_summary/{i}'
        values = ['S'+cell(prefix+'/regime'), label(row)]
        values += ([cell(prefix+'/full_regime/'+key) for key in ('off_floor', 'floor_returns', 'near_zero',
            'positive_near_zero', 'robust_positive', 'robust_negative')] if row['statistics_available'] else ['Unavailable']*6)
        lines.append(' & '.join(values)+r' \\')
    lines += [r'\bottomrule', r'\end{tabular}', r'\end{table}', '',
              'Unknown histories retain their original optimizer cap returns and have no held-out outcome.']
    for i, row in enumerate(report['unknown_census']):
        name = row['case_id'].replace('_', r'\_')
        arm = row['failed_model'].replace('_', r'\_')
        lines.append(name+': '+arm+', unresolved zero-based start '+cell(f'/unknown_census/{i}/unresolved_start')+
            ', terminal evaluations '+cell(f'/unknown_census/{i}/terminal_solver_return/nfev')+
            ', terminal iterations '+cell(f'/unknown_census/{i}/terminal_solver_return/nit')+'.')
    lines += ['', 'Complete-regime boundaries: '+(', '.join('S'+cell(f'/complete_regimes/{i}')
              for i in range(len(report['complete_regimes']))) or 'none')+
              '. Every other planned regime has unavailable full-regime statistics.', '']
    return '\n'.join(lines), list(claims.values())


def stage(repository, paths, output, tex_location=TEX_LOCATION):
    repository, output = Path(repository).resolve(), Path(output).resolve()
    require(not output.is_relative_to(repository) and not output.exists(), 'Fresh external staging directory required')
    require(tex_location.startswith('chapters/') and tex_location.endswith('.tex'), 'New chapter TeX location required')
    require(not safe(repository/'paper/source', tex_location).exists(), 'Existing manuscript source must not be replaced')
    report, pins = validate(repository, paths)
    tex, claims = render(report, paths['report'], pins[paths['report']], tex_location)
    ledger_path = repository/'validation/MASTER_CLAIM_LEDGER.json'
    if ledger_path.exists():
        existing = {value['id'] for value in read(ledger_path)['claims']}
        require(not existing.intersection(value['id'] for value in claims), 'Binding IDs already exist')
    output.mkdir(parents=True)
    tex_path = output/tex_location
    tex_path.parent.mkdir(parents=True)
    tex_path.write_text(tex, encoding='utf-8', newline='\n')
    additions = dict(schema='staged_manuscript_bindings_v1', operation='append_only_after_source_installation_and_review',
                     source_sha256=pins[paths['report']], target_tex_location=tex_location, claims=claims)
    (output/'claims.additions.json').write_text(json.dumps(additions, indent=2, allow_nan=False)+'\n', encoding='utf-8')
    receipt = dict(schema='joint_disposition_formatting_v1', reporting_accepted=True, disposition_accounting_complete=True,
        scientific_completion=False, original_publication_gate_satisfied=False, staging_only=True,
        manuscript_installed=False, ledger_modified=False, counts=report['counts'], source_pins=pins,
        formatter_sha256=sha(__file__), builder_sha256=sha(builder.__file__), staged_tex_sha256=sha(tex_path),
        claims_sha256=sha(output/'claims.additions.json'), claim_bindings=len(claims), scientific_calls=0)
    (output/'render_receipt.json').write_text(json.dumps(receipt, indent=2)+'\n', encoding='utf-8')
    return receipt


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repository', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    for name in ('report', 'audit', 'completion-review'):
        parser.add_argument('--'+name, required=True)
    parser.add_argument('--tex-location', default=TEX_LOCATION)
    args = parser.parse_args()
    print(json.dumps(stage(args.repository, {key:getattr(args, key) for key in
        ('report', 'audit', 'completion_review')}, args.output, args.tex_location), indent=2))
