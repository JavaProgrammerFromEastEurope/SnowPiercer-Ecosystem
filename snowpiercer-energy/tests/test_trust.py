import json
import multiprocessing as mp
import os
from pathlib import Path
import shutil
import subprocess
import sys
import pytest
from energy import (Asset,AssetKind,EnergyMode,EnergySystem,PowerRequest,PersistentEnergyLedger,TrustedEnergyGateway,ProductionEnergyAdmission,AdmissionDenied,AnchorMismatch,LedgerConflict)

def system():
    return EnergySystem({'s':Asset('s',AssetKind.SOURCE,10),'c':Asset('c',AssetKind.CONSUMER,20)},EnergyMode.SIMULATION)

def make(tmp_path):
    directory=tmp_path/'anchor';directory.mkdir()
    return TrustedEnergyGateway(PersistentEnergyLedger(tmp_path/'energy.db',system()),directory)

def test_admission(tmp_path):
    g=make(tmp_path);p=ProductionEnergyAdmission(g)
    assert p.submit_simulation('a',[PowerRequest('c',3)],duration_h=1).sequence==1
    with pytest.raises(AdmissionDenied):p.submit_hardware()
    with pytest.raises(AdmissionDenied):p.legacy_write()
    with pytest.raises(LedgerConflict):p.submit_simulation('a',[],duration_h=1)

def test_rollback(tmp_path):
    g=make(tmp_path);backup=tmp_path/'backup.db'
    shutil.copyfile(g.ledger.path,backup)
    g.apply('a',[],duration_h=1)
    shutil.copyfile(backup,g.ledger.path)
    with pytest.raises(AnchorMismatch):g.snapshot()

def test_truncation_and_anchor_tamper(tmp_path):
    g=make(tmp_path);g.apply('a',[],duration_h=1)
    g.anchor.write_text('invalid')
    with pytest.raises((AnchorMismatch,ValueError)):g.snapshot()

def test_unguarded_legacy_detected(tmp_path):
    g=make(tmp_path)
    g.ledger.apply('bypass',[],duration_h=1)
    with pytest.raises(AnchorMismatch):g.snapshot()

def test_missing_anchor_fail_closed(tmp_path):
    g=make(tmp_path);g.apply('a',[],duration_h=1);g.anchor.unlink()
    with pytest.raises(AnchorMismatch):g.snapshot()

def test_prepare_exception_recovery(tmp_path):
    g=make(tmp_path)
    with pytest.raises(RuntimeError):g.apply('a',[],duration_h=1,fault_hook=lambda p: (_ for _ in ()).throw(RuntimeError()) if p=='after_anchor_prepare' else None)
    assert g.snapshot()[0]==0
    assert g.apply('a',[],duration_h=1).sequence==1

@pytest.mark.parametrize('point,seq',[('after_anchor_prepare',0),('after_insert',0),('after_sqlite_commit',1),('after_anchor_commit',1)])
def test_sigkill(tmp_path,point,seq):
    g=make(tmp_path)
    code='''import os,sys
from energy import *
s=EnergySystem({'s':Asset('s',AssetKind.SOURCE,10),'c':Asset('c',AssetKind.CONSUMER,20)},EnergyMode.SIMULATION)
g=TrustedEnergyGateway(PersistentEnergyLedger(sys.argv[1],s),sys.argv[2])
def hook(p):
 if p==sys.argv[3]:os.kill(os.getpid(),9)
g.apply('a',[],duration_h=1,fault_hook=hook)
'''
    p=subprocess.run([sys.executable,'-c',code,g.ledger.path,str(g.directory),point],cwd=Path(__file__).parents[1],capture_output=True)
    assert p.returncode != 0
    assert g.snapshot()[0]==seq

def worker(path,directory,idx,q):
    try:
        g=TrustedEnergyGateway(PersistentEnergyLedger(path,system()),directory)
        q.put(g.apply(str(idx),[],duration_h=1).sequence)
    except Exception as e:q.put(type(e).__name__)

def test_concurrent(tmp_path):
    g=make(tmp_path);ctx=mp.get_context('spawn');q=ctx.Queue()
    ps=[ctx.Process(target=worker,args=(g.ledger.path,str(g.directory),i,q)) for i in range(3)]
    for p in ps:p.start()
    for p in ps:p.join(15);assert p.exitcode==0
    assert sorted(q.get(timeout=2) for _ in ps)==[1,2,3]
    assert g.snapshot()[0]==3
    q.close();q.join_thread()

def test_symlink_directory(tmp_path):
    g=make(tmp_path);link=tmp_path/'link';link.symlink_to(g.directory,target_is_directory=True)
    with pytest.raises(AdmissionDenied):TrustedEnergyGateway(g.ledger,link)
