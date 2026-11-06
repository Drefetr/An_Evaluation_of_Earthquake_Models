# Mathematical audit of C3 and M1

Audit baseline: 61aa599cd023f2441a6a0c6af9aa4b6fe9eda3e5. This is a source/code derivation review, not a new simulation, fitting campaign, human peer review, or theorem certification by vote. Repository files were read only. Companion result.json records source hashes and exact archive-member identities.

## Adjudication

C3 identifies a real scope gap. The finite weighted-moment example in Chapter 5 is correct for its stated temporal transform and productivity ratio, but it must not be generalized to all synthetic procedures. Spatial magnitude-scaled LI+ at beta=2, r=.7 fails that ratio condition. S02 M2 also fails it, because setting r=0 changes productivity but does not make the stress marks constant. Total-intensity attenuation has a different score and a different information integrand.

Failure of a sufficient upper bound alone is not a proof of divergence. Under the additional, verifiable null-law assumptions below, there is a separate proof of divergent immigrant-only null information, including the spatial LI+ setup. The corresponding positive-inhibition laws have a simple finite-information bound. None of these statements establishes that heavy tails caused the reported held-out losses, or establishes the distribution of selected fitted parameters.

M1's rare-history criticism is a valid limitation of the identification argument, not a counterexample to the proposition. Every fixed finite mark and fixed finite no-further-event interval has positive conditional survival; probabilities can nevertheless become extremely small as the mark grows. The full-law limit remains valid under its assumptions. No sample-size, estimator, robust-identification, or empirical power guarantee follows.

## 1. Source facts, not inferred transforms

### Temporal procedure and S02

Chapter 5 uses Q~Exp(beta), gamma=(3/4)log(10), g(Q)=exp(gamma*(Q-1)), and kappa_r(Q)=(1-r)exp(r*beta*Q). The external coefficient n is not part of kappa.

The S02 archived wrapper is in reproduction/s02/completed_inputs_20261031.zip, member source/research_runs/scientific_stage2_resume_20261031T205913Z/temporal/source/s02_campaign.py. Lines 40–43 loop over (M1,.7) and (M2,0), changing only the candidate law's ratio at this step. The archived cached_stage2.cpp line 32 computes
    stress = exp(gamma*excess)/exp(gamma)
    prod = (1-ratio)*exp(beta*ratio*excess).
The same computation appears in the live engine/stage2_followup/s01_s02_temporal/cached_stage2.cpp. recursive_adapter.py imports gamma from cpu_authority.GAMMA; the bundled oracle_likelihood.py defines it as .75*log(10). Therefore M2 has kappa=1 and retains the heavy stress transform.

The archived S02_STAGED_RECIPE.json gives beta=2.849401764894274. The wrapper sets n=.5 and generates with productivity_ratio=0, with h in {0,.5,.9}. r_matched/model.hpp lines 76–84 make offspring magnitude-class probabilities depend on the parent's class when h>0. At h=0, the class mixture recovers an exponential fresh-mark distribution. At h>0, the marks are not fresh independent marks conditional on past history, even if their marginal law is exponential. Applying the fresh-mark compensation theorem there requires a new conditional-mark argument, not merely a marginal moment.

S02's exact Mittag–Leffler generator and the finite 195-mode fitted candidate remain different numerical laws, as the manuscript says. Statements about the score martingale under a candidate's own null law must not be described as a proof about the actual generator's misspecified likelihood score.

### Spatial LI+

Chapter 13, equation following the first two paragraphs of 13_s04_expanded.tex, uses g_+(Q)=exp(gamma*Q), without the temporal reference shift. This is confirmed by reproduction/synthetic/source/cpu_reference.cpp lines 50–66 and generator.py strict_stress_plus (lines 353–360). Original LI uses unit stress marks.

generator.py Law specifies beta=2, r=.7, n=.35, c=.05, p=1.3, sigma=10 and a finite rectangular domain. Its trigger is an ordinary normalized Omori/spatial kernel; c>0 and the compact spatial domain make the trigger density bounded. controls_campaign.py canonical_arrays constructs fertility .3*exp(beta*.7*Q). The strict-stress field is positive and continuous on every compact time/spatial region for fixed positive ell and psi. The uniform component in the smooth background keeps its density positive. These properties supply the local lower bounds and bounded trigger kernel used below.

