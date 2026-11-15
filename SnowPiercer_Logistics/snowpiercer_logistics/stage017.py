"""LOG-CORE-017: conservative, opt-in transaction state classification.

This is NOT a distributed commit protocol. Any unresolved phase or divergence
requires independent offline investigation; no permit authorizes roll-forward.
"""
import json
import os
import stat
from dataclasses import dataclass
from .secure import AdmissionError, SecureLogisticsService
from .stage016 import ConsistencyGatedLogisticsService


@dataclass(frozen=True)
class TransactionSnapshot:
    state: str
    ledger_events: int
    witness_events: int
    phase_present: bool


def _safe_json_file(path, owner_uid):
    """Read using O_NOFOLLOW and fstat; reject hardlinks and unsafe modes."""
    flags = os.O_RDONLY | getattr(os, 'O_NOFOLLOW', 0) | getattr(os, 'O_CLOEXEC', 0)
    fd = os.open(str(path), flags)
    try:
        st = os.fstat(fd)
        if not stat.S_ISREG(st.st_mode) or st.st_uid != owner_uid or st.st_nlink != 1 or st.st_mode & 0o077 or st.st_size > 65536:
            raise AdmissionError('unsafe phase file descriptor')
        with os.fdopen(os.dup(fd), 'rb') as f:
            data = f.read(65537)
        if len(data) > 65536:
            raise AdmissionError('oversized phase')
        return json.loads(data)
    finally:
        os.close(fd)


class QuarantinedTransactionService(ConsistencyGatedLogisticsService):
    """Strictly opt-in: classify state and quarantine any uncommitted phase."""
    def transaction_snapshot(self):
        self._check_files()
        ledger = self._checkpoint()
        witness = self._read_witness()
        local = SecureLogisticsService._read_anchor(self)
        phase = self.phase_path.exists() or self.phase_path.is_symlink()
        if phase:
            # A journal may be forged or incomplete; never auto-reconcile it.
            _safe_json_file(self.phase_path, os.geteuid())
        if not isinstance(witness, dict) or type(witness.get('events')) is not int:
            raise AdmissionError('missing or invalid independent witness')
        if ledger == witness == local and not phase:
            state = 'COMMITTED'
        elif phase:
            state = 'QUARANTINED_PHASE'
        else:
            state = 'QUARANTINED_DIVERGENCE'
        return TransactionSnapshot(state, ledger['events'], witness['events'], phase)

    def _assert_consistent(self):
        snapshot = self.transaction_snapshot()
        if snapshot.state != 'COMMITTED':
            raise AdmissionError('transaction state '+snapshot.state)

    def _admit(self):
        # Inherited startup may reconcile a journal. Block it before admission.
        if self.phase_path.exists() or self.phase_path.is_symlink():
            raise AdmissionError('offline phase investigation required')
        super()._admit()
        self._assert_consistent()

    def _dispatch(self, uid, req):
        if not isinstance(req, dict):
            raise AdmissionError('invalid IPC request')
        # No legacy permit issuance or bypass of the consistency gate.
        if req.get('action') == 'issue_permit':
            raise AdmissionError('legacy production permit prohibited')
        self._assert_consistent()
        return super()._dispatch(uid, req)


def production_admission(*args, **kwargs):
    raise AdmissionError('LOG-CORE-017 NO-GO: integrated four-UID E2E, rollback and crash evidence incomplete')
