import json, subprocess, sys, tempfile
from pathlib import Path
ROOT = Path(__file__).resolve().parents[3]
RUNNER = ROOT / "scripts/ci/run_regression.py"

def test_execution_report_is_valid_json_and_atomic_write_leaves_no_temp():
    with tempfile.TemporaryDirectory() as tmp:
        report = Path(tmp) / "report.json"
        result = subprocess.run([sys.executable, str(RUNNER), "--root", str(ROOT), "--start", "539", "--end", "539", "--report", str(report), "--timeout-seconds", "30"], capture_output=True, text=True, timeout=45)
        assert result.returncode == 0, result.stdout + result.stderr
        data = json.loads(report.read_text())
        assert data["result"] == "PASS" and data["exit_code"] == 0
        assert not report.with_name(report.name + ".tmp").exists()
