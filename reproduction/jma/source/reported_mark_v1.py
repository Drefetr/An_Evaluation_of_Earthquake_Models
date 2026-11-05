"""Declared geometric reported-mark PMF and fixed-r normalized productivity.

Only the mark-PMF beta is an MLE here. Seven-arm time/location optimization is
the descriptive Route-A continuous-intensity criterion, not observed-data MLE.
No observed data, simulation, filtering or fitting driver exists in this module.
"""
from dataclasses import dataclass
import math
import numbers
import sys

DELTA = .1
R = .7
CENTISECONDS_PER_DAY = 8640000
FROZEN_TRAIN_START_KEY = 1826*CENTISECONDS_PER_DAY
FROZEN_ORIGIN_KEYS = tuple(day*CENTISECONDS_PER_DAY for day in (3652,4748,5844))


class MarkError(ValueError):
    pass


def integer(value, *, nonnegative=True):
    if isinstance(value,bool) or not isinstance(value,numbers.Integral) or (nonnegative and value<0):
        raise MarkError("EXACT_INTEGER_MARK_REQUIRED")
    return int(value)


def scale(beta):
    if isinstance(beta,bool) or not isinstance(beta,numbers.Real) or not math.isfinite(beta) or beta<=0:
        raise MarkError("FINITE_POSITIVE_BETA_REQUIRED")
    z=float(beta)*DELTA
    if not math.isfinite(z) or z<=0:
        raise MarkError("BETA_SCALE_UNREPRESENTABLE")
    return z


def log_one_minus_rho(beta):
    return math.log(-math.expm1(-scale(beta)))


def log_pmf(k,beta):
    k=integer(k);z=scale(beta)
    try:value=math.log(-math.expm1(-z))-z*k
    except OverflowError:raise MarkError("MARK_LOG_MASS_UNREPRESENTABLE") from None
    if not math.isfinite(value):
        raise MarkError("MARK_LOG_MASS_UNREPRESENTABLE")
    return value


def log_C(beta):
    z=scale(beta)
    numerator=-math.expm1(-(1-R)*z);denominator=-math.expm1(-z)
    if not 0<numerator<=denominator:
        raise MarkError("PRODUCTIVITY_NORMALIZER_UNREPRESENTABLE")
    return math.log(numerator)-math.log(denominator)


def log_kappa(k,beta):
    k=integer(k);z=scale(beta)
    try:value=log_C(beta)+R*z*k
    except OverflowError:raise MarkError("PRODUCTIVITY_UNREPRESENTABLE") from None
    if not math.isfinite(value):
        raise MarkError("PRODUCTIVITY_UNREPRESENTABLE")
    return value


def kappa(k,beta):
    value=log_kappa(k,beta)
    if value>math.log(sys.float_info.max):
        raise MarkError("PRODUCTIVITY_UNREPRESENTABLE")
    result=math.exp(value)
    if not math.isfinite(result) or result<=0:
        raise MarkError("PRODUCTIVITY_UNREPRESENTABLE")
    return result


def sufficient(ks):
    n=s=0
    for k in ks:
        n+=1;s+=integer(k)
    return n,s


def mark_total(ks,beta):
    n,s=sufficient(ks);z=scale(beta)
    try:value=n*math.log(-math.expm1(-z))-s*z
    except OverflowError:raise MarkError("MARK_TOTAL_UNREPRESENTABLE") from None
    if not math.isfinite(value):
        raise MarkError("MARK_TOTAL_UNREPRESENTABLE")
    return value


@dataclass(frozen=True,repr=False)
class TrainingMarkState:
    n: int
    s: int
    beta: float
    train_start_key: int
    origin_key: int
    def __repr__(self):
        return "<private frozen training-only mark state>"


def beta_from_sufficient(n,s):
    n,s=integer(n),integer(s)
    if n<=0 or s<=0:
        raise MarkError("GEOMETRIC_MLE_NO_FINITE_INTERIOR_SOLUTION")
    try:beta=math.log1p(n/s)/DELTA
    except (OverflowError,ZeroDivisionError):raise MarkError("BETA_MLE_UNREPRESENTABLE") from None
    scale(beta)
    return beta


def fit_scored_training(key_K_pairs,train_start_key,origin_key):
    start,end=integer(train_start_key,nonnegative=False),integer(origin_key,nonnegative=False)
    if start!=FROZEN_TRAIN_START_KEY or end not in FROZEN_ORIGIN_KEYS:
        raise MarkError("FROZEN_SCORED_TRAINING_SCOPE_REQUIRED")
    n=s=0;previous=None
    for key,k in key_K_pairs:
        key=integer(key,nonnegative=False);k=integer(k)
        if not -(1<<63)<=key<(1<<63) or not start<=key<end or (previous is not None and key<previous):
            raise MarkError("WARMUP_FUTURE_OR_UNSORTED_MARK_INPUT")
        previous=key;n+=1;s+=k
    return TrainingMarkState(n,s,beta_from_sufficient(n,s),start,end)


@dataclass(frozen=True,repr=False)
class MarkTerms:
    target_mark_log_mass: float
    parent_kappa: tuple
    target_count: int
    def __repr__(self):
        return "<private mark-once and parent-productivity terms>"


def mark_terms(parent_Ks,target_indices,beta):
    parents=tuple(integer(k) for k in parent_Ks)
    indices=tuple(integer(i) for i in target_indices)
    if any(index>=len(parents) for index in indices) or any(a>=b for a,b in zip(indices,indices[1:])):
        raise MarkError("TARGET_MARK_INDICES_NOT_UNIQUE_ORDERED_SUBSET")
    score=mark_total((parents[i] for i in indices),beta)
    return MarkTerms(score,tuple(kappa(k,beta) for k in parents),len(indices))
