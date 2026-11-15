"""Stage 008 opt-in strict IPC service; NOT an OS-enforced production sandbox.

A permit is consumed by the independent broker before reporting recovery admission.
No file repair is performed, and a failed consistency check always denies admission.
"""
from pathlib import Path
from .production import WitnessBackedLogisticsService
from .permit_authority import permit_request
from .secure import AdmissionError

class MandatoryAdmissionLogisticsService(WitnessBackedLogisticsService):
    def __init__(self, root, uid_roles, witness_socket, permit_socket, *, recovery_scope='logistics-recovery', timeout=2.0):
        super().__init__(root, uid_roles, witness_socket, timeout=timeout)
        self.permit_socket = str(permit_socket)
        if not isinstance(recovery_scope, str) or not (1 <= len(recovery_scope) <= 256):
            raise ValueError('invalid recovery scope')
        self.recovery_scope = recovery_scope

    def _admit(self):
        # Both external authorities must be reachable before any service socket is published.
        self._read_witness()
        if not Path(self.permit_socket).is_socket():
            raise AdmissionError('independent permit authority unavailable')
        super()._admit()

    def _dispatch(self, uid, req):
        if isinstance(req, dict) and req.get('action') in ('issue_permit',):
            raise AdmissionError('legacy permit issuance disabled in strict IPC')
        if isinstance(req, dict) and req.get('action') == 'recover':
            if self._poisoned:
                raise AdmissionError('service quarantined')
            self._check_files()
            args = req.get('args')
            if not isinstance(args, dict) or set(args) != {'permit'}:
                raise AdmissionError('invalid recovery arguments')
            token = args['permit']
            if not isinstance(token, str) or len(token) != 64:
                raise AdmissionError('invalid recovery permit')
            # A permit cannot authorize reconciliation of a mismatched checkpoint.
            if self._read_anchor() != self._checkpoint() or self.phase_path.exists():
                raise AdmissionError('unreconciled state')
            # The authority uses kernel-derived peer UID of this service process.
            permit_request(self.permit_socket, 'consume', scope=self.recovery_scope,
                           permit=token, timeout=self.timeout)
            return {'recovered': True, 'admission_only': True}
        return super()._dispatch(uid, req)
