"""RAIL-TRUST-001: offline Ed25519 attestation; external trust/state are mandatory."""
from __future__ import annotations
import base64
import json
import re
from pathlib import Path
from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
from .provenance import validate_baseline, ProvenanceError
from .verification import manifest

class TrustError(ValueError):
    pass

def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False, allow_nan=False).encode('utf-8')

def _decode(value, length):
    if not isinstance(value, str):
        raise TrustError('invalid encoding')
    try:
        data = base64.b64decode(value, validate=True)
    except (ValueError, Exception) as exc:
        raise TrustError('invalid base64') from exc
    if len(data) != length:
        raise TrustError('invalid byte length')
    return data

def verify_attestation(root: Path, baseline: dict, attestation: dict, trust: dict, state: dict) -> dict:
    """Pure verification. Caller must persist new state atomically in a trusted store."""
    if not all(isinstance(x, dict) for x in (baseline, attestation, trust, state)):
        raise TrustError('missing independent trust inputs')
    try:
        validate_baseline(baseline)
    except ProvenanceError as exc:
        raise TrustError(str(exc)) from exc
    if trust.get('schema_version') != 1 or state.get('schema_version') != 1:
        raise TrustError('invalid trust/state schema')
    keys = trust.get('keys')
    if not isinstance(keys, dict) or not keys:
        raise TrustError('empty trust store')
    payload = attestation.get('payload')
    if attestation.get('schema_version') != 1 or not isinstance(payload, dict):
        raise TrustError('invalid attestation')
    if set(payload) != {'domain', 'baseline_id', 'manifest_digest', 'key_id', 'sequence', 'nonce'}:
        raise TrustError('unexpected signed fields')
    if payload['domain'] != 'snowpiercer.railsystem.release.v1' or payload['baseline_id'] != baseline['baseline_id'] or payload['manifest_digest'] != baseline['manifest_digest']:
        raise TrustError('attestation bound to different baseline')
    key_id = payload['key_id']
    if not isinstance(key_id, str) or key_id not in keys:
        raise TrustError('untrusted signer')
    key = keys[key_id]
    if not isinstance(key, dict) or key.get('revoked') is not False:
        raise TrustError('revoked signer')
    sequence = payload['sequence']
    nonce = payload['nonce']
    if type(sequence) is not int or sequence < 1 or not isinstance(nonce, str) or not re.fullmatch('[A-Za-z0-9_-]{16,128}', nonce):
        raise TrustError('invalid freshness fields')
    floor = state.get('minimum_sequence')
    used = state.get('used_nonces')
    if type(floor) is not int or floor < 0 or not isinstance(used, list) or any(not isinstance(n, str) for n in used):
        raise TrustError('invalid replay state')
    if sequence <= floor or nonce in used:
        raise TrustError('replay or rollback')
    try:
        Ed25519PublicKey.from_public_bytes(_decode(key.get('public_key'), 32)).verify(_decode(attestation.get('signature'), 64), canonical(payload))
    except (InvalidSignature, ValueError) as exc:
        raise TrustError('signature invalid') from exc
    if manifest(root) != baseline['manifest']:
        raise TrustError('source manifest mismatch')
    return {'status': 'PASS', 'key_id': key_id, 'baseline_id': baseline['baseline_id'],
            'next_state': {'schema_version': 1, 'minimum_sequence': sequence, 'used_nonces': used + [nonce]}}

def evaluate_trusted(root: Path, *, baseline=None, attestation=None, trust=None, state=None, regression=None):
    """Strict release gate: no signature or trusted state -> never PASS."""
    from .release_gate import evaluate
    from .verification import coverage
    report = evaluate(root, expected_manifest=baseline.get('manifest') if isinstance(baseline, dict) else None, regression=regression)
    try:
        verified = verify_attestation(root, baseline, attestation, trust, state)
        report['gates']['trust'] = {'status': 'PASS', 'key_id': verified['key_id'], 'baseline_id': verified['baseline_id']}
        report['proposed_next_state'] = verified['next_state']
    except (TrustError, OSError, ValueError) as exc:
        status = 'BLOCKED' if any(x is None for x in (baseline, attestation, trust, state)) else 'FAIL'
        report['gates']['trust'] = {'status': status, 'reason': str(exc)}
    statuses = {g['status'] for g in report['gates'].values()}
    report['status'] = 'FAIL' if 'FAIL' in statuses else 'BLOCKED' if 'BLOCKED' in statuses else 'PASS'
    report['stage'] = 'RAIL-TRUST-001'
    report['scope'] = 'offline software verification only; PASS is not operational authorization; replay state must be committed externally'
    return report
