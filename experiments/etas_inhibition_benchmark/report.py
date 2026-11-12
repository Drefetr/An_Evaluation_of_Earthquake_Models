"""Validate accepted benchmark artifacts and generate the scientific table."""
from pathlib import Path
import argparse,hashlib,json,math,re
ROOT=Path(__file__).resolve().parents[2]

def write_lf(path,text):
    path.write_bytes(re.sub(r'\r+\n','\n',text).replace('\r','\n').encode('utf-8'))

def main():
    p=argparse.ArgumentParser();p.add_argument('--source',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args();raw=a.source.read_bytes();summary=json.loads(raw)
    if summary.get('all_final_power_interior_start_coverage_passed') is not True:raise ValueError('final-power prescribed interior starts were not accepted')
    if summary.get('passed') is not True or {r['case'] for r in summary['rows']}!={f'california_fold_{i}' for i in range(3)}:raise ValueError('accepted three-fold authority incomplete')
    for relative,expected in summary['source_sha256'].items():
        if hashlib.sha256((ROOT/relative).read_bytes()).hexdigest()!=expected:raise ValueError('executed source pin changed: '+relative)
    rows=[];settings=[];upstream_pins={a.source.as_posix():hashlib.sha256(raw).hexdigest()}
    for item in summary['rows']:
        path=a.source.parent/item['case']/'result.json';d=json.loads(path.read_bytes())
        if d['training_rounds'][-1]['interior_start_coverage']['passed'] is not True:raise ValueError('fold interior-start coverage failed')
        if not d['passed'] or not d['null']['complete'] or not d['inhibited']['complete'] or not d['training_rounds'][-1]['passed']:raise ValueError('benchmark acceptance gate failed')
        gain=d['test_gain_mean'];se=d['test_integration_standard_error']
        if not math.isfinite(gain) or se>min(.02,.01*max(1,abs(gain))):raise ValueError('heldout integration gate failed')
        theta=d['null']['selected']['parameters'];inhibited=d['inhibited']['selected']['parameters']
        initializer=ROOT/'validation/live_results/etas_gpu_pilot_states_20261111'/item['case']/'result.json';initial_bytes=initializer.read_bytes()
        if hashlib.sha256(initial_bytes).hexdigest()!=d['declustering_initialization_sha256']:raise ValueError('declustering initializer pin mismatch')
        initial=json.loads(initial_bytes);exponent=float(re.search(r'ell0 10\^\(([0-9.]+)',d['inhibition'])[1])
        settings.append(dict(background_bandwidth_km=d['background_bandwidth_km'],background_floor_fraction=d['background_floor'],background_weighting_iterations=len(initial['declustering']),shadow_radius_magnitude_exponent=exponent))
        upstream_pins[path.as_posix()]=hashlib.sha256(path.read_bytes()).hexdigest();upstream_pins[initializer.relative_to(ROOT).as_posix()]=d['declustering_initialization_sha256']
        rows.append(dict(case=d['case'],n_train=d['n_train'],n_test=d['n_test'],sigma0_km=math.exp(theta[5]),alpha_s=theta[6],q=theta[7],eta=inhibited[8],gain=gain,integration_se=se,result_sha256=hashlib.sha256(path.read_bytes()).hexdigest()))
    rows.sort(key=lambda r:r['case']);a.output.mkdir(parents=True,exist_ok=True)
    comparison_path=a.source.parent/'baseline_comparison.json';comparison=json.loads(comparison_path.read_bytes()) if comparison_path.exists() else None
    if comparison is not None and (not comparison['passed'] or comparison['accepted_summary_sha256']!=hashlib.sha256(raw).hexdigest()):raise ValueError('baseline comparison authority mismatch')
    if any(s!=settings[0] for s in settings):raise ValueError('printed common settings differ across folds')
    claims=dict(schema='typed_epplus_benchmark_values_v1',passed=True,authority_sha256=hashlib.sha256(raw).hexdigest(),rows=rows,total_gain=sum(r['gain'] for r in rows),active_folds=sum(r['eta']>0 for r in rows),eta_max=max(r['eta'] for r in rows),sigma0_search_bounds_km=[2.,100.],model_settings=settings[0],prescribed_positive_starts=summary['prescribed_positive_starts'],prescribed_positive_start_count=len(summary['prescribed_positive_starts']),interior_start_coverage=[dict(case=r['case'],training_power=json.loads((a.source.parent/r['case']/'result.json').read_bytes())['training_rounds'][-1]['training_power']) for r in rows],source_execution_sha256=summary['source_sha256'],upstream_pins_verified=upstream_pins,postprocessing_source='experiments/etas_inhibition_benchmark/report.py',postprocessing_source_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest())
    if comparison is not None:claims['original_EP_comparison']=comparison
    write_lf(a.output/'typed_claims.json',json.dumps(claims,indent=2)+'\n')
    text=r'''\subsection{Magnitude-scaled ETAS and rupture-scaled attenuation}
\label{sec:epplus_benchmark}
We fit an unweighted California excitation benchmark with a
magnitude-scaled spatial kernel
\[
 s_j(z)=\frac{q-1}{\pi\sigma_j^2}
       \left(1+\frac{\|z-z_j\|^2}{\sigma_j^2}\right)^{-q},
 \qquad \sigma_j=\sigma_0 e^{\alpha_s(M_j-M_0)}.
\]
This density is normalized on the plane; its mass inside the observation
rectangle enters the compensator, retaining regional offspring leakage.
Training immigrant probabilities weight five successive background KDE updates,
following the probability-weighting principle of stochastic declustering
\citep{ZhuangOgataVereJones2002}. The resulting density, with its inherited 5~km
bandwidth and a 5\% uniform floor, is shared by the two final fitting arms.
Training event densities omit their own KDE component.

Both arms jointly estimate $(a,d,n,c,p,\sigma_0,\alpha_s,q)$.
The attenuation arm also estimates $(\eta,\ell_0,\psi,\gamma)$ in
\[
 \lambda(t,z)=\{\mu(t)b_{\rm bg}(z)+nH(t,z)\}
 \exp\!\left\{-\eta\sum_{t_j<t}
 \frac{e^{\gamma(M_j-M_0)-(t-t_j)/\psi}}
 {[1+\|z-z_j\|^2/\ell_j^2]^2}\right\},
 \qquad \ell_j=\ell_0 10^{0.5(M_j-M_0)}.
\]
The fixed shadow-radius exponent is a statistical design choice motivated by
empirical magnitude--rupture relations \citep{wells1994rupture}. It supplies a
magnitude-scaled isotropic comparison without identifying a physical Coulomb
stress field. The uninhibited arm is retained as an exact nested candidate. At each final
quadrature resolution, the training search includes the fitted null and three
prescribed strictly positive attenuation starts, in addition to nuisance warm
starts.
The attenuation deficit uses a frozen scrambled-Sobol importance proposal during
each training optimization; independent larger proposals verify the training
ordering and the held-out numerical precision. The reported integration error
measures numerical variability across independent scrambles.

\begin{table}[htbp]
\centering
\small
\begin{tabular}{lrrrrrrr}
\toprule
Fold & $N_{\rm train}$ & $N_{\rm test}$ & $\widehat\sigma_0$ (km) & $\widehat\alpha_s$ & $\widehat q$ & $\widehat\eta$ & Test contrast (nats) \\
\midrule
'''
    for r in rows:text+=f"F{r['case'][-1]} & {r['n_train']} & {r['n_test']} & {r['sigma0_km']:.3f} & {r['alpha_s']:.3f} & {r['q']:.3f} & {r['eta']:.6f} & {r['gain']:+.4f} \\\\\n"
    text+=r'''\bottomrule
\end{tabular}
\caption{Magnitude-scaled total attenuation minus the matched magnitude-scaled
ETAS baseline. The common mark term cancels in each contrast. Spatial scales,
magnitude exponents and tail shapes shown are from the uninhibited fit.}
\label{tab:epplus_benchmark}
\end{table}
'''
    if all(abs(r['sigma0_km']-2)<1e-10 for r in rows):text+=r'All three baseline fits place $\sigma_0$ at the 2~km lower search bound. '
    if comparison is not None:
        gains=[r['gain'] for r in comparison['rows']]
        text+=f"The combined magnitude-scaled, probability-weighted-background, joint-fitting and spatial-normalization procedure improves the held-out joint score over the earlier EP procedure by {gains[0]:.3f}, {gains[1]:.3f}, and {gains[2]:.3f}~nats in F0, F1, and F2, respectively ({comparison['total_gain']:.3f}~nats in total). The comparison uses identical event and parent histories, fertility weights, and common mark scores. The earlier EP procedure normalizes each parent kernel on the observation rectangle; the present procedure normalizes on the full plane and retains regional offspring leakage. "
    if claims['active_folds']==0:text+=r'Adding the rupture-scaled attenuation returns to $\widehat\eta=0$ in all three folds. The matched scored states are identical, so all three attenuation contrasts are exactly zero.'
    else:text+=f"Attenuation is active in {claims['active_folds']} of the three training fits; the total contrast is {claims['total_gain']:+.4f}~nats, with a maximum integration standard error of {max(r['integration_se'] for r in rows):.4f}~nats."
    write_lf(a.output/'11_epplus_benchmark.tex',text+'\n');print(json.dumps(claims))

if __name__=='__main__':main()
