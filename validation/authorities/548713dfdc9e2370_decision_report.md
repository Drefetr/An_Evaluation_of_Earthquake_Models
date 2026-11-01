# Original California OC: conditional diagnostic decision report

The complete reference shows material count, temporal and spatial discrepancies for the original frozen Omori continuous (OC) forecast, alongside some ordinary-looking diagnostics. It does not support a broad adequacy claim. This is a retrospective, exploratory, fixed-state conditional check of 315 already inspected targets: 79, 167 and 69 in [2011,2016), [2016,2021) and [2021,2026). No parameters or nuisance choices were refitted.

The target remains original OC, with its density-weighted rational offspring spatial kernel and smooth background. Thread01's separately fitted optimized smooth inverse-power ETAS comparator (EP) exceeded OC by 51.051204763 pooled joint nats. That relative predictive comparison did not replace the frozen target, and it does not establish EP's adequacy. These diagnostics do not calibrate EP.

## Reference and interpretation

Each origin has 999 complete dependent branching-future paths, conditional on its own original prehistory and fitted/nuisance state. All 2,997 planned paths are complete; failed and unknown counts are both zero. Simulated events can generate descendants. Sequential observed scores use every strictly earlier admissible event. The issue-frozen NHPP is a different forecast object and has no empirical arm here. The observed-path exposure is a realised predictable compensator, not a Poisson future-count mean.

For every coordinate the appendix reports observed value, inclusive counts L=#(simulation<=observed), H=#(simulation>=observed), ties, insertion interval and supplied empirical reference interval. Insertion interval is [(1+#<)/1000,(1+#<=)/1000]; inclusive lower and upper tails are (1+L)/1000 and (1+H)/1000. Resolution is 0.001. A boundary rank is a finite comparison, not a zero probability or an exact population tail probability. Ties can make insertion intervals wide. All 84 coordinates per origin form one descriptive collection; individual tails are not separate unadjusted discoveries, and no omnibus significance test is asserted. Reference intervals describe simulated catalogues, not confidence intervals for fitted parameters or model validity.

## What the complete vector shows

Early origin: count 79 is below all 999 simulated counts (L=0,H=999,ties=0; insertion 0.001), with supplied count reference interval 121 to 453. Exposure 114.54932024184329 and trigger exposure 38.82182627332281 are also below all references. Count minus exposure is -35.54932024184329 (L=10,H=989; insertion 0.011). Gap KS 0.22224496322920195 and gap serial statistic 0.025311536051231393 both exceed every reference. Spatial Rosenblatt KS 0.16733517789142327 exceeds every reference; location dimensionless mean 2.4494637138726643 is below all references and variance 10.653917170486158 is above all. Yet time event-logsum insertion is 0.583, censored tail 0.111 and within-cell absolute maximum 0.187. The second year count 30 has insertion interval [0.370,0.409], with 39 ties. This is not uniformly poor on every coordinate.

Middle origin: total count 167 looks ordinary in its reference (L=711,H=296,ties=8; insertion [0.704,0.712], supplied count interval 90 to 398). Balance -4.373290651999895 has insertion 0.391. This total hides subblock concentration: yearly counts are 12,4,8,116,27; subblock balance maximum 0.6836875842626084 has L=997,H=2 and insertion 0.998. The fourth year's balance is +25.931179418686256 (insertion 0.998). Gap KS 0.15088891163993823 has H=8; serial 0.05049115130656217 exceeds all 999. Spatial KS 0.16932136137657972 has H=4, cross statistic 0.027677364202278305 exceeds all 999, and cell-mass residual maximum 1.278459418085198 has H=11. Conditional-location logscore insertion 0.364, within-cell density score 0.312, terminal tail 0.237 and within-cell absolute maximum 0.341 illustrate ordinary-looking components alongside those discrepancies.

Late origin: count 69 lies toward the low end (L=27,H=979,ties=7; insertion [0.021,0.028], supplied interval 69 to 279). Exposure 82.98011402768624 has insertion 0.012, while balance -13.980114027686241 has insertion 0.110. Gap KS 0.0881227829042357 has insertion 0.676, spatial KS 0.1129696501693383 has insertion 0.810 and terminal tail 1.586732938471152 has insertion 0.700. However serial statistic 0.02308692546525953 has H=2 (insertion 0.998), spatial cross statistic 0.021671079327220788 has H=8 (0.992), and dimensionless location variance 12.30394407102264 exceeds all references. Within-cell absolute maximum has insertion 0.499. A reasonable marginal shape statistic therefore does not settle dependence or concentration.

Across the descriptive cell tables, cell 4 counts are 15,7,8 against conditional expected allocations 23.493716546234523,16.132286198379887,14.770085109767768. These allocations sum conditional probabilities at the observed event times; they are not unconditional count means. Their count-minus-allocation values have insertion ranks 0.074,0.029,0.047. Other cells differ in direction: middle cell 7 count 124 has insertion 0.992, and late cell 3 count-minus-allocation +5.305104300093006 has insertion 0.991. Empty cells often tie extensively: early cell 8 count zero has 562 ties and insertion [0.001,0.563], so its lower endpoint alone is misleading.

Raw total log scores depend on the number of events and the score measure. For example early joint and location log scores exceed all reference totals while count is below all references; this is not evidence of adequate probabilities. Dimensionless location summaries, allocation residuals and spatial transforms provide complementary information. Immigrant exposure is deterministic within each fixed state: all 999 references tie at 75.72749396852048,65.12820992122843,51.19150695498898 respectively. Its [0.001,1.000] insertion interval is expected by construction, not an adequacy result. Mark totals also vary with count and do not independently validate the mark or productivity recipe.

## Independent audit and limits

The independent campaign audit passed identity/hash/status/seed checks and all-path raw count, mark and temporal-exposure checks for 2,997 paths. The full 84-coordinate raw diagnostic replay was sampled: indices 0,499,998 in each origin, nine complete paths. Maximum sampled absolute score difference was 2.2737367544323206e-12 nats (gate 1e-4); maximum non-score difference 3.410605131648481e-13 and spatial CDF difference 6.217248937900877e-15. This does not mean all 2,997 paths received full-vector independent replay. Original observed reconstructions are separately bound by the approved report's execution and oracle receipt hashes. Numerical agreement checks implementation; it does not validate the forecast's scientific adequacy.

