"""TrainOS v107 peer-authenticated Unix IPC admission broker (deny-only).

SO_PEERCRED is kernel-derived; JSON 'uid' is not an identity. Each (UID, nonce)
may be processed once, including denied requests. No commands are accepted.
Until the systemd-managed cgroup authority has a verified IPC integration, the
broker MUST DENY execution. The broker never starts a Runner or authority.

This module is a tested prototype of authentication/replay fencing, not a
production-certified broker or evidence that legacy API calls are OS-fenced.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import re
import socket
import sqlite3
import stat
import struct
import sys
import time

MAX_PACKET=2048
NONCE=re.compile(r'^[0-9a-f]{32,64}$')


def peer_uid(sock: socket.socket) -> tuple[int,int,int]:
    if not hasattr(socket,'SO_PEERCRED'):
        raise RuntimeError('Linux SO_PEERCRED is mandatory')
    return struct.unpack('3i',sock.getsockopt(socket.SOL_SOCKET,socket.SO_PEERCRED,12))


def private_root(path: Path, *, create: bool = False) -> None:
    if not path.is_absolute() or path.is_symlink():
        raise PermissionError('broker root must be absolute non-symlink')
    if create:
        path.mkdir(mode=0o711, parents=False, exist_ok=False)
    data=path.lstat()
    if not stat.S_ISDIR(data.st_mode) or data.st_uid != os.geteuid() or data.st_mode & 0o066:
        raise PermissionError('broker root must be owned by server UID, not writable by clients')
    # Directory must be searchable by clients but not writable by clients.
    if not data.st_mode & stat.S_IXOTH:
        raise PermissionError('client search permission missing')


def _db_open(path: Path) -> sqlite3.Connection:
    if path.exists() or path.is_symlink():
        st=path.lstat()
        if not stat.S_ISREG(st.st_mode) or st.st_uid!=os.geteuid() or st.st_mode & 0o077:
            raise PermissionError('unsafe SQLite admission journal owner/mode')
    if not path.exists():
        fd=os.open(path,os.O_CREAT|os.O_EXCL|os.O_WRONLY|os.O_NOFOLLOW,0o600)
        os.close(fd)
    db=sqlite3.connect(path,timeout=1.0)
    try:
        os.chmod(path,0o600)
        db.execute('PRAGMA busy_timeout=1000')
        db.execute('CREATE TABLE IF NOT EXISTS requests (uid INTEGER NOT NULL, nonce TEXT NOT NULL, operation TEXT NOT NULL, decision TEXT NOT NULL, PRIMARY KEY(uid,nonce))')
        db.commit()
        return db
    except BaseException:
        db.close()
        raise


def decide(db: sqlite3.Connection, uid: int, allowed_uid: int, payload: bytes) -> dict:
    """Deny by default. Replay checks are durable within a protected DB."""
    if uid != allowed_uid:
        return {'status':'DENIED','reason':'INVALID_PEER'}
    if len(payload)>MAX_PACKET:
        return {'status':'DENIED','reason':'OVERSIZE'}
    try:
        req=json.loads(payload)
    except (ValueError,UnicodeDecodeError):
        return {'status':'DENIED','reason':'BAD_JSON'}
    if not isinstance(req,dict) or set(req)-{'operation','nonce','uid'} or req.get('operation')!='start' or not isinstance(req.get('nonce'),str) or not NONCE.fullmatch(req['nonce']):
        return {'status':'DENIED','reason':'BAD_REQUEST'}
    # Ignore caller supplied UID. A mismatch is suspicious even when caller
    # otherwise authenticates: reject instead of trusting/confusing identity.
    if 'uid' in req and req['uid']!=uid:
        return {'status':'DENIED','reason':'UID_SPOOF'}
    try:
        db.execute('BEGIN IMMEDIATE')
        old=db.execute('SELECT decision FROM requests WHERE uid=? AND nonce=?', (uid,req['nonce'])).fetchone()
        if old:
            db.rollback()
            return {'status':'DENIED','reason':'REPLAY'}
        db.execute('INSERT INTO requests(uid,nonce,operation,decision) VALUES (?,?,?,?)', (uid,req['nonce'],'start','CONTAINMENT_NOT_CERTIFIED'))
        db.commit()
    except (sqlite3.Error,OSError):
        db.rollback()
        return {'status':'DENIED','reason':'JOURNAL_UNAVAILABLE'}
    return {'status':'DENIED','reason':'CONTAINMENT_NOT_CERTIFIED'}


def serve(root: Path, allowed_uid: int, max_requests: int = 0, ready_fd: int | None = None,
          accept_timeout: float = 5.0) -> dict:
    """Protected socket owned by server. No production execution capability."""
    private_root(root)
    if allowed_uid<=0 or allowed_uid==os.geteuid():
        raise PermissionError('separate, non-root client UID required')
    sockpath=root/'admission.sock'
    if sockpath.exists() or sockpath.is_symlink():
        raise FileExistsError('socket already exists: fail closed')
    # Prevent SQLite WAL/SHM journals from inheriting permissive host umask.
    prior_umask=os.umask(0o077)
    try:
        db=_db_open(root/'broker-journal.sqlite')
    finally:
        os.umask(prior_umask)
    accepted=[]
    with socket.socket(socket.AF_UNIX, socket.SOCK_SEQPACKET) as listener:
        listener.settimeout(accept_timeout)
        listener.bind(str(sockpath))
        os.chmod(sockpath,0o666)
        listener.listen(16)
        if ready_fd is not None:
            os.write(ready_fd,b'1')
            os.close(ready_fd)
        try:
            while max_requests==0 or len(accepted)<max_requests:
                try:conn,_=listener.accept()
                except socket.timeout:break
                with conn:
                    conn.settimeout(2.0)
                    try:
                        pid,uid,gid=peer_uid(conn)
                        message=conn.recv(MAX_PACKET+1)
                        response=decide(db,uid,allowed_uid,message)
                        conn.send(json.dumps(response).encode())
                        accepted.append({'pid':pid,'uid':uid,**response})
                    except (OSError,ValueError,RuntimeError) as exc:
                        accepted.append({'status':'DENIED','reason':type(exc).__name__})
        finally:
            db.close()
            sockpath.unlink(missing_ok=True)
    return {'schema':'trainos.uid-broker.v107','production_admitted':False,'requests':accepted}


def request(sockpath: Path, nonce: str, claimed_uid: int | None = None) -> dict:
    req={'operation':'start','nonce':nonce}
    if claimed_uid is not None:req['uid']=claimed_uid
    with socket.socket(socket.AF_UNIX,socket.SOCK_SEQPACKET) as s:
        s.settimeout(4.0)
        s.connect(str(sockpath))
        s.send(json.dumps(req).encode())
        answer=s.recv(MAX_PACKET)
    return json.loads(answer)


def main(argv=None)->int:
    p=argparse.ArgumentParser(description=__doc__)
    sub=p.add_subparsers(dest='action',required=True)
    s=sub.add_parser('serve')
    s.add_argument('--root',type=Path,required=True)
    s.add_argument('--allowed-uid',type=int,required=True)
    s.add_argument('--max-requests',type=int,default=1)
    s.add_argument('--report',type=Path,required=True)
    c=sub.add_parser('request')
    c.add_argument('--socket',type=Path,required=True)
    c.add_argument('--nonce',required=True)
    c.add_argument('--claimed-uid',type=int)
    a=p.parse_args(argv)
    if a.action=='serve':
        if a.max_requests<1:return 125
        try: result=serve(a.root,a.allowed_uid,a.max_requests)
        except (OSError,PermissionError,sqlite3.Error) as e:
            result={'status':'DENIED','error':f'{type(e).__name__}: {e}','production_admitted':False}
        a.report.write_text(json.dumps(result,indent=2)+'\n')
        print(json.dumps(result));return 125 if result.get('error') else 0
    try:result=request(a.socket,a.nonce,a.claimed_uid)
    except (OSError,ValueError) as e:
        result={'status':'DENIED','reason':type(e).__name__}
    print(json.dumps(result))
    return 0 if result.get('status')=='ADMITTED' else 125


if __name__=='__main__':raise SystemExit(main())
