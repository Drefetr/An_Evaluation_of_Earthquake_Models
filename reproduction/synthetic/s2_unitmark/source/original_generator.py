"""Independent chronological inhibited-law simulator; import performs no draws.

Only the registered synthetic roster and separate engineering pilot are public
generation entry points. Execution requires an exact source/runtime/contract
admission and conductor numerical-lease attestation. This is not an OS lock.
No production evaluator, fitter, geometry or audit oracle is imported.
"""
from __future__ import annotations

import argparse
from collections import deque
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
import hashlib
import heapq
import json
import math
import os
from pathlib import Path
import platform
import sys
import time
from typing import Any, Callable, Mapping

import numpy as np


SCHEMA = "thread04_generator_catalogue_v1"
SOURCE_EPOCH = "generator_persistence_repair_v3"
ADMISSION_SCHEMA = "thread04_generator_admission_v1"
THREAD_ENV = ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS",
              "NUMEXPR_NUM_THREADS", "VECLIB_MAXIMUM_THREADS", "BLIS_NUM_THREADS")
ROSTER = {
    "S0_uniform_null": ((410001, 410002), "uniform", 0.0, 30.0, 7.0),
    "S1_smooth_null": ((410101, 410102), "smooth", 0.0, 30.0, 7.0),
    "S2_narrow_short": ((410201, 410202), "smooth", 0.5, 5.0, 1.0 / 24.0),
    "S3_broad_long": ((410301, 410302), "smooth", 2.0, 50.0, 30.0),
}


class GeneratorFailure(RuntimeError):
    def __init__(self, code: str, message: str = ""):
        super().__init__(message or code)
        self.code = code


class AdmissionError(GeneratorFailure):
    pass


def sha256(path: str | Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def canonical_hash(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"),
                                     allow_nan=False).encode("utf-8")).hexdigest()


def runtime_fingerprint() -> dict:
    """Called during admitted preflight, never automatically on import."""
    import numpy.random._generator as np_generator
    import numpy.random._pcg64 as np_pcg64
    runtime_dll = Path(sys.executable).with_name(f"python{sys.version_info.major}{sys.version_info.minor}.dll")
    return {
        "python_version": sys.version,
        "python_executable_sha256": sha256(sys.executable),
        "python_runtime_dll_sha256": sha256(runtime_dll) if runtime_dll.is_file() else None,
        "platform": platform.platform(),
        "numpy_version": np.__version__,
        "numpy_init_sha256": sha256(np.__file__),
        "numpy_generator_extension_sha256": sha256(np_generator.__file__),
        "numpy_pcg64_extension_sha256": sha256(np_pcg64.__file__),
        "math_extension_sha256": sha256(math.__file__) if getattr(math, "__file__", None) else None,
    }


def _checked_json(path: str, expected_hash: str) -> dict:
    if not isinstance(expected_hash, str) or len(expected_hash) != 64:
        raise AdmissionError("missing_hash_pin")
    raw = Path(path).read_bytes()
    if hashlib.sha256(raw).hexdigest() != expected_hash:
        raise AdmissionError("hash_pin_mismatch")
    value = json.loads(raw)
    if not isinstance(value, dict):
        raise AdmissionError("invalid_receipt_shape")
    return value


@dataclass(frozen=True)
class Admission:
    purpose: str
    case_id: str
    seed: int
    output_root: Path
    contract_sha256: str
    source_sha256: str
    controls_source_sha256: str
    runtime_sha256: str
    lease_id: str
    lease_receipt_sha256: str
    deadline_utc: str


