"""RAIL-TRUST-015: *cryptographic protocol only* for an externally owned root.

A valid Ed25519 quote proves control of the pinned private key, NOT that the
signer has independently monotonic storage, certified hardware or OS isolation.
The verifier never authorizes production; it returns protocol evidence only.
External independent provisioning, enrollment, revocation and physical/root
anti-rollback remain mandatory operator-owned responsibilities.
"""
from __future__ import annotations

import base64
import os
import re
from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
from .trust import canonical

DOMAIN = 'snowpiercer.railsystem.external-root.quote.v1'


class RootQuoteDenied(ValueError):
    pass


def new_challenge() -> str:
    """An unpredictable single-use 256-bit challenge; caller must never reuse it."""
    return os.urandom(32).hex()


def _decode(value: str, length: int, what: str) -> bytes:
    if not isinstance(value, str):
        raise RootQuoteDenied('invalid ' + what)
    try:
        result = base64.b64decode(value, validate=True)
    except (ValueError, TypeError) as exc:
        raise RootQuoteDenied('invalid ' + what) from exc
    if len(result) != length:
        raise RootQuoteDenied('invalid ' + what + ' length')
    return result


def verify_root_quote(quote: dict, *, public_key: str, key_id: str,
                      root_id: str, challenge: str, minimum_sequence: int,
                      revoked_keys=frozenset()) -> dict:
    """Verify a pinned, challenge-bound Ed25519 root quote.

    Does NOT provide authority for physical operations or production admission.
    This checks cryptography and local input consistency, NOT device integrity,
    external monotonicity, signer enrollment or rollback-resistant custody.
    """
    if (type(quote) is not dict or set(quote) != {'payload', 'signature'}
            or type(quote['payload']) is not dict):
        raise RootQuoteDenied('invalid quote envelope')
    p = quote['payload']
    if set(p) != {'domain', 'root_id', 'key_id', 'challenge', 'sequence', 'nonce', 'schema_version'}:
        raise RootQuoteDenied('invalid quote fields')
    if (type(key_id) is not str or not re.fullmatch(r'[A-Za-z0-9_.:-]{1,96}', key_id)
            or type(root_id) is not str or not re.fullmatch(r'[A-Za-z0-9_.:-]{1,96}', root_id)
            or type(challenge) is not str or not re.fullmatch(r'[0-9a-f]{64}', challenge)
            or type(minimum_sequence) is not int or minimum_sequence < 0
            or not isinstance(revoked_keys, (set, frozenset))):
        raise RootQuoteDenied('invalid verification policy')
    if (key_id in revoked_keys or p['domain'] != DOMAIN or p['schema_version'] != 1
            or p['key_id'] != key_id or p['root_id'] != root_id
            or p['challenge'] != challenge or type(p['sequence']) is not int
            or p['sequence'] < minimum_sequence or not isinstance(p['nonce'], str)
            or len(p['nonce']) > 128):
        raise RootQuoteDenied('quote does not match pinned policy or freshness')
    key = _decode(public_key, 32, 'public key')
    sig = _decode(quote['signature'], 64, 'signature')
    try:
        Ed25519PublicKey.from_public_bytes(key).verify(sig, canonical(p))
    except (ValueError, InvalidSignature) as exc:
        raise RootQuoteDenied('invalid signed root quote') from exc
    return {'status': 'CRYPTOGRAPHIC_PROTOCOL_ONLY', 'root_id': root_id,
            'sequence': p['sequence'], 'nonce': p['nonce'],
            'independent_custody_verified': False, 'production_authorized': False,
            'physical_operations_authorized': False}


def require_independent_root(*_args, **_kwargs):
    """No test-only quote may promote the laboratory provider to production."""
    raise RootQuoteDenied('external, independently audited monotonic root not provisioned')
