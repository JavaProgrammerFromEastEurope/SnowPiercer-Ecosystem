"""Stage 581: deterministic pytest diagnostic contract."""
import importlib.util
import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[3]
SCRIPT = ROOT / "scripts/ci/run_pytest_diagnostic.py"
spec = importlib.util.spec_from_file_location("trainos_diagnostic_stage581", SCRIPT)
module = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = module
spec.loader.exec_module(module)

def test_summary_counts_are_parsed_separately():
    assert module.summarize_log("1 failed, 2 passed, 1 skipped in 0.31s")["terminal_summary_counts"] == {"PASSED":2,"FAILED":1,"ERROR":0,"SKIPPED":1,"XFAIL":0,"XPASS":0}
