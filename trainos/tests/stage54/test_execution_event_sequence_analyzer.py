from dataclasses import replace

import pytest

from kernel.command.events import (
    ExecutionEventSequenceAnalyzer,
    ExecutionEventTimelineAnalysis,
    DiagnosticTimelineContext,
)


def context(types, code="invalid_transition"):
    return DiagnosticTimelineContext(
        diagnostic_event_id="diag-1", command_id="cmd-1", diagnostic_code=code,
        diagnostic_timestamp_iso="2026-10-20T10:00:00+00:00",
        preceding_event_ids=tuple(f"e{i}" for i in range(len(types))),
        preceding_event_types=tuple(types), elapsed_seconds_from_previous_event=1.0,
        evidence_note="temporal correlation only",
    )


def test_detects_retry_then_failure_without_claiming_causation():
    result = ExecutionEventSequenceAnalyzer().analyze(ExecutionEventTimelineAnalysis(
        analyzed_events=4, diagnostic_count=1,
        contexts=(context(("command_started", "command_retrying", "command_failed")),),
    ))
    finding = next(item for item in result.findings if item.pattern_code == "retry_then_failure")
    assert finding.confidence == "moderate"
    assert "not proof" in finding.evidence_note


def test_failure_then_retry_is_order_sensitive():
    result = ExecutionEventSequenceAnalyzer().analyze(ExecutionEventTimelineAnalysis(
        analyzed_events=3, diagnostic_count=1,
        contexts=(context(("command_failed", "command_retrying")),),
    ))
    codes = {item.pattern_code for item in result.findings}
    assert "failure_then_retry" in codes
    assert "retry_then_failure" not in codes


def test_reports_terminal_event_and_start_then_failure_patterns():
    result = ExecutionEventSequenceAnalyzer().analyze(ExecutionEventTimelineAnalysis(
        analyzed_events=4, diagnostic_count=1,
        contexts=(context(("command_started", "command_failed", "command_completed")),),
    ))
    codes = {item.pattern_code for item in result.findings}
    assert {"terminal_event_before_diagnostic", "started_then_failed"} <= codes


def test_no_pattern_for_unrelated_or_empty_lifecycle():
    result = ExecutionEventSequenceAnalyzer().analyze(ExecutionEventTimelineAnalysis(
        analyzed_events=1, diagnostic_count=1,
        contexts=(context(("command_created", "command_progress_updated")),),
    ))
    assert result.findings == ()


def test_validates_input_type():
    with pytest.raises(TypeError):
        ExecutionEventSequenceAnalyzer().analyze(object())
