"""Stage 571: pytest diagnostic progress and evidence contracts."""
import importlib.util
import json
import subprocess
import sys
from pathlib import Path
import pytest

ROOT = Path(__file__).resolve().parents[3]
SCRIPT = ROOT / "scripts/ci/run_pytest_diagnostic.py"
spec = importlib.util.spec_from_file_location("run_pytest_diagnostic_stage571", SCRIPT)
module = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = module
spec.loader.exec_module(module)

def test_tail_lines_is_bounded_and_keeps_latest_lines():
    report = module.summarize_log("one\ntwo\nthree\nfour\n", tail_lines=2)
    assert report["log_tail"] == ["three", "four"]

