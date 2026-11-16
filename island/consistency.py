"""Conservative screening consistency checks; no hydraulic simulation or approval."""
from dataclasses import dataclass
from math import isfinite
from .transient import TransientPath, transient_envelope
from .geotechnics import GeotechnicalInputError, number
from .seepage import isolated_risk_propagation

@dataclass(frozen=True)
class Scenario:
    scenario_id: str
    path: TransientPath
    start_days: float
    end_days: float
    def __post_init__(self):
        if not isinstance(self.scenario_id,str) or not self.scenario_id.strip() or not isinstance(self.path,TransientPath):
            raise GeotechnicalInputError('invalid scenario')
        number(self.start_days,'start',0);number(self.end_days,'end',0)
        if self.end_days < self.start_days: raise GeotechnicalInputError('inverted window')

def _covered(series,a,b):
    if a < series.samples[0].time_days or b > series.samples[-1].time_days:
        raise GeotechnicalInputError('scenario outside observation coverage')
    # Unknown observations anywhere inside the window, including exact endpoints,
    # invalidate the complete window. Unknown knots adjacent to an interior query
    # also invalidate interpolation (handled by .at()).
    knots={a,b}|{s.time_days for s in series.samples if a<=s.time_days<=b}
    return all(series.at(t) is not None for t in sorted(knots))

def assess_scenarios(scenarios:tuple[Scenario,...],critical_gradient=None)->dict:
    if not isinstance(scenarios,tuple) or not scenarios or any(not isinstance(s,Scenario) for s in scenarios):
        raise GeotechnicalInputError('nonempty tuple of scenarios required')
    ids=[s.scenario_id for s in scenarios]
    if len(ids)!=len(set(ids)): raise GeotechnicalInputError('duplicate scenario id')
    path_ids={s.path.path_id for s in scenarios}
    if len(path_ids)!=1: raise GeotechnicalInputError('incompatible paths')
    windows={(s.start_days,s.end_days) for s in scenarios}
    if len(windows)!=1: raise GeotechnicalInputError('incompatible windows')
    envelopes=[];flags=set();complete=True
    for s in scenarios:
        known=all(_covered(series,s.start_days,s.end_days) for series in (s.path.upstream,s.path.downstream))
        result=transient_envelope(s.path,s.start_days,s.end_days,critical_gradient)
        flags.update(result['risk_flags'])
        if not known or any(result[k] is None for k in ('gradient','specific_discharge_m_s','discharge_m3_s')):
            complete=False
        envelopes.append(result)
    if not complete:
        flags.update(('SCENARIO_INPUT_INCOMPLETE','CONSERVATIVE_ESCALATION_REQUIRED'))
    bounds={}
    for key in ('gradient','specific_discharge_m_s','discharge_m3_s'):
        bounds[key]=({'low':min(e[key]['low'] for e in envelopes),'high':max(e[key]['high'] for e in envelopes)} if complete else None)
    if complete and len(scenarios)>1: flags.add('MULTI_SCENARIO_UNCERTAINTY')
    return {'path_id':next(iter(path_ids)),'scenario_ids':ids,'start_days':scenarios[0].start_days,
            'end_days':scenarios[0].end_days,**bounds,'risk_flags':sorted(flags),
            'complete':complete,'method':'conservative-scenario-union-v1',
            'engineering_approval':'BLOCKED/NO-GO'}

def escalate_asset_risks(assessments:dict[str,dict],dependencies:dict[str,tuple[str,...]],
                         allowed_edges:set[tuple[str,str]])->dict[str,list[str]]:
    if not isinstance(assessments,dict) or not assessments:
        raise GeotechnicalInputError('assessments required')
    seeds={}
    for asset,a in assessments.items():
        if not isinstance(asset,str) or not asset.strip() or not isinstance(a,dict) or a.get('engineering_approval')!='BLOCKED/NO-GO' or not isinstance(a.get('complete'),bool) or not isinstance(a.get('risk_flags'),list) or any(not isinstance(x,str) or not x.strip() for x in a['risk_flags']):
            raise GeotechnicalInputError('invalid assessment')
        flags=set(a['risk_flags'])
        if not a['complete']: flags.update(('SCENARIO_INPUT_INCOMPLETE','CONSERVATIVE_ESCALATION_REQUIRED'))
        seeds[asset]=flags
    return isolated_risk_propagation(seeds,dependencies,allowed_edges)
