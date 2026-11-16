"""SnowPiercer operations inventory, provenance checks, and conservative readiness assessment.

This module provides observations and a NO-GO advisory, never runtime admission,
actuation or a safety/operational authorization. Standard library only.
"""
from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import stat
from typing import Any

SCHEMA = 'snowpiercer.ops-assessment.v1'
MODULE_IDS = frozenset({
    'SP-SW', 'SP-AI', 'SP-RAIL', 'SP-ENERGY', 'SP-LIFE', 'SP-LOG',
    'SP-SAFE', 'SP-ISLAND', 'SP-OPS'
})
ALLOWED_STATES = frozenset({'PENDING', 'SOFTWARE_OBSERVED_NO_GO', 'ARCHIVED_NO_GO'})
HEX_DIGEST = re.compile(r'[a-f0-9]{64}\Z')
REQUIRED_BLOCKERS = frozenset(f'OPS-GATE-{i:03d}' for i in range(1, 9))


class InventoryError(ValueError):
    pass


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding='utf-8'))


def validate_catalog(catalog: dict) -> None:
    if not isinstance(catalog, dict) or catalog.get('schema') != 'snowpiercer.ops-catalog.v1':
        raise InventoryError('Unknown catalog schema')
    entries = catalog.get('modules')
    if not isinstance(entries, list) or len(entries) != 9:
        raise InventoryError('Exactly nine module records required')
    ids = [m.get('moduleId') for m in entries if isinstance(m, dict)]
    if len(ids) != 9 or set(ids) != MODULE_IDS:
        raise InventoryError('Missing, duplicate, or unknown modules')
    blockers = catalog.get('globalBlockers')
    if not isinstance(blockers, list) or len(blockers) != len(REQUIRED_BLOCKERS) or not all(isinstance(b, dict) for b in blockers):
        raise InventoryError('All eight mandatory blockers must be represented')
    if {b.get('id') for b in blockers} != REQUIRED_BLOCKERS:
        raise InventoryError('Mandatory blocker set incomplete or duplicate')
    if not all(b.get('state') == 'UNVERIFIED' and isinstance(b.get('reason'), str) and b['reason'] for b in blockers):
        raise InventoryError('A blocker cannot be marked verified by local catalog')
    for entry in entries:
        if entry.get('readiness') not in ALLOWED_STATES:
            raise InventoryError('Invalid readiness state')
        if not isinstance(entry.get('baseline'), str) or not entry['baseline']:
            raise InventoryError('A source baseline label is required')
        dependencies = entry.get('dependencies')
        if not isinstance(dependencies, list) or len(dependencies) != len(set(dependencies)):
            raise InventoryError('Invalid or duplicate dependencies')
        if not set(dependencies) <= MODULE_IDS or entry['moduleId'] in dependencies:
            raise InventoryError('Unknown or self dependency')
        items = entry.get('artifacts')
        if not isinstance(items, list):
            raise InventoryError('Artifact list required')
        if not all(isinstance(a, dict) for a in items):
            raise InventoryError('Artifact records must be objects')
        if len({a.get('path') for a in items}) != len(items):
            raise InventoryError('Duplicate artifact path')
        for artifact in items:
            if not isinstance(artifact, dict) or not isinstance(artifact.get('path'), str):
                raise InventoryError('Invalid artifact record')
            digest = artifact.get('expectedSha256')
            if digest is not None and (not isinstance(digest, str) or not HEX_DIGEST.fullmatch(digest)):
                raise InventoryError('Invalid expected sha256')
            if artifact.get('classification') not in {'ARCHIVED_RELEASE', 'REVIEWED_SOURCE', 'LOCAL_OBSERVATION'}:
                raise InventoryError('Unknown artifact classification')


def safe_artifact(root: Path, relative: str) -> Path:
    """No absolute paths, dot segments, symlink components or non-regular files."""
    if (not isinstance(relative, str) or not relative or '\\' in relative or
            relative.startswith('/') or '\x00' in relative):
        raise InventoryError('Unsafe artifact path')
    components = relative.split('/')
    if any(p in {'', '.', '..'} for p in components):
        raise InventoryError('Unsafe artifact path')
    base = root.resolve(strict=True)
    target = base
    for part in components:
        target = target / part
        try:
            mode = target.lstat().st_mode
        except FileNotFoundError:
            raise FileNotFoundError(relative) from None
        if stat.S_ISLNK(mode):
            raise InventoryError('Symlink in evidence path')
    if not target.is_file():
        raise InventoryError('Evidence must be a regular file')
    return target


def file_sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()


