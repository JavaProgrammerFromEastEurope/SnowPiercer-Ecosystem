"""AI-CORE-015: mandatory journaled production IPC, offline fail-closed recovery.

The library APIs remain available for offline tooling, NOT production admission.
"""
from pathlib import Path
from .production013 import load_config, _secret
from .production014 import PhaseJournal, JournaledAdmissionGateway
from .production012 import ProductionAdmissionIPCServer
from .isolation import AdmissionIPCServer
import socket
import threading
from .lifecycle import RecoveryRequired
from .service_identity import IsolationError
from .recovery_service import reclaim_stale_socket
from .admission import ReplayStore
from .hardening import HardenedRotationManager, IndependentAnchor
from .audit_anchor import AnchoredAdmissionGateway, AuditCheckpoint
import os
import stat


def _private_file(path, private, uid):
    p = Path(path)
    st = p.lstat()
    if p.parent != private or not stat.S_ISREG(st.st_mode) or st.st_uid != uid or st.st_nlink != 1 or stat.S_IMODE(st.st_mode) != 0o600:
        raise IsolationError('UNSAFE_PRIVATE_FILE')


class JournaledProductionIPCServer(ProductionAdmissionIPCServer):
    """Production-only server: no direct unjournaled gateway dispatch."""
    def __init__(self, journaled, socket_path, *, allowed_uids, recovery_secret, recovery_uids=()):
        if not isinstance(journaled, JournaledAdmissionGateway):
            raise TypeError('JOURNALED_GATEWAY_REQUIRED')
        journaled.verify()
        # Bypass ProductionAdmissionIPCServer constructor: it requires an anchored
        # gateway and would install its unjournaled recovery authorizer.
        if not hasattr(socket, 'SO_PEERCRED'):
            raise RuntimeError('SO_PEERCRED unsupported')
        if not allowed_uids or any(type(x) is not int or x < 0 for x in allowed_uids):
            raise ValueError('allowed_uids')
        self.gateway = journaled
        self.path = Path(socket_path)
        self.allowed_uids = frozenset(allowed_uids)
        self.recovery_uids = frozenset()
        self.recovery = None  # recovery is offline-only
        self._stop = threading.Event()
        self._sock = None


def create_service(config_path):
    """Require an explicitly provisioned phase journal and secret, no bootstrap."""
    config = load_config_015(config_path)
    uid = os.geteuid()
    if uid == 0:
        raise IsolationError('ROOT_SERVICE_FORBIDDEN')
    private = Path(config['private_dir'])
    socket_dir = Path(config['socket_dir'])
    for directory, mode in ((private, 0o700), (socket_dir, 0o710)):
        st = directory.lstat()
        if not stat.S_ISDIR(st.st_mode) or st.st_uid != uid or stat.S_IMODE(st.st_mode) != mode:
            raise IsolationError('UNSAFE_DIRECTORY')
    for name in ('db', 'legacy_anchor', 'independent_anchor', 'checkpoint', 'phase_journal'):
        _private_file(config[name], private, uid)
    sockpath = Path(config['socket_path'])
    if sockpath.parent != socket_dir:
        raise IsolationError('SOCKET_PATH_INVALID')
    keys = {source: _secret(value) for source, value in config['source_keys'].items()}
    store = ReplayStore(config['db'])
    try:
        manager = HardenedRotationManager(store, config['legacy_anchor'], keys,
            independent_anchor=IndependentAnchor(config['independent_anchor'], _secret(config['root_key'])),
            recovery_secret=_secret(config['rotation_secret']))
        gateway = AnchoredAdmissionGateway(manager, _secret(config['audit_key']),
            checkpoint=AuditCheckpoint(config['checkpoint'], _secret(config['checkpoint_key'])))
        journal = PhaseJournal(config['phase_journal'], _secret(config['phase_key']))
        adapter = JournaledAdmissionGateway(gateway, journal, _secret(config['recovery_secret']))
        reclaim_stale_socket(sockpath, service_uid=uid, socket_dir=socket_dir)
        service = JournaledProductionIPCServer(adapter, sockpath,
            allowed_uids=config['allowed_uids'], recovery_secret=_secret(config['recovery_secret']))
        gid = config['ipc_gid']
        if type(gid) is not int or gid < 0:
            raise IsolationError('INVALID_IPC_GID')
        service.socket_mode = 0o660
        service.socket_gid = gid
        return service, store
    except BaseException:
        store.close()
        raise


def load_config_015(path):
    # Validate full configuration using the established v013 schema, then
    # enforce the additional journal fields without weakening old checks.
    import json
    p = Path(path)
    st = p.lstat()
    if not stat.S_ISREG(st.st_mode) or st.st_nlink != 1 or st.st_uid != os.geteuid() or stat.S_IMODE(st.st_mode) != 0o600 or st.st_size > 16384:
        raise IsolationError('UNSAFE_CONFIG')
    with p.open('rb') as stream:
        config = json.load(stream)
    if not isinstance(config, dict) or set(config) != set(_V013_FIELDS) | {'phase_journal', 'phase_key'}:
        raise IsolationError('CONFIG_SCHEMA_INVALID')
    _secret(config['phase_key'])
    return config

_V013_FIELDS = ('private_dir','socket_dir','socket_path','db','legacy_anchor','independent_anchor',
 'checkpoint','source_keys','root_key','rotation_secret','audit_key','checkpoint_key',
 'recovery_secret','allowed_uids','recovery_uids','ipc_gid')


def run(config_path):
    """Hold the common service/recovery lock through initialization and serving."""
    from .locking020 import acquire_runtime_lock, release_runtime_lock
    config = load_config_015(config_path)
    fd = acquire_runtime_lock(config['private_dir'])
    try:
        service, store = create_service(config_path)
        try:
            service.serve()
        finally:
            store.close()
    finally:
        release_runtime_lock(fd)


def main():
    import sys
    if len(sys.argv) != 2:
        raise SystemExit('usage: python -m ai_cognition.production015 /secure/config.json')
    run(sys.argv[1])

if __name__ == '__main__':
    main()
