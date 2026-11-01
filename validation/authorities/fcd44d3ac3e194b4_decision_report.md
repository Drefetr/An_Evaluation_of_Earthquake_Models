# Audited C1 comparison

All three folds, four models (12 case fits), and 96 prescribed starts are complete. The same 612 held-out targets are scored once per model.

| Comparison | Regional timing | Conditional zone | Magnitude | Joint nats | Nats/event | Positive folds |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| E0_local-E0_global | 1.828190 | 347.958257 | 0.000000 | 349.786446 | 0.571546 | 3/3 |
| I0_local-I0_global | 17.936860 | 346.636237 | 0.000000 | 364.573096 | 0.595708 | 3/3 |
| I0_local-E0_local | -2.077741 | -1.322020 | 0.000000 | -3.399761 | -0.005555 | 0/3 |
| I0_global-E0_global | -18.186411 | -0.000000 | 0.000000 | -18.186411 | -0.029716 | 0/3 |
| (I0_local-E0_local)-(I0_global-E0_global) | 16.108670 | -1.322020 | 0.000000 | 14.786650 | 0.024161 | 2/3 |

## Per-fold comparisons

| Fold | Comparison | Events | Event | Compensator | Regional timing | Conditional zone | Joint |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| 0 | E0_local-E0_global | 203 | 103.290302 | 1.814245 | -2.083237 | 107.187783 | 105.104546 |
| 0 | I0_local-I0_global | 203 | 134.194282 | -12.308863 | 14.073801 | 107.811619 | 121.885419 |
| 0 | I0_local-E0_local | 203 | -3.000762 | 2.792900 | -0.831697 | 0.623835 | -0.207862 |
| 0 | I0_global-E0_global | 203 | -33.904743 | 16.916008 | -16.988735 | -0.000000 | -16.988735 |
| 1 | E0_local-E0_global | 155 | 113.700152 | 5.300826 | 1.797562 | 117.203415 | 119.000978 |
| 1 | I0_local-I0_global | 155 | 116.118709 | -0.282139 | 0.579009 | 115.257560 | 115.836570 |
| 1 | I0_local-E0_local | 155 | 0.385632 | -3.577528 | -1.246041 | -1.945855 | -3.191896 |
| 1 | I0_global-E0_global | 155 | -2.032925 | 2.005437 | -0.027488 | 0.000000 | -0.027488 |
| 2 | E0_local-E0_global | 254 | 121.605937 | 4.074985 | 2.113864 | 123.567058 | 125.680922 |
| 2 | I0_local-I0_global | 254 | 126.523258 | 0.327849 | 3.284049 | 123.567058 | 126.851107 |
| 2 | I0_local-E0_local | 254 | -0.000004 | 0.000001 | -0.000003 | -0.000000 | -0.000003 |
| 2 | I0_global-E0_global | 254 | -4.917325 | 3.747137 | -1.170188 | -0.000000 | -1.170188 |
| 0 | (I0_local-E0_local)-(I0_global-E0_global) | 203 | 30.903980 | -14.123107 | 16.157038 | 0.623835 | 16.780873 |
| 1 | (I0_local-E0_local)-(I0_global-E0_global) | 155 | 2.418557 | -5.582965 | -1.218553 | -1.945855 | -3.164408 |
| 2 | (I0_local-E0_local)-(I0_global-E0_global) | 254 | 4.917321 | -3.747136 | 1.170185 | -0.000000 | 1.170185 |

## Exact zone decomposition

