"""Stage 577: pytest diagnostic progress and evidence contracts."""
import importlib.util
import json
import subprocess
import sys
from pathlib import Path
import pytest

ROOT = Path(__file__).resolve().parents[3]
SCRIPT = ROOT / "scripts/ci/run_pytest_diagnostic.py"
spec = importlib.util.spec_from_file_location("run_pytest_diagnostic_stage577", SCRIPT)
module = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = module
spec.loader.exec_module(module)

def test_invalid_tail_lines_argument_is_documented_in_cli():
    completed = subprocess.run([sys.executable, str(SCRIPT), "--help"], capture_output=True, text=True, check=True)
    assert "--tail-lines" in completed.stdout

