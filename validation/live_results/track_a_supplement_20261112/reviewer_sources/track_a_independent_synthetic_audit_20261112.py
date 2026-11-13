"""Independent saved-score arithmetic; no model, fitter, or reporter imports."""
from pathlib import Path
import datetime
import hashlib
import json
import math
import statistics
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts.verify_claims import manuscript_numbers, numeric_value

DEST = ROOT / 'validation/live_results/track_a_supplement_20261112'
PINS = {}

def read(path):
    return json.loads((ROOT / path).read_text(encoding='utf-8'))

def digest(path):
    return hashlib.sha256((ROOT / path).read_bytes()).hexdigest()

def pin(path, expected=None):
    actual = digest(path)
    if expected is not None:
        assert actual == expected, (str(path), actual, expected)
    PINS[str(path).replace('\\', '/')] = actual
    return actual

def close(a, b):
    assert math.isclose(a, b, rel_tol=1e-12, abs_tol=1e-10), (a, b)

def check_score(score):
    close(score['joint'], score['P'] - score['E'] + score['M'])
    close(score['C'], -score['E'])

def stats(values):
    assert len(values) == 20 and all(math.isfinite(x) for x in values)
    mean = math.fsum(values) / 20
    variance = math.fsum((x - mean) ** 2 for x in values) / 19
    return dict(N=20, mean=mean, median=statistics.median(values),
                sample_sd=math.sqrt(variance), mcse=math.sqrt(variance / 20),
                wins=sum(x > 0 for x in values), values=values)

def compare_stats(actual, declared):
    for name, value in actual.items():
        if isinstance(value, list):
            for a, b in zip(value, declared[name]):
                close(a, b)
            assert len(value) == len(declared[name])
        else:
            close(value, declared[name])

def outcome(case, model, gate):
    values = [v for v in case['outcomes'] if (v['model'], v['gate']) == (model, gate)]
    assert len(values) == 1
    return values[0]

def wilson(wins):
    z = 1.959963984540054
    p = wins / 20
    denominator = 1 + z*z/20
    center = (p + z*z/40) / denominator
    half = z * math.sqrt(p*(1-p)/20 + z*z/1600) / denominator
    return [max(0, center-half), min(1, center+half)]

