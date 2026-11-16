"""Illustrative 1-D Darcy screening; NOT a seepage solver or design calculation."""
from dataclasses import dataclass
from .geotechnics import GeotechnicalInputError, number
from .groundwater import Interval

@dataclass(frozen=True)
class HydraulicBoundary:
    boundary_id: str
    head_m: Interval | None
    def __post_init__(self):
        if not isinstance(self.boundary_id,str) or not self.boundary_id.strip():
            raise GeotechnicalInputError('boundary id required')
        if self.head_m is not None and not isinstance(self.head_m,Interval):
            raise GeotechnicalInputError('invalid head interval')

@dataclass(frozen=True)
class SeepagePath:
    path_id: str
    upstream: HydraulicBoundary
    downstream: HydraulicBoundary
    length_m: float
    conductivity_m_s: Interval | None
    area_m2: float
    def __post_init__(self):
        if not isinstance(self.path_id,str) or not self.path_id.strip():
            raise GeotechnicalInputError('path id required')
        if not isinstance(self.upstream,HydraulicBoundary) or not isinstance(self.downstream,HydraulicBoundary):
            raise GeotechnicalInputError('invalid boundary')
        number(self.length_m,'length',0)
        number(self.area_m2,'area',0)
        if self.length_m<=0 or self.area_m2<=0: raise GeotechnicalInputError('positive geometry required')
        if self.conductivity_m_s is not None and (not isinstance(self.conductivity_m_s,Interval) or self.conductivity_m_s.low<0):
            raise GeotechnicalInputError('invalid conductivity')

def seepage_screen(path:SeepagePath, critical_gradient:Interval|None=None)->dict:
    if not isinstance(path,SeepagePath): raise GeotechnicalInputError('path type')
    if critical_gradient is not None and (not isinstance(critical_gradient,Interval) or critical_gradient.low<=0):
        raise GeotechnicalInputError('critical gradient must be positive')
    flags={'UNVERIFIED_HYDRAULIC_MODEL'}
    a,b,k=path.upstream.head_m,path.downstream.head_m,path.conductivity_m_s
    if a is None or b is None or k is None:
        flags.add('HYDRAULIC_INPUT_UNKNOWN')
        return _result(path,None,None,None,flags)
    gradient=Interval((a.low-b.high)/path.length_m,(a.high-b.low)/path.length_m)
    products=(k.low*gradient.low,k.low*gradient.high,k.high*gradient.low,k.high*gradient.high)
    flux=Interval(min(products),max(products))
    discharge=Interval(flux.low*path.area_m2,flux.high*path.area_m2)
    if gradient.low<=0<=gradient.high: flags.add('FLOW_DIRECTION_UNCERTAIN')
    if gradient.low!=gradient.high or k.low!=k.high: flags.add('PARAMETER_UNCERTAINTY')
    if critical_gradient is None: flags.add('CRITICAL_GRADIENT_UNKNOWN')
    elif max(abs(gradient.low),abs(gradient.high))>=critical_gradient.low:
        flags.add('POTENTIAL_CRITICAL_GRADIENT')
    return _result(path,gradient,flux,discharge,flags)

def _interval(i):
    return None if i is None else {'low':round(i.low,9),'high':round(i.high,9)}

def _result(path,g,q,d,flags):
    return {'path_id':path.path_id,'gradient':_interval(g),'specific_discharge_m_s':_interval(q),
            'discharge_m3_s':_interval(d),'risk_flags':sorted(flags),
            'method':'illustrative-1d-darcy-interval-screen-v1',
            'engineering_approval':'BLOCKED/NO-GO'}

def isolated_risk_propagation(seed_flags:dict[str,set[str]],dependencies:dict[str,tuple[str,...]],
                              allowed_edges:set[tuple[str,str]])->dict[str,list[str]]:
    """Explicit directed edge admission: (source,target). Denied edges cannot propagate."""
    from .groundwater import propagate_risks
    if not isinstance(allowed_edges,set) or any(not isinstance(x,tuple) or len(x)!=2 for x in allowed_edges):
        raise GeotechnicalInputError('invalid allowlist')
    nodes=set(seed_flags)|set(dependencies)
    if any(not isinstance(n,str) or not n.strip() for n in nodes):
        raise GeotechnicalInputError('invalid node')
    for target,sources in dependencies.items():
        if not isinstance(sources,tuple) or any(s not in nodes for s in sources):
            raise GeotechnicalInputError('unresolved dependency')
    declared={(source,target) for target,sources in dependencies.items() for source in sources}
    if not allowed_edges<=declared: raise GeotechnicalInputError('undeclared allowlist edge')
    filtered={target:tuple(s for s in sources if (s,target) in allowed_edges) for target,sources in dependencies.items()}
    return propagate_risks(seed_flags,filtered)
