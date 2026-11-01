# Continuously kernel-matched inhibition

This extension retains nine Stage A cases: three chronological primary windows, three constant-background restrictions, and three post-1980 training windows. The three variants reuse the same 612 test events. They are separate sensitivity analyses, not 1,836 independent observations. Magnitude productivity remains fixed at r=0.7; a common training-only conditional-bin beta is used within each case. Only triggering is replaced by Omori. Every stress history uses the pinned 195-mode, unit-scale ML survival law.

For lag u>0, define k(u)=(p-1)c^-1(1+u/c)^(-p) and S(u)=(1+u/c)^(1-p). Both c>0 and p>1 guarantee a nonnegative unit-integral kernel. With s=log(c), A(u)=log1p(u/c), and v=u/(c+u),

    d_s log k = -1+p*v
    d_p log k = 1/(p-1)-A
    d_s S = (p-1)*v*S
    d_p S = -A*S.

The finite-window parent exposure is J=S(L)-S(U), L=max(window_start-parent_time,0), U=window_end-parent_time, with parents strictly before the window end. Its derivatives are the same endpoint differences. Stable evaluation uses S(L)*[-expm1((1-p)*(A(U)-A(L)))]. No lag truncation is permitted. The finite bounds c in [0.0001,20] days and p in [1.01,2.5] are exploratory restrictions: the lower c is 8.64 seconds and p near one permits extremely long tails. A boundary estimate does not identify a physical duration; bounds will not expand after outcomes.

Let H=sum_j kappa_j k(t-t_j), kappa=(1-r)exp(r beta Q), and B=exp(a+d*x-eta*R), where R is either raw G or its training-only residual. Then lambda=B+nH and

    NLL = integral B + n sum_j kappa_j J_j - sum_i log(lambda_i).
    grad_a = integral B - sum_i B_i/lambda_i
    grad_d = integral xB - sum_i x_i B_i/lambda_i
    grad_n = sum_j kappa_j J_j - sum_i H_i/lambda_i
    grad_eta = -integral RB + sum_i R_i B_i/lambda_i
    grad_s = n sum_j kappa_j d_s J_j - sum_i n d_s H_i/lambda_i
    grad_p = n sum_j kappa_j d_p J_j - sum_i n d_p H_i/lambda_i.

Magnitude likelihood is added separately and has no derivative in these coordinates because beta is fixed from training. Stress G and its projection coefficients have NO derivatives in s,p: their ML law is unchanged. At n=0 the Omori coordinates have exactly zero gradient. At eta=0, matched inhibitory models reproduce the E-selected Omori model exactly. The ML baseline is a distinct temporal family, sharing only the Poisson boundary.

On the exact training order-16 Gauss-Legendre exposure grid, normalize weights to sum one. Write mx=sum(w*x), mG=sum(w*G), Vx=sum(w*(x-mx)^2), and CxG=sum(w*(x-mx)*(G-mG)). Set gamma1=CxG/Vx, gamma0=mG-gamma1*mx. Then R=G-gamma0-gamma1*x has weighted means sum(wR)=sum(wxR)=0 up to the frozen numerical tolerance. Vx must exceed 1e-14. The coefficients are reused without refitting on test windows and order-32 verification grids. This is exposure orthogonality, not likelihood-score orthogonality: the latter also depends on intensity weights and excitation nuisance scores.

The exact unrestricted parameter mapping is

    a_tilde=a-eta*gamma0, d_tilde=d-eta*gamma1;
    a=a_tilde+eta*gamma0, d=d_tilde+eta*gamma1.

Thus orthogonalization alone cannot improve the unrestricted family. Identical numerical boxes on raw and residual coordinates induce different physical domains. Constant raw d=0 and constant residual d_tilde=0 are different restrictions. An eta-only ridge is invariant under this coordinate change and does not by itself remove confounding. Every selected raw/orth parameter tuple must have its mapped feasibility and active boundaries reported. A mapped floor is retained only when exactly feasible; clipping would change its intensity and is forbidden. Raw and column-scaled Gram conditioning are reported separately; decorrelating G from the exposure basis need not improve every condition number or statistical identification.

The primary kernel-matched contrasts use one E_omori training-selected (c,p), shared exactly with Iraw_matched and Iorth_matched. The jointly refitted Iorth_joint is secondary and cannot replace these matched tests. A sealed Stage A coarse E point is reevaluated as a training floor within the continuous family, without refitting old runs or reusing their scores. Joint I additionally retains the selected matched orthogonal model as an exact floor. All models receive eight prospective starts and exact Poisson/nested floors; selection is training-only. Near-optimal candidates within 0.0004 training NLL must have test spread below 0.01 nats per event.

Synthetic laws are fixed in protocol.json before generation. Raw inhibition may recover between events as stress decays; its current intensity is not a valid monotone waiting envelope. The valid envelope is mu+nH, whose cumulative hazard has exact Omori survival differences. Independent time and mark streams, rejection records, caps, and no replacement histories are mandatory. Original raw inhibited truth maps to orthogonal truth only when all mapped bounds and the free-d restriction permit it. A selected matched kernel generally differs from the generating kernel; no invalid truth-containment witness is imposed on it.

Historical Iteration 27 Omori scores are descriptive only: their nuisance estimation and, in Fold 0, productivity ratio differ. No old authority is refitted. Timing, mark, and joint score differences must be reported separately with event plus compensator reconciliation. Predictive score changes are not physical causality evidence.
