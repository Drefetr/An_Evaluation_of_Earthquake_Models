# Independent fixed-input S05 point controls

This new wrapper addresses a specific control gap: the archived `controls`
command tests temporal outputs and swaps spatial mass implementations inside
the Python full84 path, but does not call the native `q01_evaluate` point ABI.
The wrapper explicitly calls `Native(...).state(...).evaluate(events)` for
every point fixture. Archived sources remain byte-exact.

**Status at preparation:** source and fake-output tests only. No DLL build,
load, integration, native control or historical likelihood has run. Independent
source review and conductor admission are required before execution.

## Reference derivation

For rectangle cell j, `rho_j=pi_j/area_j`. Define
`K_q(x,u;s)=(1+|x-u|^2/s^2)^(-q)` and
`M_j(u;s,q)=integral_cell_j K_q(x,u;s) dx`.

- OC uses `K_2(x,u;s)*rho_cell(x) / sum_j rho_j*M_j(u;s,2)`.
- EP uses `K_q(x,u;s) / sum_j M_j(u;s,q)`.
- Both backgrounds use `.05*rho_cell(x) + .95*mean_u(K_2(x,u;h)/sum_j M_j(u;h,2))`
  over the fixed training locations. Normalization is unweighted in this KDE.

The new reference computes rectangle integrals by nested Cartesian adaptive
quadrature, independent of the native polar ray algorithm and the archived
Python polar oracle. Inner and outer QUADPACK error estimates are retained;
the combined rectangle estimate is outer error plus rectangle width times the
maximum observed inner error estimate. This is an error estimate, not a proof
of quadrature accuracy for arbitrary kernels. All IntegrationWarnings, nonfinite
values and estimates above 1e-9 fail the affected control. Inner calls request
absolute/relative 1e-12 accuracy and a fixed subdivision limit of 200.

Let `mu(t)=exp(a+d*(2*t/T0-1))`, `h(lag)=(p-1)/c*(1+lag/c)^(-p)`, and
`k(Q)=n*.3*exp(.7*beta*Q)`. For each event i, the ground intensity is
`mu(t_i)+sum_{T_j<t_i} k(Q_j)*h(t_i-T_j)`. The point intensity multiplies the
background by its density and each parent term by its OC/EP spatial density.
The reference selects parents using `T_j<t_i` from the full fixed list; equal
timestamps and the current event are excluded, independently of native order.

The immigrant exposure is independently integrated as `integral_start^end mu`.
Each prehistory or future parent's trigger exposure is
`k(Q_j)*integral_max(start,T_j)^end h(t-T_j) dt`. Thus an empty future with
prehistory still has positive trigger exposure, and a single event at start
cannot cause its own intensity but does contribute exposure through the end.
The reference does not reuse native survival-difference or expm1 formulas.

The eight expected ABI components are

```
N, sum Q, B, trigger exposure, sum log(ground intensity),
sum log(point intensity), N*log(beta)-beta*sum Q,
sum log(point intensity)-B-trigger exposure+mark log score.
```

All sums use `math.fsum`. Counts must match exactly; mark sums use absolute
1e-12; all six remaining components use absolute 1e-7. A separate geometry
comparison checks native rectangle masses within absolute 1e-9.

## Fixed roster and coverage

Five laws are used: OC q=2 and EP q in {1.05,1.4,2,3}. Every law has five point
fixtures: empty future/no history, empty future/positive prehistory, zero
branching with boundary points, positive branching with duplicate timestamps,
and a single event exactly at the forecast start. There are 25 actual native
point calls plus 10 native mass comparisons. The nonuniform nine-cell pi, unequal cell areas and
two asymmetric training locations make the OC/EP weighting and background
KDE mixture distinguishable. Exact corners, internal cell intersections,
outer edges and near-boundary parent positions are covered.

The fixed scales are smooth and moderate. Passing these controls does not
certify all extreme scales, historical optimization, all full84 diagnostics,
simulation correctness or statistical calibration. Invalid native-domain
rejection is outside this valid-input comparison roster.

## Execution after separate admission

Build the unchanged archived scoring sources in an external copy. Then pass
that source directory and the explicitly built library to the new wrapper:

```powershell
python -B reproduction/regional/point_controls.py --sources C:/new/s05_build --dll C:/new/s05_build/independent.dll --output C:/new/s05_point_controls.json --build-receipt C:/new/s05_build_receipt.json
```

`--build-receipt` is optional but pins the conductor's build evidence when
available. The wrapper independently pins its own bytes, all eight archived
source/build files and the library before and after execution. These separate
hashes alone do not prove that a library was compiled from those sources.
Use the conductor's build receipt for that binding. Linux shared libraries
are accepted through the same explicit `--dll` argument.

The report must be new and outside the publication source directory. Each
fixture's inputs, component errors, quadrature estimates and exceptions are
retained. A failed fixture does not suppress later fixtures; any failure,
missing case or source drift prevents a passing report. Global setup failures
retain a failed report with the full planned fixture roster. No historical
data paths are read. The wrapper uses only the Native class, not the archived
native wrapper CLI whose historical report references a different source name.

Preparation-only fake-output checks:

```powershell
python -B -m unittest discover -s reproduction/regional/tests -p test_point_controls_static.py -v
```

Those tests do not load a DLL or evaluate the quadrature reference. A later
campaign guard must bind this new wrapper/report explicitly because the
archived `replay.sourcepins()` does not include it.
