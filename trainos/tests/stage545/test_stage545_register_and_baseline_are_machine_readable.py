import json
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]

def test_register_and_baseline_json_parse():
    register = json.loads((ROOT / "SNOWPIERCER/ECOSYSTEM_WORK_REGISTER_V22.json").read_text())
    baseline = json.loads((ROOT / "SNOWPIERCER/ECOSYSTEM_DELIVERABLE_BASELINE_V3.json").read_text())
    assert register["schema_version"] >= 1
    assert baseline["schema_version"] >= 1
