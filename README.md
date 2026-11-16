# SnowPiercer Island v0.23.0 — cumulative source (ISLAND-GEO-022)

## ISLAND-GEO-022 — Independent Monotonic Witness Root & OS-MAC Legacy Confinement

**Partial functional implementation; production security and physical works remain BLOCKED/NO-GO.**

This release adds an Ed25519-signed, challenge-fresh remote root protocol; six distinct OS-principal laboratory roles; split witness SQLite and state-bound recovery authority SQLite; fail-closed witness/root reconciliation; an explicit strict production gate that refuses to start without independently verified hardware monotonic root, OS-MAC same-UID broker confinement, and an independent service-manager lifecycle. A `SoftwareRootServer` is provided **ONLY as a rollbackable test fixture**; it cannot satisfy the production gate. Historical libraries/entrypoints are retained, with one backward-compatible `_authority_client` extension of `AttestedWriteBroker`.

- Modules: `island.monotonic_root`, `island.split_authorities`, `island.host_security`, `island.secure_runtime`.
- Unit tests: `tests/test_stage023.py`. Full strict suite: `PYTHONDONTWRITEBYTECODE=1 PYTHONWARNINGS=error::ResourceWarning,error::DeprecationWarning python -m unittest discover -s tests -v`.
- Linux six-UID lab harness (disposable privileged root controller only): `python tests/stage023_sixuid.py`. Contains actual peer credentials, UID access denials, 17 broker SIGKILL/recovery boundaries, independent permit-consume SIGKILL, root genesis rollback, selected tampering, and process evidence. Does not prove immutable monotonic hardware or kernel MAC confinement.
- Results: **3 complete strict suites × 200 PASS = 600 PASS**; **27/27 lab E2E check groups PASS**; **17/17 actual broker SIGKILL + restart PASS**, plus one permit-consume SIGKILL PASS. Initial FAIL and interrupted harness logs retained.
- Detailed requirements: `models/requirements.json`. Protocol contract: `contracts/monotonic_root_mac_v1.json`. Safety analysis: `docs/stage023_safety.md`. Architecture: `docs/stage023_architecture.md`. OS requirements: `deployment/README.md`. Evidence and machine-readable coverage: `evidence/stage023-coverage.json`.
- Not verified: trusted hardware monotonic anti-rollback root; full rollback of root+ledger+witness+permits+keys to genesis; loaded MAC policy blocking same-broker-UID legacy Python code; OS service manager/watcher independent restart; power-loss persistence; exhaustive killpoints inside root/witness/permit services; complete storage/socket interleaving coverage. These are mandatory remaining production criteria.

**Production Security: BLOCKED/NO-GO. Physical Construction & Operations: BLOCKED/NO-GO.**

---

# SnowPiercer Island v0.22.0 — cumulative source (ISLAND-GEO-021)

Historical release notes follow.

## Historical ISLAND-GEO-015 (v0.16.0)

Cumulative stages 001–015 retained, with new experimental `island.bound_recovery`.

**Partial Stage implementation.** State-bound one-use permits are tested as a library component, but are not integrated into the inherited production service. No complete OS-enforced legacy fencing, independent rollback-resistant witness, direct client attestation, or exhaustive production IPC SIGKILL proof.

**Production security: BLOCKED/NO-GO. Physical construction and operations: BLOCKED/NO-GO.**

Run: `PYTHONWARNINGS=error::ResourceWarning,error::DeprecationWarning python -m unittest discover -s tests -v`.

## ISLAND-GEO-016 (v0.17.0)

Experimental bound-permit IPC authority and pinned witness peer. The software regression is not a production security proof. See docs/stage017_architecture.md and evidence/stage017-coverage.json. Production security and physical operations remain BLOCKED/NO-GO.

## ISLAND-GEO-017 / v0.18.0

Linux isolated runtime: `python -m island.isolated_runtime`; cross-UID harness: `python tests/stage018_multiuid.py` (requires root in disposable Linux test host). Root-owned sticky 01777 IPC directory, group-mode 0660 sockets, separate private 0700 storage. Real 3-UID admission, permit, access-denial, replay, SIGKILL and witness genesis rollback tested. See `docs/stage017_architecture.md` and `evidence/stage018-coverage.json`. This does not prove OS-enforced legacy fencing or exhaustive crash resilience. Production and physical readiness remain BLOCKED/NO-GO.


## ISLAND-GEO-018 / v0.19.0

Adds `island.production_guard` and six cumulative unit checks. The new verifier is not wired into every production path. Three full strict-warning regressions each pass 163 tests. See `docs/stage019_architecture.md` and `evidence/stage019-coverage.json`. OS-enforced legacy production fencing, independent witness, complete adversarial UID tests and exhaustive SIGKILL are NOT VERIFIED. Production and physical deployment remain BLOCKED/NO-GO.

## ISLAND-GEO-019 / Island v0.20.0

Experimental guarded production entrypoint `island.guarded_runtime`; private storage/SQLite sidecar validation, witness peer UID verification and exclusive lifetime startup lease. 3 full regression runs and a limited Linux three-UID E2E harness are recorded in `evidence/`. **Independent production security and physical deployment: BLOCKED/NO-GO**. Legacy service-UID bypass and exhaustive crash-point verification remain open.

## ISLAND-GEO-020 (v0.21.0)
Experimental UID-separated write broker and facade (`island.write_broker`, `island.broker_runtime`). See `docs/stage021_architecture.md`. Not independently production certified; production security and physical construction remain BLOCKED/NO-GO.

## ISLAND-GEO-021 (Island v0.22.0)

Client-signed Ed25519 admission with broker-side signature verification, durable
nonce burns, peer-credential pinned four-role Linux IPC and independent client-origin
state-bound startup permits. Test harness: `python tests/stage022_fouruid.py`
(requires a disposable Linux root test controller). Regression:
`PYTHONWARNINGS=error::ResourceWarning,error::DeprecationWarning python -m unittest discover -s tests -v`.

**Production security is BLOCKED/NO-GO.** Broker-UID code may still invoke legacy
Python APIs directly; no MAC/LSM execution confinement, hardware monotonic root,
fully independent witness, or production-grade power-cut proof has been certified.
**Physical construction and operations: BLOCKED/NO-GO.**

Stage 021 strict regression: 3 × 184 PASS. Privileged disposable Linux four-UID E2E: 27 check groups PASS, 17/17 real broker SIGKILL and restart checks PASS. See evidence/stage022-coverage.json. OS MAC and independent monotonic root remain missing; NO-GO.
