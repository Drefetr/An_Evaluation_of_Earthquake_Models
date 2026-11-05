"""Exact constant-background subfamily of the autonomous finite-mode model."""
import hashlib
import importlib.util
import math
from pathlib import Path
import sys
import numpy as np

ROOT=Path(__file__).resolve().parents[2]
GAMMA=.75*math.log(10.)
RATIO=.7
SOURCE_PINS={
    'engine/iteration_27/code/adequacy.py':'9662c90f9ff7e120fe26c1dfc0bd969071f16774feec686b9e97731337e0ff90',
    'engine/iteration_5/code/kernels.py':'3561ef3471adf349caebebc6c2ca12881f2a3d9c7c7415d15453b5be20b978ae',
}


def load_engine():
    for relative,expected in SOURCE_PINS.items():
        if hashlib.sha256((ROOT/relative).read_bytes()).hexdigest()!=expected:raise ValueError('Existing engine source changed: '+relative)
    name='_autonomous_fixed_adequacy'
    if name not in sys.modules:
        spec=importlib.util.spec_from_file_location(name,ROOT/'engine/iteration_27/code/adequacy.py')
        module=importlib.util.module_from_spec(spec);sys.modules[name]=module;spec.loader.exec_module(module)
    return sys.modules[name]


def shared_kernel():
    return load_engine().KernelSpec('ml',1.,alpha=.5,spectral_step=.4,spectral_tail_bound=1e-8)


def mark_weights(excess,beta):
    q=np.asarray(excess,dtype=float)
    if beta<=0 or not math.isfinite(beta) or np.any(q<0) or not np.isfinite(q).all():raise ValueError('Finite nonnegative marks and positive beta required')
    return np.exp(GAMMA*(q-1.)),(1-RATIO)*np.exp(beta*RATIO*q)


def theorem_assumptions(a,n,eta,beta):
    if not all(math.isfinite(x) for x in (a,n,eta,beta)) or not 0<=n<1 or eta<0 or beta<=0:
        raise ValueError('Finite parameters, nonnegative eta, beta>0 and n<1 required')
    finite=eta==0 or beta>GAMMA
    m1=0. if eta==0 else (eta*math.exp(-GAMMA)*beta/(beta-GAMMA) if finite else None)
    representable=m1 is not None and math.isfinite(m1)
    return dict(eligible=finite and representable,m1=m1 if representable else None,
                invoked_result='Chapter 3 finite-mode stability theorem (first moments only)',
                stress_moment_condition='eta=0 or beta>gamma',gamma=GAMMA,beta=beta,
                productivity_mean=n,diagnostic_productivity_mean=1.,subcritical=n<1,
                stress_second_moment_finite=eta==0 or beta>2*GAMMA,
                productivity_second_moment_finite=n==0 or RATIO<.5,
                cross_moment_finite=eta==0 or n==0 or beta*(1-RATIO)>GAMMA,
                higher_moments_required_by_invoked_result=False,
                link_upper_bound=math.exp(a),link_lipschitz_on_reached_halfline=math.exp(a),
                rho=0.,initial_stress=0.,initial_excitation=0.,stationary_initialization=False,
                mark_law_assumption='Fresh iid Exp(beta) excess marks independent of pre-event history; this is a model assumption, not an empirical fact.')


def physical_intensity(query,times,excess,a,n,eta,beta,weights,rates):
    """Solve the declared physical mode equations from zero initial modes."""
    times=np.asarray(times,dtype=float);q=np.asarray(excess,dtype=float)
    weights=np.asarray(weights,dtype=float);rates=np.asarray(rates,dtype=float)
    if not math.isfinite(query) or query<0 or not np.isfinite(times).all():raise ValueError('Finite nonnegative query and times required')
    if times.shape!=q.shape or np.any(np.diff(times)<=0) or np.any(times<0):raise ValueError('Strictly ordered nonnegative history required')
    if weights.shape!=rates.shape or np.any(weights<=0) or np.any(rates<=0) or not np.isclose(weights.sum(),1.,rtol=0,atol=1e-14):raise ValueError('Normalized positive finite mixture required')
    if eta<0 or not 0<=n<1:raise ValueError('Physical jump scales outside domain')
    g,k=mark_weights(q,beta);Z=np.zeros(len(rates));U=np.zeros(len(rates));previous=0.
    for t,gm,kp in zip(times,g,k):
        if t>=query:break
        decay=np.exp(-rates*(t-previous));Z*=decay;U*=decay
        Z-=eta*gm;U+=rates*n*kp;previous=t
    decay=np.exp(-rates*(query-previous));Z*=decay;U*=decay
    X=float(weights@Z);H=float(weights@U)
    return dict(intensity=math.exp(a+X)+H,X=X,H=H,Z=Z,U=U)


def diagnostic_intensity(query,times,excess,a,n,eta,beta,weights,rates):
    """Independent direct sums of shared relaxation and its negative derivative."""
    times=np.asarray(times);q=np.asarray(excess);past=times<query;g,k=mark_weights(q[past],beta)
    lag=query-times[past];decay=np.exp(-lag[:,None]*np.asarray(rates))
    G=float(g@(decay@weights));H=float(k@(decay@(np.asarray(weights)*rates)))
    return math.exp(a-eta*G)+n*H


class ConstantBackgroundObjective:
    """Estimate a,n[,eta]; the affine trend coordinate is fixed exactly to zero."""
    def __init__(self,history,kernel):self.history=history;self.kernel=kernel
    def evaluate(self,parameters,gradient=True):
        p=np.asarray(parameters,dtype=float)
        if p.shape not in ((2,),(3,)):raise ValueError('Expected a,n or a,n,eta')
        full=np.array([p[0],0.,p[1],p[2] if len(p)==3 else 0.])
        # Both arms use identical integration at eta=0, preserving the exact floor.
        result=self.history.objective(full,self.kernel,RATIO,self.kernel,gradient=gradient)
        if not gradient:return result
        value,derivative=result
        return value,derivative[[0,2,3] if len(p)==3 else [0,2]]
