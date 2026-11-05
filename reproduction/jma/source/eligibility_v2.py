"""Corrected posted-JMA predicate, exact history keys and explicit dispositions.

No file/network input, population scan, source admission, mark fit or criterion
evaluation. SourceEvidence is an external-evidence requirement, not proof that
its flags are true. Handcrafted True flags cannot authorize an acquired source.
"""
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import hashlib
import math
import numbers
import re

try:
    from . import parser, geometry_v1 as geometry
except ImportError:
    import parser
    import geometry_v1 as geometry

CENTISECONDS_PER_DAY = 8640000
HISTORY_EPOCH_UTC = datetime(2005,12,31,15,tzinfo=timezone.utc)
TRAIN_START_KEY = 1826*CENTISECONDS_PER_DAY
ORIGIN_KEYS = tuple(day*CENTISECONDS_PER_DAY for day in (3652,4748,5844))
END_KEYS = tuple(day*CENTISECONDS_PER_DAY for day in (4748,5844,6940))
SUPPORT_END_KEY = 6940*CENTISECONDS_PER_DAY
EXCLUSION_PRIORITY = ("AGENCY_OUT_OF_SCOPE","SUBSIDIARY_OUT_OF_SCOPE","DETERMINATION_OUT_OF_SCOPE",
    "PRIMARY_TYPE_OUT_OF_SCOPE","PRIMARY_BELOW_THRESHOLD_NEGATIVE_SIGN_FAMILY","PRIMARY_BELOW_THRESHOLD",
    "TIME_OUT_OF_SUPPORT","DEPTH_OUT_OF_RANGE","LOCATION_OUTSIDE_DOMAIN")
ESSENTIAL_FIELDS = frozenset({"agency","subsidiary","determination","location_method","magnitude1","magnitude_type1",
    "origin","year","month","day","hour","minute","second","latitude","latitude_degrees","latitude_minutes",
    "longitude","longitude_degrees","longitude_minutes","depth"})


def exact_key(value):
    if isinstance(value,bool) or not isinstance(value,numbers.Integral) or not -(1<<63)<=value<(1<<63):
        raise ValueError("INT64_TIME_KEY_REQUIRED")
    return int(value)


