"""Evidence provenance and conservative scenario admission (not an authentication system)."""
from dataclasses import dataclass
from hashlib import sha256
import json
from .geotechnics import GeotechnicalInputError
from .consistency import Scenario, assess_scenarios, escalate_asset_risks


def _id(x, name):
    if not isinstance(x, str) or not x.strip() or x != x.strip() or len(x)>128:
        raise GeotechnicalInputError('invalid '+name)
    return x


def _version(x):
    if type(x) is not int or x < 1:
        raise GeotechnicalInputError('positive integer version required')
    return x


def _digest(x):
    if not isinstance(x,str) or len(x)!=64 or any(c not in '0123456789abcdef' for c in x):
        raise GeotechnicalInputError('invalid sha256 digest')
    return x


def evidence_digest(payload: bytes)->str:
    if not isinstance(payload,bytes): raise GeotechnicalInputError('evidence payload must be bytes')
    return sha256(payload).hexdigest()

@dataclass(frozen=True)
class EvidenceRecord:
    evidence_id: str
    source_id: str
    source_version: int
    payload_sha256: str
    observation_id: str
    def __post_init__(self):
        for name in ('evidence_id','source_id','observation_id'): _id(getattr(self,name),name)
        _version(self.source_version)
        _digest(self.payload_sha256)

@dataclass(frozen=True)
class SourcePolicy:
    source_id: str
    admitted_version: int
    admitted_digests: frozenset[str]
    def __post_init__(self):
        _id(self.source_id,'source_id'); _version(self.admitted_version)
        if not isinstance(self.admitted_digests,frozenset) or not self.admitted_digests:
            raise GeotechnicalInputError('explicit admitted digests required')
        for x in self.admitted_digests: _digest(x)

@dataclass(frozen=True)
class ScenarioEvidence:
    scenario: Scenario
    records: tuple[EvidenceRecord,...]
    def __post_init__(self):
        if not isinstance(self.scenario,Scenario) or not isinstance(self.records,tuple) or any(not isinstance(r,EvidenceRecord) for r in self.records):
            raise GeotechnicalInputError('invalid scenario evidence')


def admit_scenarios(items: tuple[ScenarioEvidence,...], policies: tuple[SourcePolicy,...],
                    payloads: dict[str,bytes], critical_gradient=None)->dict:
    if not isinstance(items,tuple) or not items or any(not isinstance(i,ScenarioEvidence) for i in items):
        raise GeotechnicalInputError('nonempty scenario evidence tuple required')
    if not isinstance(policies,tuple) or any(not isinstance(p,SourcePolicy) for p in policies):
        raise GeotechnicalInputError('invalid policies')
    if not isinstance(payloads,dict) or any(not isinstance(k,str) or not isinstance(v,bytes) for k,v in payloads.items()):
        raise GeotechnicalInputError('invalid payload mapping')
    ids=[i.scenario.scenario_id for i in items]
    if len(ids)!=len(set(ids)):raise GeotechnicalInputError('duplicate scenario id')
    policy_ids=[p.source_id for p in policies]
    if len(policy_ids)!=len(set(policy_ids)):raise GeotechnicalInputError('duplicate source policy')
    policy={p.source_id:p for p in policies}
    evidence_ids=[]; reasons=set(); trace=[]
    for item in items:
        # Require one distinct record for each observed knot, both boundaries, and conductivity.
        path=item.scenario.path
        expected={f'{series.boundary_id}@{sample.time_days}' for series in (path.upstream,path.downstream) for sample in series.samples}
        expected.add(f'{path.path_id}@conductivity')
        observed=set()
        for r in item.records:
            evidence_ids.append(r.evidence_id)
            observed.add(r.observation_id)
            p=policy.get(r.source_id)
            payload=payloads.get(r.evidence_id)
            reason=None
            if p is None:reason='SOURCE_NOT_ADMITTED'
            elif p.admitted_version!=r.source_version:reason='SOURCE_VERSION_MISMATCH'
            elif r.payload_sha256 not in p.admitted_digests:reason='DIGEST_NOT_ADMITTED'
            elif payload is None:reason='EVIDENCE_MISSING'
            elif evidence_digest(payload)!=r.payload_sha256:reason='EVIDENCE_DIGEST_MISMATCH'
            if reason: reasons.add(reason)
            trace.append({'scenario_id':item.scenario.scenario_id,'evidence_id':r.evidence_id,
                          'source_id':r.source_id,'source_version':r.source_version,
                          'observation_id':r.observation_id,'payload_sha256':r.payload_sha256,
                          'admitted':reason is None,'reason':reason})
        if observed!=expected:reasons.add('OBSERVATION_COVERAGE_MISMATCH')
        if len(observed)!=len(item.records):reasons.add('DUPLICATE_OBSERVATION')
        if path.conductivity_m_s is None:reasons.add('UNKNOWN_CONDUCTIVITY')
        for series in (path.upstream,path.downstream):
            if any(sample.head_m is None for sample in series.samples):reasons.add('UNKNOWN_OBSERVATION')
    if len(evidence_ids)!=len(set(evidence_ids)):reasons.add('DUPLICATE_EVIDENCE_ID')
    # Evaluate model consistency even if provenance fails, but never expose numerical values when rejected.
    try:
        model=assess_scenarios(tuple(i.scenario for i in items),critical_gradient)
    except GeotechnicalInputError:
        reasons.add('SCENARIO_INCONSISTENT')
        model=None
    if model is not None and not model['complete']:reasons.add('SCENARIO_INCOMPLETE')
    admitted=not reasons
    flags=set(model['risk_flags'] if model is not None else ())
    if not admitted:flags.update(('PROVENANCE_ADMISSION_DENIED','CONSERVATIVE_ESCALATION_REQUIRED'))
    return {'admitted':admitted,'reasons':sorted(reasons),'risk_flags':sorted(flags),
            'trace':trace,'scenario_ids':ids,
            'gradient':model['gradient'] if admitted else None,
            'specific_discharge_m_s':model['specific_discharge_m_s'] if admitted else None,
            'discharge_m3_s':model['discharge_m3_s'] if admitted else None,
            'engineering_approval':'BLOCKED/NO-GO',
            'trust_boundary':'caller-supplied allowlist; no cryptographic source authentication'}


def propagate_admission_risks(admissions, dependencies, allowed_edges):
    if not isinstance(admissions,dict) or not admissions:raise GeotechnicalInputError('admissions required')
    assessments={}
    for asset,a in admissions.items():
        if not isinstance(a,dict) or type(a.get('admitted')) is not bool or a.get('engineering_approval')!='BLOCKED/NO-GO' or not isinstance(a.get('risk_flags'),list):
            raise GeotechnicalInputError('invalid admission')
        flags=list(a['risk_flags'])
        if not a['admitted']: flags+=['PROVENANCE_ADMISSION_DENIED','CONSERVATIVE_ESCALATION_REQUIRED']
        assessments[asset]={'complete':a['admitted'],'risk_flags':sorted(set(flags)), 'engineering_approval':'BLOCKED/NO-GO'}
    return escalate_asset_risks(assessments,dependencies,allowed_edges)
