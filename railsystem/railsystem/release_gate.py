"""RAIL-CI-001: fail-closed, non-certifying local release gates."""
from __future__ import annotations
import json
import re
from pathlib import Path
from .verification import coverage, manifest, run_suite, VerificationError

class GateError(ValueError):
    pass

def evaluate(root: Path, *, expected_manifest: dict | None = None, regression: dict | None = None) -> dict:
    """Evaluate all release gates. BLOCKED is used for unavailable prerequisites."""
    root = Path(root).resolve()
    gates = {}
    try:
        mapping = coverage(root)
        gates['test_inventory'] = {'status': 'PASS', 'stages': len(mapping)}
    except (VerificationError, OSError) as exc:
        gates['test_inventory'] = {'status': 'FAIL', 'reason': str(exc)}
    if gates['test_inventory']['status'] != 'PASS':
        gates['regression'] = {'status': 'BLOCKED', 'reason': 'test inventory failed'}
    else:
        try:
            result = regression if regression is not None else run_suite(root)
            if not isinstance(result, dict) or not isinstance(result.get('tests_run'), int) or isinstance(result.get('tests_run'), bool) or result['tests_run'] <= 0 or result.get('successful') is not True or result.get('failures') or result.get('errors') or result.get('skipped', 0) != 0:
                gates['regression'] = {'status': 'FAIL', 'reason': 'regression incomplete or failed'}
            else:
                gates['regression'] = {'status': 'PASS', 'tests_run': result['tests_run']}
        except (Exception) as exc:
            gates['regression'] = {'status': 'FAIL', 'reason': f'{type(exc).__name__}: {exc}'}
    try:
        actual = manifest(root)
        if expected_manifest is None:
            gates['integrity'] = {'status': 'BLOCKED', 'reason': 'no independently approved baseline provided'}
        elif actual == expected_manifest:
            gates['integrity'] = {'status': 'PASS', 'files': len(actual['files'])}
        else:
            gates['integrity'] = {'status': 'FAIL', 'reason': 'manifest mismatch'}
    except (VerificationError, OSError) as exc:
        gates['integrity'] = {'status': 'FAIL', 'reason': str(exc)}
    statuses = {item['status'] for item in gates.values()}
    status = 'FAIL' if 'FAIL' in statuses else 'BLOCKED' if 'BLOCKED' in statuses else 'PASS'
    return {'schema_version': 1, 'stage': 'RAIL-CI-001', 'status': status, 'gates': gates,
            'scope': 'software release gate only; not permission for physical operations'}

def write_report(report: dict, output: Path) -> None:
    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, sort_keys=True, indent=2) + '\n', encoding='utf-8')
