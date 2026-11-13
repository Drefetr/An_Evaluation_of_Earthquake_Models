"""Export only accepted aggregate results; no fit or live-run access."""
import hashlib
import fnmatch
import importlib.util
import json
from decimal import Decimal, ROUND_HALF_EVEN
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
AUTH = ROOT/'validation/authorities'
JOINT_DIRECTORY = 'validation/live_results/joint_nuisance_20261107'
FORMATTER_PATH = ROOT/'scripts/render_joint_nuisance_results.py'
DISPOSITION_DIRECTORY = 'validation/live_results/joint_nuisance_dispositions_20261107'
DISPOSITION_FORMATTER_PATH = ROOT/'scripts/render_joint_disposition_results.py'


def joint_display(value):
    """Match the manuscript formatter's four-decimal presentation, including zero."""
    rounded=Decimal(str(value)).quantize(Decimal('0.0001'),rounding=ROUND_HALF_EVEN)
    return format(abs(rounded) if rounded==0 else rounded,'.4f')


def load_joint_study(repository):
    """Absent evidence adds nothing; present evidence must pass the full publication gate.

    This verifies saved outputs and their issued reviews, not scientific correctness
    or reviewer identity. It never reads an in-progress execution directory.
    """
    base=repository/JOINT_DIRECTORY
    if not base.exists():return None,[]
    paths={key:JOINT_DIRECTORY+'/'+filename+'.json' for key,filename in
           [('summary','summary'),('result','result'),('index','index'),
            ('audit','independent_review'),('completion_review','completion_review')]}
    if not base.is_dir() or not all((repository/p).is_file()for p in paths.values()):
        raise ValueError('Joint study publication evidence is incomplete')
    spec=importlib.util.spec_from_file_location('joint_publication_validator',FORMATTER_PATH)
    validator=importlib.util.module_from_spec(spec);spec.loader.exec_module(validator)
    try:summary,pins=validator.validate(repository,paths)
    except (KeyError,TypeError) as exc:
        raise ValueError('Malformed joint study publication evidence') from exc
    study={
        'name':'Synthetic controls - S04B joint nuisance comparison',
        'kind':'joint_simulation',
        'comparisons':{'LI_raw':'LI','LIplus_immigrant_raw':'LI+ immigrant',
            'LIplus_immigrant_BIC':'LI+ immigrant gated','LIplus_inclusive_raw':'LI+ total',
            'LIplus_inclusive_BIC':'LI+ total gated'},
        'comparator':'Jointly fitted uninhibited floor',
        'metrics':['joint'],'summary':summary,
        'display_summary':[dict(regime=r['regime'],model=r['model'],gate=r['gate'],
            mean_gain=joint_display(r['mean_gain']),median_gain=joint_display(r['median_gain']),
            wilson95=[joint_display(x)for x in r['wilson95']])for r in summary],
        'regime_names':{'4':'Immigrant: narrow/short','5':'Immigrant: broad/long',
                        '6':'Total: narrow/short','7':'Total: broad/long'},
        'note':'Temporal and background coordinates are fitted jointly with inhibition on training data. '
            'The common spatial and mark laws remain fixed. Each regime uses 20 independent seeded histories; '
            'procedures share those histories and regimes are never pooled. Mean and median gains are total '
            'held-out nats per history. Pointwise Wilson intervals describe strict-positive win indicators, '
            'not mean-gain uncertainty or simultaneous inference. Positive near-zero gains still count as wins. '
            'Active means positive selected inhibition; it does not establish parameter recovery. A null-search '
            'gap can produce a gain at zero inhibition and prevents attributing that procedure contrast to '
            'inhibition. The failed-attempt census counts unsuccessful logical optimizer attempts, including shared '
            'searches reused by raw and gated rows; their counts must not be added across procedures. Resource '
            'interruptions and administrative restarts are retained separately in the execution records. These '
            'controlled comparisons do not establish a physical mechanism or prospective forecasting performance.',
        'source':'Chapter 13, separate jointly fitted S04B comparison. Exact summary and complete execution '
                 'are bound to the final live saved-output review; source hashes are in the aggregate download.',
        'evidence_paths':paths,
        'validation_source':'scripts/render_joint_nuisance_results.py',
        'validation_source_sha256':hashlib.sha256(FORMATTER_PATH.read_bytes()).hexdigest(),
    }
    return study,[{'file':Path(p).name,'path':p,'sha256':h}for p,h in sorted(pins.items())]


