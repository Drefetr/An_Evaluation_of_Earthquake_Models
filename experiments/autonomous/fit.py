"""Proposed exploratory autonomous-subfamily fit; never runs on import."""
import argparse,csv,hashlib,json,math,os,time
from pathlib import Path
for key in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','NUMEXPR_NUM_THREADS'):os.environ[key]='1'
import numpy as np
from scipy.optimize import minimize
from threadpoolctl import threadpool_limits
from model import ROOT,GAMMA,RATIO,SOURCE_PINS,ConstantBackgroundObjective,load_engine,shared_kernel,theorem_assumptions

HERE=Path(__file__).resolve().parent
def read(p):return json.loads(Path(p).read_text())
def write(p,v):
    temporary=Path(p).with_suffix('.tmp');temporary.write_text(json.dumps(v,indent=2,allow_nan=False)+'\n');os.replace(temporary,p)
def check(deadline):
    if time.perf_counter()>=deadline:raise TimeoutError('Declared experiment deadline reached')


def json_safe(value):
    """Retain nonfinite optimizer values explicitly in strict JSON records."""
    if isinstance(value,np.ndarray):return json_safe(value.tolist())
    if isinstance(value,np.generic):return json_safe(value.item())
    if isinstance(value,float) and not math.isfinite(value):
        return {'nonfinite':'NaN' if math.isnan(value) else ('+Infinity' if value>0 else '-Infinity')}
    if isinstance(value,dict):return {str(k):json_safe(v) for k,v in value.items()}
    if isinstance(value,(list,tuple)):return [json_safe(v) for v in value]
    return value


def solve_slot(objective,start,bounds,deadline,records,checkpoint):
    def target(p):check(deadline);return objective.evaluate(p)
    initial=float(target(start)[0]);recipes=[('L-BFGS-B',dict(maxiter=250,maxls=40,ftol=1e-12,gtol=1e-7)),('L-BFGS-B',dict(maxiter=250,maxls=200,ftol=1e-12,gtol=1e-7)),('Powell',dict(maxiter=500,maxfev=5000,xtol=1e-7,ftol=1e-10))]
    for tier,(method,options) in enumerate(recipes):
        check(deadline);began=time.perf_counter();row=dict(tier=tier,method=method,start=list(start),options=options,success=False,finite_feasible=False,
            initial_nll=json_safe(initial),fresh_status='not_attempted',fresh_nll=None,
            fresh_reported_abs_delta=None,fresh_reported_tolerance=1e-7,fresh_reported_passed=False,
            nonworsening_tolerance=1e-8,nonworsening_passed=False)
        records.append(row);checkpoint();phase='optimizer'
        try:
            result=minimize((lambda p:target(p)[0]) if method=='Powell' else target,start,method=method,jac=False if method=='Powell' else True,bounds=bounds,options=options)
            # Persist the raw return before feasibility or fresh-value checks.
            raw=json_safe({key:getattr(result,key,None) for key in ('x','fun','success','status','message','nfev','njev','nhev','nit')})
            row.update(raw_return=raw,pars=raw['x'],reported_nll=raw['fun'],solver_success=bool(result.success),
                solver_status=raw['status'],message=raw['message'],nfev=raw['nfev'],nit=raw['nit'])
            checkpoint();phase='feasibility'
            vector=np.asarray(result.x,dtype=float)
            feasible=bool(vector.shape==(len(bounds),) and np.isfinite(vector).all() and all(lo<=v<=hi for v,(lo,hi) in zip(vector,bounds)))
            row['feasible_vector']=feasible
            if feasible:
                phase='fresh_evaluation';row['fresh_status']='running';checkpoint()
                fresh=float(target(vector)[0]);row.update(fresh_status='returned',fresh_nll=json_safe(fresh))
                reported=float(result.fun);finite=math.isfinite(fresh)
                delta=abs(fresh-reported) if finite and math.isfinite(reported) else None
                row.update(finite_feasible=finite,nll=fresh if finite else None,
                    fresh_reported_abs_delta=delta,fresh_reported_passed=delta is not None and delta<=1e-7,
                    nonworsening_passed=finite and fresh<=initial+1e-8)
                row['success']=bool(result.success and row['fresh_reported_passed'] and row['nonworsening_passed'])
            else:row.update(fresh_status='skipped_infeasible',nll=None)
        except Exception as exc:
            row.update(error_type=type(exc).__name__,error=str(exc),error_phase=phase)
            if phase=='fresh_evaluation':row.update(fresh_status='error',fresh_error_type=type(exc).__name__,fresh_error=str(exc))
        row['seconds']=time.perf_counter()-began;checkpoint()
        check(deadline)
        if row['success']:return row
    return None


