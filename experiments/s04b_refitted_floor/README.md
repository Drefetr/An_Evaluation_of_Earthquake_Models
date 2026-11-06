# Train-fitted background-intercept sensitivity for S04B

This experiment compares the existing saved inhibited procedures with an uninhibited floor whose background intercept is fitted on the corresponding training history. It uses all 80 original histories, with no generation, new inhibited fitting, changed gate or joint nuisance estimation. The bounds are the existing sensitivity box `a ∈ [-12,0]`; this is not an unconstrained MLE. `protocol.json` is the exact independently reviewed pre-execution protocol. Source identities are frozen in `source_pins.json`.

The experiment completed on all 80 original histories, with 480 historical phase/model floor checks and the full 20-row procedure summary. The fixed four-case pilot supplied 24 of those checks; its exact four fits were reused in the complete result. The [full execution and case records](../../validation/live_results/methodological_20261106/refitted_floor/result.json), [component summary](../../validation/live_results/methodological_20261106/refitted_floor_summary.json), and [current internal review](../../validation/reviews/METHODOLOGICAL_EDITION_20261106.json) identify the actual execution separately from this implementation.

| Matched broad/long procedure | Original fixed-floor mean gain | Mean gain against train-refitted floor | Wins against refitted floor |
|---|---:|---:|---:|
| LI+ immigrant, raw and gated | 48.3868 | 5.1631 | 19/20 |
| LI+ total, raw and gated | 53.2332 | 9.7367 | 18/20 |

All gains are total held-out joint nats. The original inhibition fits and gates are unchanged. The large reduction in gains shows that the fixed background was an important part of the original contrast; the remaining positive means describe this bounded comparator sensitivity, not joint nuisance estimation or a calibrated hypothesis test. The complete result also retains all narrow/short and mismatched-procedure outcomes.

For each phase, the code precomputes `u`, `v`, the background time integral and fixed triggering exposure/mark terms. The objective in the positive rate `b=exp(a)` is `sum(log(b*u+v))-b*A-H+M`, a concave scalar function. Endpoint derivatives or a bracketed root determine its global optimum on the declared box. The training optimum is frozen before test evaluation. Strictly earlier realized events are conditioning parents, including earlier test events; this is a sequential conditional score.

The original raw/BIC states stay unchanged. Each report supplies the old and new floor components and all five resulting procedure contrasts. `E` denotes nonnegative exposure, `C=-E` the manuscript signed exposure, and `joint=P+C+M`; therefore `delta_joint=delta_P+delta_C+delta_M`, with `delta_M=0`. Original floor components come from saved point/NLL values and the exact observed mark sum, and are checked against the newly reconstructed floor. No inhibition spatial/time quadrature is built.

The radial normalizer is the sole native calculation needed. Use an existing exact-source radial library and its build receipt, or build the existing portable `reproduction/synthetic/native.py` sources into a new external directory under the execution supervisor. The existing `build(output)` function compiles both CPU and radial libraries, although this experiment never loads or calls the CPU inhibition library. Build provenance must match `source_pins.json`; no compiler is launched by `run.py`.

The existing builder supports MSVC on Windows and a C++17 `g++` or `clang++` on other platforms. From the repository root, this invocation builds into a fresh directory and writes `build_receipt.json` alongside the libraries:

```sh
python -B -c "import sys; sys.path.insert(0, 'reproduction/synthetic'); from native import build; build('build/s04b_floor_native')"
```

Use `build/s04b_floor_native/radial.dll` on Windows, `radial.so` on Linux, or `radial.dylib` on macOS for `RADIAL` below, with `build/s04b_floor_native/build_receipt.json` for `BUILD_RECEIPT`. The supplied completed execution used MSVC; source support for another compiler is not a claim that this edition ran the experiment on that platform. On Windows the builder locates MSVC through `vswhere`, a developer shell, or `INHIBITORY_VCVARS`; elsewhere `CXX` can select the compiler. No CUDA dependency is required for this experiment.

After independent code review, reserve an exclusive numerical task and supervise compiler/control/experiment process trees with the fixed wall and memory admission limits. The CLI acknowledgement records the conductor's admission; it is not an authenticated lease or an OS resource boundary. The external supervisor must enforce and record actual limits, process identities, sampling and quiescence. The program also checks elapsed caps between cases and reports sampled self-memory; those samples alone are not a hard memory limit.

From the repository root, with `RADIAL` and `BUILD_RECEIPT` replaced by exact reviewed files and fresh output directories:

```powershell
python -B -m unittest discover -s tests -p test_s04b_refitted_floor.py -v
python -B experiments/s04b_refitted_floor/run.py --phase pilot --radial RADIAL --build-receipt BUILD_RECEIPT --output NEW_PILOT --acknowledge-reviewed-numerical-admission TRAIN_ONLY_FIXED_ROSTER
python -B experiments/s04b_refitted_floor/run.py --phase full --radial RADIAL --build-receipt BUILD_RECEIPT --pilot NEW_PILOT --output NEW_FULL --acknowledge-reviewed-numerical-admission TRAIN_ONLY_FIXED_ROSTER
```

The fixed pilot is seeds 410401, 410501, 410601 and 410701. The full run checks the pilot's exact source/input/library identities and report hashes, reuses those four scalar fits, and fits the other 76 histories once. It refuses a failed, incomplete or altered pilot. Its predeclared workload/time projection must fit the total 7200-second budget, including the pilot. No outcome-based exclusions or replacements are allowed. Exceptions return nonzero and retain failed run and partial case records. A fresh directory is always required.

These completed results answer whether a trained rate floor changes the reported score advantage. They do not provide parameter recovery, nominal testing size, global optimization certification for the historical inhibited fits, or prospective observational validation. The initial compiler-helper stop, identity-checked cleanup and successful continuation are retained beside the result; they did not change the scientific protocol, source, tolerances or case roster.