def validate_admission(record: Mapping[str, Any], *, case_id: str, seed: int,
                       purpose: str, output_root: str | Path) -> Admission:
    """Fail closed before constructing a bit generator or generating a path.

    The conductor must supply a fresh scheduler attestation for the active job.
    Hashes identify bytes; neither this attestation nor this function acquires
    or authenticates the machine-wide scheduler lease.
    """
    if record.get('schema') == 'local_inhibition_experiment_admission_v1':
        if record.get('execution_accepted') is not True or not record.get('numerical_lease_held'):
            raise AdmissionError('execution_not_admitted')
        if purpose != 'scientific_control' or case_id not in ROSTER or seed not in ROSTER[case_id][0]:
            raise AdmissionError('unregistered_scientific_seed')
        if any(os.environ.get(name) != '1' for name in THREAD_ENV):
            raise AdmissionError('thread_settings_not_one')
        root=Path(output_root).resolve()
        if not root.is_relative_to(Path(record['run_root']).resolve()):
            raise AdmissionError('output_outside_run')
        _checked_json(record['contract_path'],record['contract_sha256'])
        if sha256(__file__) != record['generator_source_sha256']:
            raise AdmissionError('generator_source_pin_mismatch')
        deadline=datetime.fromisoformat(record['deadline_utc'].replace('Z','+00:00'))
        if deadline.tzinfo is None or datetime.now(timezone.utc)>=deadline:
            raise AdmissionError('deadline_not_available')
        return Admission(purpose,case_id,seed,root,record['contract_sha256'],sha256(__file__),
                         record['controls_source_sha256'],record['runtime_sha256'],record['lease_id'],
                         record['lease_receipt_sha256'],record['deadline_utc'])
    if record.get("schema") != ADMISSION_SCHEMA or record.get("execution_accepted") is not True:
        raise AdmissionError("execution_not_admitted")
    if type(seed) is not int or type(record.get("seed")) is not int:
        raise AdmissionError("invalid_seed_type")
    if purpose not in ("engineering_pilot", "scientific_control"):
        raise AdmissionError("unknown_purpose")
    if (record.get("purpose"), record.get("case_id"), record.get("seed")) != (purpose, case_id, seed):
        raise AdmissionError("case_seed_purpose_mismatch")
    if purpose == "scientific_control":
        if case_id not in ROSTER or seed not in ROSTER[case_id][0]:
            raise AdmissionError("unregistered_scientific_seed")
    elif (case_id, seed) not in (("P_GEN_30", 499001), ("generator_deterministic_controls", 0)):
        raise AdmissionError("unregistered_engineering_case")
    if any(os.environ.get(name) != "1" for name in THREAD_ENV):
        raise AdmissionError("thread_settings_not_one")
    try:
        deadline = datetime.fromisoformat(record["deadline_utc"].replace("Z", "+00:00"))
        if deadline.tzinfo is None or datetime.now(timezone.utc) >= deadline:
            raise AdmissionError("deadline_not_available")
        root = Path(output_root).resolve()
        if root != Path(record["output_root"]).resolve():
            raise AdmissionError("output_root_mismatch")
        if not root.is_relative_to(Path(record["run_root"]).resolve()):
            raise AdmissionError("output_outside_run")
        contract = _checked_json(record["contract_path"], record["contract_sha256"])
        acceptance = _checked_json(record["contract_acceptance_path"], record["contract_acceptance_sha256"])
        if acceptance.get("accepted") is not True or acceptance.get("contract_sha256") != record["contract_sha256"]:
            raise AdmissionError("contract_not_accepted")
        # Reading the contract establishes pinned identity, not acceptance by a status string.
        if not contract:
            raise AdmissionError("empty_contract")
        source_hash = sha256(__file__)
        controls_hash = sha256(Path(__file__).with_name("generator_controls.py"))
        if source_hash != record["generator_source_sha256"] or controls_hash != record["generator_controls_source_sha256"]:
            raise AdmissionError("generator_source_pin_mismatch")
        runtime_hash = canonical_hash(runtime_fingerprint())
        if runtime_hash != record["runtime_sha256"]:
            raise AdmissionError("runtime_pin_mismatch")
        if (acceptance.get("generator_source_sha256") != source_hash or
                acceptance.get("generator_controls_source_sha256") != controls_hash or
                acceptance.get("runtime_sha256") != runtime_hash or
                purpose not in acceptance.get("allowed_purposes", []) or
                acceptance.get("deadline_utc") != record["deadline_utc"]):
            raise AdmissionError("accepted_source_runtime_scope_mismatch")
        lease = _checked_json(record["lease_receipt_path"], record["lease_receipt_sha256"])
        if (lease.get("numerical_lease_held") is not True or
                lease.get("lease_id") != record["lease_id"] or
                not isinstance(lease.get("controller_pid"), int) or lease["controller_pid"] <= 0 or
                not lease.get("process_creation_identity") or
                Path(lease["machine_lease_path"]).resolve() != Path(record["machine_lease_path"]).resolve() or
                (lease.get("purpose"), lease.get("case_id"), lease.get("seed")) != (purpose, case_id, seed) or
                lease.get("contract_sha256") != record["contract_sha256"] or
                Path(lease["output_root"]).resolve() != root):
            raise AdmissionError("numerical_lease_attestation_missing")
    except AdmissionError:
        raise
    except (KeyError, TypeError, ValueError, OSError) as exc:
        raise AdmissionError("invalid_admission", type(exc).__name__) from exc
    return Admission(purpose, case_id, seed, root, record["contract_sha256"], source_hash,
                     controls_hash, runtime_hash, record["lease_id"],
                     record["lease_receipt_sha256"], record["deadline_utc"])


