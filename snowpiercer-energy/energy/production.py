"""CORE-010 opt-in simulation service. NOT an enforced production security boundary."""
import json
import os
import socket
import stat
import threading
from pathlib import Path
from .ipc import MAX_REQUEST, peer_uid
from .ipc_v2 import MandatoryEnergyIPCServer
from .recovery_broker import CrossUIDRecoveryBroker
from .trust import AdmissionDenied
from .domain import PowerRequest
from .accounting import StorageDispatch

class IntegratedEnergyService(CrossUIDRecoveryBroker):
    """Single endpoint for simulation admission and UID-bound recovery.

    Cooperating callers use one advisory lock. Legacy direct ledger access is
    still possible and must never be treated as production-authorized.
    """
    def __init__(self, admission, path, allowed_uids):
        super().__init__(admission, path, allowed_uids)
        self._service_mutex = threading.RLock()

    def __enter__(self):
        # Keep startup verification and socket publication in one lock scope.
        return super().__enter__()

    def dispatch(self, uid, req):
        if type(uid) is not int or uid not in self.allowed_uids:
            raise AdmissionDenied('UID denied')
        if not isinstance(req, dict):
            raise AdmissionDenied('invalid schema')
        if req == {'action': 'issue'}:
            p = self.issue(uid)
            return {'ok': True, 'token': p.token, 'sequence': p.sequence, 'digest': p.digest}
        if set(req) == {'action', 'token'} and req['action'] == 'recover':
            seq, digest = self.recover(uid, req['token'])
            return {'ok': True, 'sequence': seq, 'digest': digest}
        fields = {'action','operation_id','requests','duration_h','dispatch','reserve_kw','expected_sequence'}
        if set(req) != fields or req['action'] != 'simulate':
            raise AdmissionDenied('unsupported action')
        self._check_socket()
        result = self.admission.apply(req['operation_id'],
            [PowerRequest(*x) for x in req['requests']],
            duration_h=req['duration_h'],
            dispatch=[StorageDispatch(*x) for x in req['dispatch']],
            reserve_kw=req['reserve_kw'], expected_sequence=req['expected_sequence'])
        return {'ok':True,'sequence':result.sequence,'digest':result.digest}

    def serve_one(self):
        self._check_pid()
        self._check_socket()
        if self.sock is None:
            raise AdmissionDenied('service not running')
        conn, _ = self.sock.accept()
        with conn:
            conn.settimeout(5)
            try:
                self._check_socket()
                uid = peer_uid(conn)
                raw = bytearray()
                while b'\n' not in raw:
                    chunk = conn.recv(min(4096, MAX_REQUEST+1-len(raw)))
                    if not chunk or len(raw)+len(chunk)>MAX_REQUEST:
                        raise AdmissionDenied('invalid framing')
                    raw.extend(chunk)
                if raw.count(b'\n')!=1 or not raw.endswith(b'\n'):
                    raise AdmissionDenied('invalid framing')
                req=json.loads(raw.decode('utf8'))
                with self._service_mutex:
                    response=self.dispatch(uid,req)
            except Exception as exc:
                response={'ok':False,'error':type(exc).__name__}
            try:
                conn.sendall((json.dumps(response,sort_keys=True)+'\n').encode())
            except (BrokenPipeError,ConnectionResetError,ConnectionAbortedError):
                pass
