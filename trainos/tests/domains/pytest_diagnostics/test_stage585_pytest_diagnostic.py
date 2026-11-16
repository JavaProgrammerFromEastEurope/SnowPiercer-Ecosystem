"""Stage 585: deterministic pytest diagnostic contract."""
import importlib.util
import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[3]
SCRIPT = ROOT / "scripts/ci/run_pytest_diagnostic.py"
spec = importlib.util.spec_from_file_location("trainos_diagnostic_stage585", SCRIPT)
module = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = module
spec.loader.exec_module(module)

def test_partial_log_is_not_declared_complete():
    assert module.build_report(command=["pytest"],result="INCOMPLETE_TIMEOUT",exit_code=124,elapsed_seconds=1,timeout_seconds=1,log_path=Path("log"),log_text="")["evidence_complete"] is False
