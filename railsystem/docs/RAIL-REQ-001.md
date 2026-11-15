# RAIL-REQ-001 — Requirements & Traceability

## Deliverables
- `requirements/registry.json`: 12 **proposed** baseline requirements; not approved specifications.
- `railsystem/requirements.py`: strict schema/foreign-key validation and coverage report.
- `tests/test_requirements.py`: positive and negative validation tests.

## Traceability rules
Each requirement has an immutable-style ID, statement, category, priority, owner component,
planned verification method, planned Stage, lifecycle status, and evidence references.
A verified status requires nonempty evidence references, but **the validator does not authenticate
or execute evidence**. Independent review and an evidence provenance mechanism are still required.

## Safety boundary
This is a planning and documentation tool, not a safety case or operational control system.
No movement authority, actuation, or safety certification is claimed.

## Acceptance
- Registry loads and resolves component IDs against RAIL-ARCH-001.
- All eight architecture components are covered by at least one requirement.
- Invalid IDs, classifications, stage references, and false verification claims are rejected.
- Full local unittest suite passes.
- Formal requirements approval remains pending; Stage is **implemented, review pending**.
