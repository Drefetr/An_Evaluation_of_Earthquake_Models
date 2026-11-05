"""Verbatim historical catalogue_v4 selection and lane-parser functions.
Absolute run authorization/acquisition orchestration is intentionally absent.
Portable replay supplies only verified files and a new output directory.
"""
import datetime as dt
from decimal import Decimal
from fractions import Fraction
import hashlib
import json
import os
from pathlib import Path
import uuid

COMMIT = "7105f6c1b861db46c3a8454984588f5b6a4a56e4"
UTC = dt.timezone.utc
EPOCH = dt.datetime(1970, 1, 1, tzinfo=UTC)
LATITUDE_FLOAT_EDGES = (32.0, 33.666666666666664, 35.333333333333336, 37.0)
LONGITUDE_FLOAT_EDGES = (-121.0, -118.66666666666667, -116.33333333333333, -114.0)
FIELDS = ("date", "time", "eventtype", "gtype", "magnitude", "magtype", "latitude", "longitude", "depth", "quality", "eventid", "nph", "ngrams")

class CustodyError(Exception):
    def __init__(self, code):
        self.code = code
        super().__init__(code)


def utcnow():
    return dt.datetime.now(UTC).isoformat()


def json_bytes(value):
    return (json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False) + "\n").encode("utf-8")


def atomic_json(path, value):
    path = Path(path)
    temporary = path.with_name(path.name + "." + uuid.uuid4().hex + ".part")
    try:
        with temporary.open("xb") as stream:
            stream.write(json_bytes(value))
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        if temporary.exists():
            temporary.unlink()


def append_json(path, value):
    with Path(path).open("ab") as stream:
        stream.write(json_bytes(value))
        stream.flush()
        os.fsync(stream.fileno())


def read_json(path):
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except Exception:
        raise CustodyError("CONTROL_JSON_INVALID") from None


def source_time(date, clock):
    try:
        value = dt.datetime.strptime(date + " " + clock, "%Y/%m/%d %H:%M:%S.%f" if "." in clock else "%Y/%m/%d %H:%M:%S").replace(tzinfo=UTC)
        delta = value - EPOCH
        micros = (delta.days * 86400 + delta.seconds) * 1000000 + delta.microseconds
        return value, micros, date.replace("/", "-") + "T" + clock + "Z"
    except Exception:
        raise CustodyError("INVALID_SOURCE_TIMESTAMP") from None


def in_population(tokens):
    if tokens[2] != "eq":
        return "excluded_type"
    latitude, longitude, depth = (Decimal(tokens[i]) for i in (6, 7, 8))
    if not (Decimal(32) <= latitude <= Decimal(37) and Decimal(-121) <= longitude <= Decimal(-114)):
        return "excluded_geography"
    if not Decimal(-5) <= depth <= Decimal(40):
        return "excluded_depth"
    if tokens[5] == "n":
        return "excluded_magnitude_missing"
    return "eligible_geometry"


def exact_axis_index(token, minimum, maximum):
    """Exact source-decimal/rational comparison, independent of Decimal context."""
    value = Fraction(Decimal(token))
    if value < minimum or value > maximum:
        return -1
    scaled = (value - minimum) * 3
    width = maximum - minimum
    return 0 if scaled < width else 1 if scaled < 2 * width else 2


def float_axis_index(token, edges):
    value = float(Decimal(token))
    if value < edges[0] or value > edges[-1]:
        return -1
    return 0 if value < edges[1] else 1 if value < edges[2] else 2


def validate_boundary_assignment(latitude, longitude):
    source = (exact_axis_index(latitude, 32, 37), exact_axis_index(longitude, -121, -114))
    converted = (float_axis_index(latitude, LATITUDE_FLOAT_EDGES),
                 float_axis_index(longitude, LONGITUDE_FLOAT_EDGES))
    if source != converted:
        raise CustodyError("SOURCE_BOUNDARY_ASSIGNMENT_MISMATCH")
    return source


def zone_index(latitude):
    return exact_axis_index(latitude, 32, 37)


