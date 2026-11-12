"""Joint marked occurrence likelihood with fixed spatial and mark laws.

The Omori point fields and unattenuated exposure are evaluated analytically.
Only the inhibited exposure deficit uses fixed positive quadrature. Native
recurrences calculate stress and its log-scale derivatives; variable temporal
trigger fields use bounded matrix products, never a frozen backbone.
"""
from __future__ import annotations
import ctypes as C
import importlib.util
import math
from pathlib import Path
import sys
import time
import numpy as np

HERE=Path(__file__).resolve().parent
REPO=HERE.parents[1]

def archived():
    source=REPO/'reproduction/synthetic/source'
    modules={}
    for name in ('spatial','geometry_plan','generator','controls_campaign'):
        spec=importlib.util.spec_from_file_location(name,source/(name+'.py'))
        module=importlib.util.module_from_spec(spec);sys.modules[name]=module
        spec.loader.exec_module(module);modules[name]=module
    return modules

class Geometry:
    """Exact q=2 rectangle primitive, vectorized in extended precision."""
    def masses(self,xy,rect,scale,q):
        if q!=2 or scale<=0:raise ValueError('Only the fixed q=2 law is supported')
        xy=np.asarray(xy,dtype=np.longdouble).reshape(-1,2)
        r=np.asarray(rect,dtype=np.longdouble);ss=np.longdouble(scale)**2
        x0=r[None,:,0]-xy[:,None,0];x1=r[None,:,1]-xy[:,None,0]
        y0=r[None,:,2]-xy[:,None,1];y1=r[None,:,3]-xy[:,None,1]
        def fx(x):
            v=np.sqrt(ss+x*x);return x/v*np.arctan2(v*(y1-y0),v*v+y0*y1)
        def fy(y):
            v=np.sqrt(ss+y*y);return y/v*np.arctan2(v*(x1-x0),v*v+x0*x1)
        out=np.asarray(ss/2*(fx(x1)-fx(x0)+fy(y1)-fy(y0)),dtype=float)
        if np.any(out<=0)or not np.isfinite(out).all():raise ArithmeticError('Invalid rectangle mass')
        return out

def temporal(lag,logc,p):
    c=math.exp(logc);safe=np.maximum(lag,0.);v=np.log1p(safe/c)
    k=(p-1)/c*np.exp(-p*v)*(lag>0)
    return k,k*(-1+p*safe/(c+safe)),k*(1/(p-1)-v)

def exposure(lo,hi,logc,p):
    c=math.exp(logc);l=np.log1p(lo/c);h=np.log1p(hi/c)
    sl=np.exp((1-p)*l);sh=np.exp((1-p)*h)
    value=sl*(-np.expm1((1-p)*np.log1p((hi-lo)/(c+lo))))
    return value,(p-1)*(lo/(c+lo)*sl-hi/(c+hi)*sh),-l*sl+h*sh

def background_exposure(a,d,start,end,T0):
    half=(end-start)/T0;center=(start+end)/T0-1;z=d*half
    if abs(z)<1e-5:s=1+z*z/6+z**4/120;ds=half*(z/3-z**3/45)
    else:s=math.sinh(z)/z;ds=half*(1/math.tanh(z)-1/z)
    value=math.exp(a+d*center)*(end-start)*s
    return value,value*(center+ds)

class Native:
    def __init__(self,path):
        self.lib=C.CDLL(str(Path(path).resolve()))
        self.ptr=np.ctypeslib.ndpointer(dtype=np.float64,flags='C_CONTIGUOUS')
        self.lib.joint_integral.argtypes=[C.c_int]*4+[self.ptr]*9+[C.c_double,self.ptr]
        self.lib.joint_integral.restype=C.c_int;self.lib.joint_error.restype=C.c_char_p
    def integrate(self,pt,marks,r2,area,b,t,w,h,theta,T0):
        ns,np_=r2.shape;nt=len(t);inclusive=h is not None
        if h is None:h=np.zeros(1)
        values=[np.ascontiguousarray(v,dtype=float)for v in (pt,marks,r2,area,b,t,w,h,theta)]
        out=np.zeros(9)
        # Nine input pointers; keep the explicit ABI independent of platform.
        if self.lib.joint_integral(ns,np_,nt,int(inclusive),*values,T0,out):
            raise ArithmeticError(self.lib.joint_error().decode())
        return out

