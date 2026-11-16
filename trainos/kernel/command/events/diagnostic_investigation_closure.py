from __future__ import annotations

from dataclasses import dataclass

from .diagnostic_evidence_task_closure import EvidenceTaskClosureReport
from .diagnostic_evidence_task_tracker import EvidenceTaskTrackerSnapshot
from .diagnostic_hypothesis_registry import HypothesisRegistrySnapshot


@dataclass(frozen=True, slots=True)
class InvestigationHypothesisSummary:
    """Aggregate closure state for one hypothesis; not a root-cause verdict."""

    hypothesis_id: str
    disposition: str
    task_count: int
    verified_task_count: int
    open_task_count: int
    needs_review_task_count: int
    blocked_task_count: int
    status: str
    outstanding_task_ids: tuple[str, ...]
    finding_codes: tuple[str, ...]
    recommendation: str
    recovery_required_task_count: int = 0


@dataclass(frozen=True, slots=True)
class DiagnosticInvestigationClosureReport:
    """Read-only cross-task investigation summary with explicit limitations."""

    hypotheses: tuple[InvestigationHypothesisSummary, ...]
    history_complete: bool
    total_hypotheses: int
    ready_for_expert_review_count: int
    needs_review_count: int
    blocked_count: int
    open_count: int
    unplanned_count: int
    orphan_task_ids: tuple[str, ...] = ()
    total_recovery_required_count: int = 0

    @property
    def all_investigations_ready_for_expert_review(self) -> bool:
        return (
            self.total_hypotheses > 0
            and self.ready_for_expert_review_count == self.total_hypotheses
            and self.blocked_count == 0
            and self.needs_review_count == 0
            and self.open_count == 0
            and self.total_recovery_required_count == 0
            and self.unplanned_count == 0
            and not self.orphan_task_ids
            and self.history_complete
        )


class DiagnosticInvestigationClosureReporter:
    """Aggregate task-closure results by hypothesis without changing any state.

    A ready status only means the retained tasks passed the supplied closure verifier
    and the hypothesis has an explicit supporting/refuting assessment. It does not
    establish a causal root cause, prove a fault was fixed, or authorize equipment use.
    """

    _REVIEWED_DISPOSITIONS = frozenset({"evidence_supports", "evidence_refutes"})

    def report(
        self,
        task_snapshot: EvidenceTaskTrackerSnapshot,
        hypothesis_snapshot: HypothesisRegistrySnapshot,
        closure_report: EvidenceTaskClosureReport,
    ) -> DiagnosticInvestigationClosureReport:
        if not isinstance(task_snapshot, EvidenceTaskTrackerSnapshot):
            raise TypeError("task_snapshot must be an EvidenceTaskTrackerSnapshot")
        if not isinstance(hypothesis_snapshot, HypothesisRegistrySnapshot):
            raise TypeError("hypothesis_snapshot must be a HypothesisRegistrySnapshot")
        if not isinstance(closure_report, EvidenceTaskClosureReport):
            raise TypeError("closure_report must be an EvidenceTaskClosureReport")

        tracked_by_id = {task.task_id: task for task in task_snapshot.tasks}
        result_by_id = {result.task_id: result for result in closure_report.results}
        if len(result_by_id) != len(closure_report.results):
            raise ValueError("closure report contains duplicate task IDs")
        if set(result_by_id) != set(tracked_by_id):
            raise ValueError("closure report task IDs do not match the supplied task snapshot")

        hypotheses_by_id = {hypothesis.hypothesis_id: hypothesis for hypothesis in hypothesis_snapshot.hypotheses}
        if len(hypotheses_by_id) != len(hypothesis_snapshot.hypotheses):
            raise ValueError("hypothesis snapshot contains duplicate hypothesis IDs")

        task_ids_by_hypothesis: dict[str, list[str]] = {}
        orphan_task_ids: list[str] = []
        for task in task_snapshot.tasks:
            if task.hypothesis_id not in hypotheses_by_id:
                orphan_task_ids.append(task.task_id)
                continue
            task_ids_by_hypothesis.setdefault(task.hypothesis_id, []).append(task.task_id)

        summaries: list[InvestigationHypothesisSummary] = []
        for hypothesis_id, hypothesis in sorted(hypotheses_by_id.items()):
            task_ids = sorted(task_ids_by_hypothesis.get(hypothesis_id, ()))
            task_results = [result_by_id[task_id] for task_id in task_ids]
            verified = sum(result.status == "verified" for result in task_results)
            opened = sum(
                result.status == "open" and tracked_by_id[result.task_id].state != "blocked"
                for result in task_results
            )
            review = sum(result.status == "needs_review" for result in task_results)
            recovery_required = sum(tracked_by_id[result.task_id].state == "recovery_required" for result in task_results)
            blocked = sum(
                result.status == "blocked" or tracked_by_id[result.task_id].state == "blocked"
                for result in task_results
            )
            findings = tuple(sorted({finding.code for result in task_results for finding in result.findings}))
            outstanding = tuple(
                task_id for task_id, result in zip(task_ids, task_results)
                if result.status != "verified" or tracked_by_id[task_id].state == "blocked"
            )

            if blocked:
                status = "blocked"
                recommendation = "Resolve blocking integrity or evidence findings, then rerun closure verification."
            elif recovery_required:
                status = "recovery_required"
                recommendation = "Reconcile each interrupted task against authoritative external state; record an explicit reviewed decision before retrying or closing the investigation."
            elif opened:
                status = "open_tasks"
                recommendation = "Complete or explicitly block outstanding evidence tasks before assessing investigation closure."
            elif review or not closure_report.history_complete:
                status = "needs_review"
                recommendation = "Resolve review findings and establish authoritative history completeness before drawing conclusions."
            elif not task_results:
                status = "unplanned"
                recommendation = "Create and execute an evidence collection plan; no tracked tasks are associated with this hypothesis."
            elif hypothesis.disposition not in self._REVIEWED_DISPOSITIONS:
                status = "needs_review"
                recommendation = "Obtain an explicit, traceable assessment; task completion does not determine hypothesis disposition."
            else:
                status = "ready_for_expert_review"
                recommendation = "Submit the traceable evidence and explicit assessment for independent expert review; this is not proof of root cause or remediation."

            summaries.append(InvestigationHypothesisSummary(
                hypothesis_id=hypothesis_id,
                disposition=hypothesis.disposition,
                task_count=len(task_results),
                verified_task_count=verified,
                open_task_count=opened,
                needs_review_task_count=review,
                blocked_task_count=blocked,
                status=status,
                outstanding_task_ids=outstanding,
                finding_codes=findings,
                recommendation=recommendation, recovery_required_task_count=recovery_required,
            ))

        statuses = [item.status for item in summaries]
        return DiagnosticInvestigationClosureReport(
            hypotheses=tuple(summaries),
            history_complete=closure_report.history_complete,
            total_hypotheses=len(summaries),
            ready_for_expert_review_count=statuses.count("ready_for_expert_review"),
            needs_review_count=statuses.count("needs_review"),
            blocked_count=statuses.count("blocked"),
            open_count=statuses.count("open_tasks") + statuses.count("recovery_required"),
            unplanned_count=statuses.count("unplanned"),
            orphan_task_ids=tuple(sorted(orphan_task_ids)),
            total_recovery_required_count=sum(item.recovery_required_task_count for item in summaries),
        )
