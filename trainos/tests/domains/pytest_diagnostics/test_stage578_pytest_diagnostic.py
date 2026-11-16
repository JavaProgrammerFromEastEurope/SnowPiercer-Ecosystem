"""Stage 578: deterministic pytest diagnostic contract."""
import importlib.util
import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[3]
SCRIPT = ROOT / "scripts/ci/run_pytest_diagnostic.py"
spec = importlib.util.spec_from_file_location("trainos_diagnostic_stage578", SCRIPT)
module = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = module
spec.loader.exec_module(module)

def test_completed_count_is_derived_from_node_lines():
    assert module.summarize_log("tests/stage1/test_a.py::test_a PASSED [ 50%]\ntests/stage1/test_b.py::test_b FAILED [100%]\n")["observed_completed_tests"] == 2
