from datetime import datetime, timedelta, timezone

import pytest

from kernel.command.events import (
    CommandEvent,
    CommandEventService,
    CommandEventType,
    ExecutionEventTimelineAnalyzer,
    ExecutionEventTimelineMonitor,
)


def publish(service, command_id, event_type, payload=None, timestamp=None):
    event = CommandEvent.create(command_id, event_type, payload)
    if timestamp is not None:
        event = CommandEvent(
            event_id=event.event_id,
            command_id=event.command_id,
            event_type=event.event_type,
            timestamp=timestamp,
            payload=event.payload,
        )
        service.registry.register(event)
        service.dispatcher.dispatch(event)
        return event
    return service.publish(command_id, event_type, payload)


def diagnostic(service, command_id, code="invalid_transition", timestamp=None):
    return publish(service, command_id, CommandEventType.EXECUTION_INTEGRITY_DIAGNOSTIC, {
        "diagnostic_type": "execution_integrity",
        "execution_id": command_id,
        "code": code,
        "severity": "critical",
        "message": "test finding",
    }, timestamp)


def test_correlates_prior_lifecycle_events_for_same_command_only():
    service = CommandEventService()
    monitor = ExecutionEventTimelineMonitor(service)
    base = datetime(2026, 10, 20, 10, tzinfo=timezone.utc)
    publish(service, "exec-1", CommandEventType.COMMAND_CREATED, timestamp=base)
    publish(service, "other-exec", CommandEventType.COMMAND_STARTED, timestamp=base + timedelta(seconds=1))
    publish(service, "exec-1", CommandEventType.COMMAND_RETRYING, {"attempt": 1}, base + timedelta(seconds=2))
    finding = diagnostic(service, "exec-1", timestamp=base + timedelta(seconds=4))

    analysis = ExecutionEventTimelineAnalyzer().analyze(monitor.snapshot())
    context = next(item for item in analysis.contexts if item.diagnostic_event_id == finding.event_id)
    assert context.preceding_event_types == ("command_created", "command_retrying")
    assert context.elapsed_seconds_from_previous_event == 2.0
    assert "not proof of causation" in context.evidence_note
    monitor.close()


def test_lookback_excludes_old_events_and_reports_missing_context():
    service = CommandEventService()
    monitor = ExecutionEventTimelineMonitor(service)
    base = datetime(2026, 10, 20, 10, tzinfo=timezone.utc)
    publish(service, "exec-1", CommandEventType.COMMAND_STARTED, timestamp=base)
    finding = diagnostic(service, "exec-1", timestamp=base + timedelta(seconds=100))
    context = ExecutionEventTimelineAnalyzer().analyze(monitor.snapshot(), lookback_seconds=10).contexts[0]
    assert context.diagnostic_event_id == finding.event_id
    assert context.preceding_event_ids == ()
    assert context.elapsed_seconds_from_previous_event is None
    monitor.close()


def test_monitor_retention_is_bounded_but_total_count_is_cumulative():
    service = CommandEventService()
    monitor = ExecutionEventTimelineMonitor(service, max_events=2)
    publish(service, "x", CommandEventType.COMMAND_CREATED)
    publish(service, "x", CommandEventType.COMMAND_STARTED)
    publish(service, "x", CommandEventType.COMMAND_COMPLETED)
    snapshot = monitor.snapshot()
    assert snapshot.total_events == 3
    assert len(snapshot.retained_events) == 2
    assert [item.event.event_type for item in snapshot.retained_events] == [
        CommandEventType.COMMAND_STARTED, CommandEventType.COMMAND_COMPLETED
    ]
    monitor.close()


def test_close_is_idempotent_and_stops_collection():
    service = CommandEventService()
    monitor = ExecutionEventTimelineMonitor(service)
    monitor.close()
    monitor.close()
    publish(service, "x", CommandEventType.COMMAND_CREATED)
    assert monitor.snapshot().total_events == 0


def test_validates_constructor_and_analyzer_arguments():
    with pytest.raises(TypeError):
        ExecutionEventTimelineMonitor(object())
    with pytest.raises(ValueError):
        ExecutionEventTimelineMonitor(CommandEventService(), max_events=0)
    monitor = ExecutionEventTimelineMonitor(CommandEventService())
    with pytest.raises(ValueError):
        ExecutionEventTimelineAnalyzer().analyze(monitor.snapshot(), lookback_seconds=-1)
    with pytest.raises(TypeError):
        ExecutionEventTimelineAnalyzer().analyze(object())
    monitor.close()