def unix_centiseconds(value):
    if not isinstance(value,datetime) or value.utcoffset()!=timedelta(0) or value.microsecond%10000:
        raise ValueError("EXACT_UTC_CENTISECOND_REQUIRED")
    delta=value.replace(tzinfo=None)-datetime(1970,1,1)
    return exact_key(delta.days*CENTISECONDS_PER_DAY+delta.seconds*100+delta.microseconds//10000)


HISTORY_UNIX_CENTISECONDS = unix_centiseconds(HISTORY_EPOCH_UTC)


def rebase_unix_key(value):
    return exact_key(exact_key(value)-HISTORY_UNIX_CENTISECONDS)


def kernel_days(keys):
    keys=tuple(exact_key(key) for key in keys)
    result=tuple(key/CENTISECONDS_PER_DAY for key in keys)
    for i in range(1,len(keys)):
        if keys[i]<keys[i-1] or (keys[i]==keys[i-1]) != (result[i]==result[i-1]) or result[i]<result[i-1]:
            raise ValueError("KEY_DAY_CHRONOLOGY_OR_COLLAPSE")
    return result


def prebatch_prefix_lengths(keys):
    keys=tuple(exact_key(key) for key in keys);kernel_days(keys)
    output=[];start=0
    for index,key in enumerate(keys):
        if index==0 or key!=keys[index-1]:
            start=index
        output.append(start)
    return tuple(output)


def in_window(key,start,end):
    key,start,end=exact_key(key),exact_key(start),exact_key(end)
    if start>=end:
        raise ValueError("HALF_OPEN_INTERVAL_REQUIRED")
    return start<=key<end


def phase(key,fold):
    key=exact_key(key)
    if type(fold) is not int or not 0<=fold<3:
        raise ValueError("FROZEN_FOLD_REQUIRED")
    if 0<=key<TRAIN_START_KEY:
        return "warmup_parent_only"
    if TRAIN_START_KEY<=key<ORIGIN_KEYS[fold]:
        return "scored_training"
    if ORIGIN_KEYS[fold]<=key<END_KEYS[fold]:
        return "test"
    return "outside_fold"


@dataclass(frozen=True)
class SourceEvidence:
    member_jst_year: int | None = None
    framing_verified: bool = False
    coverage_verified: bool = False
    duplicates_resolved: bool = False
    datum_verified: bool = False
    provider_semantics_verified: bool = False
    binding_sha256: str | None = None


@dataclass(frozen=True,repr=False)
class Disposition:
    status: str
    primary_reason: str
    known_exclusions: tuple
    unresolved_fields: tuple
    source_holds: tuple
    flags: tuple
    payload_sha256: str | None
    byte_offset: int | None
    history_key: int | None
    kernel_day: float | None
    reported_tenths: int | None
    K: int | None
    x_km: float | None
    y_km: float | None
    cell: int | None
    origin_reported_fractional_digits: int | None
    def __repr__(self):
        return "<private JMA occurrence disposition; fields omitted>"


def negative_primary_sign_family(raw):
    return type(raw) is bytes and re.fullmatch(rb"[ABC][0-9]",raw) is not None


def classify(record,source):
    if not isinstance(record,parser.Record) or not isinstance(source,SourceEvidence):
        raise TypeError("TYPED_RECORD_AND_SOURCE_EVIDENCE_REQUIRED")
    source_holds=[]
    for attribute,code in [("framing_verified","SOURCE_FRAMING_UNRESOLVED"),("coverage_verified","SOURCE_COVERAGE_UNRESOLVED"),
          ("duplicates_resolved","SOURCE_DUPLICATES_UNRESOLVED"),("datum_verified","SOURCE_DATUM_UNRESOLVED"),
          ("provider_semantics_verified","SOURCE_PROVIDER_SEMANTICS_UNRESOLVED")]:
        if getattr(source,attribute) is not True:
            source_holds.append(code)
    if not isinstance(source.binding_sha256,str) or re.fullmatch(r"[a-f0-9]{64}",source.binding_sha256) is None:
        source_holds.append("SOURCE_BINDING_UNRESOLVED")
    if type(source.member_jst_year) is not int or not 2006<=source.member_jst_year<=2024:
        source_holds.append("SOURCE_JST_YEAR_UNRESOLVED")
    frame=record.frame
    safe_frame=(isinstance(frame,parser.Frame) and type(frame.payload) is bytes and len(frame.payload)==96 and
                type(frame.ending) is bytes and frame.ending in {b"",b"\n",b"\r\n"} and
                type(frame.ordinal) is int and frame.ordinal>=0 and type(frame.byte_offset) is int and frame.byte_offset>=0)
    if not safe_frame:
        source_holds.append("SOURCE_RECORD_FRAMING_OR_LOCATOR_UNRESOLVED")
        return Disposition("source_held",source_holds[0],(),(),tuple(source_holds),(),None,None,
                           None,None,None,None,None,None,None,None)
    canonical=parser.parse_frame(frame)
    if canonical!=record:
        source_holds.append("SOURCE_RECORD_BINDING_MISMATCH")
    # Use the bytes-bound canonical record; never trust a substituted parsed
    # number, type, core_numbers_complete flag or secondary-field preference.
    record=canonical;raw=record.raw_fields;exclusions=set();unresolved=set()
    flags=tuple(f"{issue.field}:{issue.kind}:{issue.code}" for issue in record.issues)
    unresolved.update(issue.field for issue in record.issues if issue.field in ESSENTIAL_FIELDS and
                      issue.kind in {"missing","invalid","unresolved"})
    for name,allowed,documented,reason in [
        ("agency",{"J"},set("JUI"),"AGENCY_OUT_OF_SCOPE"),
        ("subsidiary",{"1"},set("12345"),"SUBSIDIARY_OUT_OF_SCOPE"),
        ("determination",set("KkA"),set("KSksAaNF"),"DETERMINATION_OUT_OF_SCOPE")]:
        value=record.codes.get(name)
        if value in documented and value not in allowed:
            exclusions.add(reason)
        elif value not in allowed:
            unresolved.add(name)
    primary_type=record.magnitude1.type_text
    if primary_type in set("WBS"):
        exclusions.add("PRIMARY_TYPE_OUT_OF_SCOPE")
    elif primary_type not in set("JDVdv"):
        unresolved.add("magnitude_type1")  # blank is REQUIRED ambiguity, not exclusion
    token=raw["magnitude1"];tenths=None
    if negative_primary_sign_family(token):
        exclusions.add("PRIMARY_BELOW_THRESHOLD_NEGATIVE_SIGN_FAMILY")
    elif re.fullmatch(rb"[0-9]{2}|-[0-9]",token):
        tenths=int(token)
        if tenths<45:
            exclusions.add("PRIMARY_BELOW_THRESHOLD")
    else:
        unresolved.add("magnitude1")
    key=day_value=None
    if record.origin_utc is None or record.utc_centiseconds is None:
        unresolved.add("origin")
    else:
        if (record.origin_utc+timedelta(hours=9)).year!=source.member_jst_year:
            source_holds.append("SOURCE_JST_YEAR_MISMATCH")
        key=rebase_unix_key(record.utc_centiseconds);day_value=kernel_days((key,))[0]
        if not 0<=key<SUPPORT_END_KEY:
            exclusions.add("TIME_OUT_OF_SUPPORT")
    depth=record.numbers["depth"].value
    # A numeric value can be provisional when the documented depth encoding
    # depends on the location-method code. Never turn that provisional value
    # into a known spatial exclusion. Independent trusted exclusions still win.
    depth_unresolved=any(issue.field=="depth" and issue.kind in {"missing","invalid","unresolved"}
                         for issue in record.issues)
    if depth is None or depth_unresolved:
        unresolved.add("depth")
    elif not 0<=depth<=60:
        exclusions.add("DEPTH_OUT_OF_RANGE")
    x=y=cell=None
    if record.latitude is None or record.longitude is None:
        unresolved.add("location")
    else:
        try:
            x,y=geometry.project(record.latitude,record.longitude);cell=geometry.cell_at(x,y)
            if cell is None:
                exclusions.add("LOCATION_OUTSIDE_DOMAIN")
        except (ValueError,OverflowError):
            unresolved.add("location")
    reasons=tuple(reason for reason in EXCLUSION_PRIORITY if reason in exclusions)
    if source_holds:
        status,reason="source_held",source_holds[0]
    elif reasons:
        status,reason="excluded",reasons[0]
    elif unresolved:
        status,reason="unresolved_potentially_eligible","REQUIRED_FIELD_UNRESOLVED"
    else:
        status,reason="eligible","POSTED_PREDICATE_PASSED"
    K=tenths-45 if status=="eligible" and tenths is not None else None
    return Disposition(status,reason,reasons,tuple(sorted(unresolved)),tuple(source_holds),flags,
                       frame.payload_sha256,frame.byte_offset,key,day_value,tenths,K,x,y,cell,
                       record.numbers["second"].fractional_digits)
