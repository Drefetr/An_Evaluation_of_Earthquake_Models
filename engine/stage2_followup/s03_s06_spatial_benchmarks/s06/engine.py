"""Direct ctypes bindings; geometric marks and fertility are explicit features.

The copied C++ sources own every history sum. Python only constructs spatial
features and performs optimizer orchestration. All times are strict-past, ties
remain unjittered, and target rows are the window suffix.
"""
from pathlib import Path
import ctypes as ct, hashlib, json, math, os, sys
import numpy as np
HERE=Path(__file__).resolve().parent
SCALES=(5.,15.,50.,150.,500.,1500.)
ORIGINS=(3652.,4748.,5844.);ENDS=(4748.,5844.,6940.)
XEDGE=np.array([-600.,-200.,200.,600.]);YEDGE=np.array([-800.,-800./3,800./3,800.])
RECT=np.array([(XEDGE[j],XEDGE[j+1],YEDGE[i],YEDGE[i+1]) for i in range(3) for j in range(3)])
AREA=(RECT[:,1]-RECT[:,0])*(RECT[:,3]-RECT[:,2]);CENTERS=np.c_[(RECT[:,0]+RECT[:,1])/2,(RECT[:,2]+RECT[:,3])/2]
PD=ct.POINTER(ct.c_double)
CORE_NAMES=('parent_time','event_x','event_cell','event_background_density','background_cell_mass','event_parent_density','parent_cell_mass','parent_fertility','parent_exposure_lo','parent_exposure_hi','mixture_weights','mixture_rates')
CB_NAMES=('parent_time','parent_xy','parent_fertility','parent_exposure_lo','parent_exposure_hi','event_time','event_xy','event_x','event_cell','event_background_density','background_cell_mass','rectangles')
MODELS={'FC':(0,3),'FL':(0,3),'MC':(1,4),'OC':(2,5),'OL':(2,5),'N0':(0,2),'EP':(1,7)}
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def identity(x):return hashlib.sha256(json.dumps(x,sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()
def bounds(arm):
    b=[(-12.,0.),(-2.,2.)]
    if arm=='N0':return b
    b += [(0.,.98)]
    if arm=='MC':b += [(math.log(.001),math.log(20.))]
    if arm in ('OC','OL','EP'):b += [(math.log(.0001),math.log(20.)),(1.01,2.5)]
    if arm=='EP':b += [(math.log(2),math.log(500)),(1.05,3.)]
    return b
def library(name):
    # Build products are separate from the source tree. An explicit override is
    # optional; the normal repository build/native/s06 location is discoverable.
    suffix='.dll' if os.name=='nt' else ('.dylib' if sys.platform=='darwin' else '.so')
    default=Path(__file__).resolve().parents[4]/'build/native/s06'
    directory=Path(os.environ.get('INHIBITORY_S06_NATIVE_DIR',default))
    p=directory/(name+suffix)
    if not p.is_file():raise FileNotFoundError('Build S06 native libraries under build/native/s06 or supply INHIBITORY_S06_NATIVE_DIR: '+str(p))
    lib=ct.CDLL(str(p.resolve()));prefix='ts' if name=='core' else 'cb'
    getattr(lib,prefix+'_create').argtypes=([ct.c_int]*3+[PD]*13) if name=='core' else ([ct.c_int]*2+[PD]*13)
    getattr(lib,prefix+'_create').restype=ct.c_void_p
    for suffix in ('_eval',) if name=='core' else ('_eval','_eval_fine'):
        f=getattr(lib,prefix+suffix);f.argtypes=[ct.c_void_p,ct.c_int,PD,ct.c_int,PD,PD,PD];f.restype=ct.c_int
    getattr(lib,prefix+'_destroy').argtypes=[ct.c_void_p];getattr(lib,prefix+'_last_error').restype=ct.c_char_p
    if name=='core':
        lib.cl_rectangles.argtypes=[ct.c_int,ct.c_int,PD,PD,ct.c_double,PD];lib.cl_rectangles.restype=ct.c_int
    return lib
def rectangle_integrals(xy,scale):
    xy=np.ascontiguousarray(xy,dtype='float64');r=np.ascontiguousarray(RECT);out=np.empty((len(xy),9));lib=library('core')
    if lib.cl_rectangles(len(xy),9,xy.ctypes.data_as(PD),r.ctypes.data_as(PD),scale,out.ctypes.data_as(PD)):raise RuntimeError(lib.ts_last_error().decode())
    if np.any(out<=0) or not np.isfinite(out).all():raise ValueError('rectangle integrals')
    return out
def distance2(a,b):
    # Do not form N x M x 2 arrays.
    return (np.asarray(a)[:,None,0]-np.asarray(b)[None,:,0])**2+(np.asarray(a)[:,None,1]-np.asarray(b)[None,:,1])**2
def pi_from_counts(counts):
    c=np.asarray(counts,float).reshape(3,3);z=c.sum(axis=1)
    if np.any(z<=0):raise ValueError('empty training zone')
    return ((z/z.sum())[:,None]*(c+.5)/(z[:,None]+1.5)).ravel()
def nuisance(cat,fold):
    train=(cat['t_days']>=1826)&(cat['t_days']<ORIGINS[fold]);K=cat['K'][train];xy=cat['xy_km'][train];cells=cat['cell_id'][train].astype(int)
    N=len(K);S=int(K.sum());counts=np.bincount(cells,minlength=9)
    if N<180 or np.any(counts.reshape(3,3).sum(axis=1)<30):raise ValueError('training adequacy')
    if S<=0:raise ValueError('geometric MLE has no finite positive solution')
    beta=math.log1p(N/S)/.1;rho=math.exp(-beta*.1);prefactor=-math.expm1(-.3*beta*.1)/-math.expm1(-beta*.1)
    pi=pi_from_counts(counts);loo_ref=np.empty(N)
    for i,c in enumerate(cells):
        cc=counts.copy();cc[c]-=1;loo_ref[i]=pi_from_counts(cc)[c]/AREA[c]
    d2=distance2(xy,xy);records=[]
    for h in SCALES:
        F=rectangle_integrals(xy,h);Z=F.sum(axis=1);density=(1+d2/h**2)**-2/Z[None,:];np.fill_diagonal(density,0)
        b=.05*loo_ref+.95*density.sum(axis=1)/(N-1)
        records.append(dict(bandwidth_km=h,loo_logscore=float(np.log(b).sum()),n_loo=N))
    chosen=min(range(6),key=lambda i:(-records[i]['loo_logscore'],records[i]['bandwidth_km']))
    return dict(schema='jma_nuisance_v1',fold=fold,training_start=1826.,training_end=ORIGINS[fold],N=N,sumK=S,beta=beta,rho=rho,kappa_prefactor=prefactor,reference_pi=pi.tolist(),cell_counts=counts.tolist(),h_km=SCALES[chosen],h_candidates=records,h_selected_index=chosen,h_grid_edge=chosen in (0,5),mark_measure='reported 0.1 magnitude lattice counting measure',T0=6940.)
def mixture():
    # Same exact numpy recipe as engine/iteration_5/code/kernels.py KernelSpec.
    a=.5;step=.4;tail=1e-8;coefficient=4*np.sin(np.pi*a)/(np.pi*a)
    count=int(np.ceil(max(np.log(4.)/a,np.log(coefficient/tail)/a)/step));v=np.arange(-count,count+1)*step
    raw=step*np.sin(np.pi*a)/(2*np.pi*(np.cosh(a*v)+np.cos(np.pi*a)));raw[[0,-1]]*=.5
    return raw/raw.sum(),np.exp(v)
def features(cat,nuis,start,end,sigma,family):
    t=cat['t_days'];keep=t<end;target=keep&(t>=start);train=(t>=nuis.get('training_start',1826))&(t<nuis['training_end'])
    pt=t[keep];xy=cat['xy_km'][keep];exy=cat['xy_km'][target];ec=cat['cell_id'][target].astype(int);pi=np.asarray(nuis['reference_pi']);b=pi/AREA
    kxy=cat['xy_km'][train];h=nuis['h_km'];F=rectangle_integrals(kxy,h);Z=F.sum(axis=1)
    bgmass=.05*pi+.95*np.mean(F/Z[:,None],axis=0)
    eb=.05*b[ec]+.95*np.mean((1+distance2(exy,kxy)/h**2)**-2/Z[None,:],axis=1)
    if nuis.get('background_type')=='cell':bgmass=pi.copy();eb=b[ec]
    a=dict(parent_time=pt,parent_xy=xy,parent_K=cat['K'][keep],parent_cell=cat['cell_id'][keep],parent_fertility=nuis['kappa_prefactor']*np.exp(.7*nuis['beta']*.1*cat['K'][keep]),parent_exposure_lo=np.maximum(start-pt,0),parent_exposure_hi=end-pt,event_time=t[target],event_xy=exy,event_K=cat['K'][target],event_x=2*t[target]/nuis['T0']-1,event_cell=ec,event_background_density=eb,background_cell_mass=bgmass,rectangles=RECT,cell_areas=AREA,reference_pi=pi,kde_training_xy=kxy,kde_normalizers=Z)
    if family in ('continuous','lift'):
        if family=='continuous':
            F=rectangle_integrals(xy,sigma);Z=F@b;W=F*b[None,:]/Z[:,None];spatial=b[ec,None]*(1+distance2(exy,xy)/sigma**2)**-2/Z[None,:]
        else:
            W=pi[None,:]*(1+distance2(xy,CENTERS)/sigma**2)**-2;W/=W.sum(axis=1)[:,None];spatial=W[:,ec].T/AREA[ec,None]
        a.update(event_parent_density=spatial,parent_cell_mass=W)
        a['mixture_weights'],a['mixture_rates']=mixture()
    mark=float(len(ec)*math.log(nuis['beta'])-nuis['beta']*.1*cat['K'][target].sum()) if nuis.get('mark_measure')=='continuous' else float(len(ec)*math.log(-math.expm1(-nuis['beta']*.1))-nuis['beta']*.1*int(cat['K'][target].sum()))
    a={k:np.ascontiguousarray(v,dtype='float64') for k,v in a.items()}
    m=dict(schema='jma_forecast_cache_v1',start=float(start),end=float(end),T0=nuis['T0'],marks=mark,n_events=len(ec),n_parents=len(pt),sigma_km=float(sigma),family=family,nuisance=nuis,array_sha256={k:hashlib.sha256(v.tobytes()).hexdigest() for k,v in a.items()})
    m['identity_sha256']=identity(m);return a,m
def save_cache(path,a,m):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    with path.open('xb') as f:np.savez(f,metadata_json=np.array(json.dumps(m,sort_keys=True)),**a)
def load_cache(path):
    with np.load(path,allow_pickle=False) as z:m=json.loads(str(z['metadata_json'].item()));a={k:np.ascontiguousarray(z[k]) for k in z.files if k!='metadata_json'}
    check=dict(m);saved=check.pop('identity_sha256')
    if saved!=identity(check) or m['array_sha256']!={k:hashlib.sha256(v.tobytes()).hexdigest() for k,v in a.items()}:raise ValueError('cache identity mismatch')
    return a,m
class Objective:
    def __init__(self,path):
        self.path=Path(path);self.a,self.metadata=load_cache(path);a=self.a;m=self.metadata;self.ne=m['n_events'];self.np=m['n_parents'];self.kind='competitive' if m['family']=='competitive' else 'core';self.lib=library(self.kind);self.prefix='cb' if self.kind=='competitive' else 'ts';self.handle=None
        meta=np.array([m['start'],m['end'],m['T0'],m['marks']],float);names=CB_NAMES if self.kind=='competitive' else CORE_NAMES
        args=[self.ne,self.np]+([] if self.kind=='competitive' else [195])+[a[n].ctypes.data_as(PD) for n in names]+[meta.ctypes.data_as(PD)]
        self.handle=getattr(self.lib,self.prefix+'_create')(*args)
        if not self.handle:raise ValueError(self.error())
    def error(self):return getattr(self.lib,self.prefix+'_last_error')().decode(errors='replace')
    def evaluate(self,arm,pars,*,fine=False,detailed=False):
        mid,dim=MODELS[arm];p=np.ascontiguousarray(pars,dtype='float64');out=np.empty(28);grad=np.empty(dim);logs=np.empty((self.ne,13))
        if p.shape!=(dim,):raise ValueError('dimension')
        fn=getattr(self.lib,self.prefix+('_eval_fine' if fine and self.kind=='competitive' else '_eval'))
        if fn(self.handle,mid,p.ctypes.data_as(PD),dim,out.ctypes.data_as(PD),grad.ctypes.data_as(PD),None if self.kind=='competitive' and not detailed else logs.ctypes.data_as(PD)):raise FloatingPointError(self.error())
        if self.kind=='competitive' and not detailed:logs.fill(0)
        result=dict(joint_nll=float(out[0]),joint_logscore=-float(out[0]),timing_logscore=float(out[1]),conditional_location_logscore=float(out[7]-out[8]),conditional_zone_logscore=float(out[2]),conditional_cell_logscore=float(out[3]),within_cell_density_logscore=float(out[4]),mark_logscore=float(out[5]),integrated_intensity=float(out[6]),positive_C=float(out[6]),signed_negative_C=-float(out[6]),P=float(out[7]),G=float(out[8]),trigger_exposure_unscaled=float(out[9]),gradient=grad,cell_integrated_intensity=out[10:19].copy(),cell_point_event_log_intensity_sum=out[19:28].copy(),conditional_cell_allocation=logs[:,4:13].sum(axis=0),n_events=self.ne)
        n=0 if arm=='N0' else p[2];result['offspring_exposure']=float(n*out[9]);result['immigrant_exposure']=float(out[6]-n*out[9]);result['zone_integrated_intensity']=result['cell_integrated_intensity'].reshape(3,3).sum(axis=1);result['conditional_zone_allocation']=result['conditional_cell_allocation'].reshape(3,3).sum(axis=1)
        if abs(result['joint_logscore']-(result['timing_logscore']+result['conditional_location_logscore']+result['mark_logscore']))>1e-7:raise FloatingPointError('score identity')
        if detailed:result.update(event_logs=logs[:,:4],event_conditional_cell_allocation=logs[:,4:13])
        if self.kind=='competitive' and not detailed:
            for key in ('conditional_zone_logscore','conditional_cell_logscore','within_cell_density_logscore','cell_integrated_intensity','cell_point_event_log_intensity_sum','conditional_cell_allocation','zone_integrated_intensity','conditional_zone_allocation'):result.pop(key)
        return result
    def close(self):
        if self.handle:getattr(self.lib,self.prefix+'_destroy')(self.handle);self.handle=None
    def __enter__(self):return self
    def __exit__(self,*args):self.close()
    def __del__(self):
        try:self.close()
        except Exception:pass
