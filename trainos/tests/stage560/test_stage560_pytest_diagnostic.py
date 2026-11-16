import importlib.util, json, subprocess, sys
from pathlib import Path
import pytest
ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts/ci/run_pytest_diagnostic.py"
spec = importlib.util.spec_from_file_location("run_pytest_diagnostic", SCRIPT)
module = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = module
spec.loader.exec_module(module)

def test_log_tail_is_bounded_and_keeps_latest_lines():
    report = module.summarize_log("\n".join(f"line {i}" for i in range(100)), tail_lines=5)
    assert report["log_tail"] == [f"line {i}" for i in range(95, 100)]
