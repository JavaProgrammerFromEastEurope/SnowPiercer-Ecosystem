"""Experimental independent recovery permit broker; Unix peer credentials + SQLite.

Not a production security boundary without OS-protected deployment and E2E review.
"""
import hashlib
import json
import os
from pathlib import Path
import secrets
import socket
import sqlite3
import threading
from .secure import AdmissionError, _peer_uid, _safe_dir, exclusive_lock

class RecoveryPermitAuthority:
    def __init__(self, root, operator_uid, service_uid, *, timeout=1.0):
        self.root = _safe_dir(root)
        self.operator_uid = int(operator_uid)
        self.service_uid = int(service_uid)
        self.timeout = timeout
        self.socket_path = self.root / 'permits.sock'
        self.db_path = self.root / 'permits.sqlite'
        self.lock_path = self.root / 'permits.lock'
        self._server = None
        self._thread = None
        self._lock = None
        self._stop = threading.Event()

    def _connect(self):
        db = sqlite3.connect(str(self.db_path), timeout=self.timeout, isolation_level=None)
        db.execute('PRAGMA synchronous=FULL')
        db.execute('PRAGMA journal_mode=DELETE')
        db.execute('CREATE TABLE IF NOT EXISTS permits (digest TEXT PRIMARY KEY, uid INTEGER NOT NULL, scope TEXT NOT NULL, used INTEGER NOT NULL DEFAULT 0)')
        return db

    def _handle(self, conn):
        uid = _peer_uid(conn)
        conn.settimeout(self.timeout)
        data = b''
        while b'\n' not in data:
            part = conn.recv(4096)
            if not part or len(data) + len(part) > 8192:
                raise AdmissionError('invalid permit request')
            data += part
        req = json.loads(data.split(b'\n', 1)[0])
        action = req.get('action')
        scope = req.get('scope')
        if not isinstance(scope, str) or not (1 <= len(scope) <= 256):
            raise AdmissionError('invalid scope')
        if action == 'issue':
            if uid != self.operator_uid: raise AdmissionError('operator UID rejected')
            target = req.get('target_uid')
            if type(target) is not int or target != self.service_uid:
                raise AdmissionError('invalid target UID')
            token = secrets.token_hex(32)
            digest = hashlib.sha256(token.encode()).hexdigest()
            db = self._connect()
            try:
                db.execute('INSERT INTO permits(digest,uid,scope) VALUES (?,?,?)', (digest,target,scope))
            finally:
                db.close()
            return {'permit':token}
        if action == 'consume':
            if uid != self.service_uid: raise AdmissionError('service UID rejected')
            token = req.get('permit')
            if not isinstance(token,str) or len(token)!=64:
                raise AdmissionError('invalid permit')
            digest = hashlib.sha256(token.encode()).hexdigest()
            db = self._connect()
            try:
                db.execute('BEGIN IMMEDIATE')
                cur = db.execute('UPDATE permits SET used=1 WHERE digest=? AND uid=? AND scope=? AND used=0', (digest,uid,scope))
                if cur.rowcount != 1:
                    db.execute('ROLLBACK')
                    raise AdmissionError('permit denied or already consumed')
                db.execute('COMMIT')
            finally:
                db.close()
            return {'consumed':True}
        raise AdmissionError('unknown action')

    def _loop(self):
        while not self._stop.is_set():
            try: conn,_ = self._server.accept()
            except socket.timeout: continue
            except OSError: break
            with conn:
                try: result = {'ok':True,'result':self._handle(conn)}
                except Exception as exc: result = {'ok':False,'error':type(exc).__name__,'message':str(exc)}
                try: conn.sendall((json.dumps(result)+'\n').encode())
                except OSError: pass

    def start(self):
        self._lock = exclusive_lock(self.lock_path)
        self._lock.__enter__()
        try:
            if self.socket_path.exists() or self.socket_path.is_symlink():
                raise AdmissionError('permit socket already exists')
            db = self._connect(); db.close()
            os.chmod(self.db_path,0o600)
            self._server = socket.socket(socket.AF_UNIX)
            self._server.bind(str(self.socket_path))
            os.chmod(self.socket_path,0o600)
            self._server.listen(16)
            self._server.settimeout(0.1)
            self._thread = threading.Thread(target=self._loop, daemon=True)
            self._thread.start()
            return self
        except BaseException:
            if self._server: self._server.close()
            self._lock.__exit__(None,None,None); self._lock=None
            raise

    def stop(self):
        self._stop.set()
        if self._server: self._server.close()
        if self._thread: self._thread.join(2)
        if self.socket_path.exists() and self.socket_path.is_socket(): self.socket_path.unlink()
        if self._lock: self._lock.__exit__(None,None,None); self._lock=None
    def __enter__(self): return self.start()
    def __exit__(self,*args): self.stop()

def permit_request(path, action, *, scope, target_uid=None, permit=None, timeout=2.0):
    with socket.socket(socket.AF_UNIX) as sock:
        sock.settimeout(timeout)
        sock.connect(str(path))
        sock.sendall((json.dumps({'action':action,'scope':scope,'target_uid':target_uid,'permit':permit})+'\n').encode())
        data=b''
        while b'\n' not in data:
            part=sock.recv(4096)
            if not part or len(data)+len(part)>8192: raise AdmissionError('invalid permit response')
            data+=part
        response=json.loads(data.split(b'\n',1)[0])
        if not response.get('ok'): raise AdmissionError(response.get('message','permit request rejected'))
        return response['result']
