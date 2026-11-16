"""Opt-in per-test SQLite owner/GC probe; never suppresses warnings.

Enable with `-p scripts.ci.sqlite_owner_lifecycle_v101` and set
TRAINOS_SQLITE_OWNER_REPORT to a JSONL output path. Not production code.
"""
from __future__ import annotations
import gc
import json
import os
from pathlib import Path
import sqlite3
import traceback
import tracemalloc
import weakref

_original_connect = sqlite3.connect
_records = {}
_active_test = None

class OwnedConnection(sqlite3.Connection):
    def close(self):
        entry = _records.get(id(self))
        try:
            return super().close()
        finally:
            if entry is not None:
                entry['explicitly_closed'] = True

def _connect(*args, **kwargs):
    kwargs.setdefault('factory', OwnedConnection)
    con = _original_connect(*args, **kwargs)
    if isinstance(con, OwnedConnection):
        ident = id(con)
        entry = {'test': _active_test, 'database': str(args[0] if args else kwargs.get('database')),
                 'stack': traceback.format_stack(limit=12), 'explicitly_closed': False,
                 'collected': False}
        _records[ident] = entry
        weakref.finalize(con, entry.__setitem__, 'collected', True)
    return con

def pytest_configure(config):
    tracemalloc.start(10)
    sqlite3.connect = _connect

def pytest_runtest_setup(item):
    global _active_test
    _active_test = item.nodeid

def pytest_runtest_teardown(item, nextitem):
    global _active_test
    gc.collect()
    path = os.environ.get('TRAINOS_SQLITE_OWNER_REPORT')
    if path:
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        with p.open('a', encoding='utf8') as out:
            for entry in _records.values():
                if entry['test'] == item.nodeid and not entry.get('reported'):
                    out.write(json.dumps(entry) + '\n')
                    entry['reported'] = True
    _active_test = None

def pytest_unconfigure(config):
    sqlite3.connect = _original_connect
