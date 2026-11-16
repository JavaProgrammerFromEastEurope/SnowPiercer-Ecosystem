"""ISLAND-GEO-008: external witness CAS and recoverable local admission.
Experimental protocol; independent security requires separate OS principals and immutable provisioning.
"""
import json, os, socket, sqlite3, struct, hashlib, fcntl
from pathlib import Path
from contextlib import contextmanager
from .geotechnics import GeotechnicalInputError

class AdmissionDenied(GeotechnicalInputError): pass

def digest(payload):
    if type(payload) is not bytes: raise AdmissionDenied('bytes required')
    return hashlib.sha256(b'ISLAND-GEO-008\0'+payload).hexdigest()

def _validate_record(record):
    if type(record) is not dict or set(record)!={'sequence','previous','digest'}: raise AdmissionDenied('record shape')
    if type(record['sequence']) is not int or record['sequence']<1: raise AdmissionDenied('sequence')
    if type(record['previous']) is not str or len(record['previous'])!=64 or type(record['digest']) is not str or len(record['digest'])!=64: raise AdmissionDenied('digest shape')
    for k in ('previous','digest'):
        if any(c not in '0123456789abcdef' for c in record[k]): raise AdmissionDenied('hex')

GENESIS='0'*64

def chain(previous,sequence,payload_hash):
    if type(sequence) is not int or sequence<1: raise AdmissionDenied('sequence')
    return hashlib.sha256(f'ISLAND-CHAIN-008:{sequence}:{previous}:{payload_hash}'.encode()).hexdigest()

class WitnessStore:
    """Anchor is stored outside the admission database. Do not share its writable UID."""
    def __init__(self,path): self.path=Path(path)
    def execute(self,operation,record=None):
        db=sqlite3.connect(self.path,timeout=5,isolation_level=None)
        try:
            db.execute('BEGIN IMMEDIATE')
            db.execute('CREATE TABLE IF NOT EXISTS anchor (id INTEGER PRIMARY KEY CHECK(id=1), sequence INTEGER NOT NULL, digest TEXT NOT NULL)')
            db.execute('INSERT OR IGNORE INTO anchor VALUES (1,0,?)',(GENESIS,))
            seq,head=db.execute('SELECT sequence,digest FROM anchor WHERE id=1').fetchone()
            if operation=='read': result={'sequence':seq,'digest':head}
            elif operation=='cas':
                _validate_record(record)
                if record['sequence']==seq and record['digest']==head:
                    result={'sequence':seq,'digest':head} # idempotent retry only for exact same head
                elif record['sequence']==seq+1 and record['previous']==head:
                    db.execute('UPDATE anchor SET sequence=?,digest=? WHERE id=1',(record['sequence'],record['digest']))
                    result={'sequence':record['sequence'],'digest':record['digest']}
                else: raise AdmissionDenied('witness CAS mismatch')
            else: raise AdmissionDenied('unknown operation')
            db.execute('COMMIT'); return result
        except BaseException:
            if db.in_transaction: db.execute('ROLLBACK')
            raise
        finally: db.close()

def _receive(sock):
    sock.settimeout(3)
    size=struct.unpack('!I',_read_exact(sock,4))[0]
    if size>8192: raise AdmissionDenied('oversize IPC')
    return json.loads(_read_exact(sock,size).decode())

def _read_exact(sock,n):
    data=bytearray()
    while len(data)<n:
        part=sock.recv(n-len(data))
        if not part: raise AdmissionDenied('truncated IPC')
        data.extend(part)
    return bytes(data)

def _send(sock,obj):
    raw=json.dumps(obj,sort_keys=True,separators=(',',':')).encode()
    sock.sendall(struct.pack('!I',len(raw))+raw)

class WitnessServer:
    def __init__(self,socket_path,db_path,allowed_uids):
        self.socket_path=Path(socket_path); self.store=WitnessStore(db_path); self.allowed_uids=frozenset(allowed_uids)
    def serve(self,ready=None,limit=None):
        if self.socket_path.exists(): raise AdmissionDenied('socket already exists')
        srv=socket.socket(socket.AF_UNIX,socket.SOCK_STREAM)
        try:
            srv.bind(str(self.socket_path)); os.chmod(self.socket_path,0o660); srv.listen(16); srv.settimeout(.5)
            if ready: ready.set()
            count=0
            while limit is None or count<limit:
                try: client,_=srv.accept()
                except socket.timeout: continue
                with client:
                    count+=1
                    try:
                        if not hasattr(socket,'SO_PEERCRED'): raise AdmissionDenied('SO_PEERCRED unavailable')
                        pid,uid,gid=struct.unpack('3i',client.getsockopt(socket.SOL_SOCKET,socket.SO_PEERCRED,12))
                        if uid not in self.allowed_uids: raise AdmissionDenied('UID rejected')
                        req=_receive(client)
                        if type(req) is not dict or set(req)-{'operation','record'}: raise AdmissionDenied('invalid request')
                        result=self.store.execute(req.get('operation'),req.get('record'))
                        _send(client,{'ok':True,'result':result})
                    except (AdmissionDenied,ValueError,KeyError,sqlite3.Error,OSError) as e:
                        try: _send(client,{'ok':False,'reason':str(e)})
                        except OSError: pass
        finally:
            srv.close()
            if self.socket_path.exists() and self.socket_path.is_socket(): self.socket_path.unlink()

