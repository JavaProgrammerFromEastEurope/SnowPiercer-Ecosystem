"""Simulation-only guarded ledger gateway; local file anchor is NOT a trust root."""
from contextlib import contextmanager
from dataclasses import dataclass
import fcntl
import json
import os
from pathlib import Path
import tempfile
from .domain import EnergyError
from .persistence import PersistentEnergyLedger, LedgerIntegrityError, LedgerConflict

class AdmissionDenied(EnergyError): pass
class AnchorMismatch(LedgerIntegrityError): pass

@dataclass(frozen=True)
class AnchorHead:
    sequence: int
    digest: str


def _head(snapshot):
    return AnchorHead(snapshot[0], snapshot[1])

class TrustedEnergyGateway:
    """Serializes cooperating processes and reconciles crash windows.

    Assumes exclusive control of protected anchor directory. No same-UID adversary
    protection, hardware authorization, or automatic legacy API interception.
    """
    def __init__(self, ledger: PersistentEnergyLedger, anchor_dir):
        if not isinstance(ledger, PersistentEnergyLedger): raise EnergyError('ledger required')
        self.ledger = ledger
        self.directory = Path(anchor_dir)
        if not self.directory.is_dir() or self.directory.is_symlink(): raise AdmissionDenied('anchor directory missing or symlink')
        if self.directory.stat().st_mode & 0o022: raise AdmissionDenied('anchor directory writable by others')
        self.anchor = self.directory / 'energy.anchor'
        self.lockfile = self.directory / 'energy.lock'
        with self._lock(): self._reconcile(initial=True)

    @contextmanager
    def _lock(self):
        fd = os.open(self.lockfile, os.O_CREAT | os.O_RDWR | getattr(os,'O_NOFOLLOW',0), 0o600)
        try:
            if not os.path.isfile(self.lockfile) or os.fstat(fd).st_nlink != 1: raise AdmissionDenied('invalid lock')
            fcntl.flock(fd, fcntl.LOCK_EX)
            yield
        finally:
            fcntl.flock(fd, fcntl.LOCK_UN)
            os.close(fd)

    def _read(self):
        if not self.anchor.exists(): return None
        fd = os.open(self.anchor, os.O_RDONLY | getattr(os,'O_NOFOLLOW',0))
        try:
            if not os.fstat(fd).st_nlink == 1 or os.fstat(fd).st_size > 4096: raise AnchorMismatch('invalid anchor')
            with os.fdopen(fd,'r',encoding='utf8') as f:
                fd = -1
                data = json.load(f)
        finally:
            if fd >= 0: os.close(fd)
        if not isinstance(data,dict) or set(data) != {'committed','pending','version'} or data['version'] != 1: raise AnchorMismatch('invalid anchor schema')
        def parse(value):
            if value is None: return None
            if not isinstance(value,list) or len(value)!=2 or type(value[0]) is not int or value[0]<0 or not isinstance(value[1],str): raise AnchorMismatch('invalid head')
            return AnchorHead(*value)
        return parse(data['committed']),parse(data['pending'])

    def _write(self, committed, pending=None):
        data = {'version':1,'committed':[committed.sequence,committed.digest], 'pending':None if pending is None else [pending.sequence,pending.digest]}
        fd,name=tempfile.mkstemp(prefix='.anchor-',dir=self.directory)
        try:
            os.fchmod(fd,0o600)
            with os.fdopen(fd,'w',encoding='utf8') as f:
                json.dump(data,f,sort_keys=True)
                f.flush();os.fsync(f.fileno())
            os.replace(name,self.anchor)
            dirfd=os.open(self.directory,os.O_RDONLY)
            try: os.fsync(dirfd)
            finally: os.close(dirfd)
        finally:
            if os.path.exists(name):os.unlink(name)

    def _reconcile(self, initial=False):
        actual=_head(self.ledger.snapshot())
        saved=self._read()
        if saved is None:
            if actual != AnchorHead(0,'GENESIS'): raise AnchorMismatch('anchor missing for nonempty ledger')
            if not initial: raise AnchorMismatch('anchor removed')
            self._write(actual)
            return actual
        committed,pending=saved
        if pending is None:
            if actual != committed: raise AnchorMismatch('ledger/anchor mismatch')
        elif actual == committed:
            self._write(committed)
        elif actual == pending and pending.sequence == committed.sequence+1:
            self._write(pending)
        else:
            raise AnchorMismatch('unrecoverable pending transaction')
        return actual

    def snapshot(self):
        with self._lock():
            self._reconcile()
            return self.ledger.snapshot()

    def apply(self, operation_id, requests, *, duration_h, dispatch=(), reserve_kw=0.0, expected_sequence=None, fault_hook=None):
        with self._lock():
            before=self._reconcile()
            # Compute and stage the next anchor before the SQLite commit. The
            # ledger itself remains authoritative only for simulation state.
            with self.ledger._connect() as db:
                db.execute('BEGIN IMMEDIATE')
                seq,prev,state=self.ledger._verify(db)
                if (seq,prev)!=(before.sequence,before.digest): raise AnchorMismatch('concurrent unguarded writer')
                existing=db.execute('SELECT 1 FROM entries WHERE op=?',(operation_id,)).fetchone()
                if existing: raise LedgerConflict('replay')
                if expected_sequence is not None and expected_sequence != seq: raise LedgerConflict('stale sequence')
                from .persistence import _json,_serialize_ledger,_digest
                from .accounting import StorageDispatch
                from .domain import PowerRequest
                if not isinstance(operation_id,str) or not operation_id.strip() or len(operation_id)>200: raise EnergyError('invalid operation ID')
                if not isinstance(requests,(list,tuple)) or not isinstance(dispatch,(list,tuple)) or any(not isinstance(r,PowerRequest) for r in requests) or any(not isinstance(d,StorageDispatch) for d in dispatch): raise EnergyError('invalid requests')
                req={'requests':[[r.consumer_id,r.kw] for r in requests], 'dispatch':[[d.asset_id,d.discharge_kw,d.charge_kw] for d in dispatch], 'duration_h':duration_h,'reserve_kw':reserve_kw}
                result=self.ledger._compute(state,req)
                state.update(dict(result.storage_after))
                serialized=_serialize_ledger(result)
                digest=_digest(prev,seq+1,operation_id,req,serialized,state)
                pending=AnchorHead(seq+1,digest)
                self._write(before,pending)
                if fault_hook:fault_hook('after_anchor_prepare')
                db.execute('INSERT INTO entries VALUES (?,?,?,?,?,?,?)',(seq+1,operation_id,_json(req),_json(serialized),_json(state),prev,digest))
                if fault_hook:fault_hook('after_insert')
                db.commit()
                if fault_hook:fault_hook('after_sqlite_commit')
            self._write(pending)
            if fault_hook:fault_hook('after_anchor_commit')
            from .persistence import CommittedEnergy
            return CommittedEnergy(seq+1,operation_id,result,digest)

class ProductionEnergyAdmission:
    """Explicitly scoped gateway. No physical production interface exists."""
    def __init__(self, gateway: TrustedEnergyGateway):
        if not isinstance(gateway,TrustedEnergyGateway): raise AdmissionDenied('trusted gateway required')
        self.gateway=gateway
    def submit_simulation(self,*args,**kwargs): return self.gateway.apply(*args,**kwargs)
    def submit_hardware(self,*args,**kwargs): raise AdmissionDenied('hardware control is not implemented')
    def legacy_write(self,*args,**kwargs): raise AdmissionDenied('legacy production writes forbidden')
