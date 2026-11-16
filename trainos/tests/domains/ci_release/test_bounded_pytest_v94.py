"""Bounded runner signal escalation with an actual SIGTERM-resistant child."""
import importlib.util
import json
import os
from pathlib import Path
import pytest

ROOT = Path(__file__).resolve().parents[3]
SPEC = importlib.util.spec_from_file_location('bounded_v94', ROOT / 'scripts/ci/run_bounded_pytest.py')
RUNNER = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(RUNNER)

@pytest.mark.skipif(os.name != 'posix', reason='POSIX only')
def test_sigkill_escalation_for_term_resistant_child(tmp_path):
    script = tmp_path / 'test_stubborn.py'
    # Readiness handshake: prove *both* handlers are installed before the
    # timeout begins. A scheduler can delay fork/exec under four workers.
    child_ready = tmp_path / 'child_ready'
    leader_ready = tmp_path / 'leader_ready'
    child_code = ("import pathlib,signal,time;"
                  "signal.signal(signal.SIGTERM,signal.SIG_IGN);"
                  f"pathlib.Path({str(child_ready)!r}).write_text('ready');"
                  "time.sleep(60)")
    script.write_text(
        'import pathlib, signal, subprocess, sys, time\n'
        'def test_stubborn():\n'
        f'    p = subprocess.Popen([sys.executable,"-c",{child_code!r}])\n'
        f'    ready = pathlib.Path({str(child_ready)!r})\n'
        '    deadline = time.monotonic() + 4\n'
        '    while not ready.exists() and time.monotonic() < deadline: time.sleep(0.02)\n'
        '    assert ready.exists(), "child handler not ready"\n'
        '    signal.signal(signal.SIGTERM,signal.SIG_IGN)\n'
        f'    pathlib.Path({str(leader_ready)!r}).write_text("ready")\n'
        '    time.sleep(60)\n'
    )
    report = tmp_path / 'stubborn.json'
    assert RUNNER.run_bounded([str(script), '-q'], timeout=5.0, report=report, grace=0.3) == 124
    assert leader_ready.exists() and child_ready.exists(), 'SIGTERM resistance was not established'
    result = json.loads(report.read_text())
    assert result['timed_out'] and result['leader_reaped']
    assert 'group_sigkill' in result['group_cleanup']
    assert report.with_suffix('.stdout.log').exists()
    assert report.with_suffix('.stderr.log').exists()
