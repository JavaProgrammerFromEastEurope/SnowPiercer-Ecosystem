"""RAIL-TRUST-005: fail-closed software release admission with external CAS anchor.

Provider durability, authentication and anti-rollback are external assumptions.
No distributed atomic transaction is claimed: PREPARED is a durable recovery fence.
"""
from __future__ import annotations
import json
import contextlib
import os
import signal
from pathlib import Path
from .anchored_admission import (_check_dir, _locked, _connect, _state,
                                  _read_anchor, _atomic_anchor, RecoveryRequired)
from .production_fencing import IndependentAnchor, _verify_permit
from .trusted_admission import AdmissionError
from .trust import verify_attestation
from .durable_permits import IndependentPermitLedger
from .release_gate import evaluate


def _tuple(value):
    if (not isinstance(value, tuple) or len(value) != 2 or
        type(value[0]) is not int or value[0] < 0 or
        not isinstance(value[1], str)):
        raise AdmissionError('invalid external anchor')
    return value


def _snapshot(conn, anchor, provider):
    seq, raw, phase, pending_seq, pending_nonce = _state(conn)
    if phase != 'IDLE' or pending_seq is not None or pending_nonce is not None:
        raise RecoveryRequired('recovery fence active')
    used = json.loads(raw)
    if not isinstance(used, list) or any(not isinstance(n, str) for n in used):
        raise RecoveryRequired('invalid replay ledger')
    expected = (seq, used[-1] if used else '')
    if (anchor != {'sequence': expected[0], 'nonce': expected[1]} or
        _tuple(provider.read()) != expected):
        raise RecoveryRequired('anchor disagreement')
    return seq, used


def _kill_at(point, kill_at):
    if kill_at == point:
        os.kill(os.getpid(), signal.SIGKILL)


def admit(root, *, baseline, attestation, trust, state_dir, provider=None, fault=None, _lock_held=False, kill_at=None):
    """One lock covers admission and recovery; provider must be independently trusted."""
    provider = provider if provider is not None else IndependentAnchor()
    directory = _check_dir(state_dir)
    with (contextlib.nullcontext() if _lock_held else _locked(directory)):
        anchor = _read_anchor(directory / 'anchor.json')
        conn = _connect(directory)
        try:
            seq, used = _snapshot(conn, anchor, provider)
            verified = verify_attestation(Path(root), baseline, attestation, trust,
                {'schema_version': 1, 'minimum_sequence': seq, 'used_nonces': used})
            gate = evaluate(Path(root), expected_manifest=baseline['manifest'], regression=None)
            if gate['status'] != 'PASS':
                raise AdmissionError('release gates failed')
            next_state = verified['next_state']
            next_value = (next_state['minimum_sequence'], next_state['used_nonces'][-1])
            previous = (seq, used[-1] if used else '')
            _kill_at('before_prepare', kill_at)
            conn.execute('BEGIN IMMEDIATE')
            conn.execute("UPDATE state SET phase='PREPARED',pending_sequence=?,pending_nonce=? WHERE id=1", next_value)
            conn.execute('COMMIT')
            if fault == 'after_prepare': os._exit(121)
            _kill_at('after_prepare', kill_at)
            _kill_at('before_external', kill_at)
            # CAS must be durable and monotonic; ambiguous provider failure fences recovery.
            outcome = provider.advance(previous, next_value)
            if outcome is not True:
                raise RecoveryRequired('external CAS did not confirm durability')
            if fault == 'after_external': os._exit(122)
            _kill_at('after_external', kill_at)
            _kill_at('before_local', kill_at)
            _atomic_anchor(directory / 'anchor.json', {'sequence': next_value[0], 'nonce': next_value[1]})
            if fault == 'after_local': os._exit(123)
            _kill_at('after_local', kill_at)
            _kill_at('before_final_commit', kill_at)
            conn.execute('BEGIN IMMEDIATE')
            conn.execute("UPDATE state SET sequence=?,nonces=?,phase='IDLE',pending_sequence=NULL,pending_nonce=NULL WHERE id=1",
                         (next_value[0], json.dumps(next_state['used_nonces'])))
            conn.execute('COMMIT')
            _kill_at('after_final_commit', kill_at)
            return {'stage': 'RAIL-TRUST-005', 'status': 'PASS', 'sequence': next_value[0],
                    'scope': 'software release only; no physical authorization'}
        except BaseException:
            if conn.in_transaction: conn.execute('ROLLBACK')
            raise
        finally:
            conn.close()


