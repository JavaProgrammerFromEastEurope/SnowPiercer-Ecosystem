from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from enum import Enum
from typing import Any, Callable

from .command_idempotency_store import CommandIdempotencyStore, IdempotencyStatus
from .execution_audit_store import ExecutionAuditStore


class JournalConsistencyStatus(str, Enum):
    CONSISTENT = "consistent"
    RECONCILIATION_REQUIRED = "reconciliation_required"
    CONFLICT = "conflict"
    UNBOUND = "unbound"


@dataclass(frozen=True, slots=True)
class JournalConsistencyReport:
    status: JournalConsistencyStatus
    idempotency_key: str
    execution_id: str | None
    idempotency_status: str
    execution_status: str | None
    reason: str

    @property
    def may_dispatch(self) -> bool:
        """Only a consistent pre-dispatch pair may proceed automatically."""
        return (
            self.status is JournalConsistencyStatus.CONSISTENT
            and self.idempotency_status == "claimed"
            and self.execution_status in {"created", "running"}
        )


@dataclass(frozen=True, slots=True)
class DispatchBoundaryResult:
    """Result of a dispatch-boundary check with durable single-attempt reservation.

    The reservation coordinates callers sharing the same idempotency database,
    but cannot make an external side effect atomic with SQLite or fence a device
    that ignores downstream idempotency/fencing tokens.
    """

    report: JournalConsistencyReport
    dispatched: bool
    result: Any | None = None


