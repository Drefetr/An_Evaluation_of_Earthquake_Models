# Joint likelihood and derivative contract

Let `x(t)=2t/T0-1`, `B(t,s)=exp(a+d x(t)) b(s)` and

```
k(u;c,p) = (p-1)/c (1+u/c)^(-p), u>0
H(t,s) = sum_{tj<t} k(t-tj;c,p) kappa(Qj) f(s|sj)
G(t,s) = sum_{tj<t} g(Qj) exp(-(t-tj)/psi) (1+|s-sj|²/ell²)^(-2).
```

The normalized spatial density `f`, background `b`, mark transform `kappa`
and mark density remain fixed. LI uses `g=1`; both LI+ arms use
`g=exp((3 log(10)/4) Q)`. The immigrant-only intensity is `B exp(-eta G)+nH`;
total attenuation is `(B+nH) exp(-eta G)`. Every point uses strict prehistory,
including warmup parents and earlier held-out parents. Equal-time events do
not parent one another.

For each observed interval the marked score is `joint=P-E+M=P+C+M`, where
`P=sum log(lambda_i)`, `E=integral lambda >=0`, `C=-E`, and the fixed exponential
mark contribution is `M=N log beta-beta sum Q`. Shared marks cancel in gains.

Write `l=log c`. The temporal derivatives used both at events and at all
space-time integration nodes are

```
d_l k = k[-1+p u/(c+u)]
d_p k = k[1/(p-1)-log(1+u/c)].
```

For a parent's exposure interval `[lo,hi]`, let
`S(v)=(1+v/c)^(1-p)`. The exact unattenuated temporal mass is
`J=S(lo)-S(hi)`, evaluated using `expm1` to reduce cancellation. Its derivatives
are

```
d_l J = (p-1)[lo/(c+lo) S(lo)-hi/(c+hi) S(hi)]
d_p J = -log(1+lo/c) S(lo)+log(1+hi/c) S(hi).
```

The unattenuated compensator is the analytic background integral plus
`n sum kappa(Qj) Jj`. Its derivatives in `(a,d,n,l,p)` are analytic. The
background integral is evaluated with a stable `sinh(z)/z` expansion at zero.

The inhibited exposure is evaluated as `E=E0-D`. With `A=B` for immigrant-only
inhibition and `A=B+nH` for total attenuation,

```
D = integral A [1-exp(-eta G)].
```

The five shared-coordinate derivatives differentiate `A` and `E0`; they are
not frozen-backbone derivatives. In particular total attenuation includes
the freshly recomputed fields `H`, `d_l H` and `d_p H` in the deficit. These
are formed by bounded matrix products between fixed spatial coefficients
and the variable temporal kernels.

For the inhibition coordinates, put `R=|s-sj|²/ell²`. Each stress summand
has log-ell derivative `summand*4R/(1+R)` and log-psi derivative
`summand*(t-tj)/psi`. Writing their sums as `L` and `Q`, the deficit derivatives
are `integral A exp(-eta G) (G,eta L,eta Q)`. Native recurrence updates are

```
G <- e G; L <- e L; Q <- e(Q+G_old*dt/psi), e=exp(-dt/psi),
```

followed by the appropriate stress/scale jump. This recurrence changes no
temporal Omori field or fit parameter.

Point log intensities use `logaddexp`. For immigrant-only attenuation the
inhibition derivatives multiply the attenuated background fraction. For
total attenuation the log intensity is `log(B+nH)-eta G`, so its inhibition
derivatives are directly `-(G,eta L,eta Q)`. Shared derivatives use the
corresponding background/trigger fractions. Ratios are evaluated in log
coordinates where necessary. A finite objective with a nonrepresentable
gradient is recorded as a primary failure; value-only Powell recovery may
proceed under the same frozen budget. No derivative is clipped. Timeout or
memory failure never invokes optimizer recovery.

The quadrature plan is fixed before fitting: positive adaptive spatial nodes
and log-transformed time panels split at event times, using the fixed minimum
allowed `c` rather than the fitted value. Thus the analytic gradients are
derivatives of the actual numerical objective. The geometry proxy is not a
rigorous integration-error bound. Selected states receive the declared
independent-order checks; failures remain numerical unknowns.

Coarse-order training selection is retained without re-ranking. BIC uses
consistent fine-order training scores at those verified selected states.
Both coarse/fine gate decisions and threshold distances are reported. Test
scores never choose a fit, gate, bound, starting point or replacement history.
Fine/coarse held-out evaluation is a declared numerical check, not a second
selection stage.

The exact feasible historical backbone remains a new-null candidate. The new
null is in every alternative's candidate set at eta zero. Equal objective
values prefer the included floor. An eta-zero alternative that finds a better
shared-coordinate solution is a null-search gap, not an active-inhibition
discovery. Equal solver budgets and all resolved starts certify execution of
the recipe; they do not certify a global optimum.
