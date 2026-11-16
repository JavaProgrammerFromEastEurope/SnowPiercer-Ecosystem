import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_v62_stage_docs_and_ci_policy_exist_for_every_stage():
    migrated = list((ROOT / "tests/domains").rglob("test_stage*_*.py"))
    for number in range(528, 538):
        folder = ROOT / "tests" / f"stage{number}"
        assert (folder / f"test_stage{number}_release_contract.py").exists() or list(folder.glob(f"test_stage{number}_*.py")) or any(f.name.startswith(f"test_stage{number}_") for f in migrated), number
        assert (folder / f"STAGE{number}_IMPLEMENTATION.md").is_file(), number
        assert (folder / f"STAGE{number}_TESTS.md").is_file(), number
    runner = (ROOT / "scripts/ci/run_regression.py").read_text(encoding="utf-8")
    assert "--timeout-seconds" in runner
    assert "TIMEOUT" in runner