The fitted state, training history and nuisance choices are fixed; fitting, selection, measurement and catalogue-revision uncertainty are excluded. Later observed training histories include earlier target periods, so independent per-origin simulations do not define a coherent cross-origin joint null. Cross-window patterns and any pooled quantities remain descriptive. There is no event-iid confidence interval, Wilks inference, causal triggering conclusion, untouched holdout, general calibration or validation claim. Heavy-tailed productivity has infinite second moment under the fixed mark recipe; normal/CLT count arguments are not used. Terminal exposure is censored survival information, never an added completed gap. No observed rounding model, post-observation metric choice or seed extension was introduced.

## Evidence and transition

The sole numerical reporting input is [approved scalar report](../results/approved_analysis_v1/approved_scalar_report.json), SHA256 `731a4a1481fc4dee9297a8cccba6012f1096803f5551171501f22bbd64233f93`. Definitions are in [frozen protocol](../design/scientific_protocol_v1.json), [fixed methods](../design/methods_protocol_draft_v1.md) and [independent design](../methods/independent_validation_design_v1.md). Audit evidence is [campaign audit](../reviews/production_campaign_audit_v1.json). The [complete HTML table](diagnostic_tables.html) and the appendix cover all 252 coordinates. Rendering-only revised rank figures are [early](../results/approved_analysis_v1/plots_v2/origin_01.png), [middle](../results/approved_analysis_v1/plots_v2/origin_02.png), [late](../results/approved_analysis_v1/plots_v2/origin_03.png); the JSON, rather than plotted glyphs, is authoritative.

Carry these limits and discrepant as well as ordinary-looking coordinates into authorized Thread03, "Score concentration and catalogue robustness" (`research_runs/score_robustness_20261025T102500Z`). Its first stage is exact saved-score decomposition into 15 annual UTC blocks, retaining full inherited history and four original arms (60 arm-block rows and 45 contrast rows). Independent reconciliation must be accepted before the provenance/observation-law inventory and separately admitted feasible sensitivity scenarios. Thread03 numerical work waits for the Thread02 seal; source preparation is pinned to commit `107b5c43aa9d343280bf6e21b39eee1dae0124cf`. Do not silently change the original target or rename these inspected outcomes as a holdout. This report launches no new scientific computation, optional Thread04/06, manuscript edits or live operations; New Zealand prospective pins, daily history policy and interim scoring remain untouched.

## Complete coordinate appendix

Years are chronological, zero-based within each five-year window. Cells 0 to 8 are row-major latitude then longitude. Values below preserve the approved JSON's numeric representations. Every row has planned=complete=999 and failed/unknown=0. RI denotes the supplied empirical reference interval; it is not an inferential acceptance band.

### california_fold_0