class Phase:
    def __init__(self,arrays,meta,modules,native=None,deadline=math.inf):
        self.a=arrays;self.m=meta;self.modules=modules;self.native=native;self.deadline=deadline
        self.lag=arrays['event_time'][:,None]-arrays['parent_time'][None,:]
        self.event_r2=((arrays['event_xy'][:,None,:]-arrays['parent_xy'][None,:,:])**2).sum(axis=2)
        self.M=float(len(arrays['event_time'])*np.log(meta['beta'])-meta['beta']*arrays['event_excess'].sum())
        self._plans=None;self._grids={};self._temporal={};self.evaluations=0
    def check(self):
        if time.monotonic()>=self.deadline:raise TimeoutError('Joint experiment deadline')
    def baseline(self,theta):
        a,d,n,logc,p=theta[:5];a0=self.a;m=self.m
        ks=temporal(self.lag,logc,p)
        hp=[(v*a0['parent_fertility'][None,:]*a0['event_parent_density']).sum(axis=1)for v in ks]
        js=exposure(a0['parent_exposure_lo'],a0['parent_exposure_hi'],logc,p)
        jj=np.array([v@a0['parent_fertility']for v in js])
        B,Bd=background_exposure(a,d,m['start'],m['end'],m['T0'])
        E=B+n*jj[0];grad=np.array([B,Bd,jj[0],n*jj[1],n*jj[2],0.,0.,0.])
        return hp,E,grad
    def plan(self,order):
        self.check()
        if order not in (8,16):raise ValueError('Frozen spatial order8 or16 required')
        if self._plans is None:
            a=self.a;m=self.m
            pa=dict(rectangles=a['rectangles'],reference_pi=a['reference_pi'],kde_xy=a['kde_training_xy'],
                    kde_weight=a['kde_weight'],kde_normalizer=a['kde_normalizers'],parent_xy=a['parent_xy'])
            self._plans,self.plan_info=self.modules['geometry_plan']._adaptive_area_space(pa,m,[8,16],1e-8,20)
        if order not in self._grids:
            a=self.a;m=self.m;plan=self._plans[order]
            xy=plan['space_xy'];b,cells=self.modules['controls_campaign'].background(xy,a,m)
            t,w=self.modules['controls_campaign'].time_plan(a['parent_time'],m['start'],m['end'],.0001,8*order)
            estimate=24*len(xy)*len(a['parent_time'])+xy.nbytes+3*len(t)*len(a['parent_time'])*8+256*len(t)*3*8
            if estimate>2*1024**3:raise MemoryError('Per-phase estimated arrays exceed2GiB')
            r2=np.empty((len(xy),len(a['parent_time'])))
            for j in range(0,len(xy),256):r2[j:j+256]=((xy[j:j+256,None,:]-a['parent_xy'][None,:,:])**2).sum(axis=2)
            rho=a['reference_pi'][cells]/a['cell_areas'][cells]
            coeff=np.exp(-2*np.log1p(r2/m['sigma']**2))*rho[:,None]*a['parent_fertility'][None,:]/a['parent_normalizer'][None,:]
            self._grids[order]=dict(r2=r2,coeff=coeff,b=b,area=plan['space_weight']/b,t=t,w=w,
                                    estimate=estimate,space_nodes=len(xy),time_nodes=len(t),parents=len(a['parent_time']))
        return self._grids[order]
    def deficit(self,theta,model,order):
        if self.native is None:raise ValueError('Native integral required for inhibited law')
        grid=self.plan(order);t=grid['t'];inclusive=model=='LIplus_inclusive'
        plus=model!='LI';marks=np.exp((.75*math.log(10)if plus else 0)*self.a['parent_excess'])
        key=(order,float(theta[3]),float(theta[4]))
        if inclusive:
            if self._temporal.get('key')!=key:
                lag=t[:,None]-self.a['parent_time'][None,:]
                self._temporal=dict(key=key,value=np.concatenate([v.T for v in temporal(lag,theta[3],theta[4])],axis=1))
            temporal_fields=self._temporal['value']
        total=np.zeros(9)
        for start in range(0,len(grid['b']),256):
            self.check();sl=slice(start,start+256)
            h=np.ascontiguousarray(grid['coeff'][sl]@temporal_fields)if inclusive else None
            total+=self.native.integrate(self.a['parent_time'],marks,grid['r2'][sl],grid['area'][sl],grid['b'][sl],t,grid['w'],h,theta,self.m['T0'])
        return total
    def evaluate(self,theta,model='null',order=8,require_gradient=True):
        self.check();theta=np.asarray(theta,dtype=float)
        if theta.shape!=(8,)or not np.isfinite(theta).all():raise ValueError('Eight finite coordinates required')
        self.evaluations+=1
        hp,E,eg=self.baseline(theta);a,d,n,_,_,eta,logell,logpsi=theta
        x=self.a['event_x'];logB=a+d*x+np.log(self.a['event_background_density'])
        H=hp[0];logH=np.full(len(H),-np.inf)
        if n>0:np.log(n*H,out=logH,where=H>0)
        G=L=Q=np.zeros(len(H))
        if model!='null':
            ell=math.exp(logell);psi=math.exp(logpsi);r=self.event_r2/(ell*ell)
            z=np.maximum(self.lag,0)/psi;gamma=.75*math.log(10)if model!='LI'else 0
            terms=np.exp(gamma*self.a['parent_excess'][None,:]-z)/(1+r)**2*(self.lag>0)
            G=terms.sum(axis=1);L=(terms*4*r/(1+r)).sum(axis=1);Q=(terms*z).sum(axis=1)
        inclusive=model=='LIplus_inclusive'
        basepoint=np.logaddexp(logB,logH)
        point=basepoint-eta*G if inclusive else np.logaddexp(logB-eta*G,logH)
        if model=='null':point=np.logaddexp(logB,logH)
        fraction=np.exp(logB-basepoint)if inclusive else np.exp(logB-eta*G-point)
        if model=='null':fraction=np.exp(logB-point)
        denominator=basepoint if inclusive else point
        ratio=np.zeros(len(H));rawlog=np.zeros(len(H));np.log(H,out=rawlog,where=H>0)
        with np.errstate(over='ignore',invalid='ignore'):
            np.exp(rawlog-denominator,out=ratio,where=H>0)
        trigger_fraction=np.zeros(len(H))
        if n>0:np.exp(logH-denominator,out=trigger_fraction,where=H>0)
        c_ratio=np.divide(hp[1],H,out=np.zeros(len(H)),where=H>0)
        p_ratio=np.divide(hp[2],H,out=np.zeros(len(H)),where=H>0)
        pg=np.array([fraction.sum(),(x*fraction).sum(),ratio.sum(),
                     (trigger_fraction*c_ratio).sum(),(trigger_fraction*p_ratio).sum(),0.,0.,0.])
        if model!='null':
            f=np.ones(len(H))if inclusive else fraction
            pg[5:]=[-(G*f).sum(),-(eta*L*f).sum(),-(eta*Q*f).sum()]
            deficit=self.deficit(theta,model,order);E-=deficit[0];eg-=deficit[1:]
        P=float(point.sum());joint=P-E+self.M;gradient=eg-pg
        if not all(math.isfinite(v)for v in(P,E,joint))or E< -1e-9:
            raise ArithmeticError('Nonfinite or negative full exposure')
        if require_gradient and not np.isfinite(gradient).all():raise ArithmeticError('Finite objective has unrepresentable gradient')
        return dict(P=P,E=float(E),C=-float(E),M=self.M,joint=joint,nll=-joint),gradient

def phase_from_rows(rows,gm,start,end,modules,native,deadline=math.inf):
    m=dict(start=start,end=end,T0=760,beta=gm['beta'],sigma=gm['sigma_km'],bg_floor=gm['bg_floor'],kde_h=gm['kde_h']or 10)
    arrays=modules['controls_campaign'].canonical_arrays(rows[:,0],rows[:,1:3],rows[:,3],np.asarray(gm['rectangles']),
       np.asarray(gm['reference_pi']),np.asarray(gm['kde_xy']).reshape(-1,2),np.asarray(gm['kde_weight']),m,
       [math.log(.2),.2,.35,math.log(.05),1.3],Geometry())
    return Phase(arrays,m,modules,native,deadline)