def main():
    baseline_path = 'validation/track_a_prechange_snapshot_20261112.json'
    baseline = read(baseline_path)
    assert len(baseline['sealed_json_sha256']) == 316
    pin(baseline_path)
    for path, expected in baseline['sealed_json_sha256'].items():
        pin(path, expected)
    authority_path = 'validation/live_results/track_a_supplement_20261112/s04b_joint_mcse.json'
    author_audit_path = 'validation/live_results/track_a_supplement_20261112/synthetic_table_audit.json'
    claims_path = 'validation/live_results/track_a_supplement_20261112/synthetic_numeric_claims.json'
    a = read(authority_path)
    author_audit = read(author_audit_path)
    pin(authority_path, author_audit['authority_sha256'])
    pin(claims_path, author_audit['claims_sha256'])
    pin(author_audit_path)
    pin(author_audit['reporting_module']['path'], author_audit['reporting_module']['sha256'])
    for source in a['source_files']:
        pin(source['path'], source['sha256'])
    assert len(a['source_files']) == 242
    for source in author_audit['prior_scientific_audits']:
        pin(source['path'], source['sha256'])
    for path, expected in author_audit['manuscript_sha256'].items():
        pin(path, expected)
    joint_text = (ROOT/'paper/source/chapters/13_s04b_joint_dispositions.tex').read_text()
    comparator_text = (ROOT/'paper/source/chapters/13_s04_refitted_floor.tex').read_text()
    source_cases = {}
    intercept_cases = {}
    concave_cases = {}
    for path in sorted((ROOT/'validation/live_results/s04b_joint_complete_20261111/cases').glob('*.json')):
        c = read(path)
        assert c['case_id'] not in source_cases and c['passed'] and c['training_selections_frozen']
        assert len(c['outcomes']) == 5
        source_cases[c['case_id']] = c
        intercept_cases[c['case_id']] = read('validation/live_results/methodological_20261106/refitted_floor/'+c['case_id']+'.json')
        concave_cases[c['case_id']] = read('validation/live_results/s04b_concave_20261111/'+c['case_id']+'.json')
    assert len(source_cases) == 80
    verified = []
    regime_checks = []
    numeric_rows = 0
    score_identity_count = 0
    for regime in range(4, 8):
        cases = sorted((c for c in source_cases.values() if c['regime']==regime), key=lambda c:c['case_id'])
        assert len(cases) == 20
        rr = next(v for v in a['regimes'] if v['regime']==regime)
        assert rr['case_ids'] == [c['case_id'] for c in cases]
        for key in ('n_train', 'n_test'):
            assert rr[key] == [c[key] for c in cases]
            close(rr['mean_'+key], math.fsum(c[key] for c in cases)/20)
        for c in cases:
            i = intercept_cases[c['case_id']]
            assert i['phases']['train']['n_events'] == c['n_train']
            assert i['phases']['test']['n_events'] == c['n_test']
        thin = {k:sum(c['thinning'][k] for c in cases) for k in ('accepted_immigrants','rejected_immigrants','accepted_offspring','rejected_offspring')}
        assert thin == rr['thinning']
        imm = thin['accepted_immigrants']+thin['rejected_immigrants']
        off = thin['accepted_offspring']+thin['rejected_offspring']
        assert rr['immigrant_proposals']==imm and rr['offspring_proposals']==off and rr['all_proposals']==imm+off
        close(rr['immigrant_rejection_fraction'],thin['rejected_immigrants']/imm)
        close(rr['offspring_rejection_fraction'],thin['rejected_offspring']/off)
        close(rr['all_proposal_rejection_fraction'],(thin['rejected_immigrants']+thin['rejected_offspring'])/(imm+off))
        for text in (joint_text, comparator_text):
            header = r'\textbf{S'+str(regime)+r'}: mean $N_{\mathrm{train}}='+f"{rr['mean_n_train']:.2f}"+r'$, $N_{\mathrm{test}}='+f"{rr['mean_n_test']:.2f}"+r'$'
            assert header in text
        regime_checks.append(dict(regime=regime,mean_n_train=rr['mean_n_train'],mean_n_test=rr['mean_n_test'],thinning=thin,immigrant_rejection_percent=100*thin['rejected_immigrants']/imm,offspring_rejection_percent=100*thin['rejected_offspring']/off,all_proposal_rejection_percent=100*(thin['rejected_immigrants']+thin['rejected_offspring'])/(imm+off)))
        for j in (x for x in a['joint_rows'] if x['regime']==regime):
            model,gate=j['model'],j['gate']
            values=[]
            for c in cases:
                o=outcome(c,model,gate)
                check_score(o['score']);check_score(o['new_null_score'])
                gain=o['score']['joint']-o['new_null_score']['joint']
                close(gain,o['new_gain']);close(gain,o['delta']['P']+o['delta']['C']+o['delta']['M'])
                assert o['new_win']==(gain>0)
                values.append(gain);score_identity_count+=1
            s=stats(values);compare_stats(s,j)
            for actual,declared in zip(wilson(s['wins']),j['wilson95']):close(actual,declared)
            primary=(regime,model,gate) in ((5,'LIplus_immigrant','raw'),(7,'LIplus_inclusive','raw'))
            assert j['primary']==primary
            label={'LI':'LI','LIplus_immigrant':'LI+ immigrant','LIplus_inclusive':'LI+ total'}[model]+f' ({gate})'+(r'$^{\dagger}$' if primary else '')
            line=' & '.join([f'S{regime}',label,'20/20',f"{s['mean']:.4f}",f"{s['mcse']:.4f}",f"{s['median']:.4f}",f"{s['wins']}/20",f"[{j['wilson95'][0]:.4f}, {j['wilson95'][1]:.4f}]"])
            assert line in joint_text
            numeric_rows+=1;verified.append(dict(kind='joint',regime=regime,model=model,gate=gate,**s))
        for j in (x for x in a['comparator_rows'] if x['regime']==regime):
            model,gate=j['model'],j['gate'];v={k:[] for k in ('fixed','intercept','concave')};active=0
            for c in cases:
                i=intercept_cases[c['case_id']];n=concave_cases[c['case_id']];io=outcome(i,model,gate);no=outcome(n,model,gate)
                close(io['saved_procedure_test_joint'],no['saved_procedure_test_joint'])
                active+=io['original_off_floor'];assert io['original_off_floor']==no['original_off_floor']
                saved=io['saved_procedure_test_joint']
                for key,score in [('fixed',i['phases']['test']['historical']),('intercept',i['phases']['test']['refitted']),('concave',n['phases']['test'])]:
                    check_score(score);v[key].append(saved-score['joint'])
                close(v['fixed'][-1],io['original_gain']);close(v['intercept'][-1],io['new_gain']);close(v['concave'][-1],no['concave_gain'])
            ss={k:stats(x) for k,x in v.items()}
            for k,s in ss.items():compare_stats(s,j[k]);verified.append(dict(kind='comparator',regime=regime,model=model,gate=gate,comparator=k,**s))
            assert active==j['active']
            label={'LI':'LI','LIplus_immigrant':'LI+ immigrant','LIplus_inclusive':'LI+ total'}[model]+(' gated' if gate=='BIC' else '')
            cells=[f'S{regime}',label]+[f"{ss[k]['mean']:.4f} ({ss[k]['mcse']:.4f})" for k in ('fixed','intercept','concave')]+[f"{ss['intercept']['wins']}/20",f"{ss['concave']['wins']}/20",f'{active}/20']
            assert ' & '.join(cells) in comparator_text
            numeric_rows+=1
        fc=next(x for x in a['floor_components'] if x['regime']==regime);cells=[f'S{regime}']
        for k in ('P','C','joint'):
            values=[]
            for c in cases:
                phase=intercept_cases[c['case_id']]['phases']['test'];delta=phase['refitted'][k]-phase['historical'][k];close(delta,phase['delta'][k]);values.append(delta)
            s=stats(values);compare_stats(s,fc[k]);verified.append(dict(kind='floor_component',regime=regime,component=k,**s));cells.append(f"{s['mean']:.4f} ({s['mcse']:.4f})")
        assert ' & '.join(cells) in comparator_text
        numeric_rows+=1
    assert len(verified)==92 and numeric_rows==44 and score_identity_count==400
    claims=read(claims_path)['claims'];assert len(claims)==382 and len({c['id'] for c in claims})==382
    for claim in claims:
        assert claim['bundled_source']==authority_path and claim['source_sha256']==digest(authority_path)
        value=a
        for token in claim['json_pointer'].split('/')[1:]:value=value[int(token)] if isinstance(value,list) else value[token]
        assert value==claim['value']==claim['resolved_source_value']
        display=claim['display'];precision=10**(-len(display.split('.')[1])) if '.' in display else 1
        assert abs(float(display)-value)<=precision/2+1e-12
        for location in claim['final_display_locations']:
            assert numeric_value(display) in manuscript_numbers((ROOT/'paper/source'/location).read_text())
    for path,expected in baseline['sealed_json_sha256'].items():assert digest(path)==expected
    for path,expected in PINS.items():assert digest(path)==expected
    result=dict(schema='track_a_independent_synthetic_computational_audit_v1',passed=True,
        at_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),scientific_execution=False,
        method='Independent centered-sum sample variance (denominator 19), MCSE sqrt(variance/20), and direct saved-score subtraction. No import or execution of author reporting module, scientific models, fitting, simulation or likelihood contractions.',
        reviewer_source=dict(path=Path(__file__).relative_to(ROOT).as_posix(),sha256=digest(Path(__file__))),
        source_pins=PINS,sealed_json_count_verified=316,sealed_json_unchanged=True,
        scientific_history_count=80,joint_outcome_identities_checked=400,mcse_statistics_checked=92,
        rendered_numeric_rows_checked=44,typed_claims_checked=382,regimes=regime_checks,
        statistics=verified,issues=[],
        interpretation=dict(mcse='Monte Carlo standard error of the independent-history synthetic mean, not a physical detection test or confidence interval for an observed catalogue.',s5_rejection_denominator='83.4327% concerns immigrant proposals; all-proposal rejection is 78.1988%.',s8_bic='Not recomputed here. Its BIC gate is a postprocessed sensitivity using the inherited training rule, not a prespecified S8 endpoint.'))
    output=DEST/'independent_synthetic_audit.json'
    output.write_text(json.dumps(result,indent=2,allow_nan=False)+'\n',encoding='utf-8')
    print(json.dumps({k:result[k] for k in ('passed','sealed_json_count_verified','joint_outcome_identities_checked','mcse_statistics_checked','rendered_numeric_rows_checked','typed_claims_checked')},indent=2))

if __name__=='__main__':main()
