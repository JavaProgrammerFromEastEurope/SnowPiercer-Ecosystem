import os
import socket
import tempfile
import threading
from pathlib import Path
import pytest
from snowpiercer_logistics.stage013 import (run_as_uid, assert_kernel_uid,
    assert_legacy_fenced, accept_peer_uid, verify_cross_uid_policy, mandatory_production_entrypoint)
from snowpiercer_logistics.stage010 import IsolationPolicy
from snowpiercer_logistics.secure import AdmissionError


def test_production_gate_closed():
    with pytest.raises(AdmissionError): mandatory_production_entrypoint()


def test_policy_rejects_duplicate_uid():
    with pytest.raises(AdmissionError): IsolationPolicy(12001,12002,12003,(12001,)).validate()

@pytest.mark.skipif(os.geteuid()!=0 or not hasattr(os,'setuid'),reason='requires POSIX root')
def test_real_four_uid_kernel_probe():
    policy=IsolationPolicy(12001,12002,12003,(12004,))
    assert verify_cross_uid_policy(policy)

@pytest.mark.skipif(os.geteuid()!=0 or not hasattr(os,'setuid'),reason='requires POSIX root')
def test_real_uid_legacy_fence():
    with tempfile.TemporaryDirectory(prefix='log013_',dir='/tmp') as root:
        target=Path(root)/'private.sqlite'
        target.write_bytes(b'ledger')
        os.chmod(root,0o700)
        os.chmod(target,0o600)
        assert len(assert_legacy_fenced(target,(12002,12003,12004)))==3

@pytest.mark.skipif(os.geteuid()!=0 or not hasattr(os,'setuid'),reason='requires POSIX root')
def test_legacy_fence_detects_exposure():
    with tempfile.TemporaryDirectory(prefix='log013_',dir='/tmp') as root:
        target=Path(root)/'legacy.sqlite'
        target.write_bytes(b'ledger')
        os.chmod(root,0o755)
        os.chmod(target,0o644)
        with pytest.raises(AdmissionError): assert_legacy_fenced(target,(12004,))

@pytest.mark.skipif(os.geteuid()!=0 or not hasattr(os,'setuid'),reason='requires POSIX root')
def test_unix_socket_peer_uid_is_kernel_derived():
    with tempfile.TemporaryDirectory(prefix='log013_',dir='/tmp') as root:
        os.chmod(root,0o777)
        path=str(Path(root)/'sock')
        with socket.socket(socket.AF_UNIX) as server:
            server.bind(path)
            os.chmod(path,0o777)
            server.listen(1)
            outcome=[]
            thread=threading.Thread(target=lambda: outcome.append(accept_peer_uid(server)))
            thread.start()
            try:
                r=run_as_uid(12004,'import socket,sys; s=socket.socket(socket.AF_UNIX); s.connect(sys.argv[1]); s.close()',path)
                assert r['returncode']==0,r
            finally:
                thread.join(timeout=3)
            assert outcome==[12004]
