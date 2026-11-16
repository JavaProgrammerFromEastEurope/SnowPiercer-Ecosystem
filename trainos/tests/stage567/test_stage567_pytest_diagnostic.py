import importlib.util, json, subprocess, sys
from pathlib import Path
import pytest
ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts/ci/run_pytest_diagnostic.py"
spec = importlib.util.spec_from_file_location("run_pytest_diagnostic", SCRIPT)
module = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = module
spec.loader.exec_module(module)

def test_timeout_is_never_mislabeled_as_pass_or_assertion_failure():
    report = module.build_report(command=["pytest"], result="INCOMPLETE_TIMEOUT", exit_code=124,
        elapsed_seconds=30, timeout_seconds=30, log_path=Path("run.log"), log_text="")
    assert report["result"] not in ("PASS", "FAIL")
    assert report["exit_code"] == 124
    assert report["progress"]["last_observed_test"] is None


def test_ci_runs_full_suite_diagnostic_and_uploads_evidence():
    workflow = (ROOT / ".github/workflows/trainos-tests.yml").read_text(encoding="utf-8")
    assert "scripts/ci/run_pytest_diagnostic.py" in workflow
    assert "--timeout-seconds 600" in workflow
    assert "trainos-full-suite-diagnostics" in workflow