def canonical(tokens, year, lineno, micros, iso):
    return {"event_id": "scedc:" + tokens[10], "origin_time_utc": iso, "origin_time_us": micros,
            "latitude": float(Decimal(tokens[6])), "longitude": float(Decimal(tokens[7])),
            "depth_km": float(Decimal(tokens[8])), "magnitude": float(Decimal(tokens[4])),
            "magnitude_type": tokens[5], "event_type": tokens[2], "source_year": year,
            "source_line_1based": lineno, "source_tokens": dict(zip(FIELDS, tokens)),
            "review_status": None, "uncertainty": None, "location_quality": tokens[9], "geographic_type": tokens[3]}


def diagnostic_record(tokens, year, lineno, record):
    """Date-only diagnostic representation; unavailable clocks remain null."""
    result = canonical(tokens, year, lineno, record["timestamp_us"], record["origin_time_utc"])
    result.update(source_date=record["source_date"], clock_validation_status=record["clock_validation_status"])
    return result


def parse_lane(raw, entries, parser, lane, private, opposite_index=None):
    seen = {}
    duplicates = []
    events, diagnostic = [], []
    raw_counts = {}
    precision = {k: {} for k in ("time", "latitude", "longitude", "depth", "magnitude")}
    counts = [[0] * 3 for _ in range(6)]
    hist = [[[0] * 65 for _ in range(3)] for _ in range(6)]
    missing = overflow = 0
    clock_counts = {}
    diagnostic_clock_unavailable = 0
    for entry in entries:
        year = int(Path(entry["path"]).stem)
        with (raw / Path(entry["path"]).name).open("r", encoding="ascii", errors="strict") as stream:
            for lineno, line in enumerate(stream, 1):
                try:
                    record = parser.parse_structural_line(line)
                    if record is None:
                        continue
                    tokens = line.split()
                    if len(tokens) != 13:
                        raise CustodyError("SOURCE_TOKEN_COUNT")
                    if tokens[2] not in {"eq", "qb", "nt", "ex", "sh", "sn", "st", "th", "uk"} or tokens[3] not in {"l", "r", "t"}:
                        raise CustodyError("UNKNOWN_SOURCE_TYPE_CODE")
                    if record.get("original_tokens") != tokens:
                        raise CustodyError("PARSER_CANONICAL_DISAGREEMENT")
                    if record["clock_validation_status"] == "valid":
                        stamp, micros, iso = source_time(tokens[0], tokens[1])
                        if record.get("timestamp_us") != micros or record.get("origin_time_utc") != iso:
                            raise CustodyError("PARSER_CANONICAL_DISAGREEMENT")
                    elif record["clock_validation_status"] == "unsupported_second_60":
                        micros = iso = None
                        if record["timestamp_us"] is not None or record["origin_time_utc"] is not None:
                            raise CustodyError("PARSER_CANONICAL_DISAGREEMENT")
                    else:
                        raise CustodyError("PARSER_CLOCK_STATUS_INVALID")
                    validate_boundary_assignment(tokens[6], tokens[7])
                    if record["source_year"] != year:
                        raise CustodyError("ANNUAL_YEAR_MISMATCH")
                    rowhash = hashlib.sha256(json_bytes(tokens)).digest()
                    previous = seen.get(tokens[10])
                    if previous:
                        if previous[0] != rowhash:
                            raise CustodyError("CONFLICTING_DUPLICATE_ID")
                        duplicates.append({"source_year": year, "source_line_1based": lineno,
                                           "original_year": previous[1], "original_line_1based": previous[2]})
                        continue
                    seen[tokens[10]] = (rowhash, year, lineno)
                    status = record["clock_validation_status"]
                    clock_counts[status] = clock_counts.get(status, 0) + 1
                    if status != "valid":
                        append_json(private / "private_clock_unavailable.jsonl", {
                            "source_year": year, "source_line_1based": lineno,
                            "clock_validation_status": status})
                    for name, index in (("time", 1), ("latitude", 6), ("longitude", 7), ("depth", 8), ("magnitude", 4)):
                        digits = str(len(tokens[index].split(".", 1)[1])) if "." in tokens[index] else "0"
                        precision[name][digits] = precision[name].get(digits, 0) + 1
                    reason = in_population(tokens)
                    raw_counts[reason] = raw_counts.get(reason, 0) + 1
                    if reason == "excluded_magnitude_missing":
                        missing += 1
                    if reason != "eligible_geometry":
                        continue
                    magnitude = Decimal(tokens[4])
                    if magnitude >= 2:
                        diagnostic.append(diagnostic_record(tokens, year, lineno, record))
                        diagnostic_clock_unavailable += status != "valid"
                        if lane == "train":
                            period, zone = (year - 1981) // 5, zone_index(tokens[6])
                            counts[period][zone] += 1
                            if magnitude > Decimal("8.5"):
                                overflow += 1
                            else:
                                index = min(int((magnitude - Decimal(2)) * 10), 64)
                                hist[period][zone][index] += 1
                    if magnitude >= 4:
                        if status != "valid":
                            raise CustodyError("MODEL_CLOCK_UNAVAILABLE")
                        events.append(canonical(tokens, year, lineno, micros, iso))
                except Exception as error:
                    append_json(private / "schema_failures.jsonl", {"utc": utcnow(), "source_year": year,
                                "source_line_1based": lineno, "error_class": type(error).__name__,
                                "error_code": error.code if isinstance(error, CustodyError) else "SOURCE_SCHEMA_FAILURE"})
                    code = error.code if isinstance(error, CustodyError) and error.code in {"SOURCE_BOUNDARY_ASSIGNMENT_MISMATCH", "MODEL_CLOCK_UNAVAILABLE"} else "SOURCE_SCHEMA_FAILURE"
                    raise CustodyError(code) from None
    if opposite_index is not None:
        other = read_json(opposite_index)
        if not isinstance(other, dict) or not isinstance(other.get("ids"), dict):
            raise CustodyError("CROSS_LANE_ID_INDEX_INVALID")
        if seen.keys() & other["ids"].keys():
            # Time lanes are disjoint: a repeated source ID cannot be the same
            # canonical event and must be resolved privately, never fuzzy-merged.
            raise CustodyError("CROSS_LANE_ID_CONFLICT")
    atomic_json(private / "raw_id_index.json", {"source_snapshot": COMMIT,
                "ids": {key: value[0].hex() for key, value in seen.items()}})
    events.sort(key=lambda r: (r["origin_time_us"], r["event_id"]))
    diagnostic.sort(key=lambda r: (r["source_date"], r["event_id"]))
    local_audit = {"raw_reason_counts": raw_counts, "duplicate_crosswalk": duplicates,
                   "serialized_precision_counts": precision, "unique_raw_ids": len(seen),
                   "model_event_count": len(events), "diagnostic_event_count": len(diagnostic),
                   "raw_clock_status_counts": clock_counts,
                   "diagnostic_clock_unavailable_count": diagnostic_clock_unavailable}
    atomic_json(private / "private_parse_audit.json", local_audit)
    if lane == "protected":
        return events, diagnostic, None
    corrected, admit = [], []
    for period in range(6):
        for zone in range(3):
            bins = hist[period][zone]
            mode = max(i for i, n in enumerate(bins) if n == max(bins))
            value = Decimal("2.0") + Decimal(mode) / 10 + Decimal("0.05") + Decimal("0.5")
            corrected.append(str(value))
            admit.append(counts[period][zone] >= 100 and value <= 4 and not overflow)
    scored = [r for r in events if r["source_year"] >= 1986]
    zone_counts = [sum(zone_index(r["source_tokens"]["latitude"]) == zone for r in scored) for zone in range(3)]
    summary = {"eligible_training_total": len(scored), "eligible_training_count_by_three_zones": zone_counts,
               "diagnostic_18_stratum_count": [n for period in counts for n in period],
               "diagnostic_18_corrected_modal_value": corrected, "diagnostic_18_admit_boolean": admit,
               "diagnostic_overflow_total": overflow, "documented_missing_magnitude_total": missing,
               "training_admit_boolean": all(admit) and len(scored) >= 180 and min(zone_counts) >= 30}
    atomic_json(private / "training_admission.json", summary)
    return events, diagnostic, summary
