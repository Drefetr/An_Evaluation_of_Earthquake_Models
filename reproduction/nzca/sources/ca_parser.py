"""Self-contained parser for the synthetic SCEDC schema packet.

The module deliberately has no acquisition, I/O, printing, network, or
subprocess functionality. All externally visible error text is a fixed code.
"""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
import re
from typing import Any, Iterable


# Fixed, input-independent error codes.
ERR_LINE = "invalid_line"
ERR_TOKEN_COUNT = "invalid_token_count"
ERR_DATE = "invalid_date"
ERR_TIME = "invalid_time"
ERR_NUMERIC = "invalid_numeric"
ERR_EVENTTYPE = "invalid_eventtype"
ERR_MAGTYPE = "unknown_magtype"
ERR_QUALITY = "unknown_quality"
ERR_COUNT = "invalid_count"
ERR_ID = "invalid_id"
ERR_RECORD = "invalid_record"
ERR_DUPLICATE_CONFLICT = "duplicate_conflict"
ERR_INTERNAL = "internal_error"

FIXED_CODES = frozenset(
    {
        ERR_LINE,
        ERR_TOKEN_COUNT,
        ERR_DATE,
        ERR_TIME,
        ERR_NUMERIC,
        ERR_EVENTTYPE,
        ERR_MAGTYPE,
        ERR_QUALITY,
        ERR_COUNT,
        ERR_ID,
        ERR_RECORD,
        ERR_DUPLICATE_CONFLICT,
        ERR_INTERNAL,
    }
)

MAG_TYPES = frozenset(("e", "w", "b", "s", "l", "lr", "c", "h", "d", "n"))
QUALITIES = frozenset(("A", "B", "C", "D", "Z"))


# User-authorized schema successor: quality is unused opaque metadata.
# Preserve the exact nonempty whitespace-delimited ASCII token; do not infer
# agency semantics or normalize known/unknown strings. All other rules below
# are inherited byte-for-byte from parse_v2.py.
DEPENDENCY_FILENAMES = ("parse_v3.py",)

def quality_token_allowed(token: str) -> bool:
    return type(token) is str and bool(token) and all(33 <= ord(char) <= 126 for char in token)

FIELDS = (
    "date",
    "time",
    "eventtype",
    "gtype",
    "magnitude",
    "magtype",
    "latitude",
    "longitude",
    "depth",
    "quality",
    "eventid",
    "nph",
    "ngrams",
)

RECTANGLE = (Decimal("-121"), Decimal("-114"), Decimal("32"), Decimal("37"))
DEPTH_BOUNDS = (Decimal("-5"), Decimal("40"))
MINIMUM_MAGNITUDE = Decimal("4.0")

_DATE_RE = re.compile(r"([0-9]{4})/([0-9]{2})/([0-9]{2})\Z", re.ASCII)
_TIME_RE = re.compile(
    r"([0-9]{2}):([0-9]{2}):([0-9]{2})(?:\.([0-9]{1,6}))?\Z",
    re.ASCII,
)
_DECIMAL_RE = re.compile(
    r"[+-]?(?:[0-9]+(?:\.[0-9]*)?|\.[0-9]+)(?:[eE][+-]?[0-9]+)?\Z",
    re.ASCII,
)
_COUNT_RE = re.compile(r"[0-9]+\Z", re.ASCII)

_EPOCH = datetime(1970, 1, 1, tzinfo=timezone.utc)


class ParseError(ValueError):
    """A parser failure whose complete message is a fixed safe code."""

    def __init__(self, code: str) -> None:
        self.code = code if code in FIXED_CODES else ERR_INTERNAL
        super().__init__(self.code)

    def __str__(self) -> str:
        return self.code


class DuplicateConflictError(ParseError):
    """Raised when one canonical event id has conflicting source tokens."""

    def __init__(self) -> None:
        super().__init__(ERR_DUPLICATE_CONFLICT)


# Descriptive aliases for callers using the names from the packet prose.
FixedParseError = ParseError
DuplicateConflict = DuplicateConflictError
FixedDuplicateConflict = DuplicateConflictError


def _utc_microseconds(
    year: int, month: int, day: int, hour: int, minute: int, second: int,
    microsecond: int,
) -> int:
    moment = datetime(
        year, month, day, hour, minute, second, microsecond, tzinfo=timezone.utc
    )
    delta = moment - _EPOCH
    return ((delta.days * 86_400) + delta.seconds) * 1_000_000 + delta.microseconds