class WitnessClient:
    def __init__(self,path): self.path=str(path)
    def execute(self,operation,record=None):
        with socket.socket(socket.AF_UNIX,socket.SOCK_STREAM) as sock:
            sock.settimeout(3); sock.connect(self.path)
            _send(sock,{'operation':operation,'record':record})
            result=_receive(sock)
            if not result['ok']: raise AdmissionDenied(result['reason'])
            return result['result']

@contextmanager
def _lock(path):
    fd=os.open(str(path),os.O_CREAT|os.O_RDWR|os.O_NOFOLLOW,0o600)
    try:
        fcntl.flock(fd,fcntl.LOCK_EX)
        yield
    finally: fcntl.flock(fd,fcntl.LOCK_UN); os.close(fd)

class AnchoredAdmission:
    """Local phase journal + independent witness CAS; blocks ambiguous crash states.
    Single writer through flock; never automatically advances an uncommitted local record.
    """
    def __init__(self,db_path,witness):
        self.db_path=Path(db_path); self.witness=witness
        self.lock_path=self.db_path.with_suffix('.lock')
    def _connect(self):
        db=sqlite3.connect(self.db_path,timeout=5,isolation_level=None)
        db.execute('PRAGMA synchronous=FULL')
        db.execute('PRAGMA journal_mode=DELETE')
        db.execute('CREATE TABLE IF NOT EXISTS accepted (sequence INTEGER PRIMARY KEY,digest TEXT UNIQUE NOT NULL,payload_hash TEXT NOT NULL)')
        db.execute('CREATE TABLE IF NOT EXISTS phase (id INTEGER PRIMARY KEY CHECK(id=1),sequence INTEGER NOT NULL, previous TEXT NOT NULL,digest TEXT NOT NULL,payload_hash TEXT NOT NULL)')
        return db
    def _local(self,db):
        row=db.execute('SELECT sequence,digest FROM accepted ORDER BY sequence DESC LIMIT 1').fetchone()
        return {'sequence':row[0],'digest':row[1]} if row else {'sequence':0,'digest':GENESIS}
    def _reconcile(self,db):
        local=self._local(db); remote=self.witness.execute('read'); pending=db.execute('SELECT sequence,previous,digest,payload_hash FROM phase WHERE id=1').fetchone()
        if pending:
            seq,prev,head,ph=pending
            if remote=={'sequence':seq,'digest':head} and local=={'sequence':seq-1,'digest':prev}:
                db.execute('BEGIN IMMEDIATE')
                try:
                    db.execute('INSERT INTO accepted VALUES (?,?,?)',(seq,head,ph)); db.execute('DELETE FROM phase WHERE id=1'); db.execute('COMMIT')
                except BaseException:
                    if db.in_transaction: db.execute('ROLLBACK')
                    raise
                local=self._local(db)
            elif remote==local and seq==local['sequence']+1 and prev==local['digest']:
                # No witness commit: abort uncommitted intent.
                db.execute('DELETE FROM phase WHERE id=1')
            else: raise AdmissionDenied('ambiguous phase state')
        if local!=remote: raise AdmissionDenied('rollback, witness divergence or lost local history')
        return local
    def recover(self):
        with _lock(self.lock_path):
            db=self._connect()
            try: return self._reconcile(db)
            finally: db.close()
    def admit(self,payload,crash_at=None):
        ph=digest(payload)
        with _lock(self.lock_path):
            db=self._connect()
            try:
                local=self._reconcile(db); seq=local['sequence']+1
                head=chain(local['digest'],seq,ph)
                db.execute('BEGIN IMMEDIATE')
                try:
                    db.execute('INSERT INTO phase VALUES (1,?,?,?,?)',(seq,local['digest'],head,ph))
                    db.execute('COMMIT')
                except BaseException:
                    if db.in_transaction: db.execute('ROLLBACK')
                    raise
                if crash_at=='phase': os._exit(91)
                self.witness.execute('cas',{'sequence':seq,'previous':local['digest'],'digest':head})
                if crash_at=='witness': os._exit(92)
                db.execute('BEGIN IMMEDIATE')
                try:
                    db.execute('INSERT INTO accepted VALUES (?,?,?)',(seq,head,ph))
                    db.execute('DELETE FROM phase WHERE id=1'); db.execute('COMMIT')
                except BaseException:
                    if db.in_transaction: db.execute('ROLLBACK')
                    raise
                if crash_at=='local': os._exit(93)
                return {'admitted':True,'sequence':seq,'digest':head,'engineering_approval':'BLOCKED/NO-GO'}
            finally: db.close()
