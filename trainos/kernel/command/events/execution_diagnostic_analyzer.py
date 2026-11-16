from __future__ import annotations

from collections import Counter
from dataclasses import dataclass

from .execution_diagnostic_monitor import ExecutionDiagnostic, ExecutionDiagnosticSnapshot


@dataclass(frozen=True, slots=True)
class DiagnosticRecommendation:
    """Read-only guidance for investigating a diagnostic pattern."""

    execution_id: str
    code: str
    severity: str
    occurrences: int
    repeated: bool
    priority: str
    category: str
    recommendation: str


@dataclass(frozen=True, slots=True)
class DiagnosticAnalysis:
    """Analysis of the currently retained monitor snapshot, not durable history."""

    analyzed_groups: int
    repeated_groups: int
    repeated_occurrences: int
    code_frequency: tuple[tuple[str, int], ...]
    recommendations: tuple[DiagnosticRecommendation, ...]


# Guidance is deliberately diagnostic only. No entry authorizes state mutation.
_RULES: dict[str, tuple[str, str]] = {
    "unknown_status": (
        "ledger_schema",
        "Compare the stored status with the supported status enum and review schema/version migration history; do not rewrite the status automatically.",
    ),
    "invalid_transition": (
        "state_machine",
        "Reconstruct the ordered state history and compare each transition with the permitted transition graph before deciding whether the record is corrupt.",
    ),
    "command_id_changed": (
        "identity_consistency",
        "Trace the execution and command identifiers across all records; preserve the records and investigate the source of the identity change rather than merging them.",
    ),
    "missing_initial_state": (
        "history_completeness",
        "Check whether earlier records were omitted, imported incompletely, or lost during migration before drawing conclusions about the execution lifecycle.",
    ),
    "missing_reconciliation": (
        "recovery_review",
        "Review the recovery-required state and supporting evidence; do not mark the execution completed or failed without an explicit verified reconciliation decision.",
    ),
    "invalid_attempts": (
        "execution_progress",
        "Inspect the recorded attempt count and its write path; compare against the non-negative integer invariant without resetting the counter automatically.",
    ),
    "invalid_max_attempts": (
        "execution_progress",
        "Inspect the configured maximum-attempt value and the write path; confirm it is a positive integer before considering any correction.",
    ),
    "invalid_progress": (
        "execution_progress",
        "Compare attempts and max_attempts with ExecutionProgress invariants and trace the write path; do not silently clamp the persisted values.",
    ),
    "completed_flag_mismatch": (
        "terminal_state_consistency",
        "Compare the terminal status with the completed flag and inspect the original transition; do not infer or rewrite the correct value from this finding alone.",
    ),
    "unknown_reconciliation_decision": (
        "reconciliation_review",
        "Review the reconciliation decision against the supported decision set and inspect its source; preserve the original record for investigation.",
    ),
    "missing_reconciliation_reason": (
        "reconciliation_review",
        "Inspect the reconciliation record and its evidence trail to determine why the decision reason is absent; do not invent a reason retroactively.",
    ),
    "orphan_reconciliation": (
        "reconciliation_review",
        "Trace the reconciliation record to its recovery-required history and investigate missing or mismatched execution records before linking anything.",
    ),
    "decision_status_mismatch": (
        "reconciliation_review",
        "Compare the reconciliation decision with the full ordered execution history and evidence; do not change the terminal status automatically.",
    ),
}


class ExecutionDiagnosticAnalyzer:
    """Create deterministic, non-mutating investigation guidance from a snapshot."""

    def analyze(self, snapshot: ExecutionDiagnosticSnapshot) -> DiagnosticAnalysis:
        if not isinstance(snapshot, ExecutionDiagnosticSnapshot):
            raise TypeError("snapshot must be an ExecutionDiagnosticSnapshot")

        findings = snapshot.recent_findings
        frequencies = Counter(finding.code for finding in findings)
        recommendations = tuple(
            self._recommend(finding) for finding in sorted(
                findings,
                key=lambda item: (
                    item.severity != "critical",
                    not item.repeated,
                    -item.occurrences,
                    item.execution_id,
                    item.code,
                ),
            )
        )
        return DiagnosticAnalysis(
            analyzed_groups=len(findings),
            repeated_groups=sum(finding.repeated for finding in findings),
            repeated_occurrences=sum(max(0, finding.occurrences - 1) for finding in findings),
            code_frequency=tuple(sorted(frequencies.items())),
            recommendations=recommendations,
        )

    @staticmethod
    def _recommend(finding: ExecutionDiagnostic) -> DiagnosticRecommendation:
        category, guidance = _RULES.get(
            finding.code,
            (
                "general_integrity",
                "Inspect the diagnostic message and the execution's ordered audit history; gather corroborating evidence before proposing a change.",
            ),
        )
        if finding.repeated:
            guidance = (
                f"This finding recurred {finding.occurrences} times in retained monitoring data. "
                "Prioritize a timeline and common-cause review. " + guidance
            )
        priority = "critical" if finding.severity == "critical" else (
            "high" if finding.repeated else "normal"
        )
        return DiagnosticRecommendation(
            execution_id=finding.execution_id,
            code=finding.code,
            severity=finding.severity,
            occurrences=finding.occurrences,
            repeated=finding.repeated,
            priority=priority,
            category=category,
            recommendation=guidance,
        )
