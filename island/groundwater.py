"""Conceptual interval hydrostatic screening; not groundwater flow or design approval."""
from dataclasses import dataclass
from math import isfinite
from .geotechnics import Site, GeotechnicalInputError, number, total_vertical_stress_kpa

@dataclass(frozen=True)
class Interval:
    low: float
    high: float
    def __post_init__(self):
        number(self.low, 'interval low')
        number(self.high, 'interval high')
        if self.low > self.high: raise GeotechnicalInputError('inverted interval')

@dataclass(frozen=True)
class WaterObservation:
    time_days: float
    depth_m: Interval | None
    def __post_init__(self):
        number(self.time_days, 'time', 0)
        if self.depth_m is not None:
            if not isinstance(self.depth_m, Interval) or self.depth_m.low < 0:
                raise GeotechnicalInputError('water depth interval')

@dataclass(frozen=True)
class GroundwaterSeries:
    observations: tuple[WaterObservation, ...]
    def __post_init__(self):
        if not isinstance(self.observations, tuple) or not self.observations:
            raise GeotechnicalInputError('observations required')
        if any(not isinstance(x, WaterObservation) for x in self.observations):
            raise GeotechnicalInputError('invalid observation')
        if any(b.time_days <= a.time_days for a,b in zip(self.observations, self.observations[1:])):
            raise GeotechnicalInputError('times must increase strictly')
    def at(self, time_days: float) -> Interval | None:
        number(time_days, 'query time', 0)
        obs=self.observations
        if not obs[0].time_days <= time_days <= obs[-1].time_days:
            raise GeotechnicalInputError('extrapolation prohibited')
        for a,b in zip(obs,obs[1:]):
            if time_days == a.time_days: return a.depth_m
            if time_days == b.time_days: return b.depth_m
            if a.time_days < time_days < b.time_days:
                if a.depth_m is None or b.depth_m is None: return None
                fraction=(time_days-a.time_days)/(b.time_days-a.time_days)
                return Interval(a.depth_m.low+(b.depth_m.low-a.depth_m.low)*fraction,
                                a.depth_m.high+(b.depth_m.high-a.depth_m.high)*fraction)
        return obs[0].depth_m

@dataclass(frozen=True)
class Scenario:
    scenario_id: str
    time_days: float
    water: GroundwaterSeries
    unit_weights: tuple[Interval, ...]
    def __post_init__(self):
        if not isinstance(self.scenario_id,str) or not self.scenario_id.strip():
            raise GeotechnicalInputError('scenario id')
        number(self.time_days,'scenario time',0)
        if not isinstance(self.water, GroundwaterSeries): raise GeotechnicalInputError('water series')
        if not isinstance(self.unit_weights,tuple) or not self.unit_weights:
            raise GeotechnicalInputError('weight intervals')
        if any(not isinstance(x,Interval) or x.low<=0 for x in self.unit_weights):
            raise GeotechnicalInputError('weight interval must be positive')

def interval_screen(site: Site, scenario: Scenario, depth_m: float) -> dict:
    """Conservative interval arithmetic for 1D vertical total/pore/effective stress."""
    if not isinstance(site,Site) or not isinstance(scenario,Scenario):
        raise GeotechnicalInputError('site/scenario type')
    number(depth_m,'depth',0)
    if depth_m > site.layers[-1].bottom_m: raise GeotechnicalInputError('outside explored depth')
    if len(scenario.unit_weights)!=len(site.layers):
        raise GeotechnicalInputError('layer weight count mismatch')
    water=scenario.water.at(scenario.time_days)
    lengths=[max(0,min(depth_m,l.bottom_m)-l.top_m) for l in site.layers]
    total=Interval(sum(length*w.low for length,w in zip(lengths,scenario.unit_weights)),
                   sum(length*w.high for length,w in zip(lengths,scenario.unit_weights)))
    pore=None if water is None else Interval(9.81*max(0,depth_m-water.high),
                                             9.81*max(0,depth_m-water.low))
    effective=None if pore is None else Interval(total.low-pore.high,total.high-pore.low)
    risks=set()
    if water is None: risks.add('GROUNDWATER_UNKNOWN')
    elif water.low<=depth_m: risks.add('GROUNDWATER_POSSIBLE_INTERSECTION')
    if water is not None and water.high<=depth_m: risks.add('GROUNDWATER_CERTAIN_INTERSECTION')
    if any(x.low!=x.high for x in scenario.unit_weights) or (water is not None and water.low!=water.high):
        risks.add('PARAMETER_UNCERTAINTY')
    if any(l.material in ('fill','unknown') for l in site.layers): risks.add('UNCERTAIN_STRATA')
    if site.provenance!='verified-field': risks.add('UNVERIFIED_SITE_DATA')
    return {'scenario_id':scenario.scenario_id,'time_days':scenario.time_days,
            'total_vertical_stress_kpa':_out(total),
            'hydrostatic_pore_pressure_kpa':None if pore is None else _out(pore),
            'effective_vertical_stress_kpa':None if effective is None else _out(effective),
            'risk_flags':sorted(risks),'engineering_approval':'BLOCKED/NO-GO',
            'method':'illustrative-1d-interval-hydrostatic-screen-v1'}

def _out(i): return {'low':round(i.low,6),'high':round(i.high,6)}

def propagate_risks(seed_flags:dict[str,set[str]], dependencies:dict[str,tuple[str,...]]) -> dict[str,list[str]]:
    """Monotone fixed-point propagation; dependency maps target -> upstream sources."""
    if not isinstance(seed_flags,dict) or not isinstance(dependencies,dict):
        raise GeotechnicalInputError('invalid risk graph')
    nodes=set(dependencies)|set(seed_flags)
    if not nodes or any(not isinstance(n,str) or not n.strip() for n in nodes):
        raise GeotechnicalInputError('invalid nodes')
    for n,upstream in dependencies.items():
        if not isinstance(upstream,tuple) or any(u not in nodes for u in upstream):
            raise GeotechnicalInputError('unresolved dependency')
    for n,flags in seed_flags.items():
        if not isinstance(flags,set) or any(not isinstance(f,str) or not f.strip() for f in flags):
            raise GeotechnicalInputError('invalid flags')
    result={n:set(seed_flags.get(n,set())) for n in nodes}
    while True:
        changed=False
        for n,upstream in dependencies.items():
            merged=result[n].union(*(result[u] for u in upstream))
            if merged!=result[n]: result[n]=merged; changed=True
        if not changed: break
    return {n:sorted(result[n]) for n in sorted(nodes)}
