from tests.sqlite_resource_helpers import managed_sqlite_connection
import json
import sqlite3
from pathlib import Path

import pytest

from kernel.economy.ledger_contract import (
    FinancialLedger, JournalEntry, LedgerError, Posting, create_checkpoint, verify_checkpoint,
)

KEY_OLD = b"old-key-for-tests-only-32-bytes-minimum!"
KEY_NEW = b"new-key-for-tests-only-32-bytes-minimum!"


def _entry(operation_id="anchor-op", amount=100):
    return JournalEntry(operation_id, (
        Posting("external", "JPY", "debit", amount),
        Posting("merchant", "JPY", "credit", amount),
    ), "checkpoint test")


def test_checkpoint_signs_external_database_and_verifies(tmp_path: Path):
    db = tmp_path / "ledger.sqlite3"
    backup = tmp_path / "backup.sqlite3"
    manifest = tmp_path / "backup.checkpoint.json"
    with FinancialLedger(db) as ledger:
        ledger.append(_entry())
        ledger.backup_to(backup)
    report = create_checkpoint(backup, manifest, key_id="key-2026-a", signing_key=KEY_OLD)
    assert report["ok"] is True
    verified = verify_checkpoint(backup, manifest, keyring={"key-2026-a": KEY_OLD})
    assert verified["ok"] is True
    assert verified["journal_count"] == 1


def test_database_tampering_is_detected_even_if_internal_fingerprint_is_recomputed(tmp_path: Path):
    db = tmp_path / "ledger.sqlite3"
    manifest = tmp_path / "ledger.checkpoint.json"
    with FinancialLedger(db) as ledger:
        ledger.append(_entry())
        ledger.backup_to(tmp_path / "backup.sqlite3")
    backup = tmp_path / "backup.sqlite3"
    create_checkpoint(backup, manifest, key_id="key-a", signing_key=KEY_OLD)

    # Rewrite a balanced journal and its internal fingerprint to simulate an
    # attacker who can modify SQLite and recalculate database-local hashes.
    with managed_sqlite_connection(backup) as conn:
        conn.execute("UPDATE ledger_postings SET amount_minor=101 WHERE operation_id='anchor-op'")
        canonical = {
            "operation_id": "anchor-op", "description": "checkpoint test",
            "postings": [
                {"account_id": "external", "currency": "JPY", "side": "debit", "amount_minor": 101},
                {"account_id": "merchant", "currency": "JPY", "side": "credit", "amount_minor": 101},
            ],
        }
        import hashlib
        conn.execute("UPDATE ledger_journals SET fingerprint=? WHERE operation_id='anchor-op'",
                     (hashlib.sha256(json.dumps(canonical, sort_keys=True, separators=(",", ":")).encode()).hexdigest(),))
    with pytest.raises(LedgerError, match="does not match signed checkpoint"):
        verify_checkpoint(backup, manifest, keyring={"key-a": KEY_OLD})


def test_manifest_tampering_and_untrusted_key_are_rejected(tmp_path: Path):
    db = tmp_path / "ledger.sqlite3"
    manifest = tmp_path / "checkpoint.json"
    with FinancialLedger(db) as ledger:
        ledger.append(_entry())
        ledger.backup_to(tmp_path / "backup.sqlite3")
    backup = tmp_path / "backup.sqlite3"
    create_checkpoint(backup, manifest, key_id="key-a", signing_key=KEY_OLD)
    doc = json.loads(manifest.read_text())
    doc["journal_count"] = 999
    manifest.write_text(json.dumps(doc))
    with pytest.raises(LedgerError, match="signature verification failed"):
        verify_checkpoint(backup, manifest, keyring={"key-a": KEY_OLD})
    create_checkpoint(backup, manifest, key_id="key-a", signing_key=KEY_OLD)
    with pytest.raises(LedgerError, match="not trusted"):
        verify_checkpoint(backup, manifest, keyring={"key-b": KEY_NEW})


