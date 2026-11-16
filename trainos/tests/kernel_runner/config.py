"""Functional-stage registry for TrainOS.

Legacy tests retain their original paths; stages are now domain-oriented. New
checks belong in tests/domains/<domain>/test_*.py, not numbered directories.
"""
from dataclasses import dataclass
from pathlib import Path
import re
import json


@dataclass(frozen=True, slots=True)
class StageConfig:
    name: str
    tests: list[str]


PROJECT_ROOT = Path(__file__).resolve().parents[2]
TESTS_ROOT = PROJECT_ROOT / 'tests'
LEGACY_STAGE_PATTERN = re.compile(r'^stage\d+$')

# Ordered by specificity. Classifications are based on test module names;
# ambiguous cases are placed in legacy_contracts for explicit review.
DOMAIN_KEYWORDS = (
    ('pytest_diagnostics', ('pytest_diagnostic', 'pytest_diagnose', 'full_suite_diagnostic')),
    ('financial_ledger', ('ledger', 'reconciliation', 'financial', 'accounting')),
    ('recovery', ('recovery', 'crash', 'retry', 'interrupted', 'lease')),
    ('backup_restore', ('backup', 'restore', 'snapshot')),
    ('security_governance', ('security', 'governance', 'constitution', 'constitutional', 'authorization', 'identity')),
    ('execution_scheduler', ('scheduler', 'execution', 'dispatch', 'task_queue', 'worker')),
    ('events_commands', ('command', 'event', 'journal')),
    ('registry_schema', ('registry', 'schema', 'register')),
    ('ci_release', ('release', 'regression', 'workflow', 'ci_', 'stage_matrix', 'evidence')),
    ('audit_integrity', ('audit', 'integrity', 'validation')),
    ('runtime_kernel', ('runtime', 'kernel', 'engine')),
    ('education', ('education', 'institution')),
    ('healthcare', ('healthcare', 'medical')),
    ('simulation', ('simulation',)),
    ('transactions', ('transaction', 'commit', 'idempotency')),
)
DOMAIN_NAMES = tuple(name for name, _ in DOMAIN_KEYWORDS) + (
    'cognition_learning',
    'society_governance',
    'economy_resources',
    'communication_persistence',
    'orchestration_control',
    'simulation_agents',
    'knowledge_culture',
    'population_services',
    'diagnostic_investigation',
    'legacy_contracts',
)
ASSIGNMENTS_PATH = PROJECT_ROOT / 'tests' / 'kernel_runner' / 'legacy_domain_assignments.json'


def load_assignments() -> dict[str, str]:
    """Load pinned legacy ownership; reject invalid and duplicate assignments."""
    data = json.loads(ASSIGNMENTS_PATH.read_text(encoding='utf-8'))
    if data.get('schema') != 'trainos.functional-stage-assignments.v1':
        raise ValueError('Unsupported functional stage assignment schema')
    assignments = data.get('assignments')
    if not isinstance(assignments, dict):
        raise ValueError('Expected assignments object')
    for path, domain in assignments.items():
        if not isinstance(path, str) or not path.startswith('tests/stage') or '/test_' not in path or '..' in Path(path).parts:
            raise ValueError(f'Invalid legacy test path: {path!r}')
        if domain not in DOMAIN_NAMES:
            raise ValueError(f'Unknown functional stage for {path}: {domain}')
    return assignments



def classify_legacy_test(path: Path) -> str:
    name = path.stem.lower()
    for domain, keywords in DOMAIN_KEYWORDS:
        if any(keyword in name for keyword in keywords):
            return domain
    return 'legacy_contracts'


def discover_stages() -> list[StageConfig]:
    if not TESTS_ROOT.is_dir():
        raise FileNotFoundError(f'Tests directory not found: {TESTS_ROOT}')
    groups: dict[str, set[str]] = {name: set() for name in DOMAIN_NAMES}
    assignments = load_assignments()
    discovered_legacy: set[str] = set()
    # Legacy layout is retained because old tests and scripts may reference it.
    for directory in TESTS_ROOT.iterdir():
        if directory.is_dir() and LEGACY_STAGE_PATTERN.fullmatch(directory.name):
            for test_file in directory.rglob('test_*.py'):
                relative = test_file.relative_to(PROJECT_ROOT).as_posix()
                discovered_legacy.add(relative)
                if relative not in assignments:
                    raise ValueError(f'Unassigned legacy test: {relative}; update legacy_domain_assignments.json')
                groups[assignments[relative]].add(relative)
    stale = set(assignments) - discovered_legacy
    if stale:
        raise ValueError(f'Stale legacy test assignments: {sorted(stale)[:5]}')
    # The permanent location for all future tests.
    domain_root = TESTS_ROOT / 'domains'
    if domain_root.is_dir():
        for directory in domain_root.iterdir():
            if not directory.is_dir():
                continue
            if directory.name not in groups:
                raise ValueError(f'Unregistered functional stage: {directory.name}')
            for test_file in directory.rglob('test_*.py'):
                groups[directory.name].add(test_file.relative_to(PROJECT_ROOT).as_posix())
    stages = [StageConfig(name=name, tests=sorted(groups[name]))
              for name in DOMAIN_NAMES if groups[name]]
    if not stages:
        raise RuntimeError(f'No test stages found in: {TESTS_ROOT}')
    return stages


STAGES: list[StageConfig] = discover_stages()
