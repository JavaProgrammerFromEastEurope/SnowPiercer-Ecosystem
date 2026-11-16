"""Contract for v85 functional migration and regression selection."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]

def test_v85_migration_paths_and_ownership():
    data = json.loads((ROOT / "AUDIT/FUNCTIONAL_STAGE_PHYSICAL_MIGRATION_V85.json").read_text())
    assignments = json.loads((ROOT / "tests/kernel_runner/legacy_domain_assignments.json").read_text())["assignments"]
    assert len(data["moved"]) == 10
    for old, new in data["moved"].items():
        assert not (ROOT / old).exists()
        assert (ROOT / new).is_file()
        assert old not in assignments
        assert new.startswith("tests/domains/recovery/")

def test_v85_recovery_discovery_is_unique():
    from tests.kernel_runner.config import discover_stages
    stages = discover_stages()
    recovery = next(stage for stage in stages if stage.name == "recovery")
    assert len(recovery.tests) == len(set(recovery.tests))
    assert any("tests/domains/recovery" in path for path in recovery.tests)
