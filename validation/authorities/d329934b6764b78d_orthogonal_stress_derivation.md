# Exposure-orthogonal stress depletion: derivation and prospective diagnostic contract

Status: mathematical derivation with independently audited empirical Gram diagnostics appended below.

## Projection and its exact scope

On the frozen training order-16 quadrature grid let q_l>0 be exposure weights and w_l=q_l/sum(q). The original unnormalized exposure inner product differs only by a positive scalar and has identical OLS coefficients. For x_l=2t_l/T0-1 and G_l computed using only strict prior events, define m_x=sum w x, m_G=sum w G, V_x=sum w(x-m_x)^2, C_xG=sum w(x-m_x)(G-m_G). Provided V_x>0,

    gamma1=C_xG/V_x; gamma0=m_G-gamma1*m_x;
    R(t)=G_perp(t)=G(t)-gamma0-gamma1*x(t).

Then sum w R=m_G-gamma0-gamma1*m_x=0. Also sum w x R=C_xG-gamma1*V_x+m_x*sum w R=0. These identities are exact algebraically on the discrete exposure measure; floating-point residuals are checked relative to feature scales. A positive constant rescaling of q has no effect. A singular V_x invalidates a two-coordinate projection. A zero residual variance means G is redundant with the exposure basis and must be reported explicitly.

Gamma is training-only and frozen for BOTH train/test, all five models, and order-32 checks. Recomputing gamma at order 32 changes the model, rather than isolating quadrature error. Strict pre-event history applies to target events; interior quadrature nodes use all prior parents and never future events. Pre-window history is retained.

## Coordinate mapping and constrained-family interpretation

For any real a,d,eta,

    a+d*x-eta*G = atilde+dtilde*x-eta*R,
    atilde=a-eta*gamma0; dtilde=d-eta*gamma1,
    a=atilde+eta*gamma0; d=dtilde+eta*gamma1.

The mapping is bijective for fixed eta,gamma and holds at every future t when gamma is frozen. Hence unrestricted raw and orthogonal likelihood families are identical, including test predictions. An eta-only ridge lambda_eta*eta^2/2 is unchanged by this mapping, and cannot distinguish them. Our bounded coordinate boxes [-12,0] on intercept and [-2,2] on trend are different admissible families after mapping. Their predictive comparison tests these fitting restrictions. In the constant-background variant raw d=0 and orthogonal dtilde=0 are distinct restrictions. Mapped candidates are exact floors only when destination boxes and fixed coordinates are satisfied; clipping breaks equality.

R can be negative. Therefore a signed R is required in the inhibitory evaluator, although raw G and H remain nonnegative. Negative R can locally enhance the orthogonal background relative to exp(atilde+dtilde*x); eta>=0 is not pointwise suppression of this detrended baseline everywhere. No physical inhibition conclusion follows from the name or score.

This is exposure orthogonality, not general likelihood-score orthogonality. With B=exp(atilde+dtilde*x-eta*R) and lambda=B+nH, score features contain B/lambda. Expected information for background coordinates includes weighting B^2/lambda, which is not the uniform time-exposure measure. Projection onto [1,x] also does not remove association with the n score.

## Likelihood and analytic gradients

Fix r=.7 and common training beta. Define kappa_j=(1-r)*exp(beta*r*Q_j), H(t)=sum_{tj<t} kappa_j*k(t-tj), and J=sum_j kappa_j*int_window k(t-tj)dt, with each parent exposure integrated only after its time. Stress is G(t)=sum_{tj<t} exp((.75*log(10))*(Q_j-1))*S_ml(t-tj). Stress is unchanged when the excitation kernel becomes Omori.

For event i set lambda_i=B_i+nH_i. The timing NLL is

    L=sum_l q_l B_l+nJ-sum_i log(lambda_i).

The independent mark NLL is -N*log(beta)+beta*sum_i Q_i, common to all five models. For parameter vector theta=(atilde,dtilde,n,eta),

    dL/datilde = sum_l q_l B_l - sum_i B_i/lambda_i;
    dL/ddtilde = sum_l q_l x_l B_l - sum_i x_i B_i/lambda_i;
    dL/dn = J - sum_i H_i/lambda_i;
    dL/deta = -sum_l q_l R_l B_l + sum_i R_i B_i/lambda_i.

