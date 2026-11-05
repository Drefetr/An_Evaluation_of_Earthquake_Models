"""Byte-preserving JMA format prototype; no files/network/eligibility/mark fit.

Spans are zero-based half-open, derived from the official hypfmt_e.html table.
Numeric forms are explicit conservative conventions for independent fixture
review. Unknown source semantics are issues, never inferred acceptance.
"""
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from fractions import Fraction
import hashlib
import re
from types import MappingProxyType

SPANS = MappingProxyType({
    "agency": (0, 1), "year": (1, 5), "month": (5, 7), "day": (7, 9),
    "hour": (9, 11), "minute": (11, 13), "second": (13, 17),
    "origin_error": (17, 21), "latitude_degrees": (21, 24),
    "latitude_minutes": (24, 28), "latitude_error": (28, 32),
    "longitude_degrees": (32, 36), "longitude_minutes": (36, 40),
    "longitude_error": (40, 44), "depth": (44, 49), "depth_error": (49, 52),
    "magnitude1": (52, 54), "magnitude_type1": (54, 55),
    "magnitude2": (55, 57), "magnitude_type2": (57, 58),
    "travel_table": (58, 59), "location_method": (59, 60), "subsidiary": (60, 61),
    "maximum_intensity": (61, 62), "damage": (62, 63), "tsunami": (63, 64),
    "district": (64, 65), "region": (65, 68), "region_name": (68, 92),
    "stations": (92, 95), "determination": (95, 96),
})
DOCUMENTED_CODES = MappingProxyType({
    "agency": frozenset("JUI"), "magnitude_type1": frozenset("JDdVvWBS "),
    "magnitude_type2": frozenset("JDdVvWBS "), "travel_table": frozenset("1234567 "),
    "location_method": frozenset("12345789M"), "subsidiary": frozenset("12345"),
    "determination": frozenset("KSksAaNF"),
})


@dataclass(frozen=True)
class Issue:
    field: str
    code: str
    kind: str  # missing, invalid, unresolved, reported_precision


@dataclass(frozen=True)
class Frame:
    ordinal: int
    byte_offset: int
    payload: bytes = field(repr=False)
    ending: bytes = field(repr=False)

    @property
    def payload_sha256(self):
        return hashlib.sha256(self.payload).hexdigest()


@dataclass(frozen=True)
class Number:
    raw: bytes = field(repr=False)
    coefficient: int | None
    denominator: int
    fractional_digits: int | None
    form: str

    @property
    def value(self):
        return None if self.coefficient is None else Fraction(self.coefficient, self.denominator)


@dataclass(frozen=True)
class Magnitude:
    number: Number
    type_raw: bytes = field(repr=False)
    type_text: str | None
    type_documented: bool


@dataclass(frozen=True, repr=False)
class Record:
    frame: Frame
    raw_fields: object = field(repr=False)
    numbers: object = field(repr=False)
    codes: object = field(repr=False)
    magnitude1: Magnitude | None
    magnitude2: Magnitude | None
    origin_utc: datetime | None
    utc_centiseconds: int | None
    latitude: Fraction | None
    longitude: Fraction | None
    issues: tuple[Issue, ...]
    core_numbers_complete: bool

    def __repr__(self):
        return "<private decoded JMA record; payload and values omitted>"


