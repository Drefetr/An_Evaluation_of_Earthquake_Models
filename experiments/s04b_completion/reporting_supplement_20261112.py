"""Saved-output reporting corrections only: no fitting or integration."""
import hashlib,json,math,re,statistics
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/'validation/live_results/reporting_supplement_20261112'
S8=ROOT/'validation/live_results/s8_moderate_complete_20261111'
CONCAVE=ROOT/'validation/live_results/s04b_concave_20261111'
INTERCEPT=ROOT/'validation/live_results/methodological_20261106/refitted_floor'
def read(path):return json.loads(Path(path).read_text())
def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def write(path,value):Path(path).write_text(json.dumps(value,indent=2,allow_nan=False)+'\n')
def wilson(wins,n):
    z=1.959963984540054;p=wins/n;den=1+z*z/n
    c=(p+z*z/(2*n))/den;h=z*math.sqrt(p*(1-p)/n+z*z/(4*n*n))/den
    return [max(0.,c-h),min(1.,c+h)]
def stats(gains,active):
    n=len(gains);wins=sum(x>0 for x in gains)
    return dict(N=n,mean=math.fsum(gains)/n,median=statistics.median(gains),mcse=statistics.stdev(gains)/math.sqrt(n),wins=wins,active=active,losses=sum(x<0 for x in gains),ties=sum(x==0 for x in gains),wilson95=wilson(wins,n))
def preserve(path,name):
    target=OUT/'source'/name
    if not target.exists():target.write_bytes(Path(path).read_bytes())
    return dict(path=target.relative_to(ROOT).as_posix(),sha256=sha(target))

