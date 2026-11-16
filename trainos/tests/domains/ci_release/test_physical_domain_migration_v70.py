"""Contracts for physical migration of diagnostic tests."""
import json
from pathlib import Path
from tests.kernel_runner import config

MANIFEST = config.PROJECT_ROOT / "AUDIT/FUNCTIONAL_STAGE_PHYSICAL_MIGRATION_V70.json"

def test_migration_manifest_has_ten_modules():
    assert len(json.loads(MANIFEST.read_text())["moved"]) == 10

def test_migrated_modules_exist_at_new_paths():
    for new in json.loads(MANIFEST.read_text())["moved"].values():
        assert (config.PROJECT_ROOT / new).is_file()

def test_migrated_modules_are_not_legacy_assignments():
    assignments = config.load_assignments()
    assert not (set(json.loads(MANIFEST.read_text())["moved"]) & set(assignments))

def test_migrated_modules_are_owned_by_diagnostics():
    expected = set(json.loads(MANIFEST.read_text())["moved"].values())
    actual = next(s for s in config.discover_stages() if s.name == "pytest_diagnostics")
    assert expected <= set(actual.tests)

def test_registry_has_no_duplicate_paths():
    paths = [p for stage in config.discover_stages() for p in stage.tests]
    assert len(paths) == len(set(paths))
