from dataclasses import replace

import pytest

from kernel.command.events import (
    CommandEventService,
    CommandEventType,
    ExecutionDiagnosticMonitor,
    ExecutionDiagnosticPatternAnalyzer,
)


def publish(service, execution_id, code, severity="error", message="diagnostic"):
    return service.publish(execution_id, CommandEventType.EXECUTION_INTEGRITY_DIAGNOSTIC, {
        "diagnostic_type": "execution_integrity",
        "execution_id": execution_id,
        "code": code,
        "severity": severity,
        "message": message,
    })


def test_detects_same_code_across_distinct_executions_with_evidence():
    service = CommandEventService()
    monitor = ExecutionDiagnosticMonitor(service)
    publish(service, "exec-b", "invalid_transition", "error")
    publish(service, "exec-a", "invalid_transition", "critical")
    publish(service, "exec-c", "unknown_status", "warning")

    result = ExecutionDiagnosticPatternAnalyzer().analyze(monitor.snapshot())
    assert result.analyzed_groups == 3
    assert result.unique_codes == 2
    assert result.cross_execution_pattern_count == 1
    pattern = result.patterns[0]
    assert pattern.code == "invalid_transition"
    assert pattern.execution_ids == ("exec-a", "exec-b")
    assert pattern.execution_count == 2
    assert pattern.total_occurrences == 2
    assert pattern.severity == "critical"
    assert pattern.priority == "critical"
    assert "does not prove a common cause" in pattern.recommendation
    monitor.close()


def test_same_code_repeated_within_one_execution_is_not_cross_execution_pattern():
    service = CommandEventService()
    monitor = ExecutionDiagnosticMonitor(service)
    publish(service, "exec-a", "invalid_progress")
    publish(service, "exec-a", "invalid_progress")

    result = ExecutionDiagnosticPatternAnalyzer().analyze(monitor.snapshot())
    assert result.unique_codes == 1
    assert result.cross_execution_pattern_count == 0
    assert result.patterns == ()
    monitor.close()


def test_prioritizes_more_executions_and_retains_recurrence_counts():
    service = CommandEventService()
    monitor = ExecutionDiagnosticMonitor(service)
    publish(service, "exec-a", "shared_fault", "warning")
    publish(service, "exec-a", "shared_fault", "warning")
    publish(service, "exec-b", "shared_fault", "warning")
    publish(service, "exec-c", "shared_fault", "warning")
    publish(service, "exec-a", "two_exec_fault", "error")
    publish(service, "exec-b", "two_exec_fault", "error")

    result = ExecutionDiagnosticPatternAnalyzer().analyze(monitor.snapshot())
    assert [pattern.code for pattern in result.patterns] == ["two_exec_fault", "shared_fault"]
    shared = next(pattern for pattern in result.patterns if pattern.code == "shared_fault")
    assert shared.priority == "high"
    assert shared.execution_count == 3
    assert shared.total_occurrences == 4
    monitor.close()


def test_analysis_is_read_only_and_rejects_invalid_input():
    service = CommandEventService()
    monitor = ExecutionDiagnosticMonitor(service)
    publish(service, "exec-a", "shared_fault")
    publish(service, "exec-b", "shared_fault")
    before = monitor.snapshot()
    result = ExecutionDiagnosticPatternAnalyzer().analyze(before)
    assert result == ExecutionDiagnosticPatternAnalyzer().analyze(before)
    assert monitor.snapshot() == before
    with pytest.raises(TypeError):
        ExecutionDiagnosticPatternAnalyzer().analyze(object())
    monitor.close()


def test_rejects_timestamp_without_timezone():
    service = CommandEventService()
    monitor = ExecutionDiagnosticMonitor(service)
    publish(service, "exec-a", "shared_fault")
    publish(service, "exec-b", "shared_fault")
    snapshot = monitor.snapshot()
    finding = replace(snapshot.recent_findings[0], timestamp_iso="2026-10-20T07:00:00")
    altered = replace(snapshot, recent_findings=(finding, *snapshot.recent_findings[1:]))
    with pytest.raises(ValueError, match="include a timezone"):
        ExecutionDiagnosticPatternAnalyzer().analyze(altered)
    monitor.close()
