import numpy as np
import math,sys
def _adaptive_area_space(a,m,orders,tol,near_width):
    """Geometry-only positive quadrature; indicators require NLL validation."""
    import heapq
    rules={n:np.polynomial.legendre.leggauss(n) for n in set(orders)|{8,16}}
    rect=a['rectangles'];area=(rect[:,1]-rect[:,0])*(rect[:,3]-rect[:,2])
    coeff=(1-m['bg_floor'])*a['kde_weight']/a['kde_normalizer']
    centres=a['kde_xy'];parents=a['parent_xy'];np_=len(parents)
    allsources=np.concatenate([centres,parents])
    h2=m['kde_h']**2
    def exact_mass(r,c):
        xl,xh,yl,yh=r
        px=centres[:,0].astype(np.longdouble);py=centres[:,1].astype(np.longdouble)
        x0=np.longdouble(xl)-px;x1=np.longdouble(xh)-px
        y0=np.longdouble(yl)-py;y1=np.longdouble(yh)-py;ss=np.longdouble(h2)
        def angle(l,h,A):return np.arctan2(A*(h-l),A*A+l*h)
        def fx(x):
            A=np.sqrt(ss+x*x);return x/A*angle(y0,y1,A)
        def fy(y):
            A=np.sqrt(ss+y*y);return y/A*angle(x0,x1,A)
        masses=np.asarray(ss/2*(fx(x1)-fx(x0)+fy(y1)-fy(y0)),float)
        result=m['bg_floor']*a['reference_pi'][c]*(xh-xl)*(yh-yl)/area[c]+float(masses@coeff)
        if not result>0 or not np.isfinite(result):raise FloatingPointError('ADAPTIVE_LEAF_MASS_UNRESOLVED')
        return result
    def sample(r,c,n,mass):
        xl,xh,yl,yh=r;z,w=rules[n]
        X,Y=np.meshgrid((xl+xh)/2+(xh-xl)/2*z,(yl+yh)/2+(yh-yl)/2*z,indexing='ij')
        xy=np.column_stack([X.ravel(),Y.ravel()]);aw=((xh-xl)*(yh-yl)/4*np.outer(w,w)).ravel()
        b=np.full(n*n,m['bg_floor']*a['reference_pi'][c]/area[c])
        for k in range(0,len(coeff),256):
            dx=xy[:,None,0]-centres[None,k:k+256,0];dy=xy[:,None,1]-centres[None,k:k+256,1]
            b+=((1+(dx*dx+dy*dy)/h2)**-2)@coeff[k:k+256]
        weights=aw*b;rawmass=math.fsum(weights)
        if not rawmass>0:raise FloatingPointError('ADAPTIVE_RAW_MASS_ZERO')
        weights*=mass/rawmass
        # Worst allowed spatial scale. Average over every retained parent;
        # no parent is sampled or dropped. Constant mass calibration is applied
        # before inhibition, so attenuation is never renormalized.
        stress=np.zeros(n*n);dell=np.zeros(n*n)
        for k in range(0,np_,256):
            dx=xy[:,None,0]-parents[None,k:k+256,0];dy=xy[:,None,1]-parents[None,k:k+256,1]
            rho=(dx*dx+dy*dy)/25.;one=1+rho
            stress+=(one**-2).sum(axis=1);dell+=(4*rho/one**3).sum(axis=1)
        if np_:stress/=np_;dell/=np_
        # Coordinate moments detect unresolved concentration even where a sum
        # of positive stress proxies happens to agree by cancellation.
        ux=(xy[:,0]-xl)/(xh-xl);uy=(xy[:,1]-yl)/(yh-yl)
        moments=np.array([weights@stress,weights@dell,weights@ux,weights@uy,weights@(ux*ux),weights@(uy*uy)])
        return xy,weights,moments,rawmass
    heap=[];leaves={};serial=0;total=0.
    def add(r,c,depth):
        nonlocal serial,total
        mass=exact_mass(r,c);lo=sample(r,c,8,mass);hi=sample(r,c,16,mass)
        err=max(abs(lo[3]-mass),abs(hi[3]-mass),float(np.max(np.abs(lo[2]-hi[2]))))
        xl,xh,yl,yh=r
        near=np.any((allsources[:,0]>=xl)&(allsources[:,0]<=xh)&(allsources[:,1]>=yl)&(allsources[:,1]<=yh))
        forced=bool(near and max(xh-xl,yh-yl)>near_width)
        serial+=1;key=serial;leaves[key]=(r,c,depth,mass,err,lo,hi);total+=err
        heapq.heappush(heap,(-math.inf if forced else -err,key))
    for c,r in enumerate(rect):add(tuple(r),c,0)
    splits=0
    while heap and (total>tol or heap[0][0]==-math.inf):
        _,key=heapq.heappop(heap)
        r,c,depth,mass,err,lo,hi=leaves.pop(key);total-=err
        if depth>=24:raise FloatingPointError('ADAPTIVE_SPATIAL_DEPTH_UNRESOLVED')
        xl,xh,yl,yh=r
        if xh-xl>=yh-yl:
            mid=(xl+xh)/2;children=((xl,mid,yl,yh),(mid,xh,yl,yh))
        else:
            mid=(yl+yh)/2;children=((xl,xh,yl,mid),(xl,xh,mid,yh))
        for child in children:add(child,c,depth+1)
        splits+=1
        if splits%100==0:pass
        if len(leaves)*max(orders)**2>4_000_000:raise MemoryError('ADAPTIVE_SPATIAL_MEMORY_UNRESOLVED')
    result={}
    for n in orders:
        xy=[];wt=[];sc=[]
        for r,c,depth,mass,err,lo,hi in leaves.values():
            v=lo if n==8 else hi if n==16 else sample(r,c,n,mass)
            xy.append(v[0]);wt.append(v[1]);sc.append(np.full(len(v[1]),c,np.int32))
        result[n]=dict(space_xy=np.ascontiguousarray(np.concatenate(xy)),space_weight=np.ascontiguousarray(np.concatenate(wt)),space_cell=np.concatenate(sc))
    info=dict(leaves=len(leaves),splits=splits,indicator=float(total),tolerance=tol,calibrated_uninhibited_mass=True,proxy_scale=5.,proxy_parent_count=np_)
    return result,info