def frame_bytes(data, *, mode):
    """Lossless explicit framing, never guessed from source contents.

    A malformed segment/tail is retained as a frame, not silently dropped.
    These are byte occurrences, NOT independently identified earthquakes.
    """
    if type(data) is not bytes:
        raise TypeError("BYTES_REQUIRED")
    if mode not in {"packed96", "LF96", "CRLF96"}:
        raise ValueError("EXPLICIT_FRAMING_MODE_REQUIRED")
    if mode == "packed96":
        return tuple(Frame(i // 96, i, data[i:i+96], b"") for i in range(0, len(data), 96))
    if not data:
        return ()
    separator = b"\n" if mode == "LF96" else b"\r\n"
    parts, frames, offset = data.split(separator), [], 0
    for index, payload in enumerate(parts):
        ending = separator if index < len(parts)-1 else b""
        if not payload and not ending and index == len(parts)-1:
            break  # final separator is not a second blank occurrence
        frames.append(Frame(len(frames), offset, payload, ending))
        offset += len(payload) + len(ending)
    return tuple(frames)


def _number(raw, name, issues, *, decimals=0, blank_fraction=False):
    denominator = 10 ** decimals
    if raw == b" " * len(raw):
        issues.append(Issue(name, "BLANK_VALUE", "missing"))
        return Number(raw, None, denominator, None, "missing")
    if decimals and blank_fraction and raw[-decimals:] == b" " * decimals:
        token = raw[:-decimals].strip(b" ")
        if re.fullmatch(rb"[+-]?[0-9]+", token):
            issues.append(Issue(name, "FRACTION_BYTES_ABSENT", "reported_precision"))
            return Number(raw, int(token) * denominator, denominator, 0, "integer_fraction_blank")
    token = raw.strip(b" ")
    # Decimal points, internal blanks, tabs, non-ASCII bytes and a trailing
    # fractional blank outside its documented variant are not guessed away.
    if not re.fullmatch(rb"[+-]?[0-9]+", token) or (decimals and raw.endswith(b" ")):
        issues.append(Issue(name, "UNSUPPORTED_NUMERIC_ENCODING", "invalid"))
        return Number(raw, None, denominator, None, "unresolved_encoding")
    return Number(raw, int(token), denominator, decimals, "implicit_decimal" if decimals else "integer")


def _code(raw, name, issues):
    text = chr(raw[0]) if len(raw) == 1 and 32 <= raw[0] < 127 else None
    if text is None or text not in DOCUMENTED_CODES[name]:
        issues.append(Issue(name, "UNDOCUMENTED_CODE", "unresolved"))
    return text


def _magnitude(raw, type_raw, name, code_name, issues):
    # Ordinary signed numeric F2.1 tokens are distinct from letter negatives.
    # Only the four explicitly listed letter examples are decoded in this
    # conservative epoch. Unlisted A1/B9/etc remain raw and unresolved.
    letters = {b"A0": -10, b"A9": -19, b"B0": -20, b"C0": -30}
    if raw in letters:
        number = Number(raw, letters[raw], 10, 1, "documented_letter_negative")
    elif any(65 <= byte <= 90 or 97 <= byte <= 122 for byte in raw):
        issues.append(Issue(name, "UNLISTED_NEGATIVE_MAGNITUDE_TOKEN", "unresolved"))
        number = Number(raw, None, 10, None, "unresolved_letter_token")
    else:
        number = _number(raw, name, issues, decimals=1)
    text = _code(type_raw, code_name, issues)
    if text == " ":
        issues.append(Issue(code_name, "TYPE_UNDETERMINED", "missing"))
    return Magnitude(number, type_raw, text, text in DOCUMENTED_CODES[code_name])


def _coordinate(degrees, minutes, name, limit, issues):
    if degrees.value is None or minutes.value is None:
        return None
    if not 0 <= minutes.value < 60:
        issues.append(Issue(name, "MINUTES_OUT_OF_RANGE", "invalid")); return None
    # The consulted table does not specify the composition rule for signed
    # degree tokens. Retain signed components, do not invent a hemisphere rule.
    if degrees.coefficient < 0 or degrees.raw.strip(b" ").startswith(b"-"):
        issues.append(Issue(name, "SIGNED_DEGREE_COMPOSITION_UNRESOLVED", "unresolved")); return None
    result = degrees.value + minutes.value / 60
    if not 0 <= result <= limit:
        issues.append(Issue(name, "DEGREES_OUT_OF_RANGE", "invalid")); return None
    return result


def parse_frame(frame):
    if not isinstance(frame, Frame):
        raise TypeError("FRAME_REQUIRED")
    if len(frame.payload) != 96:
        return Record(frame, MappingProxyType({}), MappingProxyType({}), MappingProxyType({}),
                      None, None, None, None, None, None,
                      (Issue("frame", "PAYLOAD_NOT_96_BYTES", "invalid"),), False)
    raw = {name: frame.payload[lo:hi] for name, (lo, hi) in SPANS.items()}
    issues, numbers = [], {}
    integers = ["year", "month", "day", "hour", "minute", "latitude_degrees", "longitude_degrees",
                "district", "region", "stations"]
    for name in integers:
        numbers[name] = _number(raw[name], name, issues)
    for name in ["second", "latitude_minutes", "longitude_minutes", "depth"]:
        numbers[name] = _number(raw[name], name, issues, decimals=2, blank_fraction=True)
    for name in ["origin_error", "latitude_error", "longitude_error", "depth_error"]:
        numbers[name] = _number(raw[name], name, issues, decimals=2)
        if numbers[name].value is not None and numbers[name].value < 0:
            issues.append(Issue(name, "NEGATIVE_REPORTED_ERROR", "invalid"))
    codes = {name: _code(raw[name], name, issues) for name in DOCUMENTED_CODES
             if name not in {"magnitude_type1", "magnitude_type2"}}
    mag1 = _magnitude(raw["magnitude1"], raw["magnitude_type1"], "magnitude1", "magnitude_type1", issues)
    mag2 = _magnitude(raw["magnitude2"], raw["magnitude_type2"], "magnitude2", "magnitude_type2", issues)
    codes.update(magnitude_type1=mag1.type_text, magnitude_type2=mag2.type_text)
    if numbers["depth"].form == "integer_fraction_blank" and codes["location_method"] != "2":
        issues.append(Issue("depth", "INTEGER_DEPTH_METHOD_RELATION_UNRESOLVED", "unresolved"))
    latitude = _coordinate(numbers["latitude_degrees"], numbers["latitude_minutes"], "latitude", 90, issues)
    longitude = _coordinate(numbers["longitude_degrees"], numbers["longitude_minutes"], "longitude", 180, issues)
    origin, tick = None, None
    needed = ["year", "month", "day", "hour", "minute", "second"]
    if all(numbers[name].value is not None for name in needed):
        second = numbers["second"].coefficient
        if second is not None and 6000 <= second < 6100:
            issues.append(Issue("second", "LEAP_SECOND_UNSUPPORTED", "unresolved"))
        elif second is None or not 0 <= second < 6000:
            issues.append(Issue("second", "SECOND_OUT_OF_RANGE", "invalid"))
        else:
            try:
                origin = datetime(*(numbers[name].coefficient for name in needed[:5]),
                                  second=second // 100, microsecond=(second % 100) * 10000,
                                  tzinfo=timezone(timedelta(hours=9))).astimezone(timezone.utc)
                elapsed = origin.replace(tzinfo=None) - datetime(1970, 1, 1)
                tick = elapsed.days * 8640000 + elapsed.seconds * 100 + elapsed.microseconds // 10000
            except (ValueError, OverflowError):
                issues.append(Issue("origin", "INVALID_CIVIL_TIME", "invalid"))
    return Record(frame, MappingProxyType(raw), MappingProxyType(numbers), MappingProxyType(codes), mag1, mag2,
                  origin, tick, latitude, longitude, tuple(issues),
                  origin is not None and latitude is not None and longitude is not None and
                  numbers["depth"].value is not None)


def parse_bytes(data, *, mode):
    return tuple(parse_frame(frame) for frame in frame_bytes(data, mode=mode))
