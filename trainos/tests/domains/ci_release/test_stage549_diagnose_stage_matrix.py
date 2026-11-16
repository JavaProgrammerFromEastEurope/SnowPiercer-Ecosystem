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

def test_slowest_stages_are_ranked_deterministically(tmp_path):
    path = summary(tmp_path, "stage\tstatus\texit_code\tseconds\tlog\n552\tPASS\t0\t8\ta.log\n551\tPASS\t0\t8\tb.log\n550\tPASS\t0\t1\tc.log\n")
    result = diagnose(path, top=2, slow_seconds=5)
    assert [row["stage"] for row in result["slowest_stages"]] == [551, 552]
    assert [row["stage"] for row in result["slow_stages"]] == [551, 552]

