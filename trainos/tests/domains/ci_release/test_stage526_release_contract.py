import importlib.util
from pathlib import Path

def test_regression_selector_is_sorted_unique_and_range_bounded():
    root=Path(__file__).resolve().parents[3]
    module_path=root/'scripts/ci/run_regression.py'
    spec=importlib.util.spec_from_file_location('trainos_run_regression',module_path)
    module=importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    selected=module.select(root,518,526)
    assert selected==sorted(set(selected))
    assert len(selected)==9
    assert all(item.startswith('tests/domains/ci_release/') for item in selected)
    assert all(Path(root / item).is_file() for item in selected)
