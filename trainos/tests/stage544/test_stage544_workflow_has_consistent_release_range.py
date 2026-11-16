from pathlib import Path

def test_workflow_range_and_evidence_filename_are_synchronized():
    root = Path(__file__).resolve().parents[2]
    workflow = (root / ".github/workflows/trainos-tests.yml").read_text()
    assert "stages-538-547" in workflow
    assert "stages-548-557" in workflow
    assert "--end 577" in workflow or "--end 587" in workflow
    assert "regression-170-577.json" in workflow or "regression-170-587.json" in workflow
    assert "stages-558-567" in workflow

