"""Conservative metadata for common ArduPilot parameters.

Unknown or firmware-specific parameters intentionally have no invented range.
"""
from __future__ import annotations

import re


EXACT={
    'BATT_CAPACITY':(0,200000,'mAh','Batarya kapasitesi'),
    'BATT_LOW_VOLT':(0,100,'V','Düşük batarya voltaj eşiği'),
    'BATT_CRT_VOLT':(0,100,'V','Kritik batarya voltaj eşiği'),
    'FENCE_RADIUS':(0,100000,'m','Sanal çit yarıçapı'),
    'FENCE_ALT_MAX':(0,10000,'m','Sanal çit azami irtifası'),
}


def metadata_for(name,vehicle_type=None):
    name=str(name).upper()
    if name in EXACT:return EXACT[name]
    if re.fullmatch(r'SERVO(?:[1-9]|1[0-6])_(?:MIN|TRIM|MAX)',name):return 500,2500,'µs','Servo PWM sınırı'
    if re.fullmatch(r'RC(?:[1-9]|1[0-8])_(?:MIN|TRIM|MAX)',name):return 750,2250,'µs','RC kanal PWM sınırı'
    if name=='RTL_ALT' and vehicle_type not in (1,):return 0,100000,'cm','Copter RTL irtifası'
    return None


def validate_metadata(name,value,vehicle_type=None):
    meta=metadata_for(name,vehicle_type)
    if meta is None:return value
    low,high,unit,_=meta
    if not low<=float(value)<=high:raise ValueError(f'{name} bu araç profili için {low:g}–{high:g} {unit} aralığında olmalı.')
    return value
