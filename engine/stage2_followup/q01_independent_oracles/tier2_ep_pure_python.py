"""Mandated pure-Python full84 EP oracle. No Q01/production DLL calls.
Independent positive angular mass quadrature and tail-safe incomplete-beta line
integrals, with independently adaptive refinement. Statistical orchestration
from the historical independently authored OC oracle; free-q geometry derived here.
"""
from __future__ import annotations
from functools import lru_cache
import math
import numpy as np
from scipy.integrate import quad


SCALARS = ('count','exposure','immigrant_exposure','trigger_exposure',
 'count_minus_exposure','time_event_logsum','timing_logscore',
 'location_logscore','mark_logscore','joint_logscore','zone_logscore',
 'cell_given_zone_logscore','within_cell_density_logscore',
 'subblock_balance_max','gap_ks','gap_serial','censored_tail',
 'spatial_rosenblatt_ks_max','spatial_rosenblatt_cross_abs',
 'cell_mass_residual_max','location_dimensionless_log_mean',
 'location_dimensionless_log_variance','within_cell_dimensionless_absmax',
 'within_cell_dimensionless_sum')
ARRAYS5 = ('year_count','year_exposure','year_count_minus_exposure')
ARRAYS9 = ('cell_count','cell_conditional_expected','cell_exposure',
 'cell_count_minus_conditional_expected','cell_count_minus_exposure')
DETAIL = ('gap','Ugap','Ux','Uy','logground','logpoint','logcell',
          'logzone','logmark','ell','w')


def require(test, code):
    if not bool(test):
        raise ValueError(code)


def _array(value, columns, code):
    out = np.asarray(value, dtype=np.float64)
    require(out.ndim == 2 and out.shape[1] == columns
            and np.isfinite(out).all(), code)
    return out


@lru_cache(maxsize=8)
def _legendre(order):
    return np.polynomial.legendre.leggauss(order)


def _angle_width(lower, upper, root):
    """Positive atan(upper/root)-atan(lower/root), without subtraction."""
    value = np.arctan2((upper-lower)*root, root*root+lower*upper)
    return np.where(value < 0, value+math.pi, value)


def _delta_minus_sin(delta):
    d2 = delta*delta
    small = delta*d2*(1/6-d2/120+d2*d2/5040-d2*d2*d2/362880)
    return np.where(np.abs(delta) < .01, small, delta-np.sin(delta))


def _line_q2(lower, upper, horizontal, scale):
    """Integral in y of K_s at fixed x-offset; all integrands positive.

    For A=1+(x/s)^2, y=s*sqrt(A)*tan(theta), the integral is
    s*A^-3/2 * integral cos(theta)^2 dtheta. Its symmetric-angle form
    avoids subtracting saturated arctangent primitives in the far tail.
    """
    lo, hi, x = np.broadcast_arrays(np.asarray(lower)/scale,
                                    np.asarray(upper)/scale,
                                    np.asarray(horizontal)/scale)
    A = 1+x*x
    root = np.sqrt(A)
    delta = _angle_width(lo, hi, root)
    hyp = np.hypot(root, lo)
    c0, s0 = root/hyp, lo/hyp
    half = delta/2
    cm = c0*np.cos(half)-s0*np.sin(half)
    sm = s0*np.cos(half)+c0*np.sin(half)
    dm = _delta_minus_sin(delta)
    angular = .5*(cm*cm*(2*delta-dm)+sm*sm*dm)
    value = scale*angular/(A*root)
    return np.where(hi > lo, value, 0.)



def line_integral(lower,upper,horizontal,scale,q=2.):
    if q==2:return _line_q2(lower,upper,horizontal,scale)
    from scipy.special import betainc,beta
    lo,hi,x=np.broadcast_arrays(np.asarray(lower,float),np.asarray(upper,float),np.asarray(horizontal,float))
    A=1+(x/scale)**2;root=scale*np.sqrt(A);a=lo/root;b=hi/root;constant=.5*beta(.5,q-.5)
    def central(v):return constant*betainc(.5,q-.5,v*v/(1+v*v))
    def tail(v):return constant*betainc(q-.5,.5,1/(1+v*v))
    def positive(l,u):
        l,u=np.broadcast_arrays(np.asarray(l,float),np.asarray(u,float))
        below=u<=1;above=l>=1
        result=np.where(below,central(u)-central(l),np.where(above,tail(l)-tail(u),central(np.ones_like(l))-central(l)+tail(np.ones_like(l))-tail(u)))
        # Positive direct quadrature for narrow intervals avoids subtraction
        # cancellation in either beta primitive. This is independent of DLLs.
        narrow=(u-l)<=1e-6*np.maximum(1,l)
        if np.any(narrow):
            z,w=_legendre(32);mid=(l[narrow]+u[narrow])/2;half=(u[narrow]-l[narrow])/2
            result[narrow]=half*np.sum(w*(1+(mid[...,None]+half[...,None]*z)**2)**(-q),axis=-1)
        return result
    left=np.maximum(a,0);right=np.maximum(b,0)
    pp=positive(left,right);nn=positive(np.maximum(-b,0),np.maximum(-a,0))
    value=scale*A**(.5-q)*np.where(a>=0,pp,np.where(b<=0,nn,central(-a)+central(b)))
    return np.where(hi>lo,value,0.)

