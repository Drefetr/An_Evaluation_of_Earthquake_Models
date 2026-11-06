"""Export only accepted aggregate results; no fit or live-run access."""
import hashlib
import fnmatch
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
AUTH = ROOT/'validation/authorities'

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
    studies.append({'name':'California - observed inhibition (S04)','comparisons':{m+'_'+g:l+' minus shared no-inhibition floor' for m,g,l in procedures},'metrics':['joint'],'windows':windows,'note':'Five fitted procedures on the same 315 targets, not five independent studies. Raw selection and BIC use training only. Gains are held-out joint log scores against a shared no-inhibition floor; no timing/location decomposition is available here. Negative outcomes and boundary selections remain included. Retrospective reused catalogues; zero gain does not establish physical absence of inhibition. Validation uses saved scalar acceptance and sampled CPU/GPU controls, not exhaustive independent likelihood replay or a global optimum certificate.','source':'Chapter 13, reported observed California inhibition comparisons (S04).'})
    audit=read('*_S04B_COMPLETE_AUDIT.json')
    accepted=read('*_S04B_MATCHED_ACCEPTANCE.json')
    assert accepted['final_scientific_accepted'] is True and accepted['accepted'] is True
    assert audit['passed'] and (audit['cases'],audit['score_rows'],audit['summary_rows'],audit['cpu_contexts'])==(80,400,20,48)
    studies.append({'name':'Synthetic controls - S04B fixed-floor and refitted-rate comparisons','kind':'simulation','comparisons':{'LI_raw':'LI','LIplus_immigrant_raw':'LI+ immigrant','LIplus_immigrant_BIC':'LI+ immigrant gated','LIplus_inclusive_raw':'LI+ total','LIplus_inclusive_BIC':'LI+ total gated'},'metrics':['joint'],'summary':audit['independent_summary'],'regime_names':{'4':'Immigrant: narrow/short','5':'Immigrant: broad/long','6':'Total: narrow/short','7':'Total: broad/long'},'note':'Each row contains 20 independent seeded histories within one generating regime. Five procedures share those same histories; 400 scores are not 400 independent replicates. Mean gains are total held-out nats per history, never earthquake-normalized. MC SE is descriptive with no automatic finite-variance or Gaussian guarantee. Wilson 95% intervals describe bounded win indicators, not mean-gain uncertainty, calibrated test power or a physical mechanism. Ties are not wins. Active counts indicate positive selected strength. Training-only BIC can select the exact floor. The shared nuisance backbone is fixed. Regimes are never pooled.','source':'Chapter 13, S04B matched-generator extension.'})
    sensitivity=read('refitted_floor_summary.json')
    generation=read('synthetic_diagnostics.json')
    assert sensitivity['passed'] and sensitivity['cases']==80 and sensitivity['historical_floor_checks']==480
    studies[-1]['refitted_floor']=sensitivity['procedure_summary']
    studies[-1]['note']+=' The narrow/short immigrant generator rejected no event in 19 of 20 histories. The lower table refits only the uninhibited background intercept on training data; all original inhibited fits and gates stay unchanged. This isolates comparator sensitivity without claiming joint nuisance fitting or parameter recovery.'
    studies[-1]['source']='Chapter 13: original fixed-floor S04B summaries, source-backed generator/parameter diagnostics, and completed 80-history intercept sensitivity.'
    payload={'studies':studies,'sources':sources,'scope':'Reported aggregates, including the dated train-only intercept sensitivity. No uncertainty intervals inferred from dependent windows. S06 acceptance covers saved rows and arithmetic, not independent likelihood replay.'}
    (out/'findings-data.json').write_text(json.dumps(payload,indent=2)+'\n',encoding='utf-8')
    template=(ROOT/'website/findings.html').read_text(encoding='utf-8')
    (out/'findings.html').write_text(template.replace('/* DATA */', 'const DATA='+json.dumps(payload).replace('<','\\u003c')+';'),encoding='utf-8')
    return payload
