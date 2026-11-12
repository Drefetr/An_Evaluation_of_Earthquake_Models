"""Training-only magnitude-scaled ETAS and rupture-scaled total attenuation.

Uses the three original California windows. Spatial offspring density is the
normalized, unweighted full-plane inverse-power law; offspring outside the
observed rectangle leave the catalogue. Background KDE is iteratively weighted
by training immigrant probabilities, then frozen identically in both arms.
An analytic uninhibited compensator is combined with scrambled-Sobol importance
integration of the attenuation deficit. All integrals, seeds and error checks
are saved; held-out data never select a fit or bandwidth.
"""
from __future__ import annotations
import argparse,hashlib,io,json,math,sys,time
from pathlib import Path
import numpy as np
import platform
from numpy.polynomial.legendre import leggauss
from scipy.optimize import minimize
from scipy.special import logsumexp
from scipy.stats import qmc
from threadpoolctl import threadpool_limits
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT))
from reproduction.score_replay.core import Inputs

NAMES=['a','d','n','log_c','p','log_sigma0','alpha_s','q','eta','log_ell0','log_psi','gamma']
BOUNDS=[(-12,0),(-2,2),(0,.98),(np.log(.0001),np.log(20)),(1.01,2.5),(np.log(2),np.log(100)),(0,2),(1.05,3),(0,4),(np.log(2),np.log(100)),(np.log(1/24),np.log(365)),(0,2.5)]
NATIVE=None

def write(p,v):
    p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(v,indent=2,allow_nan=False)+'\n')

def cache(folder,row):
    with np.load(io.BytesIO(Inputs(folder).read(row['cache'])),allow_pickle=False) as f:
        return {k:f[k].copy() for k in f.files if k!='metadata_json'},json.loads(str(f['metadata_json'].item()))

class Region:
    def __init__(self,rect):
        self.bounds=np.array([rect[:,0].min(),rect[:,1].max(),rect[:,2].min(),rect[:,3].max()]);b=self.bounds
        self.area=(b[1]-b[0])*(b[3]-b[2])
    def inside(self,xy):
        b=self.bounds;return (xy[:,0]>=b[0])&(xy[:,0]<=b[1])&(xy[:,1]>=b[2])&(xy[:,1]<=b[3])
    def radii(self,xy,order=32):
        """Polar integration split exactly at each rectangle-corner ray."""
        b=self.bounds;corners=np.array([[b[0],b[2]],[b[1],b[2]],[b[1],b[3]],[b[0],b[3]]])
        angles=np.sort(np.mod(np.arctan2(corners[None,:,1]-xy[:,None,1],corners[None,:,0]-xy[:,None,0]),2*np.pi),axis=1)
        angles=np.c_[angles,angles[:,0]+2*np.pi];z,w=leggauss(order)
        half=np.diff(angles)/2;theta=(angles[:,:-1]+half)[:,:,None]+half[:,:,None]*z
        co,si=np.cos(theta),np.sin(theta)
        rx=np.where(co>0,(b[1]-xy[:,0,None,None])/co,(b[0]-xy[:,0,None,None])/co)
        ry=np.where(si>0,(b[3]-xy[:,1,None,None])/si,(b[2]-xy[:,1,None,None])/si)
        radius=np.minimum(rx,ry)
        return (radius**2).reshape(len(xy),-1),(half[:,:,None]*w/(2*np.pi)).reshape(len(xy),-1),xy.copy()
    def mass(self,radii,scale,q):
        # Divergence-theorem boundary integral avoids unresolved narrow angular
        # sectors for parents arbitrarily close to the observation boundary.
        xy=radii[2];b=self.bounds;z,w=leggauss(32);mass=np.zeros(len(xy));ds=mass.copy();dq=mass.copy()
        for axis,edge in [(0,b[0]),(0,b[1]),(1,b[2]),(1,b[3])]:
            other=1-axis;lo=b[2*other]-xy[:,other];hi=b[2*other+1]-xy[:,other]
            cuts=np.clip(scale[:,None]*np.array([-10.,-1.,-.1,0.,.1,1.,10.]),lo[:,None],hi[:,None])
            cuts=np.sort(np.c_[lo,cuts,hi],axis=1);half=np.diff(cuts)/2;center=(cuts[:,:-1]+cuts[:,1:])/2
            v=center[:,:,None]+half[:,:,None]*z;dist=np.abs(edge-xy[:,axis]);r2=dist[:,None,None]**2+v**2
            u=r2/scale[:,None,None]**2;logu=np.log1p(u);tail=np.exp((1-q)*logu)
            den=2*np.pi*np.maximum(r2,1e-300);weight=dist[:,None,None]*half[:,:,None]*w
            mass+=np.sum(weight*(-np.expm1((1-q)*logu))/den,axis=(1,2))
            ds+=np.sum(weight*(-2*(q-1)*np.exp(-q*logu)/(2*np.pi*scale[:,None,None]**2)),axis=(1,2))
            dq+=np.sum(weight*tail*logu/den,axis=(1,2))
        return mass,ds,dq

