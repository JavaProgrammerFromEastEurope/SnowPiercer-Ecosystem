import importlib.util
from pathlib import Path
import pytest

ROOT = Path(__file__).resolve().parents[3]
SCRIPT = ROOT / "scripts/ci/run_regression.py"
spec = importlib.util.spec_from_file_location("run_regression_stage532", SCRIPT)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def test_nonpositive_timeout_is_rejected(monkeypatch):
    monkeypatch.setattr("sys.argv", [str(SCRIPT), "--start", "1", "--end", "1", "--timeout-seconds", "0"])
    with pytest.raises(SystemExit) as caught:
        module.main()
    assert caught.value.code == 2