def main():
    OUT.mkdir(parents=True,exist_ok=True);(OUT/'source').mkdir(exist_ok=True)
    s8tex=ROOT/'paper/source/chapters/13_s08_moderate.tex';ctex=ROOT/'paper/source/chapters/13_s04_refitted_floor.tex'
    snapshots=dict(s8=preserve(s8tex,'13_s08_before_20261112.tex'),comparator=preserve(ctex,'13_s04_refitted_floor_before_20261112.tex'),reporter=preserve(Path(__file__).with_name('report_s8.py'),'report_s8_before_20261112.py'))
    immutable=[S8/'summary.json',S8/'reported_summary.json',S8/'new_claims.json',CONCAVE/'summary.json']
    immutable_hashes={p.relative_to(ROOT).as_posix():sha(p) for p in immutable}
    science=read(ROOT/'experiments/s04b_joint_nuisance/protocol.json');policy=read(ROOT/'reproduction/synthetic/s8_moderate_total/protocol.json')
    box=science['shared_bounds']+science['inhibition_bounds'];coordinates=science['coordinates'];tolerance=1e-8
    census={name:dict(lower=0,upper=0,any=0) for name in coordinates};cases=[]
    for seed in policy['seeds']:
        path=S8/str(seed)/'result.json';r=read(path);assert r['passed'] and r['training_selections_frozen']
        null=r['training_checks']['null']['fine'];alt=r['training_checks']['LIplus_inclusive']['fine']
        improvement=null['nll']-alt['nll'];threshold=1.5*math.log(r['n_train']);gate=improvement>threshold
        raw=r['inhibited_test']['joint']-r['null_test']['joint'];assert abs(raw-r['gain'])<1e-9
        theta=r['fits']['LIplus_inclusive']['selected']['parameters'];boundaries=[]
        for coordinate,value,(lo,hi) in zip(coordinates,theta,box):
            side='lower' if abs(value-lo)<=tolerance else 'upper' if abs(value-hi)<=tolerance else None
            if side:census[coordinate][side]+=1;census[coordinate]['any']+=1;boundaries.append(dict(coordinate=coordinate,side=side))
        check=r['training_checks']['LIplus_inclusive']
        cases.append(dict(seed=seed,source=path.relative_to(ROOT).as_posix(),source_sha256=sha(path),n_train=r['n_train'],null_train_nll=null['nll'],attenuated_train_nll=alt['nll'],training_gain=improvement,bic_threshold=threshold,bic_active=bool(gate and theta[5]>0),raw_active=theta[5]>0,raw_gain=raw,bic_gain=raw if gate else 0.,boundaries=boundaries,inherited_strict_flag=check['passed'],training_score_doubling_delta=check['absolute_joint_delta'],scaled_gradient_doubling_delta=check['projected_gradient_scaled_delta']))
    raw=stats([v['raw_gain'] for v in cases],sum(v['raw_active'] for v in cases));bic=stats([v['bic_gain'] for v in cases],sum(v['bic_active'] for v in cases))
    s8=dict(N=20,bic_multiplier=1.5,additional_parameters=3,bic_rule='Fine training null NLL minus selected attenuation NLL > (3/2)*log(Ntrain); otherwise return the exact fitted null and zero held-out contrast.',boundary_tolerance=tolerance,boundary_coordinates=coordinates,boundary_bounds={name:dict(lower=lo,upper=hi) for name,(lo,hi) in zip(coordinates,box)},boundary_counts=census,any_boundary=sum(bool(v['boundaries']) for v in cases),inherited_false_flags=sum(not v['inherited_strict_flag'] for v in cases),max_scaled_gradient_difference=max(v['scaled_gradient_doubling_delta'] for v in cases),inherited_joint_score_tolerance=science['quadrature']['joint_absolute_tolerance'],inherited_gradient_tolerance=science['quadrature']['selected_training_gradient_scaled_tolerance'],declared_score_gate=.01,mcse_ddof=1,mcse_definition='Sample standard deviation with denominator N-1 divided by sqrt(N), including all exact floor-return zeros.',raw=raw,bic=bic,cases=cases,rejected_review_arithmetic=dict(proposed_bic_median=.1667,proposed_bic_mcse=1.6627,accepted=False,reason='Nine positive gains, three negative gains and eight exact zeros imply median zero; direct ddof=1 sample calculation gives the recorded MCSE.'))
    assert abs(bic['mean']-2.4945996750852713)<1e-10 and bic['median']==0 and bic['wins']==9 and bic['active']==12
    assert s8['any_boundary']==13 and {k:v['any'] for k,v in census.items() if v['any']}==dict(a=1,n=6,p=7,eta=2)
    assert s8['inherited_false_flags']==18
    manifest=read(ROOT/'reproduction/synthetic/input_manifest.json');intercepts=[];concaves=[];source_pins=[]
    for case in manifest['s04b']['cases']:
        ip=INTERCEPT/(case['case_id']+'.json');cp=CONCAVE/(case['case_id']+'.json')
        intercepts.append(read(ip));concaves.append(read(cp));source_pins.extend([dict(path=p.relative_to(ROOT).as_posix(),sha256=sha(p)) for p in (ip,cp)])
    rows=[]
    for regime in range(4,8):
        for model,gate in [('LI','raw'),('LIplus_immigrant','raw'),('LIplus_immigrant','BIC'),('LIplus_inclusive','raw'),('LIplus_inclusive','BIC')]:
            aa=[next(v for v in r['outcomes'] if (v['model'],v['gate'])==(model,gate)) for r in intercepts if r['regime']==regime]
            an=[next(v for v in r['outcomes'] if (v['model'],v['gate'])==(model,gate)) for r in concaves if r['regime']==regime];assert len(aa)==len(an)==20
            assert all(abs(a['saved_procedure_test_joint']-b['saved_procedure_test_joint'])<1e-9 for a,b in zip(aa,an))
            rows.append(dict(regime=regime,model=model,gate=gate,N=20,fixed_mean=math.fsum(v['original_gain'] for v in aa)/20,intercept_mean=math.fsum(v['new_gain'] for v in aa)/20,concave_mean=math.fsum(v['concave_gain'] for v in an)/20,wins_a=sum(v['new_gain']>0 for v in aa),wins_a_n=sum(v['concave_gain']>0 for v in an),active=sum(v['original_off_floor'] for v in aa)))
    criteria_source=dict(path='experiments/s04b_joint_nuisance/protocol.json',sha256=sha(ROOT/'experiments/s04b_joint_nuisance/protocol.json'),joint_score_pointer='/quadrature/joint_absolute_tolerance',joint_score_tolerance=science['quadrature']['joint_absolute_tolerance'],gradient_pointer='/quadrature/selected_training_gradient_scaled_tolerance',gradient_tolerance=science['quadrature']['selected_training_gradient_scaled_tolerance'])
    authority=dict(schema='synthetic_reporting_supplement_20261112',scientific_estimation=False,s8=s8,inherited_criteria_source=criteria_source,comparator=dict(rows=rows,win_definition='Strictly positive held-out saved-procedure contrast against the separately training-fitted a-only or (a,n) null. Both columns use all twenty histories; original inhibition gates and states are unchanged.',source_pins=source_pins),preserved_authorities=immutable_hashes,prior_source_snapshots=snapshots)
    target=OUT/'supplement.json';write(target,authority)
    # Replace only the report table and add the two requested scientific disclosures.
    text=s8tex.read_text();a=text.index('\\begin{table}');b=text.index('\\end{table}',a)+len('\\end{table}')
    table=['\\begin{table}[htbp]\\centering\\small',r'\caption{Complete S8 held-out contrasts against the jointly fitted uninhibited comparator, in nats per history. The training-only BIC gate retains attenuation when the fine training gain exceeds $1.5\log N_{\rm train}$ and returns the exact fitted null otherwise. MCSE uses the sample standard deviation of all twenty gains, including floor-return zeros, divided by $\sqrt{20}$. Wilson intervals concern strict-positive win probability.}\label{tab:s8-moderate}',r'\begin{tabular}{@{}lrrrrrr@{}}\toprule',r'Selection & Mean & Median & MCSE & Wins & Active & Wilson interval\\\midrule']
    for label,r in [('Raw',raw),('BIC',bic)]:table.append(f"{label} & {r['mean']:+.4f} & {r['median']:+.4f} & {r['mcse']:.4f} & {r['wins']}/20 & {r['active']}/20 & [{r['wilson95'][0]:.4f}, {r['wilson95'][1]:.4f}]"+r'\\')
    table.append(r'\bottomrule\end{tabular}\end{table}');text=text[:a]+'\n'.join(table)+text[b:]
    text=text.replace('The mean gain is smaller than its sample Monte Carlo standard error','The raw mean gain is smaller than its sample Monte Carlo standard error')
    disclosure=('Raw selected fits reach at least one box boundary in 13/20 histories: $p=2.5$ in 7, $n=0.98$ in 6, $\\eta=4$ in 2 and $a=0$ in 1, with overlapping counts. '
                'S8 applies its declared 0.01-nat training-score gate; 18/20 records fail the stricter inherited 0.0001-nat score and 0.0001 scaled-gradient criterion, with maximum scaled coarse/fine gradient difference 0.03324.\n\n')
    text=re.sub(r'Raw selected fits reach at least one box boundary.*?\n\n(?=All twenty training fits)', '', text, flags=re.S)
    text=text.replace('All twenty training fits',disclosure+'All twenty training fits')
    s8tex.write_text(text)
    text=ctex.read_text();a=text.index('\\begin{table}[H]');b=text.index('\\end{table}',a)+len('\\end{table}')
    table=[r'\begin{table}[H]\centering\small',r'\setlength{\tabcolsep}{3pt}',r'\caption{S04B comparator sensitivity. Mean held-out gains in nats against the fixed floor, the training-fitted intercept, and the jointly fitted $(a,n)$ comparator. The two win columns count strictly positive contrasts against their respective fitted comparators, each out of twenty histories. Active counts describe the saved attenuation procedure; original gates are unchanged. A gate returning the original fixed floor can beat a refitted floor without selecting inhibition.}\label{tab:s04b-refitted-floor}',r'\begin{tabular}{@{}llrrrrrr@{}}',r'\toprule Regime & Saved procedure & \shortstack{Fixed\\floor} & \shortstack{Fitted\\intercept} & \shortstack{Fitted\\$(a,n)$} & \shortstack{Wins\\$a$} & \shortstack{Wins\\$(a,n)$} & Active\\\midrule']
    for i,r in enumerate(rows):
        label=dict(LI='LI',LIplus_immigrant='LI+ immigrant',LIplus_inclusive='LI+ total')[r['model']]+(' gated' if r['gate']=='BIC' else '')
        table.append(f"{'S'+str(r['regime']) if i%5==0 else ''} & {label} & {r['fixed_mean']:.4f} & {r['intercept_mean']:.4f} & {r['concave_mean']:.4f} & {r['wins_a']}/20 & {r['wins_a_n']}/20 & {r['active']}/20"+r'\\')
        if i%5==4 and i<19:table.append(r'\addlinespace')
    table.append(r'\bottomrule\end{tabular}\end{table}');ctex.write_text(text[:a]+'\n'.join(table)+text[b:])
    claims=[];source=target.relative_to(ROOT).as_posix();source_sha=sha(target)
    def claim(pointer,value,display,location):
        claims.append(dict(id='synthetic-reporting-20261112-'+str(len(claims)+1).zfill(3),bundled_source=source,source_path=source,source_sha256=source_sha,json_pointer=pointer,resolved_source_value=value,value=value,display=str(display),transformation='decimal rounding to displayed precision',json_value_kind='numeric_scalar',ledger_role='manuscript_binding',final_display_locations=[location],component='Saved-output BIC, boundary, numerical-flag and comparator-win reporting',qualification='No scientific fit or integration repeated; strict-positive wins use all twenty histories and floor returns are exact zero.',status='source_bound',binding_kind='exact_json_pointer',reconciliation_status='verified_at_declared_granularity'))
    location='chapters/13_s08_moderate.tex'
    for which in ('raw','bic'):
        for key in ('mean','median','mcse'):claim(f'/s8/{which}/{key}',s8[which][key],f"{s8[which][key]:.4f}",location)
        for key in ('N','wins','active'):claim(f'/s8/{which}/{key}',s8[which][key],s8[which][key],location)
        for i,v in enumerate(s8[which]['wilson95']):claim(f'/s8/{which}/wilson95/{i}',v,f'{v:.4f}',location)
    for key,display in [('bic_multiplier','1.5'),('any_boundary','13'),('inherited_false_flags','18'),('max_scaled_gradient_difference','0.03324'),('declared_score_gate','0.01'),('inherited_joint_score_tolerance','0.0001'),('inherited_gradient_tolerance','0.0001')]:claim('/s8/'+key,s8[key],display,location)
    for coordinate in ('p','n','eta','a'):claim('/s8/boundary_counts/'+coordinate+'/any',census[coordinate]['any'],census[coordinate]['any'],location)
    for coordinate in ('p','n','eta','a'):claim('/s8/boundary_bounds/'+coordinate+'/upper',s8['boundary_bounds'][coordinate]['upper'],s8['boundary_bounds'][coordinate]['upper'],location)
    for i,r in enumerate(rows):
        for key in ('wins_a','wins_a_n'):claim(f'/comparator/rows/{i}/{key}',r[key],r[key],'chapters/13_s04_refitted_floor.tex')
    write(OUT/'new_claims.json',dict(claims=claims))
    assert all(sha(ROOT/path)==pin for path,pin in immutable_hashes.items()),'An existing scientific authority changed'
    audit=dict(schema='saved_output_reporting_audit_20261112',passed=True,scientific_estimation=False,authority_sha256=sha(target),reporter_sha256=sha(__file__),preserved_authorities=immutable_hashes,S8_cases=20,S8_BIC=bic,boundary_counts=census,boundary_tolerance=tolerance,inherited_false_flags=s8['inherited_false_flags'],inherited_criteria_source=criteria_source,max_gradient_discrepancy=s8['max_scaled_gradient_difference'],all_comparator_rows=20,strict_positive_win_columns_independently_counted=True,rejected_review_arithmetic=s8['rejected_review_arithmetic'],manuscript_sha256={p.relative_to(ROOT).as_posix():sha(p) for p in (s8tex,ctex)},typed_claims=len(claims))
    write(OUT/'audit.json',audit);print(json.dumps(dict(BIC=bic,boundary_any=s8['any_boundary'],false_flags=s8['inherited_false_flags'],claims=len(claims)),indent=2))
    write(OUT/'FROZEN.json',dict(passed=True,authority_sha256=sha(target),claims_sha256=sha(OUT/'new_claims.json'),audit_sha256=sha(OUT/'audit.json'),manuscript_sha256=audit['manuscript_sha256'],preserved_authorities=immutable_hashes))
if __name__=='__main__':main()
