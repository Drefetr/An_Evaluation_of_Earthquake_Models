# Stage B: parent-class Mittag-Leffler scale continuation

Status: prospective mathematical specification. The base three models and optional h branch are fixed before observed fitting. This is the original pooled regional B design; no spatial mixing, inhibition, productivity-law change or new target-class kernel family is introduced.

## Parent-class scale family and finite bounds

Class j is determined by the parent's observed excess magnitude Q: class 0 for 0<=Q<.5 and class 1 for Q>=.5. The shared training-only beta gives p0=-expm1(-beta*.5),p1=exp(-beta*.5). Retain r=.7 and kappa(Q)=.3exp(.7betaQ).

The pinned unit-scale 195-mode ML mixture has positive weights w_m summing to1 and unit rates lambda_m. With s=logtau and a_m=lambda_m exp(-s),

    k_s(u)=sum_m w_m a_m exp(-a_m u), u>=0;
    S_s(u)=sum_m w_m exp(-a_m u).

Each mode integrates to1 after its density factor a_m, so integral_0^infinity k_s=sum_mw_m=1 for every tau>0. Scaling changes rates, never weights or temporal mass. The parent determines which tau_j applies to its entire contribution. This is not a target-class decay model.

Freeze tau in[.001,20]days, optimized as logtau. The lower endpoint is 86.4 seconds and admits subhour scales; the upper is 20 times the retained unit-day reference. This finite approximately 4.3-decade range is a prospective numerical family, not a physical range claim or a truncation of aftershock lags. Long-tail modes and all earlier parents remain even when their ages exceed 20 days. No alternative range or bound expansion follows observed fits. Boundary solutions are bound-limited estimates, not scale-identification certificates or evidence about the value outside the range.

## Dynamic histories, exposure and exact derivatives

Let H_j(t)=sum_{parent k:class_k=j,t_k<t}kappa_k k_{s_j}(t-t_k). Retain strict pre-event history, all pretraining parents, and already observed test events. Frozen test parameters and beta do not prevent predictable history updates.

For a single mode with y=a_m u,

    d[k_s(u)]/ds = sum_m w_m a_m exp(-y)*(y-1).

For a parent with L=max(window_start-t_k,0),U=max(window_end-t_k,0), its unit temporal exposure is

    J_k(s)=sum_m w_m exp(-a_m L)*[-expm1(-a_m*(U-L))].

Its log-scale derivative is

    dJ_k/ds=sum_mw_m[(a_mL)exp(-a_mL)-(a_mU)exp(-a_mU)].

A stable equivalent per-mode expression is exp(-a_mL)*[a_mL*(-expm1(-a_m*(U-L)))-a_m*(U-L)*exp(-a_m*(U-L))]. Multiply J_k and its derivative by the parent's kappa for productivity-weighted compensators. Derivatives with respect to tau equal the log-scale derivatives divided by tau. Lags and bounds, rather than cached kernel values with edited metadata, are the immutable geometry for dynamic tau evaluation. Zero/future lags do not contribute to event intensities. Retain numerical underflow limits as zero contributions; do not clip finite event lags or remove modes.

Write J_j=sum_{parentsclassj}kappa_kJ_k(s_j) and J=J0+J1. Exact parent exposures include all quiet-window exposure and avoid numerically integrating narrow near-parent peaks. The background integral int exp(a+dx), x=2t/T0-1, can be analytic; independently reconstruct the frozen 16/32 Gauss-Legendre grids for the prescribed<=1e-4 NLL quadrature verification. Scaling the trigger does not require approximate quadrature of its density.

## The three base models and exact nesting

E0_tau1 fixes tau0=tau1=1 day. E0_tau_free estimates one common logtau. E1_tau_class estimates logtau0,logtau1 with h=delta=0. All have ground intensity

    Lambda(t)=B(t)+n*(H0(t)+H1(t)), B=exp(a+dx).

At h0 the conditional mark density is exactly f_beta(Q)=beta exp(-betaQ), common to all three models. The class model is a parent-history timing modification; it does not gain a new mark-density parameter. Joint logscore is timing plus this common mark score.

