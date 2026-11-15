"""AI-CORE-005 mandatory admission boundary for enrolled SQLite replay stores.

Software boundary only: does not defend against privileged filesystem/SQLite schema edits.
"""
import hashlib
import hmac
import json
import sqlite3
import time
from .admission import AdmissionRejected, TrustedAdmission, _json_bytes, _valid_time, _valid_nonce, MAX_WIRE_BYTES
from .core import Observation, assess
from .lifecycle import RecoveryRequired, _digest


def _chain(secret, previous, event, source, nonce, epoch):
    payload = json.dumps([previous,event,source,nonce,epoch],separators=(',',':')).encode()
    return hmac.new(secret,payload,hashlib.sha256).hexdigest()


class MandatoryAdmissionGateway:
    """Enrolment installs SQLite triggers blocking ordinary direct inserts to seen.

    HMAC audit chain detects modification/reordering of retained rows, but not a
    complete consistent rollback without an external trusted checkpoint.
    """
    def __init__(self, manager, audit_secret: bytes, *, clock=None, bootstrap=False):
        if not isinstance(audit_secret,bytes) or len(audit_secret)<32:
            raise ValueError('audit_secret must be >=32 bytes')
        if not hasattr(manager,'independent_anchor'):
            raise ValueError('hardened manager required')
        self.manager=manager
        self.store=manager.store
        self.secret=audit_secret
        self.clock=clock or time.time
        self._permit=False
        db=self.store._db
        with self.store._lock:
            db.create_function('ai_gateway_permit',0,lambda: 1 if self._permit else 0)
            if bootstrap:
                db.execute('BEGIN IMMEDIATE')
                try:
                    if db.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='gateway_meta'").fetchone():
                        raise RecoveryRequired('GATEWAY_ALREADY_ENROLLED')
                    db.execute('CREATE TABLE gateway_meta (id INTEGER PRIMARY KEY CHECK(id=1), version INTEGER NOT NULL)')
                    db.execute('INSERT INTO gateway_meta VALUES (1,1)')
                    db.execute('CREATE TABLE gateway_audit (seq INTEGER PRIMARY KEY, event TEXT NOT NULL, source TEXT NOT NULL, nonce TEXT NOT NULL, epoch INTEGER NOT NULL, previous TEXT NOT NULL, mac TEXT NOT NULL)')
                    db.execute("CREATE TRIGGER gateway_seen_insert BEFORE INSERT ON seen BEGIN SELECT CASE WHEN ai_gateway_permit()!=1 THEN RAISE(ABORT,'GATEWAY_REQUIRED') END; END")
                    db.execute("CREATE TRIGGER gateway_seen_update BEFORE UPDATE ON seen BEGIN SELECT RAISE(ABORT,'GATEWAY_IMMUTABLE'); END")
                    db.execute("CREATE TRIGGER gateway_seen_delete BEFORE DELETE ON seen BEGIN SELECT RAISE(ABORT,'GATEWAY_IMMUTABLE'); END")
                    db.execute("CREATE TRIGGER gateway_audit_update BEFORE UPDATE ON gateway_audit BEGIN SELECT RAISE(ABORT,'AUDIT_IMMUTABLE'); END")
                    db.execute("CREATE TRIGGER gateway_audit_delete BEFORE DELETE ON gateway_audit BEGIN SELECT RAISE(ABORT,'AUDIT_IMMUTABLE'); END")
                    db.execute("CREATE TRIGGER gateway_audit_insert BEFORE INSERT ON gateway_audit BEGIN SELECT CASE WHEN ai_gateway_permit()!=1 THEN RAISE(ABORT,'GATEWAY_REQUIRED') END; END")
                    db.execute('COMMIT')
                except BaseException:
                    db.execute('ROLLBACK'); raise
            self._schema_check()

    def _schema_check(self):
        db=self.store._db
        row=db.execute('SELECT version FROM gateway_meta WHERE id=1').fetchone()
        if row!=(1,): raise RecoveryRequired('GATEWAY_SCHEMA_INVALID')
        required={'gateway_seen_insert','gateway_seen_update','gateway_seen_delete','gateway_audit_insert','gateway_audit_update','gateway_audit_delete'}
        rows=db.execute("SELECT name,sql FROM sqlite_master WHERE type='trigger'").fetchall()
        found={n:s for n,s in rows}
        if not required.issubset(found) or any('ai_gateway_permit' not in found[n] for n in ('gateway_seen_insert','gateway_audit_insert')):
            raise RecoveryRequired('GATEWAY_SCHEMA_INVALID')

    def _audit_check(self):
        previous='0'*64
        rows=self.store._db.execute('SELECT seq,event,source,nonce,epoch,previous,mac FROM gateway_audit ORDER BY seq').fetchall()
        for i,(seq,event,source,nonce,epoch,prev,mac) in enumerate(rows,1):
            if seq!=i or prev!=previous or not hmac.compare_digest(mac,_chain(self.secret,prev,event,source,nonce,epoch)):
                raise RecoveryRequired('AUDIT_TAMPERED')
            previous=mac
        return len(rows),previous

    def _verify(self,envelope):
        if not isinstance(envelope,dict): raise AdmissionRejected('INVALID_ENVELOPE')
        raw=_json_bytes(envelope)
        if len(raw)>MAX_WIRE_BYTES: raise AdmissionRejected('OVERSIZED_ENVELOPE')
        if set(envelope)!={'observation','timestamp','nonce','mac'}: raise AdmissionRejected('INVALID_ENVELOPE')
        try: observation=Observation.parse(envelope['observation'])
        except (ValueError,TypeError,KeyError) as exc: raise AdmissionRejected('INVALID_OBSERVATION') from exc
        timestamp,nonce,mac=envelope['timestamp'],envelope['nonce'],envelope['mac']
        if not _valid_time(timestamp) or not _valid_nonce(nonce) or not isinstance(mac,str) or len(mac)!=64 or any(c not in '0123456789abcdef' for c in mac):
            raise AdmissionRejected('INVALID_ENVELOPE')
        key=self.manager.keys.get(observation.source)
        if key is None: raise AdmissionRejected('UNTRUSTED_SOURCE')
        body={'observation':dict(envelope['observation']),'timestamp':timestamp,'nonce':nonce}
        if not hmac.compare_digest(hmac.new(key,_json_bytes(body),hashlib.sha256).hexdigest(),mac):
            raise AdmissionRejected('AUTHENTICATION_FAILED')
        now=self.clock()
        import math
        if not isinstance(now,(int,float)) or not math.isfinite(now) or now<0: raise AdmissionRejected('CLOCK_UNAVAILABLE')
        now=int(now)
        if timestamp<now-300: raise AdmissionRejected('STALE_OBSERVATION')
        if timestamp>now+30: raise AdmissionRejected('FUTURE_OBSERVATION')
        return observation,nonce,now

    def admit(self,envelope, *, fault=None):
        observation,nonce,now=self._verify(envelope)
        with self.manager.lock,self.store._lock:
            db=self.store._db
            try:
                db.execute('BEGIN IMMEDIATE')
                self._schema_check()
                self.manager._check()
                seq,previous=self._audit_check()
                if fault=='before_insert': raise RuntimeError('simulated crash before insert')
                self._permit=True
                try:
                    db.execute('INSERT INTO seen VALUES (?,?,?,?)',(observation.source,nonce,observation.event_id,now))
                    if fault=='after_insert': raise RuntimeError('simulated crash after insert')
                    epoch=self.manager._epoch()
                    mac=_chain(self.secret,previous,'ADMIT',observation.source,nonce,epoch)
                    db.execute('INSERT INTO gateway_audit VALUES (?,?,?,?,?,?,?)',(seq+1,'ADMIT',observation.source,nonce,epoch,previous,mac))
                    if fault=='after_audit': raise RuntimeError('simulated crash after audit')
                finally:
                    self._permit=False
                db.execute('COMMIT')
            except BaseException as exc:
                self._permit=False
                try: db.execute('ROLLBACK')
                except sqlite3.Error: pass
                if isinstance(exc,sqlite3.IntegrityError): raise AdmissionRejected('REPLAY_DETECTED') from exc
                if isinstance(exc,sqlite3.Error): raise AdmissionRejected('GATEWAY_STORE_UNAVAILABLE') from exc
                raise
        return assess(dict(envelope['observation']))

    def verify(self):
        with self.manager.lock,self.store._lock:
            self._schema_check(); self.manager._check(); return self._audit_check()
