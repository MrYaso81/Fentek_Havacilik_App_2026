"""Searchable, validated autopilot parameter model."""
from dataclasses import dataclass
import math

@dataclass
class Parameter:
    name: str
    value: float|None = None
    default: float|None = None
    description: str = ''

class ParameterTree:
    def __init__(self): self.items={}
    def upsert(self,name,value=None,default=None,description=''):
        name=str(name).strip().upper()
        if not name: raise ValueError('Parametre adı boş olamaz.')
        self.items[name]=Parameter(name,value,default,description); return self.items[name]
    def search(self,query=''):
        q=str(query).strip().upper()
        return [p for n,p in sorted(self.items.items()) if q in n or q in p.description.upper()]
    def set_value(self,name,value):
        value=float(value)
        if not math.isfinite(value): raise ValueError('Parametre değeri sonlu sayı olmalı.')
        if name not in self.items:self.upsert(name)
        self.items[name].value=value; return value
