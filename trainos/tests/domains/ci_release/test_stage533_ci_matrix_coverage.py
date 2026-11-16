from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[3]


def test_ci_matrix_covers_every_stage_from_one_through_587_without_gaps():
    workflow = (ROOT / ".github/workflows/trainos-tests.yml").read_text(encoding="utf-8")
    pairs = [(int(a), int(b)) for a, b in re.findall(r"^\s+start: (\d+)\n\s+end: (\d+)$", workflow, re.M)]
    assert pairs, "workflow stage matrix is missing"
    covered = set()
    for start, end in pairs:
        assert start <= end
        stages = set(range(start, end + 1))
        assert not (covered & stages), f"overlapping stage ranges: {start}-{end}"
        covered |= stages
    assert covered == set(range(1, 588))
