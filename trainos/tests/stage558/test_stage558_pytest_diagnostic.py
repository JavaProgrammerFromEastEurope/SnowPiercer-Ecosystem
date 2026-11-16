import importlib.util, json, subprocess, sys
from pathlib import Path
import pytest
ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts/ci/run_pytest_diagnostic.py"
spec = importlib.util.spec_from_file_location("run_pytest_diagnostic", SCRIPT)
module = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = module
spec.loader.exec_module(module)

def test_progress_parser_records_last_observed_test():
    report = module.summarize_log("tests/stage1/test_a.py::test_one PASSED [ 10%]\ntests/stage2/test_b.py::test_two [ 20%]\n")
    assert report["last_observed_test"] == "tests/stage2/test_b.py::test_two"
    assert report["last_completed_test"] == "tests/stage1/test_a.py::test_one"
    durations = module.summarize_log("0.02s call tests/stage9/test_slow.py::test_slow")
    assert durations["last_observed_test"] is None
