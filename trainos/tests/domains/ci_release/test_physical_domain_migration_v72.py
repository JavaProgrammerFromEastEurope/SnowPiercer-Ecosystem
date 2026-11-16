"""Physical CI/release test migration v72 contracts."""
import json
from tests.kernel_runner import config

MANIFEST = config.PROJECT_ROOT / "AUDIT/FUNCTIONAL_STAGE_PHYSICAL_MIGRATION_V72.json"

def _moved():
    return json.loads(MANIFEST.read_text(encoding="utf-8"))["moved"]

def test_migrated_exactly_ten_modules():
    assert len(_moved()) == 10

def test_new_files_exist_old_files_absent():
    assert all((config.PROJECT_ROOT / new).is_file() and not (config.PROJECT_ROOT / old).exists() for old, new in _moved().items())

def test_registry_has_no_stale_entries():
    assert not set(_moved()).intersection(config.load_assignments())

def test_ci_release_discovers_all_migrated_modules():
    ci = next(stage for stage in config.discover_stages() if stage.name == "ci_release")
    assert set(_moved().values()).issubset(ci.tests)

def test_stage_ownership_is_unique():
    paths = [p for stage in config.discover_stages() for p in stage.tests]
    assert len(paths) == len(set(paths))

def test_migration_preserves_filenames():
    assert all(old.rsplit("/", 1)[-1] == new.rsplit("/", 1)[-1] for old, new in _moved().items())
