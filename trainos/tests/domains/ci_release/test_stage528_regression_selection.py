import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
SCRIPT = ROOT / "scripts/ci/run_regression.py"
spec = importlib.util.spec_from_file_location("run_regression_stage528", SCRIPT)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def test_selection_is_inclusive_sorted_unique_and_ignores_non_test_files(tmp_path):
    for directory, names in {
        "stage10": ["test_z.py", "test_a.py", "notes.md", "helper.py"],
        "stage11": ["test_mid.py"],
        "stage12": ["test_end.py"],
    }.items():
        folder = tmp_path / "tests" / directory
        folder.mkdir(parents=True)
        for name in names:
            (folder / name).write_text("# fixture\n", encoding="utf-8")
    selected = module.select(tmp_path, 10, 12)
    assert selected == [
        "tests/stage10/test_a.py",
        "tests/stage10/test_z.py",
        "tests/stage11/test_mid.py",
        "tests/stage12/test_end.py",
    ]
    assert selected == sorted(set(selected))
