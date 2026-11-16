"""Pure standard-library checks for conceptual Island artifacts."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

def load(relative):
    with (ROOT / relative).open(encoding="utf-8") as stream:
        return json.load(stream)

def validate():
    requirements = load("models/requirements.json")["requirements"]
    assets = load("models/assets.json")
    contracts = load("contracts/interfaces.json")["contracts"]
    hazards = load("safety/hazards.json")["hazards"]
    readiness = load("models/readiness.json")
    ids = [r["id"] for r in requirements]
    assert len(ids) == len(set(ids)) and all(r["verification"] for r in requirements)
    asset_ids = [a["id"] for a in assets["assets"]]
    assert len(asset_ids) == len(set(asset_ids))
    assert all(d["from"] in asset_ids and d["on"] in asset_ids for d in assets["dependencies"])
    assert {c["peer"] for c in contracts[:7]} == {"TrainOS", "AI-Cognition", "Rail-Systems", "Energy", "Life-Support", "Logistics", "Security"}
    assert all(c["safety_boundary"] == "no actuation authorized" for c in contracts[:7])
    assert all(h["verification"] in ("pending", "pending independent E2E") and h["residual_risk"] == "unassessed" for h in hazards)
    assert readiness["physical_deployment"] == "BLOCKED/NO-GO"
    assert not any(readiness[k] for k in ("site_selected", "engineering_approved", "permits_obtained", "safety_case_accepted", "integration_tested"))
    return {"requirements":len(requirements),"assets":len(asset_ids),"contracts":len(contracts),"hazards":len(hazards),"physical_deployment":readiness["physical_deployment"]}
