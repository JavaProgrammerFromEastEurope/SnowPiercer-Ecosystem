# LOG-CORE-021 limits and operational decision

Decision: **BLOCKED / NO-GO** for production, robotics, drones and physical
transport operations. Programmatic tests verify the named local contracts only.

- No four-independent-UID production ledger/witness/authority/client transaction
  has been implemented or accepted by this stage.
- No OS enforcement across every legacy entrypoint is established. The opt-in
  subclass rejects direct writes, but the original public ledger remains a
  separate development library and the SQLite owner can bypass Python methods.
- `Principal` and the clock are trusted host dependencies. Their remote
  authentication, clock synchronization and resistance to a compromised host
  are outside this adapter. A clock regression before `issued_at_ms` rejects a
  command; other adversarial clock manipulation is not solved.
- An event-count revision and a local SHA-256 receipt are not anti-rollback,
  externally witnessed state or a distributed exactly-once guarantee.
- Admission checks the deadline before a local operation, not after physical
  completion. There is no physical actuation or duration/safety bound here.
- This stage adds no exhaustive SIGKILL, four-UID E2E, deployment certification,
  payload mass/collision/geofence safety or independent review.
- Source audit: current `evidence/stage020_manifest.json` matched all 242
  entries before changes. The older root manifest had two stale version entries
  (`pyproject.toml`, `snowpiercer_logistics/__init__.py`), retained as history.

New stage021 evidence is separate. Passing regression and the shared correlation
probe must not be presented as resolving these operational gaps.
