import importlib.util, json, subprocess, sys
from pathlib import Path
import pytest
ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts/ci/run_pytest_diagnostic.py"
spec = importlib.util.spec_from_file_location("run_pytest_diagnostic", SCRIPT)
module = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = module
spec.loader.exec_module(module)

def test_timeout_report_is_explicitly_incomplete():
    report = module.build_report(command=["pytest"], result="INCOMPLETE_TIMEOUT", exit_code=124,
        elapsed_seconds=3.14159, timeout_seconds=3, log_path=Path("run.log"),
        log_text="tests/stage1/test_a.py::test_wait [ 50%]\n")
    assert report["result"] == "INCOMPLETE_TIMEOUT"
    assert report["exit_code"] == 124
    assert report["progress"]["last_observed_test"] == "tests/stage1/test_a.py::test_wait"
    assert "not a test-suite pass" in report["note"]
