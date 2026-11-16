from __future__ import annotations

from dataclasses import dataclass

from .execution_event_timeline import ExecutionEventTimelineAnalysis


@dataclass(frozen=True, slots=True)
class SequencePatternFinding:
    """Observed event-sequence pattern; never a claim of root cause."""

    diagnostic_event_id: str
    command_id: str
    diagnostic_code: str
    pattern_code: str
    observed_event_types: tuple[str, ...]
    evidence_note: str
    confidence: str


@dataclass(frozen=True, slots=True)
class ExecutionEventSequenceAnalysis:
    analyzed_diagnostics: int
    findings: tuple[SequencePatternFinding, ...]


class ExecutionEventSequenceAnalyzer:
    """Identify conservative, explicit lifecycle sequence patterns in timeline context."""

    _TERMINAL = frozenset({"command_completed", "command_cancelled"})

    def analyze(self, timeline: ExecutionEventTimelineAnalysis) -> ExecutionEventSequenceAnalysis:
        if not isinstance(timeline, ExecutionEventTimelineAnalysis):
            raise TypeError("timeline must be an ExecutionEventTimelineAnalysis")

        findings: list[SequencePatternFinding] = []
        for context in timeline.contexts:
            types = context.preceding_event_types
            patterns: list[tuple[str, str, str]] = []

            # Only emit a pattern when the required ordering is present in the evidence.
            failure_indexes = [i for i, item in enumerate(types) if item == "command_failed"]
            retry_indexes = [i for i, item in enumerate(types) if item == "command_retrying"]
            if failure_indexes and retry_indexes and any(r < f for r in retry_indexes for f in failure_indexes):
                patterns.append((
                    "retry_then_failure", "moderate",
                    "A retry event was observed before a failure event in the retained lookback. "
                    "This sequence is evidence for investigation, not proof that retrying caused failure.",
                ))
            if failure_indexes and retry_indexes and any(f < r for f in failure_indexes for r in retry_indexes):
                patterns.append((
                    "failure_then_retry", "moderate",
                    "A failure event was observed before a retry event in the retained lookback. "
                    "Confirm whether the event stream represents a retry of the same logical operation.",
                ))
            terminal_indexes = [i for i, item in enumerate(types) if item in self._TERMINAL]
            if terminal_indexes:
                patterns.append((
                    "terminal_event_before_diagnostic", "low",
                    "A completion or cancellation event preceded the diagnostic. Verify event ordering, "
                    "command identity, and whether the diagnostic concerns the same lifecycle.",
                ))
            if "command_started" in types and "command_failed" in types:
                patterns.append((
                    "started_then_failed", "low",
                    "Both start and failure events were observed before the diagnostic. This describes "
                    "the observed lifecycle only; it does not establish the underlying fault.",
                ))

            for code, confidence, note in patterns:
                findings.append(SequencePatternFinding(
                    diagnostic_event_id=context.diagnostic_event_id,
                    command_id=context.command_id,
                    diagnostic_code=context.diagnostic_code,
                    pattern_code=code,
                    observed_event_types=types,
                    evidence_note=note,
                    confidence=confidence,
                ))

        return ExecutionEventSequenceAnalysis(
            analyzed_diagnostics=timeline.diagnostic_count,
            findings=tuple(findings),
        )
