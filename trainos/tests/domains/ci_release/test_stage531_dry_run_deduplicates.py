import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
SCRIPT = ROOT / "scripts/ci/run_regression.py"
spec = importlib.util.spec_from_file_location("run_regression_stage531", SCRIPT)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def test_dry_run_reports_deterministic_selection_without_running_pytest(monkeypatch, tmp_path, capsys):
    folder = tmp_path / "tests" / "stage1"
    folder.mkdir(parents=True)
    test_file = folder / "test_a.py"
    test_file.write_text("def test_ok(): pass\n", encoding="utf-8")
    monkeypatch.setattr("sys.argv", [str(SCRIPT), "--root", str(tmp_path), "--start", "1", "--end", "1", "--include", "tests/stage1/test_a.py", "--dry-run"])
    assert module.main() == 0
    report = json.loads(capsys.readouterr().out)
    assert report["test_file_count"] == 1
    assert report["files"] == ["tests/stage1/test_a.py"]
