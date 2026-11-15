"""LIFE-CORE-010: explicit two-phase anchor key rotation and crash reconciliation.

Offline logical lifecycle only. External key custody and monotonicity are operator duties.
"""
from __future__ import annotations
import hashlib
import hmac
import json
import os
from pathlib import Path
from .trust_anchor import TrustedLifecycle, AnchorError, canonical

def _fsync_dir(path):
    if hasattr(os, 'O_DIRECTORY'):
        fd = os.open(path, os.O_RDONLY | os.O_DIRECTORY)
        try: os.fsync(fd)
        finally: os.close(fd)

class RotationError(AnchorError):
    pass

def _key(value):
    if not isinstance(value, bytes) or len(value) < 32:
        raise RotationError('key must be at least 32 bytes')
    return value

def _mac(key, payload):
    return hmac.new(_key(key), canonical(payload), hashlib.sha256).hexdigest()

class RotatingLifecycle(TrustedLifecycle):
    """Rotation is explicit: prepare with old key, then finalize with new key.

    Pending records are signed by BOTH keys. No implicit recovery or key fallback.
    All state-changing operations refuse a pending rotation.
    """
    def __init__(self, registry, path, *, anchor_path, secret, clock_ns=None):
        self.rotation_path = Path(str(anchor_path) + '.rotation')
        self.fence_path = Path(str(path) + '.rotation-fence')
        super().__init__(registry, path, anchor_path=anchor_path, secret=secret, clock_ns=clock_ns)
        if self.rotation_path.exists() or self.fence_path.exists():
            self.close()
            raise RotationError('pending rotation: explicit reconciliation required')

    def _pending(self, old_key, new_key):
        try:
            doc=json.loads(self.rotation_path.read_text(encoding='utf-8'))
            payload=doc['payload']
            if set(doc) != {'payload','old_mac','new_mac'} or payload.get('format')!='LIFE-CORE-010':
                raise RotationError('invalid rotation record')
            if not hmac.compare_digest(doc['old_mac'],_mac(old_key,payload)) or not hmac.compare_digest(doc['new_mac'],_mac(new_key,payload)):
                raise RotationError('rotation authentication failed')
            return payload
        except (OSError,ValueError,KeyError,TypeError) as exc:
            raise RotationError('invalid or missing rotation record') from exc

    def prepare_rotation(self, token, new_key):
        _key(new_key)
        if hmac.compare_digest(self._secret,new_key):
            raise RotationError('new key must differ')
        if self.rotation_path.exists():
            raise RotationError('rotation already pending')
        self.verify_anchor()
        self._begin()
        try:
            self._check(token,self._now())
            self._replay()
            payload={'format':'LIFE-CORE-010','version':1,'epoch_floor':self._configuration()['epoch_floor'],
                     'anchor_sha256':hashlib.sha256(self.anchor_path.read_bytes()).hexdigest(),
                     'new_key_sha256':hashlib.sha256(new_key).hexdigest()}
            document={'payload':payload,'old_mac':_mac(self._secret,payload),'new_mac':_mac(new_key,payload)}
            # Durable fail-closed marker, created while SQLite write lock is held.
            # The SQLite admission UDF checks it on every INSERT, including old clients.
            with self.fence_path.open('x', encoding='utf-8') as fence:
                fence.write('LIFE-CORE-011\n')
                fence.flush(); os.fsync(fence.fileno())
            _fsync_dir(self.fence_path.parent)
            # Exclusive create prevents accidental overwrite of a pending intent.
            self.rotation_path.parent.mkdir(parents=True,exist_ok=True)
            with self.rotation_path.open('x',encoding='utf-8') as out:
                json.dump(document,out,sort_keys=True)
                out.flush()
                os.fsync(out.fileno())
            self.db.execute('COMMIT')
            return payload
        except Exception:
            self._rollback()
            raise

    def finalize_rotation(self, token, new_key):
        """Commit new anchor. Old key is no longer accepted after completion."""
        payload=self._pending(self._secret,new_key)
        if payload['new_key_sha256']!=hashlib.sha256(new_key).hexdigest():
            raise RotationError('new key mismatch')
        self._begin()
        try:
            self._check(token,self._now())
            self._replay()
            if payload['epoch_floor']>self._configuration()['epoch_floor']:
                raise RotationError('epoch rollback')
            current=self.anchor_path.read_bytes()
            if hashlib.sha256(current).hexdigest()!=payload['anchor_sha256']:
                raise RotationError('anchor changed during rotation')
            # Once the anchor is replaced, pending intent remains for explicit cleanup.
            self._secret=new_key
            self._write_anchor(self._configuration())
            self.db.execute('COMMIT')
            self.rotation_path.unlink()
            _fsync_dir(self.rotation_path.parent)
            self.fence_path.unlink()
            _fsync_dir(self.fence_path.parent)
            return True
        except Exception:
            self._rollback()
            raise

    def transition(self,*args,**kwargs):
        if self.rotation_path.exists() or self.fence_path.exists():
            raise RotationError('pending rotation blocks writes')
        return super().transition(*args,**kwargs)

    def reconcile_rotation(self, old_key, new_key):
        """Classify interrupted rotation; no automatic rewrite or deletion.

        Returns OLD_ANCHOR or NEW_ANCHOR, or fails closed on inconsistent data.
        An operator must validate custody and complete cleanup out of band.
        """
        payload=self._pending(old_key,new_key)
        raw=self.anchor_path.read_bytes()
        if hashlib.sha256(raw).hexdigest()==payload['anchor_sha256']:
            return 'OLD_ANCHOR'
        doc=json.loads(raw)
        if not hmac.compare_digest(doc['mac'],_mac(new_key,doc['payload'])):
            raise RotationError('anchor matches neither expected key')
        if doc['payload']['epoch_floor']<payload['epoch_floor']:
            raise RotationError('anchor epoch rollback')
        return 'NEW_ANCHOR'

def inspect_interrupted_rotation(anchor_path, old_key, new_key):
    """Read-only reconciliation usable when normal opening is blocked."""
    anchor_path=Path(anchor_path)
    pending=Path(str(anchor_path)+'.rotation')
    try:
        doc=json.loads(pending.read_text(encoding='utf-8'))
        payload=doc['payload']
        if set(doc)!={'payload','old_mac','new_mac'} or payload.get('format')!='LIFE-CORE-010':
            raise RotationError('invalid pending record')
        if not hmac.compare_digest(doc['old_mac'],_mac(old_key,payload)) or not hmac.compare_digest(doc['new_mac'],_mac(new_key,payload)):
            raise RotationError('pending record authentication failed')
        raw=anchor_path.read_bytes()
        if hashlib.sha256(raw).hexdigest()==payload['anchor_sha256']:
            return 'OLD_ANCHOR'
        anchor=json.loads(raw)
        if not hmac.compare_digest(anchor['mac'],_mac(new_key,anchor['payload'])):
            raise RotationError('unrecognized anchor')
        if anchor['payload']['epoch_floor']<payload['epoch_floor']:
            raise RotationError('epoch rollback')
        return 'NEW_ANCHOR'
    except (OSError,ValueError,KeyError,TypeError) as exc:
        raise RotationError('cannot reconcile rotation') from exc