Original S04 positive histories use unit-mark immigrant inhibition. Matched S04B cases S4/S5 use magnitude-scaled immigrant inhibition; S6/S7 also thin offspring and thus implement total attenuation. A null-law calculation is not automatically a calculation under any of these positive-inhibition generating laws.

## 2. Immigrant-only score and exact moment condition

Let lambda_eta(t,z)=B(t,z)exp(-eta G(t,z))+nH(t,z), with fixed nuisance parameters. Under its own generating law the compensated score is
    U_eta = -integral [B exp(-eta G) G / lambda_eta] (dN-lambda_eta dt dz).
At eta=0 its expected bracket/information is
    I_imm(0) = E_0 integral B^2 G^2/(B+nH) dt dz.

In the temporal theorem, Cauchy–Schwarz supplies the sufficient bound by m=E[g^2/kappa]. For exponential marks and g=C exp(gamma Q),
    E[g^2/kappa]
      = C^2/(1-r) * beta/[beta(1+r)-2gamma]
when beta(1+r)>2gamma, and is infinite at or below equality.

Consequences:
- Original temporal r=.7 example: beta=2.849401764894274 gives a positive denominator and the stated finite m. Its constant C=exp(-gamma) matters for the value, not the finiteness threshold.
- Spatial LI+: beta(1+r)=3.4 < 2gamma=1.5log(10). The ratio moment is infinite. Changing or omitting the reference shift does not change that threshold.
- S02 M2: r=0, so m=E[g^2], which is infinite because beta=2.849401764894274 < 1.5log(10). M2 does not inherit the r=.7 calculation.
- Original unit-mark immigrant LI has E[1/kappa]<infinity for these exponential marks. It must not be grouped with LI+.

These conclusions about m alone say that the stated upper-bound proposition is unavailable. The next argument supplies a genuinely separate divergence proof.

## 3. Divergence under an unstopped ideal Hawkes null

Assume: empty initial history; fresh independent Exp(beta) marks; 0<n<1; finite positive immigrant mass on the finite horizon; bounded nonnegative normalized trigger kernel K_e; and a time/spatial region of positive measure after a possible first immigrant on which B and the first parent's stress kernel K_s have strictly positive lower bounds. These conditions hold for the ideal continuous-mark, spatial Omori null described above. The finite positive exponential-mixture temporal candidate also has bounded trigger kernels.

Let the first event be at (s,y), with mark q; choose (s,y) in a fixed earlier region of positive probability and consider a later compact region A. No requirement is imposed on the descendants or later immigrants. The first parent alone gives
    G(t,z)^2 >= c_s^2 g(q)^2,  (t,z) in A.

By the branching construction and E[kappa]=1, the expected total productivity of the first parent's cluster through the horizon is at most kappa(q)/(1-n). The future immigrant clusters have finite expected total productivity bounded independently of q. Bounded K_e then gives
    E[H(t,z) | first (s,y,q)] <= a_0+a_1 kappa(q)
uniformly on A. Freshness is required in this step.

For deterministic B, convexity of x -> 1/(B+nx), Jensen's inequality, and a positive lower bound on B imply
    E[B^2 G^2/(B+nH) | first (s,y,q)]
       >= c * g(q)^2/(1+kappa(q))
on A, for a fixed c>0. Integrating over A and then over the first mark yields an infinite lower bound whenever E[g^2/(1+kappa)]=infinity.

For r>0 and the stated exponential productivity, kappa grows exponentially and is bounded below by 1-r, so this moment has the same tail threshold as E[g^2/kappa]. For r=0 it is a constant multiple of E[g^2]. Thus the ideal spatial LI+ null and the ideal finite-mixture M2 null have infinite expected score bracket. This is not simply a failed upper bound.

