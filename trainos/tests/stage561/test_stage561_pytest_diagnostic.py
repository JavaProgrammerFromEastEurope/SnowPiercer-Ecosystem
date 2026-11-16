import importlib.util, json, subprocess, sys
from pathlib import Path
import pytest
ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts/ci/run_pytest_diagnostic.py"
spec = importlib.util.spec_from_file_location("run_pytest_diagnostic", SCRIPT)
module = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = module
spec.loader.exec_module(module)

def test_progress_parser_rejects_nonpositive_tail_limit():
    with pytest.raises(ValueError, match="tail_lines must be >= 1"):
        module.summarize_log("", tail_lines=0)
