"""Paired calendar-block resampling of realized-history predictive score contrasts.

Each block contains BOTH its event log-intensity contrast and its signed
integrated-rate contrast. Parameters stay at their saved training estimates.
The bootstrap is conditional on these fitted procedures, not a refitting or
physical-mechanism test. Empty calendar blocks and terminal exposure are kept.
"""
from __future__ import annotations
import argparse, gzip, hashlib, importlib.util, io, json, math, sys, time, zipfile
from pathlib import Path
import numpy as np
from scipy.stats import binomtest
from numpy.polynomial.legendre import leggauss
from threadpoolctl import threadpool_limits

ROOT=Path(__file__).resolve().parents[2]
DEVICE='cpu'
sys.path.insert(0,str(ROOT))
from reproduction.score_replay.core import Inputs

def load_cache(folder,row):
    raw=Inputs(folder).read(row['cache'])
    with np.load(io.BytesIO(raw),allow_pickle=False) as f:
        a={k:f[k].copy() for k in f.files if k!='metadata_json'}
        m=json.loads(str(f['metadata_json'].item()))
    return a,m

def edges(start,end,days):
    return np.r_[np.arange(start,end,days),end]

def grouped(t,v,e):
    return np.histogram(t,bins=e,weights=v)[0]

def split_gauss(times,weights,order,cuts):
    """Insert calendar boundaries into existing Gauss panels, preserving order."""
    z,w=leggauss(order);tt=np.asarray(times).reshape(-1,order);ww=np.asarray(weights).reshape(-1,order)
    center=(tt[:,0]+tt[:,-1])/2;half=(tt[:,-1]-tt[:,0])/(z[-1]-z[0]);newt=[];neww=[]
    for j,(c,h) in enumerate(zip(center,half)):
        left,right=c-h,c+h;inside=cuts[(cuts>left+1e-10)&(cuts<right-1e-10)]
        if not len(inside):newt.append(tt[j]);neww.append(ww[j]);continue
        endpoints=np.r_[left,inside,right];hh=np.diff(endpoints)/2;cc=(endpoints[1:]+endpoints[:-1])/2
        newt.append((cc[:,None]+hh[:,None]*z).ravel());neww.append((hh[:,None]*w).ravel())
    return np.concatenate(newt),np.concatenate(neww)

def resample(values,seed=20261111,replicates=49999):
    """Nonoverlapping block bootstrap total and paired block sign permutation."""
    x=np.asarray(values,float);rng=np.random.default_rng(seed);n=len(x)
    draws=np.empty(replicates);perms=np.empty(replicates)
    for i in range(0,replicates,1000):
        b=min(1000,replicates-i)
        draws[i:i+b]=x[rng.integers(n,size=(b,n))].sum(axis=1)
        perms[i:i+b]=(x*rng.choice([-1.,1.],size=(b,n))).sum(axis=1)
    nonzero=x[np.abs(x)>1e-12]
    return dict(total=float(x.sum()),blocks=n,positive_blocks=int((x>0).sum()),
        ci95_total=np.quantile(draws,[.025,.975]).tolist(),
        paired_sign_permutation_p=float((1+(np.abs(perms)>=abs(x.sum())).sum())/(replicates+1)),
        sign_test_p=float(binomtest(int((nonzero>0).sum()),len(nonzero),.5).pvalue) if len(nonzero) else 1.,
        replicates=replicates,seed=seed)

def rows_for(folder,procedure):
    r=json.loads((folder/'registry.json').read_bytes())
    return [(row,Inputs(folder).json(row['state'])) for row in r['rows'] if row['phase']=='test' and row['procedure_key']==procedure and (folder.name!='california' or row['study']=='primary_california')]

