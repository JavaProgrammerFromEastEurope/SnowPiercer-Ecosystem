"""Stage 575: pytest diagnostic progress and evidence contracts."""
import importlib.util
import json
import subprocess
import sys
from pathlib import Path
import pytest

ROOT = Path(__file__).resolve().parents[3]
SCRIPT = ROOT / "scripts/ci/run_pytest_diagnostic.py"
spec = importlib.util.spec_from_file_location("run_pytest_diagnostic_stage575", SCRIPT)
module = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = module
spec.loader.exec_module(module)

def test_workflow_range_and_diagnostic_tail_option_are_covered():
    workflow = (ROOT / ".github/workflows/trainos-tests.yml").read_text(encoding="utf-8")
    script = SCRIPT.read_text(encoding="utf-8")
    assert "stages-568-577" in workflow
    assert "end: 577" in workflow
    assert "--tail-lines" in script

