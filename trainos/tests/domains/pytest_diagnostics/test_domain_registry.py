"""Functional-stage registration contract."""
from tests.kernel_runner.config import STAGES, DOMAIN_NAMES, classify_legacy_test
from pathlib import Path


def test_domain_stage_names_are_unique_and_registered():
    names = [stage.name for stage in STAGES]
    assert len(names) == len(set(names))
    assert set(names) <= set(DOMAIN_NAMES)


def test_each_test_file_belongs_to_exactly_one_stage():
    paths = [path for stage in STAGES for path in stage.tests]
    assert len(paths) == len(set(paths))


def test_v67_diagnostic_modules_share_one_stage():
    domain = next(stage for stage in STAGES if stage.name == 'pytest_diagnostics')
    for n in range(578, 588):
        assert any(f'test_stage{n}_pytest_diagnostic.py' in path for path in domain.tests)


def test_unknown_legacy_names_are_not_misclassified():
    assert classify_legacy_test(Path('test_unknown_behavior.py')) == 'legacy_contracts'
