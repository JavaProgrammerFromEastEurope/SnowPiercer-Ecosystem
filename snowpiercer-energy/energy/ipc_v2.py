"""ENERGY-CORE-008 hardened simulation IPC; no physical control interface."""
import os
import socket
import stat
from .ipc import EnergyIPCServer, peer_uid, MAX_REQUEST
from .admission import UnifiedEnergyAdmission
from .trust import AdmissionDenied
import json
from .domain import PowerRequest
from .accounting import StorageDispatch

class MandatoryEnergyIPCServer(EnergyIPCServer):
    """Admission must pass through unified lock; socket inode checked per request.

    Legacy EnergyIPCServer remains importable for library compatibility and is
    NOT a production-authorized entry point. Production closure remains BLOCKED.
    """
    def __init__(self, admission: UnifiedEnergyAdmission, path, allowed_uids):
        if not isinstance(admission, UnifiedEnergyAdmission):
            raise AdmissionDenied('unified admission required')
        self.admission = admission
        super().__init__(admission.gateway, path, allowed_uids)

    def __enter__(self):
        with self.admission.locked():
            self.admission.gateway.snapshot()
            return super().__enter__()

    def _verify_socket(self):
        try:
            info = self.path.lstat()
            if not stat.S_ISSOCK(info.st_mode) or info.st_ino != self._inode or info.st_uid != os.geteuid():
                raise AdmissionDenied('socket substituted')
        except FileNotFoundError as exc:
            raise AdmissionDenied('socket removed') from exc

    def serve_one(self):
        if self.sock is None:
            raise AdmissionDenied('server not running')
        self._verify_socket()
        with self.sock.accept()[0] as conn:
            conn.settimeout(5)
            try:
                self._verify_socket()
                if peer_uid(conn) not in self.allowed_uids:
                    raise AdmissionDenied('UID not authorized')
                raw = bytearray()
                while b'\n' not in raw:
                    part = conn.recv(min(4096, MAX_REQUEST + 1 - len(raw)))
                    if not part or len(raw) + len(part) > MAX_REQUEST:
                        raise AdmissionDenied('invalid framing')
                    raw.extend(part)
                if raw.count(b'\n') != 1 or not raw.endswith(b'\n'):
                    raise AdmissionDenied('invalid trailing data')
                req = json.loads(raw.decode('utf-8'))
                if not isinstance(req, dict) or set(req) != {'action','operation_id','requests','duration_h','dispatch','reserve_kw','expected_sequence'} or req['action'] != 'simulate':
                    raise AdmissionDenied('unsupported action')
                self._verify_socket()
                result = self.admission.apply(req['operation_id'],
                    [PowerRequest(*r) for r in req['requests']],
                    duration_h=req['duration_h'], dispatch=[StorageDispatch(*d) for d in req['dispatch']],
                    reserve_kw=req['reserve_kw'], expected_sequence=req['expected_sequence'])
                response = {'ok': True, 'sequence': result.sequence, 'digest': result.digest}
            except Exception as exc:
                response = {'ok': False, 'error': type(exc).__name__}
            try:
                conn.sendall((json.dumps(response, sort_keys=True)+'\n').encode())
            except (BrokenPipeError, ConnectionResetError):
                pass