def fit_arm(objective,starts,bounds,floor,deadline,arm,checkpoint):
    candidates=[dict(pars=list(floor),nll=float(objective.evaluate(floor,False)),origin='exact_floor',start_index=-1)]
    arm.update(attempts=[],candidates=candidates,complete=False)
    for index,start in enumerate(starts):
        records=[];arm['attempts'].append(dict(start_index=index,records=records));checkpoint()
        row=solve_slot(objective,start,bounds,deadline,records,checkpoint)
        if row is not None:candidates.append(dict(pars=row['pars'],nll=row['nll'],origin='optimizer',start_index=index))
    arm['complete']=len(candidates)==len(starts)+1
    arm['selected']=min(candidates,key=lambda r:(r['nll'],r['start_index']>=0,r['start_index']))
    checkpoint()


def training_controls(coarse,fine,arm,deadline):
    all_vectors={tuple(r['pars']) for slot in arm['attempts'] for r in slot['records'] if r.get('finite_feasible')}
    all_vectors.update(tuple(r['pars']) for r in arm['candidates']);rows=[]
    for p in sorted(all_vectors):
        check(deadline);a=float(coarse.evaluate(p,False));b=float(fine.evaluate(p,False))
        rows.append(dict(pars=list(p),nll16=a,nll32=b,delta=abs(a-b)))
    selected=float(fine.evaluate(arm['selected']['pars'],False));best=min(float(fine.evaluate(r['pars'],False)) for r in arm['candidates'])
    passed=all(r['delta']<=1e-4 for r in rows) and selected-best<=1e-4
    return dict(passed=passed,states=rows,selected_order32_gap=selected-best)


def score_components(history,kernel,p):
    full=[p[0],0.,p[1],p[2] if len(p)==3 else 0.]
    logs,pieces,_=history.components(full,kernel,RATIO,kernel)
    mark=float(len(history.events)*math.log(history.beta)-history.beta*history.excess[history.mask].sum())
    ground=float(logs.sum()-pieces.sum())
    return dict(ground=ground,common_mark=mark,full_marked=ground+mark,n_events=len(history.events),integrated_intensity=float(pieces.sum()),final_tail=float(pieces[-1]),event_log_intensities=logs.tolist(),interval_compensators=pieces.tolist())


