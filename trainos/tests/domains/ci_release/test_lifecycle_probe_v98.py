"""Lifecycle probe event contract."""
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[3]

def test_lifecycle_events_are_balanced(tmp_path):
    test_file = tmp_path / 'test_ok.py'
    test_file.write_text('def test_ok(): assert True\n')
    events = tmp_path / 'events.jsonl'
    import os
    env = {**os.environ, 'TRAINOS_PYTEST_LIFECYCLE_LOG': str(events)}
    p = subprocess.run([sys.executable, '-m', 'pytest', '-q', '-p', 'scripts.ci.pytest_lifecycle_probe', str(test_file)], cwd=ROOT, env=env, capture_output=True, text=True, timeout=20)
    assert p.returncode == 0, p.stdout + p.stderr
    records = [json.loads(line) for line in events.read_text().splitlines()]
    assert [r['event'] for r in records] == ['session_start','test_start','test_finish','session_finish','unconfigure']
    assert records[-2]['exitstatus'] == 0
