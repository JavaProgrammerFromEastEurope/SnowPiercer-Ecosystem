# Safety and threat analysis
- Concurrent startup: fail-closed nonblocking lifetime flock; locally tested. Same UID can still modify files outside IPC.
- Socket substitution: symlink/file checks; path replacement races and stale socket handling not exhaustively tested.
- SQLite rollback: local checkpoint detects some mismatch, but coordinated rollback of SQLite+checkpoint is NOT detectable without independent anchor.
- Phase journal tampering: metadata checks and schema checks at startup; no cryptographic authentication.
- Recovery permits: stored in same mutable DB, not externally witnessed; cannot defend against privileged rollback.
- SIGKILL: inherited single crash test only; no complete fault injection across all boundaries.
- Cross-UID: UID extraction implemented; no distinct real-UID E2E test performed in this stage.
- Legacy bypass: public library can write DB directly if OS permissions permit; OS-enforced fencing absent.
- Physical actuation: not implemented; no real-world safety certification.
DECISION: BLOCKED / NO-GO.
