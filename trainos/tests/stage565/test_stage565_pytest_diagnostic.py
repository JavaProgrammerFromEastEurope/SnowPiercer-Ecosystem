import importlib.util, json, subprocess, sys
from pathlib import Path
import pytest
ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts/ci/run_pytest_diagnostic.py"
spec = importlib.util.spec_from_file_location("run_pytest_diagnostic", SCRIPT)
module = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = module
spec.loader.exec_module(module)

def test_cli_help_is_available():
    result = subprocess.run([sys.executable, str(SCRIPT), "--help"], capture_output=True, text=True, timeout=5)
    assert result.returncode == 0
    assert "--timeout-seconds" in result.stdout
    assert "--report" in result.stdout
