"""Release v75: migration ownership and recovery migration readiness."""
import json
from tests.kernel_runner import config

def test_v75_paths_relocated_without_duplicates():
    root = config.PROJECT_ROOT
    moved = json.loads((root / 'AUDIT/FUNCTIONAL_STAGE_PHYSICAL_MIGRATION_V75.json').read_text())['moved']
    assert len(moved) == 10
    assert len(set(moved.values())) == len(moved)
    assert all(not (root / old).exists() for old in moved)
    assert all((root / new).is_file() for new in moved.values())

def test_v75_ownership_and_recovery_preserved():
    stages = {stage.name: stage for stage in config.discover_stages()}
    moved = json.loads((config.PROJECT_ROOT / 'AUDIT/FUNCTIONAL_STAGE_PHYSICAL_MIGRATION_V75.json').read_text())['moved']
    assert set(moved.values()).issubset(set(stages['ci_release'].tests))
    assert stages['recovery'].tests
    all_paths = [path for stage in stages.values() for path in stage.tests]
    assert len(all_paths) == len(set(all_paths))