def _parse_timestamp_us(date_token: str, time_token: str) -> int:
    date_match = _DATE_RE.fullmatch(date_token)
    if date_match is None:
        raise ParseError(ERR_DATE) from None
    time_match = _TIME_RE.fullmatch(time_token)
    if time_match is None:
        raise ParseError(ERR_TIME) from None

    year, month, day = (int(part) for part in date_match.groups())
    hour, minute, second = (int(part) for part in time_match.groups()[:3])
    fraction = time_match.group(4) or ""
    if hour > 23 or minute > 59 or second > 59:
        raise ParseError(ERR_TIME) from None
    microsecond = int(fraction.ljust(6, "0")) if fraction else 0

    try:
        return _utc_microseconds(year, month, day, hour, minute, second, microsecond)
    except (ValueError, OverflowError):
        raise ParseError(ERR_DATE) from None


def _decimal_from_token(token: str) -> Decimal:
    if _DECIMAL_RE.fullmatch(token) is None:
        raise ParseError(ERR_NUMERIC) from None
    try:
        value = Decimal(token)
    except (InvalidOperation, ValueError):
        raise ParseError(ERR_NUMERIC) from None
    if not value.is_finite():
        raise ParseError(ERR_NUMERIC) from None
    return value


def _decimal_from_record(record: dict[str, Any], name: str) -> Decimal:
    value = record.get(name)
    if isinstance(value, Decimal):
        if value.is_finite():
            return value
        raise ParseError(ERR_RECORD) from None
    if isinstance(value, str):
        try:
            return _decimal_from_token(value)
        except ParseError:
            raise ParseError(ERR_RECORD) from None
    raise ParseError(ERR_RECORD) from None


def _parse_count(token: str) -> int:
    if _COUNT_RE.fullmatch(token) is None:
        raise ParseError(ERR_COUNT) from None
    try:
        return int(token)
    except (ValueError, OverflowError):
        raise ParseError(ERR_COUNT) from None


def _parse_fields(tokens: list[str]) -> dict[str, Any]:
    (date, time, eventtype, gtype, magnitude, magtype, latitude, longitude,
     depth, quality, eventid, nph, ngrams) = tokens

    timestamp_us = _parse_timestamp_us(date, time)
    if not eventtype:
        raise ParseError(ERR_EVENTTYPE) from None
    if magtype not in MAG_TYPES:
        raise ParseError(ERR_MAGTYPE) from None
    if not quality_token_allowed(quality):
        raise ParseError(ERR_QUALITY) from None
    if not eventid:
        raise ParseError(ERR_ID) from None

    magnitude_value = _decimal_from_token(magnitude)
    latitude_value = _decimal_from_token(latitude)
    longitude_value = _decimal_from_token(longitude)
    depth_value = _decimal_from_token(depth)
    if not (Decimal("-90") <= latitude_value <= Decimal("90")):
        raise ParseError(ERR_NUMERIC) from None
    if not (Decimal("-180") <= longitude_value <= Decimal("180")):
        raise ParseError(ERR_NUMERIC) from None

    nph_value = _parse_count(nph)
    ngrams_value = _parse_count(ngrams)

    canonical_id = "scedc:" + eventid
    record: dict[str, Any] = {
        "date": date,
        "time": time,
        "eventtype": eventtype,
        "gtype": gtype,
        "magnitude": magnitude,
        "magtype": magtype,
        "latitude": latitude,
        "longitude": longitude,
        "depth": depth,
        "quality": quality,
        "eventid": eventid,
        "nph": nph_value,
        "ngrams": ngrams_value,
        "original_tokens": list(tokens),
        "timestamp_us": timestamp_us,
        "canonical_id": canonical_id,
        "id": canonical_id,
        "magnitude_missing": magtype == "n",
    }

    # The four numeric values above are compared as Decimal while parsing.
    # They are exposed as exact source strings, never as binary floats.
    del magnitude_value, latitude_value, longitude_value, depth_value

    classification = _classify(record)
    record["classification"] = classification
    record["eligible"] = classification in ("training", "protected")
    return record


