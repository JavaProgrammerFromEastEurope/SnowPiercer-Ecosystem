# ISLAND-GEO-005 — Consistency & conservative escalation

## Scope
`island.consistency` introduces `Scenario`, `assess_scenarios` and `escalate_asset_risks` without changing earlier APIs. Scenario windows and path IDs must match. Unknown required observations or conductivity invalidate every numeric union bound, and produce escalation flags. Directed edge admission is required for risk propagation.

## Safety limitations
All observations are synthetic; the model uses piecewise-linear heads and a static 1D Darcy approximation. It does not solve transient groundwater PDEs, quantify probability, or prove containment in physical infrastructure. Risk escalation is logical only. No physical deployment authorization is possible.

## Verification
Run `PYTHONPATH=. python -W error::ResourceWarning -W error::DeprecationWarning -m unittest discover -s tests -v`. The historical Stage files remain included.
