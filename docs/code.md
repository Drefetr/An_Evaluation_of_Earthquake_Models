# Code guide

The repository has two code surfaces: preserved historical modules exposed through `engine/api.py`, and later Stage 2 implementations with their own build/input requirements. The [Stage 2 support matrix](../engine/stage2_followup/README.md) identifies usable components and archived or incomplete runners.

## Preserved numerical API

From the repository root:

```python
import sys
sys.path.insert(0, "engine")
from api import load

KernelSpec = load("kernels").KernelSpec
weights, rates = KernelSpec("exp", 2.0).mixture
observed = load("observed")  # PredictiveHistory, evaluate_window, fit_training
oracle = load("oracle")      # KnownLaw, evaluate_oracle
```

Loader names `empirical`, `simulator`, `paired`, `stable`, `restricted`, `fitting`, `staged`, `profile`, `level_only`, `heterogeneity`, and `cuda` expose the other preserved modules. Imports do not launch scientific campaigns. CUDA execution needs a suitable separate PyTorch installation and device. Some historical modules set numerical thread environment variables or disable bytecode writing, as their original implementations did.

Read the [methods supplement](../paper/supplements/methods_supplement.md) and current manuscript before adapting an API. The physical loading construction and independent-background diagnostic family differ. Precise-clock simulation retains paired timestamps and positive event gaps; projected ties must not be jittered. Mark transforms, normalized productivity, left limits, full quiet exposure, and the terminal no-event interval are part of the likelihood contract.

## Source preservation and execution boundaries

Historical iteration paths and source identities are preserved because numerical modules and frozen protocols verify dependency hashes. [Extraction records](../provenance/extraction_manifest.json) map originals to public files and declared variants. A file can be necessary to source validation even if its old command-line entry point depends on an unavailable archive.

Use the public wrappers for documented workflows. The observed wrapper checks frozen source and external CSV hashes before fitting; see the [data guide](data.md). Historical synthetic banks, run plans, recovery states, native binaries, and optional backends are not all supplied. Do not infer end-to-end replay support from importability or from the presence of a campaign script.

Stage 2 native kernels, independent `Q01` oracles, and runners are documented [separately](../engine/stage2_followup/README.md). Independent oracle variants use different implementation routes and should not be removed as duplicates without checking their scientific purpose. Synthetic/negative controls and numerical acceptance checks remain part of the methods, distinct from one-off worker scheduling or release-control records.