@dataclass(frozen=True)
class Limits:
    candidate_entries: int = 1_000_000
    accepted_events: int = 100_000
    spatial_per_location: int = 1_000_000
    spatial_total: int = 100_000_000
    raw_attempts_per_uniform: int = 1024
    wall_seconds: float = 600.0


@dataclass(frozen=True)
class Law:
    case_id: str
    seed: int
    background: str
    eta: float
    ell: float
    psi: float
    horizon: float = 760.0
    T0: float = 760.0
    a: float = math.log(0.2)
    d: float = 0.2
    n: float = 0.35
    c: float = 0.05
    p: float = 1.3
    sigma: float = 10.0
    beta: float = 2.0
    r: float = 0.7
    x0: float = 0.0
    x1: float = 100.0
    y0: float = 0.0
    y1: float = 100.0


def registered_law(case_id: str, seed: int, purpose: str) -> Law:
    if purpose == "scientific_control" and case_id in ROSTER and seed in ROSTER[case_id][0]:
        _, bg, eta, ell, psi = ROSTER[case_id]
        return Law(case_id, seed, bg, eta, ell, psi)
    if purpose == "engineering_pilot" and case_id == "P_GEN_30" and seed == 499001:
        return Law(case_id, seed, "smooth", 0.5, 5.0, 1.0 / 24.0, horizon=30.0)
    raise AdmissionError("unregistered_generation")


@dataclass
class Counters:
    queue_created: int = 0
    queue_processed: int = 0
    max_pending: int = 0
    accepted_decisions: int = 0
    accepted_committed: int = 0
    accepted_immigrants: int = 0
    accepted_offspring: int = 0
    rejected_immigrants: int = 0
    spatial_proposals: int = 0
    immigrant_horizon_rounding_exclusions: int = 0
    prospective_child_count_at_cap: int | None = None


@dataclass(order=True, frozen=True)
class Candidate:
    time: float
    kind: int
    root: int
    lineage: tuple[int, ...]
    parent: tuple[int, ...] | None = field(default=None, compare=False)


@dataclass(frozen=True)
class Event:
    time: float
    x: float
    y: float
    Q: float
    kind: int
    root: int
    lineage: tuple[int, ...]
    parent: tuple[int, ...] | None


class Budget:
    def __init__(self, limits: Limits, clock: Callable[[], float] = time.monotonic,
                 deadline_after: float | None = None):
        self.limits, self.clock = limits, clock
        self.started = clock()
        self.deadline_after = deadline_after

    def elapsed(self) -> float:
        return self.clock() - self.started

    def check(self) -> None:
        elapsed = self.elapsed()
        if self.deadline_after is not None and elapsed >= self.deadline_after:
            raise GeneratorFailure("global_deadline")
        if elapsed >= self.limits.wall_seconds:
            raise GeneratorFailure("wall_time_cap")


class ScalarStreams:
    """Seven separate pinned PCG64DXSM streams; no vectorized RNG calls."""
    def __init__(self, seed: int, limits: Limits, budget: Budget):
        self.limits, self.budget = limits, budget
        self.bits = {code: np.random.PCG64DXSM(np.random.SeedSequence([seed, code])) for code in range(7)}
        self.generators = {code: np.random.Generator(bits) for code, bits in self.bits.items()}
        self.raw_uniform_words = {str(code): 0 for code in range(7)}
        self.open_uniforms = {str(code): 0 for code in range(7)}
        self.poisson_calls = 0

    def uniform(self, code: int) -> float:
        for _ in range(self.limits.raw_attempts_per_uniform):
            self.budget.check()
            raw = int(self.bits[code].random_raw())
            self.raw_uniform_words[str(code)] += 1
            m = raw >> 11
            if m != 0:
                self.open_uniforms[str(code)] += 1
                return m * 2.0 ** -53
        raise GeneratorFailure("open_uniform_attempt_cap")

    def poisson(self, mean: float) -> int:
        self.budget.check()
        if not math.isfinite(mean) or mean < 0:
            raise GeneratorFailure("invalid_poisson_mean")
        self.poisson_calls += 1
        try:
            return int(self.generators[4].poisson(float(mean), size=None))
        except (ValueError, OverflowError) as exc:
            raise GeneratorFailure("poisson_not_representable") from exc

    def snapshot(self) -> dict:
        return {"raw_uniform_words": dict(self.raw_uniform_words),
                "open_uniforms": dict(self.open_uniforms), "poisson_calls": self.poisson_calls,
                "poisson_internal_raw_words": "not exposed by pinned NumPy distribution routine",
                "stream_state_sha256": {str(k): canonical_hash(v.state) for k, v in self.bits.items()}}


