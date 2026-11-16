"""Isolated, durable double-entry ledger contract (v3).

This package is an additive prototype. It does not replace the legacy
kernel.economy.transactions implementation or authorize real-money use.
"""
from .models import JournalEntry, Posting
from .currency import CurrencyRegistry, CurrencySpec
from .legacy_adapter import LegacyTransactionAdapter
from .integrity_anchor import create_checkpoint, verify_checkpoint
from .store import FinancialLedger, IdempotencyConflict, LedgerError

__all__ = [
    "CurrencyRegistry",
    "CurrencySpec",
    "create_checkpoint",
    "FinancialLedger",
    "IdempotencyConflict",
    "JournalEntry",
    "LegacyTransactionAdapter",
    "LedgerError",
    "Posting",
    "verify_checkpoint",
]
