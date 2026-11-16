"""ISLAND-GEO-015: state/UID-bound one-use permits; experimental, not a production guarantee.

The authority DB and witness DB must be independently OS-owned. Local SQLite cannot
be made rollback-proof by this module. No automatic bypass is allowed in this API.
"""
import hashlib
import json
import os
import secrets
import sqlite3
from pathlib import Path
from .anchored_admission import AdmissionDenied, GENESIS

class BoundPermitAuthority:
    """Authority-owned permits, bound to exact witness head and service/client UIDs."""
    def __init__(self, path, client_uid, service_uid, witness):
        if any(type(v) is not int or v <= 0 for v in (client_uid,service_uid)) or client_uid == service_uid:
            raise AdmissionDenied('distinct nonroot client/service UID required')
        self.path=Path(path);self.client_uid=client_uid;self.service_uid=service_uid;self.witness=witness
    def _connect(self):
        db=sqlite3.connect(self.path,isolation_level=None,timeout=5)
        try:
            db.execute('PRAGMA synchronous=FULL')
            db.execute('CREATE TABLE IF NOT EXISTS bound_permits (hash TEXT PRIMARY KEY, client_uid INTEGER NOT NULL, service_uid INTEGER NOT NULL, sequence INTEGER NOT NULL, digest TEXT NOT NULL, used INTEGER NOT NULL DEFAULT 0)')
            return db
        except BaseException:
            db.close();raise
    def issue(self, peer_uid):
        if peer_uid != self.client_uid: raise AdmissionDenied('issuer peer UID mismatch')
        head=self.witness.execute('read')
        if type(head.get('sequence')) is not int or type(head.get('digest')) is not str: raise AdmissionDenied('invalid witness head')
        token=secrets.token_hex(32)
        db=self._connect()
        try:
            db.execute('INSERT INTO bound_permits VALUES (?,?,?,?,?,0)',(hashlib.sha256(token.encode()).hexdigest(),self.client_uid,self.service_uid,head['sequence'],head['digest']))
        finally: db.close()
        return {'token':token,'sequence':head['sequence'],'digest':head['digest']}
    def consume(self, peer_uid, token):
        if peer_uid != self.service_uid: raise AdmissionDenied('consumer peer UID mismatch')
        if type(token) is not str or len(token)!=64 or any(c not in '0123456789abcdef' for c in token):
            raise AdmissionDenied('invalid token')
        db=self._connect()
        try:
            db.execute('BEGIN IMMEDIATE')
            row=db.execute('SELECT client_uid,service_uid,sequence,digest,used FROM bound_permits WHERE hash=?',(hashlib.sha256(token.encode()).hexdigest(),)).fetchone()
            if row is None or row[4] or row[0]!=self.client_uid or row[1]!=peer_uid: raise AdmissionDenied('replay or UID mismatch')
            head=self.witness.execute('read')
            if (row[2],row[3]) != (head['sequence'],head['digest']): raise AdmissionDenied('stale witness head')
            if db.execute('UPDATE bound_permits SET used=1 WHERE hash=? AND used=0',(hashlib.sha256(token.encode()).hexdigest(),)).rowcount!=1:
                raise AdmissionDenied('permit already consumed')
            db.execute('COMMIT')
            return {'consumed':True,'sequence':head['sequence'],'digest':head['digest']}
        except BaseException:
            if db.in_transaction: db.execute('ROLLBACK')
            raise
        finally:db.close()
    def execute(self,peer_uid,operation,token=None):
        if operation=='issue':return self.issue(peer_uid)
        if operation=='consume':return self.consume(peer_uid,token)
        raise AdmissionDenied('unknown operation')

def assert_legacy_fenced(client_uid, service_uid, witness_uid, local_dir, witness_dir):
    """Deployment preflight only. Requires actual negative access tests for E2E proof."""
    import stat
    if len({client_uid,service_uid,witness_uid})!=3 or any(type(u) is not int or u<=0 for u in (client_uid,service_uid,witness_uid)):
        raise AdmissionDenied('three separate nonroot UIDs required')
    for path,uid in ((local_dir,service_uid),(witness_dir,witness_uid)):
        s=Path(path).lstat()
        if not stat.S_ISDIR(s.st_mode) or s.st_uid!=uid or s.st_mode & 0o077:
            raise AdmissionDenied('unsafe deployment directory')
    return True