def temporal_bins(a,m,pars,e):
    a0,d,n,logc,p=pars[:5];c=np.exp(logc)
    t=a['event_time'];lag=t[:,None]-a['parent_time'];u=np.maximum(lag,0.)
    k=np.where(lag>0,(p-1)/c*np.exp(-p*np.log1p(u/c)),0)*a['parent_fertility']
    density=a['event_parent_density']
    lp=np.log(np.exp(a0+d*(2*t/m['T0']-1))*a['event_background_density']+n*(k*density).sum(axis=1))
    lg=np.log(np.exp(a0+d*(2*t/m['T0']-1))+n*k.sum(axis=1))
    def bg(l,r):
        center=(l+r)/m['T0']-1;z=d*(r-l)/m['T0']
        return np.exp(a0+d*center)*(r-l)*np.sinc(1j*z/np.pi).real
    exposure=[]
    for l,r in zip(e[:-1],e[1:]):
        lo=np.maximum(l-a['parent_time'],0);hi=np.maximum(r-a['parent_time'],0)
        mass=np.exp((1-p)*np.log1p(lo/c))*(-np.expm1((1-p)*np.log1p((hi-lo)/(c+lo))))
        exposure.append(bg(l,r)+n*mass@a['parent_fertility'])
    return grouped(t,lp,e),np.asarray(exposure),grouped(t,lp-lg,e)

def california(days):
    oc=dict((r['case'],(r,s)) for r,s in rows_for(ROOT/'reproduction/score_replay/california','Omori_smooth_cont'))
    ep=dict((r['case'],(r,s)) for r,s in rows_for(ROOT/'reproduction/score_replay/california_benchmark','EP'))
    out=[]
    for case,(row,state) in oc.items():
        a,m=load_cache(ROOT/'reproduction/score_replay/california',row)
        er,es=ep[case];b,bm=load_cache(ROOT/'reproduction/score_replay/california_benchmark',er)
        pars=es['parameters'];scale,q=np.exp(pars[5]),pars[6]
        mass=rectangle_mass(b['parent_xy'],b['rectangles'],scale,q)
        norm=mass*np.pi*scale**2/(q-1)
        r2=((b['event_xy'][:,None,:]-b['parent_xy'][None,:,:])**2).sum(axis=2)
        b['event_parent_density']=np.exp(-q*np.log1p(r2/scale**2))/norm
        e=edges(m['start'],m['end'],days)
        op,oe,ol=temporal_bins(a,m,state['parameters'],e)
        pp,pe,pl=temporal_bins(b,bm,pars,e)
        delta=op-oe-pp+pe;loc=ol-pl
        expected=state['expected_components']['joint']-es['expected_components']['joint']
        if abs(delta.sum()-expected)>1e-6:raise ArithmeticError(('CA sum custody',case,delta.sum(),expected))
        out.append(dict(contrast='CA_OC_minus_EP',case=case,block_days=days,edges=e.tolist(),
            delta_P=(op-pp).tolist(),delta_E=(oe-pe).tolist(),block_scores=delta.tolist(),
            location_block_scores=loc.tolist(),expected_total=expected,summary=resample(delta),location_summary=resample(loc)))
    return out

def rectangle_mass(xy,rect,scale,q):
    """Normalized full-plane radial mass via rectangular boundary integral."""
    bounds=[rect[:,0].min(),rect[:,1].max(),rect[:,2].min(),rect[:,3].max()];z,w=leggauss(32);mass=np.zeros(len(xy))
    for axis,edge in [(0,bounds[0]),(0,bounds[1]),(1,bounds[2]),(1,bounds[3])]:
        other=1-axis;lo=bounds[2*other]-xy[:,other];hi=bounds[2*other+1]-xy[:,other]
        cuts=np.clip(scale*np.array([-10.,-1.,-.1,0.,.1,1.,10.])[None,:],lo[:,None],hi[:,None]);cuts=np.sort(np.c_[lo,cuts,hi],axis=1)
        half=np.diff(cuts)/2;center=(cuts[:,:-1]+cuts[:,1:])/2;v=center[:,:,None]+half[:,:,None]*z;dist=np.abs(edge-xy[:,axis]);r2=dist[:,None,None]**2+v**2
        mass+=np.sum(dist[:,None,None]*half[:,:,None]*w*(-np.expm1((1-q)*np.log1p(r2/scale**2)))/(2*np.pi*np.maximum(r2,1e-300)),axis=(1,2))
    return mass

