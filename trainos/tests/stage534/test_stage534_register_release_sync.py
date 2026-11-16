import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_register_versions_agree_on_v62_and_completion_remains_unassessed():
    register = json.loads((ROOT / "SNOWPIERCER/ECOSYSTEM_WORK_REGISTER_V21.json").read_text(encoding="utf-8"))
    assert register["register_version"] == 21
    assert register["latest_release"]["release"] == "v62"
    assert register["latest_release"]["stage_range"] == {"start": 528, "end": 537, "count": 10}
    assert register["ecosystem_completion_percent"] is None
    markdown = (ROOT / "SNOWPIERCER/ECOSYSTEM_WORK_REGISTER_V21.md").read_text(encoding="utf-8")
    assert "TrainOS v62" in markdown
    assert "NO-GO" in markdown
