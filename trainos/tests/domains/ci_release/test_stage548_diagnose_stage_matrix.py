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

def test_valid_matrix_counts_statuses(tmp_path):
    path = summary(tmp_path, "stage\tstatus\texit_code\tseconds\tlog\n548\tPASS\t0\t2\ta.log\n549\tFAIL\t1\t5\tb.log\n550\tTIMEOUT\t124\t9\tc.log\n")
    result = diagnose(path)
    assert result["counts"] == {"PASS": 1, "FAIL": 1, "TIMEOUT": 1}
    assert result["successful"] is False