def new_zealand(days):
    path=ROOT/'reproduction/observed/historical_observed.json.gz';d=json.load(gzip.open(path))
    import pandas as pd
    frame=pd.read_csv(ROOT/'reproduction/nzca/expected/geonet_M5_shallow_1960_2026.csv')
    times=frame.t_days.to_numpy();excess=frame.excess.to_numpy()
    sys.path.insert(0,str(ROOT/'engine/iteration_27/code'))
    from adequacy import PredictiveHistory,_record_components,background_integral
    out=[]
    for name,f in d['folds'].items():
        start,end=f['train_end'],f['test_end'];e=edges(start,end,days);beta=f['fit']['beta_train']
        h=PredictiveHistory(times,excess,beta,start,end,d['T0'],32)
        # Split the original high-order event-gap panels at every calendar edge;
        # no exposure is moved across a block boundary by histogram allocation.
        cuts=np.unique(np.concatenate([edges(start,end,v) for v in (90,180,365,days)]))
        h.tq,h.wq=split_gauss(h.tq,h.wq,32,cuts)
        h.xq=2*h.tq/d['T0']-1;h.group=np.searchsorted(h.edges[1:],h.tq,side='left')
        logs={};exposures={}
        for model in ('ml_trigger','ml_shared'):
            rec=f['fit']['best'][model];tr,ratio,stress=_record_components(rec)
            lp,pieces,aux=h.components(rec['pars'],tr,ratio,stress)
            logs[model]=grouped(h.events,lp,e)
            a,trend,n=rec['pars'][:3]
            if stress is None:
                B=np.array([background_integral(a,trend,l,r,d['T0'])[0] for l,r in zip(e[:-1],e[1:])])
            else:B=grouped(h.tq,h.wq*aux[4],e)
            kp=(1-ratio)*np.exp(beta*ratio*h.excess)
            cumulative=np.array([kp[h.times<t]@tr.cdf(t-h.times[h.times<t]) for t in e])
            exposures[model]=B+n*np.diff(cumulative)
        dp=logs['ml_shared']-logs['ml_trigger'];de=exposures['ml_shared']-exposures['ml_trigger'];delta=dp-de
        expected=f['test_controls']['ml_shared']['order32']['ground_loglik']-f['test_controls']['ml_trigger']['order32']['ground_loglik']
        if abs(delta.sum()-expected)>1e-6:raise ArithmeticError(('NZ sum custody',name,delta.sum(),expected))
        out.append(dict(contrast='NZ_shared_minus_ML',case=name,block_days=days,edges=e.tolist(),delta_P=dp.tolist(),delta_E=de.tolist(),block_scores=delta.tolist(),expected_total=expected,summary=resample(delta)))
    return out

def cpu_marginal(parents,space,times,meta,eta,ell,psi):
    a,d,n,c,p,T,base,marks,sigma=meta
    lag=times[None,:]-parents[:,0,None];past=lag>0;lag=np.maximum(lag,0.)
    temporal=(p-1)/c*np.exp(-p*np.log1p(lag/c));temporal[~past]=0
    decay=np.exp(-lag/psi);decay[~past]=0;del lag,past
    magnitude=np.exp(.75*np.log(10)*parents[:,3]);bt=np.exp(a+d*(2*times/T-1));deficit_time=np.zeros(len(times))
    for begin in range(0,len(space),256):
        nodes=space[begin:begin+256]
        r2=(nodes[:,0,None]-parents[None,:,1])**2+(nodes[:,1,None]-parents[None,:,2])**2
        G=(magnitude[None,:]/(1+r2/ell**2)**2)@decay
        coeff=np.exp(-2*np.log1p(r2/sigma**2))*parents[None,:,4]/parents[None,:,5]*nodes[:,4,None]
        intensity=nodes[:,3,None]*bt[None,:]+n*(coeff@temporal)
        deficit_time+=np.sum((-np.expm1(-eta*G))*intensity*nodes[:,2,None],axis=0)
        if begin%65536==0:print('CPU LI quadrature',begin,len(space),flush=True)
    return deficit_time

def cuda_controls():
    from experiments.methodological_audit.inhibition_cuda import marginal
    parents=np.array([[.2,0.,0.,.1,1.,1.],[.7,.5,-.2,.3,.8,1.2]])
    space=np.array([[0.,0.,.5,.1,.1],[1.,1.,.5,.1,.1]]);times=np.array([.2,.5,.7,1.5]);meta=np.array([-2.,.1,.3,.05,1.3,2.,.8,-.2,10.])
    eta,ell,psi=.4,10.,2.;expected=cpu_marginal(parents,space,times,meta,eta,ell,psi)
    actual,binding=marginal(parents,space,times,meta,eta,ell,psi,ROOT/'build/uncertainty_cuda',tile=1)
    full,_=marginal(parents,space,times,meta,eta,ell,psi,ROOT/'build/uncertainty_cuda',tile=8)
    error=float(max(np.max(abs(actual-expected)),np.max(abs(full-expected))))
    if error>1e-12:raise ArithmeticError(('CUDA strict-past/tile/control',error))
    return dict(passed=True,max_absolute_error=error,expected=expected.tolist(),actual=actual.tolist(),binding=binding)