def _mass_order(bounds, centers, scale, order, q=2.):
    """Vectorized positive two-angle rectangle integral with feature splits."""
    xl,xh,yl,yh = np.moveaxis(bounds, -1, 0)
    px,py = np.moveaxis(centers, -1, 0)
    lo,hi = (xl-px)/scale,(xh-px)/scale
    bot,top = (yl-py)/scale,(yh-py)/scale
    valid = (xh > xl) & (yh > yl)
    width = _angle_width(lo, hi, np.ones_like(lo))
    # Explicitly resolve the origin and both vertical-distance transitions.
    critical1 = np.hypot(1., bot)
    critical2 = np.hypot(1., top)
    def offset(cut):
        clipped=np.clip(cut,lo,hi)
        return _angle_width(lo,clipped,np.ones_like(lo))
    # All angular coordinates are local offsets from atan(lo). Adding a tiny
    # interval width to an absolute angle near pi/2 can erase the interval.
    cuts = np.stack([np.zeros_like(lo),
        offset(-critical1),offset(-critical2),offset(np.zeros_like(lo)),
        offset(critical1),offset(critical2),width],-1)
    cuts.sort(axis=-1)
    nodes,weights = _legendre(order)
    total = np.zeros_like(lo)
    # Six vectorized segments; there is no per-center Python quadrature loop.
    for seg in range(cuts.shape[-1]-1):
        start, stop = cuts[...,seg], cuts[...,seg+1]
        span = stop-start
        delta = start[...,None]+span[...,None]*(nodes+1)/2
        # cos(theta) can lose relative precision near pi/2. Reconstruct from
        # the known left endpoint ratio and a small angular increment.
        h0 = np.hypot(1.,lo)
        cs = (np.cos(delta)-lo[...,None]*np.sin(delta))/h0[...,None]
        sn = (lo[...,None]*np.cos(delta)+np.sin(delta))/h0[...,None]
        xn = sn/cs
        inner = line_integral(bot[...,None]*scale, top[...,None]*scale,
                              xn*scale, scale,q=q)/scale
        integrand = inner/(cs*cs)
        total += span/2*np.sum(integrand*weights,axis=-1)
    return np.where(valid, scale*scale*total, 0.)


def _adaptive_mass_one(bounds, center, scale,q=2.):
    """Independent adaptive outer quadrature, feature-aware; private scalar."""
    xl,xh,yl,yh = map(float,bounds); px,py = map(float,center)
    if xh <= xl or yh <= yl:
        return 0.
    lower,upper = (xl-px)/scale,(xh-px)/scale
    cuts = {lower,upper}
    for transition in (0.,1.,math.hypot(1.,(yl-py)/scale),
                       math.hypot(1.,(yh-py)/scale)):
        for sign in (-1.,1.):
            cut = sign*transition
            if lower < cut < upper:
                cuts.add(cut)
    # theta integration resolves a narrow kernel even in very large cells.
    edges = [float(_angle_width(lower,x,1.)) for x in sorted(cuts)]
    hyp=math.hypot(1.,lower)
    def positive(delta):
        cosine=(math.cos(delta)-lower*math.sin(delta))/hyp
        sine=(lower*math.cos(delta)+math.sin(delta))/hyp
        return float(line_integral(yl-py,yh-py,
                     scale*sine/cosine,scale,q=q))/scale/(cosine*cosine)
    value=math.fsum(quad(positive,a,b,epsabs=1e-13/max(1,len(edges)-1),
                       epsrel=2e-12,limit=150)[0]
                    for a,b in zip(edges[:-1],edges[1:]))*scale*scale
    require(value > 0 and math.isfinite(value),'ADAPTIVE_RECTANGLE_FAILURE')
    return value