For raw inhibition substitute G for R and raw a,d. E0 has eta=0 exactly and must share event/exposure arrays and nuisance; its stress gradient need not vanish but its value and remaining-coordinate gradients nest exactly. At n=0 the n derivative is still well-defined because B>0; use H/lambda directly rather than log(n). A fixed d is removed from optimization but its full-vector derivative may be saved diagnostically. Central differences apply only at interior feasible coordinates; use feasible one-sided differences at bounds.

For E0 the background integral may be analytic. If inhibitory eta=0 uses quadrature, exact algebraic nesting still has integration roundoff/order error; production should use the same integration branch at the boundary or explicitly gate the discrepancy at the prescribed tolerance. The raw oracle must independently reconstruct both.

## Omori normalization and exact excitation exposure

For c>0,p>1,

    k(u)=(p-1)/c*(1+u/c)^(-p), u>=0;
    S(u)=(1+u/c)^(1-p), S(0)=1, S(infinity)=0.

Thus integral_0^infinity k=1. A parent with lag bounds L=max(start-tj,0),U=max(end-tj,0) contributes kappa_j*(S(L)-S(U)), zero if U=L. Compute stably as S(L)*[-expm1((1-p)*(log1p(U/c)-log1p(L/c)))]. Narrow excitation peaks must not be integrated with a coarse exposure quadrature. The original finite-mixture ML has the analogous exact sum over w_m exp(-rate_m*L)*[-expm1(-rate_m*(U-L))].

Only the nine-point training E0 grid c={.1,1,10}, p={1.1,1.3,1.7} is used. The chosen pair is frozen for both final Omori models. These are fixed-kernel four-coordinate evaluator gradients, not derivatives through training selection.

## Gram diagnostics: prospective saved-output schema

For each of all nine training cases save unnormalized grid identities, gamma, residual moments/scales, residual variance and weighted Gram matrices A_raw=Z_raw' W Z_raw, A_orth=Z_orth' W Z_orth, with Z_raw=[1,x,G], Z_orth=[1,x,R]. Save ordered eigenvalues, raw 2-norm condition numbers and unit-column-normalized Gram condition numbers. Orthogonality makes A_orth block diagonal between [1,x] and R, but does not guarantee a lower raw condition number: residual variance can be arbitrarily tiny. Infinite/singular conditions are represented by explicit flags and JSON null values, not invalid JSON Infinity. A zero column cannot be unit-normalized; report that fact. Primary three-prefix diagnostics are prominently tabulated, with constant-background/post-1980 cases retained.

The empirical table below was independently reconstructed from raw rows after fitting; the original prospective note remains immutable in methods/.

## Synthetic generator envelope proof

For the frozen synthetic raw law eta>=0 and G>=0. Thus exp(a+d*x-eta*G)<=mu_max=exp(a+abs(d)) on x in[-1,1]. On each accepted-history interval M(t)=mu_max+nH_ml(t) dominates the actual conditional intensity. Its cumulative hazard from clock s to s+u is mu_max*u+n*sum_j kappa_j*(S_ml(s-tj)-S_ml(s+u-tj)). It is continuous and strictly increasing since mu_max>0. Inverting an independent Exp(1) variate samples the next proposal of the dominating inhomogeneous process; accepting with lambda/M yields the intended conditional intensity. Rejections do not create parents. New accepted events update both H and G. Under frozen d=eta=0, lambda=M and every proposal accepts. This avoids the impractical bound based on a large finite-mixture instantaneous k(0). Root failures, cap hits and insufficient event counts fail engineering eligibility; no jitter, replacement or omitted modes are permitted.

## Scientific reporting

For candidate minus baseline use E=sum log(lambda_c/lambda_b), C=int(lambda_b-lambda_c), Delta=E+C. Common mark scores cancel. Report event-weighted sums separately per variant, with the same612 held-out events reused across variants. Fold0 rescue is relative to the newly recomputed matched raw ML baseline; historical -16.99 nats remains contextual unless its nuisance/optimizer identity is reconciled. Controls establish implementation behavior, not power, parameter consistency or physical stress causation.


## Primary exposure geometry

| Fold | Gamma0 | Gamma1 | Raw Gram condition | Orth Gram condition | Raw column-scaled condition | Orth column-scaled condition |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| 0 | 1.47359235 | 1.29677131 | 137.804559 | 19.2814701 | 124.155962 | 13.9282032 |
| 1 | 1.75302961 | 1.72100946 | 101.246757 | 9.22421294 | 58.8177208 | 5.29026344 |
| 2 | 1.81932899 | 1.85676582 | 108.420677 | 5.16990623 | 44.7086122 | 2.3187293 |
