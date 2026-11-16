import importlib.util, json, subprocess, sys
from pathlib import Path
import pytest
ROOT = Path(__file__).resolve().parents[3]
SCRIPT = ROOT / "scripts/ci/diagnose_stage_matrix.py"
spec = importlib.util.spec_from_file_location("diagnose_stage_matrix", SCRIPT)
module = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = module
spec.loader.exec_module(module)
diagnose = module.diagnose
DiagnosticError = module.DiagnosticError
def summary(tmp_path, contents):
    path = tmp_path / "summary.tsv"
    path.write_text(contents, encoding="utf-8")
    return path

def test_require_complete_returns_nonzero_for_nonpass(tmp_path):
    path = summary(tmp_path, "stage\tstatus\texit_code\tseconds\tlog\n551\tTIMEOUT\t124\t4\ta.log\n")
    script = ROOT / "scripts/ci/diagnose_stage_matrix.py"
    result = subprocess.run([sys.executable, str(script), str(path), "--require-complete"], capture_output=True, text=True)
    assert result.returncode == 1
    assert "TIMEOUT: 1" in result.stdout

