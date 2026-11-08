# Portable CPU execution

The CPU route executes the same C++ numerical kernels for LI, temporal and S06 controls, with platform-specific export decoration and build commands. It does not replace scientific calculations with stubs. It requires Python 3.13 and a C++17 compiler: GNU/Clang on Linux, or Visual Studio C++ tools on Windows. NumPy and SciPy supply the existing CPU iteration-27 evaluator; PyTorch and CUDA are not required for this route.

From a clean checkout, install the CPU dependencies and run bounded acceptance into a new directory:

```sh
python -m pip install -r requirements-cpu.txt
python -B -m engine.cpu_reproduction --output build/cpu_acceptance
python -B -m unittest discover -s tests -p test_cpu_portability.py -v
python -B reproduction/regional/inputs.py verify
python -B reproduction/s02/inputs.py verify
python -B reproduction/historical_fits/verify.py
python -B scripts/verify_claims.py
python -B scripts/verify_repository.py
```

No `INHIBITORY_TEST_NATIVE_ROOT`, MSVC setup or CUDA environment variable is required on Linux. A missing C++ compiler is an error. Build directories must be new; logs are retained on failure. `--stage build`, `--stage stage2` and `--stage iteration27` select bounded subsets. Only `--stage all` runs the complete core CPU roster. These commands do not launch an 80-history experiment or a manuscript replay campaign.

| CPU roster | Executed assertions | Scope |
|---|---|---|
| Stage 2 | Eight original tests, including three actual native fixtures | Imports/CLI, ranks, conservative failure arithmetic, LI boundary/gradient, S06 geometry, two-event temporal likelihood |
| Iteration 27 CPU | Nineteen unchanged historical non-GPU tests plus one explicitly labelled CPU16/CPU32 fit control | The same fixed small-fit fixture, starts, convergence assertions and refinement tolerances; real CPU likelihood/gradient calculations |
| Generic compiler controls | Three additional tests in the main suite | Preserved Windows export spelling compiled on the host, exact Poisson objective, source/output separation, explicit backend rejection |

The historical CUDA/CPU32 assertion remains unchanged in `engine/iteration_27/tests/test_horizon_pilot.py`. It is not executed or counted as a GPU check by the CPU suite. The new CPU fit adapter is `engine/cpu_fit.py`; the original hash-pinned `horizon_pilot.py` stays unchanged. CPU success does not establish GPU equivalence or replace the earlier full CUDA execution record. The original GPU-inclusive suite remains an explicit separate command on a CUDA-equipped system:

```sh
python -B -m unittest discover -s engine/iteration_27/tests -v
```

The core runner writes `checks_cpu.json`, individual test logs and per-group compiler receipts, including source/binary SHA-256 values, compiler commands/version output, Python/OS/package versions, test identifiers and counts, wall time, sampled process-tree RSS and host memory. The resource gate fails if its sampled 6-GiB process-tree or 2-GiB available-memory limits are violated. Sampling is not an exact instantaneous peak measurement. GPU parity is explicitly `not_run`. Partial stages cannot be presented as complete acceptance.

`.github/workflows/cpu-reproduction.yml` runs these controls in a fresh Ubuntu checkout on research-branch changes or manual dispatch and retains its artifacts. A workflow definition alone is not an execution record: use the successful run and its exact commit/receipt when reporting Linux acceptance. Scientific Task 1 fitting and Task 2 replay have separate reviewed protocols, runtime/resource gates and output records; this core workflow does not automatically run them.

The [bounded Linux execution acceptance](../validation/reproductions/cpu_20261107/checkout02_independent_review.json) records an actual clean checkout, the numerical CPU controls and the public selected-state reader executions. It also identifies the separate dated joint-reader continuation, which reused accepted runtime and native bytes. Linux was executed; macOS and CUDA parity were not. This receipt does not certify a fresh all-history joint run or replace the separate scientific completion/disposition records.

The later [amended joint-fit reader](../experiments/s04b_refined_cpu_reader/README.md) has a different dependency route: it automatically extracts an audited Linux x86-64 native library and original build receipt from the public archive. That command requires the pinned Python environment, but no local compiler or manual native-library variable. Its ordinary mode fits one supplied history under fresh finite local limits; its optional author mode retains the dated campaign limits. The earlier acceptance linked above does not cover this later implementation. Consult its distinct source and actual-output records; local execution never issues independent acceptance. The core compiler-based commands on this page remain unchanged.

`engine.cpu_build.build_shared(source, output, dependency_root=None, compiler=None)` is the compilation-only entry point for admitted standalone research kernels. It returns a receipt with the absolute `library` path. It preserves source bytes, hashes C++/header dependencies, disables fast-math and FP contraction, and records compiler commands. For unchanged archived Windows sources, GNU/Clang receives a compile-only macro that removes `__declspec` export decoration. A successful build does not claim that any likelihood or fit was executed.

The supported-scope table in [`engine/stage2_followup/README.md`](../engine/stage2_followup/README.md) points to the recovered input packages. Input verification, numerical replay, optimizer reruns and CPU platform acceptance remain separate evidence layers. The per-table status in [`result_provenance.md`](result_provenance.md) is authoritative for which scientific calculations were actually repeated.
