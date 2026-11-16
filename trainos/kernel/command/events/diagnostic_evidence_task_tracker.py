from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime, timezone
from threading import RLock
from typing import Iterable

from .diagnostic_evidence_collection_planner import EvidenceCollectionPlan, EvidenceCollectionTask

_TASK_STATES = frozenset({"pending", "in_progress", "completed", "blocked", "recovery_required"})


@dataclass(frozen=True, slots=True)
class EvidenceTaskTransition:
    sequence: int
    task_id: str
    from_state: str | None
    to_state: str
    actor: str
    note: str
    timestamp_iso: str


@dataclass(frozen=True, slots=True)
class TrackedEvidenceTask:
    task_id: str
    hypothesis_id: str
    task: EvidenceCollectionTask
    state: str = "pending"
    attempts: int = 0
    max_attempts: int = 3
    result_note: str = ""
    evidence_event_ids: tuple[str, ...] = ()
    updated_at_iso: str = ""


@dataclass(frozen=True, slots=True)
class EvidenceTaskTrackerSnapshot:
    tasks: tuple[TrackedEvidenceTask, ...]
    transitions: tuple[EvidenceTaskTransition, ...]
    total_registered: int
    total_transitions: int
    pending_count: int
    in_progress_count: int
    completed_count: int
    blocked_count: int
    recovery_required_count: int = 0


