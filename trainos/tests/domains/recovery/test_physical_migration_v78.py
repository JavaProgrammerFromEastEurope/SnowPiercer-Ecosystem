"""Contract for the v78 recovery domain migration."""
import json
from tests.kernel_runner import config


def test_v78_migrated_modules_have_single_recovery_owner():
    root = config.PROJECT_ROOT
    moved = json.loads((root / 'AUDIT/FUNCTIONAL_STAGE_PHYSICAL_MIGRATION_V78.json').read_text())['moved']
    assert len(moved) == 10
    assert len(set(moved.values())) == 10
    assert all(not (root / old).exists() and (root / new).is_file() for old, new in moved.items())
    stages = config.discover_stages()
    owners = {path: stage.name for stage in stages for path in stage.tests}
    assert all(owners[new] == 'recovery' for new in moved.values())
    assert len(owners) == sum(len(stage.tests) for stage in stages)


def test_v78_migration_does_not_leave_stale_assignments():
    root = config.PROJECT_ROOT
    moved = json.loads((root / 'AUDIT/FUNCTIONAL_STAGE_PHYSICAL_MIGRATION_V78.json').read_text())['moved']
    assert not set(moved).intersection(config.load_assignments())
    assert all(new.startswith('tests/domains/recovery/') for new in moved.values())
