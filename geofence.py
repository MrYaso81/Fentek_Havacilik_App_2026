"""Geofence geometry and ArduPilot fence mission helpers."""
from dataclasses import dataclass
import math

@dataclass(frozen=True)
class FencePoint:
    lat: float; lon: float

def validate_polygon(points):
    pts=[FencePoint(float(p[0]),float(p[1])) for p in points]
    if len(pts)<3: raise ValueError('Sanal çit için en az 3 nokta gerekir.')
    if any(not(-90<=p.lat<=90 and -180<=p.lon<=180) for p in pts): raise ValueError('Sanal çit koordinatı geçersiz.')
    area=sum(a.lon*b.lat-b.lon*a.lat for a,b in zip(pts,pts[1:]+pts[:1]))
    if abs(area)<1e-10: raise ValueError('Sanal çit alanı sıfır olamaz.')
    return pts

def fence_items(points,return_point=None):
    pts=validate_polygon(points); items=[{'command':'FENCE_POLYGON_VERTEX_INCLUSION','seq':i,'count':len(pts),'lat':p.lat,'lon':p.lon} for i,p in enumerate(pts)]
    if return_point is not None:
        rp=FencePoint(float(return_point[0]),float(return_point[1])); items.append({'command':'FENCE_RETURN_POINT','seq':len(items),'lat':rp.lat,'lon':rp.lon})
    return items