| Coordinate | Observed | L | H | Ties | Insertion interval | RI |
|---|---:|---:|---:|---:|---|---|
| count | 79.0 | 0 | 999 | 0 | [0.001, 0.001] | [121.0, 453.0] |
| exposure | 114.54932024184329 | 0 | 999 | 0 | [0.001, 0.001] | [135.56781665968998, 486.7588373636398] |
| immigrant_exposure | 75.72749396852048 | 999 | 999 | 999 | [0.001, 1.0] | [75.72749396852048, 75.72749396852048] |
| trigger_exposure | 38.82182627332281 | 0 | 999 | 0 | [0.001, 0.001] | [59.840322691169504, 411.03134339511934] |
| count_minus_exposure | -35.54932024184329 | 10 | 989 | 0 | [0.011, 0.011] | [-27.688296280024673, 30.060444876918297] |
| time_event_logsum | -176.45877385777717 | 582 | 417 | 0 | [0.583, 0.583] | [-286.5127593466273, 722.9245098523315] |
| timing_logscore | -291.00809409962045 | 832 | 167 | 0 | [0.833, 0.833] | [-457.2451094458201, 177.5294078363986] |
| location_logscore | -816.4419063302124 | 999 | 0 | 0 | [1.0, 1.0] | [-3711.0572699039108, -1114.3627523187763] |
| mark_logscore | 6.457475253738915 | 995 | 4 | 0 | [0.996, 0.996] | [-99.96431904129243, -0.7288862827928956] |
| joint_logscore | -1100.992525176094 | 999 | 0 | 0 | [1.0, 1.0] | [-3577.5107710811094, -1463.1505681205665] |
| zone_logscore | -74.79271735349445 | 993 | 6 | 0 | [0.994, 0.994] | [-165.84118963728275, -82.98806536238033] |
| cell_given_zone_logscore | -42.53939693772509 | 989 | 10 | 0 | [0.99, 0.99] | [-118.87048622330485, -46.17417728167845] |
| within_cell_density_logscore | -699.1097920389929 | 999 | 0 | 0 | [1.0, 1.0] | [-3254.5248960319013, -969.2567845105789] |
| subblock_balance_max | 0.46136676667844795 | 960 | 39 | 0 | [0.961, 0.961] | [0.09944111667161903, 0.481693160801643] |
| gap_ks | 0.22224496322920195 | 999 | 0 | 0 | [1.0, 1.0] | [0.03012272248403658, 0.11125043994026007] |
| gap_serial | 0.025311536051231393 | 999 | 0 | 0 | [1.0, 1.0] | [-0.012511698548783354, 0.01266304632110315] |
| censored_tail | 0.3630339660854385 | 110 | 889 | 0 | [0.111, 0.111] | [0.17244313180812987, 4.357424331947924] |
| spatial_rosenblatt_ks_max | 0.16733517789142327 | 999 | 0 | 0 | [1.0, 1.0] | [0.03699319519466915, 0.12049120340149982] |
| spatial_rosenblatt_cross_abs | 0.0136966741515359 | 979 | 20 | 0 | [0.98, 0.98] | [0.00018001394086227071, 0.01341490885545926] |
| cell_mass_residual_max | 0.9447746784159475 | 940 | 59 | 0 | [0.941, 0.941] | [0.273418861521684, 1.2515211643818198] |
| location_dimensionless_log_mean | 2.4494637138726643 | 0 | 999 | 0 | [0.001, 0.001] | [3.2234473115925217, 5.123334810207665] |
| location_dimensionless_log_variance | 10.653917170486158 | 999 | 0 | 0 | [1.0, 1.0] | [5.425324654072042, 8.421187972061608] |
| within_cell_dimensionless_absmax | 6.188942628525362 | 186 | 813 | 0 | [0.187, 0.187] | [6.055966658043472, 6.938326422637497] |
| within_cell_dimensionless_sum | 137.84391668052655 | 0 | 999 | 0 | [0.001, 0.001] | [280.6814319917778, 1543.4569929307852] |
| year_count[0] | 14.0 | 17 | 988 | 6 | [0.012, 0.018] | [16.0, 137.0] |
| year_count[1] | 30.0 | 408 | 630 | 39 | [0.37, 0.409] | [14.0, 102.0] |
| year_count[2] | 13.0 | 16 | 990 | 7 | [0.01, 0.017] | [14.0, 121.0] |
| year_count[3] | 12.0 | 19 | 986 | 6 | [0.014, 0.02] | [14.0, 152.0] |
| year_count[4] | 10.0 | 2 | 998 | 1 | [0.002, 0.003] | [15.0, 137.0] |
| year_exposure[0] | 22.376796828655227 | 7 | 992 | 0 | [0.008, 0.008] | [23.47448643277159, 132.73399495994803] |
| year_exposure[1] | 30.686684581233745 | 382 | 617 | 0 | [0.383, 0.383] | [22.422534581447284, 104.07887702721173] |
| year_exposure[2] | 20.85718067996815 | 4 | 995 | 0 | [0.005, 0.005] | [22.424870871252423, 111.5897073502337] |
| year_exposure[3] | 21.20659853979513 | 10 | 989 | 0 | [0.011, 0.011] | [22.41757906171992, 150.93798209710098] |
| year_exposure[4] | 19.42205961219115 | 0 | 999 | 0 | [0.001, 0.001] | [22.965845702595516, 124.5939919157942] |
| year_count_minus_exposure[0] | -8.376796828655227 | 65 | 934 | 0 | [0.066, 0.066] | [-10.409708307173904, 14.720681474321005] |
| year_count_minus_exposure[1] | -0.6866845812337452 | 470 | 529 | 0 | [0.471, 0.471] | [-10.12019725563626, 14.01571834603979] |
| year_count_minus_exposure[2] | -7.857180679968149 | 88 | 911 | 0 | [0.089, 0.089] | [-10.826951548899455, 14.850002010381985] |
| year_count_minus_exposure[3] | -9.20659853979513 | 64 | 935 | 0 | [0.065, 0.065] | [-11.397232320108188, 14.903882136855415] |
| year_count_minus_exposure[4] | -9.422059612191148 | 40 | 959 | 0 | [0.041, 0.041] | [-10.328733639724032, 17.671626878222014] |
| cell_count[0] | 1.0 | 898 | 288 | 187 | [0.712, 0.899] | [0.0, 5.0] |
| cell_count[1] | 5.0 | 325 | 763 | 89 | [0.237, 0.326] | [1.0, 41.0] |
| cell_count[2] | 39.0 | 169 | 852 | 22 | [0.148, 0.17] | [27.0, 178.0] |
| cell_count[3] | 2.0 | 260 | 854 | 115 | [0.146, 0.261] | [0.0, 23.0] |
| cell_count[4] | 15.0 | 0 | 999 | 0 | [0.001, 0.001] | [35.0, 218.0] |
| cell_count[5] | 2.0 | 12 | 994 | 7 | [0.006, 0.013] | [3.0, 42.0] |
| cell_count[6] | 7.0 | 660 | 414 | 75 | [0.586, 0.661] | [1.0, 31.0] |
| cell_count[7] | 8.0 | 227 | 834 | 62 | [0.166, 0.228] | [4.0, 56.0] |
| cell_count[8] | 0.0 | 562 | 999 | 562 | [0.001, 0.563] | [0.0, 5.0] |
| cell_conditional_expected[0] | 0.2647945182900121 | 22 | 977 | 0 | [0.023, 0.023] | [0.2666052733668406, 2.603460878202516] |
| cell_conditional_expected[1] | 3.3976540629284036 | 0 | 999 | 0 | [0.001, 0.001] | [4.203365563424513, 38.48659812564885] |
| cell_conditional_expected[2] | 34.778158367404565 | 49 | 950 | 0 | [0.05, 0.05] | [32.78032806070707, 180.08595479196129] |
| cell_conditional_expected[3] | 2.422055911117281 | 0 | 999 | 0 | [0.001, 0.001] | [2.771681076825427, 21.786267799155535] |
| cell_conditional_expected[4] | 23.493716546234523 | 0 | 999 | 0 | [0.001, 0.001] | [39.12496071200316, 218.36004275645092] |
| cell_conditional_expected[5] | 5.337864672917706 | 0 | 999 | 0 | [0.001, 0.001] | [7.365463191605454, 39.43901253984584] |
| cell_conditional_expected[6] | 3.113587084811356 | 40 | 959 | 0 | [0.041, 0.041] | [3.006728211407283, 27.222918232797394] |
| cell_conditional_expected[7] | 5.784266222966054 | 1 | 998 | 0 | [0.002, 0.002] | [7.40275632074073, 53.288426628438934] |
| cell_conditional_expected[8] | 0.40790261333009664 | 0 | 999 | 0 | [0.001, 0.001] | [0.4830737693812487, 4.032504088632105] |
| cell_exposure[0] | 0.5589116883814972 | 837 | 162 | 0 | [0.838, 0.838] | [0.32112946757755223, 2.055081610926935] |
| cell_exposure[1] | 5.719352151731332 | 149 | 850 | 0 | [0.15, 0.15] | [4.993538456150598, 37.889329529159085] |
| cell_exposure[2] | 43.19828369968258 | 134 | 865 | 0 | [0.135, 0.135] | [37.60580202507246, 176.19306610198356] |
| cell_exposure[3] | 4.015741066788378 | 317 | 682 | 0 | [0.318, 0.318] | [3.1728890134253174, 20.745315784142864] |
| cell_exposure[4] | 36.140422500336605 | 0 | 999 | 0 | [0.001, 0.001] | [45.59695125821622, 209.27705562433047] |
| cell_exposure[5] | 7.846269555471099 | 2 | 997 | 0 | [0.003, 0.003] | [8.538530113522986, 38.811637035076174] |
| cell_exposure[6] | 6.715148057868313 | 666 | 333 | 0 | [0.667, 0.667] | [3.5637389432700464, 27.117065393712377] |
| cell_exposure[7] | 9.773139729390087 | 103 | 896 | 0 | [0.104, 0.104] | [8.740612330015475, 47.38112115160922] |
| cell_exposure[8] | 0.5820517921935396 | 0 | 999 | 0 | [0.001, 0.001] | [0.582164072460521, 3.1967783307259605] |
| cell_count_minus_conditional_expected[0] | 0.7352054817099879 | 918 | 81 | 0 | [0.919, 0.919] | [-0.38686986708704685, 2.1547083180763016] |
| cell_count_minus_conditional_expected[1] | 1.6023459370715964 | 744 | 255 | 0 | [0.745, 0.745] | [-4.116390628832374, 5.823729765011256] |
| cell_count_minus_conditional_expected[2] | 4.221841632595435 | 808 | 191 | 0 | [0.809, 0.809] | [-10.355010149947496, 9.623147958963415] |
| cell_count_minus_conditional_expected[3] | -0.422055911117281 | 473 | 526 | 0 | [0.474, 0.474] | [-3.2166921552927823, 4.604727467672985] |
| cell_count_minus_conditional_expected[4] | -8.493716546234523 | 73 | 926 | 0 | [0.074, 0.074] | [-11.078423529070989, 10.79246464937944] |
| cell_count_minus_conditional_expected[5] | -3.337864672917706 | 139 | 860 | 0 | [0.14, 0.14] | [-5.785349580687853, 6.840442166685648] |
| cell_count_minus_conditional_expected[6] | 3.886412915188644 | 940 | 59 | 0 | [0.941, 0.941] | [-3.314071523080734, 5.278763019582419] |
| cell_count_minus_conditional_expected[7] | 2.215733777033946 | 748 | 251 | 0 | [0.749, 0.749] | [-5.472836585757424, 6.7455024422958765] |
| cell_count_minus_conditional_expected[8] | -0.40790261333009664 | 571 | 428 | 0 | [0.572, 0.572] | [-0.6805621354484103, 2.205533482162007] |
| cell_count_minus_exposure[0] | 0.4410883116185028 | 782 | 217 | 0 | [0.783, 0.783] | [-0.3691832281388137, 2.338479441467838] |
| cell_count_minus_exposure[1] | -0.7193521517313322 | 442 | 557 | 0 | [0.443, 0.443] | [-4.479761984146776, 7.522989573173415] |
| cell_count_minus_exposure[2] | -4.198283699682577 | 332 | 667 | 0 | [0.333, 0.333] | [-14.45461606636134, 18.92749887449969] |
| cell_count_minus_exposure[3] | -2.0157410667883777 | 198 | 801 | 0 | [0.199, 0.199] | [-3.206636176638498, 6.013190715980919] |
| cell_count_minus_exposure[4] | -21.140422500336605 | 7 | 992 | 0 | [0.008, 0.008] | [-15.766141894539231, 19.76821724892369] |
| cell_count_minus_exposure[5] | -5.846269555471099 | 32 | 967 | 0 | [0.033, 0.033] | [-6.137660582596705, 8.003330786260012] |
| cell_count_minus_exposure[6] | 0.2848519421316871 | 614 | 385 | 0 | [0.615, 0.615] | [-3.3929276756592155, 6.607890693230699] |
| cell_count_minus_exposure[7] | -1.7731397293900866 | 367 | 632 | 0 | [0.368, 0.368] | [-6.522301836884113, 9.491547923825834] |
| cell_count_minus_exposure[8] | -0.5820517921935396 | 571 | 428 | 0 | [0.572, 0.572] | [-0.6090900590050761, 2.4549863150896107] |