def recover(state_dir, *, provider=None, permit, recovery_public_key, fault=None,
            permit_store=None, _lock_held=False, kill_at=None):
    """Reconcile PREPARED under the admission lock with a signed, one-use permit.

    If external CAS advanced, complete; if not, abort. Ambiguity remains fenced.
    """
    provider = provider if provider is not None else IndependentAnchor()
    directory = _check_dir(state_dir)
    # Legacy library callers may omit permit_store for backwards compatibility.
    # Every production broker MUST pass an independently protected store.
    with (contextlib.nullcontext() if _lock_held else _locked(directory)):
        anchor = _read_anchor(directory / 'anchor.json')
        conn = _connect(directory)
        try:
            seq, raw, phase, pending_seq, pending_nonce = _state(conn)
            if phase != 'PREPARED' or type(pending_seq) is not int or pending_seq <= seq or not isinstance(pending_nonce, str):
                raise RecoveryRequired('no recoverable prepared transaction')
            digest = _verify_permit(permit, recovery_public_key, sequence=pending_seq, action='reconcile')
            conn.execute('CREATE TABLE IF NOT EXISTS unified_permits (digest TEXT PRIMARY KEY)')
            if conn.execute('SELECT 1 FROM unified_permits WHERE digest=?', (digest,)).fetchone():
                raise AdmissionError('reused permit')
            used = json.loads(raw)
            if not isinstance(used, list) or any(not isinstance(n, str) for n in used):
                raise RecoveryRequired('corrupt replay ledger')
            old = (seq, used[-1] if used else '')
            new = (pending_seq, pending_nonce)
            external = _tuple(provider.read())
            if external not in (old, new):
                raise RecoveryRequired('ambiguous external anchor')
            if external == old:
                if anchor != {'sequence': old[0], 'nonce': old[1]}:
                    raise RecoveryRequired('local anchor disagrees')
            else:
                if anchor not in ({'sequence': old[0], 'nonce': old[1]},
                                  {'sequence': new[0], 'nonce': new[1]}):
                    raise RecoveryRequired('local anchor disagrees')
            # Consume externally BEFORE a local write. If killed afterward,
            # the permit is intentionally burned; a *new* permit is required.
            # This favors fail-closed safety over automatic retry liveness.
            _kill_at('before_permit_consume', kill_at)
            if permit_store is not None:
                if permit_store.check_ready() is not True:
                    raise RecoveryRequired('independent permit ledger not ready')
                consumed = permit_store.consume_once(digest, sequence=pending_seq, action='reconcile')
                if consumed is not True:
                    raise RecoveryRequired('independent permit not consumed')
            _kill_at('after_permit_consume', kill_at)
            if external == new:
                # Preserve the original semantics while allowing the external
                # one-use check to precede local anchor reconciliation.
                _atomic_anchor(directory / 'anchor.json', {'sequence': new[0], 'nonce': new[1]})
            _kill_at('after_recovery_anchor', kill_at)
            if fault == 'before_commit': os._exit(124)
            _kill_at('before_recovery_commit', kill_at)
            conn.execute('BEGIN IMMEDIATE')
            if external == new:
                conn.execute("UPDATE state SET sequence=?,nonces=?,phase='IDLE',pending_sequence=NULL,pending_nonce=NULL WHERE id=1",
                             (new[0], json.dumps(used + [new[1]])))
            else:
                conn.execute("UPDATE state SET phase='IDLE',pending_sequence=NULL,pending_nonce=NULL WHERE id=1")
            conn.execute('INSERT INTO unified_permits VALUES (?)', (digest,))
            conn.execute('COMMIT')
            _kill_at('after_recovery_commit', kill_at)
            return {'status': 'RECOVERED', 'sequence': external[0]}
        except BaseException:
            if conn.in_transaction: conn.execute('ROLLBACK')
            raise
        finally:
            conn.close()
