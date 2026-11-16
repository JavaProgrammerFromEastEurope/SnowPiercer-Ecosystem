"""Contracts for v69 functional ownership migration."""
from collections import Counter
from tests.kernel_runner import config


def test_no_legacy_contracts_remaining():
    assert 'legacy_contracts' not in {d for d in config.load_assignments().values()}

def test_each_legacy_file_has_exactly_one_owner():
    assigned = config.load_assignments()
    discovered = {p.relative_to(config.PROJECT_ROOT).as_posix() for d in config.TESTS_ROOT.iterdir() if d.is_dir() and config.LEGACY_STAGE_PATTERN.fullmatch(d.name) for p in d.rglob('test_*.py')}
    assert set(assigned) == discovered

def test_stage_ownership_deterministic():
    assert [(s.name, s.tests) for s in config.discover_stages()] == [(s.name, s.tests) for s in config.discover_stages()]

def test_all_paths_unique():
    paths = [p for s in config.STAGES for p in s.tests]
    assert len(paths) == len(set(paths))

def test_domains_for_foundational_subsystems():
    assigned = config.load_assignments()
    expected = {1: 'orchestration_control', 5: 'cognition_learning', 6: 'simulation_agents', 8: 'cognition_learning', 16: 'society_governance', 21: 'economy_resources', 27: 'population_services', 32: 'communication_persistence', 61: 'diagnostic_investigation'}
    for stage, domain in expected.items():
        assert domain in {owner for path, owner in assigned.items() if path.startswith(f'tests/stage{stage}/')}

def test_all_configured_domains_registered():
    assert set(config.load_assignments().values()) <= set(config.DOMAIN_NAMES)
