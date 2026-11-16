"""Opt-in diagnostic pytest plugin: force GC at each test boundary.

Use with ``-p scripts.ci.sqlite_gc_probe`` and strict warning filters.
This does not suppress warnings or modify SQLite connections.
"""
import gc
import json
import os
import tracemalloc

import pytest

@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_teardown(item, nextitem):
    outcome = yield
    if not tracemalloc.is_tracing():
        tracemalloc.start(12)
    unreachable = gc.collect()
    record = {"nodeid": item.nodeid, "unreachable": unreachable,
              "uncollectable": len(gc.garbage), "pid": os.getpid()}
    path = os.environ.get("TRAINOS_SQLITE_GC_EVIDENCE")
    if path:
        with open(path, 'a', encoding='utf-8') as stream:
            stream.write(json.dumps(record) + '\n')
    return outcome