def write_findings(out,payload):
    """Render an already assembled export; this helper does not accept scientific inputs."""
    (out/'findings-data.json').write_text(json.dumps(payload,indent=2)+'\n',encoding='utf-8')
    template=(ROOT/'website/findings.html').read_text(encoding='utf-8')
    (out/'findings.html').write_text(template.replace('/* DATA */',
        'const DATA='+json.dumps(payload).replace('<','\\u003c')+';'),encoding='utf-8')


def load_joint_disposition_study(repository):
    """A separate accepted disposition report; never a fallback from the success gate."""
    base=repository/DISPOSITION_DIRECTORY
    if not base.exists():return None,[]
    paths={key:DISPOSITION_DIRECTORY+'/'+filename+'.json' for key,filename in
           [('report','report'),('audit','independent_review'),('completion_review','completion_review')]}
    if not base.is_dir() or not all((repository/p).is_file() for p in paths.values()):
        raise ValueError('Joint disposition publication evidence is incomplete')
    spec=importlib.util.spec_from_file_location('joint_disposition_publication_validator',DISPOSITION_FORMATTER_PATH)
    validator=importlib.util.module_from_spec(spec);spec.loader.exec_module(validator)
    try:report,pins=validator.validate(repository,paths)
    except (KeyError,TypeError) as exc:
        raise ValueError('Malformed joint disposition publication evidence') from exc
    summary=report['regime_summary']
    display=[]
    for row in summary:
        full=row['full_regime']
        values=dict(mean_gain=None,median_gain=None,wilson95=None)
        if row['statistics_available']:
            values=dict(mean_gain=joint_display(full['mean_gain']),median_gain=joint_display(full['median_gain']),
                        wilson95=[joint_display(x) for x in full['wilson95']])
        display.append(dict(regime=row['regime'],model=row['model'],gate=row['gate'],**values))
    study=dict(name='Synthetic controls - S04B joint comparison dispositions',kind='joint_disposition_simulation',
        comparisons={'LI_raw':'LI','LIplus_immigrant_raw':'LI+ immigrant','LIplus_immigrant_BIC':'LI+ immigrant gated',
                     'LIplus_inclusive_raw':'LI+ total','LIplus_inclusive_BIC':'LI+ total gated'},
        comparator='Jointly fitted uninhibited floor',metrics=['joint'],summary=summary,display_summary=display,
        regime_names={'4':'Immigrant: narrow/short','5':'Immigrant: broad/long','6':'Total: narrow/short','7':'Total: broad/long'},
        counts=report['counts'],outcomes=report['outcomes'],case_dispositions=report['case_dispositions'],
        unknown_census=report['unknown_census'],failure_census=report.get('failure_census',[]),complete_regimes=report['complete_regimes'],
        campaign_identity=report['campaign_identity'],historical_comparators=report['historical_comparators'],
        coverage=report['coverage'],scientific_completion=False,original_publication_gate_satisfied=False,
        note='Temporal and background coordinates are fitted jointly on training data; spatial and mark laws stay fixed. '
             'Each regime retains its original twenty seeded histories. An optimizer unknown or technical wall failure leaves its procedure '
             'outcomes unavailable, including when an earlier training arm completed. Unavailable outcomes are neither '
             'zero gains nor losses. Full-regime means, medians, strict wins and diagnostics require all original histories; '
             'success-only summaries are not substituted. Pointwise Wilson intervals describe strict-positive win '
             'indicators for complete regimes, not mean-gain uncertainty or simultaneous inference. Positive near-zero '
             'gains remain wins. Active selection does not establish parameter recovery; null-search gaps prevent '
             'attributing a procedure contrast solely to inhibition. Logical unsuccessful attempts may be shared by '
             'raw and gated rows and must not be added across procedures. Attempted and unrun arms, original cap '
             'returns and operational interruptions remain in the evidence. Regimes are never pooled. These controlled '
             'comparisons do not establish a physical mechanism or prospective forecasting performance.',
        source='Separate joint-comparison disposition report. All planned outcome slots, unavailable reasons, '
               'unchanged historical comparators and source hashes are retained in the aggregate download. '
               'Reporting acceptance is distinct from scientific completion.',
        evidence_paths=paths,validation_source='scripts/render_joint_disposition_results.py',
        validation_source_sha256=hashlib.sha256(DISPOSITION_FORMATTER_PATH.read_bytes()).hexdigest())
    return study,[{'file':Path(p).name,'path':p,'sha256':h} for p,h in sorted(pins.items())]


