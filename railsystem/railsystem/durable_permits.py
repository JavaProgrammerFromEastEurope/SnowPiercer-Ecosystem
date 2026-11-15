"""RAIL-TRUST-011: independent one-use recovery-permit consumption contract.

The default is deliberately unavailable. A *separately administered* service
must durably consume a permit digest with authenticated caller authorization;
placing an SQLite table beside the release database is not sufficient.
"""
from __future__ import annotations
from .trusted_admission import AdmissionError


class PermitLedgerUnavailable(AdmissionError):
    """Independent, rollback-resistant permit service is not provisioned."""


class IndependentPermitLedger:
    """Provisioned external ledger contract (no bundled production backend).

    check_ready() must authenticate the server and verify durable monotonic
    operation. consume_once(digest, sequence, action) must atomically and
    durably return True for a never-before-consumed permit and False for a
    previously consumed permit. A timeout or ambiguous result MUST NOT yield
    True. The service must not share an attacker-controlled rollback domain
    with SQLite, and must enforce the RailSystem service identity.
    """
    def check_ready(self):
        raise PermitLedgerUnavailable('independent permit ledger unavailable')

    def consume_once(self, digest: str, *, sequence: int, action: str) -> bool:
        raise PermitLedgerUnavailable('independent permit ledger unavailable')
