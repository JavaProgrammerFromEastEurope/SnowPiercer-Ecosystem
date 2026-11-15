"""Offline authenticated checkpoints and verified backups. No physical control."""
from __future__ import annotations
from contextlib import closing
import hashlib
import hmac
import json
import os
from pathlib import Path
import sqlite3
import tempfile
from .persistence import PersistentLifecycle, RecoveryError, fingerprint

class CheckpointError(RecoveryError):
    pass

def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False).encode('utf-8')

def _key(key):
    if not isinstance(key, bytes) or len(key) < 32:
        raise CheckpointError('independent secret key must contain at least 32 bytes')
    return key

def _atomic_write(path, data):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix='.' + path.name + '.', dir=path.parent)
    try:
        with os.fdopen(fd, 'wb') as f:
            f.write(data)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, path)
        if hasattr(os, 'O_DIRECTORY'):
            dfd = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY)
            try: os.fsync(dfd)
            finally: os.close(dfd)
    finally:
        if os.path.exists(tmp): os.unlink(tmp)

def _signature(payload, key):
    return hmac.new(_key(key), canonical(payload), hashlib.sha256).hexdigest()

def _verify_document(doc, key):
    if not isinstance(doc, dict) or set(doc) != {'payload', 'hmac_sha256'}:
        raise CheckpointError('invalid signed document')
    if not isinstance(doc['hmac_sha256'], str) or not hmac.compare_digest(_signature(doc['payload'], key), doc['hmac_sha256']):
        raise CheckpointError('checkpoint authentication failed')
    return doc['payload']

def _read_document(path, key):
    try:
        return _verify_document(json.loads(Path(path).read_text('utf-8')), key)
    except (OSError, UnicodeError, ValueError, TypeError) as exc:
        raise CheckpointError('invalid checkpoint document') from exc

def _head(lifecycle):
    events = lifecycle.events
    return {'sequence': len(events), 'event_hash': events[-1].event_hash if events else '0'*64,
            'state_sha256': hashlib.sha256(canonical(lifecycle.snapshot())).hexdigest()}

def create_checkpoint(store: PersistentLifecycle, anchor_path, key: bytes):
    """Write externally authenticated head; caller must protect key and anchor independently."""
    _key(key)
    store.recover()
    payload = {'format': 'snowpiercer.life.checkpoint.v1', 'registry_fingerprint': fingerprint(store.registry), **_head(store.lifecycle)}
    path = Path(anchor_path)
    if path.exists():
        old = _read_document(path, key)
        if old.get('format') != payload['format'] or old.get('registry_fingerprint') != payload['registry_fingerprint']:
            raise CheckpointError('incompatible prior anchor')
        if old.get('sequence', -1) > payload['sequence']:
            raise CheckpointError('anchor rollback rejected')
        if old.get('sequence') == payload['sequence'] and old != payload:
            raise CheckpointError('conflicting anchor at same sequence')
    _atomic_write(path, canonical({'payload': payload, 'hmac_sha256': _signature(payload, key)}))
    return payload

def verify_checkpoint(store: PersistentLifecycle, anchor_path, key: bytes, *, allow_newer_journal=True):
    """Verify anchor against journal prefix, detecting truncation and rewritten history."""
    payload = _read_document(anchor_path, key)
    if payload.get('format') != 'snowpiercer.life.checkpoint.v1' or payload.get('registry_fingerprint') != fingerprint(store.registry):
        raise CheckpointError('anchor format or registry mismatch')
    store.recover()
    seq = payload.get('sequence')
    if type(seq) is not int or seq < 0 or seq > len(store.lifecycle.events):
        raise CheckpointError('journal truncated before anchored sequence')
    if not allow_newer_journal and seq != len(store.lifecycle.events):
        raise CheckpointError('journal is ahead of anchor')
    # Reconstruct anchored state from the verified prefix rather than trusting current snapshot.
    from .lifecycle import Lifecycle
    replay = Lifecycle(store.registry)
    for event in store.lifecycle.events[:seq]:
        recreated = replay.transition(event.component_id, event.next_state, event_id=event.event_id,
                                      reason=event.reason, actor=event.actor, timestamp_utc=event.timestamp_utc)
        if recreated.as_dict() != event.as_dict():
            raise CheckpointError('journal prefix mismatch')
    if _head(replay) != {k: payload.get(k) for k in ('sequence', 'event_hash', 'state_sha256')}:
        raise CheckpointError('anchored history mismatch')
    return payload

