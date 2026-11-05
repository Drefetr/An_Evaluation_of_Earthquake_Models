"""Pinned spherical CEA geometry; recorded-coordinate criterion, not accuracy."""
from bisect import bisect_right
from fractions import Fraction
import hashlib
import json
import math
import numbers

R_KM = 6371.0088
PHI0_DEGREES, LAMBDA0_DEGREES = 37, 138
PHI0, LAMBDA0 = math.radians(PHI0_DEGREES), math.radians(LAMBDA0_DEGREES)
COS0, SIN0 = math.cos(PHI0), math.sin(PHI0)
X_RATIONAL = (Fraction(-600),Fraction(-200),Fraction(200),Fraction(600))
Y_RATIONAL = (Fraction(-800),Fraction(-800,3),Fraction(800,3),Fraction(800))
X_EDGES, Y_EDGES = tuple(map(float,X_RATIONAL)), tuple(map(float,Y_RATIONAL))
RECTANGLES = tuple((X_EDGES[x],X_EDGES[x+1],Y_EDGES[y],Y_EDGES[y+1]) for y in range(3) for x in range(3))
AREAS = tuple((xh-xl)*(yh-yl) for xl,xh,yl,yh in RECTANGLES)
CENTRES = tuple(((xl+xh)/2,(yl+yh)/2) for xl,xh,yl,yh in RECTANGLES)


def finite(value):
    if isinstance(value,bool) or not isinstance(value,numbers.Real):
        raise ValueError("FINITE_REAL_REQUIRED")
    result=float(value)
    if not math.isfinite(result):
        raise ValueError("FINITE_REAL_REQUIRED")
    return result


def project(latitude_degrees,longitude_degrees):
    latitude,longitude=finite(latitude_degrees),finite(longitude_degrees)
    if not -90<=latitude<=90 or not -180<=longitude<=180:
        raise ValueError("ANGULAR_DOMAIN")
    phi,lam=math.radians(latitude),math.radians(longitude)
    return R_KM*COS0*(lam-LAMBDA0), R_KM*(math.sin(phi)-SIN0)/COS0


def inverse(x_km,y_km):
    x,y=finite(x_km),finite(y_km)
    sine=SIN0+y*COS0/R_KM
    if not -1<=sine<=1:
        raise ValueError("INVERSE_SINE_DOMAIN")
    latitude=math.degrees(math.asin(sine))
    longitude=math.degrees(LAMBDA0+x/(R_KM*COS0))
    if not -180<=longitude<=180:
        raise ValueError("INVERSE_LONGITUDE_DOMAIN")
    return latitude,longitude


def cell_at(x_km,y_km):
    x,y=finite(x_km),finite(y_km)
    if not X_EDGES[0]<=x<=X_EDGES[-1] or not Y_EDGES[0]<=y<=Y_EDGES[-1]:
        return None
    column=min(bisect_right(X_EDGES,x)-1,2)
    zone=min(bisect_right(Y_EDGES,y)-1,2)
    return 3*zone+column


def manifest():
    value={"schema":"jma_spherical_CEA_geometry_v1","R_km_hex":R_KM.hex(),
           "centre_degrees":[PHI0_DEGREES,LAMBDA0_DEGREES],
           "x_edges_rational":[[x.numerator,x.denominator] for x in X_RATIONAL],
           "y_edges_rational":[[y.numerator,y.denominator] for y in Y_RATIONAL],
           "x_edges_hex":[x.hex() for x in X_EDGES],"y_edges_hex":[y.hex() for y in Y_EDGES],
           "rectangles_hex":[[x.hex() for x in row] for row in RECTANGLES],
           "areas_hex":[x.hex() for x in AREAS],"centres_hex":[[x.hex() for x in row] for row in CENTRES],
           "internal_owner":"north_east","outer_edges":"closed","depth_km":[0,60],
           "measure":"spherical projected km2; no ellipsoidal/measurement-accuracy assertion"}
    raw=json.dumps(value,sort_keys=True,separators=(",",":"),allow_nan=False).encode()
    return {**value,"geometry_sha256":hashlib.sha256(raw).hexdigest()}