class DiagnosticEvidenceTaskTracker:
    """Tracks execution of diagnostic evidence tasks; it never performs the tasks."""

    def __init__(self, *, max_tasks: int = 5000, max_attempts: int = 3) -> None:
        if isinstance(max_tasks, bool) or not isinstance(max_tasks, int) or max_tasks < 1:
            raise ValueError("max_tasks must be a positive integer")
        if isinstance(max_attempts, bool) or not isinstance(max_attempts, int) or max_attempts < 1:
            raise ValueError("max_attempts must be a positive integer")
        self._max_tasks = max_tasks
        self._max_attempts = max_attempts
        self._lock = RLock()
        self._tasks: dict[str, TrackedEvidenceTask] = {}
        self._transitions: list[EvidenceTaskTransition] = []
        self._total_registered = 0
        self._total_transitions = 0

    @staticmethod
    def _task_id(hypothesis_id: str, code: str) -> str:
        return f"{hypothesis_id}::{code}"

    @staticmethod
    def _actor_note(actor: str, note: str, *, actor_name: str = "actor", note_name: str = "note") -> tuple[str, str]:
        if not isinstance(actor, str) or not actor.strip():
            raise ValueError(f"{actor_name} must be a non-empty string")
        if not isinstance(note, str) or not note.strip():
            raise ValueError(f"{note_name} must be a non-empty string")
        return actor.strip(), note.strip()

    def register_plan(self, plan: EvidenceCollectionPlan) -> tuple[TrackedEvidenceTask, ...]:
        """Register tasks from a plan idempotently; reject conflicts and capacity overflow atomically."""
        if not isinstance(plan, EvidenceCollectionPlan):
            raise TypeError("plan must be an EvidenceCollectionPlan")
        candidates: list[TrackedEvidenceTask] = []
        for hypothesis_plan in plan.plans:
            if not isinstance(hypothesis_plan.hypothesis_id, str) or not hypothesis_plan.hypothesis_id.strip():
                raise ValueError("plan contains an invalid hypothesis_id")
            for task in hypothesis_plan.tasks:
                if not isinstance(task, EvidenceCollectionTask):
                    raise TypeError("plan tasks must be EvidenceCollectionTask instances")
                task_id = self._task_id(hypothesis_plan.hypothesis_id, task.code)
                candidates.append(TrackedEvidenceTask(
                    task_id=task_id, hypothesis_id=hypothesis_plan.hypothesis_id,
                    task=task, max_attempts=self._max_attempts,
                    updated_at_iso=datetime.now(timezone.utc).isoformat(),
                ))
        ids = [item.task_id for item in candidates]
        if len(ids) != len(set(ids)):
            raise ValueError("plan contains duplicate task identities")
        with self._lock:
            new_items = [item for item in candidates if item.task_id not in self._tasks]
            if len(self._tasks) + len(new_items) > self._max_tasks:
                raise OverflowError("task capacity exceeded; no tasks were registered")
            # Validate every existing identity before mutating anything, so conflicts are atomic.
            for item in candidates:
                existing = self._tasks.get(item.task_id)
                if existing is not None and (existing.hypothesis_id, existing.task) != (item.hypothesis_id, item.task):
                    raise ValueError(f"conflicting task definition: {item.task_id}")
            for item in new_items:
                self._tasks[item.task_id] = item
                self._total_registered += 1
                self._record(item.task_id, None, "pending", "planner", "task registered from evidence plan")
            return tuple(self._tasks[item.task_id] for item in candidates)

    def start(self, task_id: str, *, actor: str) -> TrackedEvidenceTask:
        actor, note = self._actor_note(actor, "Task started", note_name="internal note")
        with self._lock:
            current = self._get(task_id)
            if current.state != "pending":
                raise ValueError(f"task can start only from pending state, got {current.state}")
            updated = replace(current, state="in_progress", attempts=current.attempts + 1,
                              updated_at_iso=datetime.now(timezone.utc).isoformat())
            self._tasks[task_id] = updated
            self._record(task_id, current.state, updated.state, actor, note)
            return updated

    def complete(
        self, task_id: str, *, actor: str, result_note: str,
        evidence_event_ids: Iterable[str] = (),
    ) -> TrackedEvidenceTask:
        actor, result_note = self._actor_note(actor, result_note, note_name="result_note")
        if isinstance(evidence_event_ids, (str, bytes)):
            raise TypeError("evidence_event_ids must be an iterable of event IDs")
        try:
            evidence = tuple(evidence_event_ids)
        except TypeError as exc:
            raise TypeError("evidence_event_ids must be an iterable of event IDs") from exc
        if any(not isinstance(item, str) or not item.strip() for item in evidence):
            raise ValueError("evidence event IDs must be non-empty strings")
        if len(set(evidence)) != len(evidence):
            raise ValueError("evidence event IDs must be unique")
        with self._lock:
            current = self._get(task_id)
            if current.state != "in_progress":
                raise ValueError("only an in-progress task can be completed")
            updated = replace(current, state="completed", result_note=result_note,
                              evidence_event_ids=tuple(item.strip() for item in evidence),
                              updated_at_iso=datetime.now(timezone.utc).isoformat())
            self._tasks[task_id] = updated
            self._record(task_id, current.state, updated.state, actor, result_note)
            return updated

    def fail(self, task_id: str, *, actor: str, reason: str, retryable: bool = True) -> TrackedEvidenceTask:
        actor, reason = self._actor_note(actor, reason, note_name="reason")
        if not isinstance(retryable, bool):
            raise TypeError("retryable must be a bool")
        with self._lock:
            current = self._get(task_id)
            if current.state != "in_progress":
                raise ValueError("only an in-progress task can fail")
            next_state = "pending" if retryable and current.attempts < current.max_attempts else "blocked"
            updated = replace(current, state=next_state, result_note=reason,
                              updated_at_iso=datetime.now(timezone.utc).isoformat())
            self._tasks[task_id] = updated
            self._record(task_id, current.state, updated.state, actor, reason)
            return updated

    def block(self, task_id: str, *, actor: str, reason: str) -> TrackedEvidenceTask:
        actor, reason = self._actor_note(actor, reason, note_name="reason")
        with self._lock:
            current = self._get(task_id)
            if current.state not in {"pending", "in_progress"}:
                raise ValueError(f"task cannot be blocked from {current.state}")
            updated = replace(current, state="blocked", result_note=reason,
                              updated_at_iso=datetime.now(timezone.utc).isoformat())
            self._tasks[task_id] = updated
            self._record(task_id, current.state, updated.state, actor, reason)
            return updated

    def mark_interrupted_tasks_for_recovery(self, *, actor: str = "recovery_manager") -> tuple[TrackedEvidenceTask, ...]:
        """Quarantine every in-progress task after restart; never re-execute it."""
        actor, note = self._actor_note(actor, "Interrupted by process restart; explicit reconciliation required")
        with self._lock:
            interrupted = [item for item in self._tasks.values() if item.state == "in_progress"]
            # All validation is completed before any mutation, making this operation atomic.
            updates = [replace(item, state="recovery_required", result_note=note,
                               updated_at_iso=datetime.now(timezone.utc).isoformat())
                       for item in interrupted]
            for updated in updates:
                current = self._tasks[updated.task_id]
                self._tasks[updated.task_id] = updated
                self._record(updated.task_id, current.state, updated.state, actor, note)
            return tuple(sorted(updates, key=lambda item: item.task_id))

    def resolve_recovery_required(
        self, task_id: str, *, decision: str, actor: str, note: str,
    ) -> TrackedEvidenceTask:
        """Require an explicit operator decision before retrying or blocking interrupted work."""
        actor, note = self._actor_note(actor, note)
        if decision not in {"retry", "block"}:
            raise ValueError("decision must be 'retry' or 'block'")
        with self._lock:
            current = self._get(task_id)
            if current.state != "recovery_required":
                raise ValueError("only a recovery_required task can be reconciled")
            if decision == "retry":
                if current.attempts >= current.max_attempts:
                    raise ValueError("retry limit exhausted; task cannot be returned to pending")
                next_state = "pending"
            else:
                next_state = "blocked"
            updated = replace(current, state=next_state, result_note=note,
                              updated_at_iso=datetime.now(timezone.utc).isoformat())
            self._tasks[task_id] = updated
            self._record(task_id, current.state, next_state, actor, f"recovery decision={decision}: {note}")
            return updated

    def _get(self, task_id: str) -> TrackedEvidenceTask:
        if not isinstance(task_id, str) or not task_id.strip():
            raise ValueError("task_id must be a non-empty string")
        try:
            return self._tasks[task_id]
        except KeyError as exc:
            raise KeyError(f"unknown evidence task: {task_id}") from exc

    def _record(self, task_id: str, from_state: str | None, to_state: str, actor: str, note: str) -> None:
        self._total_transitions += 1
        self._transitions.append(EvidenceTaskTransition(
            sequence=self._total_transitions, task_id=task_id, from_state=from_state,
            to_state=to_state, actor=actor, note=note,
            timestamp_iso=datetime.now(timezone.utc).isoformat(),
        ))

    def snapshot(self) -> EvidenceTaskTrackerSnapshot:
        with self._lock:
            tasks = tuple(sorted(self._tasks.values(), key=lambda item: item.task_id))
            transitions = tuple(self._transitions)
            counts = {state: sum(item.state == state for item in tasks) for state in _TASK_STATES}
            return EvidenceTaskTrackerSnapshot(
                tasks=tasks, transitions=transitions,
                total_registered=self._total_registered, total_transitions=self._total_transitions,
                pending_count=counts["pending"], in_progress_count=counts["in_progress"],
                completed_count=counts["completed"], blocked_count=counts["blocked"],
                recovery_required_count=counts["recovery_required"],
            )
