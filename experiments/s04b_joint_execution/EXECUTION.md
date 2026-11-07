# Separately bounded continuation driver

`driver.py` is code for a new operational envelope. It is not evidence that
continuation has run. Independent source/scheduler review, a new shared run,
a current numerical lease and external process-tree supervision are required
before any historical evaluation. The old scientific protocol, original
failed pilot and its incomplete status remain unchanged.

The [operational protocol](operational_protocol.json) pins the original
scientific code/inputs and audited scheduler. It permits at most four hours
of aggregate pilot time, 32 hours of aggregate campaign time, and four hours
per supervised batch, with two numerical threads, one scientific worker,
6 GiB sampled process-tree RSS and 2 GiB host headroom. The original failed
867.911497775 scientific seconds count in both aggregate allowances. These
new allowances do not retroactively pass the old 1,800-second pilot or its
unadmitted four-hour campaign envelope. The external run's earlier expiry
still takes precedence; no allowance is raised automatically.

The driver delegates `case_run`, fitting, fine checks, historical comparisons,
BIC decisions and final aggregation to a private import of the frozen runner.
Only that import's model facade substitutes `ParallelPhase`; the original
process-wide scientific module is never modified. The unchanged feature
constructor supplies its arrays and metadata. The original native binary and
essential runtime identities are required for first-case training reuse and
for all subsequent accepted-index continuation.

Initial invocation after admission:

```text
python -B experiments/s04b_joint_execution/driver.py --admission ADMISSION.json --library ORIGINAL_LIBRARY --build-receipt ORIGINAL_BUILD.json --resume-training FAILED/science --resume-review PARTIAL_REVIEW.json --resume-archive FAILED.zip --output NEW_OUTPUT
```

The first fixed pilot case must reuse its four independently reviewed frozen
training fits; the driver evaluates only its missing test phase. Other pilot
batches each contain one case, in the original fixed pilot order. Subsequent
invocations use an independently accepted index and its review:

```text
python -B experiments/s04b_joint_execution/driver.py --admission ADMISSION.json --library ORIGINAL_LIBRARY --build-receipt ORIGINAL_BUILD.json --prior-index PREVIOUS/index.json --prior-review INDEX_REVIEW.json --output NEW_OUTPUT
```

An index review must contain `passed: true` and the exact `index_sha256`.
The admission binds both that review's bytes and the index. Complete reports
and their attempt traces are checked and copied byte for byte into the new
output. Their fit calls are never repeated. The index is a fixed completed
prefix, so duplicate, reordered, substituted or phase-crossing batches fail.
Every output index is pending independent review; writing it does not grant
acceptance or permission for another batch.

The admission JSON requires:

- `independent_review_passed`, `scheduler_review_passed` and
  `external_supervision`, all true; `phase` is `pilot` or `campaign`.
- `source_sha256` from `driver.source_identity()` and
  `operational_protocol_sha256`; the protocol independently pins frozen code,
  inputs and scheduler bytes.
- `library_sha256`, `build_receipt_sha256`, `numerical_attempt_id`, an unexpired
  `expires_utc`, and `lease_token_sha256` matching the environment value
  `JOINT_NUMERICAL_LEASE_TOKEN`. The token is a conductor attestation, not an
  authenticated security boundary.
- `threads: 2`, `workers: 1`, `sampled_process_tree_rss_cap_bytes: 6442450944`,
  and positive `wall_seconds` within every remaining allowance.
- Exact next-prefix `case_ids` and positive `case_reservations_seconds`, with
  the same key set and total at most `wall_seconds`. Leave explicit startup
  and upload headroom; a reservation equal to the entire child wall allowance
  cannot fit after preflight. The driver stops before a case if its reservation
  no longer fits the remaining child time.
- For index continuation, `prior_index_sha256` and `prior_review_sha256`.
  For the original first case, the unchanged `training_resume` grant described
  in the frozen runner's README, including all five original evidence hashes.
- For campaign batches, `pilot_projection_review_passed: true` and
  `projection_sha256` of `driver.remaining_projection(...)`. This delegates
  the frozen input/plan workload proxy and factor of three to the five accepted
  pilot records. The remaining projection must fit the aggregate remainder,
  and each reservation must cover its corresponding projected case work.

For that projection, the first resumed case's stored `wall_seconds` includes
its original training-attempt time plus the new test phase. The global budget
separately charges the original attempt once and each new batch once; it does
not add the case's already inclusive projection cost a second time.

