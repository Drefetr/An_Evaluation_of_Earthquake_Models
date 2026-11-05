"""Verbatim selection functions from the historically pinned GeoNet preparer.
Only imports and constants needed by these functions are retained.
"""
import csv
from datetime import datetime, timezone
import hashlib
import io
import math

ORIGIN = datetime(1960, 1, 1, tzinfo=timezone.utc)
CUTOFF = datetime(2026, 10, 15, tzinfo=timezone.utc)
FIELDS = ["event_id", "time_utc", "t_days", "magnitude", "excess", "depth", "latitude", "longitude", "magnitude_type", "event_type"]

def sha256(data):
    return hashlib.sha256(data).hexdigest()


def parse_time(value):
    date = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if date.tzinfo is None:
        raise ValueError("UTC offset absent")
    return date.astimezone(timezone.utc)


def finite(value):
    try:
        x = float(value)
    except (ValueError, TypeError):
        return None
    return x if math.isfinite(x) else None


def select_rows(raw_rows, *, start=ORIGIN, end=CUTOFF):
    """Keep original non-sentinel negative depths; fail on conflicting IDs.

    Returns prepared rows, all-row ledger, and duplicate statistics. Reasons
    overlap in all_reasons; primary_reason makes the dropped-row sum exact.
    """
    selected, ledger, seen = [], [], {}
    duplicates = 0
    for index, raw in enumerate(raw_rows):
        event_id = raw.get("publicid", "").strip()
        reasons = []
        if not event_id:
            reasons.append("missing_event_id")
        if event_id and event_id in seen:
            values = {key: value for key, value in raw.items() if not key.startswith("_")}
            previous = {key: value for key, value in seen[event_id].items() if not key.startswith("_")}
            if values != previous:
                raise ValueError(f"Conflicting duplicate event ID {event_id}")
            reasons.append("exact_duplicate_event_id")
            duplicates += 1
        elif event_id:
            seen[event_id] = raw
        try:
            date = parse_time(raw.get("origintime", ""))
        except (ValueError, TypeError):
            date = None
            reasons.append("invalid_or_missing_origin_time")
        if date is not None and not start <= date < end:
            reasons.append("outside_time_interval")
        magnitude = finite(raw.get("magnitude"))
        depth = finite(raw.get("depth"))
        latitude = finite(raw.get("latitude"))
        longitude = finite(raw.get("longitude"))
        if magnitude is None:
            reasons.append("invalid_or_missing_magnitude")
        elif magnitude < 5:
            reasons.append("magnitude_below_5")
        if latitude is None or longitude is None:
            reasons.append("invalid_or_missing_coordinates")
        elif not (165 <= longitude <= 180 and -48.5 <= latitude <= -33.5):
            reasons.append("outside_bbox")
        event_type = raw.get("eventtype", "").strip()
        if event_type != "earthquake":
            reasons.append("event_type_not_earthquake" if event_type else "missing_event_type")
        if depth is None:
            reasons.append("invalid_or_missing_depth")
        elif depth == -9:
            reasons.append("unknown_depth_sentinel_minus_9")
        elif depth > 40:
            reasons.append("depth_over_40_km")
        record = dict(raw_index=index, event_id=event_id,
                      source_file=raw.get("_source_file", ""), source_row=raw.get("_source_row", ""),
                      included=not reasons, primary_reason=reasons[0] if reasons else "included",
                      all_reasons=reasons, raw_event_type=event_type,
                      raw_magnitude_type=raw.get("magnitudetype", ""))
        ledger.append(record)
        if not reasons:
            selected.append(dict(event_id=event_id,
                time_utc=date.isoformat().replace("+00:00", "Z"),
                t_days=(date-ORIGIN).total_seconds()/86400,
                magnitude=magnitude, excess=magnitude-5, depth=depth,
                latitude=latitude, longitude=longitude,
                magnitude_type=raw.get("magnitudetype", "").strip(), event_type=event_type))
    selected.sort(key=lambda row: (row["t_days"], row["event_id"]))
    # Do not jitter timestamps to make a singular kernel appear valid.
    return selected, ledger, dict(exact_duplicate_rows=duplicates, unique_event_ids=len(seen), conflicting_duplicate_rows=0)


def csv_bytes(rows, fields):
    out = io.StringIO(newline="")
    writer = csv.DictWriter(out, fieldnames=fields, lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
    return out.getvalue().encode("utf-8")
