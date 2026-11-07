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

## Inspect and restore an explicitly accepted archive without refitting

Select an execution archive and its live independent review explicitly from the
public [continuation directory](../../validation/reproductions/joint_nuisance_20261107/continuation/).
Do not glob all review filenames: projection reviews are not execution archives,
and host batches store their cumulative index inside the final child directory.
The review's `index_path` identifies that child. The example below inspects the
accepted first host batch; it is not a claim that this is the latest prefix or
that all histories are complete. Replace the pair with the final accepted pair
when inspecting a completed edition.

Inspection uses only Python's standard library and the local published files.
It neither imports the scientific evaluator nor requires the exact historical
runtime. If skipping the runtime installation above, first set `JOINT_LOCAL` to
a new directory outside the checkout for the inspection output.

```sh
export JOINT_LOCAL="${JOINT_LOCAL:-$(mktemp -d ../joint-inspect.XXXXXX)}"
export JOINT_ARCHIVE=validation/reproductions/joint_nuisance_20261107/continuation/host_batch01.zip
export JOINT_REVIEW=validation/reproductions/joint_nuisance_20261107/continuation/host_batch01_independent_review.json
python -B - <<'PY' > "$JOINT_LOCAL/selection.json"
import hashlib, json, os, zipfile
from pathlib import Path, PurePosixPath
repo = Path.cwd().resolve()
archive = (repo/os.environ['JOINT_ARCHIVE']).resolve()
review_path = (repo/os.environ['JOINT_REVIEW']).resolve()
sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
review = json.loads(review_path.read_bytes())
assert review['passed'] is True and review['live_agent_review'] is True
assert review.get('final_batch_agent_review_required', False) is False
assert sha(archive) == review['artifact_sha256']
# Current host reviews supply this exact ZIP member; do not guess its location.
member = review['index_path']
def portable(value):
    path = PurePosixPath(value)
    assert value and '\\' not in value and ':' not in value
    assert not path.is_absolute() and '..' not in path.parts
    return path
index_member = portable(member)
assert index_member.name == 'index.json' and index_member.parent.name == 'science'
science = index_member.parent
child = science.parent
protocol_path = repo/'experiments/s04b_joint_nuisance/protocol.json'
op = json.loads((repo/'experiments/s04b_joint_execution/operational_protocol.json').read_bytes())
with zipfile.ZipFile(archive) as z:
    assert len(z.namelist()) == len(set(z.namelist()))
    raw = z.read(member)
    assert hashlib.sha256(raw).hexdigest() == review['index_sha256']
    index = json.loads(raw)
    result_raw = z.read(str(science/'result.json'))
    assert hashlib.sha256(result_raw).hexdigest() == review['execution_result_sha256']
    result = json.loads(result_raw)
    count = len(index['cases'])
    assert result['passed'] is True and result['status'] == 'batch_complete'
    assert result['index_sha256'] == review['index_sha256']
    assert result['complete_cases'] == review['complete_cases'] == count
    assert index['partial_case'] is None and index['last_attempt_passed'] is True
    assert index['science_protocol_sha256'] == sha(protocol_path)
    assert [row['case_id'] for row in index['cases']] == op['sequence'][:count]
    assert 0 < count <= len(op['sequence']) == 80
    for row in index['cases']:
        for field, pin in [('file', 'sha256'), ('trace', 'trace_sha256')]:
            data = z.read(str(science/portable(row[field])))
            assert hashlib.sha256(data).hexdigest() == row[pin]
    receipt = json.loads(z.read(str(child/'build/build_receipt.json')))
    assert hashlib.sha256(z.read(str(child/'build/attenuation.so'))).hexdigest() == index['library_sha256'] == receipt['library_sha256']
    assert hashlib.sha256(z.read(str(child/'build/build_receipt.json'))).hexdigest() == index['build_receipt_sha256']
    complete = count == 80
    assert result['scientific_completion'] is complete
    if complete:
        assert hashlib.sha256(z.read(str(science/'summary.json'))).hexdigest() == result['summary_sha256'] == review['summary_sha256']
selection = dict(complete_cases=count, scientific_completion=complete,
                 next_case=op['sequence'][count] if not complete else None,
                 index_schema=index['schema'], index_member=member,
                 science_member=str(science), child_member=str(child),
                 archive=str(archive), archive_sha256=sha(archive),
                 review=str(review_path), review_sha256=sha(review_path),
                 index_sha256=review['index_sha256'],
                 expected_runtime=index['runtime']['essential'])
print(json.dumps(selection, indent=2))
PY
cat "$JOINT_LOCAL/selection.json"
```

