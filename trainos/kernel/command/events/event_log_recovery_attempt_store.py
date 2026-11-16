"""Durable recovery-attempt journal with explicit retry authorization.

This journal prevents accidental infinite retries; it is not tamper-proof and should
be stored separately from the event database in deployments that need stronger trust.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from enum import Enum
from pathlib import Path
import sqlite3
import os
import math
from threading import RLock
from uuid import uuid4


class RecoveryAttemptStatus(str, Enum):
    IN_PROGRESS = "in_progress"
    FAILED = "failed"
    RETRY_AUTHORIZED = "retry_authorized"
    SUCCEEDED = "succeeded"


class RecoveryAttemptBlocked(RuntimeError):
    """A recovery attempt cannot start without resolving its durable prior state."""


@dataclass(frozen=True, slots=True)
class RecoveryAttempt:
    attempt_key: str
    status: RecoveryAttemptStatus
    attempt_count: int
    reason: str
    started_at: str | None
    updated_at: str
    last_error: str | None
    authorized_by: str | None
    authorization_reason: str | None
    checkpoint_fingerprint: str | None
    max_attempts: int
    owner_run_id: str | None = None
    fencing_token: int = 0
    owner_pid: int | None = None
    lease_expires_at: str | None = None


class EventLogRecoveryAttemptStore:
    """Persist recovery state and require explicit authorization after failure."""

    def __init__(self, database_path: str | Path):
        if not isinstance(database_path, (str, Path)) or not str(database_path).strip():
            raise ValueError("database_path must not be empty")
        self.database_path = str(Path(database_path).expanduser().resolve())
        Path(self.database_path).parent.mkdir(parents=True, exist_ok=True)
        self._lock = RLock()
        self._connection = sqlite3.connect(self.database_path, timeout=5.0, check_same_thread=False)
        try:
            self._connection.row_factory = sqlite3.Row
            with self._lock:
                self._connection.execute("""
                    CREATE TABLE IF NOT EXISTS recovery_attempts (
                        attempt_key TEXT PRIMARY KEY,
                        status TEXT NOT NULL,
                        attempt_count INTEGER NOT NULL CHECK(attempt_count >= 1),
                        reason TEXT NOT NULL,
                        started_at TEXT,
                        updated_at TEXT NOT NULL,
                        last_error TEXT,
                        authorized_by TEXT,
                        authorization_reason TEXT,
                        checkpoint_fingerprint TEXT,
                        max_attempts INTEGER NOT NULL DEFAULT 3 CHECK(max_attempts >= 1),
                        owner_pid INTEGER,
                        owner_run_id TEXT,
                        fencing_token INTEGER NOT NULL DEFAULT 0 CHECK(fencing_token >= 0),
                        lease_expires_at TEXT
                    )
                """)
                # Forward-compatible migration for journals created by Stage 89.
                columns = {row["name"] for row in self._connection.execute("PRAGMA table_info(recovery_attempts)")}
                if "checkpoint_fingerprint" not in columns:
                    self._connection.execute("ALTER TABLE recovery_attempts ADD COLUMN checkpoint_fingerprint TEXT")
                if "max_attempts" not in columns:
                    self._connection.execute("ALTER TABLE recovery_attempts ADD COLUMN max_attempts INTEGER NOT NULL DEFAULT 3")
                if "owner_pid" not in columns:
                    self._connection.execute("ALTER TABLE recovery_attempts ADD COLUMN owner_pid INTEGER")
                if "owner_run_id" not in columns:
                    self._connection.execute("ALTER TABLE recovery_attempts ADD COLUMN owner_run_id TEXT")
                if "fencing_token" not in columns:
                    self._connection.execute("ALTER TABLE recovery_attempts ADD COLUMN fencing_token INTEGER NOT NULL DEFAULT 0")
                if "lease_expires_at" not in columns:
                    self._connection.execute("ALTER TABLE recovery_attempts ADD COLUMN lease_expires_at TEXT")
                self._connection.commit()

        except BaseException:
            self._connection.close()
            raise

    @staticmethod
    def _now() -> str:
        return datetime.now(timezone.utc).isoformat()

    @staticmethod
    def _pid_is_alive(pid: int) -> bool:
        """Return whether a local process appears to exist.

        This is a conservative same-host guard, not a distributed lease: PID reuse,
        containers with different PID namespaces, and remote hosts require a stronger
        deployment-level ownership mechanism.
        """
        if isinstance(pid, bool) or not isinstance(pid, int) or pid <= 0:
            return False
        try:
            os.kill(pid, 0)
        except ProcessLookupError:
            return False
        except PermissionError:
            # The process exists but this process is not allowed to signal it.
            return True
        except OSError:
            # Unknown OS errors must fail closed and avoid stealing a live attempt.
            return True
        return True

    @staticmethod
    def _validate_key(attempt_key: str) -> str:
        if not isinstance(attempt_key, str) or not attempt_key.strip():
            raise ValueError("attempt_key must not be empty")
        return attempt_key.strip()

    @staticmethod
    def _from_row(row: sqlite3.Row | None) -> RecoveryAttempt | None:
        if row is None:
            return None
        try:
            status = RecoveryAttemptStatus(row["status"])
        except (TypeError, ValueError) as exc:
            # An unknown persisted state must never be interpreted as an ordinary
            # transition opportunity. Require explicit journal repair/reconciliation.
            raise RecoveryAttemptBlocked(
                "recovery journal contains an unknown status; manual reconciliation required"
            ) from exc
        # Validate identity and human-authored context before exposing the row or
        # allowing a transition. SQLite's declared types are affinities, not a
        # guarantee that externally modified files contain valid values.
        attempt_key = row["attempt_key"]
        if not isinstance(attempt_key, str) or not attempt_key.strip() or attempt_key != attempt_key.strip():
            raise RecoveryAttemptBlocked(
                "recovery journal contains an invalid attempt_key; manual reconciliation required"
            )
        reason = row["reason"]
        if not isinstance(reason, str) or not reason.strip():
            raise RecoveryAttemptBlocked(
                "recovery journal contains an invalid reason; manual reconciliation required"
            )

        # Journal timestamps are generated in UTC with an explicit offset. A
        # malformed or naive timestamp must not leak ValueError/TypeError from a
        # later lease comparison, where callers might mistake it for a transient
        # failure instead of corrupt durable state. Every persisted attempt has a
        # start timestamp; only the lease timestamp may be absent for inactive rows.
        for field in ("started_at", "updated_at", "lease_expires_at"):
            value = row[field]
            if value is None:
                if field in ("started_at", "updated_at"):
                    raise RecoveryAttemptBlocked(
                        f"recovery journal contains a missing {field} timestamp; manual reconciliation required"
                    )
                continue
            if not isinstance(value, str) or not value.strip():
                raise RecoveryAttemptBlocked(
                    f"recovery journal contains an invalid {field} timestamp; manual reconciliation required"
                )
            try:
                parsed = datetime.fromisoformat(value)
            except (TypeError, ValueError) as exc:
                raise RecoveryAttemptBlocked(
                    f"recovery journal contains an invalid {field} timestamp; manual reconciliation required"
                ) from exc
            if parsed.tzinfo is None or parsed.utcoffset() is None:
                raise RecoveryAttemptBlocked(
                    f"recovery journal contains a timezone-naive {field} timestamp; manual reconciliation required"
                )

        # SQLite CHECK constraints protect ordinary writes, but they can be
        # bypassed by a damaged file or an external writer. Validate critical
        # counters when reading so corrupt metadata cannot authorize transitions.
        attempt_count = row["attempt_count"]
        max_attempts = row["max_attempts"]
        fencing_token = row["fencing_token"]
        if (isinstance(attempt_count, bool) or not isinstance(attempt_count, int)
                or attempt_count < 1):
            raise RecoveryAttemptBlocked(
                "recovery journal contains an invalid attempt_count; manual reconciliation required"
            )
        if (isinstance(max_attempts, bool) or not isinstance(max_attempts, int)
                or max_attempts < 1 or attempt_count > max_attempts):
            raise RecoveryAttemptBlocked(
                "recovery journal contains inconsistent attempt limits; manual reconciliation required"
            )
        if (isinstance(fencing_token, bool) or not isinstance(fencing_token, int)
                or fencing_token < 0 or (fencing_token > 0 and fencing_token != attempt_count)):
            raise RecoveryAttemptBlocked(
                "recovery journal contains an inconsistent fencing token; manual reconciliation required"
            )
        last_error = row["last_error"]
        if status in (RecoveryAttemptStatus.IN_PROGRESS, RecoveryAttemptStatus.SUCCEEDED):
            if last_error is not None:
                raise RecoveryAttemptBlocked(
                    "recovery journal contains inconsistent last_error for a non-failed state; manual reconciliation required"
                )
        elif not isinstance(last_error, str) or not last_error.strip():
            # FAILED records and their RETRY_AUTHORIZED successors must retain the
            # failure evidence until a new attempt is actually consumed. Otherwise a
            # corrupted row could look like a clean transition with no audit context.
            raise RecoveryAttemptBlocked(
                "recovery journal contains inconsistent last_error for a failed state; manual reconciliation required"
            )
        if status is RecoveryAttemptStatus.RETRY_AUTHORIZED:
            # RETRY_AUTHORIZED is the journal's one-shot permission to start work.
            # Never consume it if the durable operator decision is incomplete or
            # malformed (for example after an external edit or partial corruption).
            authorized_by = row["authorized_by"]
            authorization_reason = row["authorization_reason"]
            checkpoint_fingerprint = row["checkpoint_fingerprint"]
            if not isinstance(authorized_by, str) or not authorized_by.strip():
                raise RecoveryAttemptBlocked(
                    "recovery journal contains incomplete retry authorization operator; manual reconciliation required"
                )
            if not isinstance(authorization_reason, str) or not authorization_reason.strip():
                raise RecoveryAttemptBlocked(
                    "recovery journal contains incomplete retry authorization reason; manual reconciliation required"
                )
            if checkpoint_fingerprint is not None and (
                not isinstance(checkpoint_fingerprint, str) or not checkpoint_fingerprint.strip()
            ):
                raise RecoveryAttemptBlocked(
                    "recovery journal contains invalid authorized checkpoint fingerprint; manual reconciliation required"
                )
        owner_run_id = row["owner_run_id"]
        owner_pid = row["owner_pid"]
        lease_expires_at = row["lease_expires_at"]
        if status is not RecoveryAttemptStatus.IN_PROGRESS:
            # PID and lease are cleared whenever an attempt leaves IN_PROGRESS.
            # Interrupted-owner reconciliation deliberately retains owner_run_id
            # on FAILED/RETRY_AUTHORIZED rows for forensic traceability, but that
            # historical UUID must never be paired with a live PID or lease.
            # SUCCEEDED rows are terminal and must not retain any owner identity.
            contradictory_owner = owner_pid is not None or lease_expires_at is not None
            if status is RecoveryAttemptStatus.SUCCEEDED and owner_run_id is not None:
                contradictory_owner = True
            if contradictory_owner:
                raise RecoveryAttemptBlocked(
                    "recovery journal contains ownership metadata outside an active attempt; manual reconciliation required"
                )
        if status is RecoveryAttemptStatus.IN_PROGRESS:
            if owner_run_id is not None:
                # Modern fenced attempts require a complete owner identity. A missing
                # or malformed PID must not make another process classify a live
                # attempt as abandoned and authorize a takeover.
                if (not isinstance(owner_run_id, str) or not owner_run_id.strip()
                        or fencing_token < 1
                        or not isinstance(lease_expires_at, str) or not lease_expires_at.strip()):
                    raise RecoveryAttemptBlocked(
                        "recovery journal contains inconsistent active ownership metadata; manual reconciliation required"
                    )
                # Timestamp syntax, timezone-awareness, and a positive integer PID
                # were validated before any takeover/reconciliation decision.
            else:
                # PID-only ownership is retained for pre-fencing legacy rows only.
                # A positive fencing token without its UUID is a torn/corrupt modern
                # owner record and must not fall back to the legacy completion path.
                if fencing_token != 0:
                    raise RecoveryAttemptBlocked(
                        "recovery journal contains inconsistent legacy ownership metadata; manual reconciliation required"
                    )
                if owner_pid is not None and (
                    isinstance(owner_pid, bool) or not isinstance(owner_pid, int) or owner_pid <= 0
                ):
                    raise RecoveryAttemptBlocked(
                        "recovery journal contains invalid legacy owner PID; manual reconciliation required"
                    )
        return RecoveryAttempt(
            attempt_key=row["attempt_key"], status=status,
            attempt_count=attempt_count, reason=row["reason"],
            started_at=row["started_at"], updated_at=row["updated_at"],
            last_error=row["last_error"], authorized_by=row["authorized_by"],
            authorization_reason=row["authorization_reason"],
            checkpoint_fingerprint=row["checkpoint_fingerprint"],
            max_attempts=row["max_attempts"],
            owner_run_id=row["owner_run_id"], fencing_token=row["fencing_token"],
            owner_pid=row["owner_pid"], lease_expires_at=row["lease_expires_at"],
        )

    def _assert_persisted_keys_valid(self) -> None:
        """Detect blank/non-canonical persisted keys before treating a lookup as absent."""
        invalid = self._connection.execute(
            "SELECT attempt_key FROM recovery_attempts "
            "WHERE attempt_key IS NULL OR typeof(attempt_key) != 'text' "
            "OR trim(attempt_key) = '' OR attempt_key != trim(attempt_key) LIMIT 1"
        ).fetchone()
        if invalid is not None:
            raise RecoveryAttemptBlocked(
                "recovery journal contains an invalid attempt_key; manual reconciliation required"
            )

    def _assert_all_persisted_rows_valid(self) -> None:
        """Validate the complete journal before any state-changing transition.

        A valid target row is not sufficient if another row is corrupt: allowing a
        new attempt or completing an existing one would mutate a journal whose global
        state cannot be trusted. Recovery journals are expected to remain bounded; a
        full scan is an intentional fail-closed tradeoff at mutation boundaries.
        """
        rows = self._connection.execute(
            "SELECT * FROM recovery_attempts ORDER BY attempt_key"
        ).fetchall()
        for row in rows:
            self._from_row(row)

    def get(self, attempt_key: str) -> RecoveryAttempt | None:
        key = self._validate_key(attempt_key)
        with self._lock:
            row = self._connection.execute(
                "SELECT * FROM recovery_attempts WHERE attempt_key = ?", (key,),
            ).fetchone()
            if row is None:
                # A corrupt key may have made a durable row unreachable by its
                # expected identifier. Audit keys only on misses to keep ordinary
                # reads proportional to the requested row.
                self._assert_persisted_keys_valid()
            return self._from_row(row)

    def begin_attempt(
        self, attempt_key: str, reason: str, *, checkpoint_fingerprint: str | None = None,
        max_attempts: int = 3, lease_seconds: int | float = 300,
    ) -> RecoveryAttempt:
        key = self._validate_key(attempt_key)
        if not isinstance(reason, str) or not reason.strip():
            raise ValueError("reason must not be empty")
        if checkpoint_fingerprint is not None and (
            not isinstance(checkpoint_fingerprint, str) or not checkpoint_fingerprint.strip()
        ):
            raise ValueError("checkpoint_fingerprint must be a non-empty string when supplied")
        if isinstance(max_attempts, bool) or not isinstance(max_attempts, int) or max_attempts < 1:
            raise ValueError("max_attempts must be a positive integer")
        if (isinstance(lease_seconds, bool) or not isinstance(lease_seconds, (int, float))
                or not math.isfinite(lease_seconds) or lease_seconds <= 0 or lease_seconds > 86400):
            raise ValueError("lease_seconds must be greater than 0 and at most 86400")
        checkpoint_fingerprint = checkpoint_fingerprint.strip() if checkpoint_fingerprint else None
        now = self._now()
        lease_expires_at = (datetime.fromisoformat(now) + timedelta(seconds=lease_seconds)).isoformat()
        owner_run_id = uuid4().hex
        with self._lock:
            self._connection.execute("BEGIN IMMEDIATE")
            try:
                self._assert_all_persisted_rows_valid()
                row = self._connection.execute(
                    "SELECT * FROM recovery_attempts WHERE attempt_key = ?", (key,),
                ).fetchone()
                if row is None:
                    # Do not create a fresh attempt while a damaged key makes an
                    # existing durable row invisible to this lookup.
                    self._assert_persisted_keys_valid()
                current = self._from_row(row)
                if current is None:
                    self._connection.execute(
                        "INSERT INTO recovery_attempts "
                        "(attempt_key,status,attempt_count,reason,started_at,updated_at,checkpoint_fingerprint,max_attempts,owner_pid,owner_run_id,fencing_token,lease_expires_at) "
                        "VALUES (?, ?, 1, ?, ?, ?, ?, ?, ?, ?, 1, ?)",
                        (key, RecoveryAttemptStatus.IN_PROGRESS.value, reason.strip(), now, now,
                         checkpoint_fingerprint, max_attempts, os.getpid(), owner_run_id, lease_expires_at),
                    )
                elif current.status is RecoveryAttemptStatus.RETRY_AUTHORIZED:
                    if current.checkpoint_fingerprint is not None and checkpoint_fingerprint != current.checkpoint_fingerprint:
                        raise RecoveryAttemptBlocked("checkpoint changed after retry authorization")
                    if current.attempt_count >= current.max_attempts:
                        raise RecoveryAttemptBlocked("maximum recovery attempts reached; new operator decision required")
                    if checkpoint_fingerprint is None:
                        checkpoint_fingerprint = current.checkpoint_fingerprint
                    self._connection.execute(
                        "UPDATE recovery_attempts SET status=?, attempt_count=attempt_count+1, reason=?, "
                        "started_at=?, updated_at=?, last_error=NULL, authorized_by=NULL, authorization_reason=NULL, "
                        "checkpoint_fingerprint=?, owner_pid=?, owner_run_id=?, fencing_token=fencing_token+1, "
                        "lease_expires_at=? WHERE attempt_key=?",
                        (RecoveryAttemptStatus.IN_PROGRESS.value, reason.strip(), now, now,
                         checkpoint_fingerprint, os.getpid(), owner_run_id, lease_expires_at, key),
                    )
                elif current.status is RecoveryAttemptStatus.IN_PROGRESS:
                    owner_row = self._connection.execute(
                        "SELECT owner_pid FROM recovery_attempts WHERE attempt_key = ?", (key,),
                    ).fetchone()
                    owner_pid = owner_row["owner_pid"] if owner_row is not None else None
                    if current.owner_run_id is not None and owner_pid is None:
                        # A fenced owner UUID with no PID cannot be classified as
                        # dead. Do not turn missing identity data into a takeover.
                        raise RecoveryAttemptBlocked(
                            "recovery owner PID is unknown; manual reconciliation required"
                        )
                    if owner_pid == os.getpid():
                        raise RecoveryAttemptBlocked("recovery attempt is already in progress in this process")
                    if current.owner_run_id is not None and (
                        isinstance(owner_pid, bool) or not isinstance(owner_pid, int) or owner_pid <= 0
                    ):
                        raise RecoveryAttemptBlocked(
                            "recovery owner PID is invalid; manual reconciliation required"
                        )
                    if owner_pid is not None and self._pid_is_alive(owner_pid):
                        # A second process must not classify a live owner's work as an
                        # interrupted attempt. Keep the durable state IN_PROGRESS; the
                        # active owner alone may finish it or a later recovery may
                        # explicitly resolve it after the owner has exited.
                        raise RecoveryAttemptBlocked(
                            "recovery attempt is already in progress in another live process"
                        )
                    self._connection.execute(
                        "UPDATE recovery_attempts SET status=?, updated_at=?, last_error=?, owner_pid=NULL, "
                        "lease_expires_at=NULL "
                        "WHERE attempt_key=? AND status=?",
                        (RecoveryAttemptStatus.FAILED.value, now,
                         "previous attempt was interrupted; explicit retry authorization required", key,
                         RecoveryAttemptStatus.IN_PROGRESS.value),
                    )
                    interrupted = self._connection.execute(
                        "SELECT * FROM recovery_attempts WHERE attempt_key = ?", (key,),
                    ).fetchone()
                    if interrupted is None:
                        raise RecoveryAttemptBlocked("interrupted recovery journal row disappeared")
                    self._commit_or_resolve_ambiguous_result(key, dict(interrupted))
                    raise RecoveryAttemptBlocked("previous recovery attempt was interrupted; authorize retry explicitly")
                elif current.status is RecoveryAttemptStatus.FAILED:
                    if current.attempt_count >= current.max_attempts:
                        raise RecoveryAttemptBlocked(
                            "maximum recovery attempts reached; new operator decision required"
                        )
                    raise RecoveryAttemptBlocked("previous recovery attempt failed; authorize retry explicitly")
                else:
                    raise RecoveryAttemptBlocked("recovery attempt already succeeded; use a new attempt key")
                # Snapshot the exact intended row while the write transaction is
                # still open. If COMMIT reports an error after the durable commit,
                # the fresh-connection resolver must match the entire row (including
                # the unique owner UUID and fencing token) before returning success.
                expected_row = self._connection.execute(
                    "SELECT * FROM recovery_attempts WHERE attempt_key = ?", (key,),
                ).fetchone()
                if expected_row is None:
                    raise RecoveryAttemptBlocked("recovery attempt row missing before commit")
                self._commit_or_resolve_ambiguous_result(key, dict(expected_row))
            except RecoveryAttemptBlocked:
                if self._connection.in_transaction:
                    self._connection.rollback()
                raise
            except Exception:
                self._connection.rollback()
                raise
        result = self.get(key)
        assert result is not None
        return result

    def renew_lease(
        self, attempt_key: str, *, owner_run_id: str, fencing_token: int,
        lease_seconds: int | float = 300,
    ) -> RecoveryAttempt:
        """Atomically extend a live recovery owner's lease without changing its fence.

        Expired leases cannot be resurrected: the caller must obtain a newly authorized
        attempt instead. The UUID and fencing token are checked in the same write
        transaction as the lease update.
        """
        key = self._validate_key(attempt_key)
        if not isinstance(owner_run_id, str) or not owner_run_id.strip():
            raise ValueError("owner_run_id must not be empty")
        if isinstance(fencing_token, bool) or not isinstance(fencing_token, int) or fencing_token < 1:
            raise ValueError("fencing_token must be a positive integer")
        if (isinstance(lease_seconds, bool) or not isinstance(lease_seconds, (int, float))
                or not math.isfinite(lease_seconds) or lease_seconds <= 0 or lease_seconds > 86400):
            raise ValueError("lease_seconds must be greater than 0 and at most 86400")
        with self._lock:
            self._connection.execute("BEGIN IMMEDIATE")
            try:
                self._assert_all_persisted_rows_valid()
                row = self._connection.execute(
                    "SELECT * FROM recovery_attempts WHERE attempt_key=? AND status=?",
                    (key, RecoveryAttemptStatus.IN_PROGRESS.value),
                ).fetchone()
                current = self._from_row(row)
                now = self._now()
                if (current is None or current.owner_run_id != owner_run_id
                        or current.fencing_token != fencing_token):
                    raise RecoveryAttemptBlocked("stale recovery owner or fencing token")
                if (current.lease_expires_at is None
                        or datetime.fromisoformat(current.lease_expires_at) <= datetime.fromisoformat(now)):
                    raise RecoveryAttemptBlocked("recovery ownership lease expired and cannot be renewed")
                expires = (datetime.fromisoformat(now) + timedelta(seconds=lease_seconds)).isoformat()
                cursor = self._connection.execute(
                    "UPDATE recovery_attempts SET lease_expires_at=?, updated_at=? "
                    "WHERE attempt_key=? AND status=? AND owner_run_id=? AND fencing_token=?",
                    (expires, now, key, RecoveryAttemptStatus.IN_PROGRESS.value, owner_run_id, fencing_token),
                )
                if cursor.rowcount != 1:
                    raise RecoveryAttemptBlocked("recovery ownership changed during lease renewal")
                expected_row = self._connection.execute(
                    "SELECT * FROM recovery_attempts WHERE attempt_key=?", (key,),
                ).fetchone()
                if expected_row is None:
                    raise RecoveryAttemptBlocked("recovery attempt row missing before lease commit")
                self._commit_or_resolve_ambiguous_result(key, dict(expected_row))
            except Exception:
                if self._connection.in_transaction:
                    self._connection.rollback()
                raise
        result = self.get(key)
        assert result is not None
        return result

    def finish_success(
        self, attempt_key: str, *, owner_run_id: str | None = None, fencing_token: int | None = None,
    ) -> RecoveryAttempt:
        return self._finish(attempt_key, RecoveryAttemptStatus.SUCCEEDED, None, owner_run_id, fencing_token)

    def finish_failure(
        self, attempt_key: str, error: str, *, owner_run_id: str | None = None, fencing_token: int | None = None,
    ) -> RecoveryAttempt:
        if not isinstance(error, str) or not error.strip():
            raise ValueError("error must not be empty")
        return self._finish(attempt_key, RecoveryAttemptStatus.FAILED, error.strip(), owner_run_id, fencing_token)

    def _commit_or_resolve_ambiguous_result(self, attempt_key: str, expected: dict[str, object]) -> None:
        """Commit a journal transition, resolving commit exceptions from durable state.

        SQLite may have committed successfully even if a wrapper/driver reports an
        exception afterward. On an exception, roll back only if a transaction remains,
        then inspect the journal through a fresh connection. Treat the operation as
        successful only when every expected field matches the durable row; otherwise
        re-raise the original commit exception.
        """
        try:
            self._connection.commit()
            return
        except Exception:
            if self._connection.in_transaction:
                try:
                    self._connection.rollback()
                except Exception:
                    # The fresh-connection check below is authoritative if possible.
                    pass
            verifier = None
            try:
                verifier = sqlite3.connect(self.database_path, timeout=0.25)
                verifier.row_factory = sqlite3.Row
                row = verifier.execute(
                    "SELECT * FROM recovery_attempts WHERE attempt_key = ?", (attempt_key,),
                ).fetchone()
                if row is not None and all(row[field] == value for field, value in expected.items()):
                    return
            except Exception:
                # Preserve the original commit failure; inability to verify is not proof
                # that the transition committed.
                pass
            finally:
                if verifier is not None:
                    verifier.close()
            raise

    def _finish(self, attempt_key: str, status: RecoveryAttemptStatus,
                error: str | None, owner_run_id: str | None, fencing_token: int | None) -> RecoveryAttempt:
        key, now = self._validate_key(attempt_key), self._now()
        with self._lock:
            # Keep the state transition and commit boundary explicit. If a trigger,
            # disk error, or other SQLite failure aborts the update, rollback leaves
            # the durable attempt in IN_PROGRESS rather than a partially applied
            # terminal state or an open transaction that poisons later operations.
            self._connection.execute("BEGIN IMMEDIATE")
            try:
                self._assert_all_persisted_rows_valid()
                current = self._connection.execute(
                    "SELECT owner_pid, owner_run_id, fencing_token, lease_expires_at FROM recovery_attempts WHERE attempt_key=? AND status=?",
                    (key, RecoveryAttemptStatus.IN_PROGRESS.value),
                ).fetchone()
                if current is None:
                    raise RecoveryAttemptBlocked("no in-progress recovery attempt to finish")
                if owner_run_id is not None or fencing_token is not None:
                    if (not isinstance(owner_run_id, str) or not owner_run_id or
                            isinstance(fencing_token, bool) or not isinstance(fencing_token, int) or
                            current["owner_run_id"] != owner_run_id or current["fencing_token"] != fencing_token):
                        raise RecoveryAttemptBlocked("stale recovery owner or fencing token")
                else:
                    # New attempts always have a run identity. PID-only completion is
                    # retained solely for rows migrated from pre-fencing schemas, where
                    # no run identity exists to present. It must never bypass fencing for
                    # a modern attempt, even when an obsolete worker shares this PID.
                    if current["owner_run_id"] is not None:
                        raise RecoveryAttemptBlocked(
                            "owner_run_id and fencing_token are required to finish a fenced recovery attempt"
                        )
                    if current["owner_pid"] != os.getpid():
                        raise RecoveryAttemptBlocked(
                            "legacy recovery attempt can only be finished by its recorded process"
                        )
                if (current["owner_run_id"] is not None and current["lease_expires_at"] is not None
                        and datetime.fromisoformat(current["lease_expires_at"]) <= datetime.fromisoformat(now)
                        and (current["owner_pid"] is None or self._pid_is_alive(current["owner_pid"]))):
                    # An expired lease never authorizes a still-live owner to finish.
                    # A supervisor may reconcile after the old process is confirmed dead,
                    # but only after validating the published candidate independently.
                    raise RecoveryAttemptBlocked("recovery ownership lease expired while owner is still alive")
                cursor = self._connection.execute(
                    "UPDATE recovery_attempts SET status=?, updated_at=?, last_error=?, owner_pid=NULL, owner_run_id=NULL, lease_expires_at=NULL "
                    "WHERE attempt_key=? AND status=? AND fencing_token=?",
                    (status.value, now, error, key, RecoveryAttemptStatus.IN_PROGRESS.value, current["fencing_token"]),
                )
                if cursor.rowcount != 1:
                    raise RecoveryAttemptBlocked("no in-progress recovery attempt to finish")
                expected_row = self._connection.execute(
                    "SELECT * FROM recovery_attempts WHERE attempt_key = ?", (key,),
                ).fetchone()
                if expected_row is None:
                    raise RecoveryAttemptBlocked("recovery attempt row missing before finish commit")
                # Ambiguous-commit recovery must compare the complete row snapshot,
                # not a subset that could overlook concurrent/unexpected field changes.
                self._commit_or_resolve_ambiguous_result(key, dict(expected_row))
            except Exception:
                if self._connection.in_transaction:
                    self._connection.rollback()
                raise
        result = self.get(key)
        assert result is not None
        return result

    def authorize_retry(
        self, attempt_key: str, *, operator: str, reason: str,
        checkpoint_fingerprint: str | None = None,
    ) -> RecoveryAttempt:
        key = self._validate_key(attempt_key)
        if not isinstance(operator, str) or not operator.strip():
            raise ValueError("operator must not be empty")
        if not isinstance(reason, str) or not reason.strip():
            raise ValueError("reason must not be empty")
        if checkpoint_fingerprint is not None and (
            not isinstance(checkpoint_fingerprint, str) or not checkpoint_fingerprint.strip()
        ):
            raise ValueError("checkpoint_fingerprint must be a non-empty string when supplied")
        with self._lock:
            # Serialize the read/validate/write transition across independent SQLite
            # connections and processes, not just threads sharing this instance.
            self._connection.execute("BEGIN IMMEDIATE")
            try:
                self._assert_all_persisted_rows_valid()
                current_row = self._connection.execute(
                    "SELECT * FROM recovery_attempts WHERE attempt_key = ?", (key,),
                ).fetchone()
                current = self._from_row(current_row)
                if current is None or current.status is not RecoveryAttemptStatus.FAILED:
                    raise RecoveryAttemptBlocked("retry can only be authorized for a failed attempt")
                if current.attempt_count >= current.max_attempts:
                    raise RecoveryAttemptBlocked(
                        "maximum recovery attempts reached; new operator decision required"
                    )
                fingerprint = (
                    checkpoint_fingerprint.strip() if checkpoint_fingerprint
                    else current.checkpoint_fingerprint
                )
                cursor = self._connection.execute(
                    "UPDATE recovery_attempts SET status=?, updated_at=?, authorized_by=?, authorization_reason=?, "
                    "checkpoint_fingerprint=? WHERE attempt_key=? AND status=?",
                    (RecoveryAttemptStatus.RETRY_AUTHORIZED.value, self._now(), operator.strip(), reason.strip(),
                     fingerprint, key, RecoveryAttemptStatus.FAILED.value),
                )
                if cursor.rowcount != 1:
                    raise RecoveryAttemptBlocked("retry can only be authorized for a failed attempt")
                expected_row = self._connection.execute(
                    "SELECT * FROM recovery_attempts WHERE attempt_key = ?", (key,),
                ).fetchone()
                if expected_row is None:
                    raise RecoveryAttemptBlocked("recovery attempt row missing before retry-authorization commit")
                self._commit_or_resolve_ambiguous_result(key, dict(expected_row))
            except Exception:
                if self._connection.in_transaction:
                    self._connection.rollback()
                raise
        result = self.get(key)
        assert result is not None
        return result

    def close(self) -> None:
        with self._lock:
            self._connection.close()

    def __del__(self) -> None:
        # Last-resort cleanup for callers retaining the historical implicit lifecycle.
        # Explicit close() remains required for deterministic resource ownership.
        connection = getattr(self, "_connection", None)
        if connection is not None:
            try:
                connection.close()
            except Exception:
                pass
