"""Independent scalar/source/context review; no model or reporter execution."""
from pathlib import Path
import ast
import datetime
from decimal import Decimal
import hashlib
import json
import math
import re

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'validation/live_results/track_a_supplement_20261112'
PINS={}

def sha(path):return hashlib.sha256((ROOT/path).read_bytes()).hexdigest()
def read(path):return json.loads((ROOT/path).read_text(encoding='utf-8'))
def pin(path,expected=None):
    value=sha(path)
    if expected is not None:assert value==expected,(str(path),value,expected)
    PINS[str(path).replace('\\','/')]=value
    return value
def resolve(path,pointer):
    value=read(path)
    for key in pointer.split('/')[1:]:
        key=key.replace('~1','/').replace('~0','~')
        value=value[int(key)] if isinstance(value,list) else value[key]
    return value
def close(a,b):assert math.isclose(a,b,rel_tol=1e-13,abs_tol=1e-12),(a,b)
def paragraph(text,anchor):
    assert text.count(anchor)==1,anchor
    start=text.index(anchor);end=text.find('\n\n',start)
    return text[start:end if end>=0 else len(text)]

def main():
    basepath='validation/track_a_prechange_snapshot_20261112.json'
    baseline=read(basepath);assert len(baseline['sealed_json_sha256'])==316
    pin(basepath)
    for p,h in baseline['sealed_json_sha256'].items():pin(p,h)
    summary_path='validation/live_results/track_a_supplement_20261112/framing_summary.json'
    claims_path='validation/live_results/track_a_supplement_20261112/framing_numeric_claims.json'
    pin(summary_path,'237641f3e77614dfb4f6bfb58c46fd92bc12a4a6a9c07471af4712f3505ea7a0')
    pin(claims_path,'1d720d846a58577646169d0371f27fcb9e079ef6b078f127ed9b8665bbcb099c')
    s=read(summary_path);claims=read(claims_path)['claims'];facts=s['facts'];bindings=s['display_bindings']
    assert len(facts)==133 and len(bindings)==len(claims)==185
    pin(s['postprocessing_source']['path'],s['postprocessing_source']['sha256'])
    for path,h in s['source_sha256'].items():pin(path,h)
    manuscript={}
    for path,h in s['manuscript_sha256'].items():
        full='paper/source/'+path;pin(full,h);manuscript[path]=(ROOT/full).read_text()
    # Construct expected scientific identities independently from names/roles.
    prefix='validation/live_results/'
    J=prefix+'track_a_supplement_20261112/s04b_joint_mcse.json'
    U=prefix+'score_uncertainty_remote_v2_20261111/summary.json'
    S8=prefix+'reporting_supplement_20261112/supplement.json'
    S8GEN=prefix+'s8_moderate_complete_20261111/summary.json'
    EP=prefix+'etas_inhibition_benchmark_interior_20261112/'
    EPU=prefix+'etas_baseline_uncertainty_20261111/summary.json'
    expected={}
    def add(key,path,pointer):expected[key]=(path,pointer)
    for regime,index in ((5,6),(7,18)):
        row=resolve(J,'/joint_rows/'+str(index))
        assert (row['regime'],row['model'],row['gate'])==(regime,'LIplus_immigrant' if regime==5 else 'LIplus_inclusive','raw')
        for metric in ('mean','median','mcse','wins','N'):add(f's{regime}_{metric}',J,f'/joint_rows/{index}/{metric}')
        add(f's{regime}_mean_n_test',J,f'/regimes/{regime-4}/mean_n_test')
        for quantity in ('immigrant_rejection_fraction','offspring_rejection_fraction','all_proposal_rejection_fraction'):
            add(f's{regime}_{quantity}_percent',J,f'/regimes/{regime-4}/{quantity}')
    add('joint_histories',prefix+'s04b_joint_complete_20261111/summary.json','/completed_histories')
    add('joint_outcomes',prefix+'s04b_joint_complete_20261111/summary.json','/completed_outcomes')
    add('s2_unthinned_histories',prefix+'s2_control_20261107/summary.json','/zero_rejection_histories')
    add('s4_rejected_immigrants',J,'/regimes/0/thinning/rejected_immigrants')
    for regime,index,comparator in ((5,8,'fixed'),(5,8,'intercept'),(7,18,'intercept'),(7,18,'concave')):
        row=resolve(J,f'/comparator_rows/{index}')
        assert (row['regime'],row['model'],row['gate'])==(regime,'LIplus_inclusive','raw')
        add(f's{regime}_total_{comparator}_mean',J,f'/comparator_rows/{index}/{comparator}/mean')
    add('s7_zero_branching_fits',prefix+'s04b_concave_20261111/summary.json','/summary/18/n_zero')
    for phase in ('raw','bic'):
        for metric in ('mean','median','mcse','wins','active','N'):add(f's8_{phase}_{metric}',S8,f'/s8/{phase}/{metric}')
    add('s8_boundary_any',S8,'/s8/any_boundary')
    add('s8_mean_n_test',S8GEN,'/generation/mean_test_events')
    add('s8_rejected_percent',S8GEN,'/generation/rejected_fraction')
    for days in (90,180,365):
        root='' if days==90 else f'/sensitivity/{days}'
        for i in range(3):
            row=resolve(U,f'{root}/rows/{i}')
            assert row['contrast']=='NZ_shared_minus_ML' and row['case']==('fold_50','fold_65','fold_80')[i]
            for metric in ('total','paired_sign_permutation_p','replicates'):add(f'nz_f{i+1}_{days}_{metric}',U,f'{root}/rows/{i}/summary/{metric}')
            for side in (0,1):add(f'nz_f{i+1}_{days}_ci{side}',U,f'{root}/rows/{i}/summary/ci95_total/{side}')
        add(f'block_days_{days}',U,f'{root}/rows/0/block_days')
    add('nz_total_loss',U,'/pooled/NZ_shared_minus_ML/total')
    add('nz_fold1_loss',U,'/rows/0/summary/total')
    add('nz_fold1_share_percent',U,'/NZ_first_fold_fraction')
    for i in range(3):
        assert resolve(U,f'/rows/{i+6}/contrast')=='CA_LIplus_total_minus_floor'
        add(f'ca_li_f{i}_total',U,f'/rows/{i+6}/summary/total')
    for i in (0,1):add(f'ca_li_pooled_90_ci{i}',U,f'/pooled/CA_LIplus_total_minus_floor/ci95_total/{i}')
    stability=prefix+'methodological_20261106/stability.json'
    for key,field in [('mode_count','modes'),('slow_modes','slow_mode_count'),('horizon','horizon_days'),('minimum_log_rate','log_rate_min'),('decay_percent','decay_threshold_percent'),('minimum_skeleton_days','minimum_coupling_time_days')]:add(key,stability,'/kernel/'+field)
    add('pinsker_eta_cutoff',prefix+'mathematics_remediation_20261111.json','/finite_horizon_visibility/eta_at_which_clipped_bound_equals_one')
    for key,pointer in [('nz_inhibited_d','/fit_contrast/inhibited_d'),('nz_null_d','/fit_contrast/null_d'),('nz_trend_depletion_rho','/event_score_weighted_trend_depletion_correlation')]:add(key,prefix+'trend_depletion_20261111.json',pointer)
    add('epplus_total_gain',EP+'baseline_comparison.json','/total_gain')
    for i in range(3):
        add(f'epplus_f{i}_gain',EP+'baseline_comparison.json',f'/rows/{i}/gain')
        add(f'epplus_f{i}_sigma_lower_km',EP+f'california_fold_{i}/result.json','/bounds/5/0')
    add('sobol_training_exponent',EP+'california_fold_0/result.json','/training_rounds/0/training_power')
    for days in (90,180,365):
        for i in (0,1):add(f'epplus_pooled_{days}_ci{i}',EPU,f'/pooled_by_block_days/{days}/ci95_total/{i}')
        add(f'epplus_pooled_{days}_p',EPU,f'/pooled_by_block_days/{days}/paired_sign_permutation_p')
    add('nz_minimum_magnitude','validation/authorities/903cb8f6fc5407b9_protocol_observed_v1.json','/data/minimum_magnitude')
    add('ca_minimum_magnitude','reproduction/nzca/cohort_contract_california.json','/population/minimum_magnitude')
    add('ca_primary_targets','validation/authorities/438d5e8eb6d872c2_case_matrix_v1.json','/denominators/observed/targets')
    add('el_mayor_episode_year','validation/acceptances/S06_ACCEPTANCE.json','/eligibility/3/year')
    special={'s4_unthinned_histories','conditional_continuous_p_min','conditional_continuous_p_max','jma_minimum_magnitude'}
    assert set(expected)|special==set(facts)
    fact_checks=[]
    for name,fact in facts.items():
        inputs=fact['inputs'];values=[]
        for item in inputs:
            pin(item['path'],item['sha256'])
            if 'json_pointer' in item:value=resolve(item['path'],item['json_pointer'])
            else:
                assert name=='jma_minimum_magnitude'
                body=(ROOT/item['path']).read_text();nodes=[n for n in ast.walk(ast.parse(body)) if isinstance(n,ast.If) and isinstance(n.test,ast.Compare) and isinstance(n.test.left,ast.Name) and n.test.left.id=='tenths' and isinstance(n.test.ops[0],ast.Lt)]
                assert len(nodes)==1 and isinstance(nodes[0].test.comparators[0],ast.Constant)
                value=nodes[0].test.comparators[0].value
                assert item['source_locator']==f'AST If at line {nodes[0].lineno}' and item['source_excerpt']==body.splitlines()[nodes[0].lineno-1]
            assert value==item['resolved_source_value'];values.append(value)
        if name in expected:
            assert len(inputs)==1 and (inputs[0]['path'],inputs[0]['json_pointer'])==expected[name],name
        if name=='s4_unthinned_histories':
            ids=resolve(J,'/regimes/0/case_ids');assert len(ids)==20 and len(inputs)==20
            assert {(i['path'],i['json_pointer']) for i in inputs}=={(prefix+'s04b_joint_complete_20261111/cases/'+cid+'.json','/thinning/rejected_immigrants') for cid in ids}
            assert all(resolve(prefix+'s04b_joint_complete_20261111/cases/'+cid+'.json','/thinning/rejected_offspring')==0 for cid in ids)
        if name.startswith('conditional_continuous_p_'):
            assert {(i['path'],i['json_pointer']) for i in inputs}=={('validation/acceptances/S05_public.json',f'/rows/{i}/{method}/pooled_upper_inclusive_p') for i in range(6) for method in ('fisher','quadratic')}
        transformation=fact['transformation']
        if transformation=='identity':computed=values[0]
        elif transformation=='exp(source)':computed=math.exp(values[0])
        elif transformation.startswith('source * '):computed=values[0]*float(transformation.split('*')[1])
        elif transformation=='count_zero of listed scientific inputs':computed=sum(x==0 for x in values)
        elif transformation=='min of listed scientific inputs':computed=min(values)
        elif transformation=='max of listed scientific inputs':computed=max(values)
        elif transformation=='target exclusion threshold in magnitude tenths / 10':computed=values[0]/10
        else:raise AssertionError(transformation)
        close(computed,fact['value']);fact_checks.append(dict(fact=name,value=computed,transformation=transformation,meaning=fact['meaning']))
    # Reconstruct exact assertions that require more than numeric display checks.
    zero_inclusion={}
    for fold in (1,2,3):
        zero_inclusion[str(fold)]={str(days):facts[f'nz_f{fold}_{days}_ci0']['value']<=0<=facts[f'nz_f{fold}_{days}_ci1']['value'] for days in (90,180,365)}
    assert zero_inclusion=={'1':{'90':False,'180':False,'365':False},'2':{'90':True,'180':True,'365':True},'3':{'90':True,'180':False,'365':False}}
    close(facts['nz_fold1_share_percent']['value'],100*facts['nz_fold1_loss']['value']/facts['nz_total_loss']['value'])
    for i in range(3):
        case=read(EP+f'california_fold_{i}/result.json');assert case['parameter_names'][5]=='log_sigma0'
        assert case['null']['selected']['parameters'][5]==case['bounds'][5][0]
        assert case['inhibited']['selected']['parameters'][8]==0 and case['inhibited']['selected']['parameters']==case['null']['selected']['parameters']
        assert case['test_gain_mean']==0 and case['training_rounds'][-1]['training_power']==14
    close(sum(facts[f'epplus_f{i}_gain']['value'] for i in range(3)),facts['epplus_total_gain']['value'])
    k=resolve(stability,'/kernel');rates=[math.exp(j*k['log_rate_max']/k['half_count']) for j in range(-k['half_count'],k['half_count']+1)]
    slow=sum(-math.expm1(-r*k['horizon_days'])<k['decay_threshold'] for r in rates)
    assert len(rates)==195 and slow==61;close(math.log(4)/min(rates),facts['minimum_skeleton_days']['value'])
    KT=resolve(prefix+'mathematics_remediation_20261111.json','/finite_horizon_visibility/K_T');close(math.sqrt(2/KT),facts['pinsker_eta_cutoff']['value'])
    # Each claim is checked at its declared, unique paragraph anchor, never by
    # searching all manuscript files for a coincidentally matching numeral.
    contexts=[]
    assert len({c['id'] for c in claims})==185
    for i,(binding,claim) in enumerate(zip(bindings,claims),1):
        name=binding['fact'];value=facts[name]['value'];display=binding['display'];d=Decimal(display.replace(',',''));tolerance=Decimal(10)**d.as_tuple().exponent/2
        assert abs(Decimal(str(value))-d)<=tolerance+abs(d)*Decimal('2e-14')
        assert claim['id']==f'track-a-framing-20261112-{i:03}' and claim['bundled_source']==summary_path and claim['source_sha256']==sha(summary_path)
        assert claim['json_pointer']==f'/facts/{name}/value' and claim['value']==claim['resolved_source_value']==value and claim['display']==display
        assert claim['component']==facts[name]['meaning'] and claim['final_display_locations']==[binding['location']]
        assert binding['paragraph_anchor'] in claim['qualification']
        scope=paragraph(manuscript[binding['location']],binding['paragraph_anchor'])
        assert binding['manuscript_literal'] in scope,(name,binding['location'],binding['paragraph_anchor'])
        contexts.append(dict(claim_id=claim['id'],fact=name,value=value,display=display,location=binding['location'],paragraph_anchor=binding['paragraph_anchor'],paragraph_sha256=hashlib.sha256(scope.encode()).hexdigest()))
    abstract=manuscript['abstract.tex'];nz=manuscript['chapters/08_score_uncertainty.tex'];ep=manuscript['chapters/11_epplus_benchmark.tex'];c13=manuscript['chapters/13_continuous_local_inhibition.tex'];c14=manuscript['chapters/14_discussion_conclusion.tex']
    assert 'A later sensitivity applying the inherited training-BIC rule' in abstract
    assert 'This gated endpoint was not declared in the executed S8 reporting protocol' in c14
    assert 'event-score geometry' in abstract and 'physical absence' in abstract
    assert 'nominal coverage is not proved' in nz and 'conditional sensitivity' in nz
    assert 'same observation domain' in ep and 'does not invalidate a proper-score comparison' in ep
    assert 'all four procedural changes' in ep and '2~km lower search bound' in ep
    assert 'not statistical detection power' in ep and 'exactly zero by nesting' in ep
    assert 'heavy-tailed generating laws' in c13 and 'not a Gaussian mean-inference guarantee' in c14
    assert '83.4' in c14 and '78.2' in c14 and facts['s5_all_proposal_rejection_fraction_percent']['value']<80
    for p,h in baseline['sealed_json_sha256'].items():assert sha(p)==h
    for p,h in PINS.items():assert sha(p)==h
    result=dict(schema='track_a_independent_statistical_framing_review_v1',passed=True,
        at_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),reviewer_task='/root/mathematics',
        scope='Internal independent computational source, scalar arithmetic and paragraph-context review; no external peer review and no new scientific fitting, simulation or likelihood integration.',
        reviewer_code=dict(path=Path(__file__).relative_to(ROOT).as_posix(),sha256=sha(Path(__file__))),
        source_pins=PINS,sealed_json_count=316,sealed_json_unchanged=True,
        named_scientific_facts_checked=len(facts),paragraph_scoped_display_bindings_checked=len(bindings),
        fact_checks=fact_checks,display_contexts=contexts,nz_zero_inclusion_by_fold_and_block_days=zero_inclusion,
        semantic_findings=[
            'NZ fold 1 intervals exclude zero at all three lengths; fold 2 includes zero throughout; fold 3 includes zero at 90 days and excludes it at 180/365 days. Prose preserves this scale sensitivity.',
            'Trend d=1.790 versus -0.252 and rho=0.9341 refer to first-fold event-score geometry. The correlation is the v-squared-weighted x-versus-G correlation after intercept partialling, not a claim about the full likelihood Hessian or all causal influences.',
            'Nested eta=0 training selections make the corresponding held-out forecasts identical algebraically. The prose explicitly separates this boundary result from calibrated detection power and physical absence.',
            'EP+ minus EP is a proper log-score comparison on the same recorded time-space domain and intensity units, while conflating magnitude scaling, training-declustered background weighting, joint fitting, and plane-versus-region spatial normalization/leakage. All three sigma0 estimates reach 2 km.',
            'Independent sign reversals do not establish exchangeability under seismic clustering; both sign-flip values and percentile block intervals are labelled conditional descriptive sensitivity summaries without proved long-memory or fitted-parameter coverage.',
            'Synthetic sample MCSEs describe independent-history finite-bank variation; the prose does not infer independent earthquakes, a Gaussian guarantee under the heavy-tailed law, or uniform detection power.',
            'S5 all-proposal rejection is 78.1988%; 83.4327% concerns immigrants only. S7 all-proposal rejection is 82.4900% and offspring rejection is 98.2143%. Denominators are distinguished.',
            'The abstract now explicitly calls the S8 BIC row a later sensitivity under the inherited training rule; the conclusion states it was not an endpoint in the executed S8 reporting protocol.',
            'The headline states that no statistically detectable improvement is established and is read as lack of established evidence, with the adjacent explicit noncalibration/power cautions; it does not assert a calibrated absence result.'
        ],issues=[])
    (OUT/'independent_framing_review.json').write_text(json.dumps(result,indent=2,allow_nan=False)+'\n',encoding='utf-8')
    print(json.dumps({k:result[k] for k in ('passed','sealed_json_count','named_scientific_facts_checked','paragraph_scoped_display_bindings_checked')},indent=2))

if __name__=='__main__':main()
