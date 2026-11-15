import os
import socket
import subprocess
import sys
import threading
from pathlib import Path
import pytest
from energy.ipc_diagnostics import (bounded_accept, AcceptDeadlineExceeded,
    authenticated_peer, assert_private_production_objects, lock_diagnostics)
from energy.trust import AdmissionDenied


def test_bounded_accept_timeout(tmp_path):
    p = tmp_path / 's'
    with socket.socket(socket.AF_UNIX) as sock:
        sock.bind(str(p)); sock.listen(1)
        with pytest.raises(AcceptDeadlineExceeded):
            bounded_accept(sock, .02)


def test_bounded_accept_success(tmp_path):
    p = tmp_path / 's'
    with socket.socket(socket.AF_UNIX) as listener:
        listener.bind(str(p)); listener.listen(1)
        with socket.socket(socket.AF_UNIX) as client:
            client.connect(str(p))
            conn, _ = bounded_accept(listener, .5)
            with conn:
                assert authenticated_peer(conn, {os.geteuid()}) == os.geteuid()
                with pytest.raises(AdmissionDenied):
                    authenticated_peer(conn, {os.geteuid() + 1})


def test_private_object_rejects_root(tmp_path):
    f = tmp_path / 'db'; f.write_text('x'); f.chmod(0o600)
    with pytest.raises(AdmissionDenied):
        assert_private_production_objects([f], 0)


def test_lock_diagnostics(tmp_path):
    f = tmp_path / 'lock'
    assert lock_diagnostics(f)['exists'] is False
    f.touch()
    assert lock_diagnostics(f)['inode'] == f.stat().st_ino


def test_real_cross_uid_kernel_credentials(tmp_path):
    if os.geteuid() != 0 or not hasattr(socket, 'SO_PEERCRED'):
        pytest.skip('root and Linux SO_PEERCRED required')
    import pwd
    users = [u for u in pwd.getpwall() if 0 < u.pw_uid < 65534 and u.pw_name != 'nobody']
    if not users:
        pytest.skip('no unprivileged account')
    user = users[0]
    sockdir = tmp_path / 'shared'; sockdir.mkdir(mode=0o711)
    sockdir.chmod(0o711)
    # pytest tmp_path ancestors can be private; use /tmp owned root sticky dir.
    import tempfile
    with tempfile.TemporaryDirectory(prefix='energy019-', dir='/tmp') as root:
        os.chmod(root, 0o711)
        path = os.path.join(root, 'ipc.sock')
        with socket.socket(socket.AF_UNIX) as listener:
            listener.bind(path); os.chmod(path, 0o666); listener.listen(1)
            child = subprocess.Popen([sys.executable, '-c',
                'import os,socket,sys;os.setgroups([]);os.setgid(int(sys.argv[1]));os.setuid(int(sys.argv[2]));s=socket.socket(socket.AF_UNIX);s.connect(sys.argv[3]);s.sendall(b"x");s.close()',
                str(user.pw_gid), str(user.pw_uid), path], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            try:
                conn, _ = bounded_accept(listener, 3)
                with conn:
                    assert authenticated_peer(conn, {user.pw_uid}) == user.pw_uid
                    with pytest.raises(AdmissionDenied):
                        authenticated_peer(conn, {os.geteuid()})
                out, err = child.communicate(timeout=3)
                assert child.returncode == 0, err
            finally:
                if child.poll() is None:
                    child.kill(); child.communicate()
