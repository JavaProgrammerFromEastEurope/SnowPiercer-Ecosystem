"""Conservative offline witness recovery. No untrusted automatic repair."""
import hashlib
import json
import os
from pathlib import Path
import stat
from .secure import AdmissionError, exclusive_lock
from .core import LogisticsLedger, Principal
from .witness import witness_request


def recover_after_witness_cas(root, witness_socket, *, permit, uid, permit_digest,
                              witness_uid=None, timeout=2.0):
    """Offline recovery: externally provisioned one-time permit digest, consumed atomically.

    This is an experimental operator API. A permit digest supplied by the caller
    is NOT an independent permit authority; callers must protect the digest.
    """
    root = Path(root)
    if os.geteuid() != int(uid):
        raise AdmissionError('recovery UID mismatch')
    if not isinstance(permit, str) or len(permit) < 32:
        raise AdmissionError('invalid recovery permit')
    if hashlib.sha256(permit.encode()).hexdigest() != permit_digest:
        raise AdmissionError('recovery permit mismatch')
    with exclusive_lock(root / 'service.lock'):
        consumed = root / ('recovery-consumed-' + permit_digest)
        if consumed.exists() or consumed.is_symlink():
            raise AdmissionError('replayed recovery permit')
        fd = os.open(consumed, os.O_CREAT | os.O_EXCL | os.O_WRONLY | getattr(os,'O_NOFOLLOW',0), 0o600)
        try:
            os.write(fd, b'consumed\n'); os.fsync(fd)
        finally:
            os.close(fd)
        dfd = os.open(root, os.O_RDONLY)
        try: os.fsync(dfd)
        finally: os.close(dfd)
        # Consume before verification: errors never restore a permit.
        anchor = root / 'checkpoint.json'
        phase = root / 'phase.json'
        for p in (anchor, phase, root/'ledger.sqlite'):
            if p.is_symlink() or not p.exists():
                raise AdmissionError('missing or symlinked recovery artifact')
            s = p.stat()
            if not stat.S_ISREG(s.st_mode) or s.st_uid != uid or s.st_nlink != 1 or s.st_mode & 0o077:
                raise AdmissionError('unsafe recovery artifact')
        before = json.loads(anchor.read_text())
        journal = json.loads(phase.read_text())
        if set(journal) != {'before','key','uid'} or journal['before'] != before:
            raise AdmissionError('invalid recovery journal')
        remote = witness_request(witness_socket, 'read', timeout=timeout)
        db = LogisticsLedger(root/'ledger.sqlite')
        try:
            state = db.verify(Principal('recovery','auditor'))
            current = {'events':state['events'], 'head_hash':state['head_hash']}
            last = db._db.execute('SELECT command_key,previous_hash,event_hash FROM events ORDER BY seq DESC LIMIT 1').fetchone()
            if (remote != current or current['events'] != before['events'] + 1
                or not last or last[0] != journal['key']
                or last[1] != before['head_hash'] or last[2] != current['head_hash']):
                raise AdmissionError('witness/ledger/phase mismatch')
        finally:
            db.close()
        # Atomic replace and directory sync; on crash, consumed permit prevents
        # re-entry and an operator must issue a fresh independent permit.
        from .secure import SecureLogisticsService
        svc = SecureLogisticsService(root, {})
        svc._atomic_json(anchor, current)
        phase.unlink()
        dfd = os.open(root, os.O_RDONLY)
        try: os.fsync(dfd)
        finally: os.close(dfd)
        return {'recovered': True, 'events':current['events']}


def recover_with_authority(root, witness_socket, permit_socket, *, permit, uid, witness_uid=None, timeout=2.0):
    """Consume broker permit before offline recovery; no local caller-supplied digest."""
    from .permit_authority import permit_request
    from .secure import AdmissionError
    import os
    if os.geteuid() != int(uid):
        raise AdmissionError('recovery UID mismatch')
    scope = str(Path(root).resolve())
    permit_request(permit_socket, 'consume', scope=scope, permit=permit, timeout=timeout)
    return recover_after_witness_cas(root, witness_socket, permit=permit, uid=uid,
        permit_digest=hashlib.sha256(permit.encode()).hexdigest(), witness_uid=witness_uid, timeout=timeout)