| Fold | Comparison | Zone | Events | Event | Compensator | Sum |
| --- | --- | --- | ---: | ---: | ---: | ---: |
| 0 | E0_local-E0_global | south | 43 | 24.405139 | 2.404472 | 26.809611 |
| 0 | E0_local-E0_global | central | 37 | -2.324219 | 17.184730 | 14.860511 |
| 0 | E0_local-E0_global | north | 123 | 81.209382 | -17.774958 | 63.434424 |
| 0 | I0_local-I0_global | south | 43 | 37.073350 | -1.660382 | 35.412968 |
| 0 | I0_local-I0_global | central | 37 | 9.426961 | 10.777919 | 20.204880 |
| 0 | I0_local-I0_global | north | 123 | 87.693971 | -21.426400 | 66.267571 |
| 0 | I0_local-E0_local | south | 43 | 0.532678 | -0.243298 | 0.289381 |
| 0 | I0_local-E0_local | central | 37 | -0.366395 | 0.224714 | -0.141682 |
| 0 | I0_local-E0_local | north | 123 | -3.167045 | 2.811484 | -0.355561 |
| 0 | I0_global-E0_global | south | 43 | -12.135533 | 3.821557 | -8.313976 |
| 0 | I0_global-E0_global | central | 37 | -12.117576 | 6.631525 | -5.486051 |
| 0 | I0_global-E0_global | north | 123 | -9.651634 | 6.462926 | -3.188708 |
| 1 | E0_local-E0_global | south | 115 | 130.410424 | -109.593918 | 20.816506 |
| 1 | E0_local-E0_global | central | 23 | -12.079179 | 40.279296 | 28.200117 |
| 1 | E0_local-E0_global | north | 17 | -4.631094 | 74.615449 | 69.984355 |
| 1 | I0_local-I0_global | south | 115 | 128.878421 | -108.751927 | 20.126494 |
| 1 | I0_local-I0_global | central | 23 | -9.140462 | 36.040451 | 26.899990 |
| 1 | I0_local-I0_global | north | 17 | -3.619251 | 72.429337 | 68.810086 |
| 1 | I0_local-E0_local | south | 115 | -2.772782 | 1.283665 | -1.489117 |
| 1 | I0_local-E0_local | central | 23 | 2.629575 | -3.622093 | -0.992518 |
| 1 | I0_local-E0_local | north | 17 | 0.528839 | -1.239100 | -0.710261 |
| 1 | I0_global-E0_global | south | 115 | -1.240779 | 0.441674 | -0.799105 |
| 1 | I0_global-E0_global | central | 23 | -0.309142 | 0.616751 | 0.307609 |
| 1 | I0_global-E0_global | north | 17 | -0.483004 | 0.947012 | 0.464008 |
| 2 | E0_local-E0_global | south | 66 | -1.362564 | 33.690369 | 32.327805 |
| 2 | E0_local-E0_global | central | 129 | 108.705988 | -54.800036 | 53.905952 |
| 2 | E0_local-E0_global | north | 59 | 14.262513 | 25.184652 | 39.447165 |
| 2 | I0_local-I0_global | south | 66 | 0.601783 | 32.405313 | 33.007096 |
| 2 | I0_local-I0_global | central | 129 | 110.286359 | -55.812162 | 54.474197 |
| 2 | I0_local-I0_global | north | 59 | 15.635116 | 23.734698 | 39.369814 |
| 2 | I0_local-E0_local | south | 66 | -0.000003 | 0.000001 | -0.000002 |
| 2 | I0_local-E0_local | central | 129 | -0.000001 | -0.000000 | -0.000001 |
| 2 | I0_local-E0_local | north | 59 | -0.000001 | 0.000001 | -0.000000 |
| 2 | I0_global-E0_global | south | 66 | -1.964350 | 1.285058 | -0.679292 |
| 2 | I0_global-E0_global | central | 129 | -1.580371 | 1.012125 | -0.568246 |
| 2 | I0_global-E0_global | north | 59 | -1.372604 | 1.449955 | 0.077351 |
| 0 | (I0_local-E0_local)-(I0_global-E0_global) | south | 43 | 12.668211 | -4.064854 | 8.603357 |
| 0 | (I0_local-E0_local)-(I0_global-E0_global) | central | 37 | 11.751180 | -6.406811 | 5.344369 |
| 0 | (I0_local-E0_local)-(I0_global-E0_global) | north | 123 | 6.484589 | -3.651442 | 2.833147 |
| 1 | (I0_local-E0_local)-(I0_global-E0_global) | south | 115 | -1.532003 | 0.841991 | -0.690012 |
| 1 | (I0_local-E0_local)-(I0_global-E0_global) | central | 23 | 2.938717 | -4.238844 | -1.300127 |
| 1 | (I0_local-E0_local)-(I0_global-E0_global) | north | 17 | 1.011843 | -2.186112 | -1.174269 |
| 2 | (I0_local-E0_local)-(I0_global-E0_global) | south | 66 | 1.964347 | -1.285057 | 0.679291 |
| 2 | (I0_local-E0_local)-(I0_global-E0_global) | central | 129 | 1.580371 | -1.012126 | 0.568245 |
| 2 | (I0_local-E0_local)-(I0_global-E0_global) | north | 59 | 1.372603 | -1.449954 | -0.077351 |

## Scope

K=3 fixed latitude zones, raw local stress, fixed ML excitation and r=.7, omega=0. Background proportions and magnitude nuisance use training only. Local triggering and local inhibition are compared with matched global/local excitation controls. Joint gains can come from zone prediction without improved regional timing; the two components must not be conflated.

The C1 model does not define within-zone cell probabilities, so cell event crosswalks have no invented cell compensators. Full compensator differences are reported per zone. Historical Iteration28 cell event penalties and recipe differences are retained separately in historical_reconciliation.json.

All comparisons are retrospective on previously examined chronological windows. No physical causality, event-iid confidence interval, Wilks boundary test, or global optimum guarantee is claimed. No follow-up model/kernel/productivity search or other stage was run.
