"""TrainOS boundary contract v1: in-memory validation only, no transport or actuation."""
import json
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

SCHEMA_VERSION = '1.0'
ALLOWED_KINDS = frozenset({'telemetry.report', 'health.report', 'audit.event'})
ALLOWED_ROLES = {'telemetry.report': 'telemetry_publisher', 'health.report': 'health_publisher', 'audit.event': 'audit_publisher'}
ID_PATTERN = re.compile(r'^[A-Za-z0-9][A-Za-z0-9_.:-]{0,63}$')
MAX_AGE_SECONDS = 60
MAX_FUTURE_SECONDS = 5
MAX_BYTES = 16384

class ContractError(ValueError):
    """Message rejected at the boundary."""

@dataclass(frozen=True)
class AcceptedMessage:
    message_id: str
    kind: str
    source: str
    timestamp: str
    payload: dict

class TrainOSBoundary:
    """Fail-closed, non-actuating, single-process validation adapter.

    Identity/role mapping is supplied by a trusted caller, not message content.
    Replay protection is local memory only, not durable or distributed.
    """
    def __init__(self, trusted_roles, now=None):
        if not isinstance(trusted_roles, dict) or not all(
            isinstance(k, str) and isinstance(v, (set, frozenset)) and
            all(isinstance(role, str) for role in v) for k, v in trusted_roles.items()
        ):
            raise TypeError('trusted_roles must map identities to role sets')
        self._roles = {key: frozenset(value) for key, value in trusted_roles.items()}
        self._now = now or (lambda: datetime.now(timezone.utc))
        self._seen = set()
        self.audit = []

    def receive(self, raw, authenticated_source):
        message_id = None
        try:
            if not isinstance(raw, bytes) or len(raw) > MAX_BYTES:
                raise ContractError('Input must be bytes within size limit')
            try:
                data = json.loads(raw.decode('utf-8'))
            except (UnicodeError, ValueError) as exc:
                raise ContractError('Malformed UTF-8 JSON') from exc
            if not isinstance(data, dict) or set(data) != {'schema_version', 'message_id', 'kind', 'source', 'timestamp', 'payload'}:
                raise ContractError('Invalid envelope fields')
            message_id = data['message_id']
            if data['schema_version'] != SCHEMA_VERSION:
                raise ContractError('Unsupported schema version')
            if not all(isinstance(data[key], str) and ID_PATTERN.fullmatch(data[key]) for key in ('message_id', 'source')):
                raise ContractError('Invalid identifier')
            if data['source'] != authenticated_source or authenticated_source not in self._roles:
                raise ContractError('Untrusted or mismatched source')
            kind = data['kind']
            if kind not in ALLOWED_KINDS:
                raise ContractError('Unknown or executable message kind')
            if ALLOWED_ROLES[kind] not in self._roles[authenticated_source]:
                raise ContractError('Source lacks role')
            if not isinstance(data['timestamp'], str) or not data['timestamp'].endswith('Z'):
                raise ContractError('Timestamp must be UTC ISO-8601 Z')
            try:
                ts = datetime.fromisoformat(data['timestamp'].replace('Z', '+00:00'))
            except ValueError as exc:
                raise ContractError('Invalid timestamp') from exc
            now = self._now()
            if now.tzinfo is None:
                raise ContractError('Clock must be timezone-aware')
            age = (now - ts).total_seconds()
            if age > MAX_AGE_SECONDS or age < -MAX_FUTURE_SECONDS:
                raise ContractError('Expired or future timestamp')
            payload = data['payload']
            if not isinstance(payload, dict) or not payload or any(not isinstance(k, str) for k in payload):
                raise ContractError('Invalid payload')
            # Only explicitly defined, non-executable observation schemas.
            if kind == 'telemetry.report':
                valid = set(payload) == {'asset_id', 'metric', 'value', 'unit'} and isinstance(payload.get('value'), (int, float)) and not isinstance(payload.get('value'), bool)
                if valid:
                    import math
                    valid = math.isfinite(payload['value']) and all(isinstance(payload[k], str) and bool(payload[k]) and len(payload[k]) <= 64 for k in ('asset_id', 'metric', 'unit'))
            elif kind == 'health.report':
                valid = set(payload) == {'asset_id', 'state'} and isinstance(payload.get('asset_id'), str) and bool(payload['asset_id']) and payload.get('state') in ('ok', 'degraded', 'unknown')
            else:
                valid = set(payload) == {'event_id', 'description'} and all(isinstance(payload.get(k), str) and 0 < len(payload[k]) <= 256 for k in ('event_id', 'description'))
            if not valid:
                raise ContractError('Payload violates read-only schema')
            key = (authenticated_source, message_id)
            if key in self._seen:
                raise ContractError('Replay detected')
            self._seen.add(key)
            result = AcceptedMessage(message_id, kind, authenticated_source, data['timestamp'], dict(payload))
            self.audit.append({'outcome': 'accepted', 'source': authenticated_source, 'message_id': message_id})
            return result
        except ContractError as exc:
            self.audit.append({'outcome': 'rejected', 'source': authenticated_source if isinstance(authenticated_source, str) else None, 'message_id': message_id if isinstance(message_id, str) else None, 'reason': str(exc)})
            raise

def load_interface_spec(path):
    data = json.loads(Path(path).read_text(encoding='utf-8'))
    if not isinstance(data, dict) or data.get('stage') != 'RAIL-IF-001' or data.get('schema_version') != SCHEMA_VERSION or data.get('actuation_allowed') is not False or data.get('message_kinds') != sorted(ALLOWED_KINDS):
        raise ContractError('Invalid interface specification')
    return data
