import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
EXPECTED = {"SP-SW", "SP-AI", "SP-RAIL", "SP-ENERGY", "SP-LIFE", "SP-LOG", "SP-SAFE", "SP-ISLAND", "SP-OPS"}


def test_inventory_ids_unique_and_each_module_has_deliverables_and_evidence():
    data = json.loads((ROOT / "SNOWPIERCER/ECOSYSTEM_DELIVERABLE_BASELINE_V2.json").read_text(encoding="utf-8"))
    modules = data["modules"]
    ids = [module["id"] for module in modules]
    assert set(ids) == EXPECTED
    assert len(ids) == len(set(ids))
    for module in modules:
        assert module["deliverables"]
        assert module["acceptance_evidence_required"]
        assert "status" in module
