"""Stage 579: deterministic pytest diagnostic contract."""
import importlib.util
import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[3]
SCRIPT = ROOT / "scripts/ci/run_pytest_diagnostic.py"
spec = importlib.util.spec_from_file_location("trainos_diagnostic_stage579", SCRIPT)
module = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = module
spec.loader.exec_module(module)

def test_remaining_count_uses_collected_total():
    assert module.summarize_log("collected 4 items\ntests/stage1/test_a.py::test_a PASSED [ 25%]\n")["unobserved_or_incomplete_tests"] == 3
