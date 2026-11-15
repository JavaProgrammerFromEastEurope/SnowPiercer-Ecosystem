import os
import socket
import threading
import pytest
from energy import (Asset,AssetKind,EnergyMode,EnergySystem,PersistentEnergyLedger,
    TrustedEnergyGateway,UnifiedEnergyAdmission,AdmissionDenied,
    CrossUIDRecoveryBroker,broker_request)

def make(tmp_path, allowed=None):
    system=EnergySystem({'gen':Asset('gen',AssetKind.SOURCE,100)},EnergyMode.SIMULATION)
    ledger=PersistentEnergyLedger(tmp_path/'ledger.db',system)
    anchor=tmp_path/'anchor';anchor.mkdir(mode=0o700)
    gateway=TrustedEnergyGateway(ledger,anchor)
    locks=tmp_path/'locks';locks.mkdir(mode=0o700)
    private=tmp_path/'private';private.mkdir(mode=0o700)
    adm=UnifiedEnergyAdmission(gateway,locks/'lock')
    return adm,CrossUIDRecoveryBroker(adm,private/'broker.sock',allowed or [os.geteuid()])

def test_local_one_shot_and_wrong_uid(tmp_path):
    adm,broker=make(tmp_path)
    p=broker.issue(os.geteuid())
    with pytest.raises(AdmissionDenied):broker.recover(os.geteuid()+1,p.token)
    with pytest.raises(AdmissionDenied):broker.recover(os.geteuid(),p.token)
    p=broker.issue(os.geteuid())
    assert broker.recover(os.geteuid(),p.token)[0]==0
    with pytest.raises(AdmissionDenied):broker.recover(os.geteuid(),p.token)

def test_stale_permit_consumed(tmp_path):
    adm,broker=make(tmp_path)
    p=broker.issue(os.geteuid())
    adm.apply('advance',[],duration_h=1)
    with pytest.raises(AdmissionDenied):broker.recover(os.geteuid(),p.token)
    with pytest.raises(AdmissionDenied):broker.recover(os.geteuid(),p.token)

def test_anchor_removal_denies_issue(tmp_path):
    adm,broker=make(tmp_path)
    adm.gateway.anchor.unlink()
    with pytest.raises(Exception):broker.issue(os.geteuid())

@pytest.mark.skipif(not hasattr(socket,'SO_PEERCRED'),reason='Linux SO_PEERCRED required')
def test_ipc_issue_recover_replay(tmp_path):
    adm,broker=make(tmp_path)
    with broker:
        t=threading.Thread(target=lambda:[broker.serve_one() for _ in range(3)])
        t.start()
        issued=broker_request(broker.path,{'action':'issue'})
        assert issued['ok']
        assert broker_request(broker.path,{'action':'recover','token':issued['token']})['ok']
        assert not broker_request(broker.path,{'action':'recover','token':issued['token']})['ok']
        t.join(5);assert not t.is_alive()

@pytest.mark.skipif(not hasattr(socket,'SO_PEERCRED'),reason='Linux SO_PEERCRED required')
def test_ipc_uid_denial(tmp_path):
    adm,broker=make(tmp_path,[os.geteuid()+99999])
    with broker:
        t=threading.Thread(target=broker.serve_one);t.start()
        assert not broker_request(broker.path,{'action':'issue'})['ok']
        t.join(5);assert not t.is_alive()

def test_socket_substitution(tmp_path):
    adm,broker=make(tmp_path)
    with broker:
        broker.path.unlink();broker.path.write_text('spoof')
        with pytest.raises(AdmissionDenied):broker.serve_one()

def test_legacy_bypass_remains_detectable(tmp_path):
    adm,broker=make(tmp_path)
    adm.gateway.ledger.apply('legacy',[],duration_h=1)
    with pytest.raises(Exception):broker.issue(os.geteuid())

def test_reject_invalid_parent_and_fork(tmp_path):
    adm,broker=make(tmp_path)
    if hasattr(os,'fork'):
        pid=os.fork()
        if pid==0:
            try:broker.issue(os.geteuid())
            except AdmissionDenied:os._exit(0)
            os._exit(1)
        assert os.waitstatus_to_exitcode(os.waitpid(pid,0)[1])==0
