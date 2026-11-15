import os
import socket
import tempfile
import threading
from pathlib import Path
import pytest
from energy import *
from energy.ipc import peer_uid


def setup(tmp_path):
    from energy.domain import Asset, AssetKind, EnergyMode, EnergySystem
    sys = EnergySystem({'gen': Asset('gen', AssetKind.SOURCE, 100)}, EnergyMode.SIMULATION)
    ledger = PersistentEnergyLedger(tmp_path / 'energy.db', sys)
    anchor = tmp_path / 'anchor'
    anchor.mkdir(mode=0o700)
    return TrustedEnergyGateway(ledger, anchor)


def request(op='op1', action='simulate'):
    return dict(action=action, operation_id=op, requests=[], duration_h=1, dispatch=[], reserve_kw=0, expected_sequence=0)


@pytest.mark.skipif(not hasattr(socket, 'SO_PEERCRED'), reason='Linux SO_PEERCRED required')
def test_authenticated_simulation_and_replay(tmp_path):
    gateway = setup(tmp_path)
    directory = tmp_path / 'private'
    directory.mkdir(mode=0o700)
    with EnergyIPCServer(gateway, directory/'service.sock', [os.getuid()]) as srv:
        def run():
            srv.serve_one()
            srv.serve_one()
        thread = threading.Thread(target=run)
        thread.start()
        assert submit_simulation(srv.path, request())['ok']
        assert not submit_simulation(srv.path, request())['ok']
        thread.join(timeout=5)
        assert not thread.is_alive()
    assert gateway.snapshot()[0] == 1


@pytest.mark.skipif(not hasattr(socket, 'SO_PEERCRED'), reason='Linux SO_PEERCRED required')
def test_denied_uid_and_hardware(tmp_path):
    gateway = setup(tmp_path)
    directory = tmp_path/'private'
    directory.mkdir(mode=0o700)
    with EnergyIPCServer(gateway, directory/'service.sock', [os.getuid()+100000]) as srv:
        t = threading.Thread(target=srv.serve_one)
        t.start()
        assert not submit_simulation(srv.path, request())['ok']
        t.join(timeout=5)
    with EnergyIPCServer(gateway, directory/'service.sock', [os.getuid()]) as srv:
        t = threading.Thread(target=srv.serve_one)
        t.start()
        assert not submit_simulation(srv.path, request(action='hardware'))['ok']
        t.join(timeout=5)
    assert gateway.snapshot()[0] == 0


def test_socket_substitution_and_directory_permissions(tmp_path):
    gateway = setup(tmp_path)
    directory = tmp_path/'private'
    directory.mkdir(mode=0o700)
    path = directory/'service.sock'
    path.write_text('occupied')
    with pytest.raises(AdmissionDenied): EnergyIPCServer(gateway, path, [os.getuid()])
    path.unlink()
    directory.chmod(0o777)
    with pytest.raises(AdmissionDenied): EnergyIPCServer(gateway, path, [os.getuid()])


def test_missing_anchor_prevents_socket_publication(tmp_path):
    gateway = setup(tmp_path)
    (tmp_path/'anchor'/'energy.anchor').unlink()
    directory = tmp_path/'private'
    directory.mkdir(mode=0o700)
    with pytest.raises(AnchorMismatch):
        with EnergyIPCServer(gateway, directory/'service.sock', [os.getuid()]): pass
    assert not (directory/'service.sock').exists()
