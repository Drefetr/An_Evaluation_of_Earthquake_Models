# Exact autonomous subfamily and theorem gate

This note maps the executed comparison to the **finite-mode stability theorem**
in `paper/source/chapters/03_stability.tex`, using the physical model in Chapter 2.
The conditional intensity is the same raw constant-background family used in
Chapter 9's sensitivity study. The new execution uses a different training
magnitude estimator and optimizer recipe; it is not a new intensity family or
a replay of the earlier fitted procedure. The [README](README.md) links the
completed outputs and both protocols. This explanatory note is current; the
executed `protocol.json` retains its unchanged pre-execution bytes.

Let positive weights sum to one and let all finitely many rates be positive.
Write `Phi(t)=sum_j w_j exp(-theta_j t)` and `h=-Phi'`. Set constant loading
`rho=0`, zero initial modes, and the link `Psi(X)=exp(a+X)` (canonical `b=1`).
Between events the physical modes decay at their respective rates. At an event
with excess mark Q their jumps are

```
Delta Z_j = -eta*g_diag(Q)
Delta U_j = theta_j*n*kappa_diag(Q).
```

Solving these finite linear mode equations gives, before any event at time t,

```
Z_j(t) = -eta sum_{T_i<t} g_diag(Q_i) exp(-theta_j (t-T_i))
U_j(t) = n sum_{T_i<t} theta_j*kappa_diag(Q_i) exp(-theta_j (t-T_i))
X(t) = -eta G(t),   sum_j w_j U_j(t) = n H(t)
lambda(t) = exp(a)*exp(-eta G(t)) + n H(t).
```

Thus the diagnostic law with **constant** background is exactly this
autonomous law: physical `g=eta*g_diag`, physical `kappa=n*kappa_diag`.
The current event never enters its own intensity. The implemented mixture is
the existing, pinned 195-mode shared kernel, not the exact infinite mixture.
For general constant rho, event-free equilibrium stress initialization
`Z_j(0)=rho/theta_j` instead yields background `exp(a+bar_x)`, where
`bar_x=sum_j w_j rho/theta_j`. That parameterization cannot identify rho and a
separately. Canonical rho=0 removes this redundancy. Stress ODE equilibrium and
zero excitation are **not a draw from the stationary law** of the event process.

Equal non-equilibrium initial stress modes `Z_j(0)=X0` instead give the
deterministic stress `X0*Phi(t)+rho*integral_0^t Phi(u)du`. Arbitrary finite
initial stress modes yield a log baseline equal to a constant plus decaying
exponentials. They do not license the earlier unrestricted
affine time trend. For nonzero affine slope its infinite-time baseline limit
is zero or infinity, whereas an admissible finite autonomous initialization
has a finite positive limit.

The selected units are days for time and dimensionless log intensity for
stress, with a using the chosen inverse-day reference. Rates and intensity
have inverse-day units; kappa is dimensionless; rho has stress/day units.

## Assumptions of the invoked theorem

| Requirement | Check for the executed subfamily |
|---|---|
| Finitely many positive rates and normalized positive weights | Exact pinned finite mixture; tiny tests check these properties |
| Constant rho>=0, finite admissible initial modes | rho=0, Z=U=0; afterwards Z<=0 and U>=0 |
| Positive nondecreasing Lipschitz link on the reached half-line | exp(a+X), X<=0; upper bound and Lipschitz constant exp(a) |
| Fresh iid marks independent of pre-event history | Posited Exp(beta) excess law; an assumption, not established by observed magnitudes |
| Finite `m1=E[g]` | For eta>0 requires beta>gamma; eta=0 gives m1=0 identically |
| Physical `E[kappa]<1` | Fixed r=.7<1 gives E[kappa_diag]=1, so the fitted n in [0,.98] is the physical branching mean |

Here `gamma=.75 log(10)`, `g_diag(Q)=exp(gamma*(Q-1))`, and
`kappa_diag(Q)=(1-r) exp(beta*r*Q)`. Under Exp(beta), for positive eta,

```
E[g] = eta*exp(-gamma)*beta/(beta-gamma),  beta>gamma.
E[kappa] = n.
```

If beta<=gamma and eta>0, the first stress moment is infinite. This is a real
failure of the theorem assumptions, despite finite values at every finite
observed mark. For example beta=gamma/2, eta=1, n=.5 fails this gate while
remaining subcritical in excitation. The declared procedure must retain an
ineligible outcome rather than change the mark law to obtain a theorem.
For eta=0 the release is identically zero even when the unscaled stress mark
has infinite mean; there is no multiplication of zero by infinity.

**No higher moments are inferred from this first-moment theorem.** For positive
eta and n, E[g^2] needs beta>2gamma, E[kappa^2] needs r<.5, and E[g*kappa] needs
beta*(1-r)>gamma. At beta=2.8494 and r=.7, the first moments exist but these
three stronger conditions all fail. The finite-mode theorem explicitly
requires no second moment; its fresh-mark cluster argument permits correlated
g and kappa. Its separate infinite-stationary-second-moment proposition is
compatible with stability. This experiment invokes no quadratic, Gaussian,
Fisher-information, or cross-moment theorem.

Under the model assumptions the finite-mode theorem provides construction,
an invariant law with its stated first Lyapunov moment, uniqueness, and weighted
Wasserstein convergence. It does not verify the mark law in a catalogue,
identify physical stress, supply a useful numerical mixing time, establish a
Wilks law, or extend to the nonlinear exact-memory limit. For the implemented mixture theta_min=exp(-38.8) per day, so the proof's
requirement t0>=log(4)/theta_min already exceeds 9.8e16 days. Its drift/coupling
certificate therefore gives no useful mixing guarantee on the catalogue
horizon. Exactly 61 of the 195 modes decay less than 1% over 24,394 days;
their normalized survival-kernel weight sums to only 0.00042934294645.
That small weight concerns Phi, not arbitrary initialized states or total
observed stress. Neither the mode count nor the worst-case proof bound is an
estimate of actual process mixing. The [portable scalar diagnostic](../methodological_audit/stability.py)
reproduces these quantities and the saved-procedure comparison without model
evaluations.

## Executed empirical question

Does this deliberately restricted autonomous statistical law improve held-out
occurrence log score over its matched eta=0 floor on the previously inspected
NZ chronology? Both arms estimate a and n on training data; only the inhibited
arm additionally estimates eta. The shared kernel, r and d=0 are fixed. Beta
is a common training-only plug-in estimate, not a joint mark-intensity fit.
The comparison concerns these fitted procedures, retains negative gains, and
does not test physical loading, causality, prospective validity or a separate
memory alternative. The exact starts, bounds, solver recovery and numerical
gates are frozen in `protocol.json`; the README links the completed execution
and its internal output review. The earlier conditional-bin beta, different
starts and solver settings are retained alongside this protocol. No
beta-only attribution of the difference between their scores is established.