def run_fold(times,excess,spec,protocol,deadline,fold,checkpoint):
    engine=load_engine();kernel=shared_kernel();end=protocol['T0'];train_end=end*spec['train_fraction'];test_end=end*spec['test_end_fraction']
    mask=times<train_end;N=int(mask.sum());qsum=float(excess[mask].sum())
    if not N or qsum<=0:raise ValueError('Training mark MLE undefined')
    beta=N/qsum;fold.update(beta_train=beta,n_train=N,train_end=train_end,test_end=test_end,mark_moment_gate=theorem_assumptions(-2.,.5,1.,beta));checkpoint()
    if beta<=GAMMA:raise ValueError('Positive-inhibition stress first moment is infinite under declared exponential mark law')
    histories={order:engine.PredictiveHistory(times,excess,beta,0.,train_end,end,order,memory_limit_mb=512.) for order in (16,32)}
    obj={order:ConstantBackgroundObjective(h,kernel) for order,h in histories.items()}
    a0=float(np.clip(np.log(.6*N/train_end),-11.5,-.1));null_starts=[[float(np.clip(a0+offset,-12,0)),n] for offset in (-.5,.5) for n in (.2,.7)]
    null_floor=[float(np.clip(np.log(N/train_end),-12,0)),0.]
    fold['null']={};fit_arm(obj[16],null_starts,[(-12.,0.),(0.,.98)],null_floor,deadline,fold['null'],checkpoint)
    if not fold['null']['complete']:raise ArithmeticError('Incomplete mandatory null starts')
    null=fold['null']['selected']['pars'];starts=[[*null,eta] for eta in (0.,.02,.05,.1,.2,.5,1.,2.)]
    fold['inhibited']={};fit_arm(obj[16],starts,[(-12.,0.),(0.,.98),(0.,3.)],[*null,0.],deadline,fold['inhibited'],checkpoint)
    if not fold['inhibited']['complete']:raise ArithmeticError('Incomplete mandatory inhibited starts')
    for name in ('null','inhibited'):
        fold[name]['training_controls']=training_controls(obj[16],obj[32],fold[name],deadline);checkpoint()
        if not fold[name]['training_controls']['passed']:raise ArithmeticError('Training quadrature/selection gate failed')
        p=fold[name]['selected']['pars'];fold[name]['theorem_assumptions']=theorem_assumptions(p[0],p[1],p[2] if len(p)==3 else 0.,beta)
    del histories,obj
    scores={}
    for order in (16,32):
        check(deadline);history=engine.PredictiveHistory(times,excess,beta,train_end,test_end,end,order,memory_limit_mb=512.)
        scores[str(order)]={name:score_components(history,kernel,fold[name]['selected']['pars']) for name in ('null','inhibited')}
        del history
    gain={order:rows['inhibited']['full_marked']-rows['null']['full_marked'] for order,rows in scores.items()}
    delta=max(abs(scores['16'][name]['full_marked']-scores['32'][name]['full_marked']) for name in ('null','inhibited'))
    passed=delta<=1e-4 and abs(gain['16']-gain['32'])<=1e-4
    fold.update(scores=scores,heldout_gain=gain['32'],heldout_gate=dict(passed=passed,max_score_delta=delta,gain_delta=abs(gain['16']-gain['32'])),complete=passed);checkpoint()
    if not passed:raise ArithmeticError('Heldout quadrature gate failed')


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--output',type=Path,required=True);parser.add_argument('--pilot',action='store_true');parser.add_argument('--data',type=Path)
    args=parser.parse_args(argv);output=args.output.resolve()
    if output.is_relative_to(HERE):parser.error('Use a fresh output directory outside experiment sources')
    output.mkdir(parents=True,exist_ok=False);protocol=read(HERE/'protocol.json');began=time.perf_counter();deadline=began+(600 if args.pilot else 1800)
    result=dict(schema='autonomous_exploratory_result_v1',passed=False,complete=False,pilot=args.pilot,folds={},protocol_sha256=hashlib.sha256((HERE/'protocol.json').read_bytes()).hexdigest(),source_hashes=SOURCE_PINS,scope=protocol['interpretation'])
    checkpoint=lambda:write(output/'result.json',result)
    checkpoint()
    try:
        path=args.data or ROOT/protocol['data']['path']
        if hashlib.sha256(path.read_bytes()).hexdigest()!=protocol['data']['sha256']:raise ValueError('Exact recovered NZ CSV required')
        with path.open(newline='',encoding='utf-8') as f:rows=list(csv.DictReader(f))
        if len(rows)!=protocol['data']['events']:raise ValueError('Catalogue denominator changed')
        times=np.array([float(r['t_days']) for r in rows]);excess=np.array([float(r['excess']) for r in rows])
        result['data_sha256']=protocol['data']['sha256'];load_engine()
        with threadpool_limits(limits=1):
            for spec in protocol['folds'][:1] if args.pilot else protocol['folds']:
                check(deadline);fold=dict(spec=spec,complete=False);result['folds'][spec['id']]=fold;checkpoint()
                run_fold(times,excess,spec,protocol,min(deadline,time.perf_counter()+600),fold,checkpoint)
        result.update(passed=True,complete=not args.pilot)
        if not args.pilot:result['pooled_gain']=sum(f['heldout_gain'] for f in result['folds'].values())
    except Exception as exc:result.update(error_type=type(exc).__name__,error=str(exc))
    finally:result['elapsed_seconds']=time.perf_counter()-began;checkpoint()
    print(json.dumps({k:result[k] for k in ('passed','complete','pilot','elapsed_seconds')}));return 0 if result['passed'] else 1


if __name__=='__main__':raise SystemExit(main())
