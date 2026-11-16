"""Real child-process timeout and cleanup contracts (POSIX)."""
import importlib.util
import json
import os
from pathlib import Path
import signal
import time
import pytest

ROOT = Path(__file__).resolve().parents[3]
SPEC = importlib.util.spec_from_file_location("bounded_pytest_v93", ROOT / "scripts/ci/run_bounded_pytest.py")
RUNNER = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(RUNNER)

@pytest.mark.skipif(os.name != "posix", reason="POSIX process groups required")
def test_timeout_kills_child_process_group(tmp_path):
    child_pid = tmp_path / "child.pid"
    test_file = tmp_path / "test_child.py"
    test_file.write_text("import subprocess,sys,time\n"
        "def test_spawn():\n"
        f"    child=subprocess.Popen([sys.executable,'-c','import time; time.sleep(60)'])\n"
        f"    open({str(child_pid)!r},'w').write(str(child.pid))\n"
        "    time.sleep(60)\n")
    report = tmp_path / "timeout.json"
    assert RUNNER.run_bounded([str(test_file), "-q"], 2.0, report, grace=0.5) == 124
    result = json.loads(report.read_text())
    assert result["timed_out"] is True
    assert result["leader_reaped"] is True
    assert result["group_absence_verified"] is True
    assert report.with_suffix(".stdout.log").exists()
    assert report.with_suffix(".stderr.log").exists()

def test_failure_report_is_durable(tmp_path):
    test_file = tmp_path / "test_failure.py"
    test_file.write_text("def test_failure(): assert False\n")
    report = tmp_path / "failed.json"
    assert RUNNER.run_bounded([str(test_file), "-q"], 10.0, report) != 0
    result = json.loads(report.read_text())
    assert result["status"] == "failed"
    assert result["leader_reaped"] is True
    assert result["returncode"] != 0
