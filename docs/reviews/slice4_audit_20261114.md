# Slice 4 forensic audit and remediation — 14 November 2026

**Baseline:** `e2fb101`
**Scope:** Chapters 11 and 12, Appendices B.9–B.10, California and Japan
regional transfer (`OC`/`FC`/`MC`/`OL`/`FL`/`EP`/`N0`), the \(M\ge 4.5\)
threshold sensitivity, the fifteen-year annual partition and the active-sequence
partition, the four-arm spatial comparison S03, the rolling California episode
backtests and JMA trend ablation S06, and the 2,997-path conditional simulation
calibration S05.
**Disposition:** **Accepted with the repairs recorded below.** Every displayed
table cell, pooled and per-target ratio, annual and sequence share, block
interval, S03 telescoping identity, S06 episode partition, and S05 rank/omnibus
statistic recomputes from its bound authority. The audit confirmed two Chapter 11
and Appendix B.9 formatting defects, two Chapter 12 and Appendix B.10
scientific-notation defects, and one S03 mathematical-clarity defect; all five
are repaired. No sign inversion, wrong comparator, denominator mismatch, or
boundary value presented as an interior optimum was found.

The independent evidence package is
`validation/live_results/slice4_audit_20261114/`. It contains eleven JSON
artifacts written by
`experiments/methodological_audit/slice4_audit_20261114.py`. The pre-change byte
snapshot is `validation/slice4_prechange_snapshot_20261114.{json,zip}`.

## 1. Non-negotiable custody result

All **749** pre-existing sealed JSON identities are byte-for-byte unchanged:
the 748 JSON files under `validation/authorities/` and
`validation/live_results/`, plus the Slice 3 acceptance record
`validation/slice3_remediation_20261114.json` that completes the roster. The
audit resolved every hash against the pre-change snapshot:

```text
snapshot records : 749
unchanged        : 749
changed          : 0
missing          : 0
```

The snapshot hash is `72690e76…` and the zip hash is `53b52ad7…`. The repaired
publication files lie outside that sealed set. The eleven artifacts contain
**574** independent checks across ten components; every component passes. The
audit did not fit a model, simulate a catalogue, rerun an optimizer, or
regenerate a sealed claim.

## 2. California primary transfer and competitive benchmarks

### 2.1 Cohort reconstruction

The canonical preferred-record file `reproduction/nzca/expected/california_events.json`
contains **1,272** unique `eq` records. All satisfy the stated reported-magnitude
and projected-domain restrictions:

| Quantity | Recomputed |
|---|---:|
| Records | 1,272 |
| Unique event identities | 1,272 |
| Minimum reported magnitude | 4.00 |
| Latitude range | 32.004–36.945° |
| Longitude range | −120.957 to −114.884° |
| Depth range | −1.9 to 28.7 km |
| 1981–1985 warmup records | 106 |
| Scored training prefixes (<2011, <2016, <2021) | 851, 930, 1,097 |
| Test windows [2011,2016), [2016,2021), [2021,2026) | 79, 167, 69 |
| Test total | 315 |
| \(M\ge 4.5\) population / warmup | 391 / 33 |
| \(M\ge 4.5\) training prefixes | 271, 287, 340 |
| \(M\ge 4.5\) test windows / total | 16, 53, 18 / 87 |

The same reconstruction is exercised by
`python -B reproduction/regional/inputs.py verify`, which validates the 6,000
S05 identities, 12 S03 selected arms, 55 S06 fit records, 15,093 numerical
crosswalk records and 6,110 payload members.

### 2.2 Primary table

| Window | Targets | OC−FC timing | per target | OC−OL location | per target |
|---|---:|---:|---:|---:|---:|
| 2011–2016 | 79 | +0.099084 | +0.001254 | +91.803255 | +1.162067 |
| 2016–2021 | 167 | +32.722878 | +0.195945 | +465.829993 | +2.789401 |
| 2021–2026 | 69 | +4.968377 | +0.072005 | +116.690274 | +1.691163 |
| Pooled | 315 | +37.790339 | +0.119969 | +674.323522 | +2.140710 |

