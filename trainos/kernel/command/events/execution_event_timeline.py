from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from threading import RLock

from .command_event import CommandEvent
from .event_service import CommandEventService
from .event_type import CommandEventType


@dataclass(frozen=True, slots=True)
class ObservedCommandEvent:
    """An event with local observation order for stable timeline analysis."""

    ordinal: int
    event: CommandEvent


@dataclass(frozen=True, slots=True)
class ExecutionEventTimelineSnapshot:
    """Bounded in-memory event timeline; not a durable audit source."""

    total_events: int
    retained_events: tuple[ObservedCommandEvent, ...]


@dataclass(frozen=True, slots=True)
class DiagnosticTimelineContext:
    """Prior same-command events that may help investigate a diagnostic."""

    diagnostic_event_id: str
    command_id: str
    diagnostic_code: str
    diagnostic_timestamp_iso: str
    preceding_event_ids: tuple[str, ...]
    preceding_event_types: tuple[str, ...]
    elapsed_seconds_from_previous_event: float | None
    evidence_note: str


@dataclass(frozen=True, slots=True)
class ExecutionEventTimelineAnalysis:
    """Read-only temporal correlations for diagnostics in a bounded snapshot."""

    analyzed_events: int
    diagnostic_count: int
    contexts: tuple[DiagnosticTimelineContext, ...]


class ExecutionEventTimelineMonitor:
    """Capture command lifecycle events for bounded, in-memory temporal analysis."""

    def __init__(self, event_service: CommandEventService, max_events: int = 2000) -> None:
        if not isinstance(event_service, CommandEventService):
            raise TypeError("event_service must be a CommandEventService")
        if isinstance(max_events, bool) or not isinstance(max_events, int) or max_events < 1:
            raise ValueError("max_events must be a positive integer")
        self._event_service = event_service
        self._max_events = max_events
        self._lock = RLock()
        self._total_events = 0
        self._events: list[ObservedCommandEvent] = []
        self._closed = False
        self._subscriptions: list[tuple[CommandEventType, object]] = []
        for event_type in CommandEventType:
            handler = self._make_handler()
            event_service.dispatcher.subscribe(event_type, handler)
            self._subscriptions.append((event_type, handler))

    def _make_handler(self):
        def handler(event: CommandEvent) -> None:
            with self._lock:
                if self._closed:
                    return
                self._total_events += 1
                self._events.append(ObservedCommandEvent(self._total_events, event))
                if len(self._events) > self._max_events:
                    del self._events[:len(self._events) - self._max_events]
        return handler

    def snapshot(self) -> ExecutionEventTimelineSnapshot:
        with self._lock:
            return ExecutionEventTimelineSnapshot(self._total_events, tuple(self._events))

    def close(self) -> None:
        with self._lock:
            if self._closed:
                return
            self._closed = True
        for event_type, handler in self._subscriptions:
            self._event_service.dispatcher.unsubscribe(event_type, handler)
        self._subscriptions.clear()

    def __enter__(self) -> ExecutionEventTimelineMonitor:
        return self

    def __exit__(self, exc_type, exc, traceback) -> None:
        self.close()


class ExecutionEventTimelineAnalyzer:
    """Correlate each retained diagnostic with earlier events for the same command.

    Temporal proximity is investigation context, not proof of causation. Events
    with other command IDs are intentionally not treated as the same execution.
    """

    def analyze(
        self,
        snapshot: ExecutionEventTimelineSnapshot,
        lookback_seconds: float = 300.0,
    ) -> ExecutionEventTimelineAnalysis:
        if not isinstance(snapshot, ExecutionEventTimelineSnapshot):
            raise TypeError("snapshot must be an ExecutionEventTimelineSnapshot")
        if isinstance(lookback_seconds, bool) or not isinstance(lookback_seconds, (int, float)) or lookback_seconds < 0:
            raise ValueError("lookback_seconds must be a non-negative number")

        events = tuple(sorted(snapshot.retained_events, key=lambda item: item.ordinal))
        by_command: dict[str, list[ObservedCommandEvent]] = {}
        for observed in events:
            by_command.setdefault(observed.event.command_id, []).append(observed)

        contexts: list[DiagnosticTimelineContext] = []
        diagnostic_type = CommandEventType.EXECUTION_INTEGRITY_DIAGNOSTIC
        lookback = timedelta(seconds=float(lookback_seconds))
        for observed in events:
            diagnostic = observed.event
            if diagnostic.event_type is not diagnostic_type:
                continue
            code = diagnostic.payload.get("code")
            if not isinstance(code, str) or not code.strip():
                continue
            earlier = [
                candidate for candidate in by_command.get(diagnostic.command_id, ())
                if candidate.ordinal < observed.ordinal
                and candidate.event.timestamp <= diagnostic.timestamp
                and diagnostic.timestamp - candidate.event.timestamp <= lookback
            ]
            previous = earlier[-1] if earlier else None
            contexts.append(DiagnosticTimelineContext(
                diagnostic_event_id=diagnostic.event_id,
                command_id=diagnostic.command_id,
                diagnostic_code=code,
                diagnostic_timestamp_iso=diagnostic.timestamp.isoformat(),
                preceding_event_ids=tuple(item.event.event_id for item in earlier),
                preceding_event_types=tuple(item.event.event_type.value for item in earlier),
                elapsed_seconds_from_previous_event=(
                    (diagnostic.timestamp - previous.event.timestamp).total_seconds() if previous else None
                ),
                evidence_note=(
                    "Earlier events share the command ID and fall within the configured lookback; "
                    "this is temporal correlation only, not proof of causation."
                    if earlier else
                    "No earlier retained event with the same command ID was found in the lookback; "
                    "history may be incomplete or outside the retention window."
                ),
            ))
        return ExecutionEventTimelineAnalysis(
            analyzed_events=len(events),
            diagnostic_count=len(contexts),
            contexts=tuple(contexts),
        )