### california_fold_1

| Coordinate | Observed | L | H | Ties | Insertion interval | RI |
|---|---:|---:|---:|---:|---|---|
| count | 167.0 | 711 | 296 | 8 | [0.704, 0.712] | [90.0, 398.0] |
| exposure | 171.3732906519999 | 766 | 233 | 0 | [0.767, 0.767] | [106.12307862508305, 397.7176553930881] |
| immigrant_exposure | 65.12820992122843 | 999 | 999 | 999 | [0.001, 1.0] | [65.12820992122843, 65.12820992122843] |
| trigger_exposure | 106.24508073077146 | 766 | 233 | 0 | [0.767, 0.767] | [40.99486870385462, 332.5894454718597] |
| count_minus_exposure | -4.373290651999895 | 390 | 609 | 0 | [0.391, 0.391] | [-24.36304833015754, 26.37370060343224] |
| time_event_logsum | 326.50433396627767 | 963 | 36 | 0 | [0.964, 0.964] | [-265.1318901939191, 583.3833505216883] |
| timing_logscore | 155.13104331427778 | 971 | 28 | 0 | [0.972, 0.972] | [-404.0987837538697, 178.1639922441339] |
| location_logscore | -1377.2122159660285 | 363 | 636 | 0 | [0.364, 0.364] | [-3078.5327441769778, -854.2404337570142] |
| mark_logscore | -15.03903662108132 | 680 | 319 | 0 | [0.681, 0.681] | [-81.68141991597025, 1.5258857118819078] |
| joint_logscore | -1237.120209272832 | 948 | 51 | 0 | [0.949, 0.949] | [-3090.695760404099, -1158.6666983824693] |
| zone_logscore | -54.351240321737635 | 998 | 1 | 0 | [0.999, 0.999] | [-141.06349727296217, -64.91967824998906] |
| cell_given_zone_logscore | -45.40932366542472 | 852 | 147 | 0 | [0.853, 0.853] | [-94.99759274159192, -36.34467053782302] |
| within_cell_density_logscore | -1277.451651978866 | 311 | 688 | 0 | [0.312, 0.312] | [-2827.300983507339, -745.7810501667373] |
| subblock_balance_max | 0.6836875842626084 | 997 | 2 | 0 | [0.998, 0.998] | [0.1093335581913649, 0.5342755611363699] |
| gap_ks | 0.15088891163993823 | 991 | 8 | 0 | [0.992, 0.992] | [0.03382369741694077, 0.13359889570638359] |
| gap_serial | 0.05049115130656217 | 999 | 0 | 0 | [1.0, 1.0] | [-0.014771943541407762, 0.013331891414106456] |
| censored_tail | 0.6161336957772795 | 236 | 763 | 0 | [0.237, 0.237] | [0.1877093442858882, 4.197445714551701] |
| spatial_rosenblatt_ks_max | 0.16932136137657972 | 995 | 4 | 0 | [0.996, 0.996] | [0.04190715397337763, 0.13574043815306824] |
| spatial_rosenblatt_cross_abs | 0.027677364202278305 | 999 | 0 | 0 | [1.0, 1.0] | [0.00016408038722648556, 0.015467075009819826] |
| cell_mass_residual_max | 1.278459418085198 | 988 | 11 | 0 | [0.989, 0.989] | [0.2905358523199022, 1.1221640823347008] |
| location_dimensionless_log_mean | 4.537391652615119 | 906 | 93 | 0 | [0.907, 0.907] | [3.0267311767975027, 5.1304041165101495] |
| location_dimensionless_log_variance | 8.76988111778304 | 976 | 23 | 0 | [0.977, 0.977] | [5.1386695203907955, 8.729679565946432] |
| within_cell_dimensionless_absmax | 6.212347511740378 | 340 | 659 | 0 | [0.341, 0.341] | [6.004244461245964, 6.929971103980396] |
| within_cell_dimensionless_sum | 488.3608010838824 | 732 | 267 | 0 | [0.733, 0.733] | [205.40046709925653, 1400.596642397477] |
| year_count[0] | 12.0 | 71 | 952 | 24 | [0.048, 0.072] | [10.0, 90.0] |
| year_count[1] | 4.0 | 1 | 999 | 1 | [0.001, 0.002] | [11.0, 84.0] |
| year_count[2] | 8.0 | 8 | 995 | 4 | [0.005, 0.009] | [11.0, 101.0] |
| year_count[3] | 116.0 | 985 | 14 | 0 | [0.986, 0.986] | [11.0, 82.0] |
| year_count[4] | 27.0 | 514 | 525 | 40 | [0.475, 0.515] | [10.0, 78.0] |
| year_exposure[0] | 18.29107124174531 | 73 | 926 | 0 | [0.074, 0.074] | [17.208322515693965, 89.54125377108929] |
| year_exposure[1] | 14.807156947487934 | 0 | 999 | 0 | [0.001, 0.001] | [17.635852582105965, 78.94189519241708] |
| year_exposure[2] | 17.96035065156303 | 26 | 973 | 0 | [0.027, 0.027] | [17.91690200624949, 106.20971472868413] |
| year_exposure[3] | 90.06882058131374 | 980 | 19 | 0 | [0.981, 0.981] | [18.22269860423967, 78.00677749971402] |
| year_exposure[4] | 30.24589122988964 | 643 | 356 | 0 | [0.644, 0.644] | [18.129240503461144, 75.47965941271092] |
| year_count_minus_exposure[0] | -6.2910712417453105 | 100 | 899 | 0 | [0.101, 0.101] | [-9.385635615830058, 12.275381426765385] |
| year_count_minus_exposure[1] | -10.807156947487934 | 13 | 986 | 0 | [0.014, 0.014] | [-9.30059471567419, 11.851754438918626] |
| year_count_minus_exposure[2] | -9.96035065156303 | 15 | 984 | 0 | [0.016, 0.016] | [-9.099935040314975, 12.814569806637579] |
| year_count_minus_exposure[3] | 25.931179418686256 | 997 | 2 | 0 | [0.998, 0.998] | [-8.603574578212452, 13.245250793272206] |
| year_count_minus_exposure[4] | -3.24589122988964 | 323 | 676 | 0 | [0.324, 0.324] | [-9.779299563795927, 11.445485954804372] |
| cell_count[0] | 0.0 | 717 | 999 | 717 | [0.001, 0.718] | [0.0, 4.0] |
| cell_count[1] | 5.0 | 452 | 634 | 87 | [0.366, 0.453] | [1.0, 27.0] |
| cell_count[2] | 17.0 | 13 | 988 | 2 | [0.012, 0.014] | [19.0, 134.0] |
| cell_count[3] | 5.0 | 732 | 343 | 76 | [0.657, 0.733] | [0.0, 20.0] |
| cell_count[4] | 7.0 | 0 | 999 | 0 | [0.001, 0.001] | [25.0, 191.0] |
| cell_count[5] | 3.0 | 80 | 969 | 50 | [0.031, 0.081] | [2.0, 30.0] |
| cell_count[6] | 4.0 | 454 | 626 | 81 | [0.374, 0.455] | [0.0, 27.0] |
| cell_count[7] | 124.0 | 991 | 8 | 0 | [0.992, 0.992] | [2.0, 45.0] |
| cell_count[8] | 2.0 | 947 | 129 | 77 | [0.871, 0.948] | [0.0, 4.0] |
| cell_conditional_expected[0] | 0.19643543552286286 | 0 | 999 | 0 | [0.001, 0.001] | [0.2838224630684332, 2.717009445291833] |
| cell_conditional_expected[1] | 3.2810458048500513 | 8 | 991 | 0 | [0.009, 0.009] | [3.4779819362141984, 24.337725212943887] |
| cell_conditional_expected[2] | 20.528594029053302 | 5 | 994 | 0 | [0.006, 0.006] | [23.484448765896335, 129.7224741434147] |
| cell_conditional_expected[3] | 1.6483874820088815 | 0 | 999 | 0 | [0.001, 0.001] | [2.2429345251889004, 18.50566654358448] |
| cell_conditional_expected[4] | 16.132286198379887 | 0 | 999 | 0 | [0.001, 0.001] | [30.178335673995278, 188.07665797608536] |
| cell_conditional_expected[5] | 3.842886450197055 | 0 | 999 | 0 | [0.001, 0.001] | [5.560330152231931, 25.249585806928852] |
| cell_conditional_expected[6] | 1.9813996560799216 | 0 | 999 | 0 | [0.001, 0.001] | [2.817957403924999, 26.17046239292152] |
| cell_conditional_expected[7] | 119.07228579825917 | 991 | 8 | 0 | [0.992, 0.992] | [5.882854944119923, 43.05442767688772] |
| cell_conditional_expected[8] | 0.3166791456488524 | 1 | 998 | 0 | [0.002, 0.002] | [0.3755219246162881, 3.2375882320898213] |
| cell_exposure[0] | 0.3513802419539744 | 620 | 379 | 0 | [0.621, 0.621] | [0.34628645577116907, 2.4503751631660995] |
| cell_exposure[1] | 6.3740114116565225 | 553 | 446 | 0 | [0.554, 0.554] | [4.150067424618574, 23.38326686640217] |
| cell_exposure[2] | 26.88929036533755 | 9 | 990 | 0 | [0.01, 0.01] | [28.56601816400981, 135.6548372546258] |
| cell_exposure[3] | 4.989623645314049 | 768 | 231 | 0 | [0.769, 0.769] | [2.6199121950608886, 17.811100538518158] |
| cell_exposure[4] | 28.87425541554352 | 0 | 999 | 0 | [0.001, 0.001] | [35.987220040198814, 179.3315674759068] |
| cell_exposure[5] | 6.650028747443474 | 29 | 970 | 0 | [0.03, 0.03] | [6.596111232855201, 21.63402492752512] |
| cell_exposure[6] | 4.618089051216613 | 406 | 593 | 0 | [0.407, 0.407] | [3.218458581081999, 24.28143171327687] |
| cell_exposure[7] | 91.48552733307443 | 988 | 11 | 0 | [0.989, 0.989] | [7.132696069020776, 42.738689903253245] |
| cell_exposure[8] | 1.1410844404595146 | 930 | 69 | 0 | [0.931, 0.931] | [0.45785209918580383, 2.5670785468474246] |
| cell_count_minus_conditional_expected[0] | -0.19643543552286286 | 724 | 275 | 0 | [0.725, 0.725] | [-0.4282078896948201, 2.029422743703944] |
| cell_count_minus_conditional_expected[1] | 1.7189541951499487 | 779 | 220 | 0 | [0.78, 0.78] | [-3.3859908836301367, 5.563524390482268] |
| cell_count_minus_conditional_expected[2] | -3.528594029053302 | 230 | 769 | 0 | [0.231, 0.231] | [-8.642296737263933, 9.322099033688403] |
| cell_count_minus_conditional_expected[3] | 3.3516125179911187 | 942 | 57 | 0 | [0.943, 0.943] | [-2.8012189319513974, 4.550262646195626] |
| cell_count_minus_conditional_expected[4] | -9.132286198379887 | 28 | 971 | 0 | [0.029, 0.029] | [-9.232555110737955, 10.203280839245814] |
| cell_count_minus_conditional_expected[5] | -0.8428864501970552 | 410 | 589 | 0 | [0.411, 0.411] | [-4.914076383173725, 6.045125861313414] |
| cell_count_minus_conditional_expected[6] | 2.0186003439200784 | 850 | 149 | 0 | [0.851, 0.851] | [-3.2286830872120955, 4.453603625744261] |
| cell_count_minus_conditional_expected[7] | 4.927714201740827 | 951 | 48 | 0 | [0.952, 0.952] | [-4.8856258904924506, 5.9179583115627] |
| cell_count_minus_conditional_expected[8] | 1.6833208543511475 | 974 | 25 | 0 | [0.975, 0.975] | [-0.5464029108266599, 1.6837267078387044] |
| cell_count_minus_exposure[0] | -0.3513802419539744 | 102 | 897 | 0 | [0.103, 0.103] | [-0.38333180455753746, 2.1732181523496] |
| cell_count_minus_exposure[1] | -1.3740114116565225 | 346 | 653 | 0 | [0.347, 0.347] | [-3.7215207179961114, 7.351792914489888] |
| cell_count_minus_exposure[2] | -9.889290365337551 | 59 | 940 | 0 | [0.06, 0.06] | [-12.998214078327948, 15.090722518355264] |
| cell_count_minus_exposure[3] | 0.010376354685950773 | 604 | 395 | 0 | [0.605, 0.605] | [-2.7644097757400985, 5.5350541651086616] |
| cell_count_minus_exposure[4] | -21.87425541554352 | 4 | 995 | 0 | [0.005, 0.005] | [-13.599705381444963, 17.611661693786253] |
| cell_count_minus_exposure[5] | -3.650028747443474 | 109 | 890 | 0 | [0.11, 0.11] | [-5.038231602797723, 6.976472844885368] |
| cell_count_minus_exposure[6] | -0.6180890512166126 | 474 | 525 | 0 | [0.475, 0.475] | [-3.2232068668089795, 7.210843773363017] |
| cell_count_minus_exposure[7] | 32.51447266692557 | 998 | 1 | 0 | [0.999, 0.999] | [-5.529713348862682, 8.405554791404963] |
| cell_count_minus_exposure[8] | 0.8589155595404854 | 895 | 104 | 0 | [0.896, 0.896] | [-0.47408414773140284, 1.8500284668679465] |