The three fold values sum to the pooled totals. The middle timing window supplies
86.59% of the pooled timing difference, which the prose rounds to “about 87%”.
The location decomposition is exact:
\(17.206741+3.514553+653.602228=674.323522\), so the within-cell share is
**96.927099%**. The timing decomposition is
\(40.898879-3.108539=37.790339\), with the exposure term signed as minus the
integrated intensity.

The contextual contrasts are also exact: OC−MC joint
\(+21.177884\) (+0.067231 per target), FC−FL location \(+671.244340\)
(+2.130934), and OC−FL joint \(+747.800021\) (+2.373968). Each wins all three
windows. These use different references and are not additive.

### 2.3 Refitted N0 and competitive EP

OC exceeds N0 by **+1,694.942967** joint nats
(+894.845888 timing, +800.097080 location), decomposed as
+1,612.690857 point-event and +82.252111 signed exposure. All three windows are
positive in every component; the middle window contributes 77.4896% of the
joint gain.

EP exceeds OC by 51.051205 joint nats (OC−EP = −51.051205), decomposed as
+0.336250 timing and −51.387454 location, with −54.591677 point-event and
+3.540472 signed exposure. The fold joint values are −6.288819, −31.742512 and
−13.019873; conditional location loses in every window. The pooled timing
difference is +0.001067 nats per target. The identity
point + compensator = joint holds for both comparisons.

### 2.4 Paired calendar-block uncertainty

| Fold | Contrast | 90-day interval | Sign-flip \(p\) |
|---|---:|---:|---:|
| F0 | −6.289 | [−21.790, 3.296] | 0.57656 |
| F1 | −31.743 | [−77.229, −3.991] | 0.02558 |
| F2 | −13.020 | [−22.823, −4.861] | 0.00366 |
| Pooled | −51.051 | [−99.930, −17.264] | 0.00018 |

The 63 pooled blocks comprise 21 per fold. The 180- and 365-day pooled
intervals are [−96.894, −16.999] with \(p=0.00130\) and
[−93.188, −17.257] with \(p=0.00726\). The location component is −51.387 with
90-day interval [−98.567, −18.423] and \(p=0.00006\). The fold totals sum to the
pooled total. These intervals remain conditional on the saved fits and the
declared block geometry.

## 3. Higher threshold, annual partition, and active sequence

### 3.1 Threshold roster and table

The \(M\ge 4.5\) authority records 391 records, 33 warmup parents, training
prefixes 271/287/340, test targets 16/53/18 (87 total), 30 procedures, 240
starts, 33 nested floors, 273 candidate slots, 15 model-window statuses, 12
primary-arm windows and 9 planned contrast windows. The reached denominators
confirm 30 procedures, 240 starts, 33 floors, 273 candidates, 240 finite solver
returns, 15 model statuses and 12 primary windows. The maximum score audit error
is \(1.1226575225009583\times10^{-11}\) nats against \(10^{-4}\).

| Comparison | \(M\ge 4.0\)/target (315) | \(M\ge 4.5\)/target (87) | \(M\ge 4.5\) total | Positive |
|---|---:|---:|---:|---:|
| OC−FC timing | +0.119969 | +0.152292 | +13.249423 | 3/3 |
| OC−OL location | +2.140710 | +2.123867 | +184.776469 | 3/3 |
| OC−MC joint | +0.067231 | +0.077518 | +6.744097 | 2/3 |

The first higher-threshold OC−MC contrast is −0.626348 nats and its OC−FC
timing total is +0.077968. The location decomposition is
\(5.881781+2.472120+176.422568=184.776469\), so the within-cell share is
**95.478914%**. The timing decomposition is
\(14.762895-1.513472=13.249423\), and the joint decomposition is
\(5.992897+0.751200=6.744097\).

### 3.2 Annual partition

Both fifteen-row annual tables were reconstructed cell by cell. Every row
matches its stored block, the target counts sum to 315 and 87, and each annual
column sums to its pooled contrast within \(10^{-11}\) nats. At \(M\ge 4.5\),
2015 and 2017 have zero targets but retain non-zero exposure terms; their
location columns are exactly zero and their per-target means are undefined, not
zero. Ten of the fifteen higher-threshold timing contributions are negative.

