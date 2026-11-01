"""Bounded public arithmetic for four-cell calibration decisions.

All inputs are explicit rows. Unknown reference or query values are ``None``
and are never treated as zero. This module performs no I/O, fitting,
simulation, resampling-index generation, or random-number generation.
"""

from bisect import bisect_left
from collections.abc import Sequence
from math import isfinite, sqrt
from numbers import Integral, Real


CELLS = ("I00", "I10", "I01", "I11")
INTERACTION_WEIGHTS = (1.0, -1.0, -1.0, 1.0)


def _finite_alpha(alpha):
    if isinstance(alpha, bool) or not isinstance(alpha, Real):
        raise TypeError("alpha must be a real number")
    alpha = float(alpha)
    if not isfinite(alpha) or not 0.0 < alpha < 1.0:
        raise ValueError("alpha must be finite and strictly between 0 and 1")
    return alpha


def _cell_value(value, label):
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, Real):
        raise TypeError(f"{label} must be a finite real number or None")
    value = float(value)
    if not isfinite(value):
        raise ValueError(f"{label} must be finite")
    return value


def _rows(rows, label):
    if isinstance(rows, (str, bytes)) or not isinstance(rows, Sequence):
        raise TypeError(f"{label} must be a sequence of 4-vectors")
    if not rows:
        raise ValueError(f"{label} must contain at least one row")
    result = []
    for row_index, row in enumerate(rows):
        if isinstance(row, (str, bytes)) or not isinstance(row, Sequence):
            raise TypeError(f"{label}[{row_index}] must be a 4-vector")
        if len(row) != len(CELLS):
            raise ValueError(f"{label}[{row_index}] must have exactly 4 cells")
        result.append(
            tuple(
                _cell_value(value, f"{label}[{row_index}][{cell_index}]")
                for cell_index, value in enumerate(row)
            )
        )
    return tuple(result)


def _plans(plans, plan_length, index_limit, label):
    if isinstance(plans, (str, bytes)) or not isinstance(plans, Sequence):
        raise TypeError(f"{label} must be a sequence of index vectors")
    if not plans:
        raise ValueError(f"{label} must contain at least one replicate plan")
    result = []
    for plan_index, plan in enumerate(plans):
        if isinstance(plan, (str, bytes)) or not isinstance(plan, Sequence):
            raise TypeError(f"{label}[{plan_index}] must be an index vector")
        if len(plan) != plan_length:
            raise ValueError(
                f"{label}[{plan_index}] must have length {plan_length}"
            )
        indices = []
        for position, index in enumerate(plan):
            if isinstance(index, bool) or not isinstance(index, Integral):
                raise TypeError(
                    f"{label}[{plan_index}][{position}] must be an integer"
                )
            index = int(index)
            if not 0 <= index < index_limit:
                raise ValueError(
                    f"{label}[{plan_index}][{position}] is outside "
                    f"0..{index_limit - 1}"
                )
            indices.append(index)
        result.append(tuple(indices))
    return tuple(result)


def _decision(interval, alpha):
    if interval is None:
        return None
    lower, upper = interval
    if upper <= alpha:
        return True
    if lower > alpha:
        return False
    return None


def _row_interaction_bounds(decisions):
    lower = 0.0
    upper = 0.0
    for weight, decision in zip(INTERACTION_WEIGHTS, decisions):
        if decision is True:
            lower += weight
            upper += weight
        elif decision is None:
            if weight > 0.0:
                upper += weight
            else:
                lower += weight
    return lower, upper


