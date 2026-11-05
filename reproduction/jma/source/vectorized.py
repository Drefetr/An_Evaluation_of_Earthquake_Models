"""Vector screening extracted from the historical independent raw parser.

No file/network access. The selected rows are independently decoded by the
original scalar parser in replay.py. See source_crosswalk.json for lineage.
"""
import math
import numpy as np

DAY = 8640000
PRIORITY = ("AGENCY_OUT_OF_SCOPE", "SUBSIDIARY_OUT_OF_SCOPE",
    "DETERMINATION_OUT_OF_SCOPE", "PRIMARY_TYPE_OUT_OF_SCOPE",
    "PRIMARY_BELOW_THRESHOLD_NEGATIVE_SIGN_FAMILY", "PRIMARY_BELOW_THRESHOLD",
    "TIME_OUT_OF_SUPPORT", "DEPTH_OUT_OF_RANGE", "LOCATION_OUTSIDE_DOMAIN")
EPOCH_ORDINAL = 732312

def numbers(matrix, lo, hi, *, decimals=0, blank_fraction=False):
    """Vectorized independent implementation of the frozen numeric grammar.

    Returns coefficient, valid mask, all-blank mask, coarse-precision mask and
    explicit-negative token mask. No string/token content is logged.
    """
    raw = matrix[:, lo:hi]
    n, width = raw.shape
    blank = (raw == 32).all(axis=1)
    nonspace = raw != 32
    first = np.argmax(nonspace, axis=1)
    last = width - 1 - np.argmax(nonspace[:, ::-1], axis=1)
    rows = np.arange(n)
    first_byte = raw[rows, first]
    signed = (first_byte == 43) | (first_byte == 45)
    negative = first_byte == 45
    digit = (raw >= 48) & (raw <= 57)
    columns = np.arange(width)[None, :]
    positions = (columns >= (first + signed)[:, None]) & (columns <= last[:, None])
    valid = (~blank) & (last >= first + signed) & ((~positions) | digit).all(axis=1)
    weights = (10 ** np.arange(width - 1, -1, -1)).astype(np.int64)
    value = np.where(digit, raw.astype(np.int64) - 48, 0) @ weights
    # Align right-trimmed integer tokens; decimals normally forbid right blanks.
    trailing = width - 1 - last
    value //= 10 ** trailing
    value *= np.where(negative, -1, 1)
    coarse = np.zeros(n, dtype=bool)
    if decimals:
        ordinary = valid & (raw[:, -1] != 32)
        if blank_fraction:
            # Exactly absent fractional bytes, with an independently valid integer prefix.
            prefix_value, prefix_ok, _, _, _ = numbers(matrix, lo, hi-decimals)
            coarse = (~blank) & (raw[:, -decimals:] == 32).all(axis=1) & prefix_ok
            value = np.where(coarse, prefix_value * 10**decimals, value)
        valid = ordinary | coarse
    return value, valid, blank, coarse, negative


def framing(data):
    """Independent complete-byte validation of all three explicit frame candidates."""
    passing = []
    for mode, stride, ending in (("packed96", 96, b""), ("LF96", 97, b"\n"),
                                  ("CRLF96", 98, b"\r\n")):
        tail = len(data) % stride
        final = tail == 0 and bool(ending)
        if not data or tail not in (0, 96):
            continue
        count = len(data)//stride + (tail == 96)
        if count == 0:
            continue
        payload = np.ndarray((count, 96), dtype=np.uint8, buffer=data, strides=(stride, 1))
        if ending:
            complete = len(data)//stride
            if complete:
                separators = np.ndarray((complete, len(ending)), dtype=np.uint8,
                    buffer=data, offset=96, strides=(stride, 1))
                if not np.all(separators == np.frombuffer(ending, dtype=np.uint8)):
                    continue
        if not np.all((payload[:, 1:5] >= 48) & (payload[:, 1:5] <= 57)):
            continue
        syntax_ok = True
        for lo in (5, 7, 9, 11):
            first, second = payload[:, lo], payload[:, lo+1]
            if not np.all((((first >= 48) & (first <= 57)) | (first == 32)) &
                          (second >= 48) & (second <= 57)):
                syntax_ok = False
                break
        if syntax_ok:
            passing.append((mode, stride, count, final, payload))
    if len(passing) != 1:
        raise ValueError("INDEPENDENT_FRAMING_NOT_UNIQUE")
    return passing[0]


def ordinal(year, month, day):
    previous = year-1
    before = np.array([0,31,59,90,120,151,181,212,243,273,304,334], dtype=np.int64)
    leap = (year % 4 == 0) & ((year % 100 != 0) | (year % 400 == 0))
    safe_month = np.clip(month, 1, 12)
    return previous*365 + previous//4 - previous//100 + previous//400 + before[safe_month-1] + (leap & (month>2)) + day


