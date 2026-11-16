import json
from pathlib import Path

def test_ecosystem_inventory_has_explicit_modules_and_no_inferred_completion():
    root=Path(__file__).resolve().parents[3]
    register=json.loads((root/'SNOWPIERCER/ECOSYSTEM_WORK_REGISTER_V20.json').read_text())
    assert register['ecosystem_completion_percent'] is None
    ids={item['id'] for item in register['modules']}
    assert {'SP-SW','SP-AI','SP-RAIL','SP-ENERGY','SP-LIFE','SP-LOG','SP-SAFE','SP-ISLAND','SP-OPS'} <= ids
    assert register['payment_integration_status']=='NO_GO_NOT_VERIFIED'
    assert register['latest_release']['release']=='v61'
