"""Requirements registry validation and evidence-free traceability reporting."""
import json
import re
from pathlib import Path
from .architecture import validate_registry

class RequirementsError(ValueError):
    pass

ID_PATTERN = re.compile(r"RAIL-REQ-\d{4}\Z")
CATEGORIES = frozenset({'architecture','functional','integration','safety','quality'})
PRIORITIES = frozenset({'critical','high','medium','low'})
METHODS = frozenset({'inspection','automated_test','unit_test','contract_test','simulation_test','integration_test','safety_review'})
STATUSES = frozenset({'proposed','approved','implemented','verified'})

def load_requirements(path, architecture):
    with Path(path).open(encoding='utf-8') as stream:
        data = json.load(stream)
    validate_requirements(data, architecture)
    return data

def validate_requirements(data, architecture):
    validate_registry(architecture)
    if not isinstance(data, dict) or data.get('schema_version') != '1.0' or data.get('stage') != 'RAIL-REQ-001':
        raise RequirementsError('Unsupported requirements schema')
    entries = data.get('requirements')
    if not isinstance(entries, list) or not entries:
        raise RequirementsError('Nonempty requirements required')
    components = {c['id'] for c in architecture['components']}
    seen = set()
    for entry in entries:
        if not isinstance(entry, dict):
            raise RequirementsError('Requirement must be an object')
        identifier = entry.get('id')
        if not isinstance(identifier, str) or not ID_PATTERN.fullmatch(identifier) or identifier in seen:
            raise RequirementsError('Invalid or duplicate requirement ID')
        seen.add(identifier)
        if not isinstance(entry.get('statement'), str) or not entry['statement'].strip():
            raise RequirementsError('Requirement statement required')
        if entry.get('component') not in components:
            raise RequirementsError('Unknown component')
        if entry.get('category') not in CATEGORIES or entry.get('priority') not in PRIORITIES:
            raise RequirementsError('Invalid classification')
        if entry.get('verification_method') not in METHODS:
            raise RequirementsError('Invalid verification method')
        if not isinstance(entry.get('planned_stage'), str) or not re.fullmatch(r'RAIL-[A-Z]+-\d{3}',entry['planned_stage']):
            raise RequirementsError('Invalid stage reference')
        if entry.get('status') not in STATUSES:
            raise RequirementsError('Invalid status')
        evidence = entry.get('verification_evidence')
        if not isinstance(evidence, list) or any(not isinstance(e,str) or not e.strip() for e in evidence) or len(evidence) != len(set(evidence)):
            raise RequirementsError('Invalid evidence list')
        if entry['status'] == 'verified' and not evidence:
            raise RequirementsError('Verified requirement requires evidence references')
        if entry['status'] != 'verified' and evidence:
            raise RequirementsError('Evidence requires verified status')
    return True

def traceability_report(data, architecture):
    validate_requirements(data, architecture)
    entries = data['requirements']
    counts = {status: sum(e['status']==status for e in entries) for status in sorted(STATUSES)}
    component_coverage = {c['id']:sum(e['component']==c['id'] for e in entries) for c in architecture['components']}
    return {'total':len(entries),'status_counts':counts,'verified':counts['verified'],
            'verification_ratio':counts['verified']/len(entries),
            'component_coverage':component_coverage,
            'uncovered_components':[key for key,value in component_coverage.items() if not value]}