def rectangle_mass(bounds, centers, scale, *, q=2.,verify=False):
    """Broadcast rectangle/center arrays and independently refine if needed.

    Orders 24/48 plus feature-aware 96 refinement are not accepted simply
    because two raw orders agree: normalized geometry checks and adaptive
    spot controls are required by controls.py. verify=True adaptively checks
    every rectangle and is intended for the bounded synthetic fixtures.
    """
    bounds,centers = np.asarray(bounds,float),np.asarray(centers,float)
    shape=np.broadcast_shapes(bounds.shape[:-1],centers.shape[:-1])
    b=np.broadcast_to(bounds,shape+(4,)); p=np.broadcast_to(centers,shape+(2,))
    require(math.isfinite(scale) and scale > 0 and np.isfinite(b).all()
            and np.isfinite(p).all(),'SPATIAL_INPUT_DOMAIN')
    v0=_mass_order(b,p,scale,24,q)
    v1=_mass_order(b,p,scale,48,q)
    threshold=2e-11*np.abs(v1)+1e-15*scale*scale
    refine=np.abs(v0-v1)>threshold
    if np.any(refine):
        refined=_mass_order(b[refine],p[refine],scale,96,q)
        old=v1[refine].copy();v1[refine]=refined
        unresolved=np.abs(refined-old)>2e-11*np.abs(refined)+1e-15*scale*scale
        where=np.flatnonzero(refine)
        for flat in where[unresolved]:
            v1.flat[flat]=_adaptive_mass_one(b.reshape(-1,4)[flat],
                                           p.reshape(-1,2)[flat],scale,q)
    if verify:
        for flat in range(v1.size):
            expected=_adaptive_mass_one(b.reshape(-1,4)[flat],
                                        p.reshape(-1,2)[flat],scale,q)
            require(abs(float(v1.flat[flat])-expected)
                    <=2e-10*abs(expected)+1e-14*scale*scale,
                    'INDEPENDENT_ADAPTIVE_RECTANGLE_MISMATCH')
    positive=(b[...,1]>b[...,0])&(b[...,3]>b[...,2])
    require(np.all(v1[positive]>0) and np.isfinite(v1).all(),
            'POSITIVE_RECTANGLE_MASS_FAILURE')
    return v1


def immigrant_integral(a,d,lower,upper,T0):
    lower,upper=np.broadcast_arrays(np.asarray(lower,float),np.asarray(upper,float))
    dt=upper-lower
    # expm1(x)/x avoids cancellation at a flat immigrant trend.
    x=2*d*dt/T0
    ratio=np.ones_like(x)
    np.divide(np.expm1(x),x,out=ratio,where=x!=0)
    value=dt*np.exp(a+d*(2*lower/T0-1))*ratio
    require(np.all(value>=0) and np.isfinite(value).all(),'IMMIGRANT_INTEGRAL')
    return value


def omori_interval(lower,upper,c,p):
    lo,hi=np.broadcast_arrays(np.asarray(lower,float),np.asarray(upper,float))
    require(np.all(lo>=0) and np.all(hi>=lo) and c>0 and p>1,
            'OMORI_INTERVAL_DOMAIN')
    survival=np.exp((1-p)*np.log1p(lo/c))
    return survival*(-np.expm1((1-p)*np.log1p((hi-lo)/(c+lo))))


def labels(points,rectangles):
    points=np.asarray(points,float);r=np.asarray(rectangles,float)
    valid=((points[:,None,0]>=r[None,:,0])&(points[:,None,0]<=r[None,:,1])
           &(points[:,None,1]>=r[None,:,2])&(points[:,None,1]<=r[None,:,3]))
    require(np.all(valid.any(axis=1)),'POINT_OUTSIDE_OMEGA')
    return np.max(np.where(valid,np.arange(9)[None,:],-1),axis=1)


