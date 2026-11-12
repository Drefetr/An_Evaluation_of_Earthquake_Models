"""Moderate total-attenuation benchmark, fixed after disjoint engineering pilots.

Generation uses the archived chronological simulator. Both fitted arms free
(a,d,n,c,p); the inhibited arm also frees (eta,ell,psi). A positive tensor
quadrature is doubled for selected-state validation, never selected on test.
"""
import os
for k in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','NUMEXPR_NUM_THREADS','BLIS_NUM_THREADS'):os.environ[k]='2'
import argparse,dataclasses,gc,json,math,time
from pathlib import Path
import numpy as np
from numpy.polynomial.legendre import leggauss
from threadpoolctl import threadpool_limits
from experiments.s04b_joint_nuisance import model,fit,checkpoint
from experiments.s04b_joint_execution.parallel_chunks import OrderedChunkScheduler,ParallelPhase

ROOT=Path(__file__).resolve().parents[2]
DATA=Path(__file__).resolve().parent/'s8_moderate_total'
OUT=ROOT/'validation/live_results/s8_moderate_20261111'
NAME='S8_moderate_total'
def read(p):return json.loads(Path(p).read_text())
def write(p,v):Path(p).parent.mkdir(parents=True,exist_ok=True);checkpoint.write(Path(p),v)

def generate():
    mods=model.archived();G=mods['generator'];G.MATCHED_NAMES.append(NAME)
    DATA.mkdir(exist_ok=False)
    protocol=dict(regime=NAME,seeds=list(range(410821,410841)),law=dict(a=math.log(.25),d=.2,n=.35,c=.05,p=1.3,eta=.4,ell=15.,psi=5.),
        engineering_seeds=list(range(499801,499811)),engineering_result=dict(proposal_rejection_fraction=.3034154090548054,mean_test_events=94.2),
        count_calibration_seeds=list(range(410801,410821)),count_calibration_result=dict(eta=.5,rejection_fraction=.3620815138282387,mean_test_events=91.45),
        engineering_rule='Choose law using only proposal thinning and event counts on disjoint engineering/calibration seeds; freeze before fresh analysis draws. Calibration training was interrupted before any held-out scoring.',
        train=[30,395],test=[395,760],fit_coordinates=['a','d','n','log_c','p','eta','log_ell','log_psi'],
        quadrature='Positive tensor Gauss-Legendre in each of nine spatial cells; archived log time panels. Coarse 8/32, selected 16/64 and 32/128; refine fitting if selected train-score error exceeds 0.01 nat.',
        selection='Eight training starts; exact fitted null included as inhibited candidate; no test selection.')
    write(DATA/'protocol.json',protocol);receipts=[]
    for seed in protocol['seeds']:
        law=G.Law(NAME,seed,'smooth',.4,15.,5.,a=math.log(.25));limits=G.Limits();budget=G.Budget(limits)
        streams=G.ScalarStreams(seed,limits,budget);sim=G._Simulator(law,limits,budget,streams);sim.run()
        rows=np.asarray([[e.time,e.x,e.y,e.Q] for e in sim.history]);np.savez_compressed(DATA/(str(seed)+'.npz'),rows=rows)
        counts=dataclasses.asdict(sim.counts);receipts.append(dict(seed=seed,law=dataclasses.asdict(law),metadata=G.fitting_metadata(law),counters=counts,
            n_train=int(np.sum((rows[:,0]>=30)&(rows[:,0]<395))),n_test=int(np.sum(rows[:,0]>=395)),rng=streams.snapshot()))
    write(DATA/'receipts.json',receipts)
    totals={k:sum(r['counters'][k] for r in receipts) for k in receipts[0]['counters'] if isinstance(receipts[0]['counters'][k],int)}
    frac=(totals['rejected_immigrants']+totals['rejected_offspring'])/totals['queue_processed']
    write(DATA/'generation_summary.json',dict(N=20,counters=totals,rejected_fraction=frac,mean_test_events=np.mean([r['n_test'] for r in receipts]),test_event_range=[min(r['n_test'] for r in receipts),max(r['n_test'] for r in receipts)]))
    print(read(DATA/'generation_summary.json'),flush=True)

class TensorPhase(ParallelPhase):
    def plan(self,order):
        self.check()
        if order not in self._grids:
            x,w=leggauss(order);a=self.a;m=self.m;xy=[];area=[]
            for x0,x1,y0,y1 in a['rectangles']:
                xx=(x0+x1)/2+(x1-x0)/2*x;yy=(y0+y1)/2+(y1-y0)/2*x
                X,Y=np.meshgrid(xx,yy);xy.extend(np.c_[X.ravel(),Y.ravel()]);area.extend((np.outer(w,w)*(x1-x0)*(y1-y0)/4).ravel())
            xy=np.asarray(xy);b,cells=self.modules['controls_campaign'].background(xy,a,m)
            t,tw=self.modules['controls_campaign'].time_plan(a['parent_time'],m['start'],m['end'],.0001,4*order)
            r2=((xy[:,None,:]-a['parent_xy'][None,:,:])**2).sum(axis=2)
            rho=a['reference_pi'][cells]/a['cell_areas'][cells]
            coeff=np.exp(-2*np.log1p(r2/m['sigma']**2))*rho[:,None]*a['parent_fertility'][None,:]/a['parent_normalizer'][None,:]
            self._grids[order]=dict(r2=r2,coeff=coeff,b=b,area=np.asarray(area),t=t,w=tw,space_nodes=len(xy),time_nodes=len(t),parents=len(a['parent_time']),estimate=r2.nbytes+coeff.nbytes)
        return self._grids[order]