class ExecutionJournalConsistencyChecker:
    """Fail-closed comparison of the idempotency ledger and execution audit log.

    This is a read-only diagnostic gate. It never repairs either journal or
    authorizes replay; callers must reconcile divergent outcomes explicitly.
    The two SQLite databases are not atomically committed together, so a
    disagreement is expected to require investigation rather than inference.
    """

    def __init__(
        self,
        idempotency_store: CommandIdempotencyStore,
        execution_audit_store: ExecutionAuditStore,
    ) -> None:
        if not isinstance(idempotency_store, CommandIdempotencyStore):
            raise TypeError("idempotency_store must be a CommandIdempotencyStore")
        if not isinstance(execution_audit_store, ExecutionAuditStore):
            raise TypeError("execution_audit_store must be an ExecutionAuditStore")
        self._idempotency_store = idempotency_store
        self._execution_audit_store = execution_audit_store

    def inspect(self, idempotency_key: str) -> JournalConsistencyReport:
        """Inspect both journals and fail closed if state changes during the read.

        The stores live in separate SQLite databases, so a cross-database atomic
        snapshot is unavailable. Re-reading both sides detects changes observed
        during this inspection; callers must still revalidate before dispatch.
        """
        if not isinstance(idempotency_key, str) or not idempotency_key.strip():
            raise ValueError("idempotency_key must not be empty")
        key = idempotency_key.strip()
        report = self._inspect_snapshot(key)
        # Preserve authoritative fail-closed diagnoses (e.g. identity conflict
        # or unreadable storage); revalidation is needed to guard only a report
        # that would otherwise permit dispatch.
        if (
            report.status is not JournalConsistencyStatus.CONSISTENT
            or report.execution_id is None
        ):
            return report
        try:
            current_record = self._idempotency_store.get(key)
            current_history = self._execution_audit_store.get_history(
                report.execution_id
            )
        except (RuntimeError, sqlite3.DatabaseError) as exc:
            return JournalConsistencyReport(
                JournalConsistencyStatus.CONFLICT,
                key,
                report.execution_id,
                "corrupt",
                None,
                f"journal changed or became unavailable during inspection: {type(exc).__name__}",
            )
        current_status = current_history[-1].get("status") if current_history else None
        current_command = (
            current_history[-1].get("command_id") if current_history else None
        )
        if (
            current_record is None
            or current_record != self._idempotency_store.get(key)
            or current_record.status.value != report.idempotency_status
            or current_record.execution_id != report.execution_id
            or current_status != report.execution_status
            or (current_history and current_command != current_record.command_name)
            or (not current_history and report.execution_status is not None)
        ):
            return JournalConsistencyReport(
                JournalConsistencyStatus.RECONCILIATION_REQUIRED,
                key,
                report.execution_id,
                (
                    current_record.status.value
                    if current_record is not None
                    else "missing"
                ),
                str(current_status) if current_status is not None else None,
                "journal state changed during inspection; discard this snapshot and inspect again",
            )
        return report

    def dispatch_if_consistent(
        self, idempotency_key: str, dispatch: Callable[[JournalConsistencyReport], Any]
    ) -> DispatchBoundaryResult:
        """Revalidate and reserve one dispatch attempt before invoking the callback.

        The SQLite compare-and-set prevents duplicate reservations across store
        instances and processes using the same idempotency database. A crash after
        reservation fails closed and requires reconciliation; the reservation is
        never automatically released because the external outcome may be unknown.
        """
        if not callable(dispatch):
            raise TypeError("dispatch must be callable")
        # Stable lock order prevents deadlocks between checker calls that share
        # these store instances. Both stores use re-entrant locks.
        with self._idempotency_store._lock:
            with self._execution_audit_store._lock:
                report = self.inspect(idempotency_key)
                if not report.may_dispatch:
                    return DispatchBoundaryResult(report=report, dispatched=False)
                try:
                    reserved = self._idempotency_store.reserve_dispatch(idempotency_key)
                except (RuntimeError, sqlite3.DatabaseError) as exc:
                    blocked = JournalConsistencyReport(
                        JournalConsistencyStatus.CONFLICT,
                        report.idempotency_key,
                        report.execution_id,
                        report.idempotency_status,
                        report.execution_status,
                        f"durable dispatch reservation failed: {type(exc).__name__}",
                    )
                    return DispatchBoundaryResult(report=blocked, dispatched=False)
                if not reserved:
                    blocked = JournalConsistencyReport(
                        JournalConsistencyStatus.RECONCILIATION_REQUIRED,
                        report.idempotency_key,
                        report.execution_id,
                        report.idempotency_status,
                        report.execution_status,
                        "dispatch was already reserved or command is no longer dispatchable",
                    )
                    return DispatchBoundaryResult(report=blocked, dispatched=False)
                try:
                    result = dispatch(report)
                except BaseException as exc:
                    # Once callback entry occurs, external outcome is not safely
                    # inferable from an exception. Preserve the reservation and
                    # mark the outcome unknown when possible; never auto-replay.
                    try:
                        self._idempotency_store.mark_unknown(
                            idempotency_key,
                            f"dispatch callback raised {type(exc).__name__}",
                        )
                    except (RuntimeError, sqlite3.DatabaseError, ValueError):
                        pass
                    raise
                return DispatchBoundaryResult(
                    report=report, dispatched=True, result=result
                )

    def _inspect_snapshot(self, idempotency_key: str) -> JournalConsistencyReport:
        if not isinstance(idempotency_key, str) or not idempotency_key.strip():
            raise ValueError("idempotency_key must not be empty")
        try:
            record = self._idempotency_store.get(idempotency_key)
        except (RuntimeError, sqlite3.DatabaseError) as exc:
            return JournalConsistencyReport(
                JournalConsistencyStatus.CONFLICT,
                idempotency_key.strip(),
                None,
                "corrupt",
                None,
                f"idempotency journal could not be read safely: {type(exc).__name__}",
            )
        if record is None:
            raise ValueError("unknown idempotency key")
        execution_id = record.execution_id
        if execution_id is None:
            return JournalConsistencyReport(
                JournalConsistencyStatus.UNBOUND,
                record.idempotency_key,
                None,
                record.status.value,
                None,
                "idempotency record has no execution binding; automatic dispatch is not authorized",
            )

        try:
            binding_count = self._idempotency_store.count_execution_bindings(
                execution_id
            )
        except sqlite3.DatabaseError as exc:
            return JournalConsistencyReport(
                JournalConsistencyStatus.CONFLICT,
                record.idempotency_key,
                execution_id,
                record.status.value,
                None,
                f"idempotency binding index could not be read safely: {type(exc).__name__}",
            )
        if binding_count != 1:
            return JournalConsistencyReport(
                JournalConsistencyStatus.CONFLICT,
                record.idempotency_key,
                execution_id,
                record.status.value,
                None,
                f"multiple idempotency records ({binding_count}) share this execution binding",
            )

        try:
            history = self._execution_audit_store.get_history(execution_id)
        except (RuntimeError, sqlite3.DatabaseError) as exc:
            return JournalConsistencyReport(
                JournalConsistencyStatus.CONFLICT,
                record.idempotency_key,
                execution_id,
                record.status.value,
                None,
                f"execution audit journal could not be read safely: {type(exc).__name__}",
            )
        if not history:
            status = (
                JournalConsistencyStatus.CONFLICT
                if record.status is IdempotencyStatus.COMPLETED
                else JournalConsistencyStatus.RECONCILIATION_REQUIRED
            )
            return JournalConsistencyReport(
                status,
                record.idempotency_key,
                execution_id,
                record.status.value,
                None,
                "bound execution is absent from the execution audit journal",
            )

        latest = history[-1]
        execution_status = latest.get("status")
        command_id = latest.get("command_id")
        if (
            not isinstance(execution_status, str)
            or not isinstance(command_id, str)
            or not command_id.strip()
        ):
            return JournalConsistencyReport(
                JournalConsistencyStatus.CONFLICT,
                record.idempotency_key,
                execution_id,
                record.status.value,
                str(execution_status) if execution_status is not None else None,
                "execution audit metadata is malformed",
            )

        # The execution ID alone is not sufficient: a corrupted or mismatched
        # audit row may point at a different command. Never authorize dispatch or
        # reconcile outcomes unless both durable journals agree on command identity.
        if command_id != record.command_name:
            return JournalConsistencyReport(
                JournalConsistencyStatus.CONFLICT,
                record.idempotency_key,
                execution_id,
                record.status.value,
                execution_status,
                "execution audit command identity does not match idempotency record",
            )

        # A durable dispatch reservation means the process may have crashed
        # either immediately before callback entry or after an external side
        # effect but before recording its outcome. On restart, the claimed
        # status alone is therefore insufficient to authorize another attempt.
        if record.status is IdempotencyStatus.CLAIMED and record.dispatch_started:
            return JournalConsistencyReport(
                JournalConsistencyStatus.RECONCILIATION_REQUIRED,
                record.idempotency_key,
                execution_id,
                record.status.value,
                execution_status,
                "dispatch reservation exists without a durable reconciled outcome",
            )

        if record.status is IdempotencyStatus.CLAIMED and execution_status in {
            "created",
            "running",
        }:
            return JournalConsistencyReport(
                JournalConsistencyStatus.CONSISTENT,
                record.idempotency_key,
                execution_id,
                record.status.value,
                execution_status,
                "both journals describe a non-terminal execution",
            )
        if (
            record.status is IdempotencyStatus.COMPLETED
            and execution_status == "completed"
        ):
            return JournalConsistencyReport(
                JournalConsistencyStatus.CONSISTENT,
                record.idempotency_key,
                execution_id,
                record.status.value,
                execution_status,
                "both journals describe a completed execution",
            )
        if (
            record.status is IdempotencyStatus.UNKNOWN
            or execution_status == "recovery_required"
        ):
            return JournalConsistencyReport(
                JournalConsistencyStatus.RECONCILIATION_REQUIRED,
                record.idempotency_key,
                execution_id,
                record.status.value,
                execution_status,
                "at least one journal requires explicit outcome reconciliation",
            )
        if record.status is IdempotencyStatus.CLAIMED and execution_status in {
            "completed",
            "failed",
        }:
            return JournalConsistencyReport(
                JournalConsistencyStatus.RECONCILIATION_REQUIRED,
                record.idempotency_key,
                execution_id,
                record.status.value,
                execution_status,
                "execution journal is terminal while idempotency ledger is not",
            )
        return JournalConsistencyReport(
            JournalConsistencyStatus.CONFLICT,
            record.idempotency_key,
            execution_id,
            record.status.value,
            execution_status,
            "idempotency and execution journals disagree",
        )
