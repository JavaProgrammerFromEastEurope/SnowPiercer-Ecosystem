import os
import socket
import threading
import pytest
from energy import (Asset,AssetKind,EnergyMode,EnergySystem,PersistentEnergyLedger,
    TrustedEnergyGateway,UnifiedEnergyAdmission,IntegratedEnergyService,broker_request,AdmissionDenied)

def make(tmp_path, uids=None):
    system=EnergySystem({'gen':Asset('gen',AssetKind.SOURCE,100)},EnergyMode.SIMULATION)
    ledger=PersistentEnergyLedger(tmp_path/'ledger.db',system)
    anchor=tmp_path/'anchor';anchor.mkdir(mode=0o700)
    gateway=TrustedEnergyGateway(ledger,anchor)
    locks=tmp_path/'locks';locks.mkdir(mode=0o700)
    private=tmp_path/'private';private.mkdir(mode=0o700)
    adm=UnifiedEnergyAdmission(gateway,locks/'lock')
    return adm,IntegratedEnergyService(adm,private/'service.sock',uids or [os.geteuid()])

def payload(op='op', seq=0):
    return dict(action='simulate',operation_id=op,requests=[],duration_h=1,dispatch=[],reserve_kw=0,expected_sequence=seq)

@pytest.mark.skipif(not hasattr(socket,'SO_PEERCRED'),reason='Linux')
def test_combined_ipc_and_permits(tmp_path):
    adm,srv=make(tmp_path)
    with srv:
        t=threading.Thread(target=lambda:[srv.serve_one() for _ in range(5)])
        t.start()
        assert broker_request(srv.path,payload())['ok']
        assert not broker_request(srv.path,payload())['ok']
        issued=broker_request(srv.path,{'action':'issue'})
        assert issued['ok']
        assert broker_request(srv.path,{'action':'recover','token':issued['token']})['ok']
        assert not broker_request(srv.path,{'action':'recover','token':issued['token']})['ok']
        t.join(5);assert not t.is_alive()

@pytest.mark.skipif(not hasattr(socket,'SO_PEERCRED'),reason='Linux')
def test_uid_denial(tmp_path):
    adm,srv=make(tmp_path,[os.geteuid()+99999])
    with srv:
        t=threading.Thread(target=srv.serve_one);t.start()
        assert not broker_request(srv.path,{'action':'issue'})['ok']
        t.join(5);assert not t.is_alive()

def test_anchor_missing_and_legacy_bypass(tmp_path):
    adm,srv=make(tmp_path)
    adm.gateway.ledger.apply('legacy',[],duration_h=1)
    with pytest.raises(Exception):
        with srv:pass
    assert not srv.path.exists()

def test_socket_replacement(tmp_path):
    adm,srv=make(tmp_path)
    with srv:
        srv.path.unlink();srv.path.write_text('spoof')
        with pytest.raises(AdmissionDenied):srv.serve_one()

def test_genesis_rollback_detected(tmp_path):
    adm,srv=make(tmp_path)
    adm.apply('first',[],duration_h=1)
    # A complete rollback of both DB and anchor is not detectable with this trust model.
    assert adm.gateway.snapshot()[0]==1
    adm.gateway.anchor.unlink()
    with pytest.raises(Exception):adm.startup()