def decode(payload, source_year):
    n = len(payload)
    values, valid, blanks, coarse, negative = {}, {}, {}, {}, {}
    fields = {"year":(1,5), "month":(5,7), "day":(7,9), "hour":(9,11),
        "minute":(11,13), "second":(13,17), "latitude_degrees":(21,24),
        "latitude_minutes":(24,28), "longitude_degrees":(32,36),
        "longitude_minutes":(36,40), "depth":(44,49)}
    for name,(lo,hi) in fields.items():
        decimal = name in {"second","latitude_minutes","longitude_minutes","depth"}
        values[name], valid[name], blanks[name], coarse[name], negative[name] = numbers(
            payload,lo,hi,decimals=2 if decimal else 0,blank_fraction=decimal)
    y,m,d = (values[k] for k in ("year","month","day"))
    leap = (y%4 == 0) & ((y%100 != 0) | (y%400 == 0))
    months = np.array([31,28,31,30,31,30,31,31,30,31,30,31])
    days_in_month = months[np.clip(m,1,12)-1] + (leap & (m==2))
    civil_ok = (y>=1)&(y<=9999)&(m>=1)&(m<=12)&(d>=1)&(d<=days_in_month)
    civil_ok &= (values["hour"]>=0)&(values["hour"]<24)&(values["minute"]>=0)&(values["minute"]<60)
    civil_ok &= (values["second"]>=0)&(values["second"]<6000)
    for name in ("year","month","day","hour","minute","second"):
        civil_ok &= valid[name]
    key = ((ordinal(y,m,d)-EPOCH_ORDINAL)*86400 + values["hour"]*3600 + values["minute"]*60)*100 + values["second"]
    year_mismatch = civil_ok & (y != source_year)
    location_ok = np.ones(n,dtype=bool)
    coords = []
    for axis,limit in (("latitude",90),("longitude",180)):
        degree, minute = axis+"_degrees",axis+"_minutes"
        coord = values[degree].astype(float)+values[minute].astype(float)/6000
        okay = valid[degree]&valid[minute]&(~negative[degree])&(values[degree]>=0)&(values[minute]>=0)&(values[minute]<6000)&(coord<=limit)
        location_ok &= okay
        coords.append(coord)
    lat,lon = coords
    r, c, s = 6371.0088, math.cos(math.radians(37)), math.sin(math.radians(37))
    x = r*c*(np.deg2rad(lon)-math.radians(138))
    yy = r*(np.sin(np.deg2rad(lat))-s)/c
    domain = location_ok&(x>=-600)&(x<=600)&(yy>=-800)&(yy<=800)
    columns = np.minimum(np.searchsorted(np.array([-600.,-200.,200.,600.]),x,side="right")-1,2)
    zones = np.minimum(np.searchsorted(np.array([-800.,-800/3,800/3,800.]),yy,side="right")-1,2)
    cell = (zones*3+columns).astype(np.int8)
    method_ok = np.isin(payload[:,59],list(map(ord,"12345789M")))
    depth_ok = valid["depth"] & ((~coarse["depth"]) | (payload[:,59]==ord("2")))
    magraw = payload[:,52:54]
    negative_family = np.isin(magraw[:,0],list(b"ABC"))&(magraw[:,1]>=48)&(magraw[:,1]<=57)
    mag_ok = ((magraw[:,0]>=48)&(magraw[:,0]<=57)&(magraw[:,1]>=48)&(magraw[:,1]<=57))|((magraw[:,0]==45)&(magraw[:,1]>=48)&(magraw[:,1]<=57))
    mag = np.where(magraw[:,0]==45,-(magraw[:,1].astype(np.int64)-48),(magraw[:,0].astype(np.int64)-48)*10+magraw[:,1].astype(np.int64)-48)
    code_ok = (payload[:,0]==74)&(payload[:,60]==49)&np.isin(payload[:,95],list(b"KkA"))&np.isin(payload[:,54],list(b"JDVdv"))
    essential_ok = code_ok&method_ok&civil_ok&location_ok&depth_ok&mag_ok
    exclusions = np.zeros((n,len(PRIORITY)),dtype=bool)
    exclusions[:,0] = np.isin(payload[:,0],list(b"UI"))
    exclusions[:,1] = np.isin(payload[:,60],list(b"2345"))
    exclusions[:,2] = np.isin(payload[:,95],list(b"SsaNF"))
    exclusions[:,3] = np.isin(payload[:,54],list(b"WBS"))
    exclusions[:,4] = negative_family
    exclusions[:,6] = civil_ok&((key<0)|(key>=6940*DAY))
    exclusions[:,7] = depth_ok&((values["depth"]<0)|(values["depth"]>6000))
    exclusions[:,8] = location_ok&(~domain)
    result = {"values":values,"valid":valid,"blanks":blanks,"coarse":coarse,
        "key":key,"year":y,"month":m,"civil_ok":civil_ok,"year_mismatch":year_mismatch,
        "lat":lat,"lon":lon,"depth":values["depth"],"x":x,"y":yy,"cell":cell,
        "zone":zones,"mag":mag,"mag_ok":mag_ok,"essential_ok":essential_ok,
        "exclusions":exclusions,"location_ok":location_ok,"depth_ok":depth_ok}
    for threshold,label in ((45,"target"),(20,"aux")):
        exc = exclusions.copy()
        exc[:,5] = mag_ok&(mag<threshold)
        any_exc = exc.any(axis=1)
        # source-year mismatch is a separate raw-source fact; source-wide flags
        # are NOT fabricated True and are NOT used to erase row classification.
        status = np.where(any_exc,1,np.where(essential_ok,0,2)).astype(np.uint8)
        reason = np.where(any_exc,np.argmax(exc,axis=1)+1,0).astype(np.uint8)
        bits = (exc.astype(np.uint16) * (1 << np.arange(len(PRIORITY),dtype=np.uint16))).sum(axis=1).astype(np.uint16)
        result[label] = {"status":status,"reason":reason,"bits":bits}
    return result


def aggregate_classification(decoded,label):
    result=decoded[label]
    return {"eligible":int(np.count_nonzero(result["status"]==0)),
        "excluded":int(np.count_nonzero(result["status"]==1)),
        "unresolved_potentially_eligible":int(np.count_nonzero(result["status"]==2)),
        "primary_reasons":{reason:int(np.count_nonzero(result["reason"]==i+1)) for i,reason in enumerate(PRIORITY)},
        "all_known_exclusions":{reason:int(np.count_nonzero(result["bits"]&(1<<i))) for i,reason in enumerate(PRIORITY)}}


