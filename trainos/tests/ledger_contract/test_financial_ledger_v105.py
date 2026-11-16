"""Finite WAL admission, concurrent constructors and handle lifecycle."""
import math
import sqlite3
import threading
import time
from concurrent.futures import ThreadPoolExecutor

import pytest

from kernel.economy.ledger_contract import FinancialLedger
from kernel.economy.ledger_contract import store


def test_locking_wal_admission_retries_until_released(tmp_path):
    path = tmp_path / 'wal.sqlite'
    keeper = sqlite3.connect(path, isolation_level=None)
    keeper.execute('PRAGMA journal_mode=WAL')
    keeper.execute('BEGIN EXCLUSIVE')
    done = threading.Event()
    result = []

    def create():
        try:
            with FinancialLedger(path, timeout_seconds=1.5) as ledger:
                result.append(ledger.journal_count())
        finally:
            done.set()
    t = threading.Thread(target=create)
    t.start()
    try:
        time.sleep(0.18)
        assert not done.is_set(), 'exclusive lock did not hold constructor'
    finally:
        keeper.rollback()
        keeper.close()
    t.join(4)
    assert not t.is_alive()
    assert result == [0]


def test_wal_admission_times_out_without_unbounded_retry(tmp_path):
    path = tmp_path / 'locked.sqlite'
    keeper = sqlite3.connect(path, isolation_level=None)
    keeper.execute('PRAGMA journal_mode=WAL')
    keeper.execute('BEGIN EXCLUSIVE')
    began = time.monotonic()
    try:
        with pytest.raises(sqlite3.OperationalError, match='locked'):
            FinancialLedger(path, timeout_seconds=0.06)
    finally:
        keeper.rollback()
        keeper.close()
    assert time.monotonic() - began < 1.5


def test_constructor_rejects_nonfinite_timeouts():
    for value in [math.nan, math.inf, -math.inf, 0, -1]:
        with pytest.raises(ValueError):
            FinancialLedger(timeout_seconds=value)


def test_constructor_failure_closes_sqlite_handle(monkeypatch, tmp_path):
    real_connect = store.sqlite3.connect
    closed = []

    class FailingConnection(sqlite3.Connection):
        def execute(self, statement, *args, **kwargs):
            if 'PRAGMA foreign_keys' in statement:
                raise sqlite3.OperationalError('injected init failure')
            return super().execute(statement, *args, **kwargs)

        def close(self):
            closed.append(True)
            return super().close()

    def connect(*args, **kwargs):
        return real_connect(*args, **{**kwargs, 'factory': FailingConnection})

    monkeypatch.setattr(store.sqlite3, 'connect', connect)
    with pytest.raises(sqlite3.OperationalError, match='injected'):
        FinancialLedger(tmp_path / 'fail.sqlite')
    assert closed == [True]


def test_parallel_initial_admission_64_ways(tmp_path):
    path = tmp_path / 'many.sqlite'
    def start(_):
        with FinancialLedger(path, timeout_seconds=4) as ledger:
            return ledger.journal_count()
    with ThreadPoolExecutor(max_workers=16) as pool:
        assert list(pool.map(start, range(64))) == [0] * 64