class Background:
    def __init__(self,xy,region,h=5.,weights=None):
        self.xy=xy;self.region=region;self.h=h;self.weights=np.ones(len(xy)) if weights is None else np.asarray(weights)
        self.weights=self.weights/self.weights.sum();self.mass=region.mass(region.radii(xy),np.full(len(xy),h),2)[0]
    def evaluate(self,xy,leave_self=False):
        out=[]
        for j in range(0,len(xy),1024):
            r2=((xy[j:j+1024,None,:]-self.xy[None,:,:])**2).sum(axis=2)
            kernel=1/(np.pi*self.h**2)*(1+r2/self.h**2)**-2/self.mass
            if leave_self:
                ix=np.arange(j,min(j+1024,len(xy)));kernel[np.arange(len(ix)),ix]=0
                den=1-self.weights[ix];value=(kernel@self.weights)/den
            else:value=kernel@self.weights
            out.append(.05/self.region.area+.95*value)
        return np.concatenate(out)
    def sample(self,u):
        """Inverse-CDF component choice, rejection from each truncated KDE."""
        b=self.region.bounds;xy=np.empty((len(u),2));floor=u[:,0]<.05
        xy[floor]=np.c_[b[0]+u[floor,2]*(b[1]-b[0]),b[2]+u[floor,3]*(b[3]-b[2])]
        ix=np.searchsorted(np.cumsum(self.weights),np.clip((u[~floor,0]-.05)/.95,0,1-1e-15))
        r=self.h*np.sqrt(u[~floor,2]/np.maximum(1-u[~floor,2],1e-15));ang=2*np.pi*u[~floor,3]
        v=self.xy[ix]+r[:,None]*np.c_[np.cos(ang),np.sin(ang)]
        # Rejection uses a separate reproducible RNG; no observed outcomes enter.
        rng=np.random.default_rng(11737)
        bad=~self.region.inside(v)
        while bad.any():
            uu=rng.random((bad.sum(),2));rr=self.h*np.sqrt(uu[:,0]/(1-uu[:,0]));aa=2*np.pi*uu[:,1]
            v[bad]=self.xy[ix[bad]]+rr[:,None]*np.c_[np.cos(aa),np.sin(aa)];bad=~self.region.inside(v)
        xy[~floor]=v;return xy

