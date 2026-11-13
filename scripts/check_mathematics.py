#!/usr/bin/env python3
"""Deterministic checks of the v3 referee objections.

No catalogue fitting, process simulation, bootstrap, manuscript edit, or
historical result regeneration is performed. Outputs are written beside this
script, unless --output is supplied. Dependencies: mpmath, sympy, numpy, scipy.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import math
import platform
from pathlib import Path
import mpmath as mp
import numpy as np
import scipy
from scipy.integrate import quad
import sympy as sp


def exact_transform_check() -> dict:
    # Scalar symbols represent Laplace transforms of causal kernels/measures.
    # The same computation is valid in the locally integrable causal convolution
    # algebra; no stationary or infinite-history assertion is being made.
    ph, h, gamma, n, m1, x0, rho, s, ng, nk, psi = sp.symbols(
        'ph h gamma n m1 x0 rho s ng nk psi')
    R = ph / (1 - n*h + gamma*ph)
    Q = R * (1 - n*h)
    X = (x0 + rho/s)*ph - ph*ng
    lam = psi + h*nk
    mg = ng - m1*lam
    mk = nk - n*lam
    rhs = (x0+rho/s)*Q + R*(gamma*X-m1*psi) - Q*mg - m1*R*h*mk
    residual = sp.factor(sp.cancel(rhs-X))
    relation_1 = sp.factor(sp.cancel(Q + gamma*R*ph - ph))
    relation_2 = sp.factor(sp.cancel(Q + n*R*h - R))
    assert residual == 0 and relation_1 == 0 and relation_2 == 0
    wrong_rhs = (x0+rho/s)*ph + R*(gamma*X-m1*psi) - Q*mg - m1*R*h*mk
    wrong_residual = sp.factor(sp.cancel(wrong_rhs-X))
    assert sp.cancel(wrong_residual-(x0+rho/s)*gamma*R*ph) == 0
    return {
        'equation_3_13_residual': str(residual),
        'Q_plus_gamma_R_Phi_minus_Phi': str(relation_1),
        'Q_plus_n_R_h_minus_R': str(relation_2),
        'reviewer_Phi_substitution_error': str(wrong_residual),
        'interpretation': 'Exact scalar convolution algebra, not a stochastic existence proof.'
    }


def fractional_no_event_check() -> dict:
    mp.mp.dps = 55
    root1 = (-1 + mp.sqrt(3)*1j)/2
    root2 = mp.conj(root1)
    def R(t):
        # Inverse Laplace of 1/(s + sqrt(s) + 1), via partial fractions in sqrt(s).
        if t == 0:
            return mp.mpf(1)
        def E(root):
            return mp.exp(root*root*t) * mp.erfc(-root*mp.sqrt(t))
        return mp.re((root1*E(root1)-root2*E(root2))/(root1-root2))
    def phi(t):
        return mp.exp(t)*mp.erfc(mp.sqrt(t))
    def iphi(t):
        return phi(t) - 1 + 2*mp.sqrt(t/mp.pi)
    def X(t):
        return phi(t) + iphi(t)
    out=[]
    for t in map(mp.mpf, ['0.1','0.5','1']):
        rq = R(t)
        ir = mp.quad(R, [0,t])
        # No jumps is not a zero compensated martingale:
        # dM_g=-lambda dt=-X dt for n=0, m1=1, Psi(X)=X on this path.
        compensator_term = mp.quad(lambda u: R(t-u)*X(u), [0,t])
        actual=X(t)
        full_rhs=rq+ir+compensator_term
        inv_R=mp.invertlaplace(lambda z: 1/(z+mp.sqrt(z)+1),t,method='dehoog')
        assert abs(inv_R-rq)<mp.mpf('1e-42')
        assert abs(full_rhs-actual)<mp.mpf('1e-42')
        out.append({
            't':float(t), 'Phi':mp.nstr(phi(t),40),
            'integral_Phi':mp.nstr(iphi(t),40), 'Q_equals_R':mp.nstr(rq,40),
            'integral_Q':mp.nstr(ir,40), 'actual_X':mp.nstr(actual,40),
            'rhs_with_martingale_term_omitted':mp.nstr(rq+ir,40),
            'omitted_compensator_contribution':mp.nstr(compensator_term,40),
            'full_rhs':mp.nstr(full_rhs,40), 'absolute_residual':mp.nstr(abs(full_rhs-actual),10),
            'wrong_Phi_replacement_full_rhs':mp.nstr(actual+compensator_term,40),
            'R_closed_form_vs_inverse_laplace_abs_error':mp.nstr(abs(inv_R-rq),10)
        })
    return {'parameters': {'n':0,'m1':1,'ell':1,'gamma':1,'alpha':0.5,'tau':1,'X0':1,'rho':1},
            'checks':out,
            'scope':'Chosen deterministic no-event path. The linear link is only needed along its positive stress range; it may be extended positively outside that range.'}


def product_derivative_checks() -> dict:
    # Chosen deterministic event histories, not simulated catalogues.
    times=np.array([0.15,0.40,0.75])
    marks_g=np.array([50.0,4.0,0.2])
    marks_k=np.array([2.0,1.0,3.0])
    T=1.0
    Bbar=1.125
    def B(t): return 1.0+0.25*t
    def history(t):
        idx=times<t
        lags=t-times[idx]
        return (float(np.dot(marks_g[idx],np.exp(-1.3*lags))),
                float(np.dot(marks_k[idx],0.9*np.exp(-0.9*lags))))
    G=np.array([history(t)[0] for t in times])
    H=np.array([history(t)[1] for t in times])
    Bi=1+0.25*times
    cuts=[0.0,*times,T]
    def integ(f):
        return sum(quad(f,l,r,epsabs=1e-12,epsrel=1e-12)[0] for l,r in zip(cuts[:-1],cuts[1:]))
    def calc(eta,n):
        J=integ(lambda t: B(t)*(-math.expm1(-eta*history(t)[0])))
        Jp=integ(lambda t: B(t)*history(t)[0]*math.exp(-eta*history(t)[0]))
        ref=Bi+n*H
        ratios=(Bi*np.exp(-eta*G)+n*H)/ref
        ratios_p=-Bi*G*np.exp(-eta*G)/ref
        product=float(np.prod(ratios))
        deriv=math.exp(J)*(Jp*product+sum(float(ratios_p[i]*np.prod(np.delete(ratios,i))) for i in range(len(times))))
        return math.exp(J)*product, deriv
    out=[]
    for n in [0.0,0.4]:
        for eta in [0.3,1.0,2.0]:
            eta_min=eta/2
            value,deriv=calc(eta,n)
            dx=1e-5
            fd=(calc(eta+dx,n)[0]-calc(eta-dx,n)[0])/(2*dx)
            envelope=math.exp(Bbar)*(Bbar+len(times))/(math.e*eta_min)
            assert abs(deriv)<=envelope
            assert math.isclose(deriv,fd,rel_tol=2e-6,abs_tol=2e-9)
            out.append({'n':n,'eta':eta,'L':value,'direct_product_derivative':deriv,
                        'central_finite_difference':fd,'claimed_uniform_envelope':envelope,
                        'envelope_pass':True})
    return {'cases':out, 'single_factor_example': {
        'B':1,'triggering':0,'G':100,'eta':1,
        'absolute_log_factor_derivative':100,
        'absolute_factor_derivative':100*math.exp(-100),
        'one_over_e_eta':1/math.e,
        'explanation':'The large log derivative is not the derivative of the likelihood factor.'}}


def paired_mcse_checks() -> list:
    out=[]
    for positive,negative in [(29,21),(61,6)]:
        N=150
        mean=(positive-negative)/N
        q=positive+negative
        sum_centered=q-N*mean*mean
        sample_se=math.sqrt(sum_centered/(N*(N-1)))
        plugin_se=math.sqrt(sum_centered/(N*N))
        mcnemar_null_se=math.sqrt(q)/N
        out.append({'N':N,'positive_discordances':positive,'negative_discordances':negative,
                    'mean_difference_pp':100*mean,
                    'sample_variance_mcse_pp':100*sample_se,
                    'plugin_mcse_pp':100*plugin_se,
                    'mcnemar_null_se_pp':100*mcnemar_null_se})
    return out


def visibility_bound_check() -> dict:
    """Evaluate Proposition 4.4 on the frozen NZ reference background.

    Integrate the *implemented* positive 195-mode mixture, independently of
    engine imports. Two changes of variables check the quadrature. The mark
    moment uses g(q)=exp(gamma*(q-1)) and kappa(q)=(1-r)*exp(beta*r*q).
    """
    root = Path(__file__).resolve().parents[1]
    source = root / 'validation/authorities/4761702854830904_reference_score_geometry.json'
    reference = json.loads(source.read_text(encoding='utf-8'))
    pars, kernel = reference['generating_pars'], reference['stress_kernel']
    T = float(reference['input_paths'][0]['horizon'])
    a, d, n, beta, ratio = (pars[k] for k in ('a', 'd', 'n', 'beta', 'ratio'))
    alpha, tau, step, tail = (kernel[k] for k in ('alpha', 'tau', 'spectral_step', 'spectral_tail_bound'))
    half_count = math.ceil(max(math.log(4)/alpha,
        math.log(4*math.sin(math.pi*alpha)/(math.pi*alpha)/tail)/alpha)/step)
    nodes = np.arange(-half_count, half_count+1)*step
    rates = np.exp(nodes)/tau
    weights = step*math.sin(math.pi*alpha)/(2*math.pi*(np.cosh(alpha*nodes)+math.cos(math.pi*alpha)))
    weights[[0, -1]] *= .5
    weights /= weights.sum()
    assert len(rates) == 195 and np.all(weights > 0)

    def integrand(u):
        decay = np.exp(-rates*u)
        phi = float(weights@decay)
        h = float((weights*rates)@decay)
        return phi*phi/h

    C, error = quad(lambda v: integrand(math.expm1(v))*math.exp(v),
                    0., math.log1p(T), epsabs=1e-5, epsrel=1e-11)
    cuts = [0., *np.geomspace(1e-12, T, 70)]
    direct = sum(quad(integrand, left, right, epsabs=1e-7, epsrel=1e-11)[0]
                 for left, right in zip(cuts[:-1], cuts[1:]))
    assert math.isclose(C, direct, rel_tol=1e-10)
    asymptotic = tau**alpha*T**(2-alpha)/(alpha*(2-alpha)*math.gamma(1-alpha))
    gamma = .75*math.log(10)
    moment_denominator = beta*(1+ratio)-2*gamma
    assert moment_denominator > 0
    moment = math.exp(-2*gamma)*beta/((1-ratio)*moment_denominator)
    background_mass = T*math.exp(a)*(math.sinh(d)/d if d else 1.)
    background_max = math.exp(a+abs(d))
    K = background_max**2*C*moment*background_mass/(n*(1-n))
    pinsker_coefficient = math.sqrt(K/2)
    threshold = 1/pinsker_coefficient
    # Tightened bound: retain B(t) >= B_min > 0 in the denominator.  The
    # direct single-parent quadrature uses the normalized offset
    # B_min/B_max^2, so the eta-dependent integral is
    #   C_T^tight = int_0^T Phi(u)^2 / (B_min/B_max^2 + n h_e(u)) du.
    background_min = math.exp(a-abs(d))
    offset = background_min/background_max**2
    def tight_integrand(u):
        decay = np.exp(-rates*u)
        phi = float(weights@decay)
        h = float((weights*rates)@decay)
        return phi*phi/(offset+n*h)
    tight, tight_error = quad(lambda v: tight_integrand(math.expm1(v))*math.exp(v),
                              0., math.log1p(T), epsabs=1e-10, epsrel=1e-12)
    tight_cuts = [0., *np.geomspace(1e-12, T, 90)]
    tight_direct = sum(quad(tight_integrand, left, right, epsabs=1e-10, epsrel=1e-12)[0]
                       for left, right in zip(tight_cuts[:-1], tight_cuts[1:]))
    assert math.isclose(tight, tight_direct, rel_tol=1e-9)
    K_tight = K*tight/C
    tight_coefficient = math.sqrt(K_tight/2)
    tight_threshold = 1/tight_coefficient
    assert math.isclose(C, 2866250.949255799, rel_tol=1e-9)
    assert math.isclose(moment, .216065146328062, rel_tol=1e-12)
    assert math.isclose(background_mass, 383.349580803454, rel_tol=1e-12)
    assert math.isclose(K, 366444.657016935, rel_tol=1e-9)
    assert math.isclose(background_min, 0.012348494430127546, rel_tol=1e-12)
    assert math.isclose(offset, 32.00110702437131, rel_tol=1e-12)
    assert math.isclose(tight, 0.10424014954814537, rel_tol=1e-8)
    assert math.isclose(K_tight, 0.0133269, rel_tol=1e-4)
    assert math.isclose(tight_threshold, 12.2504, rel_tol=1e-4)
    assert all(min(1., eta*pinsker_coefficient) == 1. for eta in (.10, 1.65))
    assert all(min(1., eta*tight_coefficient) < 1. for eta in (.10, 1.65))
    return {
        'source': str(source.relative_to(root)).replace('\\', '/'),
        'source_sha256': hashlib.sha256(source.read_bytes()).hexdigest(),
        'parameters': {'T_days': T, 'alpha': alpha, 'tau_days': tau,
                       'a': a, 'd': d, 'n': n, 'beta': beta, 'r': ratio},
        'mixture_modes': len(rates), 'C_T_195_days_squared': C,
        'C_T_195_direct_partition_check': direct, 'quadrature_error_estimate': error,
        'C_T_asymptotic_days_squared': asymptotic,
        'E_g_squared_over_kappa': moment, 'background_mass': background_mass,
        'background_max_per_day': background_max, 'K_T': K,
        'sqrt_K_T_over_2': pinsker_coefficient,
        'eta_at_which_clipped_bound_equals_one': threshold,
        'bound_for_eta_0_10': min(1., .10*pinsker_coefficient),
        'bound_for_eta_1_65': min(1., 1.65*pinsker_coefficient),
        'background_min_per_day': background_min,
        'B_min_over_B_max_squared': offset,
        'C_T_tight_days_squared': tight,
        'C_T_tight_direct_partition_check': tight_direct,
        'C_T_tight_quadrature_error_estimate': tight_error,
        'C_T_reduction_factor': C/tight,
        'K_T_tight': K_tight,
        'sqrt_K_T_tight_over_2': tight_coefficient,
        'eta_tight_at_which_clipped_bound_equals_one': tight_threshold,
        'tight_bound_for_eta_0_10': min(1., .10*tight_coefficient),
        'tight_bound_for_eta_0_178': min(1., .178*tight_coefficient),
        'tight_bound_for_eta_1_65': min(1., 1.65*tight_coefficient),
        'passed': True,
    }


def continuous_time_interpolation_check() -> dict:
    """Check the scalar constants in the explicit weak-Harris extension.

    This checks algebra, not construction of a Markov coupling. The proof in
    Chapter 3 supplies the coupling and its first-moment drift estimates.
    """
    b, k, v = sp.symbols('b k v', positive=True)
    residual = sp.expand((1+2*b*k)*(1+b*v)-(1+b*v+2*b*k))
    assert residual == 2*b*b*k*v
    # E sqrt(d*weight) <= sqrt(E d * E weight), then compare the
    # resulting pointwise bound with sqrt(d0*(1+beta*(V+V'))).
    rates = np.exp(np.arange(-97, 98)*.4)
    minimum_rate = float(rates[0])
    minimum_time = math.log(4)/minimum_rate
    slow_modes = int(np.count_nonzero(-np.expm1(-rates*24394.) < .01))
    assert math.isclose(math.log(minimum_rate), -38.8, abs_tol=1e-13)
    assert math.isclose(minimum_time, 9.8283667623941e16, rel_tol=1e-12)
    assert slow_modes == 61
    return {'residual_time_d_cost_factor_upper': 1.25,
            'residual_time_weight_factor_upper': '1+2*beta*D/kappa_V',
            'C0': 'sqrt((5/4)*(1+2*beta*D/kappa_V))',
            'nonnegative_comparison_residual': str(residual),
            'r': '-log(alpha_tilde)/t0',
            'skeleton_to_continuous_prefactor': 'C0/alpha_tilde',
            'mixture_modes': len(rates),
            'minimum_log_rate_per_day': math.log(minimum_rate),
            'minimum_rate_per_day': minimum_rate,
            'minimum_coupling_time_days': minimum_time,
            'horizon_days': 24394.,
            'modes_decaying_less_than_one_percent': slow_modes,
            'passed': True}


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--output',type=Path,default=Path(__file__).with_name('check_results.json'))
    args=ap.parse_args()
    beta=2.849401764894274
    r=0.7
    gamma=0.75*math.log(10)
    result={
        'scope':'Deterministic algebra, quadrature, and arithmetic. No manuscript edits or scientific campaign runs.',
        'versions':{'python':platform.python_version(),'mpmath':mp.__version__,'sympy':sp.__version__,'numpy':np.__version__,'scipy':scipy.__version__},
        'exact_transform_algebra':exact_transform_check(),
        'fractional_no_event':fractional_no_event_check(),
        'likelihood_product_derivative':product_derivative_checks(),
        'paired_mcse':paired_mcse_checks(),
        'finite_horizon_visibility': visibility_bound_check(),
        'continuous_time_interpolation_constants': continuous_time_interpolation_check(),
        'reviewer_alternative_envelope_moment':{
            'beta':beta,'r':r,'gamma':gamma,'gamma_plus_r_beta':gamma+r*beta,
            'Eg_finite':gamma<beta,'Ekappa_finite':r<1,
            'Eg_kappa_finite':gamma+r*beta<beta,
            'reason':'E[g*kappa] diverges under the declared synthetic exponential-mark law. Under the noninhibited Hawkes law, immigrant-to-direct-child contributions can therefore make E sum_i G(T_i-) infinite despite finite mean counts and first mark moments.'
        }
    }
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(result,indent=2))

if __name__=='__main__':
    main()
