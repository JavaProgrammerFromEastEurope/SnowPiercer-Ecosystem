"""Stage 570: pytest diagnostic progress and evidence contracts."""
import importlib.util
import json
import subprocess
import sys
from pathlib import Path
import pytest

ROOT = Path(__file__).resolve().parents[3]
SCRIPT = ROOT / "scripts/ci/run_pytest_diagnostic.py"
spec = importlib.util.spec_from_file_location("run_pytest_diagnostic_stage570", SCRIPT)
module = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = module
spec.loader.exec_module(module)

def test_outcome_counts_are_exact_and_initialized():
    report = module.summarize_log("tests/stage1/test_a.py::test_a PASSED [ 1%]\ntests/stage1/test_b.py::test_b FAILED [ 2%]\n")
    assert report["observed_outcome_counts"]["PASSED"] == 1
    assert report["observed_outcome_counts"]["FAILED"] == 1
    assert report["observed_outcome_counts"]["ERROR"] == 0

