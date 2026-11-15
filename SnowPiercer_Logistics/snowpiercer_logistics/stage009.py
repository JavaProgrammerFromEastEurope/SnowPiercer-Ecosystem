"""Stage 009 opt-in client-bound recovery admission. NOT production certified.

The authority trusts the service's kernel-authenticated UID to report the original
client UID; the service obtains that UID from SO_PEERCRED/getpeereid, not JSON.
"""
import hashlib
import secrets
import sqlite3
from .permit_authority import RecoveryPermitAuthority, permit_request
from .stage008 import MandatoryAdmissionLogisticsService
from .secure import AdmissionError, AuthorizationError

class ClientBoundPermitAuthority(RecoveryPermitAuthority):
    def _connect(self):
        db = super()._connect()
        db.execute('CREATE TABLE IF NOT EXISTS client_permits (digest TEXT PRIMARY KEY, client_uid INTEGER NOT NULL, scope TEXT NOT NULL, used INTEGER NOT NULL DEFAULT 0)')
        return db

    def _handle(self, conn):
        # This endpoint deliberately does not inherit the legacy issue/consume protocol.
        from .secure import _peer_uid
        import json
        uid = _peer_uid(conn)
        conn.settimeout(self.timeout)
        data = b''
        while b'\n' not in data:
            part = conn.recv(4096)
            if not part or len(data) + len(part) > 8192:
                raise AdmissionError('invalid request')
            data += part
        req = json.loads(data.split(b'\n', 1)[0])
        if not isinstance(req, dict): raise AdmissionError('invalid request')
        action, scope, client_uid = req.get('action'), req.get('scope'), req.get('client_uid')
        if not isinstance(scope, str) or not 1 <= len(scope) <= 256: raise AdmissionError('invalid scope')
        if type(client_uid) is not int or client_uid < 0: raise AdmissionError('invalid client UID')
        if action == 'issue_client':
            if uid != self.operator_uid: raise AdmissionError('operator UID rejected')
            token = secrets.token_hex(32)
            db = self._connect()
            try:
                db.execute('INSERT INTO client_permits(digest,client_uid,scope) VALUES (?,?,?)',
                           (hashlib.sha256(token.encode()).hexdigest(), client_uid, scope))
            finally: db.close()
            return {'permit': token}
        if action == 'consume_client':
            if uid != self.service_uid: raise AdmissionError('service UID rejected')
            token = req.get('permit')
            if not isinstance(token, str) or len(token) != 64 or any(c not in '0123456789abcdef' for c in token):
                raise AdmissionError('invalid token')
            db = self._connect()
            try:
                db.execute('BEGIN IMMEDIATE')
                cur = db.execute('UPDATE client_permits SET used=1 WHERE digest=? AND client_uid=? AND scope=? AND used=0',
                                 (hashlib.sha256(token.encode()).hexdigest(), client_uid, scope))
                if cur.rowcount != 1:
                    db.execute('ROLLBACK')
                    raise AdmissionError('permit denied, mismatched UID or replay')
                db.execute('COMMIT')
            finally: db.close()
            return {'consumed': True}
        raise AdmissionError('legacy permit protocol disabled')

class ClientBoundLogisticsService(MandatoryAdmissionLogisticsService):
    def _dispatch(self, uid, req):
        if isinstance(req, dict) and req.get('action') == 'recover':
            if uid not in self.uid_roles or self.uid_roles[uid] not in ('admin', 'operator'):
                raise AuthorizationError('recovery role denied')
            if self._poisoned: raise AdmissionError('quarantined')
            self._check_files()
            args = req.get('args')
            if not isinstance(args, dict) or set(args) != {'permit'}: raise AdmissionError('invalid recovery arguments')
            token = args['permit']
            if not isinstance(token, str) or len(token) != 64: raise AdmissionError('invalid permit')
            if self._read_anchor() != self._checkpoint() or self.phase_path.exists():
                raise AdmissionError('unreconciled state')
            # UID is taken exclusively from kernel credentials at service IPC accept.
            result = client_permit_request(self.permit_socket, 'consume_client',
                                           scope=self.recovery_scope, client_uid=uid,
                                           permit=token, timeout=self.timeout)
            return {'recovered': bool(result['consumed']), 'admission_only': True}
        return super()._dispatch(uid, req)

def client_permit_request(path, action, *, scope, client_uid, permit=None, timeout=2.0):
    import json, socket
    with socket.socket(socket.AF_UNIX) as sock:
        sock.settimeout(timeout)
        sock.connect(str(path))
        sock.sendall((json.dumps({'action':action,'scope':scope,'client_uid':client_uid,'permit':permit})+'\n').encode())
        data = b''
        while b'\n' not in data:
            part = sock.recv(4096)
            if not part or len(data)+len(part) > 8192: raise AdmissionError('invalid authority response')
            data += part
        response = json.loads(data.split(b'\n',1)[0])
        if not response.get('ok'): raise AdmissionError(response.get('message','authority rejected'))
        return response['result']