def local_inhibition(days,order=16,output=None):
    """Exact original quadrature contracted to time marginals before binning."""
    folder=ROOT/'reproduction/score_replay/observed_fixedbackbone'
    registry=json.loads((folder/'registry.json').read_bytes());inputs=Inputs(folder);out=[]
    for row in registry['rows']:
        if row['order']!=order or not row['case'].startswith('california'):continue
        state=inputs.json(row['selected_states']);params=state['models']['LIplus_inclusive']['selected']
        eta,logell,logpsi=params;ell,psi=np.exp(logell),np.exp(logpsi)
        with np.load(io.BytesIO(inputs.read(row['prepared'])),allow_pickle=False) as f:data={k:f[k].copy() for k in f.files}
        parents,events,space,times,weights,meta=(data[k] for k in ('parents','events','space','times','weights','meta'))
        a,d,n,c,p,T,base,marks,sigma=meta;start,end=times.min(),times.max()
        # Exact forecast boundaries are inherited from corresponding OC cache.
        ocrow=next(r for r,s in rows_for(ROOT/'reproduction/score_replay/california','Omori_smooth_cont') if r['case']==row['case'])
        _,m=load_cache(ROOT/'reproduction/score_replay/california',ocrow);e=edges(m['start'],m['end'],days)
        cuts=np.unique(np.concatenate([edges(m['start'],m['end'],v) for v in (90,180,365,days)]))
        times,weights=split_gauss(times,weights,order,cuts)
        dp=np.zeros(len(events))
        for j,v in enumerate(events):
            lag=v[0]-parents[:,0];past=lag>0;r2=(v[1]-parents[past,1])**2+(v[2]-parents[past,2])**2
            dp[j]=-eta*np.sum(np.exp(.75*np.log(10)*parents[past,3]-lag[past]/psi)/(1+r2/ell**2)**2)
        if DEVICE=='cuda':
            from experiments.methodological_audit.inhibition_cuda import marginal
            deficit_time,cuda_binding=marginal(parents,space,times,meta,eta,ell,psi,ROOT/'build/uncertainty_cuda')
            print('CUDA LI completed',row['case'],len(space),len(times),flush=True)
        else:deficit_time=cpu_marginal(parents,space,times,meta,eta,ell,psi)
        if output is not None:
            output.mkdir(parents=True,exist_ok=True)
            np.savez_compressed(output/(row['case']+'.npz'),time=times,exposure_contrast=-weights*deficit_time,event_time=events[:,0],point_contrast=dp,forecast_edges=np.array([m['start'],m['end']]),prepared_sha256=row['prepared']['sha256'],selected_state_sha256=row['selected_states']['sha256'])
        dP=grouped(events[:,0],dp,e);dE=-grouped(times,weights*deficit_time,e);delta=dP-dE
        reference=inputs.json(row['expected']);ex=next(v for v in reference['comparisons'] if v['model']=='LIplus_inclusive' and v['gate']=='raw')['gain']
        if abs(delta.sum()-ex)>1e-5:raise ArithmeticError(('LI sum custody',row['case'],delta.sum(),ex))
        out.append(dict(contrast='CA_LIplus_total_minus_floor',case=row['case'],block_days=days,order=order,
            edges=e.tolist(),delta_P=dP.tolist(),delta_E=dE.tolist(),block_scores=delta.tolist(),expected_total=ex,summary=resample(delta)))
    return out

