from kernel.command.events import (
    CommandEventService,
    CommandEventType,
    ExecutionDiagnosticAnalyzer,
    ExecutionDiagnosticMonitor,
)


def publish(service, *, execution_id="exec-1", code="invalid_transition", severity="error", message="bad transition"):
    return service.publish(execution_id, CommandEventType.EXECUTION_INTEGRITY_DIAGNOSTIC, {
        "diagnostic_type": "execution_integrity",
        "execution_id": execution_id,
        "code": code,
        "severity": severity,
        "message": message,
    })


def test_analyzer_counts_codes_and_prioritizes_critical_and_repeated_findings():
    service = CommandEventService()
    monitor = ExecutionDiagnosticMonitor(service)
    publish(service, execution_id="exec-a", code="invalid_transition", severity="critical")
    publish(service, execution_id="exec-a", code="invalid_transition", severity="critical")
    publish(service, execution_id="exec-b", code="unknown_new_code", severity="error")

    result = ExecutionDiagnosticAnalyzer().analyze(monitor.snapshot())
    assert result.analyzed_groups == 2
    assert result.repeated_groups == 1
    assert result.repeated_occurrences == 1
    assert result.code_frequency == (("invalid_transition", 1), ("unknown_new_code", 1))
    assert result.recommendations[0].execution_id == "exec-a"
    assert result.recommendations[0].priority == "critical"
    assert result.recommendations[0].repeated is True
    assert "recurred 2 times" in result.recommendations[0].recommendation
    assert result.recommendations[1].category == "general_integrity"
    monitor.close()


def test_repeated_noncritical_finding_gets_high_priority_and_known_guidance():
    service = CommandEventService()
    monitor = ExecutionDiagnosticMonitor(service)
    publish(service, code="invalid_progress", severity="error")
    publish(service, code="invalid_progress", severity="error")

    recommendation = ExecutionDiagnosticAnalyzer().analyze(monitor.snapshot()).recommendations[0]
    assert recommendation.priority == "high"
    assert recommendation.category == "execution_progress"
    assert "do not silently clamp" in recommendation.recommendation
    monitor.close()


def test_analyzer_is_read_only_and_empty_snapshot_has_no_recommendations():
    service = CommandEventService()
    monitor = ExecutionDiagnosticMonitor(service)
    before = monitor.snapshot()
    result = ExecutionDiagnosticAnalyzer().analyze(before)
    after = monitor.snapshot()
    assert result.analyzed_groups == 0
    assert result.recommendations == ()
    assert before == after
    monitor.close()


def test_analyzer_rejects_wrong_input_type():
    try:
        ExecutionDiagnosticAnalyzer().analyze(object())
    except TypeError:
        pass
    else:
        raise AssertionError("analyzer must reject unsupported input")
