"""Contract tests for pinned functional stage ownership."""
import json
from pathlib import Path
import pytest
from tests.kernel_runner import config


def test_assignments_are_loaded():
    assert config.load_assignments()

def test_every_legacy_test_is_pinned():
    registered = config.load_assignments()
    discovered = {p.relative_to(config.PROJECT_ROOT).as_posix() for d in config.TESTS_ROOT.iterdir() if d.is_dir() and config.LEGACY_STAGE_PATTERN.fullmatch(d.name) for p in d.rglob('test_*.py')}
    assert discovered == set(registered)

def test_no_duplicate_test_ownership():
    all_paths = [p for stage in config.STAGES for p in stage.tests]
    assert len(all_paths) == len(set(all_paths))

def test_stages_are_registered():
    assert set(s.name for s in config.STAGES) <= set(config.DOMAIN_NAMES)

def test_each_stage_has_sorted_tests():
    assert all(s.tests == sorted(s.tests) for s in config.STAGES)

def test_diagnostics_stages_578_to_587_are_one_domain():
    diagnostic = next(s for s in config.STAGES if s.name == 'pytest_diagnostics')
    assert all(any(f'test_stage{i}_pytest_diagnostic.py' in p for p in diagnostic.tests) for i in range(578,588))

def test_new_domain_tests_are_discovered():
    ci = next(s for s in config.STAGES if s.name == 'ci_release')
    assert 'tests/domains/ci_release/test_functional_stage_assignments.py' in ci.tests

def test_unregistered_domain_rejected(tmp_path, monkeypatch):
    monkeypatch.setattr(config, 'TESTS_ROOT', tmp_path)
    (tmp_path / 'domains' / 'unknown_domain').mkdir(parents=True)
    (tmp_path / 'domains' / 'unknown_domain' / 'test_example.py').write_text('pass')
    monkeypatch.setattr(config, 'load_assignments', lambda: {})
    with pytest.raises(ValueError, match='Unregistered functional stage'):
        config.discover_stages()

def test_invalid_domain_assignment_rejected(tmp_path, monkeypatch):
    f = tmp_path / 'assignments.json'
    f.write_text(json.dumps({'schema':'trainos.functional-stage-assignments.v1','assignments':{'tests/stage1/test_a.py':'unregistered'}}))
    monkeypatch.setattr(config, 'ASSIGNMENTS_PATH', f)
    with pytest.raises(ValueError, match='Unknown functional stage'):
        config.load_assignments()

def test_missing_legacy_assignment_rejected(tmp_path, monkeypatch):
    (tmp_path / 'stage900' ).mkdir()
    (tmp_path / 'stage900' / 'test_new.py').write_text('pass')
    monkeypatch.setattr(config, 'PROJECT_ROOT', tmp_path.parent)
    monkeypatch.setattr(config, 'TESTS_ROOT', tmp_path)
    monkeypatch.setattr(config, 'load_assignments', lambda: {})
    with pytest.raises(ValueError, match='Unassigned legacy test'):
        config.discover_stages()
