"""Stage 583: deterministic pytest diagnostic contract."""
import importlib.util
import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[3]
SCRIPT = ROOT / "scripts/ci/run_pytest_diagnostic.py"
spec = importlib.util.spec_from_file_location("trainos_diagnostic_stage583", SCRIPT)
module = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = module
spec.loader.exec_module(module)

def test_summary_does_not_inflate_observed_completed():
    assert module.summarize_log("4 passed in 0.20s")["observed_completed_tests"] == 0
