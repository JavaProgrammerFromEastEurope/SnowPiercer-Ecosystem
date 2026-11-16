from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor
import multiprocessing
import threading
from pathlib import Path

import pytest

from kernel.economy.ledger_contract import (
    FinancialLedger, IdempotencyConflict, JournalEntry, LedgerError, Posting,
)


def transfer(operation_id="op-1", amount=1250):
    return JournalEntry(operation_id, (
        Posting("customer:1", "JPY", "debit", amount),
        Posting("merchant:1", "JPY", "credit", amount),
    ), "test transfer")


def test_valid_append_and_signed_balances():
    with FinancialLedger() as ledger:
        assert ledger.append(transfer()) is True
        assert ledger.balance_minor("customer:1", "JPY") == -1250
        assert ledger.balance_minor("merchant:1", "JPY") == 1250
        assert ledger.balance_minor("merchant:1", "USD") == 0
        assert ledger.journal_count() == 1


def test_identical_retry_is_idempotent():
    with FinancialLedger() as ledger:
        assert ledger.append(transfer()) is True
        assert ledger.append(transfer()) is False
        assert ledger.journal_count() == 1
        assert ledger.balance_minor("merchant:1", "JPY") == 1250


def test_reusing_operation_id_with_changed_content_fails():
    with FinancialLedger() as ledger:
        ledger.append(transfer())
        with pytest.raises(IdempotencyConflict):
            ledger.append(transfer(amount=1251))
        assert ledger.journal_count() == 1


@pytest.mark.parametrize("postings", [
    (Posting("a", "JPY", "debit", 100), Posting("b", "JPY", "credit", 99)),
    (Posting("a", "JPY", "debit", 100), Posting("b", "USD", "credit", 100)),
    (Posting("a", "JPY", "debit", 100), Posting("b", "JPY", "debit", 100)),
])
def test_unbalanced_mixed_currency_or_one_sided_journals_are_rejected(postings):
    with pytest.raises(LedgerError):
        JournalEntry("bad", postings)


def test_amount_must_be_positive_integer_minor_units():
    with pytest.raises(LedgerError):
        Posting("a", "JPY", "debit", 1.5)
    with pytest.raises(LedgerError):
        Posting("a", "JPY", "debit", 0)


def test_file_backed_ledger_survives_reopen(tmp_path: Path):
    db = tmp_path / "ledger.sqlite3"
    with FinancialLedger(db) as ledger:
        ledger.append(transfer())
    with FinancialLedger(db) as reopened:
        assert reopened.journal_count() == 1
        assert reopened.balance_minor("merchant:1", "JPY") == 1250
        assert reopened.postings("op-1") == transfer().postings


def test_concurrent_identical_retries_commit_once(tmp_path: Path):
    db = tmp_path / "concurrent.sqlite3"

    def append_once(_):
        with FinancialLedger(db) as ledger:
            return ledger.append(transfer("shared-operation"))

    with ThreadPoolExecutor(max_workers=8) as pool:
        results = list(pool.map(append_once, range(24)))
    assert results.count(True) == 1
    assert results.count(False) == 23
    with FinancialLedger(db) as ledger:
        assert ledger.journal_count() == 1
        assert ledger.balance_minor("merchant:1", "JPY") == 1250


def test_database_constraints_and_ledger_are_append_only_via_public_api():
    with FinancialLedger() as ledger:
        ledger.append(transfer())
        assert ledger.postings("op-1") == transfer().postings
        assert not hasattr(ledger, "delete_journal")


def test_exact_reversal_is_compensating_and_idempotent():
    with FinancialLedger() as ledger:
        ledger.append(transfer("sale-1", 700))
        assert ledger.reverse("sale-1", "refund-1", description="Refund") is True
        assert ledger.reverse("sale-1", "refund-1", description="Refund") is False
        assert ledger.balance_minor("customer:1", "JPY") == 0
        assert ledger.balance_minor("merchant:1", "JPY") == 0
        assert ledger.journal_count() == 2
        assert ledger.postings("sale-1") == transfer("sale-1", 700).postings


