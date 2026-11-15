# RAIL-SAFE-001 — Preliminary Hazard Analysis

Scope: preliminary hazard inventory and automated structural validation only. Six illustrative hazards; not a comprehensive safety assessment. Severity labels are qualitative screening labels, not calibrated risk scores. Likelihood is **unknown** for all hazards. Controls are **proposed**, not implemented or verified.

## Safety constraints
- All hazards remain open. No operational authorization.
- Hazards link to existing requirements and architectural components.
- No live actuator, braking, signaling, or movement authority interfaces are implemented.
- Closure is intentionally prohibited by this preliminary validator. A future reviewed safety case must define evidence integrity, independence, residual-risk acceptance, hazard closure, and authorization governance.
- A requirement reference does not demonstrate risk mitigation or requirement verification.

## Acceptance
Registry validation and regression tests pass. Formal safety review remains pending; RAIL-SAFE-001 is implemented as a preliminary artifact, not independently accepted. Physical operation: NO-GO.

Run: `python -m unittest discover -s tests -v`