Setting both class scales to 1 recovers the exact fixed baseline. Setting both to the selected common scale recovers the common-free fit. The common-scale gradient equals the sum of the two parent-class log-scale gradients on that diagonal. At n0 the likelihood is independent of either scale and those gradients are exactly zero.

Nine base fit procedures have 72 mandatory starts. Each retains its constant-Poisson floor; common-free also retains the fixed baseline and class-free retains both fixed and common-diagonal completed floors. Every prescribed start must resolve. A floor or finite partial solver return cannot repair an incomplete start.

## Optional h: preserve the original Perron-normalized family

The optional branch fixes delta0 and uses the original transition matrix

    P_ij(h)=(1-h)p_i+h I(i=j),

where i is target class and j is parent class. Bounds h in[-.95min(p0/p1,p1/p0),.95] retain positive class probabilities and exactly include h0. Define class-conditional mean productivity

    m0=[1-exp(-beta(1-r)*c)]/p0, m1=exp(beta*r*c), c=.5.

These satisfy p0m0+p1m1=1. Let A=P diag(m0,m1) and rho be its Perron root. The marked class intensities are

    lambda_i(t)=p_i B(t)+(n/rho)*[P_i0H0(t)+P_i1H1(t)].

This keeps the legacy E1 normalization; do not silently substitute rho1 when h is free. At h0 rho1 and the base class model nests exactly. With unit-integral parent kernels, the normalized class offspring operator has Perron radius n. This is a model normalization, not a guarantee about physical branching or finite-variance inference under the heavy-tailed mark-productivity law.

An explicit derivative check uses U=p1m0+p0m1,V=m0m1,T=p0m0+p1m1+hU,Delta=T^2-4hV:

    rho=(T+sqrt(Delta))/2;
    drho/dh=.5*[U+(T*U-2V)/sqrt(Delta)].

Production may use the original robust 2x2 expression sqrt(Delta)=hypot(A00-A11,2sqrt(A01A10)); the independent oracle can compare trace/determinant/eigen and finite-difference formulas. Rho is independent of tau because both class kernels are normalized. At h0 explicitly preserve exact rho1 nesting while retaining the analytic derivative.

Summing over target classes gives

    Lambda(t)=B(t)+(n/rho(h))*(H0(t)+H1(t)).

Column sums remove P even when the PARENT kernels differ. The association parameter h introduces no additional ground temporal shape: its only direct ground effect at fixed n is the scalar amplitude n/rho. At fixed effective amplitude Gamma=n/rho, timing forecasts and compensators are identical across h. A machine witness should vary n(h)=Gamma*rho(h) only where all points remain feasible. Joint refitting and box constraints can indirectly change timing; this is not a direct association-based timing mechanism.

The conditional mark density for observed class i is [lambda_i/Lambda]*f_beta(Q)/p_i, and the full marked event log intensity is loglambda_i+logf_beta(Q)-logp_i. The h-dependent class allocation can directly affect mark scores. Do not invent target-class kernels to avoid the column-sum result.

## Full NLL gradients

For optional h write Gamma=n/rho, T_i=P_i0H0+P_i1H1 and e_i=p_iB+Gamma T_i at an event of target class i. The joint NLL is

    L=intB+Gamma J-sum_eventslog e_i-sum_events(logf_beta-logp_i).

For all models the nuisance beta,p_i are fixed from training, so their derivatives are not optimized. Let B_d=intxB, and P'_ij=I(i=j)-p_i. Then

    dL/da=intB-sum p_iB/e_i;
    dL/dd=B_d-sum p_i xB/e_i;
    dL/dn=J/rho-sum T_i/(rho e_i);
    dL/ds_j=Gamma*J'_j-sum Gamma*P_ij*H'_j/e_i;
    dL/dh=-Gamma*(rho'/rho)*J
           -sum Gamma*[sum_jP'_ijH_j-(rho'/rho)*T_i]/e_i.

At h0, use the same formulas or the algebraically simplified ground-NLL derivatives; they must agree for shared coordinates. Common logtau has the sum of both class derivatives. At n0 both scale and h gradients vanish exactly. No derivative through class assignment is taken: observed parent classes and the magnitude cutoff are frozen.

## Scores, optimization and gate

