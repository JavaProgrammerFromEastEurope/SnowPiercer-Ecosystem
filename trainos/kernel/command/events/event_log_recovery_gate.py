"""Fail-closed assessment of an event log after restart or backup restoration."""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .command_event_store import CommandEventStore
    from .event_integrity_anchor_store import EventIntegrityAnchorStore


class EventLogTrustStatus(str, Enum):
    VERIFIED = "verified"
    DAMAGED = "damaged"
    INSUFFICIENT_DATA = "insufficient_data"


@dataclass(frozen=True, slots=True)
class EventLogRecoveryAssessment:
    status: EventLogTrustStatus
    findings: tuple[dict[str, object], ...]
    event_sequence: int
    anchor_sequence: int | None

    @property
    def trusted_for_read(self) -> bool:
        """Only an explicitly verified log passes this conservative gate."""
        return self.status is EventLogTrustStatus.VERIFIED


class EventLogRecoveryGate:
    """Require trusted anchor evidence before recovered event history is consumed.

    This is an application-level gate. Callers must explicitly invoke it after
    opening/restoring a store and before using the history for consequential work.
    It does not provide hardware safety or remote anchor availability.
    """

    @staticmethod
    def assess(event_store: CommandEventStore,
               anchor_store: EventIntegrityAnchorStore) -> EventLogRecoveryAssessment:
        from .command_event_store import CommandEventStore
        from .event_integrity_anchor_store import EventIntegrityAnchorStore
        if not isinstance(event_store, CommandEventStore):
            raise TypeError("event_store must be a CommandEventStore")
        if not isinstance(anchor_store, EventIntegrityAnchorStore):
            raise TypeError("anchor_store must be an EventIntegrityAnchorStore")

        # Read each evidence source once per assessment. The event-log fields must
        # come from the same SQLite snapshot; otherwise a concurrent append could
        # make the reported head disagree with the hash-chain assessment.
        anchor = anchor_store.latest()
        snapshot = event_store.integrity_snapshot()
        findings = anchor_store.verify_against(
            event_store, anchor=anchor, integrity_snapshot=snapshot,
        )
        _, (sequence, _), _ = snapshot
        if anchor is None:
            status = EventLogTrustStatus.INSUFFICIENT_DATA
        elif findings:
            status = EventLogTrustStatus.DAMAGED
        else:
            status = EventLogTrustStatus.VERIFIED
        return EventLogRecoveryAssessment(
            status=status, findings=findings, event_sequence=sequence,
            anchor_sequence=None if anchor is None else anchor.event_sequence,
        )

    @staticmethod
    def require_verified(event_store: CommandEventStore,
                        anchor_store: EventIntegrityAnchorStore) -> EventLogRecoveryAssessment:
        assessment = EventLogRecoveryGate.assess(event_store, anchor_store)
        if not assessment.trusted_for_read:
            raise RuntimeError(
                f"event log recovery blocked: status={assessment.status.value}; "
                f"findings={assessment.findings!r}"
            )
        return assessment
