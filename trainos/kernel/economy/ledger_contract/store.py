"""SQLite-backed append-only financial ledger contract v3.

Designed for deterministic local persistence and testing. Production payment
systems still require threat modelling, operational controls, backup/recovery,
reconciliation, access control and external compliance review.
"""
from __future__ import annotations

from contextlib import contextmanager
from io import StringIO
import csv
import hashlib
import json
import os
import re
import sqlite3
import tempfile
import threading
import time
import math
from pathlib import Path
from typing import Iterator

from .models import JournalEntry, LedgerError, Posting

_CURRENCY_RE = re.compile(r"^[A-Z]{3}$")


class IdempotencyConflict(LedgerError):
    """An operation ID was reused with different journal content."""


class FinancialLedger:
    """Atomic SQLite journal with idempotent append and account balance queries.

    A file-backed ledger is durable across process restarts. Use one instance per
    database path per process where possible; SQLite provides cross-connection
    transaction serialization. The class deliberately does not expose mutation
    or deletion of previously committed postings.
    """

    def __init__(self, database: str | Path = ":memory:", *, timeout_seconds: float = 10.0) -> None:
        if not isinstance(timeout_seconds, (int, float)) or not math.isfinite(timeout_seconds) or timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be finite and positive")
        self._database = str(database)
        self._timeout = float(timeout_seconds)
        self._lock = threading.RLock()
        # All construction work is covered by a single finite admission budget.
        # SQLite's busy_timeout does not reliably serialize concurrent WAL
        # journal-mode transitions on an initially empty database.
        deadline = time.monotonic() + self._timeout
        self._connection = sqlite3.connect(
            self._database, timeout=self._timeout, isolation_level=None,
            check_same_thread=False,
        )
        try:
            self._connection.row_factory = sqlite3.Row
            self._connection.execute("PRAGMA busy_timeout = %d" % min(2147483647, max(1, int(self._timeout * 1000))))
            self._connection.execute("PRAGMA foreign_keys = ON")
            if self._database != ":memory:":
                self._retry_wal_admission(deadline)
                self._connection.execute("PRAGMA synchronous = FULL")
            self._initialize()
        except BaseException:
            # sqlite3 connections are NOT closed by __del__ deterministically.
            # Never retain an abandoned handle after partial initialization.
            self._connection.close()
            raise

    def _retry_wal_admission(self, deadline: float) -> None:
        while True:
            try:
                mode = self._connection.execute("PRAGMA journal_mode = WAL").fetchone()[0]
                if str(mode).lower() != "wal":
                    raise sqlite3.OperationalError("WAL journal mode not admitted")
                return
            except sqlite3.OperationalError as exc:
                # Only transient lock contention is retryable. Corruption,
                # permission failures and unsupported modes must fail closed.
                code = getattr(exc, "sqlite_errorcode", None)
                locked = code is not None and (code & 0xff) in (sqlite3.SQLITE_BUSY, sqlite3.SQLITE_LOCKED)
                if not locked and "locked" not in str(exc).lower() and "busy" not in str(exc).lower():
                    raise
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    raise
                time.sleep(min(0.025, remaining))

    def _initialize(self) -> None:
        with self._lock:
            self._connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS ledger_metadata (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL
                );
                INSERT OR IGNORE INTO ledger_metadata(key, value) VALUES ('schema_version', '1');
                CREATE TABLE IF NOT EXISTS ledger_journals (
                    operation_id TEXT PRIMARY KEY,
                    fingerprint TEXT NOT NULL,
                    currency TEXT NOT NULL,
                    description TEXT NOT NULL,
                    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now'))
                );
                CREATE TABLE IF NOT EXISTS ledger_postings (
                    posting_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    operation_id TEXT NOT NULL REFERENCES ledger_journals(operation_id),
                    ordinal INTEGER NOT NULL,
                    account_id TEXT NOT NULL,
                    currency TEXT NOT NULL,
                    side TEXT NOT NULL CHECK (side IN ('debit','credit')),
                    amount_minor INTEGER NOT NULL CHECK (amount_minor > 0),
                    UNIQUE(operation_id, ordinal)
                );
                CREATE INDEX IF NOT EXISTS idx_ledger_postings_account_currency
                    ON ledger_postings(account_id, currency);
                CREATE TABLE IF NOT EXISTS ledger_reversals (
                    original_operation_id TEXT PRIMARY KEY REFERENCES ledger_journals(operation_id),
                    reversal_operation_id TEXT NOT NULL UNIQUE REFERENCES ledger_journals(operation_id)
                );
                CREATE TABLE IF NOT EXISTS ledger_account_policies (
                    account_id TEXT NOT NULL,
                    currency TEXT NOT NULL,
                    minimum_balance_minor INTEGER NOT NULL,
                    PRIMARY KEY(account_id, currency)
                );
                """
            )

    @staticmethod
    def _fingerprint(entry: JournalEntry) -> str:
        canonical = {
            "operation_id": entry.operation_id,
            "description": entry.description,
            "postings": [
                {"account_id": p.account_id, "currency": p.currency,
                 "side": p.side, "amount_minor": p.amount_minor}
                for p in entry.postings
            ],
        }
        encoded = json.dumps(canonical, sort_keys=True, separators=(",", ":")).encode()
        return hashlib.sha256(encoded).hexdigest()

    @contextmanager
    def _transaction(self) -> Iterator[None]:
        self._connection.execute("BEGIN IMMEDIATE")
        try:
            yield
        except BaseException:
            self._connection.rollback()
            raise
        else:
            self._connection.commit()

    def _append_in_transaction(self, entry: JournalEntry) -> bool:
        fingerprint = self._fingerprint(entry)
        existing = self._connection.execute(
            "SELECT fingerprint FROM ledger_journals WHERE operation_id = ?",
            (entry.operation_id,),
        ).fetchone()
        if existing:
            if existing["fingerprint"] != fingerprint:
                raise IdempotencyConflict(
                    f"operation_id {entry.operation_id!r} already exists with different content"
                )
            return False

        # Enforce only explicitly configured account floors. Legacy/simulation
        # accounts remain compatible until an operator opts into a policy.
        deltas: dict[tuple[str, str], int] = {}
        for posting in entry.postings:
            key = (posting.account_id, posting.currency)
            deltas[key] = deltas.get(key, 0) + (
                posting.amount_minor if posting.side == "credit" else -posting.amount_minor
            )
        for (account_id, currency), delta in deltas.items():
            policy = self._connection.execute(
                "SELECT minimum_balance_minor FROM ledger_account_policies "
                "WHERE account_id = ? AND currency = ?", (account_id, currency),
            ).fetchone()
            if policy is not None:
                current = self._connection.execute(
                    "SELECT COALESCE(SUM(CASE side WHEN 'credit' THEN amount_minor "
                    "ELSE -amount_minor END), 0) AS balance FROM ledger_postings "
                    "WHERE account_id = ? AND currency = ?", (account_id, currency),
                ).fetchone()["balance"]
                if int(current) + delta < int(policy["minimum_balance_minor"]):
                    raise LedgerError(
                        f"account {account_id!r} would fall below its configured minimum balance"
                    )

        self._connection.execute(
            "INSERT INTO ledger_journals(operation_id, fingerprint, currency, description) "
            "VALUES (?, ?, ?, ?)",
            (entry.operation_id, fingerprint, entry.currency, entry.description),
        )
        self._connection.executemany(
            "INSERT INTO ledger_postings(operation_id, ordinal, account_id, currency, side, amount_minor) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            [
                (entry.operation_id, i, p.account_id, p.currency, p.side, p.amount_minor)
                for i, p in enumerate(entry.postings)
            ],
        )
        return True

    def append(self, entry: JournalEntry) -> bool:
        """Append a journal atomically; identical retries are no-ops."""
        if not isinstance(entry, JournalEntry):
            raise LedgerError("entry must be a JournalEntry")
        with self._lock, self._transaction():
            return self._append_in_transaction(entry)

    def set_minimum_balance(self, account_id: str, currency: str, minimum_balance_minor: int) -> None:
        """Configure an optional signed-balance floor for an account/currency.

        With this ledger's convention, credits increase and debits decrease the
        signed balance. A floor of zero prevents the balance becoming negative.
        No policy is enforced until explicitly configured.
        """
        if not isinstance(account_id, str) or not account_id:
            raise LedgerError("account_id is required")
        if not isinstance(currency, str) or not _CURRENCY_RE.fullmatch(currency):
            raise LedgerError("currency must be a three-letter uppercase code")
        if isinstance(minimum_balance_minor, bool) or not isinstance(minimum_balance_minor, int):
            raise LedgerError("minimum_balance_minor must be an integer")
        with self._lock, self._transaction():
            self._connection.execute(
                "INSERT INTO ledger_account_policies(account_id, currency, minimum_balance_minor) "
                "VALUES (?, ?, ?) ON CONFLICT(account_id, currency) DO UPDATE SET "
                "minimum_balance_minor = excluded.minimum_balance_minor",
                (account_id, currency, minimum_balance_minor),
            )

    def reverse(self, original_operation_id: str, reversal_operation_id: str, *, description: str = "Reversal") -> bool:
        """Create an exact compensating journal without mutating original history.

        Return True when created and False when the same reversal is retried.
        Each original journal may be reversed at most once by this API.
        """
        if not isinstance(original_operation_id, str) or not original_operation_id:
            raise LedgerError("original_operation_id is required")
        if not isinstance(reversal_operation_id, str) or not reversal_operation_id:
            raise LedgerError("reversal_operation_id is required")
        with self._lock, self._transaction():
            prior = self._connection.execute(
                "SELECT reversal_operation_id FROM ledger_reversals WHERE original_operation_id = ?",
                (original_operation_id,),
            ).fetchone()
            original = self._connection.execute(
                "SELECT currency FROM ledger_journals WHERE operation_id = ?",
                (original_operation_id,),
            ).fetchone()
            if original is None:
                raise LedgerError(f"unknown original operation {original_operation_id!r}")
            rows = self._connection.execute(
                "SELECT account_id, currency, side, amount_minor FROM ledger_postings "
                "WHERE operation_id = ? ORDER BY ordinal", (original_operation_id,),
            ).fetchall()
            reversed_postings = tuple(
                Posting(row["account_id"], row["currency"],
                        "credit" if row["side"] == "debit" else "debit",
                        int(row["amount_minor"]))
                for row in rows
            )
            entry = JournalEntry(reversal_operation_id, reversed_postings, description)
            if prior:
                if prior["reversal_operation_id"] == reversal_operation_id:
                    existing = self._connection.execute(
                        "SELECT fingerprint FROM ledger_journals WHERE operation_id = ?",
                        (reversal_operation_id,),
                    ).fetchone()
                    if existing is not None and existing["fingerprint"] == self._fingerprint(entry):
                        return False
                    raise IdempotencyConflict(
                        "reversal retry reused its ID with different content"
                    )
                raise IdempotencyConflict("original operation already has a different reversal")
            self._append_in_transaction(entry)
            self._connection.execute(
                "INSERT INTO ledger_reversals(original_operation_id, reversal_operation_id) VALUES (?, ?)",
                (original_operation_id, reversal_operation_id),
            )
            return True

    def verify_integrity(self) -> dict[str, object]:
        """Verify SQLite, journal fingerprints/balances and reversal links."""
        with self._lock:
            sqlite_rows = self._connection.execute("PRAGMA integrity_check").fetchall()
            sqlite_messages = [str(row[0]) for row in sqlite_rows]
            foreign_key_rows = self._connection.execute("PRAGMA foreign_key_check").fetchall()
            foreign_key_errors = [
                {"table": str(row[0]), "rowid": row[1], "parent": str(row[2]), "fkid": int(row[3])}
                for row in foreign_key_rows
            ]
            if foreign_key_errors:
                # Keep auditing journal contents as well; the report should surface
                # all discovered consistency problems in one pass.
                pass
            journals = self._connection.execute(
                "SELECT operation_id, fingerprint, description, currency FROM ledger_journals ORDER BY operation_id"
            ).fetchall()
            errors: list[str] = []
            for journal in journals:
                postings = self.postings(journal["operation_id"])
                try:
                    entry = JournalEntry(journal["operation_id"], postings, journal["description"])
                except LedgerError as exc:
                    errors.append(f"{journal['operation_id']}: invalid journal: {exc}")
                    continue
                if entry.currency != journal["currency"]:
                    errors.append(f"{journal['operation_id']}: stored currency mismatch")
                if self._fingerprint(entry) != journal["fingerprint"]:
                    errors.append(f"{journal['operation_id']}: fingerprint mismatch")
            reversal_links = self._connection.execute(
                "SELECT original_operation_id, reversal_operation_id FROM ledger_reversals ORDER BY original_operation_id"
            ).fetchall()
            for link in reversal_links:
                original_id = link["original_operation_id"]
                reversal_id = link["reversal_operation_id"]
                original_postings = self.postings(original_id)
                reversal_postings = self.postings(reversal_id)
                expected_inverse = sorted(
                    (p.account_id, p.currency,
                     "credit" if p.side == "debit" else "debit", p.amount_minor)
                    for p in original_postings
                )
                actual = sorted(
                    (p.account_id, p.currency, p.side, p.amount_minor)
                    for p in reversal_postings
                )
                if expected_inverse != actual:
                    errors.append(f"{original_id}: reversal postings are not an exact inverse")
            if foreign_key_errors:
                errors.append(f"foreign-key violations: {foreign_key_errors!r}")
            reconciliation = self.reconcile()
            if not reconciliation["ok"]:
                errors.append(f"reconciliation found unbalanced journals: {reconciliation['unbalanced_journals']!r}")
            return {
                "ok": sqlite_messages == ["ok"] and not foreign_key_errors and not errors,
                "sqlite_integrity": sqlite_messages,
                "foreign_key_errors": foreign_key_errors,
                "journal_count": len(journals),
                "reconciliation_ok": reconciliation["ok"],
                "errors": errors,
            }

    def balance_minor(self, account_id: str, currency: str) -> int:
        """Return signed balance: credits positive, debits negative."""
        if not account_id or not currency:
            raise LedgerError("account_id and currency are required")
        row = self._connection.execute(
            "SELECT COALESCE(SUM(CASE side WHEN 'credit' THEN amount_minor ELSE -amount_minor END), 0) AS balance "
            "FROM ledger_postings WHERE account_id = ? AND currency = ?",
            (account_id, currency),
        ).fetchone()
        return int(row["balance"])

    def journal_count(self) -> int:
        row = self._connection.execute("SELECT COUNT(*) AS n FROM ledger_journals").fetchone()
        return int(row["n"])

    def postings(self, operation_id: str) -> tuple[Posting, ...]:
        rows = self._connection.execute(
            "SELECT account_id, currency, side, amount_minor FROM ledger_postings "
            "WHERE operation_id = ? ORDER BY ordinal", (operation_id,),
        ).fetchall()
        return tuple(Posting(r["account_id"], r["currency"], r["side"], int(r["amount_minor"])) for r in rows)

    def reconcile(self) -> dict[str, object]:
        """Return a deterministic accounting reconciliation report.

        Each journal must balance independently; aggregate account balances are
        returned per (account_id, currency). This is a diagnostic snapshot, not
        an external-bank/provider settlement reconciliation.
        """
        with self._lock:
            journal_rows = self._connection.execute(
                "SELECT j.operation_id, j.currency, "
                "COALESCE(SUM(CASE p.side WHEN 'debit' THEN p.amount_minor ELSE 0 END), 0) AS debits, "
                "COALESCE(SUM(CASE p.side WHEN 'credit' THEN p.amount_minor ELSE 0 END), 0) AS credits "
                "FROM ledger_journals j LEFT JOIN ledger_postings p ON p.operation_id = j.operation_id "
                "GROUP BY j.operation_id, j.currency ORDER BY j.operation_id"
            ).fetchall()
            unbalanced = [
                {"operation_id": row["operation_id"], "currency": row["currency"],
                 "debits_minor": int(row["debits"]), "credits_minor": int(row["credits"])}
                for row in journal_rows if int(row["debits"]) != int(row["credits"])
            ]
            account_rows = self._connection.execute(
                "SELECT account_id, currency, "
                "SUM(CASE side WHEN 'credit' THEN amount_minor ELSE -amount_minor END) AS balance_minor "
                "FROM ledger_postings GROUP BY account_id, currency ORDER BY account_id, currency"
            ).fetchall()
            accounts = [
                {"account_id": row["account_id"], "currency": row["currency"],
                 "balance_minor": int(row["balance_minor"])} for row in account_rows
            ]
            return {
                "ok": not unbalanced,
                "journal_count": len(journal_rows),
                "unbalanced_journals": unbalanced,
                "account_balances": accounts,
            }

    def export_csv(self) -> str:
        """Export a stable CSV snapshot of postings for audit/reconciliation."""
        with self._lock:
            rows = self._connection.execute(
                "SELECT j.operation_id, j.created_at, j.currency AS journal_currency, "
                "j.description, p.ordinal, p.account_id, p.currency, p.side, p.amount_minor "
                "FROM ledger_journals j JOIN ledger_postings p ON p.operation_id = j.operation_id "
                "ORDER BY j.created_at, j.operation_id, p.ordinal"
            ).fetchall()
            output = StringIO(newline="")
            writer = csv.writer(output, lineterminator="\n")
            writer.writerow(["operation_id", "created_at", "journal_currency", "description",
                             "ordinal", "account_id", "currency", "side", "amount_minor"])
            for row in rows:
                writer.writerow([row[key] for key in (
                    "operation_id", "created_at", "journal_currency", "description",
                    "ordinal", "account_id", "currency", "side", "amount_minor")])
            return output.getvalue()

    @staticmethod
    def _validate_database_file(database: str | Path) -> dict[str, object]:
        """Validate a standalone database before it is accepted as a backup.

        This checks SQLite integrity, foreign keys, schema version, balanced
        journals and operation fingerprints. It is a consistency check, not a
        cryptographic authenticity check: a maliciously rewritten database and
        its fingerprints cannot be authenticated without an external trust root.
        """
        path = Path(database)
        if not path.is_file() or path.stat().st_size == 0:
            raise LedgerError("database file is missing or empty")
        conn = sqlite3.connect(str(path), timeout=10.0)
        conn.row_factory = sqlite3.Row
        try:
            integrity = [row[0] for row in conn.execute("PRAGMA integrity_check").fetchall()]
            if integrity != ["ok"]:
                raise LedgerError(f"SQLite integrity check failed: {integrity!r}")
            foreign_key_errors = conn.execute("PRAGMA foreign_key_check").fetchall()
            if foreign_key_errors:
                raise LedgerError("database contains foreign-key violations")
            tables = {row[0] for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'").fetchall()}
            required = {"ledger_metadata", "ledger_journals", "ledger_postings",
                        "ledger_reversals", "ledger_account_policies"}
            if not required.issubset(tables):
                raise LedgerError("database schema is incomplete")
            version = conn.execute(
                "SELECT value FROM ledger_metadata WHERE key='schema_version'").fetchone()
            if version is None or version[0] != "1":
                raise LedgerError("unsupported or missing ledger schema version")

            journals = conn.execute(
                "SELECT j.operation_id, j.fingerprint, j.currency, j.description, "
                "p.ordinal, p.account_id, p.currency AS posting_currency, p.side, p.amount_minor "
                "FROM ledger_journals j LEFT JOIN ledger_postings p "
                "ON p.operation_id=j.operation_id ORDER BY j.operation_id, p.ordinal"
            ).fetchall()
            grouped: dict[str, dict[str, object]] = {}
            for row in journals:
                op_id = row["operation_id"]
                item = grouped.setdefault(op_id, {
                    "fingerprint": row["fingerprint"], "currency": row["currency"],
                    "description": row["description"], "postings": []})
                if row["ordinal"] is not None:
                    item["postings"].append({
                        "ordinal": int(row["ordinal"]), "account_id": row["account_id"],
                        "currency": row["posting_currency"], "side": row["side"],
                        "amount_minor": int(row["amount_minor"]),
                    })
            for op_id, item in grouped.items():
                postings = item["postings"]
                if not postings:
                    raise LedgerError(f"journal {op_id!r} has no postings")
                debits: dict[str, int] = {}
                credits: dict[str, int] = {}
                for posting in postings:
                    target = debits if posting["side"] == "debit" else credits
                    currency = posting["currency"]
                    target[currency] = target.get(currency, 0) + posting["amount_minor"]
                if debits != credits:
                    raise LedgerError(f"journal {op_id!r} is not balanced")
                canonical = {
                    "operation_id": op_id,
                    "description": item["description"],
                    "postings": [{key: posting[key] for key in
                                  ("account_id", "currency", "side", "amount_minor")}
                                 for posting in sorted(postings, key=lambda x: x["ordinal"])],
                }
                encoded = json.dumps(canonical, sort_keys=True, separators=(",", ":")).encode()
                fingerprint = hashlib.sha256(encoded).hexdigest()
                if fingerprint != item["fingerprint"]:
                    raise LedgerError(f"journal {op_id!r} fingerprint mismatch")
            return {"ok": True, "journal_count": len(grouped), "sqlite_integrity": integrity,
                    "foreign_key_errors": 0, "schema_version": 1}
        finally:
            conn.close()

    def backup_to(self, destination: str | Path) -> dict[str, object]:
        """Create a consistent, validated SQLite backup and atomically publish it.

        Destination must be a different path from the live database. The parent
        directory must exist; callers are responsible for access controls and
        off-host backup retention.
        """
        if self._database == ":memory:":
            raise LedgerError("file-backed database is required for backup")
        source = Path(self._database).resolve()
        target = Path(destination).resolve()
        if source == target:
            raise LedgerError("backup destination must differ from source database")
        if not target.parent.is_dir():
            raise LedgerError("backup destination directory must already exist")
        fd, temporary_name = tempfile.mkstemp(prefix=f".{target.name}.", suffix=".tmp", dir=target.parent)
        os.close(fd)
        temporary = Path(temporary_name)
        try:
            with self._lock:
                destination_conn = sqlite3.connect(str(temporary))
                try:
                    self._connection.backup(destination_conn)
                    destination_conn.execute("PRAGMA journal_mode = DELETE")
                    destination_conn.commit()
                finally:
                    destination_conn.close()
            report = self._validate_database_file(temporary)
            os.replace(temporary, target)
            return {**report, "backup_path": str(target), "backup_size_bytes": target.stat().st_size}
        finally:
            if temporary.exists():
                temporary.unlink()

    @classmethod
    def restore_from_backup(
        cls, backup: str | Path, destination: str | Path, *, overwrite: bool = False,
        timeout_seconds: float = 10.0,
    ) -> dict[str, object]:
        """Restore a validated backup to a new database path.

        Existing destinations are protected by default. Restore is staged to a
        temporary file and atomically published only after validation.
        """
        source = Path(backup).resolve()
        target = Path(destination).resolve()
        if source == target:
            raise LedgerError("restore source and destination must differ")
        if not target.parent.is_dir():
            raise LedgerError("restore destination directory must already exist")
        if target.exists() and not overwrite:
            raise LedgerError("restore destination already exists; pass overwrite=True explicitly")
        source_report = cls._validate_database_file(source)
        fd, temporary_name = tempfile.mkstemp(prefix=f".{target.name}.", suffix=".restore", dir=target.parent)
        os.close(fd)
        temporary = Path(temporary_name)
        try:
            source_conn = sqlite3.connect(str(source), timeout=timeout_seconds)
            destination_conn = sqlite3.connect(str(temporary), timeout=timeout_seconds)
            try:
                source_conn.backup(destination_conn)
                destination_conn.execute("PRAGMA journal_mode = DELETE")
                destination_conn.commit()
            finally:
                destination_conn.close()
                source_conn.close()
            restored_report = cls._validate_database_file(temporary)
            if overwrite:
                os.replace(temporary, target)
            else:
                # Atomic no-clobber publication. A pre-check alone is vulnerable
                # to a race if another process creates target before publication.
                try:
                    os.link(temporary, target)
                except FileExistsError as exc:
                    raise LedgerError(
                        "restore destination already exists; pass overwrite=True explicitly"
                    ) from exc
                temporary.unlink()
            return {**restored_report, "restored_from": str(source),
                    "destination": str(target), "source_journal_count": source_report["journal_count"]}
        finally:
            if temporary.exists():
                temporary.unlink()

    def close(self) -> None:
        with self._lock:
            self._connection.close()

    def __enter__(self) -> "FinancialLedger":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.close()
