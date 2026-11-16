"""Conservative piecewise-linear head scenario screening, not a transient flow solver."""
from dataclasses import dataclass
from math import isfinite
from .groundwater import Interval
from .geotechnics import GeotechnicalInputError, number
from .seepage import HydraulicBoundary, SeepagePath, seepage_screen, isolated_risk_propagation

@dataclass(frozen=True)
class HeadSample:
    time_days: float
    head_m: Interval | None
    def __post_init__(self):
        number(self.time_days, 'time', 0)
        if self.head_m is not None and not isinstance(self.head_m, Interval):
            raise GeotechnicalInputError('head interval required or None')

@dataclass(frozen=True)
class HeadSeries:
    boundary_id: str
    samples: tuple[HeadSample, ...]
    def __post_init__(self):
        if not isinstance(self.boundary_id,str) or not self.boundary_id.strip():
            raise GeotechnicalInputError('boundary id')
        if not isinstance(self.samples,tuple) or not self.samples or any(not isinstance(s,HeadSample) for s in self.samples):
            raise GeotechnicalInputError('samples required')
        if any(b.time_days<=a.time_days for a,b in zip(self.samples,self.samples[1:])):
            raise GeotechnicalInputError('strictly increasing sample times required')
    def at(self,t:float)->Interval|None:
        number(t,'query time',0)
        if t<self.samples[0].time_days or t>self.samples[-1].time_days:
            raise GeotechnicalInputError('extrapolation prohibited')
        for s in self.samples:
            if t==s.time_days: return s.head_m
        for a,b in zip(self.samples,self.samples[1:]):
            if a.time_days<t<b.time_days:
                if a.head_m is None or b.head_m is None: return None
                f=(t-a.time_days)/(b.time_days-a.time_days)
                return Interval(a.head_m.low+(b.head_m.low-a.head_m.low)*f,
                                a.head_m.high+(b.head_m.high-a.head_m.high)*f)
        raise GeotechnicalInputError('unreachable time')

@dataclass(frozen=True)
class TransientPath:
    path_id: str
    upstream: HeadSeries
    downstream: HeadSeries
    length_m: float
    conductivity_m_s: Interval | None
    area_m2: float
    def __post_init__(self):
        if not isinstance(self.path_id,str) or not self.path_id.strip() or not isinstance(self.upstream,HeadSeries) or not isinstance(self.downstream,HeadSeries):
            raise GeotechnicalInputError('invalid transient path')
        # Reuse strict static geometry and conductivity validation.
        SeepagePath(self.path_id,HydraulicBoundary(self.upstream.boundary_id,None),
                    HydraulicBoundary(self.downstream.boundary_id,None),self.length_m,self.conductivity_m_s,self.area_m2)
        if self.upstream.boundary_id==self.downstream.boundary_id:
            raise GeotechnicalInputError('distinct boundaries required')

def _bounds(results,key):
    values=[r[key] for r in results]
    if any(v is None for v in values): return None
    return {'low':min(v['low'] for v in values),'high':max(v['high'] for v in values)}

def transient_envelope(path:TransientPath,start_days:float,end_days:float,
                       critical_gradient:Interval|None=None)->dict:
    if not isinstance(path,TransientPath): raise GeotechnicalInputError('transient path type')
    number(start_days,'start',0);number(end_days,'end',0)
    if end_days<start_days: raise GeotechnicalInputError('inverted time window')
    for series in (path.upstream,path.downstream):
        if start_days<series.samples[0].time_days or end_days>series.samples[-1].time_days:
            raise GeotechnicalInputError('window outside observation coverage')
    if critical_gradient is not None and (not isinstance(critical_gradient,Interval) or critical_gradient.low<=0):
        raise GeotechnicalInputError('invalid critical gradient')
    times=sorted({start_days,end_days}|
                 {s.time_days for series in (path.upstream,path.downstream) for s in series.samples if start_days<s.time_days<end_days})
    results=[]
    for t in times:
        static=SeepagePath(path.path_id,HydraulicBoundary(path.upstream.boundary_id,path.upstream.at(t)),
                          HydraulicBoundary(path.downstream.boundary_id,path.downstream.at(t)),
                          path.length_m,path.conductivity_m_s,path.area_m2)
        results.append(seepage_screen(static,critical_gradient))
    flags=set().union(*(set(r['risk_flags']) for r in results))
    if any(r['gradient'] is None for r in results):
        flags.add('TEMPORAL_INPUT_GAP')
    # A missing interior knot can conceal arbitrarily high gradients between observations.
    # Consequently unknown data invalidates the entire numeric envelope.
    complete=all(r['gradient'] is not None for r in results)
    if not complete:
        flags.add('TEMPORAL_ENVELOPE_UNKNOWN')
    return {'path_id':path.path_id,'start_days':start_days,'end_days':end_days,
            'evaluated_times_days':times,
            'gradient':_bounds(results,'gradient') if complete else None,
            'specific_discharge_m_s':_bounds(results,'specific_discharge_m_s') if complete else None,
            'discharge_m3_s':_bounds(results,'discharge_m3_s') if complete else None,
            'risk_flags':sorted(flags),
            'method':'piecewise-linear-head-static-darcy-envelope-v1',
            'engineering_approval':'BLOCKED/NO-GO'}

def transient_asset_risks(envelopes:dict[str,dict],dependencies:dict[str,tuple[str,...]],
                          allowed_edges:set[tuple[str,str]])->dict[str,list[str]]:
    if not isinstance(envelopes,dict) or not envelopes or any(not isinstance(k,str) or not k.strip() or not isinstance(v,dict) or not isinstance(v.get('risk_flags'),list) or v.get('engineering_approval')!='BLOCKED/NO-GO' or any(not isinstance(f,str) or not f.strip() for f in v['risk_flags']) for k,v in envelopes.items()):
        raise GeotechnicalInputError('invalid envelopes')
    return isolated_risk_propagation({k:set(v['risk_flags']) for k,v in envelopes.items()},dependencies,allowed_edges)