### california_fold_2

| Coordinate | Observed | L | H | Ties | Insertion interval | RI |
|---|---:|---:|---:|---:|---|---|
| count | 69.0 | 27 | 979 | 7 | [0.021, 0.028] | [69.0, 279.0] |
| exposure | 82.98011402768624 | 11 | 988 | 0 | [0.012, 0.012] | [84.63910442014598, 273.41609881229346] |
| immigrant_exposure | 51.19150695498898 | 999 | 999 | 999 | [0.001, 1.0] | [51.19150695498898, 51.19150695498898] |
| trigger_exposure | 31.78860707269726 | 11 | 988 | 0 | [0.012, 0.012] | [33.447597465157, 222.22459185730446] |
| count_minus_exposure | -13.980114027686241 | 109 | 890 | 0 | [0.11, 0.11] | [-21.516201861490444, 25.730431360837983] |
| time_event_logsum | -146.59291236182796 | 609 | 390 | 0 | [0.61, 0.61] | [-232.88313618752468, 319.67822429713823] |
| timing_logscore | -229.5730263895142 | 782 | 217 | 0 | [0.783, 0.783] | [-348.99757164544127, 48.51157900753179] |
| location_logscore | -672.8781278567991 | 969 | 30 | 0 | [0.97, 0.97] | [-2179.897199023438, -658.5854964466687] |
| mark_logscore | 4.795665965226562 | 953 | 46 | 0 | [0.954, 0.954] | [-55.185279408241406, 7.879563134738778] |
| joint_logscore | -897.6554882810867 | 975 | 24 | 0 | [0.976, 0.976] | [-2266.968496450347, -899.6214521113319] |
| zone_logscore | -55.07810653518308 | 981 | 18 | 0 | [0.982, 0.982] | [-120.76605284225494, -56.73137685981759] |
| cell_given_zone_logscore | -47.44870618924307 | 375 | 624 | 0 | [0.376, 0.376] | [-80.91549222667163, -25.348352347791717] |
| within_cell_density_logscore | -570.351315132373 | 974 | 25 | 0 | [0.975, 0.975] | [-1993.3626847148519, -568.0985845830087] |
| subblock_balance_max | 0.5067415866304383 | 912 | 87 | 0 | [0.913, 0.913] | [0.13027991005001163, 0.5977092960194359] |
| gap_ks | 0.0881227829042357 | 675 | 324 | 0 | [0.676, 0.676] | [0.03890685472687, 0.1515294451755272] |
| gap_serial | 0.02308692546525953 | 997 | 2 | 0 | [0.998, 0.998] | [-0.016474054122240584, 0.01581461393156039] |
| censored_tail | 1.586732938471152 | 699 | 300 | 0 | [0.7, 0.7] | [0.20475815863390756, 4.1602047948060665] |
| spatial_rosenblatt_ks_max | 0.1129696501693383 | 809 | 190 | 0 | [0.81, 0.81] | [0.04654454029690297, 0.15507137981463015] |
| spatial_rosenblatt_cross_abs | 0.021671079327220788 | 991 | 8 | 0 | [0.992, 0.992] | [0.00027744438685294053, 0.018252598010173187] |
| cell_mass_residual_max | 0.9353000407946973 | 928 | 71 | 0 | [0.929, 0.929] | [0.29059965091976264, 1.1369099079940341] |
| location_dimensionless_log_mean | 3.0323144634777903 | 37 | 962 | 0 | [0.038, 0.038] | [2.9727657609201517, 5.071058680477996] |
| location_dimensionless_log_variance | 12.30394407102264 | 999 | 0 | 0 | [1.0, 1.0] | [5.115680545645017, 8.90203834133091] |
| within_cell_dimensionless_absmax | 6.222589974706672 | 498 | 501 | 0 | [0.499, 0.499] | [5.935671300203616, 6.92541183337746] |
| within_cell_dimensionless_sum | 160.5763321022822 | 29 | 970 | 0 | [0.03, 0.03] | [157.92323331402645, 976.0888013620179] |
| year_count[0] | 14.0 | 188 | 851 | 40 | [0.149, 0.189] | [8.0, 69.0] |
| year_count[1] | 6.0 | 13 | 994 | 8 | [0.006, 0.014] | [7.0, 77.0] |
| year_count[2] | 11.0 | 112 | 913 | 26 | [0.087, 0.113] | [7.0, 83.0] |
| year_count[3] | 31.0 | 793 | 219 | 13 | [0.781, 0.794] | [7.0, 75.0] |
| year_count[4] | 7.0 | 28 | 983 | 12 | [0.017, 0.029] | [7.0, 68.0] |
| year_exposure[0] | 16.938048471817385 | 138 | 861 | 0 | [0.139, 0.139] | [15.058973492339794, 59.874545106243616] |
| year_exposure[1] | 13.191344354739721 | 2 | 997 | 0 | [0.003, 0.003] | [14.546886220629323, 73.61762201751523] |
| year_exposure[2] | 15.339667416692466 | 79 | 920 | 0 | [0.08, 0.08] | [14.018568867129577, 78.5319368895116] |
| year_exposure[3] | 23.092088325547895 | 616 | 383 | 0 | [0.617, 0.617] | [14.007174868637135, 74.50980500448411] |
| year_exposure[4] | 14.41896545888891 | 44 | 955 | 0 | [0.045, 0.045] | [13.678177206581847, 64.75938563019379] |
| year_count_minus_exposure[0] | -2.9380484718173854 | 299 | 700 | 0 | [0.3, 0.3] | [-7.672486168001907, 12.218605269723561] |
| year_count_minus_exposure[1] | -7.191344354739721 | 41 | 958 | 0 | [0.042, 0.042] | [-7.930696293059958, 11.088192049666894] |
| year_count_minus_exposure[2] | -4.339667416692466 | 189 | 810 | 0 | [0.19, 0.19] | [-8.342794365572786, 12.644755685288388] |
| year_count_minus_exposure[3] | 7.907911674452105 | 932 | 67 | 0 | [0.933, 0.933] | [-7.934942241033699, 11.300222460919628] |
| year_count_minus_exposure[4] | -7.418965458888909 | 34 | 965 | 0 | [0.035, 0.035] | [-7.752868160347148, 10.925204548467764] |
| cell_count[0] | 0.0 | 814 | 999 | 814 | [0.001, 0.815] | [0.0, 2.0] |
| cell_count[1] | 6.0 | 711 | 359 | 71 | [0.641, 0.712] | [0.0, 27.0] |
| cell_count[2] | 30.0 | 576 | 457 | 34 | [0.543, 0.577] | [12.0, 87.0] |
| cell_count[3] | 11.0 | 946 | 66 | 13 | [0.934, 0.947] | [0.0, 16.0] |
| cell_count[4] | 8.0 | 1 | 998 | 0 | [0.002, 0.002] | [15.0, 103.0] |
| cell_count[5] | 0.0 | 7 | 999 | 7 | [0.001, 0.008] | [1.0, 21.0] |
| cell_count[6] | 4.0 | 669 | 440 | 110 | [0.56, 0.67] | [0.0, 22.0] |
| cell_count[7] | 9.0 | 32 | 977 | 10 | [0.023, 0.033] | [9.0, 107.0] |
| cell_count[8] | 1.0 | 864 | 367 | 232 | [0.633, 0.865] | [0.0, 4.0] |
| cell_conditional_expected[0] | 0.18590902218327643 | 45 | 954 | 0 | [0.046, 0.046] | [0.17972498629162484, 1.2881850480187231] |
| cell_conditional_expected[1] | 2.617010206399609 | 68 | 931 | 0 | [0.069, 0.069] | [2.401650142826233, 27.271191335622422] |
| cell_conditional_expected[2] | 27.399679421880357 | 493 | 506 | 0 | [0.494, 0.494] | [15.238497761670468, 88.36317874889525] |
| cell_conditional_expected[3] | 5.694895699906994 | 871 | 128 | 0 | [0.872, 0.872] | [1.6198221541912485, 13.481007984938824] |
| cell_conditional_expected[4] | 14.770085109767768 | 2 | 997 | 0 | [0.003, 0.003] | [18.094286619351053, 99.71131763678771] |
| cell_conditional_expected[5] | 3.34588982852101 | 11 | 988 | 0 | [0.012, 0.012] | [3.553103994933522, 17.78125567906493] |
| cell_conditional_expected[6] | 2.043021303703966 | 61 | 938 | 0 | [0.062, 0.062] | [1.903583057129579, 19.41103013334672] |
| cell_conditional_expected[7] | 12.587101570511495 | 19 | 980 | 0 | [0.02, 0.02] | [13.261884297634136, 101.83705967149344] |
| cell_conditional_expected[8] | 0.3564078371255701 | 111 | 888 | 0 | [0.112, 0.112] | [0.3237623148387416, 2.8966572512724387] |
| cell_exposure[0] | 0.2342671027186755 | 533 | 466 | 0 | [0.534, 0.534] | [0.2336960612725122, 1.1838488430745455] |
| cell_exposure[1] | 5.151399301307641 | 671 | 328 | 0 | [0.672, 0.672] | [2.9018711509192574, 23.999611624307644] |
| cell_exposure[2] | 25.8568197386675 | 386 | 613 | 0 | [0.387, 0.387] | [19.071337558812317, 87.71229952019588] |
| cell_exposure[3] | 6.829527153734484 | 923 | 76 | 0 | [0.924, 0.924] | [2.024636589759541, 12.600984082472984] |
| cell_exposure[4] | 20.348740295009677 | 0 | 999 | 0 | [0.001, 0.001] | [23.410105024391708, 96.20694992789286] |
| cell_exposure[5] | 4.210469797801029 | 0 | 999 | 0 | [0.001, 0.001] | [4.439629797333118, 16.652393159011666] |
| cell_exposure[6] | 3.420258870261951 | 504 | 495 | 0 | [0.505, 0.505] | [2.355462642035312, 18.93874707673959] |
| cell_exposure[7] | 16.186550324075863 | 22 | 977 | 0 | [0.023, 0.023] | [16.302769152274553, 98.99652075875032] |
| cell_exposure[8] | 0.7420814441095265 | 847 | 152 | 0 | [0.848, 0.848] | [0.4142194044878332, 2.097579973289681] |
| cell_count_minus_conditional_expected[0] | -0.18590902218327643 | 771 | 228 | 0 | [0.772, 0.772] | [-0.30369582870850165, 1.4773215732823326] |
| cell_count_minus_conditional_expected[1] | 3.382989793600391 | 943 | 56 | 0 | [0.944, 0.944] | [-3.059274953804243, 4.332622617048959] |
| cell_count_minus_conditional_expected[2] | 2.600320578119643 | 753 | 246 | 0 | [0.754, 0.754] | [-6.858743762727311, 7.807522277989275] |
| cell_count_minus_conditional_expected[3] | 5.305104300093006 | 990 | 9 | 0 | [0.991, 0.991] | [-2.297152047468647, 4.0011014964537175] |
| cell_count_minus_conditional_expected[4] | -6.770085109767768 | 46 | 953 | 0 | [0.047, 0.047] | [-7.939752029576436, 8.921365665660566] |
| cell_count_minus_conditional_expected[5] | -3.34588982852101 | 46 | 953 | 0 | [0.047, 0.047] | [-3.716022535672022, 5.013551833174805] |
| cell_count_minus_conditional_expected[6] | 1.956978696296034 | 894 | 105 | 0 | [0.895, 0.895] | [-2.4857016606856437, 3.8492602926829798] |
| cell_count_minus_conditional_expected[7] | -3.5871015705114946 | 162 | 837 | 0 | [0.163, 0.163] | [-6.956987707030514, 7.655049866143898] |
| cell_count_minus_conditional_expected[8] | 0.6435921628744299 | 873 | 126 | 0 | [0.874, 0.874] | [-0.5096319566645792, 2.014686218947828] |
| cell_count_minus_exposure[0] | -0.2342671027186755 | 285 | 714 | 0 | [0.286, 0.286] | [-0.2778153771877794, 1.4609321686953354] |
| cell_count_minus_exposure[1] | 0.8486006986923593 | 703 | 296 | 0 | [0.704, 0.704] | [-2.9899294964599603, 5.3292071117537985] |
| cell_count_minus_exposure[2] | 4.1431802613325 | 771 | 228 | 0 | [0.772, 0.772] | [-9.05910828994045, 12.781739774774891] |
| cell_count_minus_exposure[3] | 4.170472846265516 | 956 | 43 | 0 | [0.957, 0.957] | [-2.125126976459654, 4.977807553573983] |
| cell_count_minus_exposure[4] | -12.348740295009677 | 9 | 990 | 0 | [0.01, 0.01] | [-10.604783922645389, 13.703068328647873] |
| cell_count_minus_exposure[5] | -4.210469797801029 | 16 | 983 | 0 | [0.017, 0.017] | [-3.74351997240268, 6.044362753963771] |
| cell_count_minus_exposure[6] | 0.579741129738049 | 719 | 280 | 0 | [0.72, 0.72] | [-2.401031685271969, 5.959103407190623] |
| cell_count_minus_exposure[7] | -7.1865503240758635 | 60 | 939 | 0 | [0.061, 0.061] | [-8.777379985379493, 12.114711279011448] |
| cell_count_minus_exposure[8] | 0.2579185558904735 | 683 | 316 | 0 | [0.684, 0.684] | [-0.4227927570971259, 2.3571056844020157] |
