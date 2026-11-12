"""Final-power start construction and auditable objective-call tracing."""
from pathlib import Path
import hashlib,json,math,time
import numpy as np

POSITIVE_STARTS=((.05,10.,2.),(.2,20.,5.),(.5,50.,30.))

def construct_starts(null_parameters,terminal_warm_starts):
    null=np.asarray(null_parameters,float).copy()
    if null.shape!=(12,) or not np.isfinite(null).all():raise ValueError('Twelve finite null coordinates required')
    null[8]=0.
    result=[dict(label='exact_null',role='nested_floor',initial_parameters=null.tolist())]
    for i,(eta,ell,psi) in enumerate(POSITIVE_STARTS):
        x=null.copy();x[8:11]=[eta,math.log(ell),math.log(psi)]
        result.append(dict(label=f'positive_{i}',role='prescribed_positive',initial_parameters=x.tolist(),prescribed_eta=eta,prescribed_ell=ell,prescribed_psi=psi))
    for i,warm in enumerate(terminal_warm_starts):
        x=np.asarray(warm,float).copy()
        if x.shape!=(12,) or not np.isfinite(x).all():raise ValueError('Invalid terminal warm start')
        result.append(dict(label=f'terminal_warm_{i}',role='terminal_warm',initial_parameters=x.tolist()))
    return result

class EvaluationTrace:
    def __init__(self,target,specification,power,path,check_budget=lambda:None):
        self.target=target;self.specification=specification;self.power=int(power);self.path=Path(path);self.path.parent.mkdir(parents=True,exist_ok=True)
        self.stream=self.path.open('xb');self.digest=hashlib.sha256();self.completed=0;self.interior=0;self.first=None;self.check_budget=check_budget
    def __call__(self,parameters,inhibit=False,details=False):
        self.check_budget();x=np.asarray(parameters,float);result=self.target(x,inhibit,details)
        value=float(result['nll']) if details else float(result[0])
        if not np.isfinite(value):raise ArithmeticError('Nonfinite traced objective')
        row=dict(evaluation=self.completed,training_power=self.power,parameters=x.tolist(),inhibit=bool(inhibit),details=bool(details),nll=value)
        raw=(json.dumps(row,separators=(',',':'),allow_nan=False)+'\n').encode('utf-8');self.stream.write(raw);self.stream.flush();self.digest.update(raw)
        if self.first is None:self.first=x.tolist()
        self.completed+=1
        if inhibit and not details and x[8]>0:self.interior+=1
        return result
    def close(self):
        self.stream.close()
        initial=self.specification['initial_parameters'];same=self.first is not None and np.array_equal(np.asarray(self.first),np.asarray(initial))
        return dict(initial_parameters=initial,first_evaluation_parameters=self.first,first_evaluation_matches_initial=bool(same),completed_objective_evaluations=self.completed,interior_objective_evaluations=self.interior,training_power=self.power,trace_file=self.path.name,trace_sha256=self.digest.hexdigest())

def traced_fit(module,model,specifications,power,directory,check_budget=lambda:None):
    directory=Path(directory);directory.mkdir(parents=True,exist_ok=True);records=[]
    module.write(directory/'start_protocol.json',dict(training_power=power,starts=specifications))
    for index,spec in enumerate(specifications):
        original=model.objective;trace=EvaluationTrace(original,spec,power,directory/(spec['label']+'.evaluations.jsonl'),check_budget)
        model.objective=trace
        try:one=module.fit(model,[spec['initial_parameters']],True)
        finally:
            model.objective=original;summary=trace.close();module.write(directory/(spec['label']+'.trace_summary.json'),summary)
        for record in one['records']:
            copied=dict(record,start=index,start_label=spec['label'],start_role=spec['role'],initial_parameters=spec['initial_parameters'],evaluation_trace=summary)
            records.append(copied)
    valid=[r for r in records if r['success']]
    positive=[r for r in records if r['start_role']=='prescribed_positive']
    coverage=dict(prescribed_positive_starts=len(positive),passed=len(positive)==3 and all(r['success'] and r['evaluation_trace']['first_evaluation_matches_initial'] and r['evaluation_trace']['interior_objective_evaluations']>0 for r in positive),positive_start_evaluations=[dict(label=r['start_label'],initial_parameters=r['initial_parameters'],completed=r['evaluation_trace']['completed_objective_evaluations'],interior=r['evaluation_trace']['interior_objective_evaluations']) for r in positive])
    if not valid:raise ArithmeticError('No successful final-power start')
    return dict(records=records,selected=min(valid,key=lambda r:r['nll']),complete=len(valid)==len(specifications),interior_start_coverage=coverage)

class Budget:
    def __init__(self,seconds):self.seconds=float(seconds);self.started=time.monotonic()
    def check(self):
        if time.monotonic()-self.started>=self.seconds:raise TimeoutError('Cooperative acceptance wall budget reached; incomplete traces retained')

def budget_objective(target,check):
    def wrapped(*args,**kwargs):check();return target(*args,**kwargs)
    return wrapped
