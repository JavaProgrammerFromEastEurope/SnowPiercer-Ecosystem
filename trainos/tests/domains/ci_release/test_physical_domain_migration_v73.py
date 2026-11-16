"""Functional-stage physical migration v73 contract."""
import json
from pathlib import Path
from tests.kernel_runner import config

MANIFEST = config.PROJECT_ROOT / 'AUDIT/FUNCTIONAL_STAGE_PHYSICAL_MIGRATION_V73.json'

def _moved():
    return json.loads(MANIFEST.read_text(encoding='utf-8'))['moved']

def test_moved_exactly_ten():
    assert len(_moved()) == 10

def test_source_removed_and_destination_exists():
    assert all(not (config.PROJECT_ROOT / old).exists() and (config.PROJECT_ROOT / new).is_file() for old,new in _moved().items())

def test_no_stale_assignments():
    assert not (set(_moved()) & set(config.load_assignments()))

def test_all_destinations_discovered_in_ci_release():
    stage = next(x for x in config.discover_stages() if x.name == 'ci_release')
    assert set(_moved().values()) <= set(stage.tests)

def test_global_test_ownership_is_unique():
    tests = [p for stage in config.discover_stages() for p in stage.tests]
    assert len(tests) == len(set(tests))

def test_migrated_files_use_repository_root():
    assert all('Path(__file__).resolve().parents[3]' in (config.PROJECT_ROOT / new).read_text() for new in _moved().values() if 'Path(__file__)' in (config.PROJECT_ROOT / new).read_text())
