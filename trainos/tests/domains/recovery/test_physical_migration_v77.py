"""Functional ownership checks for the v77 recovery migration."""
import json
from tests.kernel_runner import config

def test_v77_migration_paths_and_unique_ownership():
    root = config.PROJECT_ROOT
    moved = json.loads((root / 'AUDIT/FUNCTIONAL_STAGE_PHYSICAL_MIGRATION_V77.json').read_text())['moved']
    assert len(moved) == 10
    assert len(set(moved.values())) == 10
    assert all(not (root / old).exists() and (root / new).is_file() for old, new in moved.items())
    stages = {stage.name: stage for stage in config.discover_stages()}
    assert set(moved.values()).issubset(set(stages['recovery'].tests))
    paths = [p for stage in stages.values() for p in stage.tests]
    assert len(paths) == len(set(paths))

def test_v77_registry_has_no_stale_migration_paths():
    moved = json.loads((config.PROJECT_ROOT / 'AUDIT/FUNCTIONAL_STAGE_PHYSICAL_MIGRATION_V77.json').read_text())['moved']
    assignments = config.load_assignments()
    assert not set(moved).intersection(assignments)
    assert all(path.startswith('tests/domains/recovery/') for path in moved.values())