def strict_stress(t: float, x: float, y: float, history: list[Event], ell: float, psi: float) -> float:
    terms = []
    ell2 = ell * ell
    for event in history:
        if event.time < t:
            r2 = (x - event.x) ** 2 + (y - event.y) ** 2
            terms.append(math.exp(-(t - event.time) / psi) / (1.0 + r2 / ell2) ** 2)
    value = math.fsum(terms)
    if not math.isfinite(value) or value < 0:
        raise GeneratorFailure("invalid_stress")
    return value


def survival_mass(width: float, c: float, p: float) -> float:
    if not (math.isfinite(width) and width > 0 and c > 0 and p > 1):
        raise GeneratorFailure("invalid_offspring_interval")
    value = -math.expm1((1.0 - p) * math.log1p(width / c))
    if not (0 < value <= 1):
        raise GeneratorFailure("invalid_survival_mass")
    return value


class _Simulator:
    """Internal state machine. Tests may inject finite primitive tapes after admission."""
    def __init__(self, law: Law, limits: Limits, budget: Budget, streams: Any):
        self.law, self.limits, self.budget, self.streams = law, limits, budget, streams
        self.counts = Counters()
        self.queue: list[Candidate] = []
        self.history: list[Event] = []
        self.accepted_lineages: set[tuple[int, ...]] = set()
        self.parents_by_lineage: dict[tuple[int, ...], Event] = {}
        # Persistent from the first decision, including exceptions midway
        # through a tied batch. Completed commits leave this deque one by one.
        self.pending_uncommitted: deque[Event] = deque()
        self.pending_batch: list[Candidate] = []
        self.batch_cursor = 0
        self.batch_journal: list[dict] = []
        self.batch_stage = "idle"
        self.active_parent_lineage: tuple[int, ...] | None = None
        self.pending_child_delays: list[dict] = []

    def _push(self, candidate: Candidate) -> bool:
        self.budget.check()
        if not math.isfinite(candidate.time) or candidate.time < 0:
            raise GeneratorFailure("invalid_candidate_time")
        if candidate.time >= self.law.horizon:
            return False
        if self.counts.queue_created >= self.limits.candidate_entries:
            raise GeneratorFailure("candidate_entry_cap")
        if candidate.kind not in (0, 1):
            raise GeneratorFailure("invalid_candidate_kind")
        heapq.heappush(self.queue, candidate)
        self.counts.queue_created += 1
        self.counts.max_pending = max(self.counts.max_pending, len(self.queue))
        return True

    def _spatial_attempt(self, attempt: int) -> None:
        self.budget.check()
        if attempt > self.limits.spatial_per_location:
            raise GeneratorFailure("spatial_per_location_cap")
        if self.counts.spatial_proposals >= self.limits.spatial_total:
            raise GeneratorFailure("spatial_total_cap")
        self.counts.spatial_proposals += 1

    def _uniform_location(self, code: int) -> tuple[float, float]:
        self._spatial_attempt(1)
        q = self.law
        return (q.x0 + (q.x1 - q.x0) * self.streams.uniform(code),
                q.y0 + (q.y1 - q.y0) * self.streams.uniform(code))

    def _radial_location(self, code: int, center: tuple[float, float], scale: float) -> tuple[float, float]:
        for attempt in range(1, self.limits.spatial_per_location + 1):
            self._spatial_attempt(attempt)
            u, v = self.streams.uniform(code), self.streams.uniform(code)
            radius = scale * math.sqrt(u / (1.0 - u))
            angle = 2.0 * math.pi * v
            x, y = center[0] + radius * math.cos(angle), center[1] + radius * math.sin(angle)
            if not (math.isfinite(x) and math.isfinite(y)):
                raise GeneratorFailure("nonfinite_spatial_proposal")
            if self.law.x0 <= x <= self.law.x1 and self.law.y0 <= y <= self.law.y1:
                return x, y
        raise GeneratorFailure("spatial_per_location_cap")

    def _immigrant_location(self) -> tuple[float, float]:
        if self.law.background == "uniform":
            return self._uniform_location(1)
        if self.law.background != "smooth":
            raise GeneratorFailure("unknown_background")
        # Choose ONCE; outside-domain rejection never restarts mixture selection.
        component = self.streams.uniform(1)
        if component < 0.05:
            return self._uniform_location(1)
        center = (25.0, 25.0) if component < 0.525 else (75.0, 75.0)
        return self._radial_location(1, center, 10.0)

    def _mark(self, code: int) -> float:
        value = -math.log1p(-self.streams.uniform(code)) / self.law.beta
        if not math.isfinite(value) or value < 0:
            raise GeneratorFailure("invalid_mark")
        return value

    def _immigrant_times(self) -> None:
        q = self.law
        k = 2.0 * q.d / q.T0
        base = math.exp(q.a - q.d)
        total = base * math.expm1(k * q.horizon) / k if k != 0 else base * q.horizon
        cumulative, ordinal, previous_t = 0.0, 0, -1.0
        while True:
            self.budget.check()
            new_mass = cumulative - math.log(self.streams.uniform(0))
            if not math.isfinite(new_mass) or new_mass <= cumulative:
                raise GeneratorFailure("cumulative_mass_no_progress")
            cumulative = new_mass
            if cumulative >= total:
                return
            t = math.log1p(k * cumulative / base) / k if k != 0 else cumulative / base
            if not math.isfinite(t) or t < previous_t or t < 0:
                raise GeneratorFailure("immigrant_time_inversion")
            previous_t = t
            if t >= q.horizon:
                self.counts.immigrant_horizon_rounding_exclusions += 1
            else:
                self._push(Candidate(t, 0, ordinal, (ordinal,)))
            ordinal += 1

    def _schedule_children(self, event: Event) -> None:
        self.active_parent_lineage = event.lineage
        self.pending_child_delays = []
        if event.lineage not in self.accepted_lineages:
            raise GeneratorFailure("unaccepted_parent_scheduling")
        self.budget.check()
        q = self.law
        width = q.horizon - event.time
        mass = survival_mass(width, q.c, q.p)
        kappa = 0.3 * math.exp(q.r * q.beta * event.Q)  # Exact registered r=.7 constant.
        if not math.isfinite(kappa):
            raise GeneratorFailure("nonfinite_fertility")
        count = self.streams.poisson(q.n * kappa * mass)
        if count < 0:
            raise GeneratorFailure("invalid_poisson_count")
        if count > self.limits.candidate_entries - self.counts.queue_created:
            self.counts.prospective_child_count_at_cap = count
            raise GeneratorFailure("candidate_entry_cap")
        children = []
        for ordinal in range(count):
            self.budget.check()
            u = self.streams.uniform(4)
            delay = q.c * math.expm1(math.log1p(-u * mass) / (1.0 - q.p))
            t = event.time + delay
            self.pending_child_delays.append(dict(original_ordinal=ordinal,
                delay_days=delay if math.isfinite(delay) else None,
                time_days=t if math.isfinite(t) else None,
                nonfinite=not (math.isfinite(delay) and math.isfinite(t)), enqueued=False))
            if not math.isfinite(delay) or not (0 < delay < width):
                raise GeneratorFailure("conditional_delay_rounding")
            if not math.isfinite(t) or t <= event.time:
                raise GeneratorFailure("child_time_not_strict")
            if t >= q.horizon:
                raise GeneratorFailure("conditional_child_outside_horizon")
            children.append((delay, ordinal, t))
        for _, ordinal, t in sorted(children):
            self._push(Candidate(t, 1, event.root, event.lineage + (ordinal,), event.lineage))
            self.pending_child_delays[ordinal]["enqueued"] = True
        self.active_parent_lineage = None
        self.pending_child_delays = []

    def _commit_event(self, event: Event) -> None:
        """One caught-failure transaction; no RNG or scheduling inside it."""
        self.budget.check()
        if event.lineage in self.accepted_lineages:
            raise GeneratorFailure("duplicate_lineage")
        before = len(self.history)
        old_counts = (self.counts.accepted_committed, self.counts.accepted_immigrants,
                      self.counts.accepted_offspring)
        new_counts = (old_counts[0]+1, old_counts[1]+int(event.kind == 0),
                      old_counts[2]+int(event.kind == 1))
        try:
            self.history.append(event)
            self.accepted_lineages.add(event.lineage)
            self.parents_by_lineage[event.lineage] = event
            (self.counts.accepted_committed, self.counts.accepted_immigrants,
             self.counts.accepted_offspring) = new_counts
        except BaseException:
            # Preserve the prior committed prefix if a container update fails.
            del self.history[before:]
            self.accepted_lineages.discard(event.lineage)
            self.parents_by_lineage.pop(event.lineage, None)
            (self.counts.accepted_committed, self.counts.accepted_immigrants,
             self.counts.accepted_offspring) = old_counts
            raise

    def _prepare_next_batch(self) -> tuple[list[Candidate], list[Candidate]]:
        """Allocate/extract privately; a caught allocation failure keeps the queue.

        Heap pop already supplies Candidate order, so no later sort is needed.
        Neither returned container aliases the authoritative queue. This costs
        one shallow queue copy per batch and needs measured resource admission.
        """
        remaining_queue = self.queue.copy()
        t = remaining_queue[0].time
        batch = []
        while remaining_queue and remaining_queue[0].time == t:
            batch.append(heapq.heappop(remaining_queue))
        return batch, remaining_queue

    def _process_next_batch(self) -> None:
        self.budget.check()
        self.batch_stage = "extracting"
        batch, remaining_queue = self._prepare_next_batch()
        t = batch[0].time
        self.batch_cursor = 0
        self.batch_journal = []
        self.pending_uncommitted = deque()
        # All allocating preparation completed with self.queue unchanged.
        # Install persistent batch first, then swap the remaining heap; these
        # ordinary existing-attribute stores allocate no candidate containers.
        self.pending_batch = batch
        self.queue = remaining_queue
        self.batch_stage = "decisions"
        for candidate in self.pending_batch:
            entry = dict(candidate=asdict(candidate), stage="before_candidate", outcome="unknown")
            self.batch_journal.append(entry)
            self.budget.check()
            self.counts.queue_processed += 1
            if candidate.kind == 0:
                entry["stage"] = "immigrant_location"
                x, y = self._immigrant_location()
                entry.update(x_km=x, y_km=y, stage="immigrant_mark")
                Q = self._mark(2)  # Consumed even when this candidate is rejected.
                entry.update(Q=Q, stage="immigrant_acceptance")
                u_accept = self.streams.uniform(3)
                entry["acceptance_uniform"] = u_accept
                G = strict_stress(t, x, y, self.history, self.law.ell, self.law.psi)
                # Literal binary64 exponential comparison fixes floating-point policy.
                accepted = u_accept < math.exp(-self.law.eta * G)
                if not accepted:
                    self.counts.rejected_immigrants += 1
                    entry.update(stage="decision_complete", outcome="rejected")
                    self.batch_cursor += 1
                    continue
            else:
                entry["stage"] = "offspring_parent_guard"
                if candidate.parent not in self.accepted_lineages:
                    raise GeneratorFailure("orphan_offspring")
                parent = self.parents_by_lineage.get(candidate.parent)
                if parent is None or not parent.time < t:
                    raise GeneratorFailure("offspring_parent_not_strict")
                entry["stage"] = "offspring_location"
                x, y = self._radial_location(5, (parent.x, parent.y), self.law.sigma)
                entry.update(x_km=x, y_km=y, stage="offspring_mark")
                Q = self._mark(6)  # At global chronological occurrence, not scheduling.
            self.pending_uncommitted.append(Event(t, x, y, Q, candidate.kind, candidate.root,
                                                   candidate.lineage, candidate.parent))
            self.counts.accepted_decisions += 1
            entry.update(Q=Q, stage="decision_complete", outcome="accepted_uncommitted")
            self.batch_cursor += 1
        if len(self.history) + len(self.pending_uncommitted) > self.limits.accepted_events:
            raise GeneratorFailure("accepted_event_cap")
        decisions = tuple(self.pending_uncommitted)
        lineages = [event.lineage for event in decisions]
        if len(set(lineages)) != len(lineages) or any(l in self.accepted_lineages for l in lineages):
            raise GeneratorFailure("duplicate_lineage")
        entry_by_lineage = {tuple(entry["candidate"]["lineage"]): entry
                            for entry in self.batch_journal}
        # Commit the ENTIRE accepted batch before scheduling any descendants.
        self.batch_stage = "commit"
        for event in decisions:
            self._commit_event(event)
            self.pending_uncommitted.popleft()
            entry_by_lineage[event.lineage]["outcome"] = "committed"
        self.batch_stage = "schedule_children"
        for event in decisions:
            self._schedule_children(event)
        self.pending_batch = []
        self.batch_journal = []
        self.batch_cursor = 0
        self.batch_stage = "idle"

    def run(self) -> None:
        self._immigrant_times()
        while self.queue:
            self._process_next_batch()
        self.budget.check()


