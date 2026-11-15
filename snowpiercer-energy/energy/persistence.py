"""Simulation-only durable ledger. SQLite transaction is the sole commit authority."""
from dataclasses import dataclass, replace
from contextlib import contextmanager
from hashlib import sha256
import json
import os
from pathlib import Path
import sqlite3
from typing import Callable
from .domain import Asset, AssetKind, EnergyMode, EnergySystem, EnergyError, PowerRequest
from .accounting import StorageDispatch, PowerLedger, account

class LedgerIntegrityError(EnergyError): pass
class LedgerConflict(EnergyError): pass

@dataclass(frozen=True)
class CommittedEnergy:
    sequence: int
    operation_id: str
    ledger: PowerLedger
    digest: str

def _json(data):
    return json.dumps(data, sort_keys=True, separators=(',', ':'), allow_nan=False)

def _digest(prev, seq, op, request, result, state):
    return sha256(_json([prev, seq, op, request, result, state]).encode()).hexdigest()

def _serialize_ledger(ledger):
    return {k: getattr(ledger, k) for k in ledger.__dataclass_fields__}

def _deserialize_ledger(data):
    return PowerLedger(**{**data, 'allocations': tuple(tuple(x) for x in data['allocations']), 'storage_after': tuple(tuple(x) for x in data['storage_after'])})

