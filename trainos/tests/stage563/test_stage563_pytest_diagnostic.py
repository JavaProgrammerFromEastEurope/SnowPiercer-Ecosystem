import importlib.util, json, subprocess, sys
from pathlib import Path
import pytest
ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts/ci/run_pytest_diagnostic.py"
spec = importlib.util.spec_from_file_location("run_pytest_diagnostic", SCRIPT)
module = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = module
spec.loader.exec_module(module)

def test_success_report_does_not_add_timeout_note():
    report = module.build_report(command=["pytest"], result="PASS", exit_code=0,
        elapsed_seconds=1, timeout_seconds=30, log_path=Path("run.log"),
        log_text="tests/a.py::test_ok PASSED\n")
    assert report["result"] == "PASS"
    assert "note" not in report
