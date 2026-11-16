"""v103 opt-in per-file worker scheduling contracts."""
from __future__ import annotations

import os
import threading
import time
from tests.kernel_runner import runner as r
from tests.kernel_runner.config import StageConfig
import pytest


def test_workers_default_is_one(monkeypatch):
    monkeypatch.delenv('TRAINOS_KERNEL_WORKERS', raising=False)
    assert r.KernelTestRunner().workers == 1


def test_workers_invalid_fail_closed(monkeypatch):
    for val in ('0', '17', '-1', 'NaN', '1.5'):
        monkeypatch.setenv('TRAINOS_KERNEL_WORKERS', val)
        with pytest.raises(ValueError):
            r.KernelTestRunner()


def test_opt_in_workers_process_every_file_and_preserve_stage_barrier(monkeypatch):
    monkeypatch.setenv('TRAINOS_KERNEL_WORKERS', '2')
    monkeypatch.delenv('TRAINOS_KERNEL_BATCH', raising=False)
    monkeypatch.setattr(r, 'STAGES', [StageConfig('a', ['a1','a2','a3']),
                                     StageConfig('b', ['b1'])])
    obj=r.KernelTestRunner()
    calls=[]
    lock=threading.Lock()
    def run_file(name):
        with lock:
            calls.append((name, 'begin'))
        time.sleep(.025)
        with lock:
            calls.append((name, 'done'))
        return 0
    monkeypatch.setattr(obj,'_run_test',run_file)
    assert obj.run() == 0
    assert {name for name, act in calls if act=='done'}=={'a1','a2','a3','b1'}
    assert calls.index(('b1','begin')) > max(calls.index((n,'done')) for n in ('a1','a2','a3'))


def test_worker_failure_halts_before_next_stage(monkeypatch):
    monkeypatch.setenv('TRAINOS_KERNEL_WORKERS', '3')
    monkeypatch.delenv('TRAINOS_KERNEL_BATCH', raising=False)
    monkeypatch.setattr(r, 'STAGES', [StageConfig('a',['a1','a2']),StageConfig('b',['b1'])])
    obj=r.KernelTestRunner()
    calls=[]
    def run_file(name):
        calls.append(name)
        return 7 if name=='a2' else 0
    monkeypatch.setattr(obj,'_run_test',run_file)
    assert obj.run() == 1
    assert obj.failed == ['a2']
    assert 'b1' not in calls
