"""LOG-CORE-015 opt-in direct-client attestation for recovery permits.

A client must independently present the token to the authority over a kernel-
credentialled Unix socket before a service can consume it. Not production ready:
filesystem deployment, atomic witness/ledger recovery and rollback still require proof.
"""
import hashlib
import json
import secrets
from .secure import AdmissionError, _peer_uid
from .stage009 import ClientBoundPermitAuthority, ClientBoundLogisticsService


def _token_digest(token):
    if not isinstance(token, str) or len(token) != 64 or any(c not in '0123456789abcdef' for c in token):
        raise AdmissionError('invalid permit token')
    return hashlib.sha256(token.encode('ascii')).hexdigest()


class DirectAttestationAuthority(ClientBoundPermitAuthority):
    """Opt-in broker: issue -> direct client attestation -> service consume.

    Distinct service and client kernel UIDs are enforced for each request.
    Existing stage009 authority and its API are left unchanged.
    """
    def _connect(self):
        db = super()._connect()
        db.execute('CREATE TABLE IF NOT EXISTS attested_permits ('
                   'digest TEXT PRIMARY KEY, client_uid INTEGER NOT NULL, scope TEXT NOT NULL, '
                   'attested INTEGER NOT NULL DEFAULT 0, used INTEGER NOT NULL DEFAULT 0)')
        return db

    def _handle(self, conn):
        uid = _peer_uid(conn)
        conn.settimeout(self.timeout)
        data = b''
        while b'\n' not in data:
            part = conn.recv(4096)
            if not part or len(data) + len(part) > 8192:
                raise AdmissionError('invalid authority request')
            data += part
        req = json.loads(data.split(b'\n', 1)[0])
        if not isinstance(req, dict):
            raise AdmissionError('invalid authority request')
        action = req.get('action')
        scope = req.get('scope')
        if not isinstance(scope, str) or not 1 <= len(scope) <= 256:
            raise AdmissionError('invalid scope')
        if action == 'issue_attested':
            if uid != self.operator_uid:
                raise AdmissionError('operator UID rejected')
            client_uid = req.get('client_uid')
            if type(client_uid) is not int or client_uid <= 0 or client_uid in (self.service_uid, self.operator_uid):
                raise AdmissionError('invalid independent client UID')
            token = secrets.token_hex(32)
            db = self._connect()
            try:
                db.execute('INSERT INTO attested_permits(digest,client_uid,scope) VALUES(?,?,?)',
                           (_token_digest(token), client_uid, scope))
            finally:
                db.close()
            return {'permit': token}
        digest = _token_digest(req.get('permit'))
        if action == 'attest':
            if uid in (self.operator_uid, self.service_uid):
                raise AdmissionError('direct client UID required')
            db = self._connect()
            try:
                cur = db.execute('UPDATE attested_permits SET attested=1 '
                                 'WHERE digest=? AND client_uid=? AND scope=? AND used=0',
                                 (digest, uid, scope))
                if cur.rowcount != 1:
                    raise AdmissionError('client attestation denied')
            finally:
                db.close()
            return {'attested': True}
        if action == 'consume_attested':
            if uid != self.service_uid:
                raise AdmissionError('service UID rejected')
            client_uid = req.get('client_uid')
            if type(client_uid) is not int or client_uid <= 0:
                raise AdmissionError('invalid client UID')
            db = self._connect()
            try:
                db.execute('BEGIN IMMEDIATE')
                cur = db.execute('UPDATE attested_permits SET used=1 '
                                 'WHERE digest=? AND client_uid=? AND scope=? AND attested=1 AND used=0',
                                 (digest, client_uid, scope))
                if cur.rowcount != 1:
                    db.execute('ROLLBACK')
                    raise AdmissionError('unattested, mismatched or replayed permit')
                db.execute('COMMIT')
            finally:
                db.close()
            return {'consumed': True}
        raise AdmissionError('legacy authority protocol disabled')


def attested_permit_request(path, action, *, scope, client_uid=None, permit=None, timeout=2.0):
    import socket
    with socket.socket(socket.AF_UNIX) as sock:
        sock.settimeout(timeout)
        sock.connect(str(path))
        sock.sendall((json.dumps({'action': action, 'scope': scope, 'client_uid': client_uid,
                                  'permit': permit}) + '\n').encode())
        data = b''
        while b'\n' not in data:
            part = sock.recv(4096)
            if not part or len(data) + len(part) > 8192:
                raise AdmissionError('truncated authority response')
            data += part
        reply = json.loads(data.split(b'\n', 1)[0])
        if not reply.get('ok'):
            raise AdmissionError(reply.get('message', 'authority rejected'))
        return reply['result']


class AttestedLogisticsService(ClientBoundLogisticsService):
    """Recover only after independent authority has observed the client UID."""
    def _dispatch(self, uid, req):
        if isinstance(req, dict) and req.get('action') == 'recover':
            from .secure import AuthorizationError
            if uid not in self.uid_roles or self.uid_roles[uid] not in ('admin', 'operator'):
                raise AuthorizationError('recovery role denied')
            if self._poisoned:
                raise AdmissionError('quarantined')
            self._check_files()
            args = req.get('args')
            if not isinstance(args, dict) or set(args) != {'permit'}:
                raise AdmissionError('invalid recovery arguments')
            token = args['permit']
            _token_digest(token)
            if self._read_anchor() != self._checkpoint() or self.phase_path.exists():
                raise AdmissionError('unreconciled state')
            result = attested_permit_request(self.permit_socket, 'consume_attested',
                                             scope=self.recovery_scope, client_uid=uid,
                                             permit=token, timeout=self.timeout)
            return {'recovered': bool(result['consumed']), 'admission_only': True}
        return super()._dispatch(uid, req)