class Model:
    def __init__(self,a,m,bg):
        self.a,self.m,self.bg=a,m,bg;self.region=bg.region
        self.pt=a['parent_time'];self.dm=a['parent_excess'];self.pxy=a['parent_xy'];self.kp=a['parent_fertility']
        self.radii=self.region.radii(self.pxy);self.be=bg.evaluate(a['event_xy'],leave_self=m['start']==m.get('training_start') and len(a['event_xy'])==len(bg.xy))
        self.events=self.prepare(a['event_time'],a['event_xy'],self.be)
        self.nodes=None
        self.native=NATIVE
    def prepare(self,t,xy,b):
        lag=t[:,None]-self.pt;past=lag>0
        return dict(t=t,xy=xy,b=b,lag=np.maximum(lag,0),past=past,r2=((xy[:,None,:]-self.pxy[None,:,:])**2).sum(axis=2))
    def H(self,data,x,deriv=True):
        if self.native is not None:
            h,g=self.native.evaluate(data,self.dm,self.kp,x,0)
            return (h,g) if deriv else h
        a,d,n,lc,p,ls,alph,q=x[:8];c=np.exp(lc);sigma2=np.exp(2*ls+2*alph*self.dm)
        lag,r2,past=data['lag'],data['r2'],data['past'];v=r2/sigma2
        tl=np.log1p(lag/c);sl=np.log1p(v)
        k=(p-1)/c*np.exp(-p*tl)*(q-1)/(np.pi*sigma2)*np.exp(-q*sl)*self.kp*past
        h=k.sum(axis=1)
        if not deriv:return h
        ds=-2+2*q*v/(1+v)
        grad=np.stack([(k*(-1+p*lag/(c+lag))).sum(axis=1),(k*(1/(p-1)-tl)).sum(axis=1),
            (k*ds).sum(axis=1),(k*ds*self.dm).sum(axis=1),(k*(1/(q-1)-sl)).sum(axis=1)],axis=1)
        return h,grad
    def G(self,data,x):
        if self.native is not None:return self.native.evaluate(data,self.dm,self.kp,x,1)
        eta,le,lp,gamma=x[8:];psi=np.exp(lp);ell2=np.exp(2*le+np.log(10)*self.dm)
        lag,r2,past=data['lag'],data['r2'],data['past'];v=r2/ell2
        k=np.exp(gamma*self.dm-lag/psi)*(1+v)**-2*past
        return k.sum(axis=1),np.stack([(k*4*v/(1+v)).sum(axis=1),(k*lag/psi).sum(axis=1),(k*self.dm).sum(axis=1)],axis=1)
    def exact_exposure(self,x):
        a,d,n,lc,p,ls,alph,q=x[:8];c=np.exp(lc);lo=self.a['parent_exposure_lo'];hi=self.a['parent_exposure_hi']
        ul=np.log1p(lo/c);uh=np.log1p(hi/c);tl=np.exp((1-p)*ul);th=np.exp((1-p)*uh);J=tl-th
        Jc=(p-1)*(tl*lo/(c+lo)-th*hi/(c+hi));Jp=-ul*tl+uh*th
        mass,ms,mq=self.region.mass(self.radii,np.exp(ls+alph*self.dm),q)
        E=float(self.kp@(J*mass));g=np.zeros(12)
        g[2]=E;g[3]=n*self.kp@(Jc*mass);g[4]=n*self.kp@(Jp*mass);g[5]=n*self.kp@(J*ms);g[6]=n*self.kp@(J*ms*self.dm);g[7]=n*self.kp@(J*mq)
        l,r=self.m['start'],self.m['end'];T=self.m['T0'];z=d*(r-l)/T;center=(l+r)/T-1
        if abs(z)<1e-5:s=1+z*z/6+z**4/120;corr=(r-l)/T*(z/3-z**3/45)
        else:s=np.sinh(z)/z;corr=(r-l)/T*(1/np.tanh(z)-1/z)
        B=np.exp(a+d*center)*(r-l)*s;g[0]=B;g[1]=B*(center+corr)
        return B+n*E,g
    def node_setup(self,x,power=13,seed=20261111):
        """Sample fixed half-background/half-trigger proposal, including leakage."""
        u=qmc.Sobol(8,scramble=True,seed=seed).random_base2(power);N=len(u);l,r=self.m['start'],self.m['end'];c=np.exp(x[3]);p=x[4]
        lo=self.a['parent_exposure_lo'];hi=self.a['parent_exposure_hi'];flo=1-(1+lo/c)**(1-p);fhi=1-(1+hi/c)**(1-p)
        prob=self.kp*(fhi-flo);norm=prob.sum();prob/=norm
        immigrant=u[:,0]<.5;t=l+(r-l)*u[:,1];xy=self.bg.sample(u[:,2:6]);ix=np.searchsorted(np.cumsum(prob),np.minimum(u[:,2],1-1e-15))
        f=flo[ix]+u[:,3]*(fhi[ix]-flo[ix]);lag=c*np.expm1(np.log1p(-f)/(1-p))
        s=np.exp(x[5]+x[6]*self.dm[ix]);radius=s*np.sqrt(np.expm1(np.log1p(-u[:,4])/(1-x[7])));ang=2*np.pi*u[:,5]
        t[~immigrant]=self.pt[ix[~immigrant]]+lag[~immigrant]
        xy[~immigrant]=self.pxy[ix[~immigrant]]+radius[~immigrant,None]*np.c_[np.cos(ang[~immigrant]),np.sin(ang[~immigrant])]
        inside=self.region.inside(xy);t=t[inside];xy=xy[inside]
        b=self.bg.evaluate(xy);h=np.concatenate([self.H(self.prepare(t[j:j+1024],xy[j:j+1024],b[j:j+1024]),x,False) for j in range(0,len(t),1024)])
        proposal=.5*b/(r-l)+.5*h/norm
        self.nodes=dict(t=t,xy=xy,b=b,w=1/(N*proposal))
        return dict(power=power,seed=seed,draws=N,inside=int(inside.sum()),proposal_fullplane_trigger_exposure=float(norm))
    def base_values(self,data,x):
        h,hg=self.H(data,x);xt=2*data['t']/self.m['T0']-1;B=np.exp(x[0]+x[1]*xt)*data['b'];lam=B+x[2]*h
        grad=np.zeros((len(lam),12));grad[:,0]=B;grad[:,1]=B*xt;grad[:,2]=h;grad[:,3:8]=x[2]*hg
        return lam,grad
    def objective(self,x,inhibit=False,details=False):
        x=np.asarray(x);lam,dlam=self.base_values(self.events,x);E,grad=self.exact_exposure(x);P=np.log(lam).sum();grad-=np.sum(dlam/lam[:,None],axis=0)
        deficit=0.;attenpoint=0.
        if details and inhibit and x[8]==0:
            return dict(ground_point=float(P),exposure=float(E),uninhibited_exposure=float(E),attenuation_deficit=0.,nll=float(E-P))
        if inhibit:
            G,gG=self.G(self.events,x);attenpoint=x[8]*G.sum();grad[8]+=G.sum();grad[9:]+=x[8]*gG.sum(axis=0)
            data=self.nodes
            if data is None:raise RuntimeError('missing frozen integration proposal')
            for j in range(0,len(data['t']),1024):
                raw={k:v[j:j+1024] for k,v in data.items()};z=self.prepare(raw['t'],raw['xy'],raw['b']);L,dL=self.base_values(z,x);g,dg=self.G(z,x);atten=np.exp(-x[8]*g);dec=-np.expm1(-x[8]*g);w=raw['w']
                deficit+=float(w@(L*dec));grad-=np.sum(dL*(w*dec)[:,None],axis=0)
                grad[8]-=w@(L*atten*g);grad[9:]-=np.sum(dg*(w*L*atten*x[8])[:,None],axis=0)
        value=float(E-deficit-P+attenpoint)
        if details:return dict(ground_point=float(P-attenpoint),exposure=float(E-deficit),uninhibited_exposure=float(E),attenuation_deficit=deficit,nll=value)
        return value,grad