def test_original_cannot_be_reversed_twice_with_different_id():
    with FinancialLedger() as ledger:
        ledger.append(transfer("sale-2", 700))
        ledger.reverse("sale-2", "refund-2")
        with pytest.raises(IdempotencyConflict):
            ledger.reverse("sale-2", "refund-3")


def test_reverse_unknown_operation_fails():
    with FinancialLedger() as ledger:
        with pytest.raises(LedgerError):
            ledger.reverse("missing", "refund-missing")


def test_minimum_balance_policy_is_opt_in_and_enforced_atomically():
    with FinancialLedger() as ledger:
        ledger.set_minimum_balance("customer:1", "JPY", 0)
        with pytest.raises(LedgerError):
            ledger.append(transfer("overspend", 100))
        assert ledger.journal_count() == 0
        # Credit the account first, then a debit transfer is permitted.
        funding = JournalEntry("funding", (
            Posting("external", "JPY", "debit", 200),
            Posting("customer:1", "JPY", "credit", 200),
        ), "funding")
        ledger.append(funding)
        assert ledger.append(transfer("within-balance", 150)) is True
        assert ledger.balance_minor("customer:1", "JPY") == 50
        with pytest.raises(LedgerError):
            ledger.append(transfer("overspend-again", 100))
        assert ledger.balance_minor("customer:1", "JPY") == 50


def test_integrity_verification_passes_for_valid_ledger_and_reversal(tmp_path: Path):
    db = tmp_path / "integrity.sqlite3"
    with FinancialLedger(db) as ledger:
        ledger.append(transfer("sale-integrity", 321))
        ledger.reverse("sale-integrity", "refund-integrity")
        report = ledger.verify_integrity()
        assert report["ok"] is True
        assert report["sqlite_integrity"] == ["ok"]
        assert report["journal_count"] == 2
        assert report["errors"] == []


def _append_from_process(database: str, operation_id: str) -> bool:
    with FinancialLedger(database) as ledger:
        return ledger.append(transfer(operation_id, 888))


def test_concurrent_identical_retries_commit_once_across_processes(tmp_path: Path):
    db = str(tmp_path / "multiprocess.sqlite3")
    with ProcessPoolExecutor(max_workers=4, mp_context=multiprocessing.get_context("spawn")) as pool:
        results = list(pool.map(_append_from_process, [db] * 12, ["process-shared"] * 12))
    assert results.count(True) == 1
    assert results.count(False) == 11
    with FinancialLedger(db) as ledger:
        assert ledger.journal_count() == 1
        assert ledger.balance_minor("merchant:1", "JPY") == 888


def test_failed_posting_insert_rolls_back_header_and_recovers_after_reopen(tmp_path: Path):
    db = tmp_path / "rollback.sqlite3"
    with FinancialLedger(db) as ledger:
        ledger._connection.execute(
            "CREATE TRIGGER reject_crash_sim BEFORE INSERT ON ledger_postings "
            "WHEN NEW.operation_id = 'crash-sim' BEGIN SELECT RAISE(ABORT, 'simulated crash'); END"
        )
        with pytest.raises(Exception):
            ledger.append(transfer("crash-sim", 99))
        assert ledger.journal_count() == 0
        ledger._connection.execute("DROP TRIGGER reject_crash_sim")
    with FinancialLedger(db) as reopened:
        assert reopened.journal_count() == 0
        assert reopened.append(transfer("crash-sim", 99)) is True
        assert reopened.verify_integrity()["ok"] is True