def _event_record(event: Event) -> dict:
    identifier = "I" + str(event.lineage[0]) + "".join("/C" + str(i) for i in event.lineage[1:])
    return {"event_id": identifier, "time_days": event.time, "x_km": event.x, "y_km": event.y,
            "Q": event.Q, "source_kind": "immigrant" if event.kind == 0 else "offspring",
            "root_immigrant_ordinal": event.root, "lineage": list(event.lineage),
            "parent_lineage": list(event.parent) if event.parent is not None else None,
            "partition": "warmup" if event.time < 30 else "training" if event.time < 395 else "test"}


def private_failure_snapshot(sim: _Simulator, downstream_candidate_slots: int = 19,
                             failure_code: str | None = None) -> dict:
    """Private caught-failure evidence, never copied into sanitized stdout."""
    return dict(simulation_phase_status="failed" if failure_code else "complete",
                simulation_failure_code=failure_code,
                batch_stage=sim.batch_stage, batch_cursor=sim.batch_cursor,
                unfinished_batch_decisions=max(0,len(sim.pending_batch)-sim.batch_cursor),
                popped_batch=[asdict(c) for c in sim.pending_batch],
                batch_journal=sim.batch_journal,
                pending_uncommitted=[_event_record(e) for e in sim.pending_uncommitted],
                active_parent_lineage=sim.active_parent_lineage,
                pending_child_delays=sim.pending_child_delays,
                committed_event_count=len(sim.history), counters=asdict(sim.counts),
                pending_queue_entries=len(sim.queue), replacement_seed_permitted=False,
                downstream_candidate_slots=downstream_candidate_slots)