def append_joint_publications(repository,studies,sources):
    # Both fixed directories refer to this one frozen S04B campaign. A malformed
    # full-success record must raise before the separate disposition path is read.
    joint,joint_sources=load_joint_study(repository)
    disposition,disposition_sources=load_joint_disposition_study(repository)
    if joint is not None and disposition is not None:
        raise ValueError('The same joint campaign cannot publish success and disposition reports together')
    # The completed follow-up is a distinct, independently audited source epoch.
    # Historical gates above still run unchanged before the current view can
    # supersede their display. A malformed current authority is never ignored.
    current,current_sources=load_completed_joint_study(repository)
    if current is not None:
        studies.append(current);sources.extend(joint_sources+disposition_sources+current_sources)
        return
    if joint is not None:studies.append(joint);sources.extend(joint_sources)
    if disposition is not None:studies.append(disposition);sources.extend(disposition_sources)


def load_completed_joint_study(repository):
    try:from website.current_joint_results import validate
    except ModuleNotFoundError:from current_joint_results import validate
    report,pins=validate(repository)
    if report is None:return None,[]
    summary=report['summary']
    study=dict(name='Synthetic controls - complete S04B joint nuisance comparison',kind='joint_simulation',
        comparisons={'LI_raw':'LI','LIplus_immigrant_raw':'LI+ immigrant','LIplus_immigrant_BIC':'LI+ immigrant gated',
            'LIplus_inclusive_raw':'LI+ total','LIplus_inclusive_BIC':'LI+ total gated'},
        comparator='Jointly fitted uninhibited floor',metrics=['joint'],summary=summary,
        display_summary=[dict(regime=r['regime'],model=r['model'],gate=r['gate'],
            mean_gain=joint_display(r['mean_gain']),median_gain=joint_display(r['median_gain']),
            wilson95=[joint_display(x) for x in r['wilson95']]) for r in summary],
        regime_names={'4':'Immigrant: narrow/short','5':'Immigrant: broad/long','6':'Total: narrow/short','7':'Total: broad/long'},
        completed_histories=report['completed_histories'],completed_outcomes=report['completed_outcomes'],scientific_completion=True,
        note='All 80 original histories and 400 procedure outcomes are complete. Both arms fit background and temporal-triggering parameters on training data; spatial and mark laws remain fixed. Each regime has 20 independent seeded histories, shared across procedures. Regimes are never pooled or earthquake-normalized. Wilson intervals summarize strict-positive win indicators, not uncertainty in mean gain. Sample Monte Carlo errors and training/test event counts are supplied in the aggregate download and manuscript. Active fits are not detections; a zero-strength return gives an exactly nested tie, not a power test. Floor returns and boundary/search diagnostics remain visible. Matched broad/long immigrant and total attenuation both lose on average against their jointly fitted comparator.',
        source='Chapter 13, completed S04B joint comparison. Every case source and displayed aggregate field is reconstructed by an independent computational publication check. Additive presentation records bind the new MCSE table to the unchanged scientific result; historical records remain preserved.',
        evidence_paths={'summary':'validation/live_results/s04b_joint_complete_20261111/summary.json',
            'audit':'validation/live_results/s04b_joint_complete_independent_audit_20261111.json',
            'publication_review':'validation/publication_refresh_track_b_20261112/joint_publication_review.json'},
        validation_source='website/current_joint_results.py',
        validation_source_sha256=hashlib.sha256((ROOT/'website/current_joint_results.py').read_bytes()).hexdigest())
    if 'presentation' in report:
        study['mean_gain_mcse']=[{k:r[k] for k in ('regime','model','gate','N','mean','mcse')} for r in report['presentation']['mcse_rows']]
        study['regime_event_counts']=[{k:r[k] for k in ('regime','N','mean_n_train','mean_n_test')} for r in report['presentation']['regimes']]
    return study,[{'file':Path(p).name,'path':p,'sha256':h} for p,h in sorted(pins.items())]

