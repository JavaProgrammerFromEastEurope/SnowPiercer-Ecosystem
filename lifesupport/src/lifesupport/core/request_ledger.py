"""LIFE-CORE-018: opt-in authenticated request-ledger admission.

The independent anchor is a separate trust-domain assumption, not a SQLite security boundary.
A database ahead of its anchor is quarantined until explicitly reconciled.
"""
import hashlib
import hmac
import json
import os
import stat
import tempfile
from pathlib import Path

class LedgerIntegrityError(RuntimeError):
    pass


def _canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False).encode()


def _mac(key, payload):
    return hmac.new(key, _canonical(payload), hashlib.sha256).hexdigest()


def _rows(db):
    if not db.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='life_request_receipts'").fetchone():
        return []
    return db.execute('SELECT request_id,request_hash,peer_uid,sequence,event_id FROM life_request_receipts ORDER BY sequence,request_id').fetchall()


def ledger_snapshot(db):
    rows = _rows(db)
    seen = set()
    for rid, digest, uid, sequence, event_id in rows:
        if rid in seen or type(uid) is not int or uid <= 0 or type(sequence) is not int or sequence <= 0:
            raise LedgerIntegrityError('invalid receipt index')
        seen.add(rid)
        if not isinstance(digest,str) or len(digest)!=64 or any(c not in '0123456789abcdef' for c in digest):
            raise LedgerIntegrityError('invalid request hash')
        event=db.execute('SELECT event_id FROM events WHERE sequence=?',(sequence,)).fetchone()
        if not event or event[0]!=event_id:
            raise LedgerIntegrityError('receipt event mismatch')
    return {'count':len(rows), 'digest':hashlib.sha256(_canonical(rows)).hexdigest(),
            'max_sequence':max((r[3] for r in rows),default=0)}


class RequestLedgerAnchor:
    """Separate HMAC anchor; key must be provisioned independently of DB and anchor."""
    def __init__(self, path, key):
        self.path=Path(path)
        if not isinstance(key,bytes) or len(key)<32:
            raise ValueError('anchor key must contain at least 32 bytes')
        self.key=key

    def _read(self):
        if self.path.is_symlink():
            raise LedgerIntegrityError('anchor symlink rejected')
        try:
            st=self.path.stat()
            if not stat.S_ISREG(st.st_mode) or stat.S_IMODE(st.st_mode)&0o077:
                raise LedgerIntegrityError('unsafe anchor permissions')
            with self.path.open('rb') as f:
                raw=f.read(8193)
            if len(raw)>8192: raise LedgerIntegrityError('oversized anchor')
            obj=json.loads(raw)
            if not isinstance(obj,dict) or set(obj)!={'version','snapshot','mac'} or obj['version']!=1:
                raise LedgerIntegrityError('invalid anchor envelope')
            snap=obj['snapshot']
            if not isinstance(snap,dict) or set(snap)!={'count','digest','max_sequence'}:
                raise LedgerIntegrityError('invalid anchor snapshot')
            if type(snap['count']) is not int or type(snap['max_sequence']) is not int or min(snap['count'],snap['max_sequence'])<0 or not isinstance(snap['digest'],str):
                raise LedgerIntegrityError('invalid anchor values')
            if not hmac.compare_digest(str(obj['mac']),_mac(self.key,{'version':1,'snapshot':snap})):
                raise LedgerIntegrityError('anchor authentication failed')
            return snap
        except (OSError,ValueError,TypeError,KeyError) as exc:
            raise LedgerIntegrityError('anchor unavailable or corrupt') from exc

    def _write(self,snapshot):
        parent=self.path.parent
        if parent.is_symlink() or not parent.is_dir():
            raise LedgerIntegrityError('unsafe anchor directory')
        if self.path.exists() or self.path.is_symlink():
            self._read()
        envelope={'version':1,'snapshot':snapshot}
        envelope['mac']=_mac(self.key,envelope)
        fd,name=tempfile.mkstemp(prefix='.ledger-',dir=str(parent))
        try:
            os.fchmod(fd,0o600)
            with os.fdopen(fd,'wb') as out:
                out.write(_canonical(envelope));out.flush();os.fsync(out.fileno())
            os.replace(name,self.path)
            dfd=os.open(parent,os.O_RDONLY|os.O_DIRECTORY)
            try: os.fsync(dfd)
            finally: os.close(dfd)
        finally:
            if os.path.exists(name):os.unlink(name)

    def initialize(self,db):
        if self.path.exists() or self.path.is_symlink():
            raise LedgerIntegrityError('anchor already exists')
        snapshot=ledger_snapshot(db)
        self._write(snapshot)
        return snapshot

    def verify(self,db):
        trusted=self._read()
        current=ledger_snapshot(db)
        if current!=trusted:
            raise LedgerIntegrityError('ledger diverges from trusted anchor; recovery denied')
        return current

    def reconcile(self,db,*,approved_snapshot):
        """Explicit operator approval, not an automatic repair of an untrusted ledger."""
        trusted=self._read()
        current=ledger_snapshot(db)
        if current!=approved_snapshot or current['count']<trusted['count'] or current['max_sequence']<trusted['max_sequence']:
            raise LedgerIntegrityError('reconciliation rejected')
        # Prefix continuity cannot be proven from a single digest; operator must
        # validate a trusted external evidence trail before approving.
        self._write(current)
        return self.verify(db)


class LedgerAdmission:
    def __init__(self,lifecycle,anchor):
        self.lifecycle=lifecycle
        self.anchor=anchor
    def verify(self):
        self.lifecycle.verify_integrity()
        self.lifecycle._replay()
        return self.anchor.verify(self.lifecycle.db)
    def apply(self,req,uid,*,fault=None):
        from .reconciled_write import apply_request
        self.verify()
        result=apply_request(self.lifecycle,req,uid,fault=fault)
        if not result['replayed']:
            # Crash here leaves DB ahead of anchor; recovery remains fail-closed.
            self.anchor._write(ledger_snapshot(self.lifecycle.db))
        self.verify()
        return result
