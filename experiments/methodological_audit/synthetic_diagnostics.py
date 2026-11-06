"""Saved-record census only. No generator, likelihood, or optimizer imports."""
from pathlib import Path
import argparse,hashlib,json,math,statistics
import numpy as np
def main():
    REPO=Path(__file__).resolve().parents[2];ROOT=REPO/'reproduction/synthetic'
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    if args.output.exists(): raise FileExistsError(args.output)
    sha=lambda b:hashlib.sha256(b).hexdigest()
    read=lambda p:json.loads(Path(p).read_text(encoding='utf-8'))
    manifest=read(ROOT/'input_manifest.json');entries={x['path']:x for x in manifest['files']};checked={}
    def load(path,json_data=True):
        p=ROOT/path;b=p.read_bytes();m=entries[path];assert len(b)==m['bytes'] and sha(b)==m['sha256'],path;checked[path]=m['sha256']
        return json.loads(b) if json_data else p
    cases=[];fit_rows=[];examples={};bounds=[(0.,4.),(math.log(5.),math.log(150.)),(math.log(1/24),math.log(365.))]
    for c in manifest['s04b']['cases']:
        rec=load(c['generator_receipt']);p=load(c['history'],False)
        with np.load(p,allow_pickle=False)as a:rows=a['rows'].copy()
        assert rows.ndim==2 and rows.shape[1]==4 and np.isfinite(rows).all()
        counts=rec['counters'];assert rec['status']=='complete' and counts['accepted_committed']==len(rows)
        nt=int(np.sum((rows[:,0]>=30)&(rows[:,0]<395)));nv=int(np.sum((rows[:,0]>=395)&(rows[:,0]<760)))
        assert (nt,nv)==(c['n_train'],c['n_test'])
        assert counts['accepted_immigrants']+counts['accepted_offspring']==len(rows)
        assert counts['queue_processed']==len(rows)+counts['rejected_immigrants']+counts['rejected_offspring']==counts['queue_created']
        cases.append(dict(case_id=c['case_id'],regime=c['regime'],seed=c['seed'],events=len(rows),n_train=nt,n_test=nv,**counts))
        states=load(c['states']);expected=load(c['expected'])
        for model,path in c['fits'].items():
            f=load(path);s=f['selected'];p=s['pars'];assert len(p)==3 and all(math.isfinite(x)for x in p)
            assert f['status']=='complete' and s['success'] and s['finite_feasible']
            eligible=[x for x in f['records']if x.get('success')and x.get('finite_feasible')]+[{'start':-1,'pars':f['floor'],'nll':f['floor_nll']}]
            chosen=min(eligible,key=lambda r:(r['nll'],r['start']>=0,r['start']));assert chosen['pars']==p and chosen['nll']==s['nll']
            exact=[(p[i]==lo,p[i]==hi)for i,(lo,hi)in enumerate(bounds)]
            close=[(abs(p[i]-lo)<=1e-12,abs(p[i]-hi)<=1e-12)for i,(lo,hi)in enumerate(bounds)]
            row=dict(case_id=c['case_id'],regime=c['regime'],seed=c['seed'],model=model,eta=p[0],ell=math.exp(p[1]),psi=math.exp(p[2]),coordinates=p,eta_zero=p[0]==0,exact_boundary=exact,near_boundary_1e12=close,any_exact_boundary=any(any(x)for x in exact),any_near_boundary=any(any(x)for x in close),training_gain=f['floor_nll']-s['nll'],selected_start=s['start'],selected_method=s['method'],gate_active=f['floor_nll']-s['nll']>1.5*math.log(max(nt,1)))
            fit_rows.append(row)
            if c['seed']==410401 and model=='LI':
                records=[r for r in f['records']if r['start']in [0,1]]
                probes=[]
                for record in records:
                    ix=next(i for i,r in enumerate(states[model])if r['pars']==record['pars'])
                    probes.append({'record':record,'order32_train_saved_components':expected['phase_values']['order32_train'][model][ix]})
                examples['S4_seed410401_LI']=dict(selected=s,floor_nll=f['floor_nll'],starts=probes)
    regimes={}
    for regime in range(4,8):
        group=[x for x in cases if x['regime']==regime];assert len(group)==20
        sums={k:sum(x[k]for x in group)for k in ['accepted_immigrants','accepted_offspring','rejected_immigrants','rejected_offspring','events','n_train','n_test']}
        sums['immigrant_rejection_fraction']=sums['rejected_immigrants']/(sums['rejected_immigrants']+sums['accepted_immigrants'])
        sums['offspring_rejection_fraction']=sums['rejected_offspring']/(sums['rejected_offspring']+sums['accepted_offspring'])
        regimes[str(regime)]=dict(histories=len(group),totals=sums,zero_rejection_seeds=[x['seed']for x in group if x['rejected_immigrants']+x['rejected_offspring']==0],zero_offspring_seeds=[x['seed']for x in group if x['accepted_offspring']==0],mean_train=statistics.mean(x['n_train']for x in group),mean_test=statistics.mean(x['n_test']for x in group),min_train=min(x['n_train']for x in group),max_train=max(x['n_train']for x in group),rejection_by_seed={str(x['seed']):[x['rejected_immigrants'],x['rejected_offspring']]for x in group})
    summary=[]
    for regime in range(4,8):
        for model in ['LI','LIplus_immigrant','LIplus_inclusive']:
            group=[x for x in fit_rows if x['regime']==regime and x['model']==model]
            summary.append(dict(regime=regime,model=model,rows=len(group),eta_zero=sum(x['eta_zero']for x in group),any_exact_boundary=sum(x['any_exact_boundary']for x in group),any_near_boundary=sum(x['any_near_boundary']for x in group),active_boundary=sum(x['eta']>0 and x['any_near_boundary']for x in group),gate_active=sum(x['gate_active']for x in group),eta_median=statistics.median(x['eta']for x in group),ell_median=statistics.median(x['ell']for x in group),psi_median=statistics.median(x['psi']for x in group),marginal_near_boundaries={name:{'lower':sum(x['near_boundary_1e12'][i][0]for x in group),'upper':sum(x['near_boundary_1e12'][i][1]for x in group)}for i,name in enumerate(['eta','logell','logpsi'])}))
    sourcefiles=['source/generator.py','source/controls_campaign.py','source/cpu_reference.cpp','source/direct_oracle.py','replay.py','input_manifest.json']
    background_exposure=math.exp(math.log(.2)-.2)*760/(2*.2)*(math.exp(2*.2*760/760)-math.exp(2*.2*395/760))
    for row in summary:
        group=[x for x in fit_rows if x['regime']==row['regime'] and x['model']==row['model']]
        for name in ['eta','ell','psi']:
            row[name+'_min']=min(x[name] for x in group)
            row[name+'_max']=max(x[name] for x in group)
    for row in regimes.values():
        row['zero_rejection_histories']=len(row['zero_rejection_seeds'])
        row['proposed_immigrants']=row['totals']['accepted_immigrants']+row['totals']['rejected_immigrants']
        row['proposed_offspring']=row['totals']['accepted_offspring']+row['totals']['rejected_offspring']
        row['zero_offspring_histories']=len(row['zero_offspring_seeds'])
        row['immigrant_rejection_percent']=100*row['totals']['immigrant_rejection_fraction']
        row['offspring_rejection_percent']=100*row['totals']['offspring_rejection_fraction']
    result=dict(schema='saved_s04b_diagnostics_v1',passed=True,scientific_model_calls=0,source_files_checked=len(checked),cases=80,fit_vectors=240,regimes=regimes,fit_summary=summary,examples=examples,fixed_background_test_exposure=background_exposure,fixed_background_exposure_scope='Analytic integral of the fixed background over [395,760), excluding offspring excitation.',source_sha256={p:sha((ROOT/p).read_bytes())for p in sourcefiles})
    result.update(case_census=cases,fit_census=fit_rows,input_sha256=checked,
        input_root='reproduction/synthetic',
        script_sha256=sha(Path(__file__).read_bytes()),
        boundary_definition='Any selected coordinate at a box endpoint; exact equality and absolute tolerance 1e-12 in eta/logell/logpsi agree. Includes eta=0; active_boundary additionally requires eta>0.',
        coupling_status='Source-derived implication from isolated random streams and zero rejected proposals; no counterfactual simulation executed.',
        interpretation='Saved realized histories and selected vectors. These are not parameter-recovery estimates or a null-law equivalence claim.')
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(result,indent=2,allow_nan=False)+'\n',encoding='utf-8')
    print(json.dumps(dict(passed=True,cases=len(cases),fit_vectors=len(fit_rows),checked_files=len(checked),output=str(args.output))))

if __name__ == '__main__':
    main()
