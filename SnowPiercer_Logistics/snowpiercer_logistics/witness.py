"""Independent, single-writer witness authority for a POSIX Unix socket.
A distinct UID and protected directory are deployment requirements, not provided by this module.
"""
import hashlib
import json
import os
from pathlib import Path
import socket
import stat
import threading
import uuid
from .secure import AdmissionError, _peer_uid, _safe_dir, exclusive_lock


def _atomic(path, data):
    path=Path(path)
    temp=path.with_name(path.name+'.'+uuid.uuid4().hex+'.tmp')
    fd=os.open(str(temp), os.O_CREAT|os.O_EXCL|os.O_WRONLY, 0o600)
    try:
        with os.fdopen(fd,'w') as f:
            json.dump(data,f,sort_keys=True); f.flush(); os.fsync(f.fileno())
        os.replace(temp,path)
        fd=os.open(str(path.parent),os.O_RDONLY)
        try: os.fsync(fd)
        finally: os.close(fd)
    finally:
        temp.unlink(missing_ok=True)

class WitnessAuthority:
    def __init__(self,root,service_uid,*,timeout=1.0):
        self.root=_safe_dir(root)
        self.service_uid=int(service_uid)
        self.timeout=timeout
        self.anchor=self.root/'monotonic.json'
        self.socket_path=self.root/'witness.sock'
        self.lock_path=self.root/'witness.lock'
        self._lock=None; self._server=None; self._thread=None
        self._stop=threading.Event()

    def _read(self):
        if self.anchor.is_symlink(): raise AdmissionError('witness anchor symlink')
        if not self.anchor.exists(): return None
        st=self.anchor.stat()
        if not stat.S_ISREG(st.st_mode) or st.st_uid!=os.geteuid() or st.st_mode & 0o077 or st.st_nlink!=1:
            raise AdmissionError('unsafe witness anchor')
        return json.loads(self.anchor.read_text())

    def _handle(self,conn):
        conn.settimeout(self.timeout)
        if _peer_uid(conn)!=self.service_uid: raise AdmissionError('witness UID rejected')
        data=b''
        while b'\n' not in data:
            part=conn.recv(4096)
            if not part or len(data)+len(part)>8192: raise AdmissionError('invalid witness request')
            data+=part
        req=json.loads(data.split(b'\n',1)[0]); action=req.get('action')
        current=self._read()
        if action=='read': return current
        if action!='cas': raise AdmissionError('invalid witness action')
        before=req.get('before'); after=req.get('after')
        if current!=before: raise AdmissionError('witness CAS conflict')
        if not isinstance(after,dict) or type(after.get('events')) is not int or not isinstance(after.get('head_hash'),str):
            raise AdmissionError('invalid witness state')
        if current is None:
            if after['events']!=0: raise AdmissionError('non-genesis initialization')
        elif after['events']!=current['events']+1:
            raise AdmissionError('witness monotonicity violation')
        _atomic(self.anchor,after)
        return after

    def _loop(self):
        while not self._stop.is_set():
            try: conn,_=self._server.accept()
            except socket.timeout: continue
            except OSError: break
            with conn:
                try: reply={'ok':True,'result':self._handle(conn)}
                except Exception as exc: reply={'ok':False,'error':type(exc).__name__,'message':str(exc)}
                try: conn.sendall((json.dumps(reply)+'\n').encode())
                except OSError: pass

    def start(self):
        self._lock=exclusive_lock(self.lock_path); self._lock.__enter__()
        try:
            if self.socket_path.exists() or self.socket_path.is_symlink(): raise AdmissionError('witness socket exists')
            self._read()
            self._server=socket.socket(socket.AF_UNIX); self._server.bind(str(self.socket_path))
            os.chmod(self.socket_path,0o600)
            self._server.listen(8); self._server.settimeout(0.1)
            self._thread=threading.Thread(target=self._loop,daemon=True); self._thread.start()
        except BaseException:
            if self._server: self._server.close()
            self._lock.__exit__(None,None,None); self._lock=None
            raise
        return self

    def stop(self):
        self._stop.set()
        if self._server: self._server.close()
        if self._thread: self._thread.join(2)
        if self.socket_path.exists() and stat.S_ISSOCK(self.socket_path.lstat().st_mode): self.socket_path.unlink()
        if self._lock: self._lock.__exit__(None,None,None); self._lock=None
    def __enter__(self): return self.start()
    def __exit__(self,*args): self.stop()

def witness_request(path,action,*,before=None,after=None,timeout=1.0):
    with socket.socket(socket.AF_UNIX) as sock:
        sock.settimeout(timeout); sock.connect(str(path))
        sock.sendall((json.dumps({'action':action,'before':before,'after':after})+'\n').encode())
        data=b''
        while b'\n' not in data:
            part=sock.recv(4096)
            if not part or len(data)+len(part)>8192: raise AdmissionError('witness response truncated')
            data+=part
        reply=json.loads(data.split(b'\n',1)[0])
        if not reply['ok']: raise AdmissionError('witness rejected: '+reply.get('message',''))
        return reply['result']
