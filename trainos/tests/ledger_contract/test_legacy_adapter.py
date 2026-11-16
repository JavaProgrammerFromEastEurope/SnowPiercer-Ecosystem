from decimal import Decimal

import pytest

from kernel.economy.ledger_contract import FinancialLedger, LedgerError, LegacyTransactionAdapter
from kernel.economy.transactions.transaction import Transaction
from kernel.economy.transactions.transaction_type import TransactionType


def tx(**overrides):
    values = dict(
        transaction_id="TX-0001", from_account="ACC-1", to_account="ACC-2",
        amount=Decimal("25.00"), currency_id="currency-trc",
        transaction_type=TransactionType.TRANSFER,
    )
    values.update(overrides)
    return Transaction(**values)


def adapter():
    return LegacyTransactionAdapter(
        currency_codes={"currency-trc": "USD"},
        minor_unit_exponents={"USD": 2, "JPY": 0},
    )


def test_transfer_maps_to_balanced_minor_unit_journal():
    journal = adapter().to_journal(tx())
    assert journal.operation_id == "TX-0001"
    assert journal.currency == "USD"
    assert [(p.account_id, p.side, p.amount_minor) for p in journal.postings] == [
        ("ACC-1", "debit", 2500), ("ACC-2", "credit", 2500),
    ]


def test_adapter_append_preserves_legacy_balance_semantics_and_idempotency():
    bridge = adapter()
    with FinancialLedger() as ledger:
        assert bridge.append(tx(), ledger) is True
        assert bridge.append(tx(), ledger) is False
        assert ledger.balance_minor("ACC-1", "USD") == -2500
        assert ledger.balance_minor("ACC-2", "USD") == 2500


def test_unknown_currency_mapping_is_rejected():
    with pytest.raises(LedgerError, match="mapping"):
        adapter().to_journal(tx(currency_id="unknown"))


def test_missing_account_is_rejected_not_guessed():
    with pytest.raises(LedgerError, match="both from_account"):
        adapter().to_journal(tx(from_account=None))


def test_non_transfer_types_are_rejected_until_explicitly_mapped():
    with pytest.raises(LedgerError, match="only legacy TRANSFER"):
        adapter().to_journal(tx(transaction_type=TransactionType.DEPOSIT))


def test_excess_precision_is_rejected_without_rounding():
    with pytest.raises(LedgerError, match="more precision"):
        adapter().to_journal(tx(amount=Decimal("1.001")))


@pytest.mark.parametrize("amount", [Decimal("0"), Decimal("-1"), Decimal("NaN"), Decimal("Infinity")])
def test_non_positive_or_non_finite_amount_is_rejected(amount):
    with pytest.raises(LedgerError):
        adapter().to_journal(tx(amount=amount))


def test_same_account_and_unknown_type_shape_are_rejected():
    with pytest.raises(LedgerError, match="must differ"):
        adapter().to_journal(tx(to_account="ACC-1"))


def test_explicit_currency_registry_is_checked_against_adapter_exponents():
    from kernel.economy.ledger_contract import CurrencyRegistry, CurrencySpec

    registry = CurrencyRegistry((CurrencySpec("USD", 2), CurrencySpec("JPY", 0)))
    bridge = LegacyTransactionAdapter(
        currency_codes={"currency-trc": "USD"},
        minor_unit_exponents={"USD": 2},
        currency_registry=registry,
    )
    assert bridge.to_journal(tx()).postings[0].amount_minor == 2500


def test_currency_registry_rejects_unregistered_and_disabled_currency():
    from kernel.economy.ledger_contract import CurrencyRegistry, CurrencySpec

    registry = CurrencyRegistry((CurrencySpec("USD", 2), CurrencySpec("JPY", 0, enabled=False)))
    with pytest.raises(LedgerError, match="not registered"):
        registry.get("EUR")
    with pytest.raises(LedgerError, match="disabled"):
        registry.get("JPY")


def test_currency_registry_rejects_duplicate_codes_and_bad_exponents():
    from kernel.economy.ledger_contract import CurrencyRegistry, CurrencySpec

    with pytest.raises(LedgerError, match="duplicate"):
        CurrencyRegistry((CurrencySpec("USD", 2), CurrencySpec("USD", 2)))
    with pytest.raises(LedgerError, match="between 0 and 6"):
        CurrencySpec("USD", 7)


def test_adapter_rejects_registry_exponent_mismatch():
    from kernel.economy.ledger_contract import CurrencyRegistry, CurrencySpec

    registry = CurrencyRegistry((CurrencySpec("USD", 0),))
    with pytest.raises(LedgerError, match="disagrees with registry"):
        LegacyTransactionAdapter(
            currency_codes={"currency-trc": "USD"},
            minor_unit_exponents={"USD": 2},
            currency_registry=registry,
        )
