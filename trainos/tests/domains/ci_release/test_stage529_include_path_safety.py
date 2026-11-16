import importlib.util
from pathlib import Path
import pytest

ROOT = Path(__file__).resolve().parents[3]
SCRIPT = ROOT / "scripts/ci/run_regression.py"
spec = importlib.util.spec_from_file_location("run_regression_stage529", SCRIPT)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def test_explicit_include_cannot_escape_project_root(tmp_path, monkeypatch):
    inside = tmp_path / "test_inside.py"
    inside.write_text("def test_ok(): pass\n", encoding="utf-8")
    outside = tmp_path.parent / "outside_test.py"
    outside.write_text("def test_outside(): pass\n", encoding="utf-8")
    monkeypatch.setattr("sys.argv", [str(SCRIPT), "--root", str(tmp_path), "--start", "1", "--end", "1", "--include", str(outside)])
    with pytest.raises(SystemExit) as caught:
        module.main()
    assert caught.value.code == 2
    outside.unlink(missing_ok=True)
