"""LIFE-CORE-009: independently stored HMAC configuration anchors.

Trust assumptions: anchor file and secret are protected independently from SQLite.
Not protection against privileged modification of all three artifacts.
"""
from __future__ import annotations
import hashlib, hmac, json, os, tempfile
from pathlib import Path
from .hardening import HardenedLifecycle, guard_digest
from .admission import AdmissionError

class AnchorError(AdmissionError):
    pass

def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=True).encode('ascii')

class TrustedLifecycle(HardenedLifecycle):
    """Opt-in externally anchored v2 journal; all TrustedLifecycle writes verify anchor."""
    def __init__(self, registry, path, *, anchor_path, secret, clock_ns=None):
        self.anchor_path = Path(anchor_path)
        if not isinstance(secret, bytes) or len(secret)<32:
            raise AnchorError('secret must contain at least 32 bytes')
        self._secret = secret
        super().__init__(registry,path,clock_ns=clock_ns)
        try:
            if self.anchor_path.exists():
                self.verify_anchor()
        except Exception:
            self.close()
            raise

    def _configuration(self):
        status=self.verify_integrity()
        if status.get('version')!=2:
            raise AnchorError('v2 protected journal required')
        row=self.db.execute('SELECT epoch FROM coordination WHERE singleton=1').fetchone()
        return {'format':'LIFE-CORE-009','version':1,'admission_version':2,
                'guard_digest':guard_digest(),'epoch_floor':row[0] if row else 0}

    def _signature(self, data):
        return hmac.new(self._secret,canonical(data),hashlib.sha256).hexdigest()

    def _read_anchor(self):
        try:
            doc=json.loads(self.anchor_path.read_text(encoding='utf-8'))
            if not isinstance(doc,dict) or set(doc)!={'payload','mac'} or not isinstance(doc['payload'],dict) or not isinstance(doc['mac'],str):
                raise ValueError('malformed anchor')
            if not hmac.compare_digest(self._signature(doc['payload']),doc['mac']):
                raise AnchorError('anchor authentication failed')
            return doc['payload']
        except (OSError,ValueError,TypeError) as exc:
            raise AnchorError('anchor unreadable or malformed') from exc

    def verify_anchor(self):
        if not self.anchor_path.is_file():
            raise AnchorError('trusted anchor missing')
        payload=self._read_anchor()
        current=self._configuration()
        if set(payload)!=set(current):
            raise AnchorError('anchor fields mismatch')
        for key in ('format','version','admission_version','guard_digest'):
            if payload[key]!=current[key]:
                raise AnchorError('configuration mismatch: '+key)
        if type(payload['epoch_floor']) is not int or payload['epoch_floor']<0 or current['epoch_floor']<payload['epoch_floor']:
            raise AnchorError('configuration rollback detected')
        return dict(payload)

    def _write_anchor(self, payload):
        self.anchor_path.parent.mkdir(parents=True,exist_ok=True)
        fd,name=tempfile.mkstemp(prefix='.life-anchor-',dir=self.anchor_path.parent)
        try:
            with os.fdopen(fd,'w',encoding='utf-8') as out:
                json.dump({'payload':payload,'mac':self._signature(payload)},out,sort_keys=True)
                out.flush();os.fsync(out.fileno())
            os.replace(name,self.anchor_path)
            if hasattr(os,'O_DIRECTORY'):
                dfd=os.open(self.anchor_path.parent,os.O_RDONLY|os.O_DIRECTORY)
                try:os.fsync(dfd)
                finally:os.close(dfd)
        finally:
            if os.path.exists(name):os.unlink(name)

    def establish_anchor(self, token):
        """Explicit enrollment after v2 hardening, using a valid lease."""
        self._begin()
        try:
            self._check(token,self._now())
            payload=self._configuration()
            if self.anchor_path.exists():
                self.verify_anchor()
                raise AnchorError('already anchored')
            self._replay()
            self._check(token,self._now())
            self._write_anchor(payload)
            self.db.execute('COMMIT')
            return payload
        except Exception:
            self._rollback()
            raise

    def transition(self,*args,**kwargs):
        self.verify_anchor()
        return super().transition(*args,**kwargs)

    def recover(self,*,token=None):
        self.verify_anchor()
        return super().recover(token=token)

    def acquire(self,owner,*,ttl_ns):
        if self.verify_integrity().get('version')==2:
            self.verify_anchor()
        token=super().acquire(owner,ttl_ns=ttl_ns)
        # An external epoch-floor is monotonic. A crash between DB commit and
        # anchor update is recoverable; the opposite ordering is not.
        # The floor is deliberately not auto-advanced here: callers must
        # explicitly publish a new anchor after acquiring a lease.
        return token

    def advance_anchor(self,token):
        self.verify_anchor()
        self._begin()
        try:
            self._check(token,self._now())
            payload=self._configuration()
            self._write_anchor(payload)
            self.db.execute('COMMIT')
            return payload
        except Exception:
            self._rollback()
            raise
