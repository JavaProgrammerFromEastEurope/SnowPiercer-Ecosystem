import importlib.util, json, subprocess, sys
from pathlib import Path
import pytest
ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts/ci/run_pytest_diagnostic.py"
spec = importlib.util.spec_from_file_location("run_pytest_diagnostic", SCRIPT)
module = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = module
spec.loader.exec_module(module)

def test_progress_parser_counts_outcomes_without_calling_timeout_a_failure():
    report = module.summarize_log("tests/a.py::test_a PASSED\ntests/b.py::test_b FAILED\ntests/c.py::test_c SKIPPED\n")
    assert report["observed_outcome_counts"]["PASSED"] == 1
    assert report["observed_outcome_counts"]["FAILED"] == 1
    assert report["observed_outcome_counts"]["SKIPPED"] == 1
