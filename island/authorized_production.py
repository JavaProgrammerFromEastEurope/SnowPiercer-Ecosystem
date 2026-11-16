"""ISLAND-GEO-014 experimental cross-UID production admission and recovery permits.

Only an OS-provisioned deployment with no alternate write authority can fence legacy APIs.
Do not treat this module as independent anti-rollback protection.
"""
import hashlib
import json
import os
import secrets
import signal
import socket
import sqlite3
import stat
import struct
from pathlib import Path
from .anchored_admission import AdmissionDenied, WitnessStore, WitnessClient, _receive, _send
from .crash_protocol import CrashInstrumentedAdmission, POINTS
from .production_admission import peer_uid, secure_directory, secure_regular

IPC_POINTS = POINTS + ('before_ipc_accept','after_ipc_accept','before_ipc_read','after_ipc_read','after_ipc_auth','after_ipc_write')

def _kill(point, target):
    if target == point:
        os.kill(os.getpid(), signal.SIGKILL)

class PermitAuthority:
    """Separate witness-owned SQLite store. Consume is transactional, one-shot."""
    def __init__(self, db_path, client_uid, service_uid):
        if client_uid == service_uid: raise AdmissionDenied('separate client and service UID required')
        self.db_path = Path(db_path)
        self.client_uid = client_uid
        self.service_uid = service_uid
    def _db(self):
        db = sqlite3.connect(self.db_path, isolation_level=None, timeout=5)
        db.execute('PRAGMA synchronous=FULL')
        db.execute('CREATE TABLE IF NOT EXISTS permits (token_hash TEXT PRIMARY KEY, purpose TEXT NOT NULL, consumed INTEGER NOT NULL DEFAULT 0)')
        return db
    def execute(self, uid, op, token=None):
        if op == 'issue':
            if uid != self.client_uid: raise AdmissionDenied('permit issuer UID rejected')
            token = secrets.token_hex(32)
            db=self._db()
            try:
                db.execute('INSERT INTO permits(token_hash,purpose) VALUES (?,?)', (hashlib.sha256(token.encode()).hexdigest(), 'recover'))
            finally: db.close()
            return {'token':token}
        if op == 'consume':
            if uid != self.service_uid: raise AdmissionDenied('permit consumer UID rejected')
            if type(token) is not str or len(token) != 64 or any(c not in '0123456789abcdef' for c in token):
                raise AdmissionDenied('invalid permit')
            db = self._db()
            try:
                db.execute('BEGIN IMMEDIATE')
                updated = db.execute('UPDATE permits SET consumed=1 WHERE token_hash=? AND consumed=0 AND purpose=?',
                                     (hashlib.sha256(token.encode()).hexdigest(),'recover')).rowcount
                if updated != 1: raise AdmissionDenied('permit replay or unknown permit')
                db.execute('COMMIT')
                return {'consumed':True}
            except BaseException:
                if db.in_transaction: db.execute('ROLLBACK')
                raise
            finally: db.close()
        raise AdmissionDenied('unknown permit operation')

class AuthorityServer:
    """Witness and permit authority share witness UID but use separate databases."""
    def __init__(self, socket_path, witness_db, permit_db, service_uid, client_uid):
        self.path=Path(socket_path)
        self.witness=WitnessStore(witness_db)
        self.permits=PermitAuthority(permit_db,client_uid,service_uid)
        self.service_uid=service_uid
        self.client_uid=client_uid
    def serve(self, limit=None):
        secure_directory(self.path.parent, os.geteuid())
        if self.path.exists() or self.path.is_symlink(): raise AdmissionDenied('occupied authority socket')
        with socket.socket(socket.AF_UNIX,socket.SOCK_STREAM) as srv:
            srv.bind(str(self.path)); os.chmod(self.path,0o660); srv.listen(16); srv.settimeout(.5)
            count=0
            try:
                while limit is None or count<limit:
                    try: client,_=srv.accept()
                    except socket.timeout: continue
                    count+=1
                    with client:
                        client.settimeout(3)
                        try:
                            uid=peer_uid(client)
                            request=_receive(client)
                            if type(request) is not dict or set(request)-{'operation','record','token'}:
                                raise AdmissionDenied('invalid request')
                            op=request.get('operation')
                            if op in ('read','cas'):
                                if uid!=self.service_uid: raise AdmissionDenied('witness UID rejected')
                                result=self.witness.execute(op,request.get('record'))
                            else: result=self.permits.execute(uid,op,request.get('token'))
                            _send(client,{'ok':True,'result':result})
                        except (AdmissionDenied,ValueError,KeyError,OSError,sqlite3.Error) as e:
                            try: _send(client,{'ok':False,'reason':str(e)})
                            except OSError: pass
            finally:
                if self.path.is_socket(): self.path.unlink()

