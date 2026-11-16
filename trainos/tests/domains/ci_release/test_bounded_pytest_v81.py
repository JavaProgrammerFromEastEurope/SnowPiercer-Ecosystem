"""v81 regression evidence and process-lifecycle contracts."""
import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
SPEC = importlib.util.spec_from_file_location('bounded_pytest_v81', ROOT/'scripts/ci/run_bounded_pytest.py')
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def test_bounded_runner_success(tmp_path):
    test_file = tmp_path/'test_ok.py'
    test_file.write_text('def test_ok(): assert True\n')
    report = tmp_path/'success.json'
    assert MODULE.run_bounded([str(test_file),'-q'],20,report)==0
    assert json.loads(report.read_text())['status']=='passed'
    assert report.with_suffix('.pytest.log').exists()


def test_bounded_runner_failure(tmp_path):
    test_file = tmp_path/'test_bad.py'
    test_file.write_text('def test_bad(): assert False\n')
    report = tmp_path/'failure.json'
    assert MODULE.run_bounded([str(test_file),'-q'],20,report)!=0
    assert json.loads(report.read_text())['status']=='failed'


def test_bounded_runner_timeout(tmp_path):
    test_file = tmp_path/'test_hang.py'
    test_file.write_text('import time\ndef test_hang(): time.sleep(10)\n')
    report = tmp_path/'timeout.json'
    assert MODULE.run_bounded([str(test_file),'-q'],0.5,report,0.2)==124
    assert json.loads(report.read_text())['timed_out'] is True


def test_v81_migration_and_pinned_ownership():
    migration=json.loads((ROOT/'AUDIT/FUNCTIONAL_STAGE_PHYSICAL_MIGRATION_V81.json').read_text())
    assignments=json.loads((ROOT/'tests/kernel_runner/legacy_domain_assignments.json').read_text())['assignments']
    assert len(migration['moved'])==10
    for old,new in migration['moved'].items():
        assert not (ROOT/old).exists()
        assert (ROOT/new).is_file()
        assert old not in assignments
        assert new.startswith('tests/domains/recovery/')
