import unittest
from island.validation import load, validate

class Stage001Tests(unittest.TestCase):
    def test_requirement_traceability(self):
        self.assertEqual(len([r for r in load("models/requirements.json")["requirements"] if not r["id"].startswith(("ISLAND-GEO2-", "ISLAND-GEO-004-", "ISLAND-GEO-005-", "ISLAND-GEO-006-", "ISLAND-GEO-007-", "ISLAND-GEO-008-", "ISLAND-GEO-007-", "ISLAND-GEO-008-", "ISLAND-GEO-009-", "ISLAND-GEO-010-", "ISLAND-GEO-011-", "ISLAND-GEO-012-", "ISLAND-GEO-013-", "ISLAND-GEO-014-", "ISLAND-GEO-015-", "ISLAND-GEO-016-", "ISLAND-GEO-017-", "ISLAND-GEO-018-", "ISLAND-GEO-020-", "ISLAND-GEO-021-", "ISLAND-GEO-022-")) and r["id"] not in {"ISLAND-GEO-002","ISLAND-GEO-003","ISLAND-GEO-004","ISLAND-GEO-005","ISLAND-GEO-006","ISLAND-GEO-007","ISLAND-GEO-008"}]),14)
    def test_asset_identifiers(self):
        self.assertEqual(validate()["assets"],8)
    def test_interface_coverage(self):
        self.assertGreaterEqual(validate()["contracts"],7)
    def test_hazard_structure(self):
        self.assertEqual(len([h for h in load("safety/hazards.json")["hazards"] if not h["id"].startswith(("ISLAND-GEO-HZ-", "H-GEO2-", "ISLAND-HAZ-GEO-004-", "ISLAND-HAZ-GEO-005-", "ISLAND-HAZ-GEO-006-", "ISLAND-HAZ-GEO-007-", "H-GEO-008-", "ISLAND-HAZ-GEO-007-", "H-GEO-008-", "H-GEO-009-", "H-GEO-010-", "H-GEO-011-", "H-GEO-012-", "H-GEO-013-", "H-GEO-014-", "H-GEO-015-", "H-GEO-016-", "H-GEO-017-", "H-GEO-018-", "H-GEO-020-", "H-GEO-021-", "H-GEO-022-"))]),6)
    def test_readiness_gate(self):
        self.assertEqual(validate()["physical_deployment"],"BLOCKED/NO-GO")
    def test_dependencies_resolve(self):
        data=load("models/assets.json")
        ids={x["id"] for x in data["assets"]}
        self.assertTrue(all(x["on"] in ids and x["from"] in ids for x in data["dependencies"]))
    def test_no_contract_actuation(self):
        self.assertTrue(all(c["safety_boundary"] == "no actuation authorized" for c in load("contracts/interfaces.json")["contracts"][:7]))
    def test_hazards_unverified(self):
        self.assertTrue(all(h["verification"] in ("pending", "pending independent E2E") for h in load("safety/hazards.json")["hazards"]))
    def test_no_approval(self):
        self.assertFalse(load("models/readiness.json")["engineering_approved"])
    def test_requirements_unique(self):
        r=load("models/requirements.json")["requirements"]
        self.assertEqual(len(r),len({x["id"] for x in r}))

if __name__ == "__main__":
    unittest.main()