A complete selection has `next_case: null`. Inspect its summary and reviews;
there is no next fitting command. A partial selection is evidence of its exact
completed prefix only. It grants no authority to repeat that prefix or launch
the next case. In particular, do not choose this older example to omit later
accepted work or failed attempts.

If local extraction is needed, the following restores the unchanged ZIP into a
new directory and records the actual nested child paths. It performs no fitting
and does not require the original runtime:

```sh
python -B - <<'PY'
import hashlib, json, os, zipfile
from pathlib import Path, PurePosixPath
work = Path(os.environ['JOINT_LOCAL']).resolve()
assert not work.is_relative_to(Path.cwd().resolve())
selection = json.loads((work/'selection.json').read_bytes())
sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
assert sha(Path(selection['archive'])) == selection['archive_sha256']
assert sha(Path(selection['review'])) == selection['review_sha256']
restored = work/'retained'
restored.mkdir(exist_ok=False)
with zipfile.ZipFile(selection['archive']) as z:
    assert len(z.namelist()) == len(set(z.namelist()))
    for info in z.infolist():
        member = PurePosixPath(info.filename)
        assert not member.is_absolute() and '..' not in member.parts
        assert '\\' not in info.filename and ':' not in info.filename
        assert (restored/info.filename).resolve().is_relative_to(restored)
        assert (info.external_attr >> 16) & 0o170000 != 0o120000
    z.extractall(restored)
science = restored/selection['science_member']
build = restored/selection['child_member']/'build'
assert sha(science/'index.json') == selection['index_sha256']
selection.update(library=str(build/'attenuation.so'), build_receipt=str(build/'build_receipt.json'),
                 resume_arguments=['--prior-index', str(science/'index.json'),
                                   '--prior-review', selection['review']])
with (work/'restored_selection.json').open('x') as stream:
    stream.write(json.dumps(selection, indent=2)+'\n')
print(json.dumps(selection, indent=2))
PY
```

Only an admitted exact continuation additionally requires equality with
`selection['expected_runtime']` using the frozen runner's `runtime_identity()`.
That compares the CPython executable, NumPy and L-BFGS-B extensions and both
loaded OpenBLAS libraries, not just version strings. The original native library
and build receipt stay byte-identical. Their historical absolute paths need not
be reproduced for inspection. A runtime mismatch is not permission to bypass the
check, rebuild that library or repeat completed fits.

The host example uses the separately reviewed budgeted index schema. Its
continuation follows the [fixed-allocation driver](../s04b_joint_budgeted/README.md)
and current accepted operational records, not the earlier projection-gated
command below. The [public CPU reader](../../docs/reproduction_joint_cpu.md)
distinguishes a dated published continuation from an explicitly new independent
execution. After the published study is complete, use inspection or deliberately
start a separately identified fresh run; do not resume an earlier prefix.

## Historical projection-gated local batch

This older command applies only to an accepted `joint_accepted_case_index_v1`
pilot prefix and its original projection-gated operational protocol. It does not
consume a budgeted/host index or supply approval for the failed campaign forecast.
For an independently admitted use of that earlier route, first run the Linux
controls below. They use constructed fixtures, not the archived histories.
Preserve their logs with the local attempt.

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
selection = json.loads((work/'restored_selection.json').read_bytes())
admission = json.loads((work/'ADMISSION.json').read_bytes())
assert selection['index_schema'] == 'joint_accepted_case_index_v1', 'Budgeted/host prefixes use their own reviewed driver'
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
