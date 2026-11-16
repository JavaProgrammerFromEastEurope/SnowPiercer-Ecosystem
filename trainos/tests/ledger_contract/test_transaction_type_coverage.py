"""Fail-closed coverage of all legacy transaction enum members."""
from decimal import Decimal

import pytest

from kernel.economy.ledger_contract import LedgerError, LegacyTransactionAdapter
from kernel.economy.transactions.transaction import Transaction
from kernel.economy.transactions.transaction_type import TransactionType


@pytest.fixture
def adapter():
    return LegacyTransactionAdapter(
        currency_codes={"currency-trc": "USD"},
        minor_unit_exponents={"USD": 2},
    )


def transaction(kind):
    return Transaction(
        transaction_id=f"type-{kind.value}",
        from_account="account-source",
        to_account="account-destination",
        amount=Decimal("10.00"),
        currency_id="currency-trc",
        transaction_type=kind,
    )


def test_every_legacy_transaction_type_is_accounted_for(adapter):
    assert {item.value for item in TransactionType} == {
        "transfer", "deposit", "withdraw", "tax", "salary", "reward", "fine", "grant"
    }


@pytest.mark.parametrize(
    "kind",
    [kind for kind in TransactionType if kind is not TransactionType.TRANSFER],
)
def test_unsupported_legacy_types_fail_closed(adapter, kind):
    with pytest.raises(LedgerError, match="only legacy TRANSFER"):
        adapter.to_journal(transaction(kind))


def test_transfer_remains_the_only_supported_mapping(adapter):
    journal = adapter.to_journal(transaction(TransactionType.TRANSFER))
    assert journal.operation_id == "type-transfer"
    assert journal.currency == "USD"
    assert sum(p.amount_minor for p in journal.postings if p.side == "debit") == 1000
    assert sum(p.amount_minor for p in journal.postings if p.side == "credit") == 1000