def fitting_metadata(law: Law) -> dict:
    edges = [0.0, 100.0 / 3.0, 200.0 / 3.0, 100.0]
    rectangles = [[edges[x], edges[x+1], edges[y], edges[y+1]] for y in range(3) for x in range(3)]
    areas = [(r[1]-r[0])*(r[3]-r[2]) for r in rectangles]
    smooth = law.background == "smooth"
    return {"time_mode": "binary64_exact_value_ties", "integer_time_keys": None,
            "time_origin": "synthetic_day_zero", "T0_days": law.T0,
            "history_interval": [0.0, law.horizon], "warmup_interval": [0.0, min(30.0, law.horizon)],
            "training_interval": [30.0, min(395.0, law.horizon)] if law.horizon > 30 else None,
            "test_interval": [395.0, law.horizon] if law.horizon > 395 else None,
            "half_open_time_intervals": True, "rectangles": rectangles,
            "rectangle_column_order": ["x_min", "x_max", "y_min", "y_max"],
            "reference_pi": [a / 10000.0 for a in areas], "beta": law.beta, "sigma_km": law.sigma,
            "bg_floor": 0.05 if smooth else 1.0, "kde_xy": [[25.0,25.0],[75.0,75.0]] if smooth else [],
            "kde_h": 10.0 if smooth else None, "kde_weight": [0.5,0.5] if smooth else [],
            "full_immigrant_component_weights": [0.05,0.475,0.475] if smooth else [1.0],
            "adapter_projection": ["time_days", "x_km", "y_km", "Q"],
            "ancestry_fields_are_private": True}


