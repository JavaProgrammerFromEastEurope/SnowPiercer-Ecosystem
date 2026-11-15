"""RAIL-TRUST-004: fail-closed independent anchor contract and offline recovery.

No hardware monotonic counter is bundled. An explicitly provisioned external
provider must implement the contract; default production admission is BLOCKED.
"""
from __future__ import annotations
import base64
import hashlib
import json
import os
import sqlite3
from pathlib import Path
from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
from .anchored_admission import _check_dir, _locked, _connect, _state, _read_anchor, RecoveryRequired
from .trusted_admission import AdmissionError
from .trust import canonical

class IndependentAnchorUnavailable(AdmissionError):
    pass

class IndependentAnchor:
    """Provisioned hardware/service contract, implemented outside this package.

    read() -> (integer sequence, string nonce); advance(expected, next) must
    atomically compare-and-swap durable monotonic state, never decrease it.
    Provider MUST authenticate clients, resist rollback, and survive host loss.
    """
    def read(self):
        raise IndependentAnchorUnavailable('independent anchor provider not provisioned')

    def advance(self, expected, next_value):
        raise IndependentAnchorUnavailable('independent anchor provider not provisioned')


def _verify_permit(permit, public_key, *, sequence, action):
    if not isinstance(permit, dict) or set(permit) != {'payload', 'signature'}:
        raise AdmissionError('invalid recovery permit')
    payload = permit['payload']
    if not isinstance(payload, dict) or set(payload) != {'domain', 'sequence', 'action', 'permit_id'}:
        raise AdmissionError('invalid permit payload')
    if payload['domain'] != 'snowpiercer.railsystem.recovery.v1' or type(payload['sequence']) is not int or payload['sequence'] != sequence or payload['action'] != action:
        raise AdmissionError('wrong permit scope')
    if not isinstance(payload['permit_id'], str) or len(payload['permit_id']) < 24:
        raise AdmissionError('invalid permit identifier')
    try:
        key = base64.b64decode(public_key, validate=True)
        sig = base64.b64decode(permit['signature'], validate=True)
        if len(key) != 32 or len(sig) != 64: raise ValueError('invalid signature size')
        Ed25519PublicKey.from_public_bytes(key).verify(sig, canonical(payload))
    except (ValueError, TypeError, InvalidSignature) as exc:
        raise AdmissionError('invalid recovery signature') from exc
    return hashlib.sha256(canonical(payload)).hexdigest()


def _inspect_fence_locked(directory, provider):
    """Caller MUST hold admission.lock; do not acquire the lock recursively."""
    anchor = _read_anchor(directory / 'anchor.json')
    conn = _connect(directory)
    try:
        seq, _, phase, pending_seq, pending_nonce = _state(conn)
        external = provider.read()
        if not isinstance(external, tuple) or len(external) != 2 or type(external[0]) is not int or not isinstance(external[1], str):
            raise IndependentAnchorUnavailable('invalid independent anchor response')
        if phase != 'IDLE' or pending_seq is not None or pending_nonce is not None:
            raise RecoveryRequired('recovery fence active')
        if external != (seq, anchor['nonce']) or anchor['sequence'] != seq:
            raise RecoveryRequired('independent anchor disagreement')
        return {'status': 'CONSISTENT', 'sequence': seq}
    finally:
        conn.close()


def inspect_fence(directory, provider=None):
    """Fail-closed preflight; never authorizes a release on its own."""
    provider = provider if provider is not None else IndependentAnchor()
    directory = _check_dir(directory)
    with _locked(directory):
        return _inspect_fence_locked(directory, provider)


def recover_with_attestation(directory, *, provider=None, permit, recovery_public_key, fault=None):
    """Offline reconciliation; only signed permits, no independent-anchor rollback.

    Must run under the same OS owner as protected state. A separate privileged
    broker for cross-UID recovery is intentionally not provided.
    """
    provider = provider or IndependentAnchor()
    directory = _check_dir(directory)
    with _locked(directory):
        anchor = _read_anchor(directory / 'anchor.json')
        conn = _connect(directory)
        try:
            seq, raw, phase, pending_seq, pending_nonce = _state(conn)
            if phase != 'PREPARED' or type(pending_seq) is not int or pending_seq <= seq or not isinstance(pending_nonce, str):
                raise RecoveryRequired('no valid pending recovery')
            digest = _verify_permit(permit, recovery_public_key, sequence=pending_seq, action='reconcile')
            conn.execute('CREATE TABLE IF NOT EXISTS signed_permits (digest TEXT PRIMARY KEY)')
            if conn.execute('SELECT 1 FROM signed_permits WHERE digest=?', (digest,)).fetchone():
                raise AdmissionError('reused signed permit')
            ext = provider.read()
            if ext not in ((seq, json.loads(raw)[-1] if seq else ''), (pending_seq, pending_nonce)):
                raise RecoveryRequired('external anchor ambiguous')
            if fault == 'before_commit': os._exit(113)
            conn.execute('BEGIN IMMEDIATE')
            if ext[0] == seq:
                if anchor != {'sequence': seq, 'nonce': ext[1]}:
                    raise RecoveryRequired('local anchor mismatch')
                conn.execute("UPDATE state SET phase='IDLE',pending_sequence=NULL,pending_nonce=NULL WHERE id=1")
            else:
                if anchor != {'sequence': pending_seq, 'nonce': pending_nonce}:
                    raise RecoveryRequired('local anchor mismatch')
                nonces = json.loads(raw)
                if not isinstance(nonces, list): raise RecoveryRequired('invalid nonce ledger')
                conn.execute("UPDATE state SET sequence=?,nonces=?,phase='IDLE',pending_sequence=NULL,pending_nonce=NULL WHERE id=1", (pending_seq, json.dumps(nonces + [pending_nonce])))
            conn.execute('INSERT INTO signed_permits VALUES (?)', (digest,))
            conn.execute('COMMIT')
            return {'status': 'RECOVERED', 'sequence': _state(conn)[0]}
        except BaseException:
            if conn.in_transaction: conn.execute('ROLLBACK')
            raise
        finally:
            conn.close()
