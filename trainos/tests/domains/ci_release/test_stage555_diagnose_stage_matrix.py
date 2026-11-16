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

def test_json_output_is_valid_and_has_no_temp_residue(tmp_path):
    path = summary(tmp_path, "stage\tstatus\texit_code\tseconds\tlog\n555\tPASS\t0\t1\ta.log\n")
    output = tmp_path / "nested" / "diagnostics.json"
    script = ROOT / "scripts/ci/diagnose_stage_matrix.py"
    result = subprocess.run([sys.executable, str(script), str(path), "--json", str(output)], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    assert json.loads(output.read_text())["counts"]["PASS"] == 1
    assert not output.with_name(output.name + ".tmp").exists()