Calendar 2019 has 116 targets at \(M\ge 4.0\) and 37 at \(M\ge 4.5\). The signed
shares of the pooled \(M\ge 4.0\) contrasts are **77.48%** (29.280597/37.790339),
**58.247%** (392.773429/674.323522) and **37.678%** (7.979400/21.177884).
The higher-threshold 2019 contributions are +10.977080, +112.007721 and
+5.288450.

### 3.3 Active-sequence partition

The sole scored episode covers **110** targets over exactly
`2,713,564,040,000` microseconds (31.406991204 days). Its complement covers
**205** targets over 5,447.593008796 days. The active period contributes
+30.058155 of the +37.790339 pooled OC−FC timing nats, or **79.539257%**; the
complement contributes +7.732184. The active and complement OC−EP joint terms
are −18.372230 and −32.678975 and sum to the pooled −51.051205. The active
timing/location pair is (−0.806683, −17.565547); the complement pair is
(+1.142932, −33.821907).

The calendar-2019 non-active complement contains 6 targets in Fold 1 and
contributes −0.777558 OC−FC timing nats and −1.898745 OC−MC joint nats. All
sixteen displayed reporting rows per contrast were checked, including the two
empty active rows. For every arm, \(Q-E=\text{timing}\),
timing + location + mark = joint, and active + complement = total.

## 4. Japan (JMA) reported-record transfer

### 4.1 Cohort

The 19 local annual archives contain **4,019,138** source records and yield
**4,602** selected study records. The 2006–2010 warmup contains 496 records;
the expanding training prefixes are 2,829, 3,298 and 3,646; the disjoint test
windows contain 469, 348 and 460 records (**1,277** total). Fold boundaries in
centisecond keys are 3,652/4,748/5,844/6,940 days, with warmup ending at
1,826 days.

The adjudication count is 41,278 initially unresolved target observations
(41,279 auxiliary), all 41,278 target ambiguities resolved as nonqualifying
reported-primary records, and one auxiliary depth ambiguity retained with zero
target, parent or beta-observation effect.

### 4.2 Contrasts

| Comparison | Pooled nats | per record | Windows |
|---|---:|---:|---|
| OC−FC timing | −58.593466 | −0.045884 | negative 3/3 |
| OC−OL location | +1,905.743202 | +1.492360 | positive 3/3 |
| OC−EP joint | −221.211492 | −0.173227 | negative 3/3 |
| OC−MC joint | −49.194622 | −0.038524 | negative 3/3 |
| FC−FL location | +1,847.637387 | +1.446858 | positive 3/3 |
| OC−FL joint | +1,777.980521 | +1.392311 | positive 3/3 |
| OC−N0 joint | +3,262.466936 | +2.554790 | positive 3/3 |

The conditional-location deficit of 213.485907 accounts for the OC−EP joint
loss. The nine source-JST annual blocks (2016–2024) have target counts
201, 125, 143, 106, 111, 131, 140, 126 and 194; their seven contrast columns sum
to the pooled values within \(1.1\times10^{-11}\) nats. The fit roster resolves
36 procedures, 288 starts, 42 floors and 330 slots with zero failed slots. The
largest stored near-optimal spread is \(3.747311\times10^{-5}\) nats per record,
below the 0.01 gate. All three background bandwidth selectors choose the 5 km
edge and all FC spatial selectors choose the interior 15 km value; the 7/6/2
lower-bound slope counts are retained from the bound forecast-findings narrative.

## 5. Four-arm spatial comparison (S03)

Every fold row of Table `tab:s03-completed` was recomputed from the six
`*_m02_s03_*_aggregate.json` authorities:

| Region | Fold | Targets | 2−1 | 3−2 | 4−2 | 4−1 |
|---|---|---:|---:|---:|---:|---:|
| CA | 0 | 79 | −0.2962 | +1.4515 | +6.3629 | +6.0668 |
| CA | 1 | 167 | +1.0722 | +3.1070 | +29.9884 | +31.0606 |
| CA | 2 | 69 | +0.2776 | +0.7288 | +12.6035 | +12.8811 |
| NZ | 0 | 203 | +0.3421 | +2.1881 | +17.9074 | +18.2495 |
| NZ | 1 | 155 | +33.2980 | −0.3822 | −0.0583 | +33.2397 |
| NZ | 2 | 254 | −1.2518 | −3.2235 | +0.0346 | −1.2172 |

