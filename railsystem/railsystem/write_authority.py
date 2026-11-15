"""RAIL-TRUST-013: dedicated, fail-closed software release write authority.

This entrypoint does not bypass legacy Python API *availability*. OS DAC prevents
unprivileged clients from opening service-owned state; same-service-UID code,
root and storage administrators remain privileged adversaries. No rail actuation.
"""
from __future__ import annotations

import argparse
import json
import os
import signal
import socket
import stat
import sys
from pathlib import Path

from .anchored_admission import _locked
from .os_boundary import validate_production_config, DeploymentDenied
from .production_fencing import _inspect_fence_locked
from .recovery_broker import authorize_peer
from .trusted_admission import AdmissionError, read_protected_json
from .unified_admission import admit


class WriteDenied(AdmissionError):
    pass


def _secure_source(path, uid):
    """Validate a deployment-fixed artifact before accepting any IPC request."""
    path = Path(path)
    if not path.is_absolute():
        raise WriteDenied('absolute protected artifact path required')
    parent = path.parent.lstat()
    if (not stat.S_ISDIR(parent.st_mode) or parent.st_uid != uid
            or stat.S_IMODE(parent.st_mode) & 0o077):
        raise WriteDenied('untrusted protected artifact directory')
    info = path.lstat()
    if (not stat.S_ISREG(info.st_mode) or info.st_uid != uid or info.st_nlink != 1
            or stat.S_IMODE(info.st_mode) not in (0o400, 0o600)):
        raise WriteDenied('unsafe protected artifact')
    return read_protected_json(path)


class ProductionWriteAuthority:
    """Authenticated Linux Unix write endpoint; only fixed ADMIT operation.

    The caller cannot supply arbitrary paths, policies, baselines or permits.
    All state-changing operations run inside the shared admission.lock, with a
    fresh external witness check and the same protected state directory.
    """
    def __init__(self, config, *, root, baseline_file, attestation_file, trust_file):
        self.config = config
        self.root = Path(root)
        self.baseline_file = Path(baseline_file)
        self.attestation_file = Path(attestation_file)
        self.trust_file = Path(trust_file)
        self.path = Path(config['ipc_dir']) / 'write-v013.sock'
        self.sock = None
        self.identity = None
        self.provider = None
        self.ledger = None

    def _verify_path(self):
        s = self.path.lstat()
        if (not stat.S_ISSOCK(s.st_mode) or s.st_uid != os.geteuid()
                or s.st_gid != self.config['transport_gid']
                or stat.S_IMODE(s.st_mode) != 0o660
                or (s.st_dev, s.st_ino) != self.identity):
            raise WriteDenied('write socket path mismatch')

    def _remove_owned(self):
        try:
            self._verify_path()
        except (OSError, WriteDenied):
            return
        self.path.unlink()

    def start(self):
        if self.sock is not None:
            raise WriteDenied('write authority already started')
        # No socket is published until every external independent contract responds.
        provider, ledger = validate_production_config(self.config)
        uid = self.config['uids']['service']
        for p in (self.baseline_file, self.attestation_file, self.trust_file):
            _secure_source(p, uid)
        state = Path(self.config['state_dir'])
        with _locked(state):
            _inspect_fence_locked(state, provider)
            if os.path.lexists(self.path):
                raise WriteDenied('socket path occupied; never remove unknown socket')
            listener = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            try:
                listener.bind(str(self.path))
                # Socket group already belongs to process primary GID; no chown needed.
                os.chmod(self.path, 0o660)
                s = self.path.lstat()
                self.identity = (s.st_dev, s.st_ino)
                self._verify_path()
                listener.listen(8)
                self.sock = listener
                self.provider, self.ledger = provider, ledger
            except BaseException:
                listener.close()
                if self.identity is not None:
                    self._remove_owned()
                self.identity = None
                raise

    def handle_one(self):
        if self.sock is None:
            raise WriteDenied('write authority not started')
        self._verify_path()
        conn, _ = self.sock.accept()
        with conn:
            conn.settimeout(3)
            try:
                self._verify_path()
                authorize_peer(conn, frozenset({self.config['uids']['client']}))
                if conn.recv(64) != b'ADMIT\n':
                    raise WriteDenied('unsupported write command')
                state = Path(self.config['state_dir'])
                with _locked(state):
                    self._verify_path()
                    _inspect_fence_locked(state, self.provider)
                    if self.ledger.check_ready() is not True:
                        raise WriteDenied('independent permit authority not ready')
                    # Reopen protected files under lock. No client-provided JSON or paths.
                    baseline = _secure_source(self.baseline_file, os.geteuid())
                    attestation = _secure_source(self.attestation_file, os.geteuid())
                    trust = _secure_source(self.trust_file, os.geteuid())
                    outcome = admit(self.root, baseline=baseline, attestation=attestation,
                                    trust=trust, state_dir=state, provider=self.provider,
                                    _lock_held=True)
                response = {'status': outcome['status']}
            except (AdmissionError, OSError, ValueError, TypeError, TimeoutError):
                response = {'status': 'BLOCKED'}
            try:
                conn.sendall((json.dumps(response, sort_keys=True) + '\n').encode())
            except (OSError, TimeoutError):
                pass  # Fail-closed; no retry of an ambiguous successful CAS.
            return response['status']

    def close(self):
        if self.sock is None and self.identity is None:
            return
        with _locked(Path(self.config['state_dir'])):
            if self.sock is not None:
                self.sock.close()
                self.sock = None
            if self.identity is not None:
                self._remove_owned()
                self.identity = None


def serve(config, *, root, baseline_file, attestation_file, trust_file, once=False):
    authority = ProductionWriteAuthority(config, root=root, baseline_file=baseline_file,
                                         attestation_file=attestation_file, trust_file=trust_file)
    stop = False
    def on_term(_sig, _frame):
        nonlocal stop
        stop = True
    old = signal.signal(signal.SIGTERM, on_term)
    try:
        authority.start()
        authority.sock.settimeout(1.0)
        while not stop:
            try:
                authority.handle_one()
            except TimeoutError:
                continue
            if once:
                break
    finally:
        try:
            authority.close()
        finally:
            signal.signal(signal.SIGTERM, old)


def main(argv=None):
    parser = argparse.ArgumentParser(description='Software release write authority; not rail control')
    for field in ('config','root','baseline','attestation','trust'):
        parser.add_argument('--'+field, type=Path, required=True)
    parser.add_argument('--once', action='store_true')
    args = parser.parse_args(argv)
    try:
        from .os_managed_fencing import require_production_isolation
        require_production_isolation()  # mandatory OS MAC / independently attested anchor
        config = read_protected_json(args.config)
        serve(config, root=args.root, baseline_file=args.baseline,
              attestation_file=args.attestation, trust_file=args.trust, once=args.once)
        return 0
    except Exception as exc:
        print('RAIL-TRUST-013 BLOCKED: ' + type(exc).__name__, file=sys.stderr)
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
