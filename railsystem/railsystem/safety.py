"""Preliminary hazard analysis registry; documentation only, never operational authority."""
import json
import re
from pathlib import Path
from .architecture import validate_registry
from .requirements import validate_requirements

class SafetyError(ValueError):
    pass

LEVELS = frozenset({'catastrophic','critical','major','minor'})
LIKELIHOODS = frozenset({'frequent','probable','occasional','remote','improbable','unknown'})
STATUSES = frozenset({'open','under_review','mitigated','closed'})
ID = re.compile(r'RAIL-HAZ-\d{4}\Z')

def validate_hazards(data, architecture, requirements):
    validate_registry(architecture)
    validate_requirements(requirements, architecture)
    if not isinstance(data,dict) or data.get('schema_version')!='1.0' or data.get('stage')!='RAIL-SAFE-001':
        raise SafetyError('Unsupported safety schema')
    hazards=data.get('hazards')
    if not isinstance(hazards,list) or not hazards:
        raise SafetyError('Nonempty hazard log required')
    components={x['id'] for x in architecture['components']}
    reqs={x['id']:x for x in requirements['requirements']}
    seen=set()
    for h in hazards:
        if not isinstance(h,dict):
            raise SafetyError('Hazard must be an object')
        hid=h.get('id')
        if not isinstance(hid,str) or not ID.fullmatch(hid) or hid in seen:
            raise SafetyError('Invalid or duplicate hazard ID')
        seen.add(hid)
        for key in ('title','cause','consequence','detection','owner_role'):
            if not isinstance(h.get(key),str) or not h[key].strip():
                raise SafetyError('Missing hazard field: '+key)
        if h.get('component') not in components:
            raise SafetyError('Unknown component')
        if h.get('severity') not in LEVELS or h.get('likelihood') not in LIKELIHOODS:
            raise SafetyError('Invalid risk classification')
        if h.get('status') not in STATUSES:
            raise SafetyError('Invalid status')
        linked=h.get('requirement_ids')
        if not isinstance(linked,list) or not linked or len(linked)!=len(set(linked)) or any(r not in reqs for r in linked):
            raise SafetyError('Invalid requirement references')
        if not any(reqs[r]['category']=='safety' for r in linked):
            raise SafetyError('Safety requirement link required')
        controls=h.get('controls')
        if not isinstance(controls,list) or not controls or any(not isinstance(c,str) or not c.strip() for c in controls) or len(controls)!=len(set(controls)):
            raise SafetyError('Nonempty unique controls required')
        evidence=h.get('closure_evidence')
        if not isinstance(evidence,list) or any(not isinstance(e,str) or not e.strip() for e in evidence) or len(evidence)!=len(set(evidence)):
            raise SafetyError('Invalid evidence')
        if h['status'] in ('mitigated','closed'):
            raise SafetyError('Unassessed mitigation or closure not permitted in preliminary register')
        if evidence:
            raise SafetyError('Unreviewed evidence cannot be accepted')
        if h.get('operational_authorization') is not False:
            raise SafetyError('Operational authorization must be false')
    return True

def load_hazards(path, architecture, requirements):
    with Path(path).open(encoding='utf-8') as f:
        data=json.load(f)
    validate_hazards(data,architecture,requirements)
    return data

def safety_report(data, architecture, requirements):
    validate_hazards(data,architecture,requirements)
    hazards=data['hazards']
    return {'total':len(hazards), 'by_severity':{s:sum(h['severity']==s for h in hazards) for s in sorted(LEVELS)}, 'open':sum(h['status']=='open' for h in hazards), 'closed':0, 'operational_go':False, 'linked_requirements':sorted({r for h in hazards for r in h['requirement_ids']})}