The supervisor must enforce the same wall/RSS/headroom settings outside the
driver. Native calls are not asynchronously interrupted inside Python; this
is sampled termination, not a hard operating-system allocation guarantee.
Use bounded CI jobs with unconditional artifact upload and enough service
headroom. The conductor must publish/verify each accepted artifact/index
before launching a later batch; this CLI does not upload artifacts itself.

Every admitted batch records actual elapsed time, including failure, in a
hashed attempt receipt. Prior receipts are rechecked and their time summed
with the original failure. A failed partial fit blocks automatic continuation
and requires a separate independently reviewed disposition; the driver never
silently discards/restarts it. Failure before a usable index, or a duplicated
attempt identifier, emits `unindexed_attempt_requires_conductor_accounting`;
the conductor must retain and charge that execution before any new admission.
Do not resume from an older index to omit a failed attempt. The external shared
task ledger remains authoritative for the latest execution history.

`batch_complete` certifies only the requested fixed prefix. All 80 accepted
cases are required before final aggregation can state scientific execution
completion: 320 distinct fit arms, 400 outcomes, 480 historical floor checks
and 400 historical comparison identities. The aggregate preserves the original
score/gating definitions and does not claim global optimization or inference.
The final deadline is checked again after aggregate construction and summary
serialization. Late finalization retains its artifacts but cannot mark the
batch passed; the external supervisor remains authoritative for process time.
The `completed_case_fit_arms` census counts only completed cases. A separate
`partial_fit_checkpoint` lists fit records actually retained in a failed case,
including completed arms within that incomplete case. Missing/unreadable
partial evidence is unknown, not zero; additional in-progress work remains in
the preserved attempt trace.

Constructed controls, including native full-case serial/scheduled record
equivalence, first training reuse, complete-case reuse and failure/budget
handling, run with:

```text
python -B -m unittest discover -s tests -p test_joint_execution_driver.py -v
```

## Fresh Linux checkout and exact runtime

Task 1 is separate from the [selected-state reader](../../reproduction/score_replay/README.md).
The commands below restore public evidence locally; they need neither an Actions
token nor the authors' private run directories. Download the runtime and wheels
once, then retain them for offline installation. Use Ubuntu 24.04 **x86_64** with
a C++ compiler for the constructed controls, plus `git`, `curl`, `tar` and
`sha256sum`. Obtain the edition containing the continuation artifacts:

```sh
git clone https://github.com/Drefetr/An_Evaluation_of_Earthquake_Models.git
cd An_Evaluation_of_Earthquake_Models
```

