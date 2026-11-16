"""Stage 569: pytest diagnostic progress and evidence contracts."""
import importlib.util
import json
import subprocess
import sys
from pathlib import Path
import pytest

ROOT = Path(__file__).resolve().parents[3]
SCRIPT = ROOT / "scripts/ci/run_pytest_diagnostic.py"
spec = importlib.util.spec_from_file_location("run_pytest_diagnostic_stage569", SCRIPT)
module = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = module
spec.loader.exec_module(module)

def test_progress_distinguishes_observed_from_completed_test():
    report = module.summarize_log("tests/stage1/test_a.py::test_a PASSED [ 1%]\ntests/stage2/test_b.py::test_b <- /tmp/source.py PASSED [ 2%]\ntests/stage3/test_c.py::test_c ")
    assert report["last_completed_test"] == "tests/stage2/test_b.py::test_b"
    assert report["last_observed_test"] == "tests/stage3/test_c.py::test_c"
    assert report["observed_outcome_counts"]["PASSED"] == 2

