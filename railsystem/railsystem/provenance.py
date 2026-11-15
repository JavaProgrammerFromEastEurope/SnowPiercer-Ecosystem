"""RAIL-EVID-001: offline evidence provenance; never self-approves a baseline."""
from __future__ import annotations
import hashlib
import json
import re
from pathlib import Path
from .verification import manifest, coverage, VerificationError

class ProvenanceError(ValueError):
    pass

HEX = re.compile(r'^[0-9a-f]{64}$')

def canonical_digest(value: dict) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False).encode('utf-8')).hexdigest()

def validate_baseline(baseline: dict) -> dict:
    if not isinstance(baseline, dict) or baseline.get('schema_version') != 1:
        raise ProvenanceError('invalid baseline schema')
    if not isinstance(baseline.get('baseline_id'), str) or not re.fullmatch(r'[A-Za-z0-9._-]{1,80}', baseline['baseline_id']):
        raise ProvenanceError('invalid baseline ID')
    m = baseline.get('manifest')
    if not isinstance(m, dict) or m.get('algorithm') != 'sha256' or not isinstance(m.get('files'), dict) or not m['files']:
        raise ProvenanceError('invalid baseline manifest')
    for path, digest in m['files'].items():
        if not isinstance(path, str) or path.startswith('/') or '\\' in path or any(p in ('', '.', '..') for p in path.split('/')) or not isinstance(digest, str) or not HEX.fullmatch(digest):
            raise ProvenanceError('invalid file entry')
    if baseline.get('manifest_digest') != canonical_digest(m):
        raise ProvenanceError('baseline digest mismatch')
    return baseline

def candidate_baseline(root: Path, baseline_id: str) -> dict:
    """Produces an UNAPPROVED candidate; does not authorize a release."""
    m = manifest(root)
    baseline = {'schema_version': 1, 'baseline_id': baseline_id, 'manifest': m, 'manifest_digest': canonical_digest(m)}
    return validate_baseline(baseline)

def assess(root: Path, *, baseline: dict | None, approval: dict | None, evidence: dict | None) -> dict:
    gates = {}
    try:
        inventory = coverage(root)
        gates['inventory'] = {'status': 'PASS', 'stages': len(inventory)}
    except (VerificationError, OSError) as exc:
        gates['inventory'] = {'status': 'FAIL', 'reason': str(exc)}
    try:
        actual = manifest(root)
    except (VerificationError, OSError) as exc:
        actual = None
        gates['integrity'] = {'status': 'FAIL', 'reason': str(exc)}
    try:
        b = validate_baseline(baseline)
    except ProvenanceError as exc:
        b = None
        gates['baseline'] = {'status': 'BLOCKED' if baseline is None else 'FAIL', 'reason': str(exc)}
    if b is not None:
        gates['baseline'] = {'status': 'PASS', 'baseline_id': b['baseline_id']}
    if actual is not None:
        if b is None:
            gates['integrity'] = {'status': 'BLOCKED', 'reason': 'approved baseline unavailable'}
        else:
            gates['integrity'] = {'status': 'PASS' if actual == b['manifest'] else 'FAIL', 'files': len(actual)}
    # Approval must be an independently supplied, verifiable attestation. This stage
    # deliberately has no trust anchors or signature verifier, so it cannot grant PASS.
    gates['approval'] = {'status': 'BLOCKED', 'reason': 'independent cryptographic approval verification not implemented'}
    if approval is not None and (not isinstance(approval, dict) or approval.get('baseline_id') != (b or {}).get('baseline_id')):
        gates['approval'] = {'status': 'FAIL', 'reason': 'approval does not reference baseline'}
    if evidence is None:
        gates['evidence'] = {'status': 'BLOCKED', 'reason': 'no regression evidence supplied'}
    elif not isinstance(evidence, dict) or not isinstance(evidence.get('regression'), dict):
        gates['evidence'] = {'status': 'FAIL', 'reason': 'invalid evidence structure'}
    else:
        r = evidence['regression']
        if r.get('successful') is not True or type(r.get('tests_run')) is not int or r['tests_run'] <= 0 or r.get('failures') or r.get('errors') or r.get('skipped', 0) != 0:
            gates['evidence'] = {'status': 'FAIL', 'reason': 'regression evidence reports incomplete or failed run'}
        elif actual is None or evidence.get('manifest') != actual or r.get('stage_test_files') != (inventory if gates['inventory']['status'] == 'PASS' else None):
            gates['evidence'] = {'status': 'FAIL', 'reason': 'evidence manifest or inventory mismatch'}
        else:
            gates['evidence'] = {'status': 'PASS', 'tests_run': r['tests_run'], 'note': 'self-reported; provenance not authenticated'}
    statuses = {g['status'] for g in gates.values()}
    status = 'FAIL' if 'FAIL' in statuses else 'BLOCKED' if 'BLOCKED' in statuses else 'PASS'
    return {'schema_version': 1, 'stage': 'RAIL-EVID-001', 'status': status, 'gates': gates, 'scope': 'offline software evidence checks only; not operational approval'}
