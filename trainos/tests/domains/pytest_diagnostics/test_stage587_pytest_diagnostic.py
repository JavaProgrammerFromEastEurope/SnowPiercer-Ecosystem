"""Stage 587: deterministic pytest diagnostic contract."""
import importlib.util
import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[3]
SCRIPT = ROOT / "scripts/ci/run_pytest_diagnostic.py"
spec = importlib.util.spec_from_file_location("trainos_diagnostic_stage587", SCRIPT)
module = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = module
spec.loader.exec_module(module)

def test_workflow_includes_v67_shard():
    assert "stages-578-587" in (ROOT / ".github/workflows/trainos-tests.yml").read_text()
