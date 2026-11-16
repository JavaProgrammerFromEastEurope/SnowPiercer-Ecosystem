"""Opt-in sqlite3 connection allocation/GC provenance at pytest test boundaries.

No warning filters, automatic connection closure, or production changes.
"""
from __future__ import annotations
import gc
import json
import os
from pathlib import Path
import sqlite3
import time
import traceback
import tracemalloc
import weakref

_original = sqlite3.connect
_records = {}
_events = []
_counter = 0

class OwnedConnection(sqlite3.Connection):
    def close(self):
        entry = _records.get(id(self))
        try:
            return super().close()
        finally:
            if entry is not None:
                entry['explicit_close'] = True

def _connect(*args, **kwargs):
    global _counter
    kwargs.setdefault('factory', OwnedConnection)
    conn = _original(*args, **kwargs)
    if isinstance(conn, OwnedConnection):
        _counter += 1
        key = id(conn)
        record = {'sequence': _counter, 'database': str(args[0] if args else kwargs.get('database')),
                  'allocation_stack': traceback.format_stack(limit=22), 'explicit_close': False,
                  'created_at_test': _current[0], 'collected': False}
        _records[key] = record
        weakref.finalize(conn, lambda r=record: r.update(collected=True))
    return conn

_current = ['collection']

class Probe:
    def pytest_runtest_setup(self, item):
        _current[0] = item.nodeid
    def pytest_runtest_teardown(self, item, nextitem):
        _current[0] = item.nodeid
        collected = gc.collect()
        leaked = [r['sequence'] for r in _records.values() if r['collected'] and not r['explicit_close']]
        _events.append({'test': item.nodeid, 'gc_collected': collected, 'unclosed_collected': leaked,
                        'tracked': len(_records), 'time': time.monotonic()})
    def pytest_sessionfinish(self, session, exitstatus):
        _current[0] = 'sessionfinish'
        gc.collect()
        output = Path(os.environ.get('TRAINOS_SQLITE_OWNER_REPORT', 'AUDIT/sqlite_owner_boundaries.json'))
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps({'schema': 'trainos.sqlite-owners.v100', 'exitstatus': int(exitstatus),
                          'records': list(_records.values()), 'boundaries': _events}, indent=2))

def main(argv=None):
    import sys
    import pytest
    tracemalloc.start(15)
    sqlite3.connect = _connect
    return int(pytest.main(sys.argv[1:] if argv is None else argv, plugins=[Probe()]))

if __name__ == '__main__':
    raise SystemExit(main())
