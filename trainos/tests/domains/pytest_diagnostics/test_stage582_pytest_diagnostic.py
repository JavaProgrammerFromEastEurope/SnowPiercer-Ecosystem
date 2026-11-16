"""Stage 582: deterministic pytest diagnostic contract."""
import importlib.util
import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[3]
SCRIPT = ROOT / "scripts/ci/run_pytest_diagnostic.py"
spec = importlib.util.spec_from_file_location("trainos_diagnostic_stage582", SCRIPT)
module = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = module
spec.loader.exec_module(module)

def test_absent_summary_remains_unknown():
    assert module.summarize_log("tests/stage1/test_a.py::test_a PASSED [100%]")["terminal_summary_counts"] is None
