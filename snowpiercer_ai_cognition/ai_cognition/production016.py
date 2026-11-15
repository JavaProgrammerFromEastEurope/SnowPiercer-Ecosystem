"""AI-CORE-016: offline cold recovery and production entrypoint fencing.

Recovery is intentionally NOT an IPC operation. Operator must stop service,
provide signed permit and independently validate the committed observation.
"""
import fcntl
import os
from pathlib import Path
from .production015 import load_config_015, _private_file
from .production013 import _secret
from .admission import ReplayStore
from .hardening import HardenedRotationManager, IndependentAnchor
from .audit_anchor import AnchoredAdmissionGateway, AuditCheckpoint
from .gateway import MandatoryAdmissionGateway
from .production014 import PhaseJournal
from .production012 import DurableRecoveryAuthorizer
from .lifecycle import RecoveryRequired
from .service_identity import IsolationError
from .recovery_service import reclaim_stale_socket


def cold_recover(config_path, permit, *, operator_verified=False):
    """Recover a PREPARED phase under an exclusive, offline process lock.

    No automatic reconciliation: permit must authenticate the old checkpoint;
    operator_verified asserts independent review of the pending event.
    """
    if operator_verified is not True:
        raise RecoveryRequired('OPERATOR_VERIFICATION_REQUIRED')
    config = load_config_015(config_path)
    uid = os.geteuid()
    if uid == 0:
        raise IsolationError('ROOT_SERVICE_FORBIDDEN')
    private = Path(config['private_dir'])
    sockdir = Path(config['socket_dir'])
    for directory, mode in ((private, 0o700), (sockdir, 0o710)):
        st = directory.lstat()
        import stat
        if not stat.S_ISDIR(st.st_mode) or st.st_uid != uid or stat.S_IMODE(st.st_mode) != mode:
            raise IsolationError('UNSAFE_DIRECTORY')
    for name in ('db', 'legacy_anchor', 'independent_anchor', 'checkpoint', 'phase_journal'):
        _private_file(config[name], private, uid)
    socket_path = Path(config['socket_path'])
    if socket_path.parent != sockdir:
        raise IsolationError('SOCKET_PATH_INVALID')
    # Reject active IPC before touching the recovery state.
    reclaim_stale_socket(socket_path, service_uid=uid, socket_dir=sockdir)
    from .locking020 import acquire_runtime_lock, release_runtime_lock
    fd = acquire_runtime_lock(private)
    try:
        # Check again under the exclusive lock: another process could have
        # published a socket while the recovery lock was being acquired.
        reclaim_stale_socket(socket_path, service_uid=uid, socket_dir=sockdir)
        store = ReplayStore(config['db'])
        try:
            keys = {source: _secret(value) for source, value in config['source_keys'].items()}
            manager = HardenedRotationManager(store, config['legacy_anchor'], keys,
                independent_anchor=IndependentAnchor(config['independent_anchor'], _secret(config['root_key'])),
                recovery_secret=_secret(config['rotation_secret']))
            checkpoint = AuditCheckpoint(config['checkpoint'], _secret(config['checkpoint_key']))
            journal = PhaseJournal(config['phase_journal'], _secret(config['phase_key']))
            state = journal.read()
            if state['phase'] != 'PREPARED':
                raise RecoveryRequired('NO_PENDING_RECOVERY')
            old = (state['seq'], state['head'])
            anchored = checkpoint.read()
            if anchored != old and anchored[0] != old[0] + 1:
                raise RecoveryRequired('CHECKPOINT_NOT_AT_PREPARED_HEAD')
            # Build the gateway without its normal constructor's mandatory
            # checkpoint match. Never expose this object to production IPC.
            gateway = AnchoredAdmissionGateway.__new__(AnchoredAdmissionGateway)
            gateway.checkpoint = checkpoint
            MandatoryAdmissionGateway.__init__(gateway, manager, _secret(config['audit_key']))
            gateway._schema_check()
            manager._check()
            current = gateway._audit_check()
            if current != old and (current[0] != old[0] + 1 or
                    store._db.execute('SELECT previous FROM gateway_audit WHERE seq=?', (current[0],)).fetchone() != (old[1],)):
                raise RecoveryRequired('RECONCILIATION_AMBIGUOUS')
            if anchored != old and anchored != current:
                raise RecoveryRequired('CHECKPOINT_NOT_AT_AUDIT_HEAD')
            authorizer = DurableRecoveryAuthorizer(gateway, _secret(config['recovery_secret']))
            if current != old and anchored == old:
                result = authorizer.reconcile(permit)
            else:
                # Burn the permit even if no event committed. No silent reset.
                import hmac
                from .isolation import recovery_permit
                if not isinstance(permit, dict) or set(permit) != {'id','seq','head','mac'}:
                    raise RecoveryRequired('RECOVERY_PERMIT_INVALID')
                try:
                    expected = recovery_permit(_secret(config['recovery_secret']), permit['id'], permit['seq'], permit['head'])
                    valid = hmac.compare_digest(expected['mac'], permit['mac'])
                except (ValueError, TypeError, KeyError):
                    valid = False
                if not valid or (permit['seq'], permit['head']) != old:
                    raise RecoveryRequired('RECOVERY_PERMIT_INVALID')
                import sqlite3
                try:
                    store._db.execute('BEGIN IMMEDIATE')
                    store._db.execute('INSERT INTO production_recovery_permits VALUES (?,?,?)',
                                      (permit['id'], *old))
                    store._db.execute('COMMIT')
                except sqlite3.IntegrityError as exc:
                    store._db.execute('ROLLBACK')
                    raise RecoveryRequired('RECOVERY_PERMIT_REPLAY') from exc
                result = current if anchored == current else old
            journal.write('CLEAN', *result)
            if gateway.verify() != result or journal.read() != {'phase':'CLEAN','seq':result[0],'head':result[1]}:
                raise RecoveryRequired('RECOVERY_POSTCHECK_FAILED')
            return result
        finally:
            store.close()
    finally:
        release_runtime_lock(fd)


def main():
    raise SystemExit('Offline recovery requires an authenticated operator integration; no CLI permit arguments are accepted')

if __name__ == '__main__':
    main()
