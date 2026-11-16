from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from .diagnostic_evidence_task_tracker import EvidenceTaskTrackerSnapshot


@dataclass(frozen=True, slots=True)
class EvidenceRecoveryIntegrityFinding:
    code: str
    severity: str
    task_id: str | None
    message: str


@dataclass(frozen=True, slots=True)
class EvidenceRecoveryIntegrityReport:
    findings: tuple[EvidenceRecoveryIntegrityFinding, ...]
    task_count: int
    transition_count: int
    recovery_required_count: int

    @property
    def is_consistent(self) -> bool:
        return not any(item.severity == "error" for item in self.findings)


class DiagnosticEvidenceRecoveryIntegrityVerifier:
    """Read-only audit of evidence-task transition history and recovery decisions."""

    _ALLOWED = frozenset({
        (None, "pending"), ("pending", "in_progress"), ("pending", "blocked"),
        ("in_progress", "completed"), ("in_progress", "pending"),
        ("in_progress", "blocked"), ("in_progress", "recovery_required"),
        ("recovery_required", "pending"), ("recovery_required", "blocked"),
    })
    _STATES = frozenset({"pending", "in_progress", "completed", "blocked", "recovery_required"})

    @staticmethod
    def _timestamp_valid(value: object) -> bool:
        if not isinstance(value, str) or not value.strip():
            return False
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return False
        return parsed.tzinfo is not None and parsed.utcoffset() is not None

    def verify(self, snapshot: EvidenceTaskTrackerSnapshot) -> EvidenceRecoveryIntegrityReport:
        if not isinstance(snapshot, EvidenceTaskTrackerSnapshot):
            raise TypeError("snapshot must be an EvidenceTaskTrackerSnapshot")
        findings: list[EvidenceRecoveryIntegrityFinding] = []

        def add(code: str, severity: str, task_id: str | None, message: str) -> None:
            findings.append(EvidenceRecoveryIntegrityFinding(code, severity, task_id, message))

        task_by_id = {task.task_id: task for task in snapshot.tasks}
        if len(task_by_id) != len(snapshot.tasks):
            add("duplicate_task_ids", "error", None, "Task snapshot contains duplicate task IDs.")
        if isinstance(snapshot.total_registered, bool) or not isinstance(snapshot.total_registered, int) or snapshot.total_registered < len(snapshot.tasks):
            add("invalid_registration_count", "error", None, "Lifetime registration count is below the retained task count or invalid.")
        if snapshot.total_transitions != len(snapshot.transitions):
            add("transition_count_mismatch", "error", None, "Transition counter does not match retained transition records.")
        sequences = [item.sequence for item in snapshot.transitions]
        if sequences != list(range(1, len(snapshot.transitions) + 1)):
            add("transition_sequence_invalid", "error", None, "Transition sequence contains gaps, duplicates, or out-of-order records.")

        state_counts = {state: sum(item.state == state for item in snapshot.tasks) for state in self._STATES}
        declared_counts = {
            "pending": snapshot.pending_count, "in_progress": snapshot.in_progress_count,
            "completed": snapshot.completed_count, "blocked": snapshot.blocked_count,
            "recovery_required": snapshot.recovery_required_count,
        }
        for state, actual in state_counts.items():
            if declared_counts[state] != actual:
                add("state_count_mismatch", "error", None, f"Declared {state} count does not match task records.")

        latest_state: dict[str, str] = {}
        starts: dict[str, int] = {}
        recovery_entries: set[str] = set()
        recovery_resolutions: set[str] = set()
        last_timestamp_by_task: dict[str, datetime] = {}
        for transition in snapshot.transitions:
            task_id = transition.task_id if isinstance(transition.task_id, str) else None
            if task_id not in task_by_id:
                add("transition_unknown_task", "error", task_id, "Transition refers to a task absent from the snapshot.")
            if (transition.from_state, transition.to_state) not in self._ALLOWED:
                add("transition_not_allowed", "error", task_id, "Transition uses a forbidden state edge.")
            if not isinstance(transition.actor, str) or not transition.actor.strip() or not isinstance(transition.note, str) or not transition.note.strip():
                add("transition_missing_audit_context", "error", task_id, "Transition lacks a non-empty actor or note.")
            if not self._timestamp_valid(transition.timestamp_iso):
                add("transition_timestamp_invalid", "error", task_id, "Transition timestamp must be ISO-8601 with an explicit timezone.")
            else:
                parsed = datetime.fromisoformat(transition.timestamp_iso.replace("Z", "+00:00"))
                previous = last_timestamp_by_task.get(task_id or "")
                if previous is not None and parsed < previous:
                    add("transition_time_reversed", "error", task_id, "Transition timestamp moves backwards for this task.")
                last_timestamp_by_task[task_id or ""] = parsed
            if task_id in latest_state:
                if transition.from_state != latest_state[task_id]:
                    add("transition_chain_discontinuous", "error", task_id, "Transition chain does not continue from the previous state.")
            elif transition.from_state is not None:
                add("initial_transition_missing", "error", task_id, "First retained transition for task is not its initial registration.")
            if task_id is not None:
                latest_state[task_id] = transition.to_state
                if transition.to_state == "in_progress":
                    starts[task_id] = starts.get(task_id, 0) + 1
                if transition.from_state == "in_progress" and transition.to_state == "recovery_required":
                    recovery_entries.add(task_id)
                if transition.from_state == "recovery_required":
                    expected = "retry" if transition.to_state == "pending" else "block" if transition.to_state == "blocked" else None
                    if expected is None or not isinstance(transition.note, str) or f"recovery decision={expected}:" not in transition.note:
                        add("recovery_decision_record_invalid", "error", task_id, "Recovery exit lacks a matching explicit retry/block decision in its audit note.")
                    else:
                        recovery_resolutions.add(task_id)

        for task_id, task in task_by_id.items():
            if task.state not in self._STATES:
                add("task_state_invalid", "error", task_id, "Task has an unsupported state.")
            if latest_state.get(task_id) != task.state:
                add("current_state_history_mismatch", "error", task_id, "Current task state disagrees with its latest transition.")
            if isinstance(task.attempts, bool) or not isinstance(task.attempts, int) or task.attempts < 0 or isinstance(task.max_attempts, bool) or not isinstance(task.max_attempts, int) or task.max_attempts < 1 or task.attempts > task.max_attempts:
                add("attempt_counts_invalid", "error", task_id, "Task attempt counts are invalid.")
            elif starts.get(task_id, 0) != task.attempts:
                add("attempt_count_history_mismatch", "error", task_id, "Recorded attempts disagree with in-progress transition count.")
            if task.state == "recovery_required" and task_id not in recovery_entries:
                add("recovery_entry_missing", "error", task_id, "Task is recovery_required but history has no in_progress-to-recovery_required transition.")
            if task.state in {"pending", "blocked"} and task_id in recovery_entries and task_id not in recovery_resolutions:
                add("recovery_resolution_missing", "error", task_id, "Task left recovery state without a matching explicit decision record.")

        findings.sort(key=lambda item: (item.severity, item.task_id or "", item.code, item.message))
        return EvidenceRecoveryIntegrityReport(
            findings=tuple(findings), task_count=len(snapshot.tasks),
            transition_count=len(snapshot.transitions), recovery_required_count=state_counts["recovery_required"],
        )
