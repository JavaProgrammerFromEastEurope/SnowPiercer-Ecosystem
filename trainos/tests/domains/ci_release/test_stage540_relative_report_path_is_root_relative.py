import json, subprocess, sys, tempfile
from pathlib import Path
ROOT = Path(__file__).resolve().parents[3]
RUNNER = ROOT / "scripts/ci/run_regression.py"

def test_relative_report_path_is_root_relative():
    with tempfile.TemporaryDirectory() as tmp:
        report = Path(tmp) / "evidence.json"
        result = subprocess.run([sys.executable, str(RUNNER), "--root", str(ROOT), "--start", "540", "--end", "540", "--dry-run", "--report", str(report)], capture_output=True, text=True)
        # Dry-run intentionally does not create execution evidence. Its selection must still be valid.
        assert result.returncode == 0, result.stderr