def parse_line(line: str) -> dict[str, Any] | None:
    """Parse one synthetic SCEDC row.

    Empty and comment-only lines return ``None``. A data row must have exactly
    13 whitespace-separated tokens. Numeric values are validated and compared
    with :class:`decimal.Decimal`, while the returned fields retain the exact
    source token strings. ``timestamp_us`` is exact integer UTC microseconds.
    """

    if not isinstance(line, str):
        raise ParseError(ERR_LINE) from None

    candidate = line.lstrip()
    if not candidate:
        return None
    if candidate.startswith("#"):
        return None

    tokens = candidate.split()
    if len(tokens) != len(FIELDS):
        raise ParseError(ERR_TOKEN_COUNT) from None
    return _parse_fields(tokens)


def _classify(record: dict[str, Any]) -> str:
    eventtype = record.get("eventtype")
    magtype = record.get("magtype")
    if eventtype != "eq":
        return "excluded_type"
    if magtype == "n" or record.get("magnitude_missing") is True:
        return "excluded_magnitude_missing"

    magnitude = _decimal_from_record(record, "magnitude")
    if magnitude < MINIMUM_MAGNITUDE:
        return "excluded_magnitude"

    latitude = _decimal_from_record(record, "latitude")
    longitude = _decimal_from_record(record, "longitude")
    west, east, south, north = RECTANGLE
    if not (west <= longitude <= east and south <= latitude <= north):
        return "excluded_geography"

    depth = _decimal_from_record(record, "depth")
    shallow, deep = DEPTH_BOUNDS
    if not (shallow <= depth <= deep):
        return "excluded_depth"

    timestamp_us = _timestamp_us_from_record(record)
    if timestamp_us < _HISTORY_START_US:
        return "outside_time"
    if timestamp_us < _TRAINING_START_US:
        return "prehistory"
    if timestamp_us < _PROTECTED_START_US:
        return "training"
    if timestamp_us < _END_US:
        return "protected"
    return "outside_time"


_HISTORY_START_US = _utc_microseconds(1981, 1, 1, 0, 0, 0, 0)
_TRAINING_START_US = _utc_microseconds(1986, 1, 1, 0, 0, 0, 0)
_PROTECTED_START_US = _utc_microseconds(2011, 1, 1, 0, 0, 0, 0)
_END_US = _utc_microseconds(2026, 1, 1, 0, 0, 0, 0)


def _timestamp_us_from_record(record: dict[str, Any]) -> int:
    value = record.get("timestamp_us")
    if isinstance(value, int) and not isinstance(value, bool):
        return value
    date = record.get("date")
    time = record.get("time")
    if isinstance(date, str) and isinstance(time, str):
        return _parse_timestamp_us(date, time)
    raise ParseError(ERR_RECORD) from None


def classify_record(record: dict[str, Any]) -> str:
    """Return one frozen eligibility/time class for a parsed record.

    Structural exclusions are evaluated before temporal bands. Spatial and
    depth rectangles are closed; temporal bands are half-open. The band from
    the history start to the training start is ``prehistory``.
    """

    if not isinstance(record, dict):
        raise ParseError(ERR_RECORD) from None
    try:
        return _classify(record)
    except ParseError:
        raise
    except (KeyError, TypeError, ValueError, OverflowError):
        raise ParseError(ERR_RECORD) from None


def _canonical_identity(record: dict[str, Any]) -> tuple[str, tuple[str, ...]]:
    if not isinstance(record, dict):
        raise ParseError(ERR_RECORD) from None

    tokens_value = record.get("original_tokens")
    if not isinstance(tokens_value, (list, tuple)):
        raise ParseError(ERR_RECORD) from None
    tokens = tuple(tokens_value)
    if len(tokens) != len(FIELDS) or any(not isinstance(token, str) for token in tokens):
        raise ParseError(ERR_RECORD) from None

    eventid = record.get("eventid", tokens[10])
    if not isinstance(eventid, str) or not eventid:
        raise ParseError(ERR_ID) from None
    if eventid != tokens[10]:
        raise ParseError(ERR_RECORD) from None
    expected_id = "scedc:" + eventid
    canonical_id = record.get("canonical_id", record.get("id", expected_id))
    if not isinstance(canonical_id, str) or not canonical_id:
        raise ParseError(ERR_ID) from None
    if canonical_id != expected_id:
        raise ParseError(ERR_RECORD) from None
    return canonical_id, tokens