def fit(model,starts,inhibit):
    records=[];dim=12 if inhibit else 8
    for index,start in enumerate(starts):
        tick=time.perf_counter();base=np.asarray(start,float)
        def target(v):
            x=base.copy();x[:dim]=v;v,g=model.objective(x,inhibit);return v,g[:dim]
        opt=minimize(target,base[:dim],jac=True,bounds=BOUNDS[:dim],method='L-BFGS-B',options=dict(maxiter=350,maxls=40,ftol=1e-10,gtol=2e-5))
        attempts=[dict(success=bool(opt.success),message=str(opt.message),nfev=int(opt.nfev),nll=float(opt.fun))]
        if not opt.success:
            opt=minimize(target,opt.x,jac=True,bounds=BOUNDS[:dim],method='L-BFGS-B',options=dict(maxiter=1000,maxls=200,ftol=1e-11,gtol=2e-5))
            attempts.append(dict(success=bool(opt.success),message=str(opt.message),nfev=int(opt.nfev),nll=float(opt.fun)))
        x=base.copy();x[:dim]=opt.x
        records.append(dict(start=index,success=bool(opt.success),message=str(opt.message),parameters=x.tolist(),nll=float(opt.fun),nit=int(opt.nit),nfev=int(opt.nfev),seconds=time.perf_counter()-tick,attempts=attempts))
        print('fit',model.m['case_id'],'inhibited' if inhibit else 'null',index,records[-1]['nll'],records[-1]['success'],round(records[-1]['seconds'],1),flush=True)
    valid=[r for r in records if r['success']]
    if not valid:raise ArithmeticError('no successful training optimization')
    return dict(records=records,selected=min(valid,key=lambda r:r['nll']),complete=len(valid)==len(starts))