def test_reconciliation_and_csv_export_are_consistent():
    with FinancialLedger() as ledger:
        ledger.append(transfer("reconcile-1", 500))
        ledger.append(transfer("reconcile-2", 250))
        report = ledger.reconcile()
        assert report["ok"] is True
        assert report["journal_count"] == 2
        balances = {(x["account_id"], x["currency"]): x["balance_minor"]
                    for x in report["account_balances"]}
        assert balances[("customer:1", "JPY")] == -750
        assert balances[("merchant:1", "JPY")] == 750
        exported = ledger.export_csv()
        assert exported.startswith("operation_id,created_at,journal_currency,description,")
        assert "reconcile-1" in exported and "reconcile-2" in exported
        assert ledger.verify_integrity()["ok"] is True


def _reverse_from_process(database: str, original_id: str, reversal_id: str) -> bool:
    with FinancialLedger(database) as ledger:
        return ledger.reverse(original_id, reversal_id)


def test_concurrent_reversal_retries_across_processes_commit_once(tmp_path: Path):
    db = str(tmp_path / "concurrent-reversal.sqlite3")
    with FinancialLedger(db) as ledger:
        ledger.append(transfer("sale-concurrent-reversal", 444))
    with ProcessPoolExecutor(max_workers=4, mp_context=multiprocessing.get_context("spawn")) as pool:
        results = list(pool.map(
            _reverse_from_process,
            [db] * 8,
            ["sale-concurrent-reversal"] * 8,
            ["refund-concurrent-reversal"] * 8,
        ))
    assert results.count(True) == 1
    assert results.count(False) == 7
    with FinancialLedger(db) as ledger:
        assert ledger.journal_count() == 2
        assert ledger.verify_integrity()["ok"] is True


def test_reversal_retry_with_changed_description_is_conflict():
    with FinancialLedger() as ledger:
        ledger.append(transfer("sale-description", 700))
        assert ledger.reverse("sale-description", "refund-description", description="Refund") is True
        with pytest.raises(IdempotencyConflict, match="different content"):
            ledger.reverse("sale-description", "refund-description", description="Different refund")
        assert ledger.journal_count() == 2


def test_backup_and_restore_preserve_balances_and_verify_integrity(tmp_path: Path):
    source = tmp_path / "source.sqlite3"
    backup = tmp_path / "backups" / "ledger.backup.sqlite3"
    backup.parent.mkdir()
    restored = tmp_path / "restored.sqlite3"
    with FinancialLedger(source) as ledger:
        ledger.append(transfer("backup-op-1", 1234))
        ledger.append(transfer("backup-op-2", 321))
        report = ledger.backup_to(backup)
        assert report["ok"] is True
        assert report["journal_count"] == 2
    restore_report = FinancialLedger.restore_from_backup(backup, restored)
    assert restore_report["ok"] is True
    assert restore_report["source_journal_count"] == 2
    with FinancialLedger(restored) as ledger:
        assert ledger.journal_count() == 2
        assert ledger.balance_minor("merchant:1", "JPY") == 1555
        assert ledger.verify_integrity()["ok"] is True
        assert ledger.reconcile()["ok"] is True


def test_restore_refuses_to_overwrite_existing_destination_by_default(tmp_path: Path):
    source = tmp_path / "source.sqlite3"
    backup = tmp_path / "backup.sqlite3"
    destination = tmp_path / "destination.sqlite3"
    with FinancialLedger(source) as ledger:
        ledger.append(transfer("safe-restore", 10))
        ledger.backup_to(backup)
    destination.write_bytes(b"keep-existing")
    with pytest.raises(LedgerError, match="already exists"):
        FinancialLedger.restore_from_backup(backup, destination)
    assert destination.read_bytes() == b"keep-existing"


def test_restore_rejects_corrupt_or_incomplete_backup_without_publishing(tmp_path: Path):
    source = tmp_path / "source.sqlite3"
    backup = tmp_path / "backup.sqlite3"
    destination = tmp_path / "restored.sqlite3"
    with FinancialLedger(source) as ledger:
        ledger.append(transfer("restore-valid", 100))
        ledger.backup_to(backup)
    corrupt = tmp_path / "corrupt.sqlite3"
    corrupt.write_bytes(b"not a sqlite database")
    with pytest.raises(Exception):
        FinancialLedger.restore_from_backup(corrupt, destination)
    assert not destination.exists()