def calibrate(reference_rows, query_rows, alpha=0.05):
    """Calibrate all four cells for aligned reference and query rows.

    Each known query/cell interval is add-one smoothed over the full reference
    denominator ``R + 1``. ``known_ge`` counts known reference values greater
    than or equal to the query, so ties are retained. Unknown references widen
    the upper endpoint. A ``None`` query has no interval and decision ``None``.

    Per-cell ``rejection_bounds`` are conservative proportion bounds over all
    planned query rows: ``[True / N, (True + None) / N]``. Interaction bounds
    use row weights ``(1, -1, -1, 1)`` with each unknown decision allowed to be
    binary 0 or 1. A paired point mean and MCSE are returned only when every
    row resolves all four decisions and ``N >= 2``.
    """

    alpha = _finite_alpha(alpha)
    reference_rows = _rows(reference_rows, "reference_rows")
    query_rows = _rows(query_rows, "query_rows")
    reference_count = len(reference_rows)
    query_count = len(query_rows)

    sorted_known = []
    unknown_reference_counts = []
    for cell_index in range(len(CELLS)):
        known = sorted(
            row[cell_index]
            for row in reference_rows
            if row[cell_index] is not None
        )
        sorted_known.append(known)
        unknown_reference_counts.append(reference_count - len(known))

    rank_intervals = {cell: [] for cell in CELLS}
    decisions = {cell: [] for cell in CELLS}
    rejection_bounds = {}

    for row in query_rows:
        for cell_index, cell in enumerate(CELLS):
            query_value = row[cell_index]
            if query_value is None:
                interval = None
            else:
                known = sorted_known[cell_index]
                known_ge = len(known) - bisect_left(known, query_value)
                unknown = unknown_reference_counts[cell_index]
                interval = [
                    (1 + known_ge) / (reference_count + 1),
                    (1 + known_ge + unknown) / (reference_count + 1),
                ]
            rank_intervals[cell].append(interval)
            decisions[cell].append(_decision(interval, alpha))

    for cell in CELLS:
        rejected = sum(decision is True for decision in decisions[cell])
        unknown = sum(decision is None for decision in decisions[cell])
        rejection_bounds[cell] = [
            rejected / query_count,
            (rejected + unknown) / query_count,
        ]

    row_bounds = [
        _row_interaction_bounds(
            tuple(decisions[cell][row_index] for cell in CELLS)
        )
        for row_index in range(query_count)
    ]
    interaction_bounds = [
        sum(bound[0] for bound in row_bounds) / query_count,
        sum(bound[1] for bound in row_bounds) / query_count,
    ]

    all_resolved = all(
        decisions[cell][row_index] is not None
        for row_index in range(query_count)
        for cell in CELLS
    )
    if not all_resolved:
        interaction_status = "unresolved"
    elif query_count < 2:
        interaction_status = "insufficient"
    else:
        interaction_status = "resolved"

    interaction_mean = None
    interaction_mcse = None
    if interaction_status == "resolved":
        row_values = [
            sum(
                weight * decision
                for weight, decision in zip(
                    INTERACTION_WEIGHTS,
                    (decisions[cell][row_index] for cell in CELLS),
                )
            )
            for row_index in range(query_count)
        ]
        interaction_mean = sum(row_values) / query_count
        sample_variance = sum(
            (value - interaction_mean) ** 2 for value in row_values
        ) / (query_count - 1)
        interaction_mcse = sqrt(sample_variance / query_count)

    return {
        "cells": CELLS,
        "rank_intervals": rank_intervals,
        "decisions": decisions,
        "rejection_bounds": rejection_bounds,
        "interaction_bounds": interaction_bounds,
        "interaction": {
            "status": interaction_status,
            "mean": interaction_mean,
            "mcse": interaction_mcse,
        },
    }


def summarize_resamples(
    reference_rows,
    query_rows,
    reference_plans,
    query_plans=None,
    alpha=0.05,
):
    """Recalibrate explicit replicate plans and return compact results.

    ``reference_plans`` and optional ``query_plans`` are sequences of index
    vectors, one vector per replicate. Reference vectors have length ``R``;
    query vectors have length ``N``. The same reference indices are used for
    all four cells. With ``query_plans=None`` the original query rows are held
    fixed, isolating reference-plan sensitivity. Supplied query plans pair the
    same query rows across all four cells.

    Output contains only replicate-level rejection endpoints, interaction
    bounds, and paired point-mean/MCSE status. Query-level decisions are not
    retained for each replicate.
    """

    alpha = _finite_alpha(alpha)
    reference_rows = _rows(reference_rows, "reference_rows")
    query_rows = _rows(query_rows, "query_rows")
    reference_count = len(reference_rows)
    query_count = len(query_rows)

    reference_plans = _plans(
        reference_plans,
        reference_count,
        reference_count,
        "reference_plans",
    )
    if query_plans is not None:
        query_plans = _plans(
            query_plans,
            query_count,
            query_count,
            "query_plans",
        )
        if len(query_plans) != len(reference_plans):
            raise ValueError(
                "reference_plans and query_plans must have the same number "
                "of replicates"
            )

    replicate_count = len(reference_plans)
    rejection_bounds = {
        cell: {"lower": [], "upper": []} for cell in CELLS
    }
    interaction_bounds = {"lower": [], "upper": []}
    point_mcse = {"status": [], "mean": [], "mcse": []}

    for replicate_index in range(replicate_count):
        sampled_references = tuple(
            reference_rows[index]
            for index in reference_plans[replicate_index]
        )
        if query_plans is None:
            sampled_queries = query_rows
        else:
            sampled_queries = tuple(
                query_rows[index] for index in query_plans[replicate_index]
            )

        result = calibrate(sampled_references, sampled_queries, alpha)
        for cell in CELLS:
            lower, upper = result["rejection_bounds"][cell]
            rejection_bounds[cell]["lower"].append(lower)
            rejection_bounds[cell]["upper"].append(upper)
        interaction_bounds["lower"].append(result["interaction_bounds"][0])
        interaction_bounds["upper"].append(result["interaction_bounds"][1])
        point_mcse["status"].append(result["interaction"]["status"])
        point_mcse["mean"].append(result["interaction"]["mean"])
        point_mcse["mcse"].append(result["interaction"]["mcse"])

    return {
        "cells": CELLS,
        "replicates": replicate_count,
        "query_mode": "fixed" if query_plans is None else "paired_resample",
        "rejection_bounds": rejection_bounds,
        "interaction_bounds": interaction_bounds,
        "point_mcse": point_mcse,
    }