def test_key_rotation_accepts_old_manifest_and_new_manifest(tmp_path: Path):
    db = tmp_path / "ledger.sqlite3"
    manifest_old = tmp_path / "old.json"
    manifest_new = tmp_path / "new.json"
    with FinancialLedger(db) as ledger:
        ledger.append(_entry())
        ledger.backup_to(tmp_path / "backup.sqlite3")
    backup = tmp_path / "backup.sqlite3"
    create_checkpoint(backup, manifest_old, key_id="key-old", signing_key=KEY_OLD)
    create_checkpoint(backup, manifest_new, key_id="key-new", signing_key=KEY_NEW)
    dual_keyring = {"key-old": KEY_OLD, "key-new": KEY_NEW}
    assert verify_checkpoint(backup, manifest_old, keyring=dual_keyring)["key_id"] == "key-old"
    assert verify_checkpoint(backup, manifest_new, keyring=dual_keyring)["key_id"] == "key-new"
    assert verify_checkpoint(backup, manifest_new, keyring={"key-new": KEY_NEW})["ok"] is True


def test_checkpoint_refuses_missing_or_short_key(tmp_path: Path):
    db = tmp_path / "ledger.sqlite3"
    with FinancialLedger(db) as ledger:
        ledger.append(_entry())
        ledger.backup_to(tmp_path / "backup.sqlite3")
    with pytest.raises(LedgerError, match="at least 32 bytes"):
        create_checkpoint(tmp_path / "backup.sqlite3", tmp_path / "checkpoint.json",
                          key_id="weak", signing_key=b"short")


def test_checkpoint_sequence_and_trusted_digest_detect_rollback(tmp_path: Path):
    db = tmp_path / "ledger.sqlite3"
    backup = tmp_path / "backup.sqlite3"
    first_manifest = tmp_path / "checkpoint-1.json"
    second_manifest = tmp_path / "checkpoint-2.json"
    with FinancialLedger(db) as ledger:
        ledger.append(_entry("sequence-1", 100))
        ledger.backup_to(backup)
    first = create_checkpoint(
        backup, first_manifest, key_id="key-a", signing_key=KEY_OLD, sequence=1
    )
    assert verify_checkpoint(
        backup, first_manifest, keyring={"key-a": KEY_OLD},
        minimum_sequence=1, expected_manifest_sha256=first["manifest_sha256"],
    )["sequence"] == 1

    with FinancialLedger(db) as ledger:
        ledger.append(_entry("sequence-2", 200))
        ledger.backup_to(backup)
    second = create_checkpoint(
        backup, second_manifest, key_id="key-a", signing_key=KEY_OLD,
        sequence=2, previous_manifest_sha256=first["manifest_sha256"],
    )
    verified = verify_checkpoint(
        backup, second_manifest, keyring={"key-a": KEY_OLD},
        minimum_sequence=2, expected_manifest_sha256=second["manifest_sha256"],
    )
    assert verified["sequence"] == 2
    assert verified["previous_manifest_sha256"] == first["manifest_sha256"]

    with pytest.raises(LedgerError, match="rollback detected"):
        verify_checkpoint(
            tmp_path / "backup.sqlite3", first_manifest,
            keyring={"key-a": KEY_OLD}, minimum_sequence=2,
        )
    with pytest.raises(LedgerError, match="digest mismatch"):
        verify_checkpoint(
            backup, second_manifest, keyring={"key-a": KEY_OLD},
            expected_manifest_sha256=first["manifest_sha256"],
        )


def test_checkpoint_sequence_rejects_invalid_values(tmp_path: Path):
    db = tmp_path / "ledger.sqlite3"
    with FinancialLedger(db) as ledger:
        ledger.append(_entry())
        ledger.backup_to(tmp_path / "backup.sqlite3")
    with pytest.raises(LedgerError, match="positive integer"):
        create_checkpoint(
            tmp_path / "backup.sqlite3", tmp_path / "checkpoint.json",
            key_id="key-a", signing_key=KEY_OLD, sequence=0,
        )
    with pytest.raises(LedgerError, match="positive integer"):
        verify_checkpoint(
            tmp_path / "backup.sqlite3", tmp_path / "nonexistent.json",
            keyring={"key-a": KEY_OLD}, minimum_sequence=0,
        )
