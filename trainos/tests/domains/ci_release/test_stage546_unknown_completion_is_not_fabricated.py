import json
from pathlib import Path
ROOT = Path(__file__).resolve().parents[3]

def test_ecosystem_completion_remains_unknown_without_approved_measurement():
    register = json.loads((ROOT / "SNOWPIERCER/ECOSYSTEM_WORK_REGISTER_V22.json").read_text())
    assert register.get("ecosystem_completion_percent") is None
