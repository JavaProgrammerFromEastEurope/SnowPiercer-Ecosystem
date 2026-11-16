"""Stage 576: pytest diagnostic progress and evidence contracts."""
import importlib.util
import json
import subprocess
import sys
from pathlib import Path
import pytest

ROOT = Path(__file__).resolve().parents[3]
SCRIPT = ROOT / "scripts/ci/run_pytest_diagnostic.py"
spec = importlib.util.spec_from_file_location("run_pytest_diagnostic_stage576", SCRIPT)
module = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = module
spec.loader.exec_module(module)

def test_report_contains_collected_count_even_without_test_lines():
    report = module.build_report(command=["pytest"], result="FAIL", exit_code=1,
        elapsed_seconds=1, timeout_seconds=10, log_path=Path("run.log"),
        log_text="collected 7 items\n")
    assert report["progress"]["collected_tests"] == 7