def validate_state(state):
    pars=np.asarray(state['params'],float)
    require(pars.shape==(11,) and np.isfinite(pars).all(),'PARAMETER_SHAPE')
    a,d,n,c,p,s,h,beta,T0,start,end=pars
    require(n>=0 and c>0 and p>1 and s>0 and h>0 and beta>0
            and T0>0 and end>=start,'PARAMETER_DOMAIN')
    rect=_array(state['rectangles'],4,'RECTANGLE_SHAPE')
    require(rect.shape==(9,4) and np.all(rect[:,1]>rect[:,0])
            and np.all(rect[:,3]>rect[:,2]),'RECTANGLE_DOMAIN')
    xe=np.unique(rect[:,:2]);ye=np.unique(rect[:,2:])
    require(len(xe)==4 and len(ye)==4,'NINE_CELL_CARTESIAN_EDGE_COUNT')
    canonical=np.array([[xe[j],xe[j+1],ye[i],ye[i+1]]
                         for i in range(3) for j in range(3)])
    require(np.array_equal(rect,canonical),'NINE_CELL_CARTESIAN_ORDER_OR_OVERLAP')
    pi=np.asarray(state['pi'],float)
    require(pi.shape==(9,) and np.all(pi>0) and abs(pi.sum()-1)<1e-12,
            'REFERENCE_MASS_DOMAIN')
    train=_array(state['training_xy'],2,'TRAINING_SHAPE')
    require(len(train)>0,'EMPTY_TRAINING_BACKGROUND')
    labels(train,rect)
    pre=_array(state['prehistory'],4,'PREHISTORY_SHAPE')
    require(np.all(pre[:,0]<start) and np.all(pre[:,1]>=0)
            and np.all(np.diff(pre[:,0])>=0),'PREHISTORY_CHRONOLOGY')
    labels(pre[:,2:],rect)
    blocks=np.asarray(state['subblocks'],float)
    require(blocks.shape==(6,) and blocks[0]==start and blocks[-1]==end
            and np.all(np.diff(blocks)>0),'SUBBLOCK_DOMAIN')
    return pars,rect,pi,train,pre,blocks


class Geometry:
    """Q01 EP geometry from raw rows, pure Python/NumPy/SciPy positive integrals."""
    def __init__(self,rect,pi,train,parents,scale,bandwidth,q):
        self.rect,self.pi,self.train,self.parents=rect,pi,train,parents
        self.scale,self.bandwidth,self.q=scale,bandwidth,q
        self.area=(rect[:,1]-rect[:,0])*(rect[:,3]-rect[:,2]);self.rho=pi/self.area
        self.pm=rectangle_mass(rect[None,:,:],parents[:,None,:],scale,q=q)
        self.pz=self.pm.sum(axis=1);self.pc=self.pm/self.pz[:,None]
        self.tm=rectangle_mass(rect[None,:,:],train[:,None,:],bandwidth,q=2)
        self.tz=self.tm.sum(axis=1);self.bc=.05*pi+.95*np.mean(self.tm/self.tz[:,None],axis=0)
        require(np.all(self.pz>0) and np.all(self.tz>0) and np.max(abs(self.pc.sum(axis=1)-1),initial=0)<1e-10 and abs(self.bc.sum()-1)<1e-10,'NORMALIZED_INDEPENDENT_EP_GEOMETRY')
    def point(self,points,cells):
        dr2=np.sum((points[:,None,:]-self.parents[None,:,:])**2,axis=-1)
        offspring=np.exp(-self.q*np.log1p(dr2/self.scale**2))/self.pz[None,:]
        dr2=np.sum((points[:,None,:]-self.train[None,:,:])**2,axis=-1)
        bg=.05*self.rho[cells]+.95*np.mean((1+dr2/self.bandwidth**2)**-2/self.tz[None,:],axis=1)
        return offspring,bg
    def cdf_batch(self,points,mu,weights):
        r=self.rect;rho=self.rho;count=len(points);x=points[:,0];y=points[:,1]
        # Contiguous Cartesian domain, independently validated before this class.
        whole=np.array([r[0,0],r[2,1],r[0,2],r[6,3]])
        left=np.repeat(whole[None,:],count,axis=0);left[:,1]=x
        parent_x=rectangle_mass(left[:,None,:],self.parents[None,:,:],self.scale,q=self.q)/self.pz[None,:]
        train_x=rectangle_mass(left[:,None,:],self.train[None,:,:],self.bandwidth,q=2)/self.tz[None,:]
        clip=np.maximum(0,np.minimum(x[:,None],r[None,:,1])-r[None,:,0])
        floor_x=np.sum(clip*(r[None,:,3]-r[None,:,2])*rho[None,:],axis=1)
        numerator_x=mu*(.05*floor_x+.95*np.mean(train_x,axis=1))+np.sum(weights*parent_x,axis=1)
        ground=mu+weights.sum(axis=1)
        active=(x[:,None]>=r[None,:,0])&(x[:,None]<=r[None,:,1])
        for col in range(2):active[x==r[col,1],col::3]=False
        lower=r[None,:,2];upper=np.maximum(lower,np.minimum(r[None,:,3],y[:,None]))
        floor_full=np.sum(active*(r[None,:,3]-lower)*rho[None,:],axis=1)
        floor_partial=np.sum(active*(upper-lower)*rho[None,:],axis=1)
        def cross(centers,scale,q,normalizer):
            dx=x[:,None]-centers[None,:,0];lo=whole[2]-centers[None,:,1];hi=whole[3]-centers[None,:,1];part=y[:,None]-centers[None,:,1]
            full=line_integral(lo,hi,dx,scale,q=q)/normalizer[None,:]
            below=line_integral(lo,part,dx,scale,q=q)/normalizer[None,:]
            return full,below
        pf,py=cross(self.parents,self.scale,self.q,self.pz);tf,ty=cross(self.train,self.bandwidth,2,self.tz)
        denominator=mu*(.05*floor_full+.95*np.mean(tf,axis=1))+np.sum(weights*pf,axis=1)
        numerator=mu*(.05*floor_partial+.95*np.mean(ty,axis=1))+np.sum(weights*py,axis=1)
        ux,uy=numerator_x/ground,numerator/denominator
        require(np.isfinite(ux).all() and np.isfinite(uy).all() and np.all((ux>=-1e-10)&(ux<=1+1e-10)) and np.all((uy>=-1e-10)&(uy<=1+1e-10)),'INDEPENDENT_EP_CDF_DOMAIN')
        return ux,uy