In every fold, \((4-1)=(2-1)+(4-2)\) and
\((4-1)=(2-1)+(3-2)+(4-3)\) hold to \(10^{-12}\) nats. The non-telescoping sum
\((2-1)+(3-2)+(4-2)\) differs from \((4-1)\) by exactly \((3-2)\); it counts the
intermediate step twice. The manuscript now states this explicitly. The
background detail is a separate point: arm 3 alone uses leave-one-out background
fitting, while arm 4 inherits arm 2's KDE background, so \((4-3)\) changes both
the offspring law and the background procedure rather than isolating a pure tail
effect.

The regional EP−OC totals are exact:

| Region | Timing | Location | Joint |
|---|---:|---:|---:|
| CA | −0.820470 | +50.828928 | +50.008459 |
| NZ | +2.145205 | +48.126852 | +50.272057 |

They agree with
`validation/authorities/1210ed825946f8e7_s02_s03_derived_values.json` and with a
direct sum over the six stored arm-score vectors. The mark contrast cancels in
every fold.

## 6. Episode backtests and JMA trend ablation (S06)

All five California rows and both partition rows match
`1b543087985ae113_s06_manuscript_values.json`:

* 1994: 64 targets; FC −527.0462, MC −525.5013, OC −526.7452, EP −521.5603;
  OC−FC full/active/complement +0.3010/−0.0672/+0.3682.
* 1999: 75 targets; EP wins; +11.3083/+11.3970/−0.0887.
* 2004: 30 targets; EP wins; +1.4237/−0.1897/+1.6134.
* 2010: 125 targets; EP loses; −5.6229/−6.0147/+0.3918.
* 2019: 127 targets; EP wins; +26.1693/+26.3067/−0.1374.

Active plus complement equals the full contrast to \(10^{-10}\) nats, and the
active and complement target counts sum to each block total. EP has the highest
stored joint score in the 1994, 1999, 2004 and 2019 blocks and the lowest in
2010, as stated.

All eight JMA trend rows match the authority. Free-trend versus \(d=0\) pooled
values are:

| Trend | OC−FC timing | OC−EP timing | OC−EP joint |
|---|---:|---:|---:|
| free | −58.5935 | −7.7256 | −221.2115 |
| \(d=0\) | −37.9115 | −13.5846 | −222.2269 |

The free and stationary fold columns sum to the pooled rows, and all 1,277
targets are shared across the trend alternatives.

## 7. Conditional simulation diagnostics (S05)

### 7.1 Three-origin summary

The frozen OC experiment completed **999** paths at each of three origins,
**2,997** total, with zero failed and zero unknown. Each origin has 84 recorded
coordinates. The count, supplied count interval and insertion interval are:

| Origin | Count | Supplied interval | Insertion |
|---|---:|---:|---:|
| Early | 79 | 121–453 | [0.001, 0.001] |
| Middle | 167 | 90–398 | [0.704, 0.712] |
| Late | 69 | 69–279 | [0.021, 0.028] |

The early gap KS 0.222245 and spatial KS 0.167335 exceed all 999 references,
while its time event-logsum insertion is 0.583, censored tail 0.111 and
within-cell absolute maximum 0.187. The middle yearly counts are 12, 4, 8, 116
and 27; its subblock-balance maximum has insertion 0.998, serial dependence
exceeds all references, and the location and within-cell scores have insertions
0.364 and 0.312. The late gap KS and spatial KS have insertions 0.676 and 0.810,
while serial dependence is 0.998, spatial cross dependence 0.992 and
dimensionless location variance exceeds all references.

Cell 4 contains 15, 7 and 8 events against conditional allocations of
23.493717, 16.132286 and 14.770085, with count-minus-allocation insertion ranks
0.074, 0.029 and 0.047. The early empty cell 8 has 562 ties and insertion
[0.001, 0.563]; the middle cell 7 count 124 has insertion 0.992; the late cell 3
count-minus-allocation +5.305104 has insertion 0.991. Immigrant exposure ties
identically across all 999 paths; exposure minus trigger exposure equals that
fixed immigrant term, and the exposure and trigger-exposure ranks coincide at
every origin.

