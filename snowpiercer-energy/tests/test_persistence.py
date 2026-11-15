import multiprocessing as mp
import os
from pathlib import Path
import sqlite3
from contextlib import closing
import subprocess
import sys
import pytest
from energy import (Asset,AssetKind,EnergyMode,EnergySystem,PowerRequest,StorageDispatch, PersistentEnergyLedger,LedgerIntegrityError,LedgerConflict)

def system():
    return EnergySystem({'s':Asset('s',AssetKind.SOURCE,10), 'b':Asset('b',AssetKind.STORAGE,5,capacity_kwh=20,stored_kwh=10), 'c':Asset('c',AssetKind.CONSUMER,20,critical=True)},EnergyMode.SIMULATION)

def make(tmp_path): return PersistentEnergyLedger(tmp_path/'energy.db',system())

def worker(path, op, q):
    try:
        x=PersistentEnergyLedger(path,system()).apply(op,[PowerRequest('c',12)],duration_h=1,dispatch=[StorageDispatch('b',2)])
        q.put(('ok',x.sequence))
    except Exception as exc:q.put(('error',type(exc).__name__))

def test_persistent_reopen(tmp_path):
    p=make(tmp_path)
    result=p.apply('op1',[PowerRequest('c',12)],duration_h=1,dispatch=[StorageDispatch('b',2)])
    assert result.sequence==1
    assert PersistentEnergyLedger(p.path,system()).snapshot()[2]['b']==8

def test_replay_and_collision(tmp_path):
    p=make(tmp_path)
    p.apply('x',[],duration_h=1)
    with pytest.raises(LedgerConflict):p.apply('x',[],duration_h=1)
    with pytest.raises(LedgerConflict):p.apply('x',[],duration_h=2)
    assert p.snapshot()[0]==1

def test_stale_sequence(tmp_path):
    p=make(tmp_path);p.apply('x',[],duration_h=1,expected_sequence=0)
    with pytest.raises(LedgerConflict):p.apply('y',[],duration_h=1,expected_sequence=0)

def test_rollback_hook(tmp_path):
    p=make(tmp_path)
    def fail(point):
        if point=='after_insert':raise RuntimeError('crash')
    with pytest.raises(RuntimeError):p.apply('x',[],duration_h=1,fault_hook=fail)
    assert p.snapshot()[0]==0
    assert p.apply('x',[],duration_h=1).sequence==1

@pytest.mark.parametrize('point,expected', [('after_begin',0),('after_verify',0),('after_insert',0),('after_commit',1)])
def test_sigkill_boundaries(tmp_path,point,expected):
    p=make(tmp_path)
    code='''import os,sys
from energy import *
s=EnergySystem({'s':Asset('s',AssetKind.SOURCE,10),'b':Asset('b',AssetKind.STORAGE,5,capacity_kwh=20,stored_kwh=10),'c':Asset('c',AssetKind.CONSUMER,20,critical=True)},EnergyMode.SIMULATION)
p=PersistentEnergyLedger(sys.argv[1],s)
def hook(where):
 if where==sys.argv[2]: os.kill(os.getpid(),9)
p.apply('k',[PowerRequest('c',12)],duration_h=1,dispatch=[StorageDispatch('b',2)],fault_hook=hook)
'''
    proc=subprocess.run([sys.executable,'-c',code,p.path,point],cwd=Path(__file__).parents[1],capture_output=True)
    assert proc.returncode != 0
    assert p.snapshot()[0]==expected
    assert p.snapshot()[2]['b']==(8 if expected else 10)

def test_concurrent_distinct(tmp_path):
    p=make(tmp_path);ctx=mp.get_context('spawn');q=ctx.Queue()
    ps=[ctx.Process(target=worker,args=(p.path,str(i),q)) for i in range(4)]
    for proc in ps:proc.start()
    results=[q.get(timeout=20) for _ in ps]
    for proc in ps:proc.join(timeout=20);assert proc.exitcode==0
    q.close();q.join_thread()
    assert sorted(results)==[('ok',i) for i in range(1,5)]
    assert p.snapshot()[2]['b']==2

def test_concurrent_same_id(tmp_path):
    p=make(tmp_path);ctx=mp.get_context('spawn');q=ctx.Queue()
    ps=[ctx.Process(target=worker,args=(p.path,'same',q)) for _ in range(3)]
    for proc in ps:proc.start()
    results=[q.get(timeout=20) for _ in ps]
    for proc in ps:proc.join(timeout=20);assert proc.exitcode==0
    q.close();q.join_thread()
    assert len([r for r in results if r[0]=='ok'])==1
    assert p.snapshot()[0]==1

def test_tamper(tmp_path):
    p=make(tmp_path);p.apply('x',[],duration_h=1)
    with closing(sqlite3.connect(p.path)) as db:
        with db: db.execute("UPDATE entries SET digest='fake' WHERE seq=1")
    with pytest.raises(LedgerIntegrityError):p.snapshot()
    with pytest.raises(LedgerIntegrityError):p.apply('y',[],duration_h=1)

def test_truncated_history_detected_when_gap(tmp_path):
    p=make(tmp_path)
    for i in range(3):p.apply(str(i),[],duration_h=1)
    with closing(sqlite3.connect(p.path)) as db:
        with db: db.execute('DELETE FROM entries WHERE seq=2')
    with pytest.raises(LedgerIntegrityError):p.snapshot()

def test_config_mismatch(tmp_path):
    p=make(tmp_path)
    changed=system();changed.assets['s']=Asset('s',AssetKind.SOURCE,11)
    with pytest.raises(LedgerIntegrityError):PersistentEnergyLedger(p.path,changed)

def test_invalid_dispatch_rolls_back(tmp_path):
    p=make(tmp_path)
    with pytest.raises(Exception):p.apply('x',[],duration_h=1,dispatch=[StorageDispatch('b',5,5)])
    assert p.snapshot()[0]==0

@pytest.mark.parametrize('n',range(16))
def test_bounded_model(tmp_path,n):
    p=make(tmp_path)
    charge=(n%4)*1.0
    duration=0.5+(n//4)*0.25
    result=p.apply(str(n),[PowerRequest('c',6)],duration_h=duration,dispatch=[StorageDispatch('b',charge_kw=charge)])
    assert abs(result.ledger.generation_kw-result.ledger.charge_kw-result.ledger.reserve_kw-result.ledger.delivered_kw-result.ledger.curtailed_kw)<1e-8
    assert p.snapshot()[0]==1
