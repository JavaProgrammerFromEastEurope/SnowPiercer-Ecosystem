"""AI-CORE-001: deterministic, read-only cognitive recommendation boundary."""
from dataclasses import dataclass
from enum import Enum
from typing import Any, Mapping
import hashlib
import json

class Decision(str, Enum):
    OBSERVE = 'OBSERVE'
    INVESTIGATE = 'INVESTIGATE'
    ESCALATE = 'ESCALATE'

ALLOWED_SOURCES = frozenset({'trainos', 'rail', 'energy', 'life_support', 'logistics', 'security', 'island', 'operations'})
ALLOWED_SEVERITIES = frozenset({'info', 'warning', 'critical'})

@dataclass(frozen=True)
class Observation:
    event_id: str
    source: str
    severity: str
    description: str

    @classmethod
    def parse(cls, payload: Mapping[str, Any]) -> 'Observation':
        if not isinstance(payload, Mapping) or set(payload) != {'event_id', 'source', 'severity', 'description'}:
            raise ValueError('invalid observation schema')
        if any(not isinstance(payload[k], str) for k in payload):
            raise ValueError('all fields must be strings')
        if not (1 <= len(payload['event_id']) <= 128 and payload['event_id'].isascii() and
                all(c.isalnum() or c in '-_.' for c in payload['event_id'])):
            raise ValueError('invalid event_id')
        if payload['source'] not in ALLOWED_SOURCES or payload['severity'] not in ALLOWED_SEVERITIES:
            raise ValueError('invalid source or severity')
        if not 1 <= len(payload['description']) <= 2048 or any(ord(c) < 32 for c in payload['description']):
            raise ValueError('invalid description')
        return cls(**dict(payload))

@dataclass(frozen=True)
class Recommendation:
    event_id: str
    decision: Decision
    reason_code: str
    evidence_sha256: str
    actionable: bool = False

    def as_dict(self) -> dict:
        return {'event_id': self.event_id, 'decision': self.decision.value,
                'reason_code': self.reason_code, 'evidence_sha256': self.evidence_sha256,
                'actionable': self.actionable}

def assess(payload: Mapping[str, Any]) -> Recommendation:
    """Pure assessment: never executes a command, mutates state, or calls external systems."""
    observation = Observation.parse(payload)
    canonical = json.dumps(observation.__dict__, sort_keys=True, ensure_ascii=False,
                           separators=(',', ':')).encode('utf-8')
    decision, code = {
        'info': (Decision.OBSERVE, 'SEVERITY_INFO'),
        'warning': (Decision.INVESTIGATE, 'SEVERITY_WARNING'),
        'critical': (Decision.ESCALATE, 'SEVERITY_CRITICAL'),
    }[observation.severity]
    return Recommendation(observation.event_id, decision, code, hashlib.sha256(canonical).hexdigest())