### 7.2 All 252 coordinate rows

All 252 Appendix B.10 rows (84 per origin) were parsed and compared with the
approved scalar report: observed value, inclusive \(L\), inclusive \(H\), tie
count, insertion interval and reference interval. **252/252 match** within their
display precision. The `immigrant_exposure` row is marked `(fixed)` in every
origin, and its interval is [0.001, 1.000] by construction.

### 7.3 Omnibus statistics and closure

| Model | Fold | Conditional \(N\) | Min-rank | Quadratic | Fisher-type |
|---|---|---:|---:|---:|---:|
| OC | 0 | 0.002 | 0.070 | 0.004 | 0.001 |
| OC | 1 | 0.594 | 0.075 | 0.003 | 0.004 |
| OC | 2 | 0.056 | 0.069 | 0.007 | 0.012 |
| EP | 0 | 0.002 | 0.070 | 0.004 | 0.002 |
| EP | 1 | 0.698 | 0.075 | 0.005 | 0.006 |
| EP | 2 | 0.036 | 0.069 | 0.009 | 0.008 |

Every origin retains 82 stochastic coordinates; each quadratic and Fisher
statistic has exactly one value equal to the observed statistic. All six
continuous omnibus tests reject at 5%, and no minimum-rank test does. The
implementation matches the reported definitions: ridge \(10^{-8}\), eight
declared coordinates, symmetric observed-plus-999 standardization, inclusive
upper pooled rank, and Fisher \(=-\sum_j\log\widetilde p_j\).

The independent closure covered 5,994 point-score paths and 15 full-vector EP
paths with 84 coordinates and 11 event-detail columns. The maxima are:

```text
point score          1.1714291758835316e-09 nats
full-vector score    9.0949470177292820e-12
other diagnostic     8.1854523159563540e-12
spatial CDF          6.6613381477509390e-15
event log            1.1013412404281553e-13
gap                  1.1546319456101628e-14
```

All agree with `S05_public.json`, `S05_independent_replay_public.json` and
`S05_CLOSURE_REVIEW.json`.

## 8. Confirmed repairs

### 8.1 Raw math tokens in Chapter 11

**Locator:** `paper/source/chapters/11_external_transfer_benchmarks.tex`,
lines 37, 91, 123, 171, 173, 180, 183, 203, 208, 215, 218, 224, 256, 323 and
325.

The split tokens `M $\geq$ 4.0`, `M $\geq$ 4.5`, `M $\geq$ 6`, `M5.0`, `Mw`,
`Beta` and `r = 0.7`, the raw anchor phrase `at u satisfies u < t $\leq$ u + 30
days`, and the raw scientific notation `8.19e-11`, `1.13e-11`, `4.55e-13`,
`1.82e-10`, `1e-4` and `3.75e-5` were replaced by
`$M\geq 4.0$`, `$M\geq 4.5$`, `$M\geq 6$`, `$M\,5.0$`,
`$M_{\mathrm w}$`, `The rate $\beta$`, `$r=0.7$`,
`$u<t\leq u+30$~days`, `$8.19\times10^{-11}$`,
`$1.13\times10^{-11}$`, `$4.55\times10^{-13}$`,
`$1.82\times10^{-10}$`, `$10^{-4}$` and `$3.75\times10^{-5}$`.
The byte-level comparison against the pre-change zip confirms that every
pre-existing scalar numeric literal survives; only presentation changed.

### 8.2 Threshold tokens in Appendix B.9

**Locator:** `paper/source/appendix_tables/ch11_backup.tex`, lines 5 and 70.
The two split threshold phrases were normalized to `$M\geq 4.0$` and
`$M\geq 4.5$`.

### 8.3 Raw scientific notation in the S05 closure table

**Locator:** `paper/source/chapters/12_s05_completed.tex`, closure table.
The six maxima were formatted as math-mode values. The numeric values and the
claim-ledger bindings are unchanged.

### 8.4 Raw scientific notation in Appendix B.10

**Locator:** `paper/source/appendix_tables/ch12_audit.tex`, independent
computational audit paragraph.
Three audit maxima and the raw tolerance were formatted as
`$2.2737367544323206\times10^{-12}$`, `$3.410605131648481\times10^{-13}$`,
`$6.217248937900877\times10^{-15}$` and `$10^{-4}$`.

