"""POSIX Unix-socket admission; identity is kernel-derived, never supplied by clients.
No hardware actuation; local same-host security boundary only.
"""
import contextlib
import fcntl
import hashlib
import json
import os
from pathlib import Path
import socket
import sqlite3
import stat
import struct
import threading
import time
import uuid
from .core import (LogisticsLedger, Principal, Container, Location, Cargo, CargoState,
                   Mission, MissionState, Transfer, AuthorizationError, InvariantError, ConflictError)

class AdmissionError(RuntimeError): pass

@contextlib.contextmanager
def exclusive_lock(path):
    path = Path(path)
    if path.is_symlink(): raise AdmissionError("symlink lock")
    fd = os.open(str(path), os.O_CREAT | os.O_RDWR | getattr(os, 'O_NOFOLLOW', 0), 0o600)
    try:
        s = os.fstat(fd)
        if not stat.S_ISREG(s.st_mode) or s.st_uid != os.geteuid() or s.st_nlink != 1 or s.st_mode & 0o077:
            raise AdmissionError("unsafe lock")
        
        try: fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc: raise AdmissionError("service lock busy") from exc
        yield
    finally:
        os.close(fd)

def _safe_dir(root):
    p = Path(root)
    if p.is_symlink(): raise AdmissionError("symlink directory")
    p.mkdir(mode=0o700, parents=True, exist_ok=True)
    s = p.stat()
    if not stat.S_ISDIR(s.st_mode) or s.st_uid != os.geteuid() or s.st_mode & 0o077:
        raise AdmissionError("unsafe directory ownership/mode")
    return p

def _peer_uid(conn):
    if hasattr(socket, 'SO_PEERCRED'):
        return struct.unpack('3i', conn.getsockopt(socket.SOL_SOCKET, socket.SO_PEERCRED, 12))[1]
    if hasattr(conn, 'getpeereid'):
        return conn.getpeereid()[0]
    raise AdmissionError("kernel peer credentials unavailable")

def _digest(data):
    return hashlib.sha256(json.dumps(data, sort_keys=True, separators=(',', ':')).encode()).hexdigest()

