import os
import socket
import threading
import pytest
from energy import PersistentEnergyLedger, TrustedEnergyGateway, UnifiedEnergyAdmission, submit_simulation, AdmissionDenied
from energy.domain import Asset, AssetKind, EnergyMode, EnergySystem
from energy.ipc_v2 import MandatoryEnergyIPCServer


def make(tmp_path):
    system=EnergySystem({'gen':Asset('gen',AssetKind.SOURCE,100)},EnergyMode.SIMULATION)
    ledger=PersistentEnergyLedger(tmp_path/'ledger.db',system)
    anchor=tmp_path/'anchor';anchor.mkdir(mode=0o700)
    gateway=TrustedEnergyGateway(ledger,anchor)
    lockdir=tmp_path/'locks';lockdir.mkdir(mode=0o700)
    private=tmp_path/'private';private.mkdir(mode=0o700)
    admission=UnifiedEnergyAdmission(gateway,lockdir/'lock')
    return admission,private/'service.sock'

def request(op='one', action='simulate', sequence=0):
    return dict(action=action,operation_id=op,requests=[],duration_h=1,dispatch=[],reserve_kw=0,expected_sequence=sequence)

@pytest.mark.skipif(not hasattr(socket,'SO_PEERCRED'),reason='Linux only')
def test_mandatory_gateway_and_replay(tmp_path):
    adm,path=make(tmp_path)
    with MandatoryEnergyIPCServer(adm,path,[os.geteuid()]) as srv:
        thread=threading.Thread(target=lambda:(srv.serve_one(),srv.serve_one()))
        thread.start()
        assert submit_simulation(path,request())['ok']
        assert not submit_simulation(path,request())['ok']
        thread.join(5)
        assert not thread.is_alive()
    assert adm.gateway.snapshot()[0]==1

@pytest.mark.skipif(not hasattr(socket,'SO_PEERCRED'),reason='Linux only')
def test_denied_uid_and_hardware(tmp_path):
    adm,path=make(tmp_path)
    with MandatoryEnergyIPCServer(adm,path,[os.geteuid()+100000]) as srv:
        t=threading.Thread(target=srv.serve_one);t.start()
        assert not submit_simulation(path,request())['ok'];t.join(5)
    with MandatoryEnergyIPCServer(adm,path,[os.geteuid()]) as srv:
        t=threading.Thread(target=srv.serve_one);t.start()
        assert not submit_simulation(path,request(action='hardware'))['ok'];t.join(5)

@pytest.mark.skipif(not hasattr(socket,'SO_PEERCRED'),reason='Linux only')
def test_socket_substitution_fails_closed(tmp_path):
    adm,path=make(tmp_path)
    with MandatoryEnergyIPCServer(adm,path,[os.geteuid()]) as srv:
        path.unlink();path.write_text('replacement')
        with pytest.raises(AdmissionDenied):srv.serve_one()


def test_requires_admission(tmp_path):
    adm,path=make(tmp_path)
    with pytest.raises(AdmissionDenied):MandatoryEnergyIPCServer(adm.gateway,path,[os.geteuid()])


def test_missing_anchor_blocks_publication(tmp_path):
    adm,path=make(tmp_path)
    adm.gateway.anchor.unlink()
    with pytest.raises(Exception):
        with MandatoryEnergyIPCServer(adm,path,[os.geteuid()]):pass
    assert not path.exists()

@pytest.mark.skipif(not hasattr(os,'fork'),reason='POSIX fork required')
def test_concurrent_startup_one_socket_owner(tmp_path):
    import multiprocessing
    adm,path=make(tmp_path)
    def attempt(queue):
        try:
            local=UnifiedEnergyAdmission(adm.gateway,adm.lock_path)
            with MandatoryEnergyIPCServer(local,path,[os.geteuid()]):
                queue.put('success')
                import time
                time.sleep(.3)
        except Exception:
            queue.put('denied')
    ctx=multiprocessing.get_context('fork')
    q=ctx.Queue()
    p1=ctx.Process(target=attempt,args=(q,));p1.start()
    assert q.get(timeout=5)=='success'
    p2=ctx.Process(target=attempt,args=(q,));p2.start()
    assert q.get(timeout=5)=='denied'
    p1.join(5);p2.join(5)
    assert p1.exitcode==p2.exitcode==0
    q.close();q.join_thread()