def deduplicate(
    records: Iterable[dict[str, Any]],
) -> tuple[list[dict[str, Any]], int]:
    """Collapse identical source rows and sort by timestamp, then id.

    A repeated id is accepted only when its exact original token tuple is
    identical. A repeated id with different tokens raises the fixed
    ``duplicate_conflict`` error. Distinct ids at the same timestamp remain
    distinct and are ordered lexically by canonical id.
    """

    unique: dict[str, tuple[tuple[str, ...], dict[str, Any], int]] = {}
    duplicate_count = 0

    try:
        iterator = iter(records)
    except TypeError:
        raise ParseError(ERR_RECORD) from None

    for record in iterator:
        canonical_id, tokens = _canonical_identity(record)
        timestamp_us = _timestamp_us_from_record(record)
        existing = unique.get(canonical_id)
        if existing is None:
            unique[canonical_id] = (tokens, record, timestamp_us)
            continue
        existing_tokens, _, existing_timestamp_us = existing
        if tokens != existing_tokens or timestamp_us != existing_timestamp_us:
            raise DuplicateConflictError() from None
        duplicate_count += 1

    ordered = sorted(unique.items(), key=lambda item: (item[1][2], item[0]))
    return [item[1][1] for item in ordered], duplicate_count


def parse_structural_line(line: str) -> dict[str, Any] | None:
    """Validate source structure/date; expose a narrowly unavailable clock.

    This native successor retains strict parse_line unchanged. It never invents
    a timestamp. Calendar-date diagnostics can use the separate source_date;
    callers MUST reject unavailable clocks for every non-time-eligible M4 row.
    Only the observed lexical seconds-60 range is recognized as unavailable;
    malformed clocks and every other structural error remain fatal.
    """
    if not isinstance(line, str):
        raise ParseError(ERR_LINE) from None
    candidate = line.lstrip()
    if not candidate or candidate.startswith("#"):
        return None
    tokens = candidate.split()
    if len(tokens) != len(FIELDS):
        raise ParseError(ERR_TOKEN_COUNT) from None
    (date, clock, eventtype, gtype, magnitude, magtype, latitude, longitude,
     depth, quality, eventid, nph, ngrams) = tokens
    match = _DATE_RE.fullmatch(date)
    if match is None:
        raise ParseError(ERR_DATE) from None
    try:
        source_date = datetime(*(int(part) for part in match.groups())).date()
    except (ValueError, OverflowError):
        raise ParseError(ERR_DATE) from None
    if eventtype not in {"eq", "qb", "nt", "ex", "sh", "sn", "st", "th", "uk"}:
        raise ParseError(ERR_EVENTTYPE) from None
    if gtype not in {"l", "r", "t"}:
        raise ParseError(ERR_RECORD) from None
    if magtype not in MAG_TYPES:
        raise ParseError(ERR_MAGTYPE) from None
    if not quality_token_allowed(quality):
        raise ParseError(ERR_QUALITY) from None
    if not eventid:
        raise ParseError(ERR_ID) from None
    magnitude_value = _decimal_from_token(magnitude)
    latitude_value = _decimal_from_token(latitude)
    longitude_value = _decimal_from_token(longitude)
    depth_value = _decimal_from_token(depth)
    if not Decimal("-90") <= latitude_value <= Decimal("90"):
        raise ParseError(ERR_NUMERIC) from None
    if not Decimal("-180") <= longitude_value <= Decimal("180"):
        raise ParseError(ERR_NUMERIC) from None
    nph_value, ngrams_value = _parse_count(nph), _parse_count(ngrams)
    try:
        timestamp_us = _parse_timestamp_us(date, clock)
        origin_time_utc = date.replace("/", "-") + "T" + clock + "Z"
        clock_status = "valid"
    except ParseError:
        match = _TIME_RE.fullmatch(clock)
        if match is None:
            raise ParseError(ERR_TIME) from None
        hour, minute, second = (int(part) for part in match.groups()[:3])
        if hour > 23 or minute > 59 or second != 60:
            raise ParseError(ERR_TIME) from None
        timestamp_us = None
        origin_time_utc = None
        clock_status = "unsupported_second_60"
    return {
        **dict(zip(FIELDS, tokens)), "nph": nph_value, "ngrams": ngrams_value,
        "original_tokens": list(tokens), "timestamp_us": timestamp_us,
        "origin_time_utc": origin_time_utc, "source_date": source_date.isoformat(),
        "source_year": source_date.year, "clock_validation_status": clock_status,
        "canonical_id": "scedc:" + eventid, "id": "scedc:" + eventid,
        "magnitude_missing": magtype == "n",
    }

