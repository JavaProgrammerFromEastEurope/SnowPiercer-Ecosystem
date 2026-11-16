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

def test_diagnostic_buckets_and_rows_are_sorted(tmp_path):
    path = summary(tmp_path, "stage\tstatus\texit_code\tseconds\tlog\n557\tTIMEOUT\t124\t7\tz.log\n555\tFAIL\t1\t3\tf.log\n556\tPASS\t0\t1\tp.log\n")
    result = diagnose(path)
    assert [row["stage"] for row in result["stages"]] == [555, 556, 557]
    assert [row["stage"] for row in result["failed_stages"]] == [555]
    assert [row["stage"] for row in result["timed_out_stages"]] == [557]

