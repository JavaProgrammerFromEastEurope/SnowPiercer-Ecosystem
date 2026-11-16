"""v79 functional-stage migration ownership contract."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]

def test_v79_moved_paths_exist_and_old_paths_are_absent():
    migration = json.loads((ROOT / 'AUDIT/FUNCTIONAL_STAGE_PHYSICAL_MIGRATION_V79.json').read_text())
    assert len(migration['moved']) == 10
    for old, new in migration['moved'].items():
        assert not (ROOT / old).exists()
        assert (ROOT / new).is_file()

def test_v79_registry_contains_no_stale_moved_assignments():
    migration = json.loads((ROOT / 'AUDIT/FUNCTIONAL_STAGE_PHYSICAL_MIGRATION_V79.json').read_text())
    registry = json.loads((ROOT / 'tests/kernel_runner/legacy_domain_assignments.json').read_text())['assignments']
    assert not set(migration['moved']).intersection(registry)
    assert len(set(migration['moved'].values())) == 10
