"""AI-CORE-007: local Unix socket admission service and recovery authorization.

OS access isolation requires a separately provisioned service UID and filesystem ACLs.
"""
import hashlib
import hmac
import json
import os
import socket
import sqlite3
import struct
import threading
from pathlib import Path
from .lifecycle import RecoveryRequired
from .admission import AdmissionRejected

MAX_REQUEST = 65536


def _wire(obj):
    return json.dumps(obj, sort_keys=True, separators=(',', ':'), allow_nan=False).encode('utf-8')


def recovery_permit(secret, token_id, seq, head):
    """Mint externally: never expose the recovery secret to an untrusted client."""
    if not isinstance(secret, bytes) or len(secret) < 32: raise ValueError('recovery secret')
    if not isinstance(token_id,str) or not (8 <= len(token_id) <= 128): raise ValueError('token id')
    if type(seq) is not int or seq < 0 or not isinstance(head,str) or len(head)!=64: raise ValueError('checkpoint')
    payload={'id':token_id,'seq':seq,'head':head}
    return dict(payload, mac=hmac.new(secret,_wire(payload),hashlib.sha256).hexdigest())


class RecoveryAuthorizer:
    """Single-use HMAC permits, tied to checkpoint and persisted in the replay DB."""
    def __init__(self, gateway, secret):
        if not isinstance(secret,bytes) or len(secret)<32: raise ValueError('secret')
        self.gateway=gateway; self.secret=secret
        with gateway.store._lock:
            gateway.store._db.execute('CREATE TABLE IF NOT EXISTS ipc_recovery_used (id TEXT PRIMARY KEY)')

    def reconcile(self, permit):
        if not isinstance(permit,dict) or set(permit)!={'id','seq','head','mac'}: raise RecoveryRequired('RECOVERY_PERMIT_INVALID')
        try:
            expected=recovery_permit(self.secret,permit['id'],permit['seq'],permit['head'])
            if not isinstance(permit['mac'],str) or not hmac.compare_digest(expected['mac'],permit['mac']): raise ValueError('mac')
        except (ValueError,TypeError,KeyError) as exc: raise RecoveryRequired('RECOVERY_PERMIT_INVALID') from exc
        gw=self.gateway
        with gw.manager.lock,gw.store._lock:
            if gw.checkpoint.read()!=(permit['seq'],permit['head']): raise RecoveryRequired('RECOVERY_PERMIT_STALE')
            db=gw.store._db
            if db.execute('SELECT 1 FROM ipc_recovery_used WHERE id=?',(permit['id'],)).fetchone(): raise RecoveryRequired('RECOVERY_PERMIT_REPLAY')
            # No database/checkpoint atomic commit exists; a crash after reconcile
            # but before recording consumption is fenced by the checkpoint mismatch.
            result=gw.reconcile(authorized=True)
            db.execute('INSERT INTO ipc_recovery_used VALUES (?)',(permit['id'],))
            return result


class AdmissionIPCServer:
    """Unix-domain server. Caller supplies an already configured anchored gateway.

    The service must run as a separate UID and own the DB and anchor directories;
    socket mode and peer UID checks alone are not a filesystem sandbox.
    """
    def __init__(self, gateway, socket_path, *, allowed_uids, recovery_secret, recovery_uids=()):
        if not hasattr(socket,'SO_PEERCRED'): raise RuntimeError('SO_PEERCRED unsupported')
        if not allowed_uids or any(type(x) is not int or x<0 for x in allowed_uids): raise ValueError('allowed_uids')
        self.gateway=gateway; self.path=Path(socket_path)
        self.allowed_uids=frozenset(allowed_uids); self.recovery_uids=frozenset(recovery_uids)
        self.recovery=RecoveryAuthorizer(gateway,recovery_secret)
        self._stop=threading.Event(); self._sock=None

    def serve(self, *, ready=None):
        if self.path.exists(): raise RuntimeError('socket path exists; refuse unlink')
        sock=socket.socket(socket.AF_UNIX,socket.SOCK_STREAM); self._sock=sock
        try:
            sock.bind(str(self.path)); os.chmod(self.path,getattr(self,"socket_mode",0o600))
            if hasattr(self,"socket_gid"): os.chown(self.path,-1,self.socket_gid)
            sock.listen(16); sock.settimeout(0.2)
            if ready is not None: ready.set()
            while not self._stop.is_set():
                try: conn,_=sock.accept()
                except socket.timeout: continue
                with conn:
                    conn.settimeout(3)
                    try:
                        pid,uid,gid=struct.unpack('3i',conn.getsockopt(socket.SOL_SOCKET,socket.SO_PEERCRED,12))
                        if uid not in self.allowed_uids: raise PermissionError('PEER_UID_DENIED')
                        data=bytearray()
                        while b'\n' not in data and len(data)<=MAX_REQUEST:
                            chunk=conn.recv(min(4096,MAX_REQUEST+1-len(data)))
                            if not chunk: break
                            data.extend(chunk)
                        if len(data)>MAX_REQUEST or b'\n' not in data: raise ValueError('REQUEST_SIZE_OR_FRAMING')
                        request=json.loads(bytes(data).split(b'\n',1)[0])
                        if not isinstance(request,dict): raise ValueError('REQUEST_INVALID')
                        if request.get('op')=='admit' and set(request)=={'op','envelope'}:
                            result=self.gateway.admit(request['envelope'])
                            response={'ok':True,'decision':str(result)}
                        elif request.get('op')=='verify' and set(request)=={'op'}:
                            seq,head=self.gateway.verify(); response={'ok':True,'seq':seq,'head':head}
                        elif request.get('op')=='recover' and set(request)=={'op','permit'}:
                            if uid not in self.recovery_uids: raise PermissionError('RECOVERY_UID_DENIED')
                            seq,head=self.recovery.reconcile(request['permit']); response={'ok':True,'seq':seq,'head':head}
                        else: raise ValueError('OPERATION_DENIED')
                    except (ValueError,PermissionError,RecoveryRequired,AdmissionRejected,sqlite3.Error,KeyError,TypeError) as exc:
                        response={'ok':False,'error':type(exc).__name__}
                    conn.sendall(_wire(response)+b'\n')
        finally:
            sock.close(); self._sock=None
            try: self.path.unlink()
            except FileNotFoundError: pass

    def stop(self): self._stop.set()


def ipc_request(path, request, *, timeout=3):
    data=_wire(request)+b'\n'
    if len(data)>MAX_REQUEST: raise ValueError('request too large')
    with socket.socket(socket.AF_UNIX,socket.SOCK_STREAM) as sock:
        sock.settimeout(timeout); sock.connect(str(path)); sock.sendall(data)
        reply=bytearray()
        while b'\n' not in reply and len(reply)<=MAX_REQUEST:
            part=sock.recv(4096)
            if not part: break
            reply.extend(part)
        if b'\n' not in reply or len(reply)>MAX_REQUEST: raise RuntimeError('invalid IPC response')
        return json.loads(bytes(reply).split(b'\n',1)[0])
