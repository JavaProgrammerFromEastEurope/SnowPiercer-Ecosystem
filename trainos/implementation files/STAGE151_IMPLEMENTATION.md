# TrainOS Stage 151 — unknown external outcome after restart

This stage adds focused regression coverage for interrupted diagnostic tasks when a process exits after dispatch but before receiving a definitive acknowledgement.

The existing `InterruptedTaskReconciler` is intentionally read-only. Tests establish that:

- no external observation means the task remains `recovery_required`;
- `partial_or_unknown` never recommends a retry;
- an observation claiming completion still requires independent verification and is not applied automatically;
- conflicting observations for the same task block a decision;
- malformed observations and observations for tasks outside `recovery_required` cannot justify retry.

No production code changes were necessary. Observations are caller-supplied assertions, not proof that an authoritative source was actually queried. Any retry remains a separate explicit, reviewed decision; this component does not dispatch or repeat external commands.
