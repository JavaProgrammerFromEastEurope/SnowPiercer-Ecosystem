# RAIL-VER-001 — Verification Infrastructure & Regression Evidence

Status: locally implemented; independent verification and CI integration pending.

## Scope

- Stage-to-test-file registry with explicit coverage checks.
- Standard-library unittest discovery and machine-readable JSON evidence.
- SHA-256 manifest of source, documentation, registries, and tests.
- Explicit UTC evidence timestamp and rejection of reports written inside source tree.
- No actuating interfaces, no physical train control.

## Limitations

- SHA-256 hashes establish byte-level integrity against a separately trusted manifest, not authorship or provenance.
- The evidence records test counts and failures; it does not establish requirement verification or railway safety certification.
- Test discovery and file-to-stage mapping are not per-test requirement traceability.
- CI execution, signing, reproducible environments, independent review, and hardware-in-loop validation remain outstanding.

## Acceptance

Run `python -m unittest discover -s tests -v` and `python -m railsystem.verify_cli --output ../RailSystem_v0.8_evidence.json`. Review the report and manifest externally.
