from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime

from .execution_diagnostic_monitor import ExecutionDiagnosticSnapshot


_SEVERITY_RANK = {"critical": 0, "error": 1, "warning": 2, "info": 3}


@dataclass(frozen=True, slots=True)
class CrossExecutionDiagnosticPattern:
    """A diagnostic code observed in multiple distinct executions.

    A shared code is correlation evidence only; it does not establish a shared
    root cause. The execution IDs and timestamps are retained as review evidence.
    """

    code: str
    severity: str
    execution_ids: tuple[str, ...]
    execution_count: int
    total_occurrences: int
    first_seen_iso: str
    last_seen_iso: str
    priority: str
    recommendation: str


@dataclass(frozen=True, slots=True)
class DiagnosticPatternAnalysis:
    """Read-only cross-execution pattern summary for a bounded monitor snapshot."""

    analyzed_groups: int
    unique_codes: int
    cross_execution_pattern_count: int
    patterns: tuple[CrossExecutionDiagnosticPattern, ...]


class ExecutionDiagnosticPatternAnalyzer:
    """Identify diagnostic codes recurring across separate executions."""

    def analyze(self, snapshot: ExecutionDiagnosticSnapshot) -> DiagnosticPatternAnalysis:
        if not isinstance(snapshot, ExecutionDiagnosticSnapshot):
            raise TypeError("snapshot must be an ExecutionDiagnosticSnapshot")

        grouped = defaultdict(list)
        for finding in snapshot.recent_findings:
            grouped[finding.code].append(finding)

        patterns = []
        for code, findings in grouped.items():
            execution_ids = tuple(sorted({finding.execution_id for finding in findings}))
            if len(execution_ids) < 2:
                continue

            severity = min(
                (finding.severity for finding in findings),
                key=lambda value: _SEVERITY_RANK.get(value, len(_SEVERITY_RANK)),
            )
            occurrences = sum(finding.occurrences for finding in findings)
            times = [self._parse_time(finding.first_seen_iso or finding.timestamp_iso) for finding in findings]
            last_times = [self._parse_time(finding.timestamp_iso) for finding in findings]
            first_seen = min(times)
            last_seen = max(last_times)
            priority = "critical" if severity == "critical" else (
                "high" if len(execution_ids) >= 3 or occurrences > len(findings) else "normal"
            )
            recommendation = (
                f"Diagnostic code '{code}' appeared in {len(execution_ids)} distinct executions "
                f"({occurrences} retained occurrence(s)) between {first_seen.isoformat()} and "
                f"{last_seen.isoformat()}. Compare event timelines, software/configuration versions, "
                "and shared environmental conditions. A shared code alone does not prove a common cause; "
                "preserve evidence and do not automatically change execution state."
            )
            patterns.append(CrossExecutionDiagnosticPattern(
                code=code,
                severity=severity,
                execution_ids=execution_ids,
                execution_count=len(execution_ids),
                total_occurrences=occurrences,
                first_seen_iso=first_seen.isoformat(),
                last_seen_iso=last_seen.isoformat(),
                priority=priority,
                recommendation=recommendation,
            ))

        patterns.sort(key=lambda pattern: (
            _SEVERITY_RANK.get(pattern.severity, len(_SEVERITY_RANK)),
            -pattern.execution_count,
            -pattern.total_occurrences,
            pattern.code,
        ))
        return DiagnosticPatternAnalysis(
            analyzed_groups=len(snapshot.recent_findings),
            unique_codes=len(grouped),
            cross_execution_pattern_count=len(patterns),
            patterns=tuple(patterns),
        )

    @staticmethod
    def _parse_time(value: str) -> datetime:
        try:
            parsed = datetime.fromisoformat(value)
        except (TypeError, ValueError) as exc:
            raise ValueError("diagnostic timestamps must be valid ISO-8601 values") from exc
        if parsed.tzinfo is None or parsed.utcoffset() is None:
            raise ValueError("diagnostic timestamps must include a timezone")
        return parsed
