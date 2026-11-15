"""CORE-015 opt-in fail-closed witness transaction journal.

A pending phase is never automatically accepted or replayed. Independent
witness CAS durability and production OS isolation are deployment obligations.
"""
import json
import os
import stat
import tempfile
from pathlib import Path
from .trust import AdmissionDenied
from .trust_boundary import WitnessedEnergyService, WitnessUnavailable


class PendingWitnessTransaction(AdmissionDenied):
    """Operator reconciliation required: outcome cannot be proven locally."""


class JournaledWitnessEnergyService(WitnessedEnergyService):
    """Persist intent BEFORE local mutation, then witness CAS, then clear intent.

    No automatic recovery of ambiguous outcomes. All operations fail closed
    until independent evidence reconciles the transaction.
    """
    def __init__(self, admission, path, allowed_uids, permit_db, checkpoint_dir, witness):
        self.phase_path = Path(checkpoint_dir) / 'witness.phase'
        self._require_clean()
        super().__init__(admission, path, allowed_uids, permit_db, checkpoint_dir, witness)
        self._require_clean()

    def _require_clean(self):
        try:
            st = self.phase_path.lstat()
        except FileNotFoundError:
            return
        if not stat.S_ISREG(st.st_mode) or st.st_uid != os.geteuid() or st.st_nlink != 1 or st.st_mode & 0o077:
            raise PendingWitnessTransaction('unsafe phase journal')
        raise PendingWitnessTransaction('pending witness phase; independent reconciliation required')

    def _phase_write(self, before, action):
        self._require_clean()
        payload = json.dumps({'version': 1, 'action': action, 'revision': before.revision,
                              'sequence': before.sequence, 'digest': before.digest,
                              'permit_fingerprint': before.permit_fingerprint}, sort_keys=True).encode()
        fd = os.open(self.phase_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, 'O_NOFOLLOW', 0), 0o600)
        try:
            with os.fdopen(fd, 'wb') as out:
                out.write(payload)
                out.flush()
                os.fsync(out.fileno())
        except BaseException:
            # Keep journal even on failure; cannot prove durable state.
            raise
        self._fsync_parent()

    def _fsync_parent(self):
        fd = os.open(self.phase_path.parent, os.O_RDONLY | getattr(os, 'O_DIRECTORY', 0))
        try:
            os.fsync(fd)
        finally:
            os.close(fd)

    def _phase_clear(self):
        self.phase_path.unlink()
        self._fsync_parent()

    def _transact(self, action, operation):
        self._check_pid()
        with self._mutex:
            self._require_clean()
            before = self._verify_witness()
            self._phase_write(before, action)
            # A crash or any exception leaves the phase for explicit reconciliation.
            result = operation()
            self._publish(before)
            self._phase_clear()
            return result

    def issue(self, uid):
        # Call the anchored implementation, not the witness implementation,
        # to avoid recursive publication and lock reentry.
        from .permit_anchor import AnchoredDurableEnergyService
        return self._transact('issue', lambda: AnchoredDurableEnergyService.issue(self, uid))

    def recover(self, uid, token):
        from .permit_anchor import AnchoredDurableEnergyService
        return self._transact('recover', lambda: AnchoredDurableEnergyService.recover(self, uid, token))

    def dispatch(self, uid, req):
        if isinstance(req, dict) and req.get('action') == 'simulate':
            from .production import IntegratedEnergyService
            return self._transact('simulate', lambda: IntegratedEnergyService.dispatch(self, uid, req))
        return super().dispatch(uid, req)

    def __enter__(self):
        self._require_clean()
        return super().__enter__()
