from dataclasses import replace
from datetime import datetime, timezone

import pytest

from kernel.command.events import (
    CommandEvent, CommandEventType, DiagnosticEvidenceValidator,
    EventRegistry,
)


def _event(event_id, command_id="cmd-1", event_type=CommandEventType.COMMAND_STARTED):
    payload = {"code": "integrity_mismatch"} if event_type is CommandEventType.EXECUTION_INTEGRITY_DIAGNOSTIC else {}
    return CommandEvent(event_id, command_id, event_type, datetime.now(timezone.utc), payload)


def _snapshot():
    from tests.domains.ci_release.test_diagnostic_evidence_validator import _registry_with_assessment
    registry, _, _ = _registry_with_assessment()
    snapshot = registry.snapshot()
    assessment = replace(snapshot.assessments[0], evidence_event_ids=("start-2",))
    return replace(snapshot, assessments=(assessment,))


def test_registry_validation_uses_retained_events_and_marks_history_incomplete():
    events = EventRegistry()
    events.register(_event("diag-1", event_type=CommandEventType.EXECUTION_INTEGRITY_DIAGNOSTIC))
    events.register(_event("start-1"))
    result = DiagnosticEvidenceValidator().validate_from_registry(_snapshot(), events)
    assert result.events_supplied == 2
    assert result.history_complete is False
    assert any(issue.code == "history_may_be_incomplete" for issue in result.issues)
    assert any(issue.code == "missing_diagnostic_event" and issue.severity == "warning" for issue in result.issues) is False
    assert any(issue.code == "missing_evidence_event" and issue.severity == "warning" for issue in result.issues)


def test_registry_snapshot_is_deterministic_and_respects_per_command_bound():
    events = EventRegistry(max_events_per_command=2)
    events.register(_event("old"))
    events.register(_event("kept-1"))
    events.register(_event("kept-2"))
    ids = [event.event_id for event in events.all_events()]
    assert len(ids) == 2
    assert "old" not in ids
    assert ids == sorted(ids, key=lambda event_id: next(
        event.timestamp for event in events.all_events() if event.event_id == event_id
    ))


def test_registry_validation_rejects_wrong_registry_type():
    with pytest.raises(TypeError, match="EventRegistry"):
        DiagnosticEvidenceValidator().validate_from_registry(_snapshot(), object())
