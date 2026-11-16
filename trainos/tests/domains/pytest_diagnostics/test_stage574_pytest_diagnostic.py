"""Stage 574: pytest diagnostic progress and evidence contracts."""
import importlib.util
import json
import subprocess
import sys
from pathlib import Path
import pytest

ROOT = Path(__file__).resolve().parents[3]
SCRIPT = ROOT / "scripts/ci/run_pytest_diagnostic.py"
spec = importlib.util.spec_from_file_location("run_pytest_diagnostic_stage574", SCRIPT)
module = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = module
spec.loader.exec_module(module)

def test_timeout_report_remains_incomplete_and_preserves_exit_code():
    report = module.build_report(command=["pytest"], result="INCOMPLETE_TIMEOUT", exit_code=124,
        elapsed_seconds=2.5, timeout_seconds=2, log_path=Path("run.log"), log_text="")
    assert report["result"] == "INCOMPLETE_TIMEOUT"
    assert report["exit_code"] == 124
    assert report["elapsed_seconds"] == 2.5

