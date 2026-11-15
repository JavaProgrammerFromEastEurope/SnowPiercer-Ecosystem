"""ENERGY-CORE-020: opt-in bounded production IPC facade.

OS provisioning and independent witness are mandatory external obligations.
This does not make legacy library calls inaccessible to same-UID code.
"""
import json
import socket
import time
from .os_boundary import IsolatedProductionEnergyService
from .ipc import MAX_REQUEST
from .ipc_diagnostics import bounded_accept, authenticated_peer, lock_diagnostics
from .trust import AdmissionDenied


class BoundedIsolatedEnergyService(IsolatedProductionEnergyService):
    """Strict UID policy, witness preflight, bounded accept and per-request framing.

    The socket is published only after parent class startup verification. A
    request is dispatched once; broken client connections never cause replay.
    """
    def __init__(self, *args, accept_timeout_s=3.0, request_timeout_s=3.0, **kwargs):
        for value in (accept_timeout_s, request_timeout_s):
            if isinstance(value, bool) or not isinstance(value, (int, float)) or not 0 < value <= 60:
                raise AdmissionDenied('invalid IPC deadline')
        self.accept_timeout_s = accept_timeout_s
        self.request_timeout_s = request_timeout_s
        super().__init__(*args, **kwargs)

    def serve_one(self):
        self._check_pid()
        self._check_socket()
        if self.sock is None:
            raise AdmissionDenied('service not running')
        conn, _ = bounded_accept(self.sock, self.accept_timeout_s)
        with conn:
            conn.settimeout(self.request_timeout_s)
            try:
                self._check_socket()
                uid = authenticated_peer(conn, self.allowed_uids)
                raw = bytearray()
                deadline = time.monotonic() + self.request_timeout_s
                while b'\n' not in raw:
                    if time.monotonic() >= deadline or len(raw) >= MAX_REQUEST:
                        raise AdmissionDenied('request deadline or size exceeded')
                    conn.settimeout(max(0.001, deadline - time.monotonic()))
                    chunk = conn.recv(min(4096, MAX_REQUEST - len(raw)))
                    if not chunk:
                        raise AdmissionDenied('incomplete request')
                    raw.extend(chunk)
                if raw.count(b'\n') != 1 or not raw.endswith(b'\n'):
                    raise AdmissionDenied('invalid framing')
                request = json.loads(raw.decode('utf-8'))
                with self._service_mutex:
                    response = self.dispatch(uid, request)
            except (Exception, socket.timeout) as exc:
                response = {'ok': False, 'error': type(exc).__name__}
            try:
                conn.sendall((json.dumps(response, sort_keys=True) + '\n').encode())
            except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError, socket.timeout):
                pass

    def diagnostic_snapshot(self):
        return lock_diagnostics(self.admission.lock_path)
