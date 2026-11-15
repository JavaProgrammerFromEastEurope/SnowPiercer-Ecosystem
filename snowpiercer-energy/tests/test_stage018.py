import os
import subprocess
import sys
from pathlib import Path
import pytest
from energy.os_boundary import ProductionUIDPolicy, require_private_tree
from energy.trust import AdmissionDenied


def test_reject_same_uid():
    uid = max(os.geteuid(), 1)
    with pytest.raises(AdmissionDenied):
        ProductionUIDPolicy(uid, uid, frozenset({uid+1})).validate()


def test_reject_root_or_client_collision():
    with pytest.raises(AdmissionDenied):
        ProductionUIDPolicy(0, 3001, frozenset({3002})).validate()
    with pytest.raises(AdmissionDenied):
        ProductionUIDPolicy(3000, 3001, frozenset({3000})).validate()


def test_reject_wrong_effective_uid():
    uid = os.geteuid() + 20000
    with pytest.raises(AdmissionDenied):
        ProductionUIDPolicy(uid, uid+1, frozenset({uid+2})).validate()


def test_private_tree_and_symlink(tmp_path):
    private = tmp_path / 'private'
    private.mkdir(mode=0o700)
    require_private_tree([private], os.geteuid())
    private.chmod(0o777)
    with pytest.raises(AdmissionDenied):
        require_private_tree([private], os.geteuid())
    private.chmod(0o700)
    link = tmp_path / 'link'
    link.symlink_to(private)
    with pytest.raises(AdmissionDenied):
        require_private_tree([link], os.geteuid())


def test_real_uid_isolation_when_root(tmp_path):
    if os.geteuid() != 0 or not Path('/usr/sbin/runuser').exists():
        pytest.skip('root and runuser required for real cross-UID test')
    import pwd
    accounts = [p for p in pwd.getpwall() if p.pw_uid > 0 and p.pw_uid < 65534 and p.pw_name not in ('nobody',)]
    if not accounts:
        pytest.skip('no unprivileged account available')
    account = accounts[0]
    secret = tmp_path / 'secret'
    secret.write_text('private')
    secret.chmod(0o600)
    # A non-root process must not read root-owned private data.
    proc = subprocess.run(['/usr/sbin/runuser', '-u', account.pw_name, '--',
                           sys.executable, '-c', 'import sys;open(sys.argv[1]).read()', str(secret)],
                          capture_output=True, timeout=10)
    assert proc.returncode != 0
