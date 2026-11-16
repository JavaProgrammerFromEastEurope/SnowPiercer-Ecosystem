"""Ensure historical duplicate basenames remain collectable."""
import configparser
import json
from pathlib import Path
from tests.kernel_runner import config

def test_importlib_collection_configured():
    parser = configparser.ConfigParser()
    parser.read(config.PROJECT_ROOT / 'pytest.ini')
    assert '--import-mode=importlib' in parser['pytest']['addopts']

def test_relocated_release_contracts_registered_once():
    report = json.loads((config.PROJECT_ROOT / 'AUDIT/FUNCTIONAL_STAGE_PHYSICAL_MIGRATION_V74.json').read_text())
    moved = report['moved']
    assert len(moved) == 10
    assert all(not (config.PROJECT_ROOT / old).exists() for old in moved)
    assert all((config.PROJECT_ROOT / new).is_file() for new in moved.values())
    stage = next(s for s in config.discover_stages() if s.name == 'ci_release')
    assert set(moved.values()).issubset(stage.tests)

def test_all_domain_ownership_unique():
    targets = [p for stage in config.discover_stages() for p in stage.tests]
    assert len(targets) == len(set(targets))
