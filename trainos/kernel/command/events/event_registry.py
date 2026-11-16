from __future__ import annotations

from collections import defaultdict
from .command_event import CommandEvent
from .command_event_store import CommandEventStore
from .event_integrity_anchor_store import EventIntegrityAnchorStore
from .event_log_recovery_gate import EventLogRecoveryGate


class EventRegistry:
    def __init__(self, max_events_per_command: int = 100, *, store: CommandEventStore | None = None,
                 anchor_store: EventIntegrityAnchorStore | None = None,
                 require_trusted_reads: bool = False) -> None:
        if max_events_per_command < 1:
            raise ValueError("max_events_per_command must be positive")

        if store is not None and not isinstance(store, CommandEventStore):
            raise TypeError("store must be a CommandEventStore or None")
        if not isinstance(require_trusted_reads, bool):
            raise TypeError("require_trusted_reads must be a bool")
        if anchor_store is not None and not isinstance(anchor_store, EventIntegrityAnchorStore):
            raise TypeError("anchor_store must be an EventIntegrityAnchorStore or None")
        if require_trusted_reads and (store is None or anchor_store is None):
            raise ValueError("trusted reads require both a persistent event store and an anchor store")
        self._max_events = max_events_per_command
        self._store = store
        self._anchor_store = anchor_store
        self._require_trusted_reads = require_trusted_reads
        if require_trusted_reads:
            # Protect direct reads from this store too, not only reads routed through
            # this registry. This preserves default behavior for legacy callers.
            store.enable_trusted_reads(anchor_store)
        self._events: dict[str, list[CommandEvent]] = defaultdict(list)

    def _require_trusted_history(self) -> None:
        if self._require_trusted_reads:
            # Deliberately assessed for every read: no cached trust decision can outlive
            # a later database change or anchor-store outage.
            EventLogRecoveryGate.require_verified(self._store, self._anchor_store)

    def register(self, event: CommandEvent) -> None:
        if not isinstance(event, CommandEvent):
            raise TypeError("event must be a CommandEvent")
        if self._store is not None:
            self._store.append(event)
        history = self._events[event.command_id]
        history.append(event)

        if len(history) > self._max_events:
            del history[:-self._max_events]

    def get_events(self, command_id: str) -> tuple[CommandEvent, ...]:
        self._require_trusted_history()
        if self._store is not None:
            return self._store.get_events(command_id)
        return tuple(self._events.get(command_id, ()))

    def all_events(self) -> tuple[CommandEvent, ...]:
        """Return a deterministic snapshot of currently retained events.

        This is not a durable or complete audit history: each command is bounded by
        ``max_events_per_command`` and older events may already have been evicted.
        """
        self._require_trusted_history()
        if self._store is not None:
            return self._store.all_events()
        events = [event for history in self._events.values() for event in history]
        return tuple(sorted(events, key=lambda event: (event.timestamp, event.event_id)))

    def get_latest(self, command_id: str) -> CommandEvent | None:
        self._require_trusted_history()
        if self._store is not None:
            history = self._store.get_events(command_id)
            return history[-1] if history else None
        history = self._events.get(command_id)
        return history[-1] if history else None

    def clear(self, command_id: str | None = None) -> None:
        if self._store is not None:
            raise RuntimeError("cannot clear an append-only persistent event registry")
        if command_id is None:
            self._events.clear()
        else:
            self._events.pop(command_id, None)