class AuthorityClient(WitnessClient):
    def execute(self,operation,record=None,token=None):
        with socket.socket(socket.AF_UNIX,socket.SOCK_STREAM) as sock:
            sock.settimeout(3); sock.connect(self.path)
            _send(sock,{'operation':operation,'record':record,'token':token})
            result=_receive(sock)
            if type(result) is not dict or result.get('ok') is not True:
                raise AdmissionDenied(result.get('reason','invalid authority response') if type(result) is dict else 'invalid authority response')
            return result['result']

class AuthorizedProductionServer:
    """Mandatory entrypoint for this service; legacy APIs still exist outside OS fencing."""
    def __init__(self, socket_path, local_db, authority_socket, client_uid, witness_uid, crash_at=None):
        self.path=Path(socket_path); self.db=Path(local_db); self.authority=Path(authority_socket)
        self.client_uid=client_uid; self.witness_uid=witness_uid; self.crash_at=crash_at
        if crash_at is not None and crash_at not in IPC_POINTS: raise AdmissionDenied('invalid crash point')
    def _preflight(self):
        uid=os.geteuid()
        if len({uid,self.client_uid,self.witness_uid})!=3 or 0 in {uid,self.client_uid,self.witness_uid}:
            raise AdmissionDenied('three separate nonroot UIDs required')
        secure_directory(self.path.parent,uid)
        secure_directory(self.db.parent,uid)
        if self.path.exists() or self.path.is_symlink(): raise AdmissionDenied('production socket occupied')
        if self.db.exists(): secure_regular(self.db,uid)
        if self.authority.is_symlink() or not self.authority.is_socket() or self.authority.stat().st_uid!=self.witness_uid:
            raise AdmissionDenied('authority endpoint mismatch')
    def serve(self, limit=None, recovery_token=None):
        self._preflight()
        authority=(getattr(self,"authority_client_factory",AuthorityClient))(self.authority)
        # Mandatory permit consumed before any recovery attempt. No automatic privileged bypass.
        if recovery_token is None: raise AdmissionDenied('recovery permit required for startup')
        authority.execute('consume',token=recovery_token)
        admission=CrashInstrumentedAdmission(self.db,authority)
        admission.recover()
        os.chmod(self.db,0o600); os.chmod(self.db.with_suffix('.lock'),0o600)
        with socket.socket(socket.AF_UNIX,socket.SOCK_STREAM) as srv:
            srv.bind(str(self.path)); os.chmod(self.path,0o660); srv.listen(16); srv.settimeout(.5)
            count=0
            try:
                while limit is None or count<limit:
                    _kill('before_ipc_accept',self.crash_at)
                    try: client,_=srv.accept()
                    except socket.timeout: continue
                    count+=1
                    _kill('after_ipc_accept',self.crash_at)
                    with client:
                        client.settimeout(3)
                        try:
                            if peer_uid(client)!=self.client_uid: raise AdmissionDenied('client UID rejected')
                            _kill('before_ipc_read',self.crash_at)
                            request=_receive(client)
                            _kill('after_ipc_read',self.crash_at)
                            if type(request) is not dict or set(request)!={'operation','payload'} or request['operation']!='admit':
                                raise AdmissionDenied('invalid request')
                            if type(request['payload']) is not str or len(request['payload'])>8192:
                                raise AdmissionDenied('invalid payload')
                            payload=bytes.fromhex(request['payload'])
                            if len(payload)>4096: raise AdmissionDenied('oversize payload')
                            _kill('after_ipc_auth',self.crash_at)
                            # Crash injection is a test-only service configuration.
                            result=admission.admit(payload,crash_at=self.crash_at if self.crash_at in POINTS else None)
                            _send(client,{'ok':True,'result':result})
                            _kill('after_ipc_write',self.crash_at)
                        except (AdmissionDenied,ValueError,OSError,sqlite3.Error) as e:
                            try: _send(client,{'ok':False,'reason':str(e)})
                            except OSError: pass
            finally:
                if self.path.is_socket(): self.path.unlink()
