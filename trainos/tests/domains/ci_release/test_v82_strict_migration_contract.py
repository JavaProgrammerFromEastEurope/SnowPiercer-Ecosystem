from pathlib import Path
import json

ROOT = Path(__file__).resolve().parents[3]

def test_v82_migrated_modules_have_single_domain_owner():
    registry = json.loads((ROOT/'tests/kernel_runner/legacy_domain_assignments.json').read_text())['assignments']
    for number in range(408,418):
        name = f'test_stage{number}_schema_recovery.py'
        assert (ROOT/'tests/domains/recovery'/name).is_file()
        assert not (ROOT/f'tests/stage{number}'/name).exists()
        assert f'tests/stage{number}/{name}' not in registry

def test_v82_explicit_asyncio_fixture_scope():
    assert 'asyncio_default_fixture_loop_scope = function' in (ROOT/'pytest.ini').read_text()
