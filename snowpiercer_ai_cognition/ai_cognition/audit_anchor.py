"""AI-CORE-006: authenticated external audit checkpoint and fail-closed gateway.

The checkpoint directory and key must be protected independently of the database.
"""
import hashlib
import hmac
import json
import os
import sqlite3
from pathlib import Path
from .gateway import MandatoryAdmissionGateway
from .lifecycle import RecoveryRequired


def _canonical(seq, head):
    return json.dumps({'seq':seq,'head':head},sort_keys=True,separators=(',',':')).encode()


class AuditCheckpoint:
    def __init__(self, path, key):
        if not isinstance(key,bytes) or len(key)<32: raise ValueError('checkpoint key must be >=32 bytes')
        self.path=Path(path); self.key=key

    def read(self):
        try:
            raw=self.path.read_bytes()
            if len(raw)>512: raise ValueError('oversized checkpoint')
            record=json.loads(raw)
            if set(record)!={'seq','head','mac'}: raise ValueError('format')
            seq,head=record['seq'],record['head']
            if type(seq) is not int or seq<0 or not isinstance(head,str) or len(head)!=64: raise ValueError('format')
            if not hmac.compare_digest(hmac.new(self.key,_canonical(seq,head),hashlib.sha256).hexdigest(),record['mac']): raise ValueError('mac')
            return seq,head
        except (OSError,ValueError,TypeError,KeyError) as exc:
            raise RecoveryRequired('AUDIT_CHECKPOINT_UNAVAILABLE') from exc

    def write(self,seq,head,*,bootstrap=False):
        if type(seq) is not int or seq<0 or not isinstance(head,str) or len(head)!=64: raise ValueError('checkpoint')
        if bootstrap:
            if self.path.exists() or (seq,head)!=(0,'0'*64): raise RecoveryRequired('CHECKPOINT_ALREADY_EXISTS')
        else:
            oldseq,oldhead=self.read()
            if seq!=oldseq+1: raise RecoveryRequired('CHECKPOINT_NONMONOTONIC')
        record={'seq':seq,'head':head,'mac':hmac.new(self.key,_canonical(seq,head),hashlib.sha256).hexdigest()}
        self.path.parent.mkdir(parents=True,exist_ok=True)
        tmp=self.path.with_name(self.path.name+'.pending')
        fd=os.open(tmp,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
        try:
            with os.fdopen(fd,'wb') as f:
                f.write(json.dumps(record,sort_keys=True).encode()); f.flush(); os.fsync(f.fileno())
            os.replace(tmp,self.path)
            directory=os.open(self.path.parent,os.O_RDONLY)
            try: os.fsync(directory)
            finally: os.close(directory)
        finally:
            if tmp.exists(): tmp.unlink()


class AnchoredAdmissionGateway(MandatoryAdmissionGateway):
    """Fail closed on checkpoint drift; explicit reconciliation for crash after DB commit.

    A single trusted writer is required. SQLite and checkpoint are separate commit
    domains, so a crash after DB COMMIT creates a fenced, not auto-repaired state.
    """
    def __init__(self,manager,audit_secret,*,checkpoint,clock=None,bootstrap=False):
        if not isinstance(checkpoint,AuditCheckpoint): raise ValueError('checkpoint required')
        self.checkpoint=checkpoint
        super().__init__(manager,audit_secret,clock=clock,bootstrap=bootstrap)
        with self.manager.lock,self.store._lock:
            if bootstrap: self.checkpoint.write(0,'0'*64,bootstrap=True)
            self.verify()

    def _check_checkpoint(self):
        actual=self._audit_check()
        if actual!=self.checkpoint.read(): raise RecoveryRequired('AUDIT_CHECKPOINT_MISMATCH')
        return actual

    def verify(self):
        with self.manager.lock,self.store._lock:
            self._schema_check(); self.manager._check()
            return self._check_checkpoint()

    def admit(self,envelope,*,fault=None):
        with self.manager.lock,self.store._lock:
            self.verify()
            # The base gateway commits its SQLite transaction first. Any crash
            # before checkpoint update requires explicit operator reconciliation.
            result=super().admit(envelope,fault=fault if fault!='after_commit' else None)
            if fault=='after_commit': raise RuntimeError('simulated crash after database commit')
            seq,head=self._audit_check()
            self.checkpoint.write(seq,head)
            return result

    def reconcile(self,*,authorized=False):
        """Explicitly approve exactly one committed-but-unanchored record.

        The operator must verify the underlying event externally before approval.
        """
        if authorized is not True: raise RecoveryRequired('RECONCILIATION_NOT_AUTHORIZED')
        with self.manager.lock,self.store._lock:
            self._schema_check(); self.manager._check()
            oldseq,oldhead=self.checkpoint.read()
            seq,head=self._audit_check()
            if seq!=oldseq+1: raise RecoveryRequired('RECONCILIATION_AMBIGUOUS')
            row=self.store._db.execute('SELECT previous FROM gateway_audit WHERE seq=?',(seq,)).fetchone()
            if row is None or row[0]!=oldhead: raise RecoveryRequired('RECONCILIATION_CHAIN_MISMATCH')
            self.checkpoint.write(seq,head)
            return self.verify()
