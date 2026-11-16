import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def test_inventory_does_not_claim_physical_readiness_or_unverified_payments():
    data = json.loads((ROOT / "SNOWPIERCER/ECOSYSTEM_DELIVERABLE_BASELINE_V2.json").read_text(encoding="utf-8"))
    assert data["policy"]["software_tests_prove_physical_readiness"] is False
    assert data["policy"]["completion_percent"] == "not calculated until scope, weights, acceptance criteria, and evidence are approved"
    by_id = {module["id"]: module for module in data["modules"]}
    assert any("sandbox" in gate.lower() for gate in by_id["SP-SW"]["critical_gates"])
    assert by_id["SP-RAIL"]["status"] != "READY"
    assert by_id["SP-ENERGY"]["status"] != "READY"
