"""Immutable value objects for the Financial Ledger Contract v1."""
from __future__ import annotations

from dataclasses import dataclass
import re

_CURRENCY_RE = re.compile(r"^[A-Z]{3}$")
_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:/-]{0,127}$")


class LedgerError(ValueError):
    """A journal entry violates the ledger contract."""


@dataclass(frozen=True, slots=True)
class Posting:
    """One positive integer-minor-unit debit or credit posting."""

    account_id: str
    currency: str
    side: str
    amount_minor: int

    def __post_init__(self) -> None:
        if not isinstance(self.account_id, str) or not _ID_RE.fullmatch(self.account_id):
            raise LedgerError("account_id must be a non-empty safe identifier (max 128 chars)")
        if not isinstance(self.currency, str) or not _CURRENCY_RE.fullmatch(self.currency):
            raise LedgerError("currency must be a three-letter uppercase ISO-style code")
        if self.side not in {"debit", "credit"}:
            raise LedgerError("side must be 'debit' or 'credit'")
        if isinstance(self.amount_minor, bool) or not isinstance(self.amount_minor, int):
            raise LedgerError("amount_minor must be an integer, not float/Decimal/bool")
        if self.amount_minor <= 0:
            raise LedgerError("amount_minor must be positive")


@dataclass(frozen=True, slots=True)
class JournalEntry:
    """An idempotent, balanced, single-currency journal operation."""

    operation_id: str
    postings: tuple[Posting, ...]
    description: str = ""

    def __post_init__(self) -> None:
        if not isinstance(self.operation_id, str) or not _ID_RE.fullmatch(self.operation_id):
            raise LedgerError("operation_id must be a non-empty safe identifier (max 128 chars)")
        if not isinstance(self.postings, tuple):
            raise LedgerError("postings must be a tuple")
        if len(self.postings) < 2:
            raise LedgerError("a journal must contain at least two postings")
        if any(not isinstance(p, Posting) for p in self.postings):
            raise LedgerError("every posting must be a Posting")
        currencies = {p.currency for p in self.postings}
        if len(currencies) != 1:
            raise LedgerError("a journal must use exactly one currency")
        debits = sum(p.amount_minor for p in self.postings if p.side == "debit")
        credits = sum(p.amount_minor for p in self.postings if p.side == "credit")
        if debits == 0 or credits == 0:
            raise LedgerError("a journal must include at least one debit and one credit")
        if debits != credits:
            raise LedgerError("journal debits and credits must balance")
        if not isinstance(self.description, str) or len(self.description) > 1000:
            raise LedgerError("description must be a string of at most 1000 characters")

    @property
    def currency(self) -> str:
        return self.postings[0].currency