class SecureLogisticsService:
    """Single writer service. UID roles are configured by privileged operator, not IPC."""
    def __init__(self, root, uid_roles, *, timeout=2.0):
        self.root = _safe_dir(root)
        self.uid_roles = {int(k): v for k,v in uid_roles.items()}
        if any(v not in ('admin','operator','auditor') for v in self.uid_roles.values()):
            raise ValueError('invalid role')
        self.timeout = timeout
        self.socket_path = self.root/'service.sock'
        self.lock_path = self.root/'service.lock'
        self.db_path = self.root/'ledger.sqlite'
        self.anchor_path = self.root/'checkpoint.json'
        self.phase_path = self.root/'phase.json'
        self._server = None
        self._stop = threading.Event()
        self._thread = None
        self._db = None
        self._poisoned = False
        self._lifetime_lock = None

    def _check_files(self):
        for p in (self.db_path, self.anchor_path, self.root/'ledger.sqlite-wal', self.root/'ledger.sqlite-shm', self.phase_path):
            if p.is_symlink(): raise AdmissionError('symlink file: '+p.name)
            if p.exists():
                s = p.stat()
                if not stat.S_ISREG(s.st_mode) or s.st_uid != os.geteuid() or s.st_nlink != 1 or s.st_mode & 0o077:
                    raise AdmissionError('unsafe file: '+p.name)

    def _checkpoint(self):
        state = self._db.verify(Principal('service','auditor'))
        return {'events':state['events'], 'head_hash':state['head_hash']}

    def _read_anchor(self):
        if not self.anchor_path.exists(): return None
        with self.anchor_path.open('r') as f: return json.load(f)

    def _write_anchor(self, value):
        self._atomic_json(self.anchor_path, value)

    def _atomic_json(self, destination, value):
        tmp = self.root/(destination.name+'.'+uuid.uuid4().hex+'.tmp')
        fd = os.open(str(tmp), os.O_WRONLY|os.O_CREAT|os.O_EXCL, 0o600)
        try:
            with os.fdopen(fd,'w') as f:
                json.dump(value,f,sort_keys=True); f.flush(); os.fsync(f.fileno())
            os.replace(tmp,destination)
            dfd=os.open(str(self.root),os.O_RDONLY)
            try: os.fsync(dfd)
            finally: os.close(dfd)
        finally:
            if tmp.exists(): tmp.unlink()

    def _reconcile(self):
        anchor = self._read_anchor()
        current = self._checkpoint()
        if not self.phase_path.exists():
            if anchor != current:
                raise AdmissionError('checkpoint mismatch without authenticated phase')
            return
        with self.phase_path.open('r') as f:
            phase = json.load(f)
        if set(phase) != {'before', 'key', 'uid'} or not isinstance(phase['key'], str):
            raise AdmissionError('invalid phase journal')
        if anchor != phase['before']:
            raise AdmissionError('phase previous anchor mismatch')
        if current == anchor:
            # Command did not commit, or replayed an existing idempotency key.
            self.phase_path.unlink()
            return
        if current['events'] != anchor['events'] + 1:
            raise AdmissionError('unexpected event delta')
        last = self._db._db.execute('SELECT command_key,previous_hash,event_hash FROM events ORDER BY seq DESC LIMIT 1').fetchone()
        if not last or last[0] != phase['key'] or last[1] != anchor['head_hash'] or last[2] != current['head_hash']:
            raise AdmissionError('phase does not match committed event')
        self._write_anchor(current)
        self.phase_path.unlink()

    def _admit(self):
        self._check_files()
        self._db = LogisticsLedger(self.db_path)
        # SQLite may have just created files; lock-down before serving requests.
        for suffix in ('','-wal','-shm'):
            p=Path(str(self.db_path)+suffix)
            if p.exists(): os.chmod(p,0o600)
        self._db._db.execute('CREATE TABLE IF NOT EXISTS recovery_permits(token_hash TEXT PRIMARY KEY, uid INTEGER NOT NULL, used INTEGER NOT NULL DEFAULT 0)')
        current=self._checkpoint()
        anchor=self._read_anchor()
        if anchor is None:
            # An existing populated DB with no anchor must not silently become a new genesis.
            if current['events'] != 0 or self.phase_path.exists(): raise AdmissionError('missing anchor or orphaned phase')
            self._write_anchor(current)
        else:
            self._reconcile()

    def start(self):
        if self._server: raise AdmissionError('already started')
        # Retain the flock for the entire service lifetime, not only startup.
        self._lifetime_lock = exclusive_lock(self.lock_path)
        self._lifetime_lock.__enter__()
        try:
            if self.socket_path.is_symlink(): raise AdmissionError('socket symlink')
            if self.socket_path.exists():
                s=self.socket_path.lstat()
                if not stat.S_ISSOCK(s.st_mode) or s.st_uid != os.geteuid(): raise AdmissionError('unsafe socket')
                probe=socket.socket(socket.AF_UNIX)
                probe.settimeout(0.3)
                try:
                    probe.connect(str(self.socket_path))
                except (ConnectionRefusedError, FileNotFoundError):
                    self.socket_path.unlink()
                else:
                    raise AdmissionError('active service already running')
                finally: probe.close()
            try:
                self._admit()
                self._server=socket.socket(socket.AF_UNIX)
                self._server.bind(str(self.socket_path))
                os.chmod(self.socket_path,0o600)
                self._server.listen(16)
                self._server.settimeout(0.2)
            except BaseException:
                if self._db: self._db.close(); self._db=None
                if self._server: self._server.close(); self._server=None
                raise
        except BaseException:
            self._lifetime_lock.__exit__(None,None,None)
            self._lifetime_lock = None
            raise
        self._thread=threading.Thread(target=self._loop,daemon=True)
        self._thread.start()
        return self

    def _loop(self):
        while not self._stop.is_set():
            try: conn,_=self._server.accept()
            except socket.timeout: continue
            except OSError: break
            with conn:
                conn.settimeout(self.timeout)
                try:
                    uid=_peer_uid(conn)
                    if uid not in self.uid_roles: raise AuthorizationError('unmapped peer UID')
                    buf=b''
                    while b'\n' not in buf:
                        chunk=conn.recv(4096)
                        if not chunk: raise AdmissionError('truncated request')
                        buf+=chunk
                        if len(buf)>65536: raise AdmissionError('oversize request')
                    req=json.loads(buf.split(b'\n',1)[0]); result=self._dispatch(uid,req)
                    reply={'ok':True,'result':result}
                except (Exception,) as exc:
                    reply={'ok':False,'error':type(exc).__name__,'message':str(exc)}
                try: conn.sendall((json.dumps(reply,sort_keys=True)+'\n').encode())
                except OSError: pass

    def _dispatch(self, uid, req):
        if self._poisoned: raise AdmissionError('service quarantined after checkpoint failure')
        self._check_files()
        if not isinstance(req,dict): raise AdmissionError('invalid request')
        action=req.get('action'); args=req.get('args',{})
        if not isinstance(args,dict): raise AdmissionError('invalid arguments')
        principal=Principal('uid:'+str(uid),self.uid_roles[uid])
        if action=='verify': return self._db.verify(principal)
        if action=='get_cargo':
            c=self._db.get_cargo(principal,args['cargo_id'])
            return dict(vars(c),state=c.state.value) if c else None
        if action=='issue_permit':
            if principal.role!='admin': raise AuthorizationError('admin only')
            target=int(args['uid']); token=uuid.uuid4().hex+uuid.uuid4().hex
            self._db._db.execute('INSERT INTO recovery_permits(token_hash,uid) VALUES(?,?)',(hashlib.sha256(token.encode()).hexdigest(),target))
            return {'permit':token}
        if action=='recover':
            token=args['permit']; digest=hashlib.sha256(token.encode()).hexdigest()
            self._db._db.execute('BEGIN IMMEDIATE')
            try:
                cur=self._db._db.execute('UPDATE recovery_permits SET used=1 WHERE token_hash=? AND uid=? AND used=0',(digest,uid))
                if cur.rowcount!=1: raise AuthorizationError('invalid/consumed permit')
                self._db._db.execute('COMMIT')
            except BaseException:
                self._db._db.execute('ROLLBACK'); raise
            # Recovery does not repair mismatched checkpoints; a permit only records admission.
            if self._read_anchor()!=self._checkpoint(): raise AdmissionError('checkpoint mismatch')
            return {'recovered':True}
        methods={'add_container':Container,'add_location':Location,'register_cargo':Cargo,'create_mission':Mission,'record_transfer':Transfer}
        if action in methods or action in ('transition_cargo','transition_mission'):
            if self.phase_path.exists(): raise AdmissionError('pending recovery phase')
            self._atomic_json(self.phase_path, {'before':self._checkpoint(), 'key':args['key'], 'uid':uid})
        if action in methods:
            item=methods[action](**args['item'])
            fn=getattr(self._db,action)
            try: result=fn(principal,args['key'],item)
            except BaseException:
                if self._checkpoint() == self._read_anchor(): self.phase_path.unlink(missing_ok=True)
                raise
        elif action in ('transition_cargo','transition_mission'):
            enum=CargoState if action=='transition_cargo' else MissionState
            identifier='cargo_id' if action=='transition_cargo' else 'mission_id'
            try: result=getattr(self._db,action)(principal,args['key'],args[identifier],enum(args['target']))
            except BaseException:
                if self._checkpoint() == self._read_anchor(): self.phase_path.unlink(missing_ok=True)
                raise
        else: raise AdmissionError('unknown action')
        # Ledger commit precedes anchor fsync; an authenticated local phase allows bounded roll-forward.
        try:
            self._write_anchor(self._checkpoint())
            self.phase_path.unlink(missing_ok=True)
        except BaseException:
            self._poisoned=True
            raise
        return result

    def stop(self):
        self._stop.set()
        if self._server: self._server.close()
        if self._thread: self._thread.join(timeout=3)
        if self._db: self._db.close(); self._db=None
        if self.socket_path.exists() and stat.S_ISSOCK(self.socket_path.lstat().st_mode): self.socket_path.unlink()
        self._server=None
        if self._lifetime_lock is not None:
            self._lifetime_lock.__exit__(None,None,None)
            self._lifetime_lock=None

    def __enter__(self): return self.start()
    def __exit__(self,*args): self.stop()

def request(socket_path, action, args=None, timeout=2.0):
    with socket.socket(socket.AF_UNIX) as s:
        s.settimeout(timeout)
        s.connect(str(socket_path))
        s.sendall((json.dumps({'action':action,'args':args or {}},sort_keys=True)+'\n').encode())
        data=b''
        while b'\n' not in data:
            part=s.recv(4096)
            if not part: raise AdmissionError('closed response')
            data+=part
            if len(data)>65536: raise AdmissionError('oversize response')
        return json.loads(data.split(b'\n',1)[0])