def create_backup(store: PersistentLifecycle, backup_path, manifest_path, key: bytes, anchor_path=None):
    """Consistent SQLite backup, signed hash manifest, optional anchor verification."""
    _key(key)
    backup_path, manifest_path = Path(backup_path), Path(manifest_path)
    if backup_path.resolve() == store.path.resolve() or backup_path.resolve() == manifest_path.resolve():
        raise CheckpointError('backup paths must be distinct')
    if anchor_path is not None:
        verify_checkpoint(store, anchor_path, key)
    store.recover()
    backup_path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix='.backup-', dir=backup_path.parent)
    os.close(fd)
    try:
        target = sqlite3.connect(tmp)
        try:
            store.db.backup(target)
        finally:
            target.close()
        # verify SQLite backup using original registry and full replay
        with PersistentLifecycle(store.registry, tmp) as check:
            if _head(check.lifecycle) != _head(store.lifecycle):
                raise CheckpointError('backup head differs from source')
        digest = hashlib.sha256(Path(tmp).read_bytes()).hexdigest()
        payload = {'format': 'snowpiercer.life.backup.v1', 'registry_fingerprint': fingerprint(store.registry),
                   'backup_sha256': digest, **_head(store.lifecycle)}
        os.replace(tmp, backup_path)
        _atomic_write(manifest_path, canonical({'payload': payload, 'hmac_sha256': _signature(payload, key)}))
        return payload
    finally:
        if os.path.exists(tmp): os.unlink(tmp)

def verify_backup(registry, backup_path, manifest_path, key: bytes, anchor_path=None):
    payload = _read_document(manifest_path, key)
    if payload.get('format') != 'snowpiercer.life.backup.v1' or payload.get('registry_fingerprint') != fingerprint(registry):
        raise CheckpointError('backup manifest mismatch')
    try:
        digest = hashlib.sha256(Path(backup_path).read_bytes()).hexdigest()
    except OSError as exc:
        raise CheckpointError('backup missing') from exc
    if not hmac.compare_digest(digest, str(payload.get('backup_sha256'))):
        raise CheckpointError('backup digest mismatch')
    # Opening with mode=ro prevents accidentally initializing a missing database.
    with closing(sqlite3.connect(f'file:{Path(backup_path).resolve()}?mode=ro', uri=True)) as db:
        integrity = db.execute('PRAGMA integrity_check').fetchone()
        if integrity != ('ok',):
            raise CheckpointError('sqlite integrity check failed')
    with PersistentLifecycle(registry, backup_path) as restored:
        if _head(restored.lifecycle) != {k: payload.get(k) for k in ('sequence','event_hash','state_sha256')}:
            raise CheckpointError('backup journal head mismatch')
        if anchor_path is not None:
            verify_checkpoint(restored, anchor_path, key)
    return payload

def restore_backup(registry, backup_path, manifest_path, destination_path, key: bytes, anchor_path=None):
    """Restore only to a NEW destination; never overwrite an active database."""
    verify_backup(registry, backup_path, manifest_path, key, anchor_path)
    destination = Path(destination_path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    data = Path(backup_path).read_bytes()
    fd = os.open(destination, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        with os.fdopen(fd, 'wb') as out:
            out.write(data)
            out.flush()
            os.fsync(out.fileno())
    except Exception:
        destination.unlink(missing_ok=True)
        raise
    return destination