def artifact_observation(root: Path, artifact: dict) -> dict:
    result = {'path': artifact['path'], 'classification': artifact['classification']}
    try:
        target = safe_artifact(root, artifact['path'])
        result['sha256'] = file_sha256(target)
        result['sizeBytes'] = target.stat().st_size
        expected = artifact.get('expectedSha256')
        if expected is None:
            result['status'] = 'PRESENT_UNATTESTED'
        elif expected == result['sha256']:
            result['status'] = 'DIGEST_MATCH_UNATTESTED'
        else:
            result['status'] = 'DIGEST_MISMATCH'
            result['expectedSha256'] = expected
    except (FileNotFoundError, OSError, InventoryError) as error:
        result['status'] = 'UNAVAILABLE_OR_UNSAFE'
        result['error'] = f'{type(error).__name__}: {error}'
    return result


def dependency_cycles(modules: list[dict]) -> list[list[str]]:
    edges = {m['moduleId']: sorted(m['dependencies']) for m in modules}
    # Johnson-style exhaustive simple cycles, canonicalizing rotated paths.
    cycles: set[tuple[str, ...]] = set()
    for start in sorted(edges):
        def visit(node: str, path: list[str]) -> None:
            for neighbor in edges[node]:
                if neighbor == start:
                    cycles.add(tuple(path))
                elif neighbor not in path and neighbor > start:
                    visit(neighbor, path + [neighbor])
        visit(start, [start])
    return [list(c) + [c[0]] for c in sorted(cycles)]


def assess(root: Path, catalog: dict, *, at: str | None = None) -> dict:
    validate_catalog(catalog)
    registered = []
    findings = []
    for module in catalog['modules']:
        observations = [artifact_observation(root, a) for a in module['artifacts']]
        record = {'moduleId': module['moduleId'], 'baseline': module['baseline'],
                  'sourceReadiness': module['readiness'],
                  'dependencies': module['dependencies'], 'evidence': observations,
                  'operationalReady': False}
        registered.append(record)
        if module['readiness'] == 'PENDING':
            findings.append({'code': 'MODULE_BASELINE_PENDING', 'moduleId': module['moduleId']})
        if not observations:
            findings.append({'code': 'NO_ARTIFACTS', 'moduleId': module['moduleId']})
        for artifact in observations:
            if artifact['status'] in {'UNAVAILABLE_OR_UNSAFE', 'DIGEST_MISMATCH'}:
                findings.append({'code': 'ARTIFACT_INTEGRITY_FAILURE',
                                 'moduleId': module['moduleId'], 'path': artifact['path']})
    cycles = dependency_cycles(catalog['modules'])
    for cycle in cycles:
        findings.append({'code': 'DEPENDENCY_CYCLE', 'path': cycle})
    for control in catalog.get('globalBlockers', []):
        if not isinstance(control, dict) or not isinstance(control.get('id'), str):
            raise InventoryError('Invalid blocker record')
        findings.append({'code': 'UNVERIFIED_REQUIRED_CONTROL',
                         'controlId': control['id'], 'reason': control.get('reason', '')})
    if not catalog.get('globalBlockers'):
        raise InventoryError('No safety controls defined: cannot evaluate')
    return {
        'schema': SCHEMA, 'assessedAt': at or datetime.now(timezone.utc).isoformat(),
        'assessmentKind': 'OFFLINE_EVIDENCE_INVENTORY_ONLY',
        'sourceSnapshot': catalog['snapshot'],
        'modules': registered,
        'findings': findings,
        'summary': {'modulesObserved': len(registered),
                    'evidenceRecords': sum(len(m['evidence']) for m in registered),
                    'digestMatchesUnattested': sum(a['status'] == 'DIGEST_MATCH_UNATTESTED'
                        for m in registered for a in m['evidence']),
                    'artifactFailures': sum(a['status'] in {'UNAVAILABLE_OR_UNSAFE', 'DIGEST_MISMATCH'}
                        for m in registered for a in m['evidence']),
                    'dependencyCycles': len(cycles),
                    'unverifiedControls': len(catalog['globalBlockers'])},
        'operationalReady': False, 'decision': 'NO_GO',
        'ecosystemCompletionPercent': None,
        'limits': [
            'SHA-256 concordance is not a trusted timestamp or independent integrity root.',
            'Local software tests are not cross-module hardware or safety certification.',
            'No GO authority, safety actuation, permit issuance or production admission exists in this tool.',
            'Source snapshot is fixed; newer releases must be re-imported and re-verified.'
        ]
    }


def write_report(report: dict, dest: Path) -> None:
    """Atomic replacement for ordinary files; no durability or security assertion."""
    dest.parent.mkdir(parents=True, exist_ok=True)
    temporary = dest.with_name(dest.name + f'.tmp-{os.getpid()}')
    try:
        with temporary.open('x', encoding='utf-8') as stream:
            json.dump(report, stream, ensure_ascii=False, indent=2)
            stream.write('\n')
        os.replace(temporary, dest)
    finally:
        temporary.unlink(missing_ok=True)
