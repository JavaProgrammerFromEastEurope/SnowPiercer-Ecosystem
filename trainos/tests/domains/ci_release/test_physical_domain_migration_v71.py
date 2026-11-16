"""Contracts for the second diagnostic domain migration batch."""
import json
from tests.kernel_runner import config

MANIFEST = config.PROJECT_ROOT / "AUDIT/FUNCTIONAL_STAGE_PHYSICAL_MIGRATION_V71.json"

def _moved():
    return json.loads(MANIFEST.read_text(encoding="utf-8"))["moved"]

def test_exactly_ten_historical_modules_migrated():
    assert len(_moved()) == 10

def test_all_new_modules_exist_and_old_paths_do_not():
    assert all((config.PROJECT_ROOT / new).is_file() and not (config.PROJECT_ROOT / old).exists() for old, new in _moved().items())

def test_migrated_modules_are_no_longer_legacy_assignments():
    assert not set(_moved()).intersection(config.load_assignments())

def test_migrated_modules_are_discovered_in_diagnostics():
    diagnostic = next(stage for stage in config.discover_stages() if stage.name == "pytest_diagnostics")
    assert set(_moved().values()).issubset(diagnostic.tests)

def test_all_stage_paths_have_unique_owners():
    paths = [p for stage in config.discover_stages() for p in stage.tests]
    assert len(paths) == len(set(paths))

def test_migration_preserves_test_source_identity():
    for old, new in _moved().items():
        assert old.split("/")[-1] == new.split("/")[-1]
