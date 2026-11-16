# ISLAND-GEO-006 — Evidence provenance and scenario admission

EvidenceRecord binds source ID, positive version, observation ID and SHA-256 of raw evidence bytes. SourcePolicy is an explicit caller-supplied allowlist of version and digests. Admission checks complete knot coverage for both hydraulic boundaries and conductivity, duplicates, source-version mismatches, missing bytes, digest mismatches, and inherited scenario consistency. Rejected inputs suppress ALL numeric envelopes and emit conservative risk flags.

**Trust limitation:** A digest detects modification relative to a supplied allowlist but cannot authenticate its origin; an adversary controlling both allowlist and bytes can forge provenance. No signatures, PKI, OS isolation, independent witnesses, laboratory attestations, calibration evidence, or site data are present. The observation bytes are not independently parsed or checked against numerical model values; provenance binding is to an observation identifier, not verified measurement semantics. This is NOT an engineering approval mechanism.

Cross-asset propagation remains a software-only directed graph. Hazard mitigations OPEN. Physical readiness BLOCKED/NO-GO.
