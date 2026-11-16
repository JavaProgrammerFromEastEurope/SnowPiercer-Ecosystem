"""Stage 568: pytest diagnostic progress and evidence contracts."""
import importlib.util
import json
import subprocess
import sys
from pathlib import Path
import pytest

ROOT = Path(__file__).resolve().parents[3]
SCRIPT = ROOT / "scripts/ci/run_pytest_diagnostic.py"
spec = importlib.util.spec_from_file_location("run_pytest_diagnostic_stage568", SCRIPT)
module = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = module
spec.loader.exec_module(module)

def test_collection_count_is_read_in_both_pytest_summary_orders():
    first = module.summarize_log("1386 tests collected\n")
    second = module.summarize_log("collected 42 items\n")
    assert first["collected_tests"] == 1386
    assert second["collected_tests"] == 42

