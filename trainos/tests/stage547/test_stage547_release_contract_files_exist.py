import json
import os
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]

def test_v63_release_contract_artifacts_exist():
    migrated = list((ROOT / "tests/domains").rglob("test_stage*_*.py"))
    for n in range(538, 548):
        folder = ROOT / "tests" / f"stage{n}"
        assert list(folder.glob("test_*.py")) or any(f.name.startswith(f"test_stage{n}_") for f in migrated), n
        assert (folder / f"STAGE{n}_IMPLEMENTATION.md").is_file(), n
        assert (folder / f"STAGE{n}_TESTS.md").is_file(), n
    assert (ROOT / "scripts/ci/run_regression.py").is_file()
    assert os.access(ROOT / "scripts/ci/run_stage_matrix.sh", os.X_OK)
