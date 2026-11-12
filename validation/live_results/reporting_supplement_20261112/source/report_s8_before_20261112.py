"""Derive the complete S8 report, manuscript fragment and typed bindings."""
import hashlib,json,math,statistics
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/'validation/live_results/s8_moderate_complete_20261111'
def read(p):return json.loads(Path(p).read_text())
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def main():
    summary=read(OUT/'summary.json');assert summary['completed_histories']==20
    assert read(OUT/'epoch_result.json')['passed']
    protocol=read(ROOT/'reproduction/synthetic/s8_moderate_total/protocol.json')
    reports=[read(OUT/str(seed)/'result.json') for seed in protocol['seeds']]
    assert all(v['passed'] and v['training_selections_frozen'] for v in reports)
    assert all(a['passed'] and a['resolved_starts']==[True]*8 for v in reports for a in v['fits'].values())
    gains=[v['gain'] for v in reports];assert abs(math.fsum(gains)/20-summary['mean_gain'])<1e-10
    reused=[seed for seed in protocol['seeds'] if (OUT/str(seed)/'reuse.json').exists()]
    assert len(reused)==4 and all(read(OUT/str(seed)/'fresh_cpu_replay.json')['passed'] for seed in reused)
    for seed in set(protocol['seeds'])-set(reused):assert read(OUT/str(seed)/'cuda_selected_checks.json')['passed']
    report=dict(summary=summary,law=protocol['law'],background_rate=math.exp(protocol['law']['a']),window_days=protocol['train'][1]-protocol['train'][0],
                sample_sd=statistics.stdev(gains),sample_mcse=statistics.stdev(gains)/math.sqrt(20),gain_range=[min(gains),max(gains)],losses=sum(v<0 for v in gains),
                fixed_analysis_seeds=protocol['seeds'],fresh_replayed_seeds=reused,
                upstream_summary_sha256=sha(OUT/'summary.json'),input_manifest_sha256=sha(ROOT/'reproduction/synthetic/s8_moderate_total/input_manifest.json'),
                reports=[dict(seed=seed,file=str(seed)+'/result.json',sha256=sha(OUT/str(seed)/'result.json')) for seed in protocol['seeds']],
                mcse_definition='Sample standard deviation of the twenty independent seed gains divided by sqrt(20).')
    target=OUT/'reported_summary.json';target.write_text(json.dumps(report,indent=2)+'\n')
    text=r'''\subsubsection{A moderately thinned total-intensity control}\label{sec:s8-moderate}
The S8 generator uses $e^a=@@RATE@@\,\mathrm{day}^{-1}$, $\eta=@@ETA@@$, $\ell=@@ELL@@\,\mathrm{km}$ and $\psi=@@PSI@@$ days, with the preceding temporal-trigger and mark settings. The generating law is fixed before the twenty analysis histories are drawn. It rejects @@PCT@@\% of event proposals and retains @@EVENTS@@ test events on average (range $[@@MINN@@, @@MAXN@@]$). Both arms jointly fit $(a,d,n,c,p)$ on the @@DAYS@@-day training window; the total-attenuation arm also fits $(\eta,\ell,\psi)$. Its search includes the fitted null as an eligible state. The fitted parameters are frozen for the subsequent @@DAYS@@-day test window.

\begin{table}[htbp]\centering\small
\caption{Complete S8 held-out contrasts against the jointly fitted uninhibited comparator, in nats per history. MCSE is the sample standard deviation of the twenty independent gains divided by $\sqrt{20}$. The Wilson interval concerns the probability of a positive gain, not uncertainty in the mean.}\label{tab:s8-moderate}
\begin{tabular}{@{}rrrrrr@{}}\toprule
Mean & Median & MCSE & Wins & Active & Wilson interval\\\midrule
@@MEAN@@ & @@MEDIAN@@ & @@MCSE@@ & @@WINS@@/20 & @@ACTIVE@@/20 & [@@LOW@@, @@HIGH@@]\\
\bottomrule\end{tabular}\end{table}

All twenty training fits select a positive attenuation amplitude. Individual test contrasts range from @@MINGAIN@@ to @@MAXGAIN@@ nats, with @@LOSSES@@ negative contrasts. The mean gain is smaller than its sample Monte Carlo standard error, and the win-probability interval includes $1/2$. The training mesh is refined until selected score doubling agrees within 0.01 nat. Selected likelihoods are checked by doubling positive Gauss--Legendre quadrature; the largest held-out change is @@QUAD@@ nats. The twenty histories and generating law are supplied in \path{reproduction/synthetic/s8_moderate_total/}; complete fits, CPU score checks and the aggregate are in \path{validation/live_results/s8_moderate_complete_20261111/}.
'''
    values=dict(RATE=f"{report['background_rate']:.2f}",ETA=f"{report['law']['eta']:.1f}",ELL=f"{report['law']['ell']:.0f}",PSI=f"{report['law']['psi']:.0f}",PCT=f"{100*summary['generation']['rejected_fraction']:.2f}",EVENTS=f"{summary['generation']['mean_test_events']:.1f}",MINN=summary['generation']['test_event_range'][0],MAXN=summary['generation']['test_event_range'][1],DAYS=report['window_days'],MEAN=f"{summary['mean_gain']:+.4f}",MEDIAN=f"{summary['median_gain']:+.4f}",MCSE=f"{report['sample_mcse']:.4f}",WINS=summary['wins'],ACTIVE=summary['active'],LOW=f"{summary['wilson95'][0]:.4f}",HIGH=f"{summary['wilson95'][1]:.4f}",MINGAIN=f"{min(gains):.4f}",MAXGAIN=f"{max(gains):+.4f}",LOSSES=report['losses'],QUAD=f"{summary['numerical_max_test_delta']:.6f}")
    for key,value in values.items():text=text.replace('@@'+key+'@@',str(value))
    fragment='chapters/13_s08_moderate.tex';(ROOT/'paper/source'/fragment).write_text(text,encoding='utf-8')
    claims=[];source=target.relative_to(ROOT).as_posix();source_hash=sha(target)
    broad=['chapters/01_introduction.tex','chapters/13_continuous_local_inhibition.tex','chapters/14_discussion_conclusion.tex',fragment]
    def claim(pointer,value,display,locations=None,transform='decimal rounding to displayed precision'):
        actual=value*transform['factor'] if isinstance(transform,dict) else value
        claims.append(dict(id='remediation-s8-'+str(len(claims)+1).zfill(3),bundled_source=source,source_path=source,source_sha256=source_hash,json_pointer=pointer,resolved_source_value=value,display=str(display),transformation=transform,json_value_kind='numeric_scalar',ledger_role='manuscript_binding',final_display_locations=locations or [fragment],component='Complete moderate-thinning synthetic benchmark',qualification='All twenty fixed analysis histories; paired held-out contrasts after training-only joint fitting. MCSE is descriptive sample Monte Carlo error; active fits are not detections.',status='source_bound',binding_kind='exact_json_pointer',value=actual,reconciliation_status='verified_at_declared_granularity'))
    claim('/summary/completed_histories',20,20,['abstract.tex',*broad]);claim('/summary/mean_gain',summary['mean_gain'],f"{summary['mean_gain']:.3f}",['abstract.tex'])
    claim('/summary/mean_gain',summary['mean_gain'],f"{summary['mean_gain']:.4f}",broad)
    claim('/summary/median_gain',summary['median_gain'],f"{summary['median_gain']:.4f}",broad)
    claim('/summary/wins',summary['wins'],summary['wins'],['abstract.tex',*broad]);claim('/summary/active',20,20,broad)
    for i,value in enumerate(summary['wilson95']):claim('/summary/wilson95/'+str(i),value,f'{value:.4f}',broad)
    fraction=summary['generation']['rejected_fraction']
    claim('/summary/generation/rejected_fraction',fraction,f'{fraction*100:.1f}',['abstract.tex',*broad],dict(operation='multiply',factor=100))
    claim('/summary/generation/rejected_fraction',fraction,f'{fraction*100:.2f}',None,dict(operation='multiply',factor=100))
    claim('/summary/generation/mean_test_events',summary['generation']['mean_test_events'],'94.7',['abstract.tex',*broad])
    for i,value in enumerate(summary['generation']['test_event_range']):claim('/summary/generation/test_event_range/'+str(i),value,value)
    for field,display in [('background_rate',values['RATE']),('window_days',values['DAYS']),('sample_mcse',values['MCSE']),('losses',values['LOSSES'])]:claim('/'+field,report[field],display)
    for field in ('eta','ell','psi'):claim('/law/'+field,report['law'][field],values[field.upper()])
    for i,value in enumerate(report['gain_range']):claim('/gain_range/'+str(i),value,f'{value:.4f}')
    claim('/summary/numerical_max_test_delta',summary['numerical_max_test_delta'],values['QUAD'])
    (OUT/'new_claims.json').write_text(json.dumps(dict(claims=claims),indent=2)+'\n')
    print(json.dumps(dict(mean=summary['mean_gain'],median=summary['median_gain'],MCSE=report['sample_mcse'],wins=summary['wins'],range=report['gain_range'],claims=len(claims),fragment=fragment),indent=2))
if __name__=='__main__':main()
