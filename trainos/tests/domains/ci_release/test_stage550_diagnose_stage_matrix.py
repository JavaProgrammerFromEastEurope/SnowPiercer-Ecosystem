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

def test_missing_expected_stages_are_reported(tmp_path):
    path = summary(tmp_path, "stage\tstatus\texit_code\tseconds\tlog\n550\tPASS\t0\t1\ta.log\n552\tPASS\t0\t1\tb.log\n")
    result = diagnose(path, expected_start=550, expected_end=552)
    assert result["missing_stages"] == [551]
    assert result["coverage_complete"] is False

