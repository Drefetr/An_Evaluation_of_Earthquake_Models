"""Private fixed-backbone LI+ prototype. No stdout rows or fit arrays.

Baseline B/H fields and integration nodes must be prepared causally and frozen
by an admitted geometry/temporal provider. This does not refit that backbone.
"""
import argparse,ctypes,hashlib,json
from pathlib import Path
import numpy as np
from scipy.optimize import minimize

def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()

class Engine:
    def __init__(self,dll,features,qref=0):
        self.dll=ctypes.CDLL(str(Path(dll).resolve()));self.qref=float(qref)
        ptr=np.ctypeslib.ndpointer(dtype=np.float64,flags='C_CONTIGUOUS')
        self.dll.m02_nll.argtypes=[ctypes.c_int]*3+[ptr]*4+[ctypes.c_double,ptr]
        self.dll.m02_nll.restype=ctypes.c_int;self.dll.m02_error.restype=ctypes.c_char_p
        with np.load(features,allow_pickle=False) as f:
            self.e,self.n,self.p=[np.ascontiguousarray(f[k],dtype=np.float64) for k in ('events','nodes','parents')]
        for a,width in ((self.e,6),(self.n,6),(self.p,4)):
            if a.ndim!=2 or a.shape[1]!=width or not np.isfinite(a).all():raise ValueError('M02_FEATURE_SCHEMA')
    def evaluate(self,p):
        p=np.ascontiguousarray(p,dtype=np.float64);out=np.empty(8)
        if p.shape!=(5,):raise ValueError('M02_PARAMETER_SCHEMA')
        if self.dll.m02_nll(len(self.e),len(self.n),len(self.p),self.e,self.n,self.p,p,self.qref,out):
            raise ArithmeticError(self.dll.m02_error().decode())
        return out

def fit(engine,mode,starts,critical):
    if mode not in ('immigrant','inclusive','split'):raise ValueError('M02_MODE')
    if len(starts)!=8:raise ValueError('M02_EIGHT_STARTS_REQUIRED')
    if not np.isfinite(critical) or critical<0:raise ValueError('M02_CRITICAL')
    def physical(x):
        eta=x[:2] if mode=='split' else [x[0],x[0] if mode=='inclusive' else 0]
        return np.array([*eta,np.exp(x[-3]),np.exp(x[-2]),x[-1]])
    bounds=([(0,10)]* (2 if mode=='split' else 1))+[(np.log(.5),np.log(100)),(np.log(.001),np.log(20)),(0,np.log(10)/2)]
    def value_grad(x):
        p=physical(x);v=engine.evaluate(p)
        eta=v[1:3].tolist() if mode=='split' else [v[1]+(v[2] if mode=='inclusive' else 0)]
        return float(v[0]),np.array([*eta,v[3]*p[2],v[4]*p[3],v[5]])
    def fun(x):return value_grad(x)[0]
    floor=engine.evaluate([0,0,1,1,0]);candidates=[]
    for index,start in enumerate(starts):
        x=np.asarray(start,float)
        if x.shape!=(len(bounds),) or any(not lo<=v<=hi for v,(lo,hi) in zip(x,bounds)):raise ValueError('M02_START_BOUNDS')
        result=minimize(value_grad,x,jac=True,method='L-BFGS-B',bounds=bounds,options={'maxls':200})
        candidates.append(dict(start=index,method='L-BFGS-B',success=bool(result.success),x=result.x.tolist(),nll=float(result.fun),message=str(result.message)))
        if not result.success:
            result=minimize(fun,result.x,method='Powell',bounds=bounds)
            candidates.append(dict(start=index,method='Powell',success=bool(result.success),x=result.x.tolist(),nll=float(result.fun),message=str(result.message)))
    valid=[c for c in candidates if c['success'] and np.isfinite(c['nll'])]
    winner=min(valid,key=lambda c:c['nll']) if valid else None
    off=winner is not None and floor[0]-winner['nll']>critical
    selected=physical(winner['x']) if off else np.array([0,0,1,1,0])
    near=[c for c in valid if c['nll']<=min([float(floor[0])]+[c['nll'] for c in valid])+4e-4]
    return dict(schema='m02_fixed_backbone_fit_v1',status='resolved' if len(valid)==8 else 'incomplete_starts',mode=mode,critical=float(critical),floor_nll=float(floor[0]),selected=selected.tolist(),off_floor=bool(off),candidates=candidates,near_optimal=near,physical_gradients='analytic_prototype_pending_independent_controls')

def main():
    p=argparse.ArgumentParser();p.add_argument('--dll',required=True);p.add_argument('--features',required=True);p.add_argument('--config',required=True);p.add_argument('--output',required=True);a=p.parse_args()
    config=json.loads(Path(a.config).read_text(encoding='utf-8-sig'))
    if config.get('execution_admitted') is not True:raise ValueError('M02_NOT_ADMITTED')
    for key,path in [('dll_sha256',a.dll),('features_sha256',a.features)]:
        if config[key]!=sha(path):raise ValueError('M02_PIN_MISMATCH')
    result=fit(Engine(a.dll,a.features,config['qref']),config['mode'],config['starts'],config['critical_improvement'])
    result['pins']={k:sha(v) for k,v in dict(dll=a.dll,features=a.features,config=a.config,source=__file__).items()}
    with Path(a.output).open('x',encoding='utf-8') as f:json.dump(result,f,indent=2,allow_nan=False)
if __name__=='__main__':main()