def pooled(rows,field='block_scores',seed=20261111,replicates=49999):
    arrays=[np.asarray(r[field]) for r in rows];rng=np.random.default_rng(seed);draws=np.zeros(replicates);perms=np.zeros(replicates)
    for x in arrays:
        for i in range(0,replicates,1000):
            b=min(1000,replicates-i);draws[i:i+b]+=x[rng.integers(len(x),size=(b,len(x)))].sum(axis=1);perms[i:i+b]+=(x*rng.choice([-1.,1.],size=(b,len(x)))).sum(axis=1)
    total=float(sum(x.sum() for x in arrays));allx=np.concatenate(arrays);nz=allx[abs(allx)>1e-12]
    return dict(total=total,ci95_total=np.quantile(draws,[.025,.975]).tolist(),paired_sign_permutation_p=float((1+(abs(perms)>=abs(total)).sum())/(replicates+1)),sign_test_p=float(binomtest(int((nz>0).sum()),len(nz),.5).pvalue) if len(nz) else 1.,blocks=len(allx),seed=seed,replicates=replicates,stratification='resample blocks separately within each disjoint fold, then sum')

def marginal_rows(folder,days):
    result=[]
    for path in sorted(folder.glob('*.npz')):
        with np.load(path,allow_pickle=False) as z:
            l,r=z['forecast_edges'];e=edges(l,r,days);dp=grouped(z['event_time'],z['point_contrast'],e);de=grouped(z['time'],z['exposure_contrast'],e)
        score=dp-de;result.append(dict(contrast='CA_LIplus_total_minus_floor',case=path.stem,block_days=days,order=16,edges=e.tolist(),delta_P=dp.tolist(),delta_E=de.tolist(),block_scores=score.tolist(),summary=resample(score)))
    return result

def main():
    global DEVICE
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=Path,required=True);p.add_argument('--block-days',type=float,default=90);p.add_argument('--skip-li',action='store_true');p.add_argument('--device',choices=('cpu','cuda'),default='cpu');a=p.parse_args();DEVICE=a.device
    a.output.mkdir(parents=True,exist_ok=True);begin=time.perf_counter();source_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    report=dict(schema='paired_calendar_block_score_uncertainty_v1',block_days=a.block_days,
        inference='Paired nonoverlapping calendar blocks; conditional on saved training fits. Equal-duration block resampling estimates uncertainty of the total; terminal shorter block retained. Two-sided random sign permutation and binomial sign test are across blocks, not earthquakes.',rows=[])
    dependency_pins={}
    if DEVICE=='cuda':
        for file in ('inhibition_cuda.py','inhibition_marginal.cu'):
            dependency_pins[file]=hashlib.sha256(Path(__file__).with_name(file).read_bytes()).hexdigest()
        report['cuda_controls']=cuda_controls()
    report['device']=DEVICE;report['dependency_sha256']=dependency_pins
    with threadpool_limits(limits=2):
        for name,fun in [('nz',new_zealand),('ca',california)]+([] if a.skip_li else [('li',lambda d:local_inhibition(d,output=a.output/'marginals'))]):
            rows=fun(a.block_days);report['rows']+=rows
            (a.output/(name+'.json')).write_text(json.dumps(rows,indent=2)+'\n')
            print(name,[(r['case'],r['summary']) for r in rows],flush=True)
        report['pooled']={contrast:pooled([r for r in report['rows'] if r['contrast']==contrast]) for contrast in sorted({r['contrast'] for r in report['rows']})}
        ca=[r for r in report['rows'] if r['contrast']=='CA_OC_minus_EP'];report['pooled']['CA_OC_minus_EP_location']=pooled(ca,'location_block_scores')
        nz=[r for r in report['rows'] if r['contrast']=='NZ_shared_minus_ML'];report['NZ_first_fold_fraction']=nz[0]['summary']['total']/sum(r['summary']['total'] for r in nz)
        report['sensitivity']={}
        for size in (180,365):
            rr=new_zealand(size)+california(size)+([] if a.skip_li else marginal_rows(a.output/'marginals',size))
            report['sensitivity'][str(size)]=dict(rows=rr,pooled={contrast:pooled([r for r in rr if r['contrast']==contrast]) for contrast in sorted({r['contrast'] for r in rr})})
    report['elapsed_seconds']=time.perf_counter()-begin
    if source_sha256!=hashlib.sha256(Path(__file__).read_bytes()).hexdigest():raise RuntimeError('source changed during execution')
    for name,expected in dependency_pins.items():
        if expected!=hashlib.sha256(Path(__file__).with_name(name).read_bytes()).hexdigest():raise RuntimeError('CUDA dependency changed during execution')
    report['source_sha256']=source_sha256
    (a.output/'summary.json').write_text(json.dumps(report,indent=2)+'\n')
if __name__=='__main__':main()
