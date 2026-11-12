"""Independent gradient, regional-mass and nested-floor numerical controls."""
import argparse,json,sys
from pathlib import Path
import numpy as np
from scipy.integrate import dblquad
from scipy.optimize._numdiff import approx_derivative
from threadpoolctl import threadpool_limits
sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
from experiments.etas_inhibition_benchmark.run_frozen_20261111 import Region,Background,Model,write

def run():
    region=Region(np.array([[0.,100.,0.,100.]]));xy=np.array([[20.,20.],[45.,40.],[60.,60.]]);t=np.array([1.,3.,7.])
    a=dict(parent_time=t,parent_excess=np.array([.1,.5,1.]),parent_xy=xy,parent_fertility=np.array([.3,.5,.8]),parent_exposure_lo=np.zeros(3),parent_exposure_hi=10-t,event_time=t,event_xy=xy)
    m=dict(start=0.,end=10.,T0=10.,training_start=0.);b=Background(xy,region,5);model=Model(a,m,b)
    x=np.array([-2.,.1,.5,np.log(.1),1.3,np.log(5.),.5,1.7,.2,np.log(20.),np.log(5.),1.]);model.node_setup(x,10)
    value,gradient=model.objective(x,True);fd=approx_derivative(lambda v:model.objective(v,True)[0],x,method='3-point').ravel();err=float(np.max(np.abs(gradient-fd)))
    # Cartesian adaptive integral has no polar rays or corner-angle machinery.
    masses=[]
    for point,s,q in [(xy[0],5.,1.7),(np.array([.001,99.999]),2.,1.05),(xy[1],40.,3.)]:
        f=lambda yy,xx:(q-1)/(np.pi*s*s)*(1+((xx-point[0])**2+(yy-point[1])**2)/(s*s))**(-q)
        expected,error=dblquad(f,0,100,lambda _:0,lambda _:100,epsabs=1e-9,epsrel=1e-9)
        actual=region.mass(region.radii(point[None,:],64),np.array([s]),q)[0][0]
        masses.append(dict(actual=float(actual),cartesian_reference=float(expected),reference_error=float(error),absolute_error=float(abs(actual-expected))))
    floor=x.copy();floor[8]=0;fv,fg=model.objective(floor,True);nv,ng=model.objective(floor,False)
    rows=[]
    for seed in range(20261140,20261144):
        model.node_setup(x,16,seed);rows.append(model.objective(x,True,True))
    return dict(passed=err<1e-6 and max(v['absolute_error'] for v in masses)<1e-8 and abs(fv-nv)<1e-12 and float(np.max(abs(fg[:8]-ng[:8])))<1e-12,
        gradient_max_absolute_error=err,analytic_gradient=gradient.tolist(),finite_difference_gradient=fd.tolist(),mass_controls=masses,nested_floor_objective_error=float(abs(fv-nv)),nested_floor_nuisance_gradient_error=float(np.max(abs(fg[:8]-ng[:8]))),importance_integration_replicates=rows)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    with threadpool_limits(limits=1):r=run()
    write(a.output,r);print(json.dumps(r));raise SystemExit(0 if r['passed'] else 1)