For these two applications E[g]<infinity. Fresh-mark compensation, finite mean count and integrable/bounded stress kernels imply E integral BG <infinity. Therefore the immigrant score is a true integrable compensated martingale. If its terminal value were square integrable, the martingale/isometry implication would force its expected bracket to be finite. Hence its terminal null second moment is also infinite. This last integrability step must accompany a claim about the terminal score variance, rather than only the bracket.

Do not use a proof conditioning on “exactly one event and no descendants” at n>0 while keeping the first mark unweighted. That conditional event probability decays with kappa(q), and the mark distribution is tilted. The existing n=0 Poisson counterexample in Chapter 5 correctly uses mark/count independence; it does not justify the positive-n case without another argument.

For S02 h>0, neither the fresh-mark proof above nor its conclusion is automatically a theorem for the actual persistent-mark generator. For S02 h=0, the own-candidate-law statement is sufficient to show that the claimed r=.7 regularity does not cover M2; it is not a claim of exact generator/candidate identity.

## 4. Total-intensity attenuation: different score and mixed moments

For lambda_eta=(B+nH)exp(-eta G), with fixed nuisance parameters,
    partial_eta log(lambda_eta)=-G,
    U_eta,total = -integral G (dN-lambda_eta dt dz).
Its null expected bracket is
    I_total(0) = E_0 integral G^2(B+nH) dt dz,
not E integral B^2G^2/(B+nH).

A first parent gives a background contribution proportional to E[g^2]. With n>0 and a positive trigger/stress overlap, its same-parent diagonal contribution is proportional to E[g^2*kappa]. For g=C exp(gamma Q), those necessary moments have thresholds
    E[g^2]<infinity             iff 2gamma<beta,
    E[g^2*kappa]<infinity       iff 2gamma+r beta<beta,
    E[g*kappa]<infinity         iff gamma+r beta<beta.
The last condition is relevant to absolute first-moment control of integral G lambda_0, not a substitute second-moment criterion.

At spatial beta=2,r=.7 all three displayed moments diverge. The diagonal term alone proves infinite expected null bracket. No first-moment conditioning on absence of later descendants is needed because the integrand is nonnegative and the first-parent contribution remains present.

These are necessary obstructions, not a sufficient joint-moment theorem. G^2 H contains cross-parent products, and offspring-count dependence can require additional cluster/productivity moments. For example, even g=1 does not reduce total-attenuation score regularity to E[kappa]<infinity; heavy fertility creates high count moments. Do not claim that E[g^2*kappa]<infinity by itself establishes total-score square integrability.

For total attenuation at these marks, E integral G lambda_0 can already be infinite. The safe immediate conclusion is divergence of expected null predictable bracket/information and failure of an L2 score-martingale argument. A claim identifying this with an ordinary terminal variance needs an integrability/martingale argument; the immigrant proof's E integral BG bound does not transfer to total attenuation.

## 5. Positive inhibition, finite horizons and implemented simulation

For immigrant attenuation and eta>0,
    (B exp(-eta G)G)^2/lambda_eta
       <= B G^2 exp(-eta G)
       <= 4B/(e^2 eta^2).
Therefore finite immigrant mass gives finite expected score bracket at every fixed positive eta, independently of the raw stress-mark second moment.

For total attenuation and eta>0,
    G^2 lambda_eta
       <= [4/(e^2 eta^2)](B+nH).
Under the fresh-mark subcritical Hawkes envelope, E_eta integral(B+nH) is finite, bounded by the corresponding envelope's mean event count. Thus every fixed positive eta also has finite score bracket in this family. Neither bound is uniform as eta approaches zero. Neither proves a CLT, Wilks law, searched-nuisance regularity, or a prediction-error bound.

A finite observation horizon is not a bound on the ideal mark distribution or the ideal event count. The null divergence proof above already uses a finite horizon. Conversely, finite realized scores do not contradict divergent moments across hypothetical histories.