def inputs(case):
    folder=ROOT/'reproduction/score_replay/california';reg=json.loads((folder/'registry.json').read_bytes())
    rows={r['phase']:r for r in reg['rows'] if r['case']==case and r['procedure_key']=='Omori_smooth_cont' and r['study']=='primary_california'}
    train,tm=cache(folder,rows['train']);test,vm=cache(folder,rows['test']);return train,tm,test,vm,rows

def run_case(case,out,power=13,check_power=16):
    tick=time.perf_counter();train,tm,test,vm,source=inputs(case);region=Region(train['rectangles']);bg=Background(train['event_xy'],region,tm['kde_bandwidth'])
    start=np.array([-3.4,0.,.6,np.log(.01),1.2,np.log(5),.5,1.6,0,np.log(20),np.log(5),.75*np.log(10)])
    starts=[start.copy() for _ in range(3)]
    starts[1][[5,6,7]]=[np.log(2),.8,2.];starts[2][[5,6,7]]=[np.log(15),.2,1.2]
    decluster=[]
    for iteration in range(5):
        model=Model(train,tm,bg);fit0=fit(model,starts if iteration==0 else [start],False);start=np.array(fit0['selected']['parameters'])
        lam,_=model.base_values(model.events,start);mu=np.exp(start[0]+start[1]*(2*train['event_time']/tm['T0']-1))*model.be
        weights=mu/lam;decluster.append(dict(iteration=iteration,training_nll=fit0['selected']['nll'],expected_immigrants=float(weights.sum()),parameters=start.tolist()))
        bg=Background(train['event_xy'],region,tm['kde_bandwidth'],weights)
    # Freeze the final declustered density and refit both arms from this point.
    model=Model(train,tm,bg);null=fit(model,[start,*starts],False);x0=np.array(null['selected']['parameters']);proposal=model.node_setup(x0,power)
    active=[]
    for eta,ell,psi in [(.05,10,2),(.2,20,5),(.5,50,30)]:
        x=x0.copy();x[8:11]=[eta,np.log(ell),np.log(psi)];active.append(x)
    inh=fit(model,[x0,*active],True)
    # The exact null is always an eligible nested candidate, without noisy E.
    if null['selected']['nll']<=inh['selected']['nll']:
        inh['selected']=dict(null['selected'],nested_null=True)
    selected=np.array(inh['selected']['parameters']);evalmodel=Model(test,vm,bg)
    scores=[]
    for seed in range(20261120,20261124):
        info=evalmodel.node_setup(x0,check_power,seed)
        s0=evalmodel.objective(x0,False,True);s1=evalmodel.objective(selected,True,True)
        scores.append(dict(seed=seed,proposal=info,null=s0,inhibited=s1,gain=s0['nll']-s1['nll']))
    gains=np.array([v['gain'] for v in scores]);training_checks=[]
    for seed in range(20261130,20261132):
        model.node_setup(x0,check_power,seed)
        training_checks.append(dict(seed=seed,null_nll=model.objective(x0,False,True)['nll'],inhibited_nll=model.objective(selected,True,True)['nll']))
    result=dict(case=case,parameter_names=NAMES,bounds=BOUNDS,declustering=decluster,background_weights=bg.weights.tolist(),null=null,inhibited=inh,training_proposal=proposal,training_independent_checks=training_checks,test_scores=scores,
        test_gain_mean=float(gains.mean()),test_integration_standard_error=float(gains.std(ddof=1)/np.sqrt(len(gains))),elapsed_seconds=time.perf_counter()-tick,
        n_train=len(train['event_time']),n_test=len(test['event_time']),source_cache_sha256={k:v['cache']['sha256'] for k,v in source.items()},
        background='Training-only iterative immigrant-probability weighted KDE, fixed 5 km inherited bandwidth and 5% uniform floor; leave-self-out density during training. Final density held identical in both arms.',
        spatial='Unweighted full-plane inverse-power offspring kernel; sigma(m)=sigma0 exp(alpha_s (m-M0)); exact regional leakage in compensator.',
        inhibition='Total intensity multiplied by exp(-eta G); G uses exp(gamma (m-M0)) marks, exponential relaxation, and ell(m)=ell0 10^(0.5 (m-M0)).')
    write(out/'result.json',result);return result

