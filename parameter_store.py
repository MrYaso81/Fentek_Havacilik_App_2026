"""Session-local parameter values and conservative ArduPilot write validation."""
import math
import struct

def checked_value(value,kind):
    value=float(value)
    if not math.isfinite(value):raise ValueError('Sonlu bir sayı girin.')
    limits={1:(0,255),2:(-128,127),3:(0,65535),4:(-32768,32767),5:(0,4294967295),6:(-2147483648,2147483647)}
    if kind in limits:
        lo,hi=limits[kind]
        if value!=int(value) or not lo<=value<=hi:raise ValueError('Parametre türünün tam sayı sınırı aşıldı.')
    elif kind!=9:raise ValueError('Bu parametre türüne yazma desteklenmiyor.')
    try:encoded=struct.unpack('<f',struct.pack('<f',value))[0]
    except (OverflowError,struct.error):raise ValueError('Değer çok büyük.')
    if not math.isfinite(encoded) or (kind in limits and encoded!=value):raise ValueError('Değer kayıpsız gönderilemiyor.')
    return encoded


def validate_safety_parameter(name,value):
    """Refuse writes that explicitly bypass ArduPilot's pre-arm protection."""
    name=str(name).upper()
    if name=='ARMING_CHECK' and float(value)==0:
        raise ValueError('ARMING_CHECK=0 tüm uçuş öncesi kontrolleri kapatır; Fentek Havacılık bu yazmayı engeller.')
    if name=='ARMING_SKIPCHK' and float(value)!=0:
        raise ValueError('ARMING_SKIPCHK uçuş öncesi kontrolleri atlatır; Fentek Havacılık bu yazmayı engeller.')
    return value
