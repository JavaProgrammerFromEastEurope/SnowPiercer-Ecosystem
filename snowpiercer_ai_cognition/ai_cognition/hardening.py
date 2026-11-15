"""AI-CORE-004 independent authenticated anchor and one-shot recovery authorization."""
import hashlib
import hmac
import json
import os
import threading
from pathlib import Path
from .lifecycle import RecoveryRequired, RotationManager


def _mac(key, payload):
    return hmac.new(key, payload, hashlib.sha256).hexdigest()


class IndependentAnchor:
    """Separate durable signed checkpoint. Secret MUST be provisioned outside SQLite/anchor.

    This software adapter does not provide hardware rollback resistance.
    """
    def __init__(self, path, secret):
        if not isinstance(secret, bytes) or len(secret) < 32:
            raise ValueError('independent anchor secret must be >=32 bytes')
        self.path = Path(path)
        self.secret = secret
        self.lock = threading.RLock()

    def read(self):
        with self.lock:
            try:
                raw = self.path.read_bytes()
                if len(raw) > 1024:
                    raise ValueError('oversized')
                record = json.loads(raw)
                if set(record) != {'epoch', 'mac'} or type(record['epoch']) is not int or record['epoch'] < 0:
                    raise ValueError('format')
                expected = _mac(self.secret, str(record['epoch']).encode('ascii'))
                if not hmac.compare_digest(expected, record['mac']):
                    raise ValueError('authentication')
                return record['epoch']
            except (OSError, ValueError, TypeError, KeyError) as exc:
                raise RecoveryRequired('INDEPENDENT_ANCHOR_UNAVAILABLE') from exc

    def advance(self, epoch, *, bootstrap=False):
        with self.lock:
            if type(epoch) is not int or epoch < 0:
                raise ValueError('epoch')
            if bootstrap:
                if self.path.exists() or epoch != 0:
                    raise RecoveryRequired('ANCHOR_ALREADY_PROVISIONED')
            else:
                previous = self.read()
                if epoch != previous + 1:
                    raise RecoveryRequired('ANCHOR_NONMONOTONIC')
            self.path.parent.mkdir(parents=True, exist_ok=True)
            record = {'epoch': epoch, 'mac': _mac(self.secret, str(epoch).encode('ascii'))}
            temp = self.path.with_name(self.path.name + '.tmp')
            fd = os.open(str(temp), os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
            try:
                with os.fdopen(fd, 'wb') as f:
                    f.write(json.dumps(record, sort_keys=True).encode('ascii'))
                    f.flush(); os.fsync(f.fileno())
                os.replace(temp, self.path)
                dirfd = os.open(str(self.path.parent), os.O_RDONLY)
                try: os.fsync(dirfd)
                finally: os.close(dirfd)
            finally:
                if temp.exists(): temp.unlink()


class HardenedRotationManager(RotationManager):
    """Opt-in stricter API: dual anchors, signed recovery tokens and audit trail."""
    def __init__(self, store, anchor_path, keys, *, independent_anchor, recovery_secret, bootstrap=False):
        if not isinstance(independent_anchor, IndependentAnchor):
            raise ValueError('independent anchor required')
        if not isinstance(recovery_secret, bytes) or len(recovery_secret) < 32:
            raise ValueError('recovery secret required')
        self.independent_anchor = independent_anchor
        self.recovery_secret = recovery_secret
        self._initializing = True
        super().__init__(store, anchor_path, keys, bootstrap=bootstrap)
        self._initializing = False
        with store._lock:
            store._db.execute('CREATE TABLE IF NOT EXISTS recovery_tokens (token_id TEXT PRIMARY KEY)')
            store._db.execute('CREATE TABLE IF NOT EXISTS lifecycle_audit (seq INTEGER PRIMARY KEY AUTOINCREMENT, event TEXT NOT NULL, source TEXT NOT NULL, epoch INTEGER NOT NULL)')
        if bootstrap:
            independent_anchor.advance(0, bootstrap=True)
        self._check()

    def _check(self):
        super()._check()
        if not self._initializing and self.independent_anchor.read() != self._epoch():
            raise RecoveryRequired('INDEPENDENT_ANCHOR_MISMATCH')

    def _write_anchor(self, epoch, exclusive=False):
        # Durable independent checkpoint precedes legacy anchor. A crash between
        # writes fails closed and requires operator intervention.
        if not exclusive:
            self.independent_anchor.advance(epoch)
        super()._write_anchor(epoch, exclusive=exclusive)

    def _audit(self, event, source):
        self.store._db.execute('INSERT INTO lifecycle_audit(event,source,epoch) VALUES (?,?,?)', (event,source,self._epoch()))

    def provision(self, source):
        super().provision(source)
        with self.store._lock: self._audit('PROVISION',source)

    def rotate(self, source, new_key, fault=None):
        try:
            super().rotate(source,new_key,fault=fault)
        finally:
            with self.store._lock: self._audit('ROTATION_ATTEMPT',source)

    def recovery_token(self, source, key, token_id):
        """Offline-authority helper; do not expose recovery_secret to the runtime in production."""
        if not isinstance(token_id,str) or not (16 <= len(token_id) <= 128) or not token_id.isascii():
            raise ValueError('token_id')
        with self.store._lock:
            row = self.store._db.execute('SELECT generation FROM rotation WHERE source=?',(source,)).fetchone()
            if row is None: raise RecoveryRequired('UNKNOWN_SOURCE')
            body = json.dumps([source,row[0],self._epoch(),hashlib.sha256(key).hexdigest(),token_id],separators=(',',':')).encode()
            return _mac(self.recovery_secret,body)

    def recover(self, source, key, *, approved=False, token_id=None, authorization=None):
        if not isinstance(token_id,str) or not (16 <= len(token_id) <= 128) or not token_id.isascii() or not isinstance(authorization,str):
            raise RecoveryRequired('RECOVERY_NOT_AUTHORIZED')
        with self.lock, self.store._lock:
            if self.independent_anchor.read() != self._epoch():
                raise RecoveryRequired('INDEPENDENT_ANCHOR_MISMATCH')
            expected = self.recovery_token(source,key,token_id)
            if not hmac.compare_digest(expected,authorization):
                raise RecoveryRequired('RECOVERY_NOT_AUTHORIZED')
            db=self.store._db
            if db.execute('SELECT 1 FROM recovery_tokens WHERE token_id=?',(token_id,)).fetchone():
                raise RecoveryRequired('RECOVERY_TOKEN_REPLAY')
            super().recover(source,key,approved=True)
            db.execute('INSERT INTO recovery_tokens(token_id) VALUES (?)',(token_id,))
            self._audit('RECOVERY',source)