def ks_uniform(values):
    values=np.sort(np.asarray(values,float));n=len(values)
    if not n:return 0.
    return float(max(np.max(np.arange(1,n+1)/n-values),
                     np.max(values-np.arange(n)/n)))


def evaluate(state,events,*,batch_size=4):
    """Return private stats and event details; caller exports scalar allowlist."""
    full=np.asarray(state['params'],float);require(full.shape==(12,) and full[11]>1,'EP_Q_DOMAIN');spatial_q=float(full[11]);pars,rect,pi,train,pre,blocks=validate_state(dict(state,params=full[:11]))
    a,d,n,c,p,scale,h,beta,T0,start,end=pars
    events=_array(events,4,'EVENT_SHAPE')
    require(np.all(np.diff(events[:,0])>=0) and np.all(events[:,0]>=start)
            and np.all(events[:,0]<end) and np.all(events[:,1]>=0),
            'EVENT_CHRONOLOGY')
    N=len(events);cells=labels(events[:,2:],rect)
    parents=np.vstack((pre,events));tp=parents[:,0];qp=parents[:,1]
    fert=.3*np.exp(.7*beta*qp)
    require(np.isfinite(fert).all(),'PRODUCTIVITY_NONFINITE')
    geo=Geometry(rect,pi,train,parents[:,2:],scale,h,spatial_q)
    def exposure(lo,hi):
        valid=tp<hi
        J=omori_interval(np.maximum(lo-tp[valid],0),hi-tp[valid],c,p)
        bg=float(immigrant_integral(a,d,lo,hi,T0))
        offspring=n*fert[valid]*J
        return bg+float(np.sum(offspring)),bg,bg*geo.bc+offspring@geo.pc[valid]
    E,B,Ec=exposure(start,end)
    detail=np.empty((N,11));cell_expected=np.zeros(9)
    for begin in range(0,N,batch_size):
        stop=min(N,begin+batch_size);te=events[begin:stop,0]
        point=events[begin:stop,2:];ci=cells[begin:stop]
        lag=te[:,None]-tp[None,:]
        temporal=np.zeros_like(lag);valid=lag>0
        temporal[valid]=(p-1)/c*np.exp(-p*np.log1p(lag[valid]/c))
        weighted=n*temporal*fert[None,:]
        mu=np.exp(a+d*(2*te/T0-1));ground=mu+weighted.sum(axis=1)
        spat,bg=geo.point(point,ci)
        point_rate=mu*bg+np.sum(weighted*spat,axis=1)
        cell_rate=mu[:,None]*geo.bc[None,:]+weighted@geo.pc
        zone_rate=cell_rate.reshape(-1,3,3).sum(axis=2)
        rows=np.arange(stop-begin)
        cp=cell_rate[rows,ci];zp=zone_rate[rows,ci//3]
        require(np.all(point_rate>0) and np.all(ground>0)
                and np.all(cp>0) and np.all(zp>0),'POSITIVE_EVENT_INTENSITY')
        lg,lp,lc,lz=map(np.log,(ground,point_rate,cp,zp))
        ux,uy=geo.cdf_batch(point,mu,weighted)
        logmark=math.log(beta)-beta*events[begin:stop,1]
        ell=lp-lg+math.log(float(geo.area.sum()))
        w=lp-lc+np.log(geo.area[ci])
        detail[begin:stop,2:]=np.column_stack((ux,uy,lg,lp,lc,lz,logmark,ell,w))
        cell_expected+=np.sum(cell_rate/ground[:,None],axis=0)
    previous=start
    for i,time in enumerate(events[:,0]):
        gap,_,_=exposure(previous,float(time));detail[i,0]=gap
        detail[i,1]=-math.expm1(-gap);previous=float(time)
    tail,_,_=exposure(previous,end)
    require(abs(float(detail[:,0].sum())+tail-E)<=1e-10*max(1.,E),
            'GAP_CENSORED_EXPOSURE_IDENTITY')
    yc=[];ye=[]
    for lo,hi in zip(blocks[:-1],blocks[1:]):
        yc.append(int(np.count_nonzero((events[:,0]>=lo)&(events[:,0]<hi))))
        ye.append(exposure(lo,hi)[0])
    yc,ye=np.asarray(yc),np.asarray(ye)
    require(yc.sum()==N and abs(ye.sum()-E)<=1e-10*max(1.,E)
            and abs(Ec.sum()-E)<=1e-10*max(1.,E)
            and abs(cell_expected.sum()-N)<=1e-10*max(1,N),
            'COUNT_SPATIAL_SUBBLOCK_MASS_IDENTITY')
    cc=np.bincount(cells,minlength=9)
    Sg=float(detail[:,4].sum());loc=float((detail[:,5]-detail[:,4]).sum())
    mark=float(detail[:,8].sum());timing=Sg-E
    stats=dict(count=N,exposure=E,immigrant_exposure=B,trigger_exposure=E-B,
      count_minus_exposure=N-E,time_event_logsum=Sg,timing_logscore=timing,
      location_logscore=loc,mark_logscore=mark,joint_logscore=timing+loc+mark,
      zone_logscore=float((detail[:,7]-detail[:,4]).sum()),
      cell_given_zone_logscore=float((detail[:,6]-detail[:,7]).sum()),
      within_cell_density_logscore=float((detail[:,5]-detail[:,6]).sum()),
      subblock_balance_max=float(np.max(abs(yc-ye)/(1+ye))),
      gap_ks=ks_uniform(detail[:,1]),
      gap_serial=float(np.mean((detail[1:,1]-.5)*(detail[:-1,1]-.5))) if N>1 else 0.,
      censored_tail=tail,
      spatial_rosenblatt_ks_max=max(ks_uniform(detail[:,2]),ks_uniform(detail[:,3])),
      spatial_rosenblatt_cross_abs=abs(float(np.mean((detail[:,2]-.5)*(detail[:,3]-.5)))) if N else 0.,
      cell_mass_residual_max=float(np.max(abs(cc-cell_expected)/(1+cell_expected))),
      location_dimensionless_log_mean=float(np.mean(detail[:,9])) if N else 0.,
      location_dimensionless_log_variance=float(np.var(detail[:,9])) if N else 0.,
      within_cell_dimensionless_absmax=float(np.max(abs(detail[:,10]))) if N else 0.,
      within_cell_dimensionless_sum=float(detail[:,10].sum()),
      year_count=yc.tolist(),year_exposure=ye.tolist(),
      year_count_minus_exposure=(yc-ye).tolist(),cell_count=cc.tolist(),
      cell_conditional_expected=cell_expected.tolist(),cell_exposure=Ec.tolist(),
      cell_count_minus_conditional_expected=(cc-cell_expected).tolist(),
      cell_count_minus_exposure=(cc-Ec).tolist())
    require(set(stats)==set(SCALARS+ARRAYS5+ARRAYS9)
            and all(np.isfinite(v).all() for v in map(np.asarray,stats.values())),
            'COMPLETE_FINITE_SCALAR_VECTOR')
    return stats,detail
