import importlib.util, json, subprocess, sys
from pathlib import Path
import pytest
ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts/ci/run_pytest_diagnostic.py"
spec = importlib.util.spec_from_file_location("run_pytest_diagnostic", SCRIPT)
module = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = module
spec.loader.exec_module(module)

def test_atomic_json_writer_emits_valid_report(tmp_path):
    path = tmp_path / "nested" / "report.json"
    module.atomic_json(path, {"result": "INCOMPLETE_TIMEOUT", "count": 2})
    assert json.loads(path.read_text()) == {"count": 2, "result": "INCOMPLETE_TIMEOUT"}
    assert not path.with_name(path.name + ".tmp").exists()
