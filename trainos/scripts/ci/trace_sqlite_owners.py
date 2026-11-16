"""Opt-in SQLite connection owner audit for isolated pytest executions.

Run as: python scripts/ci/trace_sqlite_owners.py -- tests/... -q
Records creation sites, explicit close calls, and live owners. Does not close,
collect, or suppress warnings on behalf of the code under test.
"""
from __future__ import annotations
import argparse
import atexit
import json
import sqlite3
import sys
import traceback
import tracemalloc
import weakref
from pathlib import Path

_ORIGINAL = sqlite3.connect
_RECORDS = {}

class TracedConnection(sqlite3.Connection):
    def close(self):
        record = _RECORDS.get(id(self))
        try:
            return super().close()
        finally:
            if record is not None:
                record['closed'] = True

def traced_connect(*args, **kwargs):
    kwargs.setdefault('factory', TracedConnection)
    connection = _ORIGINAL(*args, **kwargs)
    if isinstance(connection, TracedConnection):
        key = id(connection)
        record = {'database': str(args[0]) if args else str(kwargs.get('database')),
                  'creation_stack': traceback.format_stack(limit=14), 'closed': False}
        _RECORDS[key] = record
        weakref.finalize(connection, lambda k=key: _RECORDS.get(k, {}).update(collected=True))
    return connection

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--report', type=Path, required=True)
    parser.add_argument('pytest_args', nargs=argparse.REMAINDER)
    ns = parser.parse_args()
    args = ns.pytest_args[1:] if ns.pytest_args[:1] == ['--'] else ns.pytest_args
    if not args:
        parser.error('pytest args required')
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
    tracemalloc.start(10)
    sqlite3.connect = traced_connect
    import pytest
    try:
        return int(pytest.main(args))
    finally:
        ns.report.parent.mkdir(parents=True, exist_ok=True)
        ns.report.write_text(json.dumps({'schema':'trainos.sqlite-owner-audit.v1',
            'tracked_connections':len(_RECORDS),
            'not_explicitly_closed':[v for v in _RECORDS.values() if not v['closed']]}, indent=2))

if __name__ == '__main__':
    raise SystemExit(main())
