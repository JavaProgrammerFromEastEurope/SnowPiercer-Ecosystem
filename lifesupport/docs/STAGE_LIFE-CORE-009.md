# LIFE-CORE-009 — Trusted Configuration Anchoring & Integrity Enforcement

Run: `PYTHONPATH=src python -m unittest discover -s tests -v`

Enrollment: create `TrustedLifecycle(registry, db_path, anchor_path=..., secret=32_byte_secret)`, acquire a lease, `protect(token)`, `harden(token)`, `establish_anchor(token)`. Afterwards `verify_anchor()` checks external HMAC and local guard configuration. To publish a new epoch floor, acquire a new lease and call `advance_anchor(token)`.

The key must be managed outside the repository. Keep a separate secure backup of the anchor and key. No physical device actuation is supported.
