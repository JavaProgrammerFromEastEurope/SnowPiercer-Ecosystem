import importlib.util
import json
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[3]
SCRIPT = ROOT / "scripts/ci/run_regression.py"
spec = importlib.util.spec_from_file_location("run_regression_stage530", SCRIPT)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def test_timeout_is_reported_as_124_and_persisted(monkeypatch, tmp_path):
    tests = tmp_path / "tests" / "stage1"
    tests.mkdir(parents=True)
    (tests / "test_slow.py").write_text("def test_slow(): pass\n", encoding="utf-8")
    report_path = tmp_path / "evidence" / "regression.json"
    monkeypatch.setattr("sys.argv", [str(SCRIPT), "--root", str(tmp_path), "--start", "1", "--end", "1", "--timeout-seconds", "1", "--report", str(report_path)])
    monkeypatch.setattr(module.subprocess, "run", lambda *a, **k: (_ for _ in ()).throw(subprocess.TimeoutExpired(cmd="pytest", timeout=1, output=b"partial", stderr=b"late")))
    assert module.main() == 124
    report = json.loads(report_path.read_text(encoding="utf-8"))
    assert report["result"] == "TIMEOUT"
    assert report["exit_code"] == 124
    assert report["timeout_seconds"] == 1
    assert report["timeout_details"]["partial_stdout"] == "partial"
