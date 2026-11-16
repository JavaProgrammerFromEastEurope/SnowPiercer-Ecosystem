"""v97: detect children remaining after pytest leader exits successfully."""
import importlib.util
import json
import os
from pathlib import Path
import pytest

ROOT = Path(__file__).resolve().parents[3]
SPEC = importlib.util.spec_from_file_location('bounded_v97', ROOT / 'scripts/ci/run_bounded_pytest.py')
RUNNER = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(RUNNER)

@pytest.mark.skipif(os.name != 'posix', reason='POSIX only')
def test_successful_leader_with_residual_child_is_not_pass(tmp_path):
    test_file = tmp_path / 'test_detached.py'
    test_file.write_text(
        'import subprocess,sys\n'
        'def test_spawn_child():\n'
        '    subprocess.Popen([sys.executable,"-c","import time;time.sleep(30)"], '
        'stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)\n'
    )
    report = tmp_path / 'residual.json'
    assert RUNNER.run_bounded([str(test_file), '-q'], 12, report, grace=0.5) == 125
    result = json.loads(report.read_text())
    assert result['unexpected_residual_group'] is True
    assert result['status'] == 'failed'
    assert result['group_absence_verified'] is True

def test_clean_pytest_process_reports_pass(tmp_path):
    test_file = tmp_path / 'test_clean.py'
    test_file.write_text('def test_ok(): assert True\n')
    report = tmp_path / 'clean.json'
    assert RUNNER.run_bounded([str(test_file), '-q'], 12, report) == 0
    result = json.loads(report.read_text())
    assert result['status'] == 'passed'
    assert result['unexpected_residual_group'] is False
