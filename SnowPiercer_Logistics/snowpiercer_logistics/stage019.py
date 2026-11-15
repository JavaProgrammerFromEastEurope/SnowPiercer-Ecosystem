"""LOG-CORE-019: integrated admission preflight and explicit transaction fencing.

Experimental opt-in only. This does not implement atomic distributed commit.
"""
import os
import stat
from pathlib import Path
from .secure import AdmissionError, SecureLogisticsService
from .stage018 import EvidenceGatedLogisticsService
from .stage015 import attested_permit_request


def _socket_inode(path):
    """Reject symlinks and unsafe socket types without following the final component."""
    path = Path(path)
    st = path.lstat()
    if not stat.S_ISSOCK(st.st_mode) or stat.S_ISLNK(st.st_mode):
        raise AdmissionError('endpoint is not a socket')
    if st.st_mode & 0o002:
        raise AdmissionError('world-writable endpoint')
    return (st.st_dev, st.st_ino, st.st_uid)


class TransactionAdmissionService(EvidenceGatedLogisticsService):
    """Opt-in integrated guard: witness, ledger, phase and permit endpoint.

    Does not automatically reconcile a witness-advanced crash. Inherited
    library APIs are intentionally retained for compatibility.
    """
    def _assert_endpoints(self):
        _socket_inode(self.witness_socket)
        _socket_inode(self.permit_socket)
        if Path(self.witness_socket).resolve() == Path(self.permit_socket).resolve():
            raise AdmissionError('witness and permit endpoint alias')

    def _admit(self):
        self._assert_endpoints()
        super()._admit()
        self._assert_endpoints()

    def _dispatch(self, uid, req):
        if not isinstance(req, dict):
            raise AdmissionError('invalid request')
        if req.get('action') == 'issue_permit':
            raise AdmissionError('legacy permit issuance forbidden')
        self._assert_endpoints()
        self._assert_consistent()
        # Recovery is delegated to the direct-client-attested service.
        # No bypass around authority consumption is introduced.
        return super()._dispatch(uid, req)


def inspect_transaction(service):
    """Read-only evidence; no mutation, no permit consumption."""
    decision = service.recovery_decision()
    return {'state': decision.state, 'permitted': decision.permitted,
            'ledger': decision.ledger, 'checkpoint': decision.checkpoint,
            'witness': decision.witness, 'phase_present': decision.phase_present}


def production_admission(*args, **kwargs):
    raise AdmissionError('LOG-CORE-019 BLOCKED: independent four-UID transaction/crash proof incomplete')
