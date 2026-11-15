"""Offline lifecycle model. NEVER controls physical equipment."""
from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from hashlib import sha256
import json
from typing import Mapping
from .registry import Registry, RegistryError

class State(str, Enum):
    REGISTERED = 'REGISTERED'
    INITIALIZING = 'INITIALIZING'
    STANDBY = 'STANDBY'
    ACTIVE = 'ACTIVE'
    DEGRADED = 'DEGRADED'
    FAULT = 'FAULT'
    ISOLATED = 'ISOLATED'
    MAINTENANCE = 'MAINTENANCE'

TRANSITIONS = {
    State.REGISTERED: frozenset({State.INITIALIZING, State.ISOLATED}),
    State.INITIALIZING: frozenset({State.STANDBY, State.FAULT, State.ISOLATED}),
    State.STANDBY: frozenset({State.ACTIVE, State.MAINTENANCE, State.FAULT, State.ISOLATED}),
    State.ACTIVE: frozenset({State.STANDBY, State.DEGRADED, State.FAULT, State.ISOLATED}),
    State.DEGRADED: frozenset({State.STANDBY, State.FAULT, State.ISOLATED}),
    State.FAULT: frozenset({State.ISOLATED, State.MAINTENANCE}),
    State.ISOLATED: frozenset({State.MAINTENANCE, State.INITIALIZING}),
    State.MAINTENANCE: frozenset({State.INITIALIZING, State.ISOLATED}),
}

class TransitionError(RegistryError):
    pass

@dataclass(frozen=True)
class Event:
    sequence: int
    event_id: str
    component_id: str
    previous_state: State
    next_state: State
    reason: str
    actor: str
    timestamp_utc: str
    previous_hash: str
    event_hash: str

    def canonical_fields(self) -> dict:
        return {k: (v.value if isinstance(v, State) else v) for k,v in vars(self).items() if k != 'event_hash'}

    def as_dict(self) -> dict:
        return {**self.canonical_fields(), 'event_hash': self.event_hash}

class Lifecycle:
    """In-memory simulation; caller must persist and independently secure audit events."""
    def __init__(self, registry: Registry):
        self.registry = registry
        self._states = {cid: State.REGISTERED for cid in registry.components}
        self._events: list[Event] = []
        self._by_id: dict[str, Event] = {}

    def state(self, component_id: str) -> State:
        if component_id not in self._states:
            raise TransitionError(f'unknown component {component_id}')
        return self._states[component_id]

    @property
    def events(self) -> tuple[Event, ...]:
        return tuple(self._events)

    def snapshot(self) -> dict[str, str]:
        return {k:v.value for k,v in sorted(self._states.items())}

    def transition(self, component_id: str, next_state: State | str, *, event_id: str,
                   reason: str, actor: str, timestamp_utc: str | None = None) -> Event:
        if not isinstance(event_id, str) or not event_id.strip() or not isinstance(reason,str) or not reason.strip() or not isinstance(actor,str) or not actor.strip():
            raise TransitionError('event_id, reason, actor must be nonempty strings')
        if component_id not in self._states:
            raise TransitionError(f'unknown component {component_id}')
        try:
            target = State(next_state)
        except (ValueError, TypeError) as exc:
            raise TransitionError('unknown target state') from exc
        if event_id in self._by_id:
            raise TransitionError('duplicate event_id (replay rejected)')
        current = self._states[component_id]
        if target not in TRANSITIONS[current]:
            raise TransitionError(f'forbidden transition {current.value} -> {target.value}')
        if target == State.ACTIVE:
            missing = [dep for dep in self.registry.components[component_id]['depends_on'] if self._states[dep] != State.ACTIVE]
            if missing:
                raise TransitionError(f'inactive dependencies: {", ".join(sorted(missing))}')
        # A dependent ACTIVE component must not silently remain ACTIVE if its prerequisite exits ACTIVE.
        if current == State.ACTIVE and target != State.ACTIVE:
            active_dependents = [cid for cid,c in self.registry.components.items()
                                 if component_id in c['depends_on'] and self._states[cid] == State.ACTIVE]
            if active_dependents:
                raise TransitionError(f'active dependents must transition first: {", ".join(sorted(active_dependents))}')
        stamp = timestamp_utc or datetime.now(timezone.utc).isoformat().replace('+00:00','Z')
        try:
            parsed = datetime.fromisoformat(stamp.replace('Z','+00:00'))
        except (ValueError, AttributeError) as exc:
            raise TransitionError('invalid timestamp') from exc
        if parsed.tzinfo is None or parsed.utcoffset().total_seconds() != 0:
            raise TransitionError('timestamp must be UTC')
        if self._events and parsed < datetime.fromisoformat(self._events[-1].timestamp_utc.replace('Z','+00:00')):
            raise TransitionError('nonmonotonic timestamp')
        previous_hash = self._events[-1].event_hash if self._events else '0'*64
        fields = dict(sequence=len(self._events)+1, event_id=event_id, component_id=component_id,
                      previous_state=current.value, next_state=target.value, reason=reason, actor=actor,
                      timestamp_utc=stamp, previous_hash=previous_hash)
        digest = sha256(json.dumps(fields, sort_keys=True, separators=(',',':'),ensure_ascii=False).encode()).hexdigest()
        event = Event(**{**fields,'previous_state':current,'next_state':target,'event_hash':digest})
        self._states[component_id] = target
        self._events.append(event)
        self._by_id[event_id] = event
        return event

    def verify_audit(self) -> bool:
        prev = '0'*64
        states = {cid: State.REGISTERED for cid in self.registry.components}
        seen = set()
        for seq,event in enumerate(self._events,1):
            fields = event.canonical_fields()
            digest = sha256(json.dumps(fields,sort_keys=True,separators=(',',':'),ensure_ascii=False).encode()).hexdigest()
            if (event.sequence != seq or event.previous_hash != prev or event.event_hash != digest
                    or event.event_id in seen or event.component_id not in states
                    or states[event.component_id] != event.previous_state
                    or event.next_state not in TRANSITIONS[event.previous_state]):
                return False
            seen.add(event.event_id)
            states[event.component_id] = event.next_state
            prev = digest
        return states == self._states and len(self._by_id) == len(self._events)
