"""Stage 013: real kernel-credential and filesystem isolation acceptance probes.

Acceptance is deliberately NOT production authorization. Run only in a disposable
privileged Linux test environment; never create host accounts or alter host roots.
"""
import json
import os
import socket
import stat
import subprocess
import sys
from pathlib import Path
from .secure import AdmissionError, _peer_uid
from .stage010 import IsolationPolicy


def _drop_to(uid):
    def change():
        os.setgroups([])
        os.setgid(uid)
        os.setuid(uid)
    return change


def run_as_uid(uid, script, *args, timeout=5):
    """Run an isolated probe with actual kernel UID, not a mocked credential."""
    if os.name != 'posix' or not hasattr(os, 'setuid') or os.geteuid() != 0:
        raise AdmissionError('root POSIX test runner required')
    if type(uid) is not int or uid <= 0:
        raise AdmissionError('invalid probe UID')
    try:
        result = subprocess.run([sys.executable, '-c', script, *map(str,args)],
                                preexec_fn=_drop_to(uid), capture_output=True,
                                text=True, timeout=timeout, check=False, close_fds=True)
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise AdmissionError('cross-UID probe failed') from exc
    return {'uid': uid, 'returncode': result.returncode,
            'stdout': result.stdout[-2048:], 'stderr': result.stderr[-2048:]}


def assert_kernel_uid(uid):
    result = run_as_uid(uid, 'import os; print(os.geteuid())')
    if result['returncode'] or result['stdout'].strip() != str(uid):
        raise AdmissionError('kernel UID mismatch')
    return True


def assert_legacy_fenced(path, denied_uids):
    """Prove denial of direct open for specified real unprivileged UIDs."""
    script = """import os, sys
try:
    fd = os.open(sys.argv[1], os.O_RDONLY)
    os.close(fd)
    sys.exit(2)
except PermissionError:
    sys.exit(0)
except OSError:
    sys.exit(3)
"""
    results = []
    for uid in denied_uids:
        result = run_as_uid(uid, script, path)
        results.append(result)
        if result['returncode'] != 0:
            raise AdmissionError('legacy direct access not proven denied')
    return results


def accept_peer_uid(listener):
    """Return kernel-attested peer UID for an accepted AF_UNIX stream."""
    conn, _ = listener.accept()
    try:
        return _peer_uid(conn)
    finally:
        conn.close()


def verify_cross_uid_policy(policy):
    if not isinstance(policy, IsolationPolicy):
        raise AdmissionError('invalid policy')
    policy.validate()
    if os.geteuid() != 0:
        raise AdmissionError('privileged cross-UID acceptance unavailable')
    for uid in (policy.service_uid, policy.witness_uid, policy.authority_uid) + policy.client_uids:
        assert_kernel_uid(uid)
    return True


def mandatory_production_entrypoint(*args, **kwargs):
    """Unconditionally fail closed until external independent E2E certification."""
    raise AdmissionError('production admission blocked: independent evidence absent')
