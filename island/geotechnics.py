"""Conservative conceptual screening ONLY; not a geotechnical design method."""
from dataclasses import dataclass
from math import isfinite

class GeotechnicalInputError(ValueError): pass

def number(value, name, low=None, strict=False):
    if isinstance(value, bool) or not isinstance(value, (int,float)) or not isfinite(value):
        raise GeotechnicalInputError(f"{name}: finite numeric value required")
    if low is not None and (value <= low if strict else value < low):
        raise GeotechnicalInputError(f"{name}: outside permitted range")
    return float(value)

@dataclass(frozen=True)
class Layer:
    name: str
    top_m: float
    bottom_m: float
    unit_weight_kn_m3: float
    material: str
    def __post_init__(self):
        if not isinstance(self.name,str) or not self.name.strip(): raise GeotechnicalInputError('layer name')
        if self.material not in ('soil','rock','fill','unknown'): raise GeotechnicalInputError('material')
        number(self.top_m,'top',0)
        number(self.bottom_m,'bottom',self.top_m,True)
        number(self.unit_weight_kn_m3,'unit weight',0,True)

@dataclass(frozen=True)
class Site:
    layers: tuple[Layer,...]
    groundwater_depth_m: float | None
    surface_pressure_kpa: float
    footprint_m2: float
    provenance: str = 'synthetic'
    def __post_init__(self):
        if not isinstance(self.layers,tuple) or not self.layers: raise GeotechnicalInputError('layers required')
        if any(not isinstance(x,Layer) for x in self.layers): raise GeotechnicalInputError('invalid layer')
        if abs(self.layers[0].top_m)>1e-9: raise GeotechnicalInputError('must begin at surface')
        for prev,nxt in zip(self.layers,self.layers[1:]):
            if abs(prev.bottom_m-nxt.top_m)>1e-9: raise GeotechnicalInputError('gap or overlap')
        if self.groundwater_depth_m is not None: number(self.groundwater_depth_m,'groundwater',0)
        number(self.surface_pressure_kpa,'pressure',0)
        number(self.footprint_m2,'footprint',0,True)
        if self.provenance not in ('synthetic','unverified-field','verified-field'):
            raise GeotechnicalInputError('provenance')

def total_vertical_stress_kpa(site:Site,depth_m:float)->float:
    """Simplified total overburden; excludes pore pressure and surcharge."""
    number(depth_m,'depth',0)
    if depth_m>site.layers[-1].bottom_m: raise GeotechnicalInputError('outside explored depth')
    return sum(max(0,min(depth_m,x.bottom_m)-x.top_m)*x.unit_weight_kn_m3 for x in site.layers)

def hydrostatic_pore_pressure_kpa(site:Site,depth_m:float)->float | None:
    """Illustrative hydrostatic pressure with fixed water unit weight 9.81 kN/m³."""
    number(depth_m,'depth',0)
    if depth_m>site.layers[-1].bottom_m: raise GeotechnicalInputError('outside explored depth')
    if site.groundwater_depth_m is None: return None
    return 9.81*max(0,depth_m-site.groundwater_depth_m)

def screen(site:Site,depth_m:float)->dict:
    total=total_vertical_stress_kpa(site,depth_m)
    pore=hydrostatic_pore_pressure_kpa(site,depth_m)
    risks=[]
    if site.groundwater_depth_m is None: risks.append('GROUNDWATER_UNKNOWN')
    elif site.groundwater_depth_m<=depth_m: risks.append('GROUNDWATER_INTERSECTION')
    if any(x.material in ('fill','unknown') for x in site.layers): risks.append('UNCERTAIN_STRATA')
    if site.provenance!='verified-field': risks.append('UNVERIFIED_SITE_DATA')
    # No bearing-capacity, settlement or stability approval is computed.
    return {'total_vertical_stress_kpa':round(total,6),
            'hydrostatic_pore_pressure_kpa':None if pore is None else round(pore,6),
            'effective_vertical_stress_kpa':None if pore is None else round(total-pore,6),
            'applied_force_kn':round(site.surface_pressure_kpa*site.footprint_m2,6),
            'risk_flags':sorted(risks),'engineering_approval':'BLOCKED/NO-GO',
            'method':'illustrative-1d-hydrostatic-screen-v1'}
