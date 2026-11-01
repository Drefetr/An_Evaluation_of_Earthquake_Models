"""Q01 independent saved-state, CPU coverage and complete-denominator audit.

No production fitter/gate implementation is imported. No numerical engine runs.
"""
import argparse, csv, hashlib, json, math, statistics
from pathlib import Path
import numpy as np

MODES = [('LI', 'raw'), ('LIplus_immigrant', 'raw'), ('LIplus_immigrant', 'BIC'),
         ('LIplus_inclusive', 'raw'), ('LIplus_inclusive', 'BIC')]
NAMES = ['S4_narrow_short_imm', 'S5_broad_long_imm', 'S6_narrow_short_total', 'S7_broad_long_total']
PHASES = ['order16_train','order16_test','order32_train','order32_test']
def read(p): return json.loads(Path(p).read_text(encoding='utf-8-sig'))
def sha(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def close(a,b,tol=1e-10):
    assert math.isfinite(float(a)) and math.isfinite(float(b)) and abs(float(a)-float(b)) <= tol, (a,b,tol)
def source_bindings(report,run):
    review=read(run/'reviews/Q01_protocol_review.json');dependencies=read(run/'validation/M01_dependency_provenance.json')['expected']
    for path,digest in report['source_pins'].items():
        prefix='/home/gpt/'+run.name+'/'
        if path.startswith(prefix):
            relative=path[len(prefix):];assert sha(run/relative)==digest==review['pins'][relative]
        else:assert dependencies[path]==digest
def audit_case(fitdir, values_override=None):
    report=read(fitdir/'report.json'); states=read(fitdir/'states.json')
    source_bindings(report,fitdir.parent.parent)
    if values_override is not None:report['phase_values']=values_override
    assert set(report['phase_values'])==set(PHASES)
    for filename,digest in report['new_fit_pins'].items(): assert sha(fitdir/filename)==digest
    phase_counts={}
    for phase in PHASES:
        chunks=report['phases'][phase]; assert chunks
        event_count=0
        for chunk in chunks:
            path=fitdir/chunk['path'];assert sha(path)==chunk['sha256']
            with np.load(path,allow_pickle=False) as data:event_count+=len(data['events'])
        phase_counts[phase]=event_count
    assert phase_counts['order16_train']==phase_counts['order32_train']
    assert phase_counts['order16_test']==phase_counts['order32_test']
    result={}; diagnostics=[]
    for model in ['LI','LIplus_immigrant','LIplus_inclusive']:
        fit=read(fitdir/(model+'_fit_private.json'))
        journal=[json.loads(x) for x in (fitdir/(model+'_solver_returns_private.jsonl')).read_text().splitlines() if x.strip()]
        assert fit['records']==journal
        pars=[tuple(x['pars']) for x in states[model]]; assert len(pars)==len(set(pars)) and len(pars)>0
        retained={tuple(x['pars']) for x in journal if x.get('finite_feasible')}|{tuple(fit['floor'])}
        assert set(pars)==retained
        values={}
        for phase in PHASES:
            v=report['phase_values'][phase][model]
            assert len(v)==len(pars) and all(len(x)==6 and all(math.isfinite(y) for y in x) for x in v)
            values[phase]=[x[0] for x in v]
        assert {r['start'] for r in journal if r.get('success') and r.get('finite_feasible')}==set(range(8))
        assert fit['status']=='complete'
        eligible=[x for x in journal if x.get('success') and x.get('finite_feasible')]
        eligible.append(dict(start=-1,pars=fit['floor'],nll=fit['floor_nll']))
        winner=min(eligible,key=lambda r:(r['nll'],r['start']>=0,r['start']))
        assert winner['pars']==fit['selected']['pars'] and winner['nll']==fit['selected']['nll']
        selected=pars.index(tuple(winner['pars'])); floor=pars.index(tuple(fit['floor']))
        replay=max([abs(values['order16_train'][pars.index(tuple(r['pars']))]-r['nll']) for r in journal if r.get('finite_feasible')]+[abs(values['order16_train'][floor]-fit['floor_nll']),abs(values['order16_train'][selected]-winner['nll'])])
        assert replay<=1e-7
        delta=max(abs(a-b) for phase in ['train','test'] for a,b in zip(values['order16_'+phase],values['order32_'+phase])); assert delta<=1e-4
        gap=values['order32_train'][selected]-min(values['order32_train']); assert gap<=1e-4
        rows=[x for x in report['results'] if x['model']==model]
        assert len(rows)==(1 if model=='LI' else 2)
        ntrain=rows[0]['n_train']; ntest=rows[0]['n_test']; assert ntrain>0 and ntest>0
        assert ntrain==phase_counts['order16_train'] and ntest==phase_counts['order16_test']
        threshold=1.5*math.log(ntrain)
        gates=[values['order'+str(order)+'_train'][floor]-values['order'+str(order)+'_train'][selected]>threshold for order in [16,32]]
        assert gates[0]==gates[1]
        near=[i for i,x in enumerate(values['order16_train']) if x<=values['order16_train'][selected]+4e-4]
        forecasts=[values['order32_test'][i] for i in near]; spread=(max(forecasts)-min(forecasts))/ntest; assert spread<.01
        for row in rows:
            choice=selected if row['gate']=='raw' or gates[0] else floor
            gain=values['order32_test'][floor]-values['order32_test'][choice]
            assert row['status']=='complete' and row['win']==(gain>0) and row['off_floor']==(pars[choice][0]>0)
            assert row['selected_state_index']==choice
            close(row['gain'],gain,2e-8 if values_override is not None else 1e-10)
            close(row['near_optimal_spread_per_event'],spread,2e-8 if values_override is not None else 1e-10)
            result[(model,row['gate'])]=row
        diagnostics.append(dict(model=model,states=len(pars),quadrature_max=delta,order32_gap=gap,replay_max=replay,spread=spread))
    assert set(result)==set(MODES) and report['passed'] is True and report['status']=='converged'
    return report,result,diagnostics

def audit_cpu(cpu_path,fitdir):
    cpu=read(cpu_path); gpu=read(fitdir/'report.json'); states=read(fitdir/'states.json')
    source_bindings(cpu,fitdir.parent.parent)
    assert cpu['fit_report_sha256']==sha(fitdir/'report.json')
    assert cpu['passed'] is True and cpu['computational_passed'] is True and cpu['scientific_passed'] is True
    assert set(cpu['phase_values'])==set(PHASES)
    rows=[]
    for phase in PHASES:
        assert set(cpu['phase_values'][phase])==set(states)
        for model in states:
            a=cpu['phase_values'][phase][model]; b=gpu['phase_values'][phase][model]
            assert len(a)==len(b)==len(states[model]) and len(a)>0
            maxima=[0.]*6
            for x,y in zip(a,b):
                assert len(x)==len(y)==6
                for i,(u,v) in enumerate(zip(x,y)):
                    close(u,v,1e-8); maxima[i]=max(maxima[i],abs(u-v))
            rows.append(dict(phase=phase,model=model,states=len(a),output_maxima=maxima))
    assert len(rows)==12
    audit_case(fitdir,cpu['phase_values'])
    return rows

def summary(rows):
    out=[]
    for regime in range(4,8):
        for model,gate in MODES:
            group=[r for r in rows if int(r['regime'])==regime and (r['model'],r['gate'])==(model,gate)]
            assert len(group)==20
            gains=[float(r['gain']) for r in group]; wins=sum(x>0 for x in gains); n=20; p=wins/n; z=1.959963984540054; den=1+z*z/n
            center=(p+z*z/(2*n))/den; half=z*math.sqrt(p*(1-p)/n+z*z/(4*n*n))/den
            out.append(dict(regime=regime,model=model,gate=gate,n=n,mean_gain=statistics.mean(gains),median_gain=statistics.median(gains),mean_standard_error=statistics.stdev(gains)/math.sqrt(n),wins=wins,win_rate=p,win_wilson95=[center-half,center+half],off_floor=sum(bool(r['off_floor']) for r in group)))
    return out

def audit_campaign(config_path, results, scores_path, summary_path):
    config=read(config_path); cases=config['cases']
    assert len(cases)==80 and len({c['case_id'] for c in cases})==80
    expected={(r,s) for r in range(4,8) for s in range(410001+100*r,410021+100*r)}
    assert {(c['regime'],c['seed']) for c in cases}==expected
    anchors={f'{NAMES[r-4]}_seed{410001+100*r}' for r in range(4,8)}
    assert set(config['audit_cases'])==anchors
    allrows=[]; receipts=[]; cpurows=[]; pins={}
    run=results.parent
    for path in [config_path,scores_path,summary_path,run/'reviews/Q01_protocol_review.json',run/'reviews/Q01_boundary_adjudication.json',run/'validation/M01_dependency_provenance.json',Path(__file__),*sorted((run/'source').glob('*.py'))]:pins[str(path.resolve())]=sha(path)
    for case in cases:
        folder=results/(case['case_id']+'_fit')
        report,rows,checks=audit_case(folder)
        assert (report['regime'],report['seed'])==(case['regime'],case['seed'])
        generated=results.parent/'cases'/case['case_id']
        assert not list(generated.glob('*partial*')) and not list(generated.glob('*failure*'))
        original={p.name:sha(p) for p in generated.iterdir() if p.is_file()}
        assert original==report['original_pins']
        for filename,digest in original.items():pins[str((generated/filename).resolve())]=digest
        for filename,digest in report['new_fit_pins'].items():pins[str((folder/filename).resolve())]=digest
        for chunks in report['phases'].values():
            for chunk in chunks:pins[str((folder/chunk['path']).resolve())]=chunk['sha256']
        generator=read(generated/'generator_receipt.json')
        assert generator['status']=='complete' and (generator['regime'],generator['seed'],generator['law'])==(case['regime'],case['seed'],NAMES[case['regime']-4])
        with np.load(generated/'generated_private.npz',allow_pickle=False) as archive:data=np.ascontiguousarray(archive['rows'])
        assert data.ndim==2 and data.shape[1]==4 and np.isfinite(data).all()
        assert np.all(np.diff(data[:,0])>=0) and np.all((data[:,0]>=0)&(data[:,0]<760)) and np.all(data[:,3]>=0)
        assert hashlib.sha256(data.tobytes()).hexdigest()==report['generated_rows_sha256']
        counts=generator['counters'];assert len(data)==counts['accepted_committed']==counts['accepted_decisions']
        assert counts['accepted_immigrants']+counts['accepted_offspring']==len(data)
        assert counts['queue_created']==counts['queue_processed']==len(data)+counts['rejected_immigrants']+counts['rejected_offspring']
        if case['regime']<6:assert counts['rejected_offspring']==0 and generator['rng']['open_uniforms']['7']==0
        for row in rows.values():
            assert row['n_train']==int(np.sum((data[:,0]>=30)&(data[:,0]<395)))
            assert row['n_test']==int(np.sum((data[:,0]>=395)&(data[:,0]<760)))
        pins[str(generated/'generator_receipt.json')]=sha(generated/'generator_receipt.json')
        pins[str(folder/'report.json')]=sha(folder/'report.json')
        for row in rows.values():allrows.append(dict(case_id=case['case_id'],regime=case['regime'],seed=case['seed'],**row))
        receipts.append(dict(case_id=case['case_id'],checks=checks))
        if case['case_id'] in anchors:
            cp=results/(case['case_id']+'_audit')/'report.json';cpurows.extend(audit_cpu(cp,folder));pins[str(cp)]=sha(cp)
    assert len(allrows)==400 and len(cpurows)==48
    with scores_path.open(newline='') as stream:saved=list(csv.DictReader(stream))
    assert len(saved)==400
    key=lambda x:(x['case_id'],x['model'],x['gate'])
    bykey={key(x):x for x in allrows};assert len(bykey)==400 and {key(x) for x in saved}==set(bykey)
    for row in saved:
        truth=bykey[key(row)]
        for k in ['gain','near_optimal_spread_per_event']:close(row[k],truth[k])
        for k in ['regime','seed','n_train','n_test']:assert int(row[k])==truth[k]
        for k in ['win','off_floor']:assert row[k].lower()==str(truth[k]).lower()
    independent=summary(allrows)
    if summary_path.suffix=='.csv':
        with summary_path.open(newline='') as stream:published=list(csv.DictReader(stream))
        for row in published:
            for k in ['regime','n','wins']:row[k]=int(row[k])
            row['mean_standard_error']=float(row.pop('mc_se'))
            row['win_rate']=row['wins']/row['n']
            row['win_wilson95']=[float(row.pop('wilson95_low')),float(row.pop('wilson95_high'))]
    else:published=read(summary_path)
    assert len(published)==20
    published_map={(x['regime'],x['model'],x['gate']):x for x in published};assert len(published_map)==20
    for row in independent:
        saved=published_map[(row['regime'],row['model'],row['gate'])]
        for k in ['n','wins']:assert row[k]==saved[k]
        if 'off_floor' in saved:assert row['off_floor']==saved['off_floor']
        for k in ['mean_gain','median_gain','mean_standard_error','win_rate']:close(row[k],saved[k])
        for x,y in zip(row['win_wilson95'],saved['win_wilson95']):close(x,y)
    return dict(schema='Q01_complete_campaign_audit_v1',passed=True,cases=80,score_rows=400,summary_rows=20,cpu_contexts=48,independent_summary=independent,cases_review=receipts,cpu_coverage=cpurows,pins=pins)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--fit-dir',type=Path);p.add_argument('--cpu-report',type=Path);p.add_argument('--config',type=Path);p.add_argument('--results',type=Path);p.add_argument('--scores',type=Path);p.add_argument('--summary',type=Path);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    if a.fit_dir:
        report,rows,checks=audit_case(a.fit_dir)
        receipt=dict(schema='Q01_saved_state_independent_v1',fit_report_sha256=sha(a.fit_dir/'report.json'),seed=report['seed'],regime=report['regime'],checks=checks,score_rows=5,passed=True)
        if a.cpu_report: receipt['cpu']=audit_cpu(a.cpu_report,a.fit_dir)
    else:
        assert all([a.config,a.results,a.scores,a.summary]);receipt=audit_campaign(a.config,a.results,a.scores,a.summary)
    a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(json.dumps(receipt,indent=2)+'\n')