The implementation is a further distinct object:
- generator.py uniform uses a 53-bit grid and _mark uses -log1p(-u)/beta. Literal generated marks therefore have a finite machine-dependent maximum.
- S02 r_matched/model.hpp open_uniform uses a 52-bit midpoint grid, also producing finite representable marks.
- Both generators impose event/resource/numerical caps and retain failed or unknown outcomes. Synthetic generator.py explicitly reports candidate, event, wall-time and representability failures; S02 model.hpp returns event_cap/numerical_failure.
- The completed saved histories are a finite collection of finite machine outputs. Ideal infinite-moment claims must not be described as literal infinite variances of that finite collection, or of an accepted-output distribution without specifying conditioning.

Stopping at caps, truncating a mark law, conditioning on completion, and evaluating the ideal unstopped law are different operations. The mathematical result here concerns the ideal unstopped continuous exponential-mark law. One should not use it to claim that the completed simulations are invalid or that a cap constitutes a mathematically justified truncation correction.

## 6. Identification and rare histories

The active-identification proof in 04_identifiability.tex compares a first event at s with mark q and no event before a later t. Along that one-parent history, conditional no-further-event survival is
    S_q(s,t)=exp{-integral_s^t B(v) exp[-eta g(q)Phi(v-s)] dv
                    -n kappa(q) integral_0^(t-s) h(u) du}.
For each finite q, local integrability of h and finite B give S_q>0, so the full-law comparison has support. Continuity permits extension from almost-everywhere mark values. Dividing the intensity identity by kappa(q) and taking q to infinity then identifies the trigger term as written.

At n>0 and fixed t-s>0, writing a=n integral_0^(t-s)h>0 gives
    S_q(s,t) <= exp[-a kappa(q)].
For kappa(q)=(1-r)exp(r beta q), r>0, this survival shrinks as an exponential of an exponential in q. The joint probability of a large mark and this quiet history is smaller still. This quantifies why the proof is not a practical finite-sample identification method.

This rarity does not invalidate structural identifiability: equality of full laws includes all these positive-support finite-q histories before the limit. But the result supplies no lower bound on usable history frequency, information, estimation rate, finite-catalogue uncertainty or robustness. It also does not cover bounded marks, unknown/state-dependent mark laws, or M2's kappa=1, which fails kappa(q)->infinity. Failure of this proof's assumptions does not prove nonidentifiability of those other models.

No assertion that large-mark rare histories prove empirical identification should survive. The restricted proposition itself need not be removed merely because its proof uses rare histories.

## 7. What the manuscript should change

1. Chapter 5: rename/scope the numerical example to the stated temporal r=.7 law. Add a short explicit applicability comparison for spatial LI+ and S02 M2 with the actual g transforms. Keep existing finite example and protected numerical displays; new numeric literals need normal claim custody if introduced.
2. Chapter 5: present the total-attenuation null score separately. Do not transfer the immigrant ratio bound to total attenuation. State necessary diagonal moment obstructions; do not invent a complete sufficient mixed-moment theorem.
3. If making a positive-n null-divergence claim, include the first-parent/Jensen proof with its bounded-kernel, fresh-mark and ideal-law assumptions. Otherwise state only that the existing proposition does not apply.
4. Add the positive-eta bounds, and distinguish own-null law, positive generating law, misspecified candidate scores, finite numerical histories and stopping. Avoid describing all S04B histories as having an infinite-variance generating score.
5. S02 section: explicitly say M2 changes productivity to r=0 while retaining magnitude-scaled stress. Fresh-mark theory does not cover h>0 without a separate argument.
6. S04 section: state that null heavy-tail irregularity is a possible methodological concern, not an established explanation for negative held-out gains. Optimizer selection, shared-coordinate adjustment, finite sample noise, model mismatch, kernel scale, gates and observation procedure remain separate mechanisms; the saved contrast alone identifies none causally. No new fits are required to make this correction.
7. Identification section: quantify rare-history survival or state its decay plainly and add that the proof gives no useful-history probability or finite-sample estimator guarantee. Preserve the distinction between an ideal identification theorem and practical identification of fitted procedures.

## Final boundary

The audit establishes source-backed transform differences and analytic null/interior regularity results. It does not establish that the campaigns' finite numerical losses were caused by an infinite moment, that every tested candidate equals a generating law, that a finite list of successful simulations estimates a tail moment reliably, or that the restricted identification proposition identifies the empirical models.