def test_backup_rejects_in_memory_database(tmp_path: Path):
    with FinancialLedger() as ledger:
        with pytest.raises(LedgerError, match="file-backed"):
            ledger.backup_to(tmp_path / "memory.backup.sqlite3")


def test_backup_detects_tampered_journal_fingerprint(tmp_path: Path):
    source = tmp_path / "tampered.sqlite3"
    backup = tmp_path / "tampered-backup.sqlite3"
    with FinancialLedger(source) as ledger:
        ledger.append(transfer("tamper-source", 100))
        ledger._connection.execute(
            "UPDATE ledger_journals SET description='changed without fingerprint update' "
            "WHERE operation_id='tamper-source'"
        )
        with pytest.raises(LedgerError, match="fingerprint mismatch"):
            ledger.backup_to(backup)
    assert not backup.exists()


def test_restore_rejects_unsupported_schema_version_without_publishing(tmp_path: Path):
    source = tmp_path / "schema-source.sqlite3"
    backup = tmp_path / "schema-backup.sqlite3"
    destination = tmp_path / "schema-restored.sqlite3"
    with FinancialLedger(source) as ledger:
        ledger.append(transfer("schema-op", 50))
        ledger.backup_to(backup)
    connection = __import__("sqlite3").connect(backup)
    try:
        connection.execute(
            "UPDATE ledger_metadata SET value='999' WHERE key='schema_version'"
        )
        connection.commit()
    finally:
        connection.close()
    with pytest.raises(LedgerError, match="schema version"):
        FinancialLedger.restore_from_backup(backup, destination)
    assert not destination.exists()


def test_restore_overwrite_is_explicit_and_restored_database_is_usable(tmp_path: Path):
    source = tmp_path / "overwrite-source.sqlite3"
    backup = tmp_path / "overwrite-backup.sqlite3"
    destination = tmp_path / "overwrite-destination.sqlite3"
    with FinancialLedger(source) as ledger:
        ledger.append(transfer("restore-current", 400))
        ledger.backup_to(backup)
    destination.write_bytes(b"old destination")
    report = FinancialLedger.restore_from_backup(backup, destination, overwrite=True)
    assert report["ok"] is True
    with FinancialLedger(destination) as restored:
        assert restored.balance_minor("merchant:1", "JPY") == 400
        assert restored.verify_integrity()["ok"] is True


def test_backup_preserves_reversal_links_and_account_policies(tmp_path: Path):
    source = tmp_path / "state-source.sqlite3"
    backup = tmp_path / "state-backup.sqlite3"
    destination = tmp_path / "state-restored.sqlite3"
    with FinancialLedger(source) as ledger:
        ledger.set_minimum_balance("wallet", "JPY", 0)
        ledger.append(JournalEntry("fund-wallet", (
            Posting("external", "JPY", "debit", 500),
            Posting("wallet", "JPY", "credit", 500),
        ), "fund wallet"))
        ledger.append(JournalEntry("spend-wallet", (
            Posting("wallet", "JPY", "debit", 125),
            Posting("merchant", "JPY", "credit", 125),
        ), "spend wallet"))
        ledger.reverse("spend-wallet", "refund-wallet")
        ledger.backup_to(backup)
    FinancialLedger.restore_from_backup(backup, destination)
    with FinancialLedger(destination) as restored:
        assert restored.balance_minor("wallet", "JPY") == 500
        assert restored.verify_integrity()["ok"] is True
        with pytest.raises(LedgerError, match="minimum balance"):
            restored.append(JournalEntry("overspend-restored", (
                Posting("wallet", "JPY", "debit", 501),
                Posting("merchant", "JPY", "credit", 501),
            ), "should fail"))


