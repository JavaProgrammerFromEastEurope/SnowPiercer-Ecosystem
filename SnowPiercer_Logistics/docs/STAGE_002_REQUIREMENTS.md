# LOG-CORE-002 Requirements
- R-002-01: Preserve LOG-CORE-001 public model and ledger API.
- R-002-02: Derive IPC client UID from kernel peer credentials; reject unmapped UIDs.
- R-002-03: Bind configured UID to a role; never trust client-supplied principal.
- R-002-04: Reject concurrent live service startup; protect startup with advisory flock.
- R-002-05: Store recovery permits as SHA256 digests and consume atomically once.
- R-002-06: Refuse startup on missing, mismatched, or malformed checkpoint.
- R-002-07: Refuse symlink substitution of known ledger, checkpoint and socket paths.
- R-002-08: Run three strict regression suites and preserve evidence.
- R-002-09: Maintain production NO-GO without independently validated end-to-end assurance.