def main():
    global NATIVE
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=Path,required=True);p.add_argument('--case',default='all');p.add_argument('--power',type=int,default=13);p.add_argument('--check-power',type=int,default=16);p.add_argument('--native-threads',type=int,default=2,help='Compiled pairwise contractions; 0 selects reference NumPy');p.add_argument('--backend',choices=('cpu','cuda'),default='cpu');a=p.parse_args()
    if a.backend=='cuda':
        from experiments.etas_inhibition_benchmark.gpu_native import build,Native
        NATIVE=Native(build(ROOT/'build/etas_benchmark_gpu_20261111'))
    elif a.native_threads:
        from experiments.etas_inhibition_benchmark.native import build,Native
        NATIVE=Native(build(ROOT/'build/etas_benchmark_native_20261111'/platform.system()),threads=a.native_threads)
    source_files=[Path(__file__),Path(__file__).with_name('native.py'),Path(__file__).with_name('pairs.cpp')]
    if a.backend=='cuda':source_files += [Path(__file__).with_name('gpu_native.py'),Path(__file__).with_name('gpu_pairs.cu')]
    pins={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in source_files}
    write(a.output/'launch.json',dict(source_sha256=pins,native_threads=a.native_threads,backend=a.backend))
    cases=[f'california_fold_{i}' for i in range(3)] if a.case=='all' else [a.case];rows=[]
    with threadpool_limits(limits=1):
        for case in cases:
            print('starting',case,flush=True);r=run_case(case,a.output/case,a.power,a.check_power);rows.append(r);print(case,r['test_gain_mean'],r['test_integration_standard_error'],r['elapsed_seconds'],flush=True)
    for name,expected in pins.items():
        if hashlib.sha256(Path(__file__).with_name(name).read_bytes()).hexdigest()!=expected:raise RuntimeError('source changed during pilot execution')
    write(a.output/'summary.json',dict(schema='magnitude_scaled_etas_inhibition_benchmark_pilot_v1',accepted=False,source_sha256=pins,rows=[dict(case=r['case'],test_gain_mean=r['test_gain_mean'],test_integration_standard_error=r['test_integration_standard_error'],n_train=r['n_train'],n_test=r['n_test']) for r in rows]))
if __name__=='__main__':main()
