from pathlib import Path
from scripts.ci.run_regression import select

def test_selector_is_sorted_and_unique():
    root = Path(__file__).resolve().parents[3]
    files = select(root, 538, 538)
    assert files == sorted(set(files))
    assert files
    assert all(name.startswith("tests/domains/ci_release/") and Path(name).name.startswith("test_") for name in files)