class PersistentEnergyLedger:
    """Single SQLite database, serialized writers via BEGIN IMMEDIATE.

    Trust boundary: directory/database and writer identity must be protected externally.
    A hash chain detects accidental modifications, not attacker-controlled rewrites.
    """
    def __init__(self, path, system: EnergySystem, *, timeout=10.0):
        if not isinstance(system, EnergySystem) or system.mode != EnergyMode.SIMULATION:
            raise EnergyError('simulation system required')
        self.path = str(path)
        if self.path == ':memory:': raise EnergyError('persistent file required')
        if not isinstance(timeout, (int, float)) or isinstance(timeout, bool) or not 0 < timeout <= 120: raise EnergyError('invalid timeout')
        self.timeout = timeout
        self.template = system
        self._initial = {k: a.stored_kwh for k,a in sorted(system.assets.items()) if a.kind == AssetKind.STORAGE}
        self._fingerprint = sha256(_json([[k,a.kind.value,a.rated_kw,a.critical,a.capacity_kwh,a.stored_kwh,a.efficiency] for k,a in sorted(system.assets.items())]).encode()).hexdigest()
        if not Path(self.path).parent.is_dir(): raise EnergyError('database directory missing')
        with self._connect() as db:
            db.execute('BEGIN IMMEDIATE')
            db.execute('CREATE TABLE IF NOT EXISTS metadata (id INTEGER PRIMARY KEY CHECK(id=1), fingerprint TEXT NOT NULL, initial TEXT NOT NULL)')
            db.execute('CREATE TABLE IF NOT EXISTS entries (seq INTEGER PRIMARY KEY, op TEXT NOT NULL UNIQUE, request TEXT NOT NULL, result TEXT NOT NULL, state TEXT NOT NULL, prev TEXT NOT NULL, digest TEXT NOT NULL)')
            row = db.execute('SELECT fingerprint, initial FROM metadata WHERE id=1').fetchone()
            if row is None:
                db.execute('INSERT INTO metadata VALUES (1,?,?)',(self._fingerprint,_json(self._initial)))
            elif row != (self._fingerprint, _json(self._initial)):
                raise LedgerIntegrityError('asset configuration mismatch')
            self._verify(db)
            db.commit()

    @contextmanager
    def _connect(self):
        db = sqlite3.connect(self.path, timeout=self.timeout, isolation_level=None)
        db.execute('PRAGMA busy_timeout=10000')
        db.execute('PRAGMA synchronous=FULL')
        db.execute('PRAGMA journal_mode=DELETE')
        try:
            yield db
        finally:
            db.close()

    def _verify(self, db):
        check = db.execute('PRAGMA quick_check').fetchone()
        if check != ('ok',): raise LedgerIntegrityError('sqlite integrity failed')
        row = db.execute('SELECT fingerprint,initial FROM metadata WHERE id=1').fetchone()
        if row != (self._fingerprint, _json(self._initial)): raise LedgerIntegrityError('metadata changed')
        state = dict(self._initial)
        prev = 'GENESIS'
        seq = 0
        for n,op,request,result,stored,previous,digest in db.execute('SELECT seq,op,request,result,state,prev,digest FROM entries ORDER BY seq'):
            seq += 1
            if n != seq or previous != prev: raise LedgerIntegrityError('broken sequence')
            try:
                if _digest(prev,n,op,json.loads(request),json.loads(result),json.loads(stored)) != digest: raise LedgerIntegrityError('digest mismatch')
                req = json.loads(request)
                expected = self._compute(state,req)
                if _json(_serialize_ledger(expected)) != result: raise LedgerIntegrityError('ledger computation mismatch')
                after = dict(expected.storage_after)
                state.update(after)
                if _json(state) != stored: raise LedgerIntegrityError('storage state mismatch')
            except (ValueError, TypeError, KeyError, OverflowError) as exc:
                raise LedgerIntegrityError('invalid journal content') from exc
            prev = digest
        return seq,prev,state

    def _compute(self, state, req):
        assets = {k: replace(a, stored_kwh=state[k]) if a.kind == AssetKind.STORAGE else a for k,a in self.template.assets.items()}
        system = EnergySystem(assets, EnergyMode.SIMULATION)
        return account(system, tuple(PowerRequest(*r) for r in req['requests']), duration_h=req['duration_h'], dispatch=tuple(StorageDispatch(*d) for d in req['dispatch']), reserve_kw=req['reserve_kw'])

    def snapshot(self):
        with self._connect() as db:
            db.execute('BEGIN IMMEDIATE')
            result = self._verify(db)
            db.commit()
            return result

    def apply(self, operation_id: str, requests, *, duration_h, dispatch=(), reserve_kw=0.0, expected_sequence=None, fault_hook: Callable[[str],None] | None=None):
        if not isinstance(operation_id,str) or not operation_id.strip() or len(operation_id)>200: raise EnergyError('invalid operation ID')
        if not isinstance(requests,(tuple,list)) or not isinstance(dispatch,(tuple,list)): raise EnergyError('invalid input sequence')
        if any(not isinstance(r,PowerRequest) for r in requests) or any(not isinstance(d,StorageDispatch) for d in dispatch): raise EnergyError('invalid inputs')
        req = {'requests': [[r.consumer_id,r.kw] for r in requests], 'dispatch': [[d.asset_id,d.discharge_kw,d.charge_kw] for d in dispatch], 'duration_h':duration_h, 'reserve_kw':reserve_kw}
        encoded = _json(req)
        with self._connect() as db:
            db.execute('BEGIN IMMEDIATE')
            if fault_hook: fault_hook('after_begin')
            seq,prev,state = self._verify(db)
            if fault_hook: fault_hook('after_verify')
            existing = db.execute('SELECT request FROM entries WHERE op=?',(operation_id,)).fetchone()
            if existing is not None: raise LedgerConflict('replayed operation' if existing[0]==encoded else 'operation ID collision')
            if expected_sequence is not None and (type(expected_sequence) is not int or expected_sequence != seq): raise LedgerConflict('stale sequence')
            result = self._compute(state,req)
            state.update(dict(result.storage_after))
            serialized = _serialize_ledger(result)
            digest = _digest(prev,seq+1,operation_id,req,serialized,state)
            db.execute('INSERT INTO entries VALUES (?,?,?,?,?,?,?)',(seq+1,operation_id,encoded,_json(serialized),_json(state),prev,digest))
            if fault_hook: fault_hook('after_insert')
            db.commit()
            if fault_hook: fault_hook('after_commit')
            return CommittedEnergy(seq+1,operation_id,result,digest)
