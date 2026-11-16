import csv
from pathlib import Path
import pytest
from scripts.ci.summarize_stage_results import summarize, SummaryError

def test_duplicate_stage_rows_are_rejected(tmp_path):
    path = tmp_path / "summary.tsv"
    with path.open("w", newline="") as f:
        w = csv.writer(f, delimiter="\t"); w.writerow(["stage","status","exit_code","seconds","log"]); w.writerow([1,"PASS",0,1,"stage-1.log"]); w.writerow([1,"PASS",0,1,"stage-1b.log"])
    with pytest.raises(SummaryError, match="duplicate stage"):
        summarize(path)
