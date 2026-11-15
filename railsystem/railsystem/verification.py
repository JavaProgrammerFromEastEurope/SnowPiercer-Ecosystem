"""RAIL-VER-001: local, non-certifying regression evidence utilities."""
from __future__ import annotations
import hashlib
import io
import json
import re
import unittest
from datetime import datetime, timezone
from pathlib import Path

STAGE_TESTS = {
    'RAIL-ARCH-001': ('test_architecture.py', 'test_contracts.py'),
    'RAIL-REQ-001': ('test_requirements.py',),
    'RAIL-SAFE-001': ('test_safety.py',),
    'RAIL-IF-001': ('test_integration.py',),
    'RAIL-SIM-001': ('test_simulation.py',),
    'RAIL-OPS-001': ('test_operations.py',),
    'RAIL-VER-001': ('test_verification.py',),
    'RAIL-CI-001': ('test_release_gate.py',),
    'RAIL-EVID-001': ('test_provenance.py',),
    'RAIL-TRUST-001': ('test_trust.py',),
    'RAIL-TRUST-002': ('test_trusted_admission.py',),
    'RAIL-TRUST-003': ('test_anchored_admission.py',),
    'RAIL-TRUST-004': ('test_production_fencing.py',),
    'RAIL-TRUST-005': ('test_unified_admission.py',),
    'RAIL-TRUST-006': ('test_recovery_boundary.py',),
    'RAIL-TRUST-007': ('test_atomic_startup.py',),
    'RAIL-TRUST-008': ('test_lifecycle_fencing.py',),
    'RAIL-TRUST-009': ('test_lifecycle_lock_009.py',),
    'RAIL-TRUST-010': ('test_recovery_broker.py',),
    'RAIL-TRUST-011': ('test_privileged_recovery.py',),
    'RAIL-TRUST-012': ('test_provider_ipc_012.py', 'test_os_boundary_012.py'),
    'RAIL-TRUST-013': ('test_write_authority_013.py',),
    'RAIL-TRUST-014': ('test_isolated_authorities_014.py',),
    'RAIL-TRUST-015': ('test_monotonic_root_015.py', 'test_mac_fencing_015.py'),
}

class VerificationError(ValueError):
    pass


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open('rb') as f:
        for chunk in iter(lambda: f.read(65536), b''):
            h.update(chunk)
    return h.hexdigest()


def manifest(root: Path) -> dict:
    root = Path(root).resolve()
    if not root.is_dir():
        raise VerificationError('project root does not exist')
    entries = {}
    for folder in ('railsystem', 'tests', 'docs', 'architecture', 'requirements', 'safety', 'interfaces', 'systemd', 'deployment'):
        directory = root / folder
        if not directory.is_dir():
            if folder in ('systemd', 'deployment'):
                continue  # optional new sources; older project roots stay valid
            raise VerificationError(f'missing directory: {folder}')
        for p in sorted(directory.rglob('*')):
            if not p.is_file() or p.is_symlink() or '__pycache__' in p.parts or p.suffix in ('.pyc', '.pyo'):
                continue
            rel = p.relative_to(root).as_posix()
            entries[rel] = sha256_file(p)
    return {'algorithm': 'sha256', 'files': dict(sorted(entries.items()))}


def verify_manifest(root: Path, expected: dict) -> bool:
    if not isinstance(expected, dict) or expected.get('algorithm') != 'sha256' or not isinstance(expected.get('files'), dict):
        raise VerificationError('invalid manifest')
    return manifest(root) == expected


def stage_for_test(filename: str) -> str:
    matches = [stage for stage, names in STAGE_TESTS.items() if filename in names]
    if len(matches) != 1:
        raise VerificationError(f'unmapped or ambiguous test: {filename}')
    return matches[0]


def coverage(root: Path) -> dict:
    tests = sorted(p.name for p in (Path(root) / 'tests').glob('test_*.py'))
    for name in tests:
        stage_for_test(name)
    mapped = {name for names in STAGE_TESTS.values() for name in names}
    missing = sorted(mapped - set(tests))
    if missing:
        raise VerificationError(f'missing tests: {missing}')
    return {stage: list(names) for stage, names in STAGE_TESTS.items()}


def run_suite(root: Path) -> dict:
    root = Path(root).resolve()
    coverage(root)
    suite = unittest.defaultTestLoader.discover(str(root / 'tests'), pattern='test_*.py')
    stream = io.StringIO()
    result = unittest.TextTestRunner(stream=stream, verbosity=2).run(suite)
    failures = [{'test': str(test), 'message': detail} for test, detail in result.failures]
    errors = [{'test': str(test), 'message': detail} for test, detail in result.errors]
    return {'schema_version': 1, 'stage': 'RAIL-VER-001', 'tests_run': result.testsRun,
            'failures': failures, 'errors': errors, 'skipped': len(result.skipped),
            'successful': result.wasSuccessful(), 'stage_test_files': coverage(root),
            'log': stream.getvalue()}


def evidence(root: Path, *, timestamp: str) -> dict:
    if not re.fullmatch(r'\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z', timestamp):
        raise VerificationError('timestamp must be explicit UTC ISO-8601')
    try:
        datetime.strptime(timestamp, '%Y-%m-%dT%H:%M:%SZ')
    except ValueError as exc:
        raise VerificationError('invalid timestamp') from exc
    return {'generated_at_utc': timestamp, 'regression': run_suite(root), 'manifest': manifest(root),
            'scope': 'local software checks only; no independent safety certification'}


def write_evidence(root: Path, output: Path, *, timestamp: str) -> dict:
    root = Path(root).resolve()
    output = Path(output).resolve()
    if output == root or root in output.parents:
        raise VerificationError('write evidence outside the source tree')
    report = evidence(root, timestamp=timestamp)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2, sort_keys=True, ensure_ascii=False) + '\n', encoding='utf-8')
    return report