def generate_registered(record: Mapping[str, Any], *, case_id: str, seed: int,
                        purpose: str, output_root: str | Path) -> dict:
    """Generate once into a fresh local directory; return sanitized receipt only.

    All accepted/partial rows and ancestry remain in private JSONL artifacts.
    Caps produce failed-seed artifacts, never shortened successful replicates.
    Receipt I/O is cooperative; an OS-blocked write still needs the scheduler's
    process-tree timeout/held-state handling, not an assumed hard Python timer.
    """
    admitted = validate_admission(record, case_id=case_id, seed=seed, purpose=purpose, output_root=output_root)
    law = registered_law(case_id, seed, purpose)
    folder = admitted.output_root / f"{case_id}_seed{seed}"
    folder.mkdir(parents=True, exist_ok=False)  # Never overwrite an earlier/failed attempt.
    limits = Limits()
    deadline = datetime.fromisoformat(admitted.deadline_utc.replace("Z", "+00:00"))
    remaining_deadline = (deadline - datetime.now(timezone.utc)).total_seconds()
    budget = Budget(limits, deadline_after=remaining_deadline)
    streams = ScalarStreams(seed, limits, budget)
    sim = _Simulator(law, limits, budget, streams)
    status, failure = "complete", None
    try:
        sim.run()
    except GeneratorFailure as exc:
        status, failure = "failed", exc.code
    except (OverflowError, ValueError, MemoryError) as exc:
        status, failure = "failed", "runtime_" + type(exc).__name__
    metadata = {"schema": SCHEMA, "source_epoch": SOURCE_EPOCH,
                "law": asdict(law), "limits": asdict(limits),
                "fitting_metadata": fitting_metadata(law), "purpose": purpose,
                "admission": asdict(admitted) | {"output_root": str(admitted.output_root)}}
    paths = {}
    for name, events in (("events.jsonl", sim.history), ("pending_uncommitted.jsonl", sim.pending_uncommitted)):
        path = folder / name
        with path.open("x", encoding="utf-8", newline="\n") as stream:
            for event in events:
                stream.write(json.dumps(_event_record(event), sort_keys=True, allow_nan=False) + "\n")
        paths[name] = {"path": str(path), "sha256": sha256(path)}
    queue_path = folder / "pending_queue_private.jsonl"
    with queue_path.open("x", encoding="utf-8", newline="\n") as stream:
        for candidate in sim.queue:
            stream.write(json.dumps(asdict(candidate), sort_keys=True, allow_nan=False) + "\n")
    paths[queue_path.name] = {"path": str(queue_path), "sha256": sha256(queue_path)}
    meta_path = folder / "catalogue_metadata.json"
    meta_path.write_text(json.dumps(metadata, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    paths[meta_path.name] = {"path": str(meta_path), "sha256": sha256(meta_path)}
    state_path = folder / "failure_state_private.json"
    state_path.write_text(json.dumps(private_failure_snapshot(sim,
                          19 if purpose == "scientific_control" else 0, failure), indent=2, allow_nan=False) + "\n",
                          encoding="utf-8")
    paths[state_path.name] = {"path": str(state_path), "sha256": sha256(state_path)}
    if budget.elapsed() >= limits.wall_seconds:
        status, failure = "failed", "wall_time_cap_including_flush"
    partitions = {name: 0 for name in ("warmup", "training", "test")}
    for event in sim.history:
        partitions["warmup" if event.time < 30 else "training" if event.time < 395 else "test"] += 1
    if budget.elapsed() >= remaining_deadline:
        status, failure = "failed", "global_deadline_including_flush"
    receipt = {"schema": "thread04_generator_sanitized_receipt_v1", "source_epoch": SOURCE_EPOCH,
               "case_id": case_id,
               "seed": seed, "purpose": purpose, "status": status, "failure_code": failure,
               "complete_horizon": status == "complete", "aggregate_partition_counts": partitions,
               "counters": asdict(sim.counts), "pending_queue_entries": len(sim.queue),
               "pending_uncommitted_count": len(sim.pending_uncommitted),
               "rng_counters_and_state_hashes": streams.snapshot(), "artifacts": paths,
               "elapsed_monotonic_seconds_before_receipt": budget.elapsed(),
               "contract_sha256": admitted.contract_sha256, "generator_source_sha256": admitted.source_sha256,
               "controls_source_sha256": admitted.controls_source_sha256,
               "runtime_sha256": admitted.runtime_sha256, "lease_id": admitted.lease_id,
               "fit_or_scientific_acceptance": False, "replacement_seed_permitted": False,
               "downstream_candidate_slots": 19 if purpose == "scientific_control" else 0,
               "downstream_status": "pending_controls_and_audit" if status == "complete" else "blocked_retained"}
    # Serialize locally first; stdout exposes only this closed scalar/path allowlist.
    receipt_path = folder / "receipt_sanitized.json"
    receipt_path.write_text(json.dumps(receipt, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    if (budget.elapsed() >= limits.wall_seconds or budget.elapsed() >= remaining_deadline) and receipt["status"] == "complete":
        code = "global_deadline_including_receipt_flush" if budget.elapsed() >= remaining_deadline else "wall_time_cap_including_receipt_flush"
        receipt.update(status="failed", failure_code=code,
                       complete_horizon=False, downstream_status="blocked_retained")
        receipt_path.write_text(json.dumps(receipt, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    return receipt


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--admission", required=True)
    parser.add_argument("--case-id", required=True)
    parser.add_argument("--seed", required=True, type=int)
    parser.add_argument("--purpose", required=True, choices=("engineering_pilot", "scientific_control"))
    parser.add_argument("--output-root", required=True)
    args = parser.parse_args(argv)
    try:
        record = json.loads(Path(args.admission).read_text(encoding="utf-8"))
        receipt = generate_registered(record, case_id=args.case_id, seed=args.seed,
                                      purpose=args.purpose, output_root=args.output_root)
        print(json.dumps(receipt, sort_keys=True, allow_nan=False))
        return 0 if receipt["status"] == "complete" else 2
    except (GeneratorFailure, FileExistsError, OSError, ValueError) as exc:
        # No raw exception text, rows, RNG state or traceback on stdout.
        print(json.dumps({"schema": "thread04_generator_preflight_failure_v1", "status": "failed",
                          "failure_code": getattr(exc, "code", type(exc).__name__),
                          "case_id": args.case_id, "seed": args.seed,
                          "fit_or_scientific_acceptance": False}))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