def build(out):
    studies=[];sources=[]
    def read(pattern):
        manifest=json.loads((ROOT/'validation/authority_manifest.json').read_text(encoding='utf-8'))
        matches=[r for r in manifest if fnmatch.fnmatch(Path(r.get('historical_bundled_path',r['bundled_path'])).name,pattern)]
        if len(matches)!=1:raise ValueError('ambiguous or missing authority: '+pattern)
        row=matches[0];p=ROOT/row['bundled_path'];actual=hashlib.sha256(p.read_bytes()).hexdigest()
        if actual!=row['sha256']:raise ValueError('public authority hash mismatch: '+row['bundled_path'])
        sources.append({'file':p.name,'path':row['bundled_path'],'sha256':actual})
        return json.loads(p.read_text(encoding='utf-8'))
    assert read('*_s03_saved_checks.json')['passed']
    for region,label in [('ca','California'),('nz','New Zealand')]:
        windows=[]
        for i in range(3):
            d=read(f'*_m02_s03_{region}_{i}_aggregate.json');assert d['status']=='complete'
            rows={r['arm']:r for r in d['results']};n=rows[1]['n_test']
            assert all(r['n_test']==n for r in rows.values())
            values={}
            for key,a,b in [('unweighted',2,1),('loo',3,2),('ep',4,1)]:
                values[key]={m:rows[a]['scores'][m]-rows[b]['scores'][m] for m in ['joint','timing','location']}
            windows.append({'label':f'Window {i+1}','n':n,'values':values})
        assert sum(w['n'] for w in windows)==({'ca':315,'nz':612}[region])
        studies.append({'name':f'{label}  -  spatial model choices','comparisons':{'ep':'EP minus OC: change the spatial triggering model','unweighted':'Unweighted minus OC: remove background weighting','loo':'LOO minus unweighted: change background estimation'},'metrics':['joint','timing','location'],'windows':windows,'note':'Training-selected temporal and magnitude parameters are held fixed; background level, trend and reproduction are refitted where required. These comparisons evaluate fitted procedures, not isolated physical causes. The same regional targets are reused across comparisons. New Zealand data were inspected repeatedly during development.','source':'Chapter 11, completed four-arm spatial decomposition (S03).'})
    d=read('*_s06_manuscript_values.json')
    studies.append({'name':'California  -  five historical episodes','comparisons':{'EP':'EP minus OC','MC':'MC minus OC','FC':'FC minus OC'},'metrics':['joint'],'windows':[{'label':str(r['year']),'n':r['n'],'values':{m:{'joint':r['joint'][m]-r['joint']['OC']} for m in ['EP','MC','FC']}} for r in d['CA']],'note':'Models use strictly earlier training prefixes, but episode selection is retrospective. These five blocks share an archive and overlapping training histories; they are not five independent experiments. The 1992 episodes failed the declared training-count or zone-adequacy rules. These 421 targets are a different study population from the three-window comparison.','source':'Chapter 11, five-episode causal-prefix backtest (S06).'})
    for trend,label in [('dfree','fitted background trend'),('d0','stationary background')]:
        studies.append({'name':f'Japan  -  {label}','comparisons':{'fc':'OC minus FC: timing-law comparison','ep':'OC minus EP: competitive comparison'},'metrics':['timing'],'windows':[{'label':f'Window {r["fold"]+1}','n':r['n'],'values':{'fc':{'timing':r['OC_minus_FC_timing']},'ep':{'timing':r['OC_minus_EP_timing']}}} for r in d['JMA'] if r['trend']==trend],'note':'The same 1,277 targets are evaluated under both trend settings. Their totals must not be added. Removing the fitted background trend improves pooled OC - FC timing, but does not reverse its negative sign. This retrospective comparison does not establish the physical reason for the mismatch.','source':'Chapter 11, JMA trend ablation (S06).'})
    acceptance=read('*_S04_observed_reporting_acceptance.json')
    d=read('*_S04_observed_public_results.json')
    assert acceptance['status']=='accepted_for_reporting' and acceptance['terminal'] is True
    assert acceptance['results']['sha256']==sources[-1]['sha256'] and d['public_aggregate'] is True
    procedures=[('LI','raw','LI: original unpenalized'),('LIplus_immigrant','raw','LI+ background-only: raw'),('LIplus_immigrant','BIC','LI+ background-only: BIC'),('LIplus_inclusive','raw','LI+ total-intensity: raw'),('LIplus_inclusive','BIC','LI+ total-intensity: BIC')]
    folds=d['folds'];assert len(folds)==3 and sum(f['n_test'] for f in folds)==315
    rows={(r['case_id'],r['model'],r['gate']):r for r in d['rows']}
    assert len(rows)==len(d['rows'])==15
    windows=[]
    for i,f in enumerate(folds):
        values={}
        for model,gate,label in procedures:
            r=rows[(f['case_id'],model,gate)]
            assert r['accepted_numerics'] is True and r['status']=='resolved' and r['n_test']==f['n_test']
            assert abs(r['gain_joint']-(r['floor_nll']-r['selected_nll']))<1e-9
            values[model+'_'+gate]={'joint':r['gain_joint']}
        windows.append({'label':f'Window {i+1}','n':f['n_test'],'values':values})
    studies.append({'name':'California - observed inhibition (S04)','comparisons':{m+'_'+g:l+' minus shared no-inhibition floor' for m,g,l in procedures},'metrics':['joint'],'windows':windows,'note':'Five fitted procedures on the same 315 targets, not five independent studies. Raw selection and BIC use training only. Gains are held-out joint log scores against a shared no-inhibition floor; no timing/location decomposition is available here. Negative outcomes and boundary selections remain included. Retrospective reused catalogues; zero gain does not establish physical absence of inhibition. Original fit audits used saved acceptance and sampled CPU/GPU controls. The later CPU replay recomputes the declared held-out selected and floor scores at the original quadrature orders; it does not repeat training selection, every optimizer candidate, or certify a global optimum.','source':'Chapter 13, reported observed California inhibition comparisons (S04).'})
    audit=read('*_S04B_COMPLETE_AUDIT.json')
    accepted=read('*_S04B_MATCHED_ACCEPTANCE.json')
    assert accepted['final_scientific_accepted'] is True and accepted['accepted'] is True
    assert audit['passed'] and (audit['cases'],audit['score_rows'],audit['summary_rows'],audit['cpu_contexts'])==(80,400,20,48)
    studies.append({'name':'Synthetic controls - S04B fixed-floor and refitted-rate comparisons','kind':'simulation','comparisons':{'LI_raw':'LI','LIplus_immigrant_raw':'LI+ immigrant','LIplus_immigrant_BIC':'LI+ immigrant gated','LIplus_inclusive_raw':'LI+ total','LIplus_inclusive_BIC':'LI+ total gated'},'metrics':['joint'],'summary':audit['independent_summary'],'regime_names':{'4':'Immigrant: narrow/short','5':'Immigrant: broad/long','6':'Total: narrow/short','7':'Total: broad/long'},'note':'Each row contains 20 independent seeded histories within one generating regime. Five procedures share those same histories; 400 scores are not 400 independent replicates. Mean gains are total held-out nats per history, never earthquake-normalized. MC SE is descriptive with no automatic finite-variance or Gaussian guarantee. Wilson 95% intervals describe bounded win indicators, not mean-gain uncertainty, calibrated test power or a physical mechanism. Ties are not wins. Active counts indicate positive selected strength. Training-only BIC can select the exact floor. The shared nuisance backbone is fixed. Regimes are never pooled.','source':'Chapter 13, S04B matched-generator extension.'})
    sensitivity=read('refitted_floor_summary.json')
    generation=read('synthetic_diagnostics.json')
    assert sensitivity['passed'] and sensitivity['cases']==80 and sensitivity['historical_floor_checks']==480
    studies[-1]['refitted_floor']=sensitivity['procedure_summary']
    studies[-1]['note']+=' The narrow/short immigrant generator rejected no event in 19 of 20 histories. The lower table refits only the uninhibited background intercept on training data; all original inhibited fits and gates stay unchanged. This isolates comparator sensitivity without claiming joint nuisance fitting or parameter recovery. In the separate original unit-mark S04 controls, all 20 narrow/short histories had no rejected proposals; they are not additional S04B replicates.'
    studies[-1]['source']='Chapter 13: original fixed-floor S04B summaries, source-backed generator/parameter diagnostics, and completed 80-history intercept sensitivity.'
    payload={'studies':studies,'sources':sources,'scope':'Reported aggregates, including the completed 80-history joint comparison and historical fixed-floor/intercept sensitivity. Observed selectors show point contrasts; multi-scale block intervals are descriptive sensitivity summaries and nominal sign-flip references are not calibrated for unverified long-memory dependence. The moderate control and stronger ETAS benchmark are reported in the current guide and monograph. Original historical fitting searches were not repeated by this publication build.'}
    append_joint_publications(ROOT,studies,sources)
    write_findings(out,payload)
    return payload
