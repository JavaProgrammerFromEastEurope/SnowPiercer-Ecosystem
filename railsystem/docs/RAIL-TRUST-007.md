# RAIL-TRUST-007 — Atomic Startup Publication & Recovery Fencing Verification

## Scope and requirements
- RAIL-TRUST-007-R1: Startup must acquire `admission.lock` before inspecting the SQLite/local/external anchor state, and hold it until socket bind, permissions, identity verification and listen complete.
- R2: Recovery and admission use the same lock through existing API paths; a PREPARED state blocks startup.
- R3: Existing library APIs remain callable for compatibility, but are NOT a proven non-bypassable production boundary.
- R4: A missing independent anchor provider fails closed.
- R5: Socket replacement, symlink and competing startup fail closed without unlinking attacker-owned paths.

## Contracts
`_inspect_fence_locked(directory, provider)` is an internal function requiring the caller to hold `admission.lock`. `inspect_fence` retains the prior public signature and acquires the lock itself. `ProductionBoundary.start` holds one lock across inspection and publication; `close` holds it while tearing down its socket. Nested flock acquisition is prohibited.

## Crash and concurrency analysis
`flock` is advisory and is released when the process exits, including SIGKILL. A crash during socket publication can leave a stale socket filesystem entry, which intentionally prevents startup until separately investigated. Recovery still requires a signed permit for the existing `recover_with_attestation` path. The tests cover lock-holder SIGKILL, not all admission/anchor crash windows.

## Safety analysis and open hazards
- **OPEN**: no independent hardware-backed monotonic anchor in this environment.
- **OPEN**: no unified transactional fence spanning active socket request handling, external CAS and SQLite; startup/close lock is narrower.
- **OPEN**: same-UID processes can call legacy library APIs; no enforceable process-wide mandatory admission.
- **OPEN**: no cross-UID privileged recovery broker or full UID isolation matrix.
- **OPEN**: no full SIGKILL injection matrix for all state transitions.
- **OPEN**: SQLite and anchor storage can be rolled back together by privileged attackers.
- **OPEN**: stale socket after SIGKILL requires operator intervention; socket pathname identity checks are not an immutable directory-handle defense.

## Verification
Run `PYTHONPATH=. python -W error::ResourceWarning -W error::DeprecationWarning -m unittest discover -s tests -v` from the project root. Tests are local software regression only, not safety certification. Python's unraisable destructor warnings can still print as `Exception ignored` without failing unittest; logs must be inspected for this condition.

## Release decision
**BLOCKED / NO-GO** pending independent provider, end-to-end crash matrix, cross-UID tests and production boundary closure.