The original workflow used `actions/setup-python@v5` with CPython 3.13.18.
The corresponding [official Python release](https://github.com/actions/python-versions/releases/tag/3.13.18-40336726450)
contains the exact executable recorded by the failed pilot. Its Ubuntu 24.04
x64 archive and the two Linux wheels below were downloaded and their relevant
member hashes checked against the retained runtime. This is an artifact-byte
check, not a claim that this documentation executed a fresh Linux fit.

```sh
set -eu
# From the repository root; the workspace must be new and outside the checkout.
export JOINT_LOCAL="$(mktemp -d "$(dirname "$PWD")/joint-local.XXXXXX")"
export JOINT_PYTHON=/opt/hostedtoolcache/Python/3.13.18/x64
curl --fail --location \
  https://github.com/actions/python-versions/releases/download/3.13.18-40336726450/python-3.13.18-linux-24.04-x64.tar.gz \
  --output "$JOINT_LOCAL/python.tar.gz"
printf '%s  %s\n' \
  683005a1465d94d40045f6a1a6eb316885b5f08d3360f7922b44ef58a14a9eed \
  "$JOINT_LOCAL/python.tar.gz" | sha256sum --check

# Keep the original installation prefix; never replace an existing interpreter.
if [ ! -e "$JOINT_PYTHON" ]; then
  sudo install -d "$JOINT_PYTHON"
  sudo tar -xzf "$JOINT_LOCAL/python.tar.gz" -C "$JOINT_PYTHON"
fi
printf '%s  %s\n' \
  5d782b88e6d48cc376d3e4b890539876ccaf7235acb1a265b7880ba471432cba \
  "$JOINT_PYTHON/bin/python3.13" | sha256sum --check
"$JOINT_PYTHON/bin/python3.13" -m venv --symlinks "$JOINT_LOCAL/venv"
. "$JOINT_LOCAL/venv/bin/activate"
python -m pip download --only-binary=:all: --no-deps \
  --dest "$JOINT_LOCAL/wheels" numpy==2.2.6 scipy==1.15.3
printf '%s  %s\n' \
  1bc23a79bfabc5d056d106f9befb8d50c31ced2fbc70eedb8155aec74a45798f \
  "$JOINT_LOCAL/wheels/numpy-2.2.6-cp313-cp313-manylinux_2_17_x86_64.manylinux2014_x86_64.whl" \
  c9deabd6d547aee2c9a81dee6cc96c6d7e9a9b1953f74850c179f91fdc729cb7 \
  "$JOINT_LOCAL/wheels/scipy-1.15.3-cp313-cp313-manylinux_2_17_x86_64.manylinux2014_x86_64.whl" \
  | sha256sum --check
python -m pip install --no-index --find-links "$JOINT_LOCAL/wheels" numpy==2.2.6 scipy==1.15.3
python -m pip install -r requirements.txt
```

For a disconnected machine, prepare a complete wheelhouse with
`python -m pip download -r requirements.txt --dest WHEELHOUSE` on the same
Ubuntu/Python architecture, retain its checksums, and replace the last command
with `python -m pip install --no-index --find-links WHEELHOUSE -r requirements.txt`.
The original Python tarball must also be available locally. A stock system
Python, source rebuild, different wheel tag or different BLAS binary may have
the same version string and still fail the exact-resume contract. Do not bypass
that failure or rebuild the retained native library to make it pass.

## Restore the latest published prefix without refitting

The public [continuation directory](../../validation/reproductions/joint_nuisance_20261107/continuation/)
contains cumulative `pilotXX.zip` artifacts and their separate
`pilotXX_independent_review.json` records. Choose the greatest **verified complete
prefix**, not merely the lexically last filename. The following reads only local
files, verifies the review's archive/index pins and restores that prefix. When
there is no published accepted prefix, it prepares the original frozen-training
resume instead; it never discards a newer accepted index.

```sh
python -B - <<'PY'
import hashlib, json, os, zipfile
from pathlib import Path
from experiments.s04b_joint_execution import driver
repo = Path.cwd().resolve()
work = Path(os.environ['JOINT_LOCAL']).resolve()
assert not work.is_relative_to(repo)
sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
op, _ = driver.verify_protocol()
base = repo/'validation/reproductions/joint_nuisance_20261107'
choices = []
for review_path in (base/'continuation').glob('*_independent_review.json'):
    review = json.loads(review_path.read_bytes())
    if review.get('passed') is not True:
        continue
    archive = review_path.with_name(review_path.name.replace('_independent_review.json', '.zip'))
    assert sha(archive) == review['artifact_sha256']
    with zipfile.ZipFile(archive) as z:
        raw = z.read('science/index.json')
        assert hashlib.sha256(raw).hexdigest() == review['index_sha256']
        index = json.loads(raw)
    assert index['partial_case'] is None
    ids = [r['case_id'] for r in index['cases']]
    assert ids == op['sequence'][:len(ids)]
    choices.append((len(ids), archive, review_path, index))
if choices:
    maximum = max(c[0] for c in choices)
    leaders = [c for c in choices if c[0] == maximum]
    assert len({json.dumps(c[3], sort_keys=True) for c in leaders}) == 1
    count, archive, review_path, index = leaders[0]
    expected_runtime = index['runtime']['essential']
else:
    count = 0
    archive = base/'failed_pilot01/execution.zip'
    assert sha(archive) == op['original_failure']['failed_archive_sha256']
    review_path = repo/'validation/reproductions/continuation_20261107/original_joint_partial_review.json'
    assert sha(review_path) == op['original_failure']['partial_audit_sha256']
    with zipfile.ZipFile(archive) as z:
        expected_runtime = json.loads(z.read('science/result.json'))['runtime']['essential']
actual_runtime = driver.frozen.runtime_identity()['essential']
assert actual_runtime == expected_runtime, {
    k: (expected_runtime.get(k), actual_runtime.get(k))
    for k in set(expected_runtime) | set(actual_runtime)
    if expected_runtime.get(k) != actual_runtime.get(k)
}
restored = work/'retained'
restored.mkdir(exist_ok=False)
with zipfile.ZipFile(archive) as z:
    assert len(z.namelist()) == len(set(z.namelist()))
    for info in z.infolist():
        target = (restored/info.filename).resolve()
        assert not Path(info.filename).is_absolute() and target.is_relative_to(restored)
        assert (info.external_attr >> 16) & 0o170000 != 0o120000
    z.extractall(restored)
build = restored/'build'
receipt = json.loads((build/'build_receipt.json').read_bytes())
assert sha(build/'attenuation.so') == receipt['library_sha256']
args = (['--prior-index', str(restored/'science/index.json'), '--prior-review', str(review_path)]
        if count else ['--resume-training', str(restored/'science'), '--resume-review', str(review_path),
                       '--resume-archive', str(archive)])
selection = dict(complete_cases=count, next_case=op['sequence'][count] if count < 80 else None,
                 archive=str(archive), archive_sha256=sha(archive), review=str(review_path),
                 review_sha256=sha(review_path), library=str(build/'attenuation.so'),
                 build_receipt=str(build/'build_receipt.json'), resume_arguments=args)
with (work/'selection.json').open('x') as f:
    f.write(json.dumps(selection, indent=2)+'\n')
print(json.dumps(selection, indent=2))
PY
```

The runtime assertion checks the CPython executable, NumPy extension,
L-BFGS-B extension and both loaded OpenBLAS libraries, as well as version,
architecture and byte order. The driver repeats this check and validates every
copied case, trace and charged attempt before evaluation. The original
`attenuation.so` and build receipt remain byte-identical; the old absolute path
inside that receipt is historical metadata, not a path the local run must use.

An accepted public prefix does not erase later failures or coordinate concurrent
owners. Before continuing the shared study, include every later attempt in its
reviewed disposition and ensure that no other owner is executing the next case.
If all 80 cases are present, the continuation is complete: inspect the retained
summary and reviews rather than initiating another parameter search.

## Run an explicitly admitted local batch

First run the Linux controls below. They use constructed fixtures, not the
archived histories. Preserve their logs with the local attempt.

```sh
python -B -m unittest discover -s tests -p test_joint_parallel_chunks.py -v
python -B -m unittest discover -s tests -p test_joint_execution_driver.py -v
python -B -m unittest discover -s scripts/tests -p test_supervise_research_linux.py -v
```

Prepare a fresh `ADMISSION.json` using the exact schema above and the locally
restored `selection.json`. Bind the published
[driver source review](../../validation/reproductions/continuation_20261107/joint_driver_source_review.json)
and [scheduler review](../../validation/reproductions/continuation_20261107/parallel_scheduler_source_review.json);
verify their source hashes before inheriting their source-review flags. This
does not give the new output an independent review. Use a new attempt ID and
expiry, the next fixed prefix, explicit positive case reservations, and the
remaining aggregate allowances recorded in the restored index. Pilot batches
contain one history. Campaign batches additionally need the reviewed measured
pilot projection; do not invent that approval to reach the next phase.

Set `JOINT_NUMERICAL_LEASE_TOKEN` to a fresh locally generated nonce and put its
SHA-256 in that admission. The nonce is an execution attestation, not a GitHub
credential. With the admission at `$JOINT_LOCAL/ADMISSION.json`, prepare and run
the existing Linux supervisor as follows:

```sh
python -B - <<'PY'
import json, os, sys
from pathlib import Path
work = Path(os.environ['JOINT_LOCAL']).resolve()
selection = json.loads((work/'selection.json').read_bytes())
admission = json.loads((work/'ADMISSION.json').read_bytes())
assert selection['next_case'] is not None
assert admission['case_ids'][0] == selection['next_case']
command = [sys.executable, '-B', 'experiments/s04b_joint_execution/driver.py',
           '--admission', str(work/'ADMISSION.json'), '--output', str(work/'batch/science'),
           '--library', selection['library'], '--build-receipt', selection['build_receipt'],
           *selection['resume_arguments']]
env = {k: '2' for k in ('OMP_NUM_THREADS', 'OPENBLAS_NUM_THREADS', 'MKL_NUM_THREADS',
                       'NUMEXPR_NUM_THREADS', 'BLIS_NUM_THREADS')}
env['JOINT_NUMERICAL_LEASE_TOKEN'] = os.environ['JOINT_NUMERICAL_LEASE_TOKEN']
spec = dict(command=command, cwd=str(Path.cwd()), output=str(work/'batch/supervision'), env=env,
            wall_cap_seconds=admission['wall_seconds'], rss_cap_bytes=6442450944,
            host_headroom_bytes=2147483648, sample_seconds=.5)
with (work/'supervisor_spec.json').open('x') as f:
    json.dump(spec, f, indent=2)
PY
python -B scripts/supervise_research.py "$JOINT_LOCAL/supervisor_spec.json"
```

Keep the entire batch directory, admission and supervisor specification, including
failures. A later batch must use its newly reviewed cumulative index and the
same runtime/native identities. Do not switch to an earlier public ZIP to omit
work performed locally. Fresh fitting on another CPU environment is a distinct
independent execution with a new protocol/provenance record; it is not an exact
resume and must not silently repeat the completed fits under the old attempt.
