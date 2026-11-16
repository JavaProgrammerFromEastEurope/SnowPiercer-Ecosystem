"""Fail-closed startup assessment and non-destructive recovery preparation.

The component deliberately never replaces the active event database. It can make a
verified recovery candidate available at a new path, but promotion remains an explicit
operator/deployment decision.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from threading import Event, Thread
import math

from .command_event_store import CommandEventStore
from .event_integrity_anchor_store import EventIntegrityAnchorStore
from .event_log_backup import EventLogBackupManager
from .event_log_recovery_gate import EventLogRecoveryAssessment, EventLogRecoveryGate
from .event_log_recovery_attempt_store import (
    EventLogRecoveryAttemptStore, RecoveryAttemptBlocked,
)


class StartupRecoveryStatus(str, Enum):
    TRUSTED = "trusted"
    RECOVERY_REQUIRED = "recovery_required"
    RECOVERY_READY = "recovery_ready"
    BLOCKED = "blocked"


@dataclass(frozen=True, slots=True)
class StartupRecoveryResult:
    status: StartupRecoveryStatus
    assessment: EventLogRecoveryAssessment | None
    recovery_path: str | None
    findings: tuple[dict[str, object], ...]


class EventLogStartupRecovery:
    """Assess event-log trust at startup and optionally prepare a verified recovery copy."""

    @staticmethod
    def run(
        active_database_path: str | Path,
        anchor_store: EventIntegrityAnchorStore,
        *,
        backup_path: str | Path | None = None,
        recovery_destination_path: str | Path | None = None,
        recovery_attempt_store: EventLogRecoveryAttemptStore | None = None,
        recovery_attempt_key: str | None = None,
        recovery_reason: str = "startup event-log recovery",
        max_recovery_attempts: int = 3,
        recovery_lease_seconds: int | float = 300,
        recovery_heartbeat_interval_seconds: int | float | None = None,
    ) -> StartupRecoveryResult:
        if not isinstance(anchor_store, EventIntegrityAnchorStore):
            raise TypeError("anchor_store must be an EventIntegrityAnchorStore")
        if recovery_attempt_store is not None and not isinstance(
            recovery_attempt_store, EventLogRecoveryAttemptStore
        ):
            raise TypeError("recovery_attempt_store must be an EventLogRecoveryAttemptStore")
        if recovery_attempt_store is not None and (
            not isinstance(recovery_attempt_key, str) or not recovery_attempt_key.strip()
        ):
            raise ValueError("recovery_attempt_key is required when recovery_attempt_store is supplied")
        if recovery_attempt_store is not None:
            if (isinstance(recovery_lease_seconds, bool)
                    or not isinstance(recovery_lease_seconds, (int, float))
                    or not math.isfinite(recovery_lease_seconds)
                    or recovery_lease_seconds <= 0 or recovery_lease_seconds > 86400):
                raise ValueError("recovery_lease_seconds must be greater than 0 and at most 86400")
            heartbeat_interval = (
                recovery_heartbeat_interval_seconds
                if recovery_heartbeat_interval_seconds is not None
                else recovery_lease_seconds / 3
            )
            if (isinstance(heartbeat_interval, bool)
                    or not isinstance(heartbeat_interval, (int, float))
                    or not math.isfinite(heartbeat_interval)
                    or heartbeat_interval <= 0 or heartbeat_interval >= recovery_lease_seconds):
                raise ValueError("recovery heartbeat interval must be greater than 0 and shorter than the lease")
        else:
            heartbeat_interval = None
        active = Path(active_database_path).expanduser().resolve()
        if not active.exists():
            assessment = None
            findings: tuple[dict[str, object], ...] = ({"code": "active_log_missing"},)
        else:
            store = CommandEventStore(active)
            try:
                assessment = EventLogRecoveryGate.assess(store, anchor_store)
            except Exception as exc:
                assessment = None
                findings = ({"code": "startup_assessment_error",
                             "error_type": type(exc).__name__, "message": str(exc)},)
            else:
                findings = assessment.findings
            finally:
                store.close()

            if assessment is not None and assessment.trusted_for_read:
                return StartupRecoveryResult(
                    StartupRecoveryStatus.TRUSTED, assessment, None, (),
                )
            if assessment is not None and not findings:
                findings = ({"code": "active_log_not_trusted",
                             "status": assessment.status.value},)

        if backup_path is None or recovery_destination_path is None:
            return StartupRecoveryResult(
                StartupRecoveryStatus.RECOVERY_REQUIRED, assessment, None, findings,
            )

        destination = Path(recovery_destination_path).expanduser().resolve()
        backup = Path(backup_path).expanduser().resolve()
        anchor_path = Path(anchor_store.database_path).expanduser().resolve()
        if destination in {active, backup, anchor_path}:
            return StartupRecoveryResult(
                StartupRecoveryStatus.BLOCKED, assessment, None,
                findings + ({"code": "recovery_path_collision"},),
            )

        try:
            checkpoint_fingerprint = EventLogBackupManager.fingerprint_file(backup_path)
        except Exception as exc:
            return StartupRecoveryResult(
                StartupRecoveryStatus.BLOCKED, assessment, None,
                findings + ({"code": "backup_fingerprint_failed",
                             "error_type": type(exc).__name__, "message": str(exc)},),
            )

        attempt_started = False
        attempt_owner_run_id = None
        attempt_fencing_token = None
        if recovery_attempt_store is not None:
            # Reconcile the narrow crash window where restore_backup() atomically
            # published the candidate but the process died before finish_success().
            # Never trust the existing destination merely because it exists: both
            # the backup and candidate must independently verify against the anchor,
            # and their assessed chain positions must agree with the journaled input.
            prior = recovery_attempt_store.get(recovery_attempt_key)
            if (prior is not None and destination.exists() and
                    prior.status.value == "in_progress"):
                # Publication alone does not prove the previous owner has stopped.
                # A still-running owner could be concurrently finishing the same
                # attempt or performing follow-up work. PID liveness is only a
                # conservative local guard; when ownership cannot be established as
                # dead, fail closed and leave the journal untouched.
                if (prior.owner_pid is None or
                        EventLogRecoveryAttemptStore._pid_is_alive(prior.owner_pid)):
                    return StartupRecoveryResult(
                        StartupRecoveryStatus.BLOCKED, assessment, None,
                        findings + ({"code": "recovery_owner_still_alive_or_unknown"},),
                    )
            if (prior is not None and destination.exists() and prior.status.value in
                    {"in_progress", "succeeded"}):
                # A process can restart after publishing the candidate, either before
                # committing SUCCEEDED or after that commit but before the caller
                # receives the result. Both windows must be idempotent: validate the
                # durable checkpoint and candidate rather than trying to publish again.
                try:
                    if prior.checkpoint_fingerprint != checkpoint_fingerprint:
                        raise RuntimeError("backup checkpoint differs from recorded attempt")
                    backup_assessment = EventLogBackupManager.verify_backup(backup, anchor_store)
                    candidate_assessment = EventLogBackupManager._assess_database(destination, anchor_store)
                    if not backup_assessment.trusted_for_read or not candidate_assessment.trusted_for_read:
                        raise RuntimeError("backup or published candidate is not trusted")
                    if (backup_assessment.event_sequence != candidate_assessment.event_sequence or
                            backup_assessment.anchor_sequence != candidate_assessment.anchor_sequence):
                        raise RuntimeError("candidate does not match the verified backup checkpoint")
                    if prior.status.value == "in_progress":
                        recovery_attempt_store.finish_success(
                            recovery_attempt_key, owner_run_id=prior.owner_run_id,
                            fencing_token=prior.fencing_token,
                        )
                        finding_code = "recovered_publication_after_interruption"
                    else:
                        finding_code = "reused_verified_recovery_candidate"
                    return StartupRecoveryResult(
                        StartupRecoveryStatus.RECOVERY_READY, candidate_assessment,
                        str(destination), findings + ({"code": finding_code},),
                    )
                except Exception as exc:
                    failure_code = (
                        "interrupted_publication_reconciliation_failed"
                        if prior.status.value == "in_progress"
                        else "recovery_candidate_reconciliation_failed"
                    )
                    return StartupRecoveryResult(
                        StartupRecoveryStatus.BLOCKED, assessment, None,
                        findings + ({"code": failure_code,
                                     "error_type": type(exc).__name__, "message": str(exc)},),
                    )
            try:
                started_attempt = recovery_attempt_store.begin_attempt(
                    recovery_attempt_key, recovery_reason,
                    checkpoint_fingerprint=checkpoint_fingerprint,
                    max_attempts=max_recovery_attempts,
                    lease_seconds=recovery_lease_seconds,
                )
                attempt_owner_run_id = started_attempt.owner_run_id
                attempt_fencing_token = started_attempt.fencing_token
                attempt_started = True
            except RecoveryAttemptBlocked as exc:
                return StartupRecoveryResult(
                    StartupRecoveryStatus.BLOCKED, assessment, None,
                    findings + ({"code": "recovery_attempt_blocked", "message": str(exc)},),
                )

        heartbeat_stop = Event()
        heartbeat_errors: list[Exception] = []
        heartbeat_thread: Thread | None = None
        if attempt_started:
            def renew_while_working() -> None:
                assert recovery_attempt_store is not None
                assert heartbeat_interval is not None
                while not heartbeat_stop.wait(float(heartbeat_interval)):
                    try:
                        recovery_attempt_store.renew_lease(
                            recovery_attempt_key, owner_run_id=attempt_owner_run_id,
                            fencing_token=attempt_fencing_token,
                            lease_seconds=recovery_lease_seconds,
                        )
                    except Exception as heartbeat_error:
                        heartbeat_errors.append(heartbeat_error)
                        heartbeat_stop.set()
                        return

            heartbeat_thread = Thread(
                target=renew_while_working, name="trainos-recovery-lease-heartbeat", daemon=True,
            )
            heartbeat_thread.start()

        restore_error: Exception | None = None
        restored = None
        try:
            restored = EventLogBackupManager.restore_backup(
                backup_path, destination, anchor_store,
                expected_sha256=checkpoint_fingerprint,
            )
        except Exception as exc:
            restore_error = exc
        finally:
            heartbeat_stop.set()
            if heartbeat_thread is not None:
                heartbeat_thread.join()

        # A heartbeat failure means this worker can no longer prove that it owns
        # recovery. Do not mark success or failure: leave IN_PROGRESS for the
        # reconciliation path, which must independently verify the candidate.
        if heartbeat_errors:
            heartbeat_error = heartbeat_errors[0]
            return StartupRecoveryResult(
                StartupRecoveryStatus.BLOCKED, assessment, None,
                findings + ({"code": "recovery_lease_heartbeat_failed",
                             "error_type": type(heartbeat_error).__name__,
                             "message": str(heartbeat_error)},),
            )

        if restore_error is not None:
            if attempt_started:
                try:
                    recovery_attempt_store.finish_failure(
                        recovery_attempt_key, f"{type(restore_error).__name__}: {restore_error}",
                        owner_run_id=attempt_owner_run_id, fencing_token=attempt_fencing_token,
                    )
                except Exception:
                    # Preserve the original recovery failure; the durable IN_PROGRESS
                    # state will be reconciled as interrupted on the next startup.
                    pass
            return StartupRecoveryResult(
                StartupRecoveryStatus.BLOCKED, assessment, None,
                findings + ({"code": "recovery_candidate_rejected",
                             "error_type": type(restore_error).__name__, "message": str(restore_error)},),
            )
        assert restored is not None
        if attempt_started:
            try:
                recovery_attempt_store.finish_success(
                    recovery_attempt_key, owner_run_id=attempt_owner_run_id,
                    fencing_token=attempt_fencing_token,
                )
            except Exception as exc:
                # Keep the candidate for explicit reconciliation on the next startup.
                # Deleting by pathname here is unsafe: another process could have replaced
                # that path after publication, and Stage 91's reconciliation path already
                # verifies the checkpoint and candidate before marking the attempt successful.
                # This call still returns BLOCKED, so the candidate is not promoted or
                # reported as ready until the durable journal transition is confirmed.
                return StartupRecoveryResult(
                    StartupRecoveryStatus.BLOCKED, assessment, None,
                    findings + ({"code": "recovery_attempt_journal_update_failed",
                                 "error_type": type(exc).__name__, "message": str(exc)},),
                )
        return StartupRecoveryResult(
            StartupRecoveryStatus.RECOVERY_READY, restored,
            str(Path(recovery_destination_path).expanduser().resolve()), findings,
        )
