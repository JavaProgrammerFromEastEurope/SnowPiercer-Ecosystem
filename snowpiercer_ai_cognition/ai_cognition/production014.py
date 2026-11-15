"""AI-CORE-014: fail-closed journaled anchored admission.

Not a distributed atomic commit: the durable phase journal makes the gap
observable; operator authorization is still required to reconcile it.
"""
import hashlib
import hmac
import json
import os
import stat
from pathlib import Path
from .audit_anchor import AnchoredAdmissionGateway
from .lifecycle import RecoveryRequired
from .production012 import DurableRecoveryAuthorizer


def _encode(obj):
    return json.dumps(obj, sort_keys=True, separators=(',', ':')).encode()


class PhaseJournal:
    def __init__(self, path, key):
        if not isinstance(key, bytes) or len(key) < 32:
            raise ValueError('journal key')
        self.path = Path(path)
        self.key = key

    def read(self):
        try:
            st = self.path.lstat()
            if not stat.S_ISREG(st.st_mode) or st.st_nlink != 1 or stat.S_IMODE(st.st_mode) != 0o600 or st.st_size > 2048:
                raise ValueError('unsafe journal')
            record = json.loads(self.path.read_bytes())
            if set(record) != {'phase', 'seq', 'head', 'mac'} or record['phase'] not in ('PREPARED', 'CLEAN'):
                raise ValueError('journal format')
            body = {k: record[k] for k in ('phase', 'seq', 'head')}
            if type(body['seq']) is not int or body['seq'] < 0 or not isinstance(body['head'], str) or len(body['head']) != 64:
                raise ValueError('journal format')
            expected = hmac.new(self.key, _encode(body), hashlib.sha256).hexdigest()
            if not isinstance(record['mac'], str) or not hmac.compare_digest(expected, record['mac']):
                raise ValueError('journal mac')
            return body
        except (OSError, ValueError, TypeError, KeyError) as exc:
            raise RecoveryRequired('PHASE_JOURNAL_UNTRUSTED') from exc

    def write(self, phase, seq, head):
        if phase not in ('PREPARED', 'CLEAN') or type(seq) is not int or seq < 0 or not isinstance(head, str) or len(head) != 64:
            raise ValueError('phase')
        body = {'phase': phase, 'seq': seq, 'head': head}
        record = dict(body, mac=hmac.new(self.key, _encode(body), hashlib.sha256).hexdigest())
        tmp = self.path.with_name(self.path.name + '.pending')
        fd = os.open(tmp, os.O_CREAT | os.O_EXCL | os.O_WRONLY | getattr(os, 'O_NOFOLLOW', 0), 0o600)
        try:
            with os.fdopen(fd, 'wb') as f:
                f.write(_encode(record)); f.flush(); os.fsync(f.fileno())
            os.replace(tmp, self.path)
            dfd = os.open(self.path.parent, os.O_RDONLY)
            try: os.fsync(dfd)
            finally: os.close(dfd)
        finally:
            if tmp.exists(): tmp.unlink()


class JournaledAdmissionGateway:
    """Single-writer production adapter; does not expose raw gateway for writes."""
    def __init__(self, gateway, journal, recovery_secret):
        if not isinstance(gateway, AnchoredAdmissionGateway) or not isinstance(journal, PhaseJournal):
            raise TypeError('anchored gateway and journal required')
        self.gateway = gateway
        self.journal = journal
        self.authorizer = DurableRecoveryAuthorizer(gateway, recovery_secret)
        self.verify()

    def verify(self):
        with self.gateway.manager.lock, self.gateway.store._lock:
            state = self.journal.read()
            if state['phase'] != 'CLEAN':
                raise RecoveryRequired('PHASE_RECOVERY_REQUIRED')
            actual = self.gateway.verify()
            if (state['seq'], state['head']) != actual:
                raise RecoveryRequired('PHASE_JOURNAL_MISMATCH')
            return actual

    def admit(self, envelope, *, fault=None):
        with self.gateway.manager.lock, self.gateway.store._lock:
            seq, head = self.verify()
            # Validate before preparing a durable phase.
            self.gateway._verify(envelope)
            self.journal.write('PREPARED', seq, head)
            if fault == 'after_prepare':
                raise RuntimeError('simulated crash after prepare')
            try:
                result = self.gateway.admit(envelope, fault='after_commit' if fault == 'after_commit' else None)
            except Exception:
                # Ordinary rejected admissions (not process crashes) must not
                # poison the service if SQLite and checkpoint are unchanged.
                # On ambiguous state, preserve PREPARED and fail closed.
                try:
                    if self.gateway.verify() == (seq, head):
                        self.journal.write('CLEAN', seq, head)
                except Exception:
                    pass
                raise
            if fault == 'after_checkpoint':
                raise RuntimeError('simulated crash after checkpoint')
            new_seq, new_head = self.gateway.verify()
            self.journal.write('CLEAN', new_seq, new_head)
            return result

    def recover(self, permit=None):
        """Fail closed by default; externally authorized reconciliation only."""
        with self.gateway.manager.lock, self.gateway.store._lock:
            state = self.journal.read()
            if state['phase'] != 'PREPARED':
                return self.verify()
            old = (state['seq'], state['head'])
            if self.gateway.checkpoint.read() != old:
                raise RecoveryRequired('PHASE_CHECKPOINT_UNEXPECTED')
            current = self.gateway._audit_check()
            if current == old:
                # No DB commit; safely clear intent after checking trust chain.
                self.gateway.manager._check()
                self.gateway._schema_check()
                self.journal.write('CLEAN', *old)
                return self.verify()
            if permit is None:
                raise RecoveryRequired('RECOVERY_PERMIT_REQUIRED')
            result = self.authorizer.reconcile(permit)
            self.journal.write('CLEAN', *result)
            return self.verify()