For candidate minus baseline, timingDelta=sumlog(Lambda_c/Lambda_b)+int(Lambda_b-Lambda_c)=E_timing+C. JointDelta=timingDelta+markDelta. Alternatively fullmarked event contrasts plus the same regional compensator give jointDelta. Report both and do not label the timing event term as the full marked event term when h is free. Base h0 mark differences cancel exactly; optional h mark differences need not.

Use training joint NLL only, all 8 starts, analytic gradients, L-BFGS-B maxls 200 followed only on failure by bounded Powell from the original prescribed start. Save exact floors, every return and candidate forecast. Near-optimal training candidates within 4e-4 get full held-out scores; spread/Ntest must be strictly below .01 nats/event. Broad parameter support and passing forecast spread do not establish timescale identification.

Optional h may run only after all 9 base procedures/72 starts, complete raw-row audit and forecast stability pass, and class versus common improves held-out TIMING by strictly more than 1e-4 total nats in at least 2 of 3 windows. There is no invented additional aggregate-gain requirement. Protect the declared optional fit and independent-audit reserves. This retrospective held-out gate is adaptive selection; an executed h comparison is not untouched confirmation. The h code/protocol and synthetic engineering are frozen before base observed outcomes. Optional observed execution adds 3 fits/24 starts; a failed gate means notrun, not negative evidence for an unexecuted branch.

## Fixed-seed engineering laws and numerical clocks

The two prospective h=0 synthetic laws are common tau=.02 day and class tau0=.005,tau1=.5day. Both use a=log(.4),d0,n.2,beta 2.85,r.7,T0=horizon 500, train end 350. The 500-day horizon/0.4 daily immigration law was adopted before generation to retain 200 expected immigrants while lowering binary64 clock ULP relative to 5000 days. Absolute tau values, bounds and seeds are unchanged; this is engineering conditioning, not observed data rescaling. Exact time/mark seeds are in protocol.json. All 4 models, including the optional h engine, are fit on both histories before base observed fitting: 8 procedures/64 starts regardless of the later h gate. Synthetic beta is known; the observed training-only nuisance adapter is separately verified.

For h0,d0 the conditional ground law is exactly mu+nH. Invert its integrated hazard mu*u+n*sum_class,mode w_m*state_class,mode*(1-exp(-lambda_m*u/tau_class)) against one independent-log(openuniform). No acceptance/rejection uniform is consumed, since envelope and actual intensity coincide. Draw the independent exponential magnitude after each event, then assign its parent class/scale. Record sampled step versus actual retained binary64 elapsed time, use reconstructible retained clocks and fail ties, caps or numerical projection/root failures without jitter or redraw. Independent direct-history truth train/test score bindings and16/32 checks remain mandatory.

The common truth is contained in common-free, class-free and class-h; the class truth in class-free and class-h. Fixed tau1 is not a generating truth for these two histories and receives no invalid truth-witness requirement. Truth parameters never enter the optimizer candidate pool. These engineering examples do not establish power, coverage, tight recovery or prospective forecast success.

## Historical Omori bridge and scope

The immutable Iteration 27 fold_scores.csv totals etas_omori full marked logscore -990.1700634129872 over the same 612 targets. Its selected productivity ratios are .4,.7,.7 in Folds 0-2 (the first differs from B), its beta is a global training MLE (Fold 0 approximately 3.1016219113), and its Omori family used its own continuous/kernel selection. B fixes r=.7, uses the retained conditional-bin training beta and a different temporal family. Preserve the exact source/rows/pins in design/historical_omori_bridge.json.

Tabulate historical and new timing, mark, full-joint and compensator values and their raw arithmetic differences only as a descriptive comparison of separately specified forecasting procedures. Magnitude scores do not generally cancel across those recipes. No matched kernel-only gain, physical explanation or exact replication of the earlier +12.46 nats follows. No refit of old Omori runs or new matched Omori search is in scope.

All B results are conditional retrospective comparisons on previously inspected chronological test windows with overlapping training prefixes. No spatial pooling fix is inserted because C results were positive. Parent-class scales are not the full target-class MDFHP framework. No physical causality, event-iid confidence interval, Wilks boundary inference, global-optimum guarantee, alternate bounds or automatic further stage is claimed.
