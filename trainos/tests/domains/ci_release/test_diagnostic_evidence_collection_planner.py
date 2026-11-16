from datetime import datetime, timedelta, timezone

import pytest

from kernel.command.events import (
    CommandEvent, CommandEventType, DiagnosticEvidenceCollectionPlanner,
    DiagnosticHypothesisRegistry, ExecutionEventSequenceAnalyzer,
    ExecutionEventTimelineAnalysis, DiagnosticTimelineContext,
)


def _event(event_id, event_type, *, command_id="cmd-1", payload=None, seconds_ago=30):
    return CommandEvent(event_id, command_id, event_type,
                        datetime.now(timezone.utc) - timedelta(seconds=seconds_ago), payload or {})


def _registry_and_events():
    context = DiagnosticTimelineContext(
        diagnostic_event_id="diag-1", command_id="cmd-1", diagnostic_code="integrity_mismatch",
        diagnostic_timestamp_iso=datetime.now(timezone.utc).isoformat(),
        preceding_event_ids=("start-1", "fail-1"),
        preceding_event_types=("command_started", "command_failed"),
        elapsed_seconds_from_previous_event=1.0, evidence_note="observed sequence only",
    )
    analysis = ExecutionEventTimelineAnalysis(analyzed_events=2, diagnostic_count=1, contexts=(context,))
    registry = DiagnosticHypothesisRegistry()
    hypothesis = registry.register_findings(ExecutionEventSequenceAnalyzer().analyze(analysis).findings)[0]
    events = (
        _event("diag-1", CommandEventType.EXECUTION_INTEGRITY_DIAGNOSTIC,
               payload={"code": "integrity_mismatch"}, seconds_ago=5),
        _event("start-1", CommandEventType.COMMAND_STARTED, seconds_ago=20),
        _event("fail-1", CommandEventType.COMMAND_FAILED, seconds_ago=10),
    )
    return registry, hypothesis, events


def test_plan_lists_missing_evidence_and_incomplete_history():
    registry, hypothesis, events = _registry_and_events()
    plan = DiagnosticEvidenceCollectionPlanner().plan(registry.snapshot(), events)
    item = plan.plans[0]
    codes = {task.code for task in item.tasks}
    assert item.hypothesis_id == hypothesis.hypothesis_id
    assert "complete_event_history" in codes
    assert "collect_additional_events" in codes
    assert "request_explicit_assessment" in codes
    assert plan.task_count == sum(len(p.tasks) for p in plan.plans)
    assert plan.high_priority_task_count == sum(t.priority == "high" for p in plan.plans for t in p.tasks)


def test_complete_history_with_explicit_assessment_still_requests_expert_review():
    registry, hypothesis, events = _registry_and_events()
    registry.assess(hypothesis.hypothesis_id, "evidence_supports", ("start-1", "fail-1"),
                    "reviewer", "Observed two event types; cause remains unproven.")
    plan = DiagnosticEvidenceCollectionPlanner().plan(registry.snapshot(), events, history_complete=True)
    codes = {task.code for task in plan.plans[0].tasks}
    assert "independent_expert_review" in codes
    assert "complete_event_history" not in codes
    assert plan.history_complete is True


def test_integrity_problem_is_high_priority_and_does_not_mutate_registry():
    registry, hypothesis, events = _registry_and_events()
    registry.assess(hypothesis.hypothesis_id, "evidence_supports", ("start-1", "fail-1"), "reviewer", "Review.")
    bad = tuple(e for e in events if e.event_id != "diag-1") + (
        _event("diag-1", CommandEventType.EXECUTION_INTEGRITY_DIAGNOSTIC,
               payload={"code": "wrong_code"}),
    )
    before = registry.snapshot()
    plan = DiagnosticEvidenceCollectionPlanner().plan(before, bad, history_complete=True)
    tasks = {task.code: task for task in plan.plans[0].tasks}
    assert "verify_diagnostic_code" in tasks
    assert tasks["verify_diagnostic_code"].priority == "high"
    assert registry.snapshot() == before


def test_plan_is_deterministic_and_has_safety_limitations():
    registry, _, events = _registry_and_events()
    planner = DiagnosticEvidenceCollectionPlanner()
    first = planner.plan(registry.snapshot(), events, history_complete=True)
    second = planner.plan(registry.snapshot(), events, history_complete=True)
    assert first == second
    assert any("does not retrieve data" in item for item in first.limitations)
    assert any("not proof" in item for item in first.limitations)


def test_invalid_inputs_are_rejected():
    planner = DiagnosticEvidenceCollectionPlanner()
    registry, _, events = _registry_and_events()
    with pytest.raises(TypeError):
        planner.plan(object(), events)
    with pytest.raises(TypeError):
        planner.plan(registry.snapshot(), "not events")
    with pytest.raises(TypeError):
        planner.plan(registry.snapshot(), (object(),))
    with pytest.raises(TypeError):
        planner.plan(registry.snapshot(), events, history_complete=1)
    with pytest.raises(TypeError):
        DiagnosticEvidenceCollectionPlanner(validator=object())
    with pytest.raises(TypeError):
        DiagnosticEvidenceCollectionPlanner(assessor=object())
