"""AI-CORE-013: fresh-process production factory with mandatory identity preflight.

Trusted local config is provisioned by the service administrator, never via IPC.
The recovery operation is deliberately offline if the audit checkpoint is fenced.
"""
import json
import os
import stat
from pathlib import Path
from .admission import ReplayStore
from .hardening import HardenedRotationManager, IndependentAnchor
from .audit_anchor import AnchoredAdmissionGateway, AuditCheckpoint
from .production012 import ProductionAdmissionIPCServer
from .recovery_service import reclaim_stale_socket
from .service_identity import IsolationError


def _secret(value):
    if not isinstance(value, str) or len(value) != 64:
        raise IsolationError('INVALID_SECRET')
    try:
        result = bytes.fromhex(value)
    except ValueError as exc:
        raise IsolationError('INVALID_SECRET') from exc
    if len(result) != 32:
        raise IsolationError('INVALID_SECRET')
    return result


def load_config(path):
    path = Path(path)
    info = path.lstat()
    if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1 or info.st_uid != os.geteuid() or stat.S_IMODE(info.st_mode) != 0o600:
        raise IsolationError('UNSAFE_CONFIG')
    if info.st_size > 16384:
        raise IsolationError('CONFIG_TOO_LARGE')
    with path.open('rb') as stream:
        config = json.load(stream)
    required = {'private_dir','socket_dir','socket_path','db','legacy_anchor','independent_anchor',
                'checkpoint','source_keys','root_key','rotation_secret','audit_key',
                'checkpoint_key','recovery_secret','allowed_uids','recovery_uids','ipc_gid'}
    if not isinstance(config,dict) or set(config) != required:
        raise IsolationError('CONFIG_SCHEMA_INVALID')
    return config


def create_service(config_path):
    """Rebuild SQLite and trust objects on every process launch, fail closed."""
    config = load_config(config_path)
    uid = os.geteuid()
    if uid == 0:
        raise IsolationError('ROOT_SERVICE_FORBIDDEN')
    private = Path(config['private_dir'])
    socket_dir = Path(config['socket_dir'])
    for directory, mode in ((private,0o700),(socket_dir,0o710)):
        info = directory.lstat()
        if not stat.S_ISDIR(info.st_mode) or info.st_uid != uid or stat.S_IMODE(info.st_mode) != mode:
            raise IsolationError('UNSAFE_DIRECTORY')
    db_path = Path(config['db'])
    for name in ('db','legacy_anchor','independent_anchor','checkpoint'):
        path = Path(config[name])
        if path.parent != private:
            raise IsolationError('PRIVATE_PATH_REQUIRED')
        info = path.lstat()
        if not stat.S_ISREG(info.st_mode) or info.st_uid != uid or stat.S_IMODE(info.st_mode) != 0o600 or info.st_nlink != 1:
            raise IsolationError('UNSAFE_PRIVATE_FILE')
    socket_path = Path(config['socket_path'])
    if socket_path.parent != socket_dir:
        raise IsolationError('SOCKET_PATH_INVALID')
    keys = {source:_secret(value) for source,value in config['source_keys'].items()}
    store = ReplayStore(str(db_path))
    try:
        manager = HardenedRotationManager(store,config['legacy_anchor'],keys,
                  independent_anchor=IndependentAnchor(config['independent_anchor'],_secret(config['root_key'])),
                  recovery_secret=_secret(config['rotation_secret']))
        gateway = AnchoredAdmissionGateway(manager,_secret(config['audit_key']),
                  checkpoint=AuditCheckpoint(config['checkpoint'],_secret(config['checkpoint_key'])))
        gateway.verify()
        reclaim_stale_socket(socket_path,service_uid=uid,socket_dir=socket_dir)
        service = ProductionAdmissionIPCServer(gateway,socket_path,
                    allowed_uids=config['allowed_uids'], recovery_uids=config['recovery_uids'],
                    recovery_secret=_secret(config['recovery_secret']))
        if type(config['ipc_gid']) is not int or config['ipc_gid'] < 0:
            raise IsolationError('INVALID_IPC_GID')
        service.socket_mode = 0o660
        service.socket_gid = config['ipc_gid']
        return service,store
    except BaseException:
        store.close()
        raise


def run(config_path):
    service,store = create_service(config_path)
    try:
        service.serve()
    finally:
        store.close()


def main():
    import sys
    if len(sys.argv)!=2:
        raise SystemExit('usage: python -m ai_cognition.production013 /secure/config.json')
    run(sys.argv[1])

if __name__ == '__main__':
    raise SystemExit('LEGACY_PRODUCTION_ENTRYPOINT_DISABLED: use production015')
