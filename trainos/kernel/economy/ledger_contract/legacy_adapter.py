"""Explicit adapter from legacy TrainOS Transaction values to ledger journals.

This adapter is deliberately opt-in. It never guesses currency mappings,
minor-unit exponents, or missing account identities.
"""
from __future__ import annotations

from decimal import Decimal, InvalidOperation
from typing import Mapping

from kernel.economy.transactions.transaction import Transaction

from .models import JournalEntry, LedgerError, Posting
from .currency import CurrencyRegistry


class LegacyTransactionAdapter:
    """Convert supported legacy transfers into a balanced journal entry.

    Args:
        currency_codes: mapping from legacy ``currency_id`` to ISO-style code.
        minor_unit_exponents: mapping from ISO currency code to its decimal
            exponent (e.g. an explicitly configured ``JPY: 0`` or ``USD: 2``).

    Transactions with absent accounts, unknown currency IDs, unsupported
    transaction types, non-positive amounts, or excess decimal precision are
    rejected rather than silently inferred or rounded.
    """

    def __init__(
        self,
        *,
        currency_codes: Mapping[str, str],
        minor_unit_exponents: Mapping[str, int],
        currency_registry: CurrencyRegistry | None = None,
    ) -> None:
        self._currency_codes = dict(currency_codes)
        self._exponents = dict(minor_unit_exponents)
        self._currency_registry = currency_registry
        for legacy_id, code in self._currency_codes.items():
            if not isinstance(legacy_id, str) or not legacy_id:
                raise LedgerError("legacy currency IDs must be non-empty strings")
            if not isinstance(code, str) or len(code) != 3 or not code.isalpha() or not code.isupper():
                raise LedgerError(f"invalid configured currency code for {legacy_id!r}")
            if code not in self._exponents:
                raise LedgerError(f"missing minor-unit exponent for currency {code}")
            if self._currency_registry is not None:
                spec = self._currency_registry.get(code)
                if spec.minor_unit_exponent != self._exponents[code]:
                    raise LedgerError(f"configured exponent disagrees with registry for {code}")
        for code, exponent in self._exponents.items():
            if not isinstance(code, str) or len(code) != 3 or not code.isalpha() or not code.isupper():
                raise LedgerError("currency exponent keys must be uppercase three-letter codes")
            if isinstance(exponent, bool) or not isinstance(exponent, int) or not 0 <= exponent <= 6:
                raise LedgerError(f"minor-unit exponent for {code} must be an integer from 0 to 6")

    def to_journal(self, transaction: Transaction) -> JournalEntry:
        if not isinstance(transaction, Transaction):
            raise LedgerError("transaction must be a legacy Transaction")
        if transaction.from_account is None or transaction.to_account is None:
            raise LedgerError("both from_account and to_account are required for transfer adaptation")
        if not transaction.from_account or not transaction.to_account:
            raise LedgerError("account IDs must be non-empty")
        if transaction.from_account == transaction.to_account:
            raise LedgerError("source and destination accounts must differ")
        tx_type = getattr(transaction.transaction_type, "value", None)
        if tx_type != "transfer":
            raise LedgerError("only legacy TRANSFER transactions are supported by v1 adapter")
        currency = self._currency_codes.get(transaction.currency_id)
        if currency is None:
            raise LedgerError(f"no ISO currency mapping configured for {transaction.currency_id!r}")
        exponent = self._exponents[currency]
        if self._currency_registry is not None:
            spec = self._currency_registry.get(currency)
            if spec.minor_unit_exponent != exponent:
                raise LedgerError(f"configured exponent disagrees with registry for {currency}")
        try:
            amount = transaction.amount if isinstance(transaction.amount, Decimal) else Decimal(str(transaction.amount))
        except (InvalidOperation, ValueError, TypeError) as exc:
            raise LedgerError("transaction amount must be a finite Decimal-compatible value") from exc
        if not amount.is_finite() or amount <= 0:
            raise LedgerError("transaction amount must be finite and positive")
        scale = Decimal(10) ** exponent
        scaled = amount * scale
        integral = scaled.to_integral_value()
        if scaled != integral:
            raise LedgerError(f"amount has more precision than configured for {currency}")
        amount_minor = int(integral)
        description = f"legacy_transaction:{tx_type}"
        return JournalEntry(
            operation_id=transaction.transaction_id,
            postings=(
                Posting(transaction.from_account, currency, "debit", amount_minor),
                Posting(transaction.to_account, currency, "credit", amount_minor),
            ),
            description=description,
        )

    def append(self, transaction: Transaction, ledger) -> bool:
        """Convert and append using the ledger's atomic/idempotent API."""
        if ledger is None or not callable(getattr(ledger, "append", None)):
            raise LedgerError("ledger must expose an append(entry) method")
        return ledger.append(self.to_journal(transaction))