class OrderPhase:
    def __init__(self,phase,order):self.phase=phase;self.order=order
    def __getattr__(self,k):return getattr(self.phase,k)
    def evaluate(self,theta,name='null',order=8,require_gradient=True):
        return self.phase.evaluate(theta,name,self.order if order==8 else 2*self.order,require_gradient)

def fit_seed(seed):
    start=time.monotonic();folder=OUT/str(seed);folder.mkdir(parents=True,exist_ok=False)
    record=next(r for r in read(DATA/'receipts.json') if r['seed']==seed)
    mods=model.archived();native=model.Native(ROOT/'validation/live_results/s04b_joint_complete_20261111/native/joint.dll')
    rows=np.load(DATA/(str(seed)+'.npz'))['rows'];gm=record['metadata'];science=read(ROOT/'experiments/s04b_joint_nuisance/protocol.json')
    science['solver']['powell']['maxfev']=15000
    science['solver']['maxiter']=500
    result=dict(seed=seed,passed=False,n_train=record['n_train'],n_test=record['n_test'],fits={},training_checks={})
    def log(v):
        with (folder/'attempts.jsonl').open('a') as f:f.write(checkpoint.dumps(v)+'\n')
    with threadpool_limits(limits=2),OrderedChunkScheduler() as scheduler:
        original=model.phase_from_rows(rows,gm,30,395,mods,native)
        train=TensorPhase(original.a,original.m,mods,native,math.inf,scheduler=scheduler)
        initial=np.array([math.log(.25),.2,.35,math.log(.05),1.3,0.,math.log(30.),math.log(7.)])
        for name in ('null','LIplus_inclusive'):
            eligible=initial if name=='null' else np.asarray(result['fits']['null']['selected']['parameters'])
            order=8
            while True:
                phase=OrderPhase(train,order)
                arm=fit.fit_arm(phase,name,science,eligible,log)
                if not arm['passed']:
                    result.update(error='Unresolved starts',failed_arm=arm);write(folder/'result.json',result);return 1
                check=fit.fine_check(phase,name,arm,science)
                # S8 score convergence is checked at 0.01 nat per selected state.
                if check['absolute_joint_delta']<=.01:break
                log(dict(event='quadrature_refit',model=name,old_order=order,selected_score_delta=check['absolute_joint_delta']))
                order*=2
                if order>32:raise ArithmeticError('S8 selected quadrature convergence failed')
            result['fits'][name]=arm;result['training_checks'][name]=dict(check,fit_order=order)
            write(folder/'result.json',result)
        result['training_selections_frozen']=True
        del train,original;gc.collect()
        original=model.phase_from_rows(rows,gm,395,760,mods,native)
        test=TensorPhase(original.a,original.m,mods,native,math.inf,scheduler=scheduler)
        theta=result['fits']['LIplus_inclusive']['selected']['parameters'];null=result['fits']['null']['selected']['parameters']
        null_score=test.evaluate(null,'null',16)[0];order=16
        while True:
            score=test.evaluate(theta,'LIplus_inclusive',order)[0];fine=test.evaluate(theta,'LIplus_inclusive',order*2)[0]
            delta=abs(score['joint']-fine['joint'])
            if delta<=.01:break
            order*=2
            if order>64:raise ArithmeticError('S8 held-out quadrature convergence failed')
        result.update(passed=True,null_test=null_score,inhibited_test=fine,test_order=order*2,test_quadrature_delta=delta,
            gain=fine['joint']-null_score['joint'],eta=theta[5],wall_seconds=time.monotonic()-start)
        write(folder/'result.json',result)
    print(json.dumps(dict(seed=seed,passed=True,gain=result['gain'],seconds=result['wall_seconds'])),flush=True);return 0

def summarize():
    results=[read(OUT/str(seed)/'result.json') for seed in read(DATA/'protocol.json')['seeds']]
    assert all(r['passed'] for r in results)
    gain=np.asarray([r['gain'] for r in results]);summary=dict(completed_histories=20,mean_gain=float(gain.mean()),median_gain=float(np.median(gain)),wins=int(np.sum(gain>0)),wilson95=__import__('experiments.s04b_joint_nuisance.run',fromlist=['wilson']).wilson(int(np.sum(gain>0)),20),active=sum(r['eta']>0 for r in results),generation=read(DATA/'generation_summary.json'),numerical_max_test_delta=max(r['test_quadrature_delta'] for r in results))
    write(OUT/'summary.json',summary);print(summary)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('operation',choices=['generate','fit','summary']);p.add_argument('--seed',type=int);a=p.parse_args()
    if a.operation=='generate':generate()
    elif a.operation=='summary':summarize()
    else:raise SystemExit(fit_seed(a.seed))