### 8.5 Telescoping clarification in S03

**Locator:** `paper/source/chapters/11_s03_completed.tex`, penultimate
paragraph.

The old sentence correctly said that \((2-1)+(3-2)+(4-2)\) is not the total but
did not identify the discrepancy. The audit verified in every fold that
\((4-1)=(2-1)+(4-2)\), that \((4-1)=(2-1)+(3-2)+(4-3)\), and that the
non-telescoping sum exceeds \((4-1)\) by exactly \((3-2)\). The paragraph now
states that the intermediate differences telescope, that the second expression
counts the \((3-2)\) step twice, and that arm 4 inherits arm 2's background so
\((4-3)\) is not a pure tail effect.

### 8.6 No remaining raw notation in the Slice 4 sources

A regular-expression sweep over the eight Slice 4 `.tex` files finds no
remaining `M $\geq$`, `r = 0.7`, `M5.0`, ` Mw`, ` Beta`, or bare
`d.dddd e±dd` scientific-notation token outside math mode.

## 9. Build, claim ledger, and repository checks

The paper was rebuilt with Tectonic 0.17.0 from the repaired sources:

```text
pages                      252
undefined references       0
undefined citations        0
missing figures            0
overfull boxes             0
overfull vertical boxes    0
missing glyph warnings     0
replacement characters     0
PDF SHA-256                86831b75734eda345f3be03803bc88fa64d54038946bc1a901407885c579f1ba
```

The claim ledger reconciles **3,604** Slice 4 records across the eight sources,
with **0** missing declared manuscript displays. The full ledger resolves
12,718 literal manuscript display records with no failure. The repository check
covers 10,908 files with no payload mismatch. The complete test rosters pass:
918 main tests, 44 regional-input tests, 6 S02 input tests, 80 website selector
combinations, both input verifiers, the historical-fit verifier and all seven
review slices.

## 10. Limitations

* The audit recomputes saved quantities and deterministic algebra; it does not
  rerun the historical optimizers, simulate catalogues, or reconstruct every
  raw history. The JMA raw-record counts are checked against the preserved
  expected arrays and selection code, not by re-parsing all 4,019,138 source
  records in this run.
* The S05 public aggregate does not expose the eight-coordinate vectors. The
  quadratic and Fisher statistics are checked against the public JSON, the
  retained-coordinate table and the executable definitions, but are not
  recomputed from the 999 simulated vectors. The six minimum-rank p-values
  coincide across models at each origin (0.070, 0.075, 0.069). The source
  projection review asserts exact source-to-public identity for all six rows,
  and tie-heavy discrete coordinates can produce this coincidence; the audit
  found no transcription duplication but cannot re-derive the private rank
  curves.
* The paired block intervals remain conditional on the saved fits and the
  declared block geometry. Calendar blocks are dependent, and the sign-flip
  reference is not a sequence-level randomization.
* The 7/6/2 lower-bound background-slope counts and the 41,277-plus-one
  adjudication split are documentary statements bound to the forecast-findings
  narrative; the aggregate JSON supplies the total counts, not those partitions.
* The S06 episode-origin roster and block-end rules are retrospective. The audit
  verifies the final rows, partition arithmetic and shared target populations,
  not the original optimizer runs.
* The S03 regional totals are descriptive sums over six archived folds and are
  not independent replications. Arm 4 inherits arm 2's background, so
  \((4-3)\) is not a pure offspring-tail contrast.
* The conditional diagnostics are fixed-state and per-origin. They do not form a
  cross-origin joint null and do not include fitting, selection or catalogue
  uncertainty.

## 11. Artifacts

```text
audit script     experiments/methodological_audit/slice4_audit_20261114.py
audit package    validation/live_results/slice4_audit_20261114/
snapshot         validation/slice4_prechange_snapshot_20261114.json
snapshot zip     validation/slice4_prechange_snapshot_20261114.zip
manuscript       paper/manuscript_unified.pdf
claim ledger     validation/MASTER_CLAIM_LEDGER.json
review bundle    ../review_slices/slice_4_regional_transfer_and_calibration/
```
