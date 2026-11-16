"""Opt-in pytest lifecycle event journal; no warning filtering or GC mutation."""
import json
import os
from pathlib import Path
import time

_path = os.environ.get('TRAINOS_PYTEST_LIFECYCLE_LOG')

def _emit(event, **fields):
    if not _path:
        return
    record = {'event': event, 'monotonic_ns': time.monotonic_ns(), 'pid': os.getpid(), **fields}
    path = Path(_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('a', encoding='utf-8') as f:
        f.write(json.dumps(record, sort_keys=True) + '\n')
        f.flush()
        os.fsync(f.fileno())

def pytest_sessionstart(session):
    _emit('session_start')

def pytest_runtest_logstart(nodeid, location):
    _emit('test_start', nodeid=nodeid)

def pytest_runtest_logfinish(nodeid, location):
    _emit('test_finish', nodeid=nodeid)

def pytest_sessionfinish(session, exitstatus):
    _emit('session_finish', exitstatus=int(exitstatus))

def pytest_unconfigure(config):
    _emit('unconfigure')
