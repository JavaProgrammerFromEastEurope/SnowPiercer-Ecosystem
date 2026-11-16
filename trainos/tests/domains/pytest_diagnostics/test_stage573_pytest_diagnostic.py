"""Stage 573: pytest diagnostic progress and evidence contracts."""
import importlib.util
import json
import subprocess
import sys
from pathlib import Path
import pytest

ROOT = Path(__file__).resolve().parents[3]
SCRIPT = ROOT / "scripts/ci/run_pytest_diagnostic.py"
spec = importlib.util.spec_from_file_location("run_pytest_diagnostic_stage573", SCRIPT)
module = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = module
spec.loader.exec_module(module)

def test_atomic_json_replaces_target_with_valid_json(tmp_path):
    target = tmp_path / "report.json"
    target.write_text("stale", encoding="utf-8")
    module.atomic_json(target, {"result": "PASS", "count": 2})
    assert json.loads(target.read_text(encoding="utf-8")) == {"result": "PASS", "count": 2}
    assert not target.with_name("report.json.tmp").exists()

