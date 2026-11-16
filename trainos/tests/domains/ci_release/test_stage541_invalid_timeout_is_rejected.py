import subprocess, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[3]
RUNNER = ROOT / "scripts/ci/run_regression.py"

def test_zero_timeout_is_rejected_before_execution():
    result = subprocess.run([sys.executable, str(RUNNER), "--root", str(ROOT), "--start", "541", "--end", "541", "--timeout-seconds", "0", "--dry-run"], capture_output=True, text=True)
    assert result.returncode == 2
    assert "must be >= 1" in result.stderr