def test_restore_no_clobber_publication_is_atomic(tmp_path: Path):
    source = tmp_path / "race-source.sqlite3"
    backup = tmp_path / "race-backup.sqlite3"
    destination = tmp_path / "race-destination.sqlite3"
    with FinancialLedger(source) as ledger:
        ledger.append(transfer("race-op", 10))
        ledger.backup_to(backup)
    destination.write_bytes(b"preserve me")
    with pytest.raises(LedgerError, match="already exists"):
        FinancialLedger.restore_from_backup(backup, destination)
    assert destination.read_bytes() == b"preserve me"


def test_integrity_and_reconcile_both_detect_posting_tampering(tmp_path: Path):
    db = tmp_path / "posting-tamper.sqlite3"
    with FinancialLedger(db) as ledger:
        ledger.append(transfer("tamper-posting", 100))
        # Simulate out-of-band database corruption, bypassing the public API.
        ledger._connection.execute(
            "UPDATE ledger_postings SET amount_minor=99 "
            "WHERE operation_id='tamper-posting' AND side='credit'"
        )
        integrity = ledger.verify_integrity()
        reconciliation = ledger.reconcile()
        assert integrity["ok"] is False
        assert integrity["reconciliation_ok"] is False
        assert reconciliation["ok"] is False
        assert any("invalid journal" in error or "fingerprint mismatch" in error for error in integrity["errors"])


def test_integrity_detects_foreign_key_violations(tmp_path: Path):
    import sqlite3

    db = tmp_path / "foreign-key-tamper.sqlite3"
    with FinancialLedger(db) as ledger:
        ledger.append(transfer("fk-tamper", 100))
        # Use a separate connection with FK enforcement disabled to simulate
        # corruption from an external maintenance tool.
        connection = sqlite3.connect(db)
        try:
            connection.execute("PRAGMA foreign_keys=OFF")
            connection.execute("DELETE FROM ledger_journals WHERE operation_id='fk-tamper'")
            connection.commit()
        finally:
            connection.close()
        report = ledger.verify_integrity()
        assert report["ok"] is False
        assert report["foreign_key_errors"]


def test_backup_during_concurrent_appends_is_a_consistent_snapshot(tmp_path: Path):
    db = tmp_path / "concurrent-backup-source.sqlite3"
    backup = tmp_path / "concurrent-backup.sqlite3"
    start = threading.Event()
    # Initialize schema before competing writer connections open the database.
    with FinancialLedger(db):
        pass

    def writer(worker: int) -> int:
        start.wait(timeout=5)
        committed = 0
        for i in range(20):
            op_id = f"backup-w{worker}-{i}"
            with FinancialLedger(db) as ledger:
                ledger.append(transfer(op_id, 10 + i))
            committed += 1
        return committed

    with ThreadPoolExecutor(max_workers=4) as pool:
        futures = [pool.submit(writer, worker) for worker in range(4)]
        start.set()
        # Take a valid SQLite snapshot while independent connections are writing.
        with FinancialLedger(db) as ledger:
            report = ledger.backup_to(backup)
        committed = sum(f.result(timeout=15) for f in futures)

    assert committed == 80
    assert report["ok"] is True
    with FinancialLedger(backup) as snapshot:
        assert snapshot.verify_integrity()["ok"] is True
        assert snapshot.reconcile()["ok"] is True
        assert snapshot.journal_count() <= 80


def test_reversal_posting_tampering_is_detected_by_integrity_check(tmp_path: Path):
    db = tmp_path / "reversal-tamper.sqlite3"
    with FinancialLedger(db) as ledger:
        ledger.append(transfer("sale-tamper-reversal", 200))
        ledger.reverse("sale-tamper-reversal", "refund-tamper-reversal")
        ledger._connection.execute(
            "UPDATE ledger_postings SET amount_minor=199 "
            "WHERE operation_id='refund-tamper-reversal' AND side='debit'"
        )
        report = ledger.verify_integrity()
        assert report["ok"] is False
        assert any("fingerprint mismatch" in error or "exact inverse" in error
                   for error in report["errors"])
