import subprocess, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[3]
RUNNER = ROOT / "scripts/ci/run_regression.py"

def test_include_rejects_non_test_python_file():
    result = subprocess.run([sys.executable, str(RUNNER), "--root", str(ROOT), "--start", "539", "--end", "539", "--include", "scripts/ci/run_regression.py", "--dry-run"], capture_output=True, text=True)
    assert result.returncode == 2
    assert "inside tests/" in result.stderr
