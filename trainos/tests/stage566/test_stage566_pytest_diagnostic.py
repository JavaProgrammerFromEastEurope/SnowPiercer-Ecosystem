import importlib.util, json, subprocess, sys
from pathlib import Path
import pytest
ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts/ci/run_pytest_diagnostic.py"
spec = importlib.util.spec_from_file_location("run_pytest_diagnostic", SCRIPT)
module = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = module
spec.loader.exec_module(module)

def test_ci_matrix_includes_latest_stage_range():
    workflows = list((ROOT / ".github/workflows").glob("*.y*ml"))
    assert workflows
    text = "\n".join(path.read_text(encoding="utf-8") for path in workflows)
    assert "stages-558-567" in text
    assert "end: 577" in text
